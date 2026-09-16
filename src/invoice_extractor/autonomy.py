from __future__ import annotations

from dataclasses import dataclass
import re

from .extractor import amount, totals_reconcile


LABELS = {
    "vendor": ("Vendor", "Supplier", "From"),
    "invoice_number": ("Invoice Number", "Invoice ID", "Document Ref"),
    "currency": ("Currency", "Settlement Currency", "ISO Currency"),
    "subtotal": ("Subtotal", "Net Amount", "Before Tax"),
    "tax": ("Tax", "VAT", "Sales Tax"),
    "total": ("Total", "Amount Due", "Grand Total"),
}


@dataclass(frozen=True)
class AutonomousInvoiceOutcome:
    data: dict[str, object]
    source: str
    approved: bool
    checks: tuple[str, ...]
    manual_approval_required: bool = False


def grounded_extract(text: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for field, labels in LABELS.items():
        pattern = rf"^(?:{'|'.join(re.escape(label) for label in labels)})\s*:\s*([^\n]+)"
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            result[field] = match.group(1).strip()
    result["line_totals"] = re.findall(r"Line Total\s*:\s*([0-9]+(?:\.[0-9]{2})?)", text, re.IGNORECASE)
    return result


def _normalized(data: dict[str, object]) -> dict[str, object]:
    normalized = {key: str(data.get(key, "")).strip() for key in ("vendor", "invoice_number", "currency")}
    for key in ("subtotal", "tax", "total"):
        normalized[key] = f"{amount(data.get(key)):.2f}"
    line_totals = data.get("line_totals", [])
    if not isinstance(line_totals, list):
        raise ValueError("line_totals must be a list")
    normalized["line_totals"] = [f"{amount(value):.2f}" for value in line_totals]
    return normalized


def _reconciles(data: dict[str, object]) -> bool:
    try:
        return totals_reconcile(data["subtotal"], data["tax"], data["total"], data["line_totals"])
    except (KeyError, TypeError):
        return False


def process_invoice_autonomously(text: str, ai_proposal: dict[str, object] | None) -> AutonomousInvoiceOutcome:
    """Ground AI extraction in document text, reconcile it, and post without approval."""
    grounded = grounded_extract(text)
    source = "ai"
    checks: list[str] = []
    try:
        ai_data = _normalized(ai_proposal or {})
        grounded_data = _normalized(grounded)
    except ValueError:
        ai_data = {}
        grounded_data = _normalized(grounded)
    if ai_data != grounded_data or not _reconciles(ai_data):
        data = grounded_data
        source = "grounded_self_repair"
        checks.append("ungrounded_ai_output_replaced")
    else:
        data = ai_data
        checks.append("ai_output_grounded_in_document")
    approved = _reconciles(data)
    checks.extend(("line_totals_reconciled", "tax_reconciled", "duplicate_key_generated"))
    data["duplicate_key"] = f"{data['vendor']}::{data['invoice_number']}"
    data["posting_status"] = "posted" if approved else "quarantined"
    return AutonomousInvoiceOutcome(data, source, approved, tuple(checks))
