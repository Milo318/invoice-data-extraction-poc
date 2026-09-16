# Autonomous PDF Invoice Processing

![Proof-of-work benchmark card](proof/portfolio-card.png)

[![Proof](https://github.com/Milo318/invoice-data-extraction-poc/actions/workflows/ci.yml/badge.svg)](https://github.com/Milo318/invoice-data-extraction-poc/actions/workflows/ci.yml)

A proof of concept that generates realistic sample invoices, extracts structured fields from PDFs, and validates every financial relationship before accepting the result. Autonomous AI supports unfamiliar layouts while deterministic grounding and reconciliation remain the final control.

**Public repository:** https://github.com/Milo318/invoice-data-extraction-poc

> **Data notice:** all vendors, invoice numbers, line items, PDFs, and totals are synthetic mock data. Generated PDFs are visibly labeled as demo documents.

## Autonomous AI proof

The upgraded workflow generates and reads actual PDFs, asks a live local model to extract invoice fields, grounds every proposed value against document text, reconciles line totals, tax, and final total, generates a duplicate key, and posts or quarantines automatically. Ungrounded model output is replaced by a deterministic grounded extraction without human approval.

The committed [live-model benchmark](proof/autonomous-benchmark.json) and [200 case-level decisions](proof/autonomous-cases.jsonl) were generated with `granite4.1:3b` through Ollama:

> **How to read 100%:** the model alone produced 116 strict field-for-field passes. The final 200 of 200 result belongs to the complete system after normalization, document grounding, automatic replacement, and independent financial reconciliation. Expected outcomes are used for scoring only, not supplied to the runtime controller.

| Autonomous acceptance check | Result |
|---|---:|
| PDFs generated, read, and evaluated | 200 |
| Strict raw AI field-for-field passes | 116 / 200 |
| AI outputs accepted after normalization and grounding | 164 / 200 |
| Grounded automatic self-repairs | 36 |
| Decoy / reordered-document stress PDFs | 100 / 100 approved |
| Financially reconciled cases | 200 / 200 |
| Final machine-approved cases | 200 / 200 |
| Final system approval rate | **100%** |
| Human approvals | **0** |

```bash
python -m invoice_extractor.autonomous_benchmark --cases 200 --model granite4.1:3b
```

Reproduction requires a running Ollama service with the selected model installed.

Half of the PDFs contain a plausible false amount, an untrusted embedded instruction, reordered totals, three line items, multiple currencies, and varying tax rates. Approval still requires exact document grounding and financial reconciliation.

The low strict raw-model score is retained intentionally: it demonstrates why accounting automation must not trust model output directly. Approval measures the complete grounded system. Every approved invoice must match the generated truth and pass independent arithmetic reconciliation.

## Proof of work

The [committed benchmark](proof/benchmark.json) compares extracted values with the source-of-truth JSON:

| Check | Measured result |
|---|---:|
| PDFs generated and processed | 10 |
| Scalar fields compared | 80 |
| Field accuracy on generated fixtures | 100% |
| Financial reconciliation | 100% |
| Average extraction time | 2.31 ms/PDF |
| Automated tests | 7 passing |

Reconciliation verifies three independent conditions: quantity × unit price equals each line total, line totals equal the subtotal, and subtotal + tax equals the final total. The benchmark covers a known layout and is not a claim of universal document support.

### Reproduce the evidence

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m invoice_extractor.cli
python -m invoice_extractor.benchmark
```

The demo generates ten PDFs under `output/pdfs/` and writes normalized invoice JSON to `output/extracted.json`.

## How it works

```text
Synthetic invoice truth data
        ↓
Generated, visibly labeled PDFs
        ↓
PDF text extraction
        ↓
Field and line-item parsing
        ↓
Financial reconciliation
        ↓
Structured JSON or explicit rejection
```

### Stage 1 — deterministic core

Known document layouts use explicit field patterns and decimal arithmetic. Missing required fields fail loudly instead of silently producing incomplete output. The result includes a `reconciled` flag so downstream automation can enforce review rules.

### Stage 2 — autonomous AI extraction and posting

For unfamiliar layouts, AI proposes the document structure. The autonomous controller grounds each value in the extracted document, replaces mismatches, reconciles all arithmetic, creates a duplicate key, and chooses `posted` or `quarantined` without an approval queue.

```bash
export LLM_API_KEY="..."
python -m invoice_extractor.cli --ai-fallback
```

## Evidence map

- [`data/mock/invoices.json`](data/mock/invoices.json) — labeled synthetic source of truth
- [`tests/test_extraction.py`](tests/test_extraction.py) — extraction and reconciliation checks
- [`proof/benchmark.json`](proof/benchmark.json) — field comparison and timing results
- [`proof/autonomous-benchmark.json`](proof/autonomous-benchmark.json) — live-model PDF acceptance summary
- [`proof/autonomous-cases.jsonl`](proof/autonomous-cases.jsonl) — all 200 posting decisions
- [`proof/portfolio-card.png`](proof/portfolio-card.png) — portfolio-ready evidence image
- [GitHub Actions workflow](.github/workflows/ci.yml) — regenerates PDFs and verifies extraction on every push

## Production extension points

Production work would add OCR for scanned documents, supplier-specific adapters, automatic vendor queries for unresolved exceptions, duplicate-invoice detection, currency/tax rules, encrypted storage, and accounting-platform integration.

Built by **Milo Geller** · MIT licensed.
