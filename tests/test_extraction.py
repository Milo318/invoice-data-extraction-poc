from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from invoice_extractor.extractor import extract_invoice
from invoice_extractor.generator import generate_pdfs
from invoice_extractor.ai import validate_ai_invoice


SOURCE = Path(__file__).parents[1] / "data" / "mock" / "invoices.json"


class InvoiceTests(unittest.TestCase):
    def test_all_generated_invoices_extract_and_reconcile(self) -> None:
        with TemporaryDirectory() as directory:
            paths = generate_pdfs(SOURCE, Path(directory))
            invoices = [extract_invoice(path) for path in paths]
            self.assertEqual(len(invoices), len(json.loads(SOURCE.read_text())))
            self.assertTrue(all(invoice.reconciled for invoice in invoices))

    def test_known_invoice_values(self) -> None:
        with TemporaryDirectory() as directory:
            path = generate_pdfs(SOURCE, Path(directory))[0]
            invoice = extract_invoice(path)
            self.assertEqual(invoice.invoice_number, "MOCK-INV-1001")
            self.assertEqual(str(invoice.total), "1428.00")
            self.assertEqual(len(invoice.items), 2)

    def test_ai_result_is_independently_reconciled(self) -> None:
        raw = {
            "vendor": "Mock Vendor", "invoice_number": "MOCK-AI-1", "issue_date": "2026-01-01",
            "due_date": "2026-02-01", "currency": "EUR",
            "items": [{"description": "Service", "quantity": 2, "unit_price": "100.00", "line_total": "200.00"}],
            "subtotal": "200.00", "tax": "38.00", "total": "238.00",
        }
        validated = validate_ai_invoice(raw)
        self.assertTrue(validated["reconciled"])
        self.assertEqual(validated["extraction_stage"], "ai")


if __name__ == "__main__":
    unittest.main()
