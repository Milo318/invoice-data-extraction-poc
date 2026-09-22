from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ai import extract_unstructured_invoice
from .extractor import extract_invoice, extract_text
from .generator import generate_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and reconcile structured invoice data from PDFs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Existing PDF or directory of PDFs; omit to generate the synthetic demo",
    )
    parser.add_argument("--source", type=Path, default=Path("data/mock/invoices.json"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("output/pdfs"))
    parser.add_argument("--output", type=Path, default=Path("output/extracted.json"))
    parser.add_argument("--ai-fallback", action="store_true")
    args = parser.parse_args()
    if args.input:
        generated = (
            [args.input]
            if args.input.is_file() and args.input.suffix.lower() == ".pdf"
            else sorted(args.input.glob("*.pdf"))
            if args.input.is_dir()
            else []
        )
        if not generated:
            raise ValueError("No PDF inputs found")
    else:
        generated = generate_pdfs(args.source, args.pdf_dir)
    results: list[dict[str, object]] = []
    failures = []
    for path in generated:
        try:
            try:
                result = extract_invoice(path).to_dict()
            except ValueError:
                if not args.ai_fallback:
                    raise
                # AI-only results are proposals: arithmetic cannot prove provenance.
                result = extract_unstructured_invoice(extract_text(path))
                result["review_required"] = True
            if not result["reconciled"]:
                raise ValueError("Invoice totals do not reconcile")
            results.append(result)
        except Exception as error:
            # A malformed PDF or unavailable provider quarantines this file only.
            failures.append(
                {
                    "file": path.name,
                    "status": "quarantined",
                    "error_type": type(error).__name__,
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    quarantine = args.output.with_name(args.output.stem + ".quarantine.json")
    quarantine.write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pdfs_processed": len(generated),
                "invoices_extracted": len(results),
                "quarantined": len(failures),
            },
            indent=2,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
