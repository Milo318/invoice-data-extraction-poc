from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from .extractor import extract_invoice
from .generator import generate_pdfs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/mock/invoices.json"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("output/pdfs"))
    parser.add_argument("--output", type=Path, default=Path("proof/benchmark.json"))
    args = parser.parse_args()
    truth = {item["invoice_number"]: item for item in json.loads(args.source.read_text(encoding="utf-8"))}
    pdfs = generate_pdfs(args.source, args.pdf_dir)
    started = perf_counter()
    extracted = [extract_invoice(path) for path in pdfs]
    elapsed = perf_counter() - started
    scalar_fields = ("vendor", "invoice_number", "issue_date", "due_date", "currency", "subtotal", "tax", "total")
    correct = total = 0
    for invoice in extracted:
        expected = truth[invoice.invoice_number]
        values = invoice.to_dict()
        for field in scalar_fields:
            expected_value = f"{expected[field]:.2f}" if field in {"subtotal", "tax", "total"} else expected[field]
            correct += values[field] == expected_value
            total += 1
    result = {
        "synthetic_data": True,
        "pdfs_processed": len(pdfs),
        "scalar_fields_compared": total,
        "field_accuracy_percent": round(correct / total * 100, 2),
        "financial_reconciliation_percent": round(sum(item.reconciled for item in extracted) / len(extracted) * 100, 2),
        "processing_time_ms": round(elapsed * 1000, 3),
        "average_ms_per_pdf": round(elapsed * 1000 / len(pdfs), 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
