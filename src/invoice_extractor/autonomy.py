from __future__ import annotations

from dataclasses import dataclass
import re

from .extractor import amount, totals_reconcile, SUPPORTED_CURRENCIES
from hashlib import sha256
import json


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
        pattern = (
            rf"^(?:{'|'.join(re.escape(label) for label in labels)})\s*:\s*([^\n]+)"
        )
        matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous document field: {field}")
        result[field] = matches[0].group(1).strip()
    result["line_totals"] = re.findall(
        r"Line Total[ \t]*:[ \t]*([^\n]+)", text, re.IGNORECASE
    )
    return result


def _normalized(data: dict[str, object]) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ValueError("Invoice proposal must be an object")
    normalized = {
        key: str(data.get(key, "")).strip()
        for key in ("vendor", "invoice_number", "currency")
    }
    if (
        any(
            not isinstance(data.get(key), str) or not data[key].strip()
            for key in ("vendor", "invoice_number", "currency")
        )
        or normalized["currency"] not in SUPPORTED_CURRENCIES
    ):
        raise ValueError("Invoice identity or currency invalid")
    for key in ("subtotal", "tax", "total"):
        normalized[key] = f"{amount(data.get(key)):.2f}"
    line_totals = data.get("line_totals", [])
    if not isinstance(line_totals, list) or not line_totals:
        raise ValueError("line_totals must be a list")
    normalized["line_totals"] = [f"{amount(value):.2f}" for value in line_totals]
    return normalized


def _reconciles(data: dict[str, object]) -> bool:
    try:
        return totals_reconcile(
            data["subtotal"], data["tax"], data["total"], data["line_totals"]
        )
    except (KeyError, TypeError):
        return False


def process_invoice_autonomously(
    text: str, ai_proposal: dict[str, object] | None
) -> AutonomousInvoiceOutcome:
    """Return validated data or quarantine; never claim an external posting."""
    checks = []
    try:
        grounded_data = _normalized(grounded_extract(text))
    except (ValueError, TypeError):
        return AutonomousInvoiceOutcome(
            {"posting_status": "quarantined"},
            "document_rejected",
            False,
            ("missing_or_ambiguous_document_fields",),
        )
    try:
        ai_data = _normalized(ai_proposal)
    except (ValueError, TypeError):
        ai_data = None
    if ai_data != grounded_data or not _reconciles(grounded_data):
        data = grounded_data
        source = "grounded_self_repair"
        checks.append("ungrounded_ai_output_replaced")
    else:
        data = ai_data
        source = "ai"
        checks.append("ai_output_grounded_in_document")
    approved = _reconciles(data)
    checks.append(
        "financial_reconciliation_passed"
        if approved
        else "financial_reconciliation_failed"
    )
    # The key is an identity hint. Duplicate detection requires persistent storage.
    identity = json.dumps([data["vendor"], data["invoice_number"]], ensure_ascii=False)
    data["duplicate_key"] = sha256(identity.encode()).hexdigest()
    data["posting_status"] = "ready_for_posting" if approved else "quarantined"
    return AutonomousInvoiceOutcome(data, source, approved, tuple(checks))
