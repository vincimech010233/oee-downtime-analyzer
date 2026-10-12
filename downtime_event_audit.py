"""Reconcile synthetic shift downtime against bounded, nonoverlapping event intervals."""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from oee import analyze, load_shifts, number, percent, text_field

EVENT_FIELDS = ("shift", "start_minute", "end_minute", "cause")
MAX_EVENTS = 5000
MAX_CAUSES = 100
MAX_BYTES = 1_000_000


def audit(shift_csv: Path, event_csv: Path):
    """Validate a complete event ledger and return deterministic summary data."""
    shifts = load_shifts(shift_csv)
    by_name = {shift.name: shift for shift in shifts}
    if len(by_name) != len(shifts):
        raise ValueError("shift names must be unique for event reconciliation")
    if event_csv.stat().st_size > MAX_BYTES:
        raise ValueError("event CSV exceeds 1 MB limit")
    events = defaultdict(list)
    with event_csv.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != EVENT_FIELDS:
            raise ValueError("event CSV header does not match required schema")
        for row_number, record in enumerate(reader, 2):
            if row_number > MAX_EVENTS + 1:
                raise ValueError(f"event CSV exceeds {MAX_EVENTS} rows")
            if None in record or any(value is None for value in record.values()):
                raise ValueError(f"row {row_number}: missing or extra event fields")
            shift_name = text_field(record["shift"], "shift", row_number)
            if shift_name not in by_name:
                raise ValueError(f"row {row_number}: shift not found in shift CSV")
            cause = text_field(record["cause"], "cause", row_number)
            start = number(record["start_minute"], "start_minute", row_number)
            end = number(record["end_minute"], "end_minute", row_number)
            if not (0 <= start < end <= by_name[shift_name].planned):
                raise ValueError(f"row {row_number}: event interval outside shift or empty")
            events[shift_name].append((start, end, cause))
    causes = Counter()
    per_shift = []
    total_events = 0
    for shift in sorted(shifts, key=lambda s: s.name):
        series = sorted(events[shift.name], key=lambda x: (x[0], x[1], x[2]))
        previous_end = 0
        observed = 0
        for start, end, cause in series:
            if start < previous_end:
                raise ValueError(f"shift {shift.name}: overlapping event intervals")
            duration = end - start
            observed += duration
            causes[cause] += duration
            previous_end = end
        if observed != shift.downtime:
            raise ValueError(
                f"shift {shift.name}: event minutes {observed} do not match "
                f"summary downtime {shift.downtime}"
            )
        total_events += len(series)
        per_shift.append({
            "shift": shift.name,
            "planned_minutes": shift.planned,
            "expected_downtime_minutes": shift.downtime,
            "event_downtime_minutes": observed,
            "events": len(series),
        })
    if len(causes) > MAX_CAUSES:
        raise ValueError(f"event CSV exceeds {MAX_CAUSES} distinct causes")
    metrics = analyze(shifts)
    if sum(causes.values()) != metrics["downtime"]:
        raise ValueError("event duration totals failed reconciliation")
    ranking = [{"cause": cause, "minutes": minutes} for cause, minutes in
               sorted(causes.items(), key=lambda item: (-item[1], item[0]))]
    return {
        "status": "RECONCILED",
        "input_type": "synthetic_shift_and_event_csv",
        "shifts": per_shift,
        "event_count": total_events,
        "downtime_minutes": metrics["downtime"],
        "oee_exact": str(metrics["oee"]),
        "oee_percent": percent(metrics["oee"]),
        "event_cause_ranking": ranking,
    }


def markdown(result):
    """Deterministic summary without untrusted HTML or active links."""
    lines = [
        "# Synthetic downtime event reconciliation",
        "",
        "**Status:** RECONCILED against the supplied shift totals; not field-validated.",
        "",
        f"Events: {result['event_count']}; downtime: {result['downtime_minutes']} min; "
        f"shift-summary OEE: {result['oee_percent']} (unchanged).",
        "",
        "## Event-level downtime Pareto",
        "",
        "| Cause | Minutes | Share | Cumulative |",
        "| --- | ---: | ---: | ---: |",
    ]
    cumulative = 0
    for item in result["event_cause_ranking"]:
        cumulative += item["minutes"]
        # Cause text is already restricted by oee.text_field. Escape Markdown emphasis.
        cause = item["cause"].replace("_", "\\_")
        minutes = item["minutes"]
        total = result["downtime_minutes"]
        lines.append(
            f"| {cause} | {minutes} | {percent(Fraction(minutes, total))} | "
            f"{percent(Fraction(cumulative, total))} |"
        )
    if not result["event_cause_ranking"]:
        lines.append("| No downtime | 0 | — | — |")
    lines.extend([
        "",
        "## Shift reconciliation",
        "",
        "| Shift | Expected min | Event min | Events |",
        "| --- | ---: | ---: | ---: |",
    ])
    for item in result["shifts"]:
        name = item["shift"].replace("_", "\\_")
        lines.append(f"| {name} | {item['expected_downtime_minutes']} | "
                     f"{item['event_downtime_minutes']} | {item['events']} |")
    lines.extend([
        "",
        "Only one continuous time axis per named shift is modeled. Events must not overlap.",
        "The summary CSV's single cause label is intentionally not used for the event-level ranking.",
        "All inputs are synthetic; this output makes no claim about a real factory, "
        "causal attribution, or validated MES/SCADA integration.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(directory: Path, result):
    """Create non-overwriting private files; best-effort rollback on write failure."""
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("output directory cannot be a symlink")
    files = [
        (directory / "event_audit.json", json.dumps(result, indent=2, ensure_ascii=False) + "\n"),
        (directory / "event_audit.md", markdown(result)),
    ]
    created = []
    try:
        for path, content in files:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(path, flags, 0o600)
            created.append(path)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as target:
                target.write(content)
    except (OSError, UnicodeError):
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shifts", type=Path, help="existing synthetic OEE shift-summary CSV")
    parser.add_argument("events", type=Path, help="synthetic downtime events CSV")
    parser.add_argument("--output-dir", type=Path, default=Path("results/events"))
    args = parser.parse_args(argv)
    try:
        result = audit(args.shifts, args.events)
        write_outputs(args.output_dir, result)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.error(str(error))
    print(f"{result['status']}: {result['event_count']} events; "
          f"{result['downtime_minutes']} downtime minutes; OEE {result['oee_percent']}")


if __name__ == "__main__":
    main()
