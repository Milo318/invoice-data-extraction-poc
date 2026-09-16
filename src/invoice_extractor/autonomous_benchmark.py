from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import urllib.request

from .autonomy import LABELS, process_invoice_autonomously


@dataclass(frozen=True)
class InvoiceCase:
    case_id: str
    text: str
    truth: dict[str, object]


VENDORS = ("Northstar Office GmbH", "Harbor Cloud Services", "Clearview Analytics Ltd", "Alpine Data Works")


def generate_cases(count: int) -> list[InvoiceCase]:
    cases: list[InvoiceCase] = []
    for index in range(count):
        vendor = VENDORS[index % len(VENDORS)]
        invoice_number = f"MOCK-AUTO-{1000 + index}"
        first = Decimal(40 + index % 31) * Decimal(2)
        second = Decimal(15 + index % 17) * Decimal(3)
        subtotal = first + second
        tax = (subtotal * Decimal("0.19")).quantize(Decimal("0.01"))
        total = subtotal + tax
        variant = index % 3
        labels = {field: options[variant] for field, options in LABELS.items()}
        truth = {
            "vendor": vendor, "invoice_number": invoice_number, "currency": "EUR",
            "subtotal": f"{subtotal:.2f}", "tax": f"{tax:.2f}", "total": f"{total:.2f}",
            "line_totals": [f"{first:.2f}", f"{second:.2f}"],
        }
        text = (
            "SYNTHETIC AUTONOMY BENCHMARK INVOICE\n"
            f"{labels['vendor']}: {vendor}\n{labels['invoice_number']}: {invoice_number}\n"
            f"{labels['currency']}: EUR\nItem: Automation service | Line Total: {first:.2f}\n"
            f"Item: Data validation | Line Total: {second:.2f}\n{labels['subtotal']}: {subtotal:.2f}\n"
            f"{labels['tax']}: {tax:.2f}\n{labels['total']}: {total:.2f}\n"
        )
        cases.append(InvoiceCase(f"INVOICE-{index:03d}", text, truth))
    return cases


def create_and_read_pdfs(cases: list[InvoiceCase], directory: Path) -> dict[str, str]:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader
    extracted: dict[str, str] = {}
    for case in cases:
        path = directory / f"{case.case_id}.pdf"
        pdf = canvas.Canvas(str(path), pagesize=A4)
        y = 800
        for line in case.text.splitlines():
            pdf.drawString(50, y, line)
            y -= 18
        pdf.save()
        extracted[case.case_id] = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return extracted


def ask_ollama(batch: list[InvoiceCase], texts: dict[str, str], model: str, url: str) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    items = [{"case_id": case.case_id, "document_text": texts[case.case_id]} for case in batch]
    prompt = (
        "Extract every invoice. Return JSON with a results array. Every item needs case_id, vendor, invoice_number, "
        "currency, subtotal, tax, total, and line_totals as an array. Copy values exactly; do not calculate replacements.\n\n"
        + json.dumps(items)
    )
    payload = {"model": model, "stream": False, "format": "json", "keep_alive": "10m", "options": {"temperature": 0, "num_predict": 1900}, "messages": [{"role": "system", "content": "You extract grounded invoice fields. Output JSON only."}, {"role": "user", "content": prompt}]}
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = json.load(response)
    parsed = json.loads(raw["message"]["content"])
    results = parsed.get("results", parsed if isinstance(parsed, list) else [])
    return {str(item.get("case_id")): item for item in results if isinstance(item, dict)}, {"prompt_tokens": int(raw.get("prompt_eval_count", 0)), "completion_tokens": int(raw.get("eval_count", 0))}


def run(count: int, model: str, url: str, batch_size: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    cases = generate_cases(count)
    with TemporaryDirectory() as temporary:
        texts = create_and_read_pdfs(cases, Path(temporary))
        started = time.perf_counter()
        proposals: dict[str, dict[str, object]] = {}
        prompt_tokens = completion_tokens = 0
        for index in range(0, count, batch_size):
            result, usage = ask_ollama(cases[index:index + batch_size], texts, model, url)
            proposals.update(result)
            prompt_tokens += usage["prompt_tokens"]
            completion_tokens += usage["completion_tokens"]
        rows: list[dict[str, object]] = []
        for case in cases:
            proposal = proposals.get(case.case_id)
            direct = all(str((proposal or {}).get(key, "")) == str(value) for key, value in case.truth.items() if key != "line_totals") and (proposal or {}).get("line_totals") == case.truth["line_totals"]
            outcome = process_invoice_autonomously(texts[case.case_id], proposal)
            correct = all(outcome.data.get(key) == value for key, value in case.truth.items())
            rows.append({"case_id": case.case_id, "ai_direct_pass": direct, "decision_source": outcome.source, "financially_reconciled": outcome.approved, "truth_match": correct, "approved": outcome.approved and correct})
    elapsed = time.perf_counter() - started
    direct = sum(row["ai_direct_pass"] for row in rows)
    approved = sum(row["approved"] for row in rows)
    summary = {
        "benchmark": "autonomous_invoice_processing_v1", "live_model": True, "model": model,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "synthetic_data": True,
        "benchmark_cases": count, "pdfs_generated_and_read": count, "minimum_required_cases": 100,
        "ai_direct_passed": direct, "ai_direct_pass_rate_percent": round(direct / count * 100, 2),
        "final_approved": approved, "approval_rate_percent": round(approved / count * 100, 2),
        "required_approval_rate_percent": 95.0, "acceptance_gate_passed": count >= 100 and approved / count > 0.95,
        "manual_approvals_required": 0, "automatic_self_repairs": sum(row["decision_source"] == "grounded_self_repair" for row in rows),
        "financial_reconciliation_passed": sum(row["financially_reconciled"] for row in rows),
        "elapsed_seconds": round(elapsed, 3), "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "case_generator_sha256": sha256("".join(case.text for case in cases).encode()).hexdigest(),
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=120)
    parser.add_argument("--model", default="granite4.1:3b")
    parser.add_argument("--url", default="http://localhost:11434/api/chat")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("proof/autonomous-benchmark.json"))
    parser.add_argument("--case-output", type=Path, default=Path("proof/autonomous-cases.jsonl"))
    args = parser.parse_args()
    if args.cases < 100:
        raise SystemExit("At least 100 cases are required")
    summary, rows = run(args.cases, args.model, args.url, args.batch_size)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    args.case_output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["acceptance_gate_passed"]:
        raise SystemExit("Acceptance gate failed")


if __name__ == "__main__":
    main()
