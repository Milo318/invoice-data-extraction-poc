"""Archive integrity only: current runtime behavior is tested separately."""

from pathlib import Path
import json
import unittest


ROOT = Path(__file__).parents[1]


class HistoricalEvidenceTests(unittest.TestCase):
    def test_historical_benchmark_archive_is_internally_consistent(self) -> None:
        summary = json.loads((ROOT / "proof" / "autonomous-benchmark.json").read_text())
        rows = [
            json.loads(line)
            for line in (ROOT / "proof" / "autonomous-cases.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertTrue(summary["live_model"])
        self.assertGreaterEqual(summary["benchmark_cases"], 200)
        self.assertGreaterEqual(summary["approval_rate_percent"], 96)
        self.assertTrue(summary["acceptance_gate_passed"])
        self.assertGreaterEqual(summary["stress_cases"], 100)
        self.assertGreaterEqual(summary["stress_approval_rate_percent"], 96)
        self.assertEqual(summary["manual_approvals_required"], 0)
        self.assertEqual(len(rows), summary["benchmark_cases"])
        self.assertEqual(
            sum(row["challenge"] != "standard" for row in rows), summary["stress_cases"]
        )
        self.assertTrue(all(row["approved"] for row in rows))
