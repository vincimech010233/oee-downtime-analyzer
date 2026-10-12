"""Deterministic offline tests using synthetic time intervals only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from downtime_event_audit import audit, markdown, write_outputs

SUMMARY_HEADER = (
    "shift,planned_minutes,downtime_minutes,ideal_cycle_seconds,total_units,good_units,cause\n"
)
EVENT_HEADER = "shift,start_minute,end_minute,cause\n"


class DowntimeEventAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.shifts = self.work / "shifts.csv"
        self.events = self.work / "events.csv"
        self.shifts.write_text(SUMMARY_HEADER + "A,60,20,60,30,28,Generic\n", encoding="utf-8")

    def event_text(self, body):
        self.events.write_text(EVENT_HEADER + body, encoding="utf-8")
        return self.events

    def check_error(self, body, message):
        self.event_text(body)
        with self.assertRaisesRegex(ValueError, message):
            audit(self.shifts, self.events)

    def test_two_causes_complete_reconciliation(self):
        self.event_text("A,10,15,Setup\nA,30,45,Material shortage\n")
        result = audit(self.shifts, self.events)
        self.assertEqual(result["status"], "RECONCILED")
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["downtime_minutes"], 20)
        self.assertEqual(result["event_cause_ranking"], [
            {"cause": "Material shortage", "minutes": 15},
            {"cause": "Setup", "minutes": 5},
        ])
        self.assertEqual(result["oee_percent"], "46.67%")
        self.assertIn("75.00%", markdown(result))

    def test_unsorted_adjacent_intervals_accepted(self):
        self.event_text("A,20,30,Setup\nA,10,20,Setup\n")
        self.assertEqual(audit(self.shifts, self.events)["event_count"], 2)

    def test_overlap_rejected_even_if_duration_sum_matches(self):
        self.check_error("A,10,20,Setup\nA,19,29,Material\n", "overlapping")

    def test_reconciliation_rejects_missing_and_excess_events(self):
        for body in ["A,10,15,Setup\n", "A,10,31,Setup\n"]:
            self.check_error(body, "do not match")

    def test_unknown_shift_and_duplicate_summary_shift(self):
        self.check_error("B,1,21,Setup\n", "not found")
        self.shifts.write_text(SUMMARY_HEADER + "A,60,20,60,30,28,Generic\nA,60,0,60,60,60,\n")
        self.check_error("A,0,20,Setup\n", "must be unique")

    def test_invalid_intervals_and_causes(self):
        for body in [
            "A,1,1,Setup\n", "A,0,61,Setup\n", "A,-1,19,Setup\n",
            "A,40,20,Setup\n", "A,10,30,\n", "A,10,30,<script>\n",
            "A,10,30,Setup,extra\n", "A,10,30\n",
        ]:
            with self.subTest(body=body):
                self.event_text(body)
                with self.assertRaises(ValueError):
                    audit(self.shifts, self.events)

    def test_header_rejected(self):
        self.events.write_text("start,end,cause\n0,20,Setup\n")
        with self.assertRaisesRegex(ValueError, "schema"):
            audit(self.shifts, self.events)

    def test_zero_downtime_without_events(self):
        self.shifts.write_text(SUMMARY_HEADER + "A,60,0,60,60,60,\n")
        self.event_text("")
        result = audit(self.shifts, self.events)
        self.assertEqual(result["event_cause_ranking"], [])
        self.assertEqual(result["downtime_minutes"], 0)
        self.assertIn("No downtime", markdown(result))

    def test_sort_ties_by_name(self):
        self.event_text("A,0,10,Zeta\nA,10,20,Alpha\n")
        self.assertEqual([x["cause"] for x in audit(self.shifts, self.events)["event_cause_ranking"]],
                         ["Alpha", "Zeta"])

    def test_size_limit(self):
        self.events.write_text("x" * 1_000_001)
        with self.assertRaisesRegex(ValueError, "1 MB"):
            audit(self.shifts, self.events)

    def test_outputs_reproducible_private_and_nonoverwriting(self):
        self.event_text("A,0,20,Setup\n")
        result = audit(self.shifts, self.events)
        first = self.work / "out_a"
        second = self.work / "out_b"
        write_outputs(first, result)
        write_outputs(second, result)
        for name in ("event_audit.json", "event_audit.md"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        self.assertEqual(json.loads((first / "event_audit.json").read_text())["event_count"], 1)
        if os.name == "posix":
            self.assertEqual((first / "event_audit.json").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            write_outputs(first, result)
        self.assertEqual(sorted(p.name for p in first.iterdir()), ["event_audit.json", "event_audit.md"])

    def test_existing_markdown_rolls_back_new_json(self):
        self.event_text("A,0,20,Setup\n")
        result = audit(self.shifts, self.events)
        output = self.work / "collision"
        output.mkdir()
        existing = output / "event_audit.md"
        existing.write_text("Do not overwrite", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            write_outputs(output, result)
        self.assertEqual(existing.read_text(), "Do not overwrite")
        self.assertFalse((output / "event_audit.json").exists())

    def test_reject_symlink_output_directory(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        self.event_text("A,0,20,Setup\n")
        destination = self.work / "actual"
        destination.mkdir()
        link = self.work / "link"
        link.symlink_to(destination, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            write_outputs(link, audit(self.shifts, self.events))
        self.assertEqual(list(destination.iterdir()), [])

    def test_cli_success_and_failed_validation_writes_nothing(self):
        self.event_text("A,10,30,Setup\n")
        output = self.work / "cli_output"
        command = [sys.executable, str(ROOT / "downtime_event_audit.py"),
                   str(self.shifts), str(self.events), "--output-dir", str(output)]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("RECONCILED", run.stdout)
        output2 = self.work / "should_not_exist"
        self.event_text("A,0,21,Setup\n")
        run = subprocess.run(command[:-1] + [str(output2)], cwd=ROOT, text=True,
                             capture_output=True, timeout=5)
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(output2.exists())


if __name__ == "__main__":
    unittest.main()
