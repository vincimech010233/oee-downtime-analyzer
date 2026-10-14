"""Deterministic tests for one-cause-at-a-time OEE what-if arithmetic."""

import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oee import analyze, load_shifts  # noqa: E402
from oee_recovery import recovery_scenarios, report_scenarios  # noqa: E402


class RecoveryTests(unittest.TestCase):
    def fixture(self, body):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.csv"
            path.write_text(
                "shift,planned_minutes,downtime_minutes,ideal_cycle_seconds,total_units,good_units,cause\n" + body,
                encoding="utf-8",
            )
            return analyze(load_shifts(path))

    def test_hand_calculated_gain_and_cause_isolation(self):
        metrics = self.fixture("A,60,10,60,40,36,Setup\nB,60,20,60,30,27,Breakdown\n")
        # 120 planned; 90 operating; 70 made, 63 good; effective yield=63/90.
        result = recovery_scenarios(metrics, 50)
        self.assertEqual(metrics["oee"], Fraction(63, 120))
        self.assertEqual(result[0]["cause"], "Breakdown")
        self.assertEqual(result[0]["recovered_minutes"], 10)
        self.assertEqual(result[0]["oee_gain"], Fraction(7, 120))
        self.assertEqual(result[0]["conditional_oee"], Fraction(70, 120))
        self.assertEqual(result[1]["recovered_minutes"], 5)
        self.assertEqual(result[1]["oee_gain"], Fraction(7, 240))
        self.assertEqual(result[1]["conditional_oee"], Fraction(133, 240))

    def test_boundaries_zero_full_and_no_more_than_one(self):
        metrics = self.fixture("A,60,10,60,40,36,Setup\n")
        for percent in (0, 100):
            result = recovery_scenarios(metrics, percent)[0]
            self.assertEqual(result["recovered_minutes"], Fraction(percent, 10))
            self.assertLessEqual(result["conditional_oee"], 1)
            self.assertGreaterEqual(result["conditional_oee"], metrics["oee"])
        self.assertEqual(recovery_scenarios(metrics, 0)[0]["oee_gain"], 0)
        self.assertEqual(recovery_scenarios(metrics, 100)[0]["conditional_oee"], Fraction(18, 25))

    def test_invalid_recovery_percent_fails_closed(self):
        metrics = self.fixture("A,60,10,60,40,36,Setup\n")
        for value in (-1, 101, 1.5, True, "50"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recovery_scenarios(metrics, value)

    def test_undefined_baseline_abstains(self):
        idle = self.fixture("A,60,60,60,0,0,Breakdown\n")
        no_parts = self.fixture("A,60,10,60,0,0,Setup\n")
        for metrics in (idle, no_parts):
            self.assertIsNone(recovery_scenarios(metrics, 50))
            self.assertIn("Not estimable", report_scenarios(metrics, 50))

    def test_no_downtime_does_not_invent_scenario(self):
        metrics = self.fixture("A,60,0,60,60,60,\n")
        self.assertEqual(recovery_scenarios(metrics, 50), [])
        self.assertIn("No recorded downtime", report_scenarios(metrics, 50))

    def test_sample_cli_and_reproducible_output(self):
        command = [sys.executable, str(ROOT / "oee_recovery.py"), str(ROOT / "data/synthetic_shifts.csv")]
        a = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
        b = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual((a.returncode, b.returncode), (0, 0), a.stderr + b.stderr)
        self.assertEqual(a.stdout, b.stdout)
        self.assertIn("Baseline OEE: **73.40%**", a.stdout)
        self.assertIn("Material shortage", a.stdout)
        self.assertIn("reduction: **50%**", a.stdout)

    def test_bad_cli_input_and_percent(self):
        command = [sys.executable, str(ROOT / "oee_recovery.py"), str(ROOT / "data/synthetic_shifts.csv")]
        for extra in (["--recovery-percent", "-1"], ["--recovery-percent", "101"]):
            r = subprocess.run(command + extra, cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(r.returncode, 2)
            self.assertIn("must be 0..100", r.stderr)
        r = subprocess.run(command[:-1] + ["not-present.csv"], cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 2)

    def test_escaping_of_cause_field_and_deterministic_ranking(self):
        metrics = self.fixture("A,60,10,60,40,36,Setup (S1)\nB,60,10,60,40,36,Alpha\n")
        text = report_scenarios(metrics, 50)
        self.assertLess(text.index("| Alpha |"), text.index("| Setup (S1) |"))


if __name__ == "__main__":
    unittest.main()
