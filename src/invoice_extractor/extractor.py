from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
import re


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
    items = tuple(
        LineItem(description=match.group(1).strip(), quantity=int(match.group(2)), unit_price=Decimal(match.group(3)), line_total=Decimal(match.group(4)))
        for match in item_pattern.finditer(text)
        if "Description" not in match.group(1)
    )
    if not items:
        raise ValueError(f"No line items found in {path.name}")
    subtotal, tax, total = (Decimal(fields[key]) for key in ("subtotal", "tax", "total"))
    line_items_match = sum(item.line_total for item in items) == subtotal
    multiplication_match = all(item.quantity * item.unit_price == item.line_total for item in items)
    reconciled = line_items_match and multiplication_match and subtotal + tax == total
    return Invoice(
        vendor=fields["vendor"], invoice_number=fields["invoice_number"], issue_date=fields["issue_date"],
        due_date=fields["due_date"], currency=fields["currency"], items=items,
        subtotal=subtotal, tax=tax, total=total, reconciled=reconciled,
    )
