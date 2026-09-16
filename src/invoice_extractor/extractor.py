from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Iterable


def amount(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc


def totals_reconcile(subtotal: object, tax: object, total: object, line_totals: Iterable[object]) -> bool:
    try:
        values = amount(subtotal), amount(tax), amount(total)
        line_sum = sum((amount(value) for value in line_totals), Decimal("0"))
    except ValueError:
        return False
    return line_sum == values[0] and values[0] + values[1] == values[2]


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class Invoice:
    vendor: str
    invoice_number: str
    issue_date: str
    due_date: str
    currency: str
    items: tuple[LineItem, ...]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    reconciled: bool
    extraction_stage: str = "deterministic"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["items"] = [asdict(item) for item in self.items]
        for key in ("subtotal", "tax", "total"):
            result[key] = f"{result[key]:.2f}"
        for item in result["items"]:
            item["unit_price"] = f"{item['unit_price']:.2f}"
            item["line_total"] = f"{item['line_total']:.2f}"
        return result


FIELD_PATTERNS = {
    "vendor": r"Vendor:\s*(.+)",
    "invoice_number": r"Invoice Number:\s*(\S+)",
    "issue_date": r"Issue Date:\s*(\d{4}-\d{2}-\d{2})",
    "due_date": r"Due Date:\s*(\d{4}-\d{2}-\d{2})",
    "currency": r"Currency:\s*([A-Z]{3})",
    "subtotal": r"Subtotal:\s*([\d.]+)",
    "tax": r"Tax:\s*([\d.]+)",
    "total": r"Total:\s*([\d.]+)",
}


def invoice_from_dict(raw: dict[str, object], extraction_stage: str = "deterministic") -> Invoice:
    required = {"vendor", "invoice_number", "issue_date", "due_date", "currency", "items", "subtotal", "tax", "total"}
    missing = required - raw.keys()
    raw_items = raw.get("items")
    if missing or not isinstance(raw_items, (list, tuple)) or not raw_items:
        raise ValueError(f"Invoice failed schema validation; missing={sorted(missing)}")
    try:
        items = tuple(
            item if isinstance(item, LineItem) else LineItem(
                description=str(item["description"]).strip(),
                quantity=int(item["quantity"]),
                unit_price=amount(item["unit_price"]),
                line_total=amount(item["line_total"]),
            )
            for item in raw_items
        )
        subtotal, tax, total = (amount(raw[key]) for key in ("subtotal", "tax", "total"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invoice contains invalid line items or financial values") from exc
    reconciled = (
        all(item.quantity * item.unit_price == item.line_total for item in items)
        and totals_reconcile(subtotal, tax, total, (item.line_total for item in items))
    )
    return Invoice(
        vendor=str(raw["vendor"]).strip(),
        invoice_number=str(raw["invoice_number"]).strip(),
        issue_date=str(raw["issue_date"]).strip(),
        due_date=str(raw["due_date"]).strip(),
        currency=str(raw["currency"]).strip(),
        items=items,
        subtotal=subtotal,
        tax=tax,
        total=total,
        reconciled=reconciled,
        extraction_stage=extraction_stage,
    )


def extract_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install project dependencies before reading PDFs") from exc
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def extract_invoice(path: Path) -> Invoice:
    text = extract_text(path)
    fields: dict[str, str] = {}
    for name, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"Required field {name!r} not found in {path.name}")
        fields[name] = match.group(1).strip()
    item_pattern = re.compile(r"^(.+?)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*$", re.MULTILINE)
    items = [
        {"description": match.group(1).strip(), "quantity": match.group(2), "unit_price": match.group(3), "line_total": match.group(4)}
        for match in item_pattern.finditer(text)
        if "Description" not in match.group(1)
    ]
    if not items:
        raise ValueError(f"No line items found in {path.name}")
    return invoice_from_dict({**fields, "items": items})
