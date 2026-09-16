from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ai import extract_unstructured_invoice
from .extractor import extract_invoice, extract_text
from .generator import generate_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and reconcile structured invoice data from PDFs.")
    parser.add_argument("--source", type=Path, default=Path("data/mock/invoices.json"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("output/pdfs"))
    parser.add_argument("--output", type=Path, default=Path("output/extracted.json"))
    parser.add_argument("--ai-fallback", action="store_true")
    args = parser.parse_args()
    generated = generate_pdfs(args.source, args.pdf_dir)
    results: list[dict[str, object]] = []
    for path in generated:
        try:
            results.append(extract_invoice(path).to_dict())
        except ValueError:
            if not args.ai_fallback:
                raise
            results.append(extract_unstructured_invoice(extract_text(path)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdfs_generated": len(generated), "invoices_extracted": len(results), "reconciled": sum(bool(item.get("reconciled")) for item in results)}, indent=2))


if __name__ == "__main__":
    main()
