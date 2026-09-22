# Changelog

## 1.1.0

Validation and failure-handling update for validated pdf invoice extraction.

- Preserve fractional quantities instead of silently converting them to integers.
- Validate nonempty identities, ISO dates, supported currencies and finite monetary values.
- Reconcile quantity × unit price, line sums, subtotal, tax and total.
- Reject missing or conflicting labeled document fields.
- Process existing PDFs and isolate malformed documents into a quarantine report.
- Return `ready_for_posting` for accepted text extraction; no external accounting posting occurs.

The documented runtime contracts now take precedence over historical benchmark cards.
Old live-model results remain preserved as historical evidence. See README for supported
input formats, output semantics and the checks to reproduce locally.
