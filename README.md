# Validated PDF Invoice Extraction

Extract invoice data with exact quantities, financial checks and explicit quarantine.

[![Quality](https://github.com/Milo318/invoice-data-extraction-poc/actions/workflows/ci.yml/badge.svg)](https://github.com/Milo318/invoice-data-extraction-poc/actions/workflows/ci.yml)

## What the current implementation guarantees

- Preserve fractional quantities instead of silently converting them to integers.
- Validate nonempty identities, ISO dates, supported currencies and finite monetary values.
- Reconcile quantity × unit price, line sums, subtotal, tax and total.
- Reject missing or conflicting labeled document fields.
- Process existing PDFs and isolate malformed documents into a quarantine report.
- Return `ready_for_posting` for accepted text extraction; no external accounting posting occurs.

## Run

Requires Python 3.11 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m invoice_extractor.cli
python -m invoice_extractor.cli --input /path/to/pdfs --output output/invoices.json
python -m invoice_extractor.benchmark --output /tmp/invoice-benchmark.json
```

## Scope and integration contract

Without `--input`, the CLI generates and extracts the bundled synthetic demo PDFs. With
`--input`, it reads an existing PDF or directory. Successful rows go to the requested JSON;
failures go to `<output-stem>.quarantine.json`. Any quarantined input produces exit code 1
while preserving successful results.

The deterministic parser supports labeled text PDFs. Supported currencies are EUR, USD,
GBP and CHF, using nonnegative amounts with at most two decimal places. Quantities support
up to six decimal places. Scans need a separate OCR adapter; credit notes and arbitrary
layouts are outside the current contract.

`--ai-fallback` uses `LLM_API_KEY` (optional `LLM_MODEL`/`LLM_API_URL`). Its arithmetic-checked
results carry `review_required: true`: arithmetic alone cannot prove that proposed values
occur in the document. The separate grounded text controller rejects unknown or ambiguous
documents and returns a posting decision. A duplicate key is only an identity hint;
actual duplicate detection requires persistent storage.

## Verification

```bash
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
```

CI runs these checks and a fresh deterministic benchmark on Python 3.11 and 3.13.
Tests include malformed inputs, known regression cases and mocked provider failures.
No credentials or live model calls are needed for the test suite. Provider responses have
size limits, JSON-object validation and bounded retries for transient failures.

## Benchmark evidence

All bundled datasets are synthetic. `proof/benchmark.json` records a deterministic demo
run; it does not establish performance on arbitrary customer data. The older
`proof/autonomous-benchmark.json`, case JSONL and portfolio image are **historical v1.0.0
artifacts**, not quality or accuracy guarantees for v1.1.0. Their archive-consistency test
does not execute the current controller or a live model.

Use the current regression suite to verify the current behavior. A fresh live-model
benchmark is optional and requires a configured Ollama instance; none is implied by a green
CI result. [Changes and compatibility](CHANGELOG.md).

Built by **Milo Geller** · [MIT licensed](LICENSE).
