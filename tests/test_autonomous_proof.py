from pathlib import Path
import json
import unittest


ROOT = Path(__file__).parents[1]


class AutonomousProofTests(unittest.TestCase):
    def test_committed_live_benchmark_meets_acceptance_gate(self) -> None:
        summary = json.loads((ROOT / "proof" / "autonomous-benchmark.json").read_text())
        rows = [json.loads(line) for line in (ROOT / "proof" / "autonomous-cases.jsonl").read_text().splitlines()]
        self.assertTrue(summary["live_model"])
        self.assertGreaterEqual(summary["benchmark_cases"], 100)
        self.assertGreater(summary["approval_rate_percent"], 95)
        self.assertTrue(summary["acceptance_gate_passed"])
        self.assertEqual(summary["manual_approvals_required"], 0)
        self.assertEqual(len(rows), summary["benchmark_cases"])
        self.assertTrue(all(row["approved"] for row in rows))
