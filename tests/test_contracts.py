import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from invoice_extractor.extractor import invoice_from_dict, extract_invoice
from invoice_extractor.autonomy import process_invoice_autonomously
from invoice_extractor.generator import generate_pdfs
from invoice_extractor.cli import main


def invoice():
    return {
        "vendor": "Demo",
        "invoice_number": "A",
        "issue_date": "2026-01-01",
        "due_date": "2026-02-01",
        "currency": "EUR",
        "items": [
            {
                "description": "Work",
                "quantity": 1.9,
                "unit_price": "100",
                "line_total": "190",
            }
        ],
        "subtotal": "190",
        "tax": "36.10",
        "total": "226.10",
    }


class ContractTests(unittest.TestCase):
    def test_fractional_quantities_are_preserved_exactly(self):
        result = invoice_from_dict(invoice())
        self.assertEqual(str(result.items[0].quantity), "1.9")
        self.assertTrue(result.reconciled)
        self.assertEqual(result.to_dict()["items"][0]["quantity"], "1.9")

    def test_bad_dates_currency_and_identity_are_rejected(self):
        for field, value in [
            ("issue_date", "not-a-date"),
            ("due_date", "2025-01-01"),
            ("currency", "INVALID"),
            ("vendor", None),
            ("invoice_number", ""),
        ]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                invoice_from_dict({**invoice(), field: value})

    def test_nonfinite_and_invalid_quantities_are_rejected(self):
        for value in [True, 0, -1, "NaN", "Infinity", None]:
            raw = invoice()
            raw["items"][0]["quantity"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                invoice_from_dict(raw)

    def test_nonfinite_and_overprecise_money_is_rejected(self):
        for value in ["NaN", "Infinity", "-1", "1.999", True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                invoice_from_dict({**invoice(), "total": value})

    def test_unknown_document_is_quarantined_without_exception(self):
        outcome = process_invoice_autonomously("Unrecognized document", {})
        self.assertFalse(outcome.approved)
        self.assertEqual(outcome.data["posting_status"], "quarantined")

    def test_conflicting_document_values_are_quarantined(self):
        text = "Vendor: Demo\nInvoice Number: A\nCurrency: EUR\nSubtotal: 100.00\nTax: 19.00\nTotal: 119.00\nTotal: 999.00\nLine Total: 100.00"
        self.assertFalse(process_invoice_autonomously(text, None).approved)

    def test_partial_total_label_does_not_match_subtotal(self):
        text = "Vendor: Demo\nInvoice Number: A\nIssue Date: 2026-01-01\nDue Date: 2026-02-01\nCurrency: EUR\nWork | 1 | 100.00 | 100.00\nSubtotal: 100.00\nTax: 19.00\n"
        with (
            patch("invoice_extractor.extractor.extract_text", return_value=text),
            self.assertRaises(ValueError),
        ):
            extract_invoice(Path("unused.pdf"))

    def test_cli_processes_existing_pdfs_and_isolates_bad_file(self):
        source = Path(__file__).parents[1] / "data/mock/invoices.json"
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = generate_pdfs(source, root / "pdfs")
            (root / "pdfs/bad.pdf").write_text("not a PDF")
            args = [
                "extract",
                "--input",
                str(root / "pdfs"),
                "--output",
                str(root / "out.json"),
            ]
            with (
                patch.object(sys, "argv", args),
                self.assertRaises(SystemExit) as exited,
            ):
                main()
            self.assertEqual(exited.exception.code, 1)
            self.assertEqual(
                len(json.loads((root / "out.json").read_text())), len(paths)
            )
            self.assertEqual(
                json.loads((root / "out.quarantine.json").read_text())[0]["file"],
                "bad.pdf",
            )

    def test_reconciliation_does_not_claim_external_posting(self):
        text = "Vendor: Demo\nInvoice Number: A\nCurrency: EUR\nSubtotal: 100.00\nTax: 19.00\nTotal: 119.00\nLine Total: 100.00"
        outcome = process_invoice_autonomously(text, None)
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.data["posting_status"], "ready_for_posting")
