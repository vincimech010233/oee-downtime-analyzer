import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oee import Shift, analyze, load_shifts, pareto_svg, report


ROOT = Path(__file__).resolve().parents[1]
HEADER = "shift,planned_minutes,downtime_minutes,ideal_cycle_seconds,total_units,good_units,cause\n"


class OeeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def write_csv(self, body):
        path = self.work / "shifts.csv"
        path.write_text(HEADER + body, encoding="utf-8")
        return path

    def test_hand_calculated_shift(self):
        shifts = load_shifts(self.write_csv("A,60,10,60,40,36,Setup\n"))
        result = analyze(shifts)
        self.assertEqual(result["availability"], Fraction(5, 6))
        self.assertEqual(result["performance"], Fraction(4, 5))
        self.assertEqual(result["quality"], Fraction(9, 10))
        self.assertEqual(result["oee"], Fraction(3, 5))
        self.assertEqual(result["pareto"], [("Setup", 10)])

    def test_sample_totals_pareto_and_mathematical_consistency(self):
        result = analyze(load_shifts(ROOT / "data/synthetic_shifts.csv"))
        self.assertEqual((result["planned"], result["downtime"], result["operating"]), (1440, 180, 1260))
        self.assertEqual((result["total"], result["good"]), (1095, 1057))
        self.assertEqual(result["oee"], Fraction(1057, 1440))
        self.assertEqual(result["oee"], result["availability"] * result["performance"] * result["quality"])
        self.assertEqual(result["pareto"], [("Material shortage", 90), ("Setup", 60), ("Maintenance", 30)])
        self.assertEqual(sum(minutes for _, minutes in result["pareto"]), result["downtime"])
        self.assertIn("100.00%", report(result))
        ET.fromstring(pareto_svg(result))

    def test_zero_output_and_zero_operating_time(self):
        idle = analyze(load_shifts(self.write_csv("Idle,60,60,60,0,0,Breakdown\n")))
        self.assertEqual(idle["oee"], 0)
        self.assertFalse(idle["performance_defined"])
        self.assertFalse(idle["quality_defined"])
        self.assertIn("undefined when operating time is zero", report(idle))
        no_output = analyze(load_shifts(self.write_csv("No output,60,10,60,0,0,Setup\n")))
        self.assertEqual(no_output["availability"], Fraction(5, 6))
        self.assertEqual(no_output["performance"], 0)
        self.assertFalse(no_output["quality_defined"])

    def test_no_downtime_and_deterministic_ties(self):
        no_down = analyze(load_shifts(self.write_csv("A,60,0,60,60,60,\n")))
        self.assertEqual(no_down["oee"], 1)
        self.assertEqual(no_down["pareto"], [])
        ET.fromstring(pareto_svg(no_down))
        tied = analyze(load_shifts(self.write_csv("A,60,10,60,40,36,Zeta\nB,60,10,60,40,36,Alpha\n")))
        self.assertEqual(tied["pareto"], [("Alpha", 10), ("Zeta", 10)])

    def test_invalid_rows_are_rejected(self):
        invalid = [
            "A,0,0,60,0,0,\n",
            "A,60,-1,60,0,0,Setup\n",
            "A,60,61,60,0,0,Setup\n",
            "A,60,0,0,0,0,\n",
            "A,60,10,60,51,50,Setup\n",
            "A,60,10,60,40,41,Setup\n",
            "A,60,10,60,40,36,\n",
            "A,60,0,60,0,0,Setup\n",
            "A,60,10,60,40,36,Setup\nB,60,10,30,40,36,Setup\n",
            "A,60,10,60,40,36,Setup,extra\n",
            "A,60,10,60,40\n",
            "A,60,10,60,40,36,<img src=x>\n",
        ]
        for body in invalid:
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    load_shifts(self.write_csv(body))

    def test_cli_creates_report_and_svg_in_requested_directory(self):
        output = self.work / "out"
        result = subprocess.run(
            [sys.executable, str(ROOT / "oee.py"), str(ROOT / "data/synthetic_shifts.csv"), "--output-dir", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OEE 73.40%", result.stdout)
        self.assertIn("Material shortage", (output / "report.md").read_text())
        ET.parse(output / "pareto.svg")
        self.assertEqual(sorted(path.name for path in output.iterdir()), ["pareto.svg", "report.md"])


if __name__ == "__main__":
    unittest.main()
