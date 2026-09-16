from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from invoice_extractor.extractor import extract_invoice
from invoice_extractor.generator import generate_pdfs
from invoice_extractor.ai import validate_ai_invoice
from invoice_extractor.autonomy import process_invoice_autonomously
from invoice_extractor.autonomous_benchmark import generate_cases


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

    def test_autonomous_invoice_posts_without_human_approval(self) -> None:
        case = generate_cases(1)[0]
        outcome = process_invoice_autonomously(case.text, case.truth)
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.data["posting_status"], "posted")
        self.assertFalse(outcome.manual_approval_required)

    def test_ungrounded_ai_invoice_self_repairs(self) -> None:
        case = generate_cases(1)[0]
        wrong = {**case.truth, "total": "999.00"}
        outcome = process_invoice_autonomously(case.text, wrong)
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.source, "grounded_self_repair")
        self.assertEqual(outcome.data["total"], case.truth["total"])

    def test_autonomous_benchmark_has_200_pdf_cases(self) -> None:
        cases = generate_cases(200)
        self.assertEqual(len(cases), 200)
        self.assertEqual(sum(case.challenge != "standard" for case in cases), 100)


if __name__ == "__main__":
    unittest.main()
