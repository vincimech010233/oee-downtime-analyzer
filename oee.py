"""Analyze synthetic shift production and render a deterministic Pareto report."""

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from html import escape
from pathlib import Path


FIELDS = ("shift", "planned_minutes", "downtime_minutes", "ideal_cycle_seconds", "total_units", "good_units", "cause")
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Shift:
    name: str
    planned: int
    downtime: int
    cycle_seconds: int
    total: int
    good: int
    cause: str

    @property
    def operating(self):
        return self.planned - self.downtime


def number(raw, label, row):
    if not re.fullmatch(r"[0-9]{1,7}", raw):
        raise ValueError(f"row {row}: {label} must be a nonnegative integer")
    return int(raw)


def text_field(raw, label, row):
    if not raw or len(raw) > 80 or not raw[0].isalnum() or any(
        not (char.isalnum() or char in " _-./()") for char in raw
    ):
        raise ValueError(f"row {row}: invalid {label}")
    return raw


def load_shifts(path):
    if path.stat().st_size > 1_000_000:
        raise ValueError("CSV exceeds 1 MB limit")
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or tuple(reader.fieldnames) != FIELDS:
            raise ValueError("CSV header does not match the required schema")
        shifts = []
        for row_number, record in enumerate(reader, 2):
            if row_number > 1001:
                raise ValueError("CSV exceeds 1000 shift rows")
            if None in record or any(value is None for value in record.values()):
                raise ValueError(f"row {row_number}: missing or extra fields")
            name = text_field(record["shift"], "shift", row_number)
            cause = record["cause"]
            if cause:
                text_field(cause, "cause", row_number)
            planned = number(record["planned_minutes"], "planned_minutes", row_number)
            downtime = number(record["downtime_minutes"], "downtime_minutes", row_number)
            cycle = number(record["ideal_cycle_seconds"], "ideal_cycle_seconds", row_number)
            total = number(record["total_units"], "total_units", row_number)
            good = number(record["good_units"], "good_units", row_number)
            if not 1 <= planned <= 1440 or not 1 <= cycle <= 3600 or downtime > planned:
                raise ValueError(f"row {row_number}: invalid planned time, downtime, or cycle")
            operating = planned - downtime
            if good > total or total * cycle > operating * 60:
                raise ValueError(f"row {row_number}: impossible production counts")
            if (downtime > 0 and not cause) or (downtime == 0 and cause):
                raise ValueError(f"row {row_number}: cause must identify positive downtime only")
            shifts.append(Shift(name, planned, downtime, cycle, total, good, cause))
    if not shifts:
        raise ValueError("CSV has no shift rows")
    if len({shift.cycle_seconds for shift in shifts}) != 1:
        raise ValueError("all shifts must use the same ideal cycle time")
    if len({shift.cause for shift in shifts if shift.downtime}) > 12:
        raise ValueError("CSV exceeds 12 downtime causes; split the analysis")
    return shifts


def analyze(shifts):
    planned = sum(shift.planned for shift in shifts)
    downtime = sum(shift.downtime for shift in shifts)
    operating = planned - downtime
    total = sum(shift.total for shift in shifts)
    good = sum(shift.good for shift in shifts)
    cycle = shifts[0].cycle_seconds
    causes = Counter()
    for shift in shifts:
        if shift.downtime:
            causes[shift.cause] += shift.downtime
    if sum(causes.values()) != downtime:
        raise ValueError("downtime categories do not reconcile")
    availability = Fraction(operating, planned)
    performance = Fraction(total * cycle, operating * 60) if operating else Fraction(0)
    quality = Fraction(good, total) if total else Fraction(0)
    oee = availability * performance * quality
    pareto = sorted(causes.items(), key=lambda item: (-item[1], item[0]))
    return {
        "planned": planned,
        "downtime": downtime,
        "operating": operating,
        "total": total,
        "good": good,
        "cycle": cycle,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "quality_defined": total > 0,
        "performance_defined": operating > 0,
        "oee": oee,
        "pareto": pareto,
    }


def percent(value):
    return f"{float(value) * 100:.2f}%"


def markdown_cell(value):
    return escape(value).replace("|", "\\|")


def report(metrics):
    lines = [
        "# Synthetic production OEE and downtime report",
        "",
        "All values come from the synthetic CSV. No real plant or MES/SCADA data was used.",
        "",
        "## Totals and definitions",
        "",
        f"- Planned time: {metrics['planned']} min; downtime: {metrics['downtime']} min; operating time: {metrics['operating']} min.",
        f"- Ideal cycle: {metrics['cycle']} s/unit; total units: {metrics['total']}; good units: {metrics['good']}.",
        "- Availability = operating / planned.",
        "- Performance = total units × ideal cycle seconds / (operating minutes × 60).",
        "- Quality = good units / total units.",
        "- OEE = Availability × Performance × Quality.",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Availability | {percent(metrics['availability'])} |",
        f"| Performance | {percent(metrics['performance'])} |",
        f"| Quality | {percent(metrics['quality']) if metrics['quality_defined'] else 'Undefined (0 used for OEE)'} |",
        f"| OEE | {percent(metrics['oee'])} |",
        "",
    ]
    if not metrics["performance_defined"]:
        lines.extend(["Performance is undefined when operating time is zero; 0 is used for OEE.", ""])
    lines.extend(["## Downtime Pareto", "", "| Rank | Cause | Minutes | Share | Cumulative |", "| ---: | --- | ---: | ---: | ---: |"])
    cumulative = 0
    for rank, (cause, minutes) in enumerate(metrics["pareto"], 1):
        cumulative += minutes
        lines.append(f"| {rank} | {markdown_cell(cause)} | {minutes} | {percent(Fraction(minutes, metrics['downtime']))} | {percent(Fraction(cumulative, metrics['downtime']))} |")
    if not metrics["pareto"]:
        lines.append("| — | No downtime recorded | 0 | — | — |")
    lines.extend(["", "![Downtime Pareto](pareto.svg)", "", "Interpret OEE only with these definitions and the stated ideal cycle. The cause rank identifies where this synthetic dataset records the most downtime; it is not a validated plant decision.", ""])
    return "\n".join(lines)


def pareto_svg(metrics):
    data = metrics["pareto"]
    width = max(640, 140 + 120 * len(data))
    top, height, left = 65, 260, 75
    right = width - 60
    bottom = top + height
    max_minutes = max((minutes for _, minutes in data), default=1)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 450" role="img" aria-labelledby="title desc">',
        '<title id="title">Downtime Pareto chart</title>',
        '<desc id="desc">Bars show downtime minutes by cause in descending order. The orange line shows cumulative percentage.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="75" y="30" font-family="sans-serif" font-size="18">Synthetic downtime by cause</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#333"/>',
        f'<text x="5" y="{top}" font-family="sans-serif" font-size="12">{max_minutes} min</text>',
        f'<text x="{right + 4}" y="{top}" font-family="sans-serif" font-size="12">100%</text>',
        f'<text x="{right + 4}" y="{bottom}" font-family="sans-serif" font-size="12">0%</text>',
    ]
    if not data:
        out.append('<text x="75" y="190" font-family="sans-serif">No downtime recorded</text>')
    else:
        step = (right - left) / len(data)
        points = []
        cumulative = 0
        for index, (cause, minutes) in enumerate(data):
            x = left + step * (index + 0.5)
            bar_height = height * minutes / max_minutes
            cumulative += minutes
            y_line = bottom - height * cumulative / metrics["downtime"]
            points.append(f"{x:.1f},{y_line:.1f}")
            out.extend([
                f'<rect x="{x - 25:.1f}" y="{bottom - bar_height:.1f}" width="50" height="{bar_height:.1f}" fill="#1769aa"/>',
                f'<text x="{x:.1f}" y="{bottom - bar_height - 6:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12">{minutes}</text>',
                f'<text x="{x:.1f}" y="{bottom + 22}" text-anchor="middle" font-family="sans-serif" font-size="12">{escape(cause[:22 if len(data) <= 5 else 14])}</text>',
            ])
        joined_points = " ".join(points)
        out.append(f'<polyline points="{joined_points}" fill="none" stroke="#c05800" stroke-width="3"/>')
        for point in points:
            x, y = point.split(",")
            out.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#c05800"/>')
    out.extend([
        f'<rect x="{left}" y="410" width="15" height="12" fill="#1769aa"/>',
        f'<text x="{left + 22}" y="421" font-family="sans-serif" font-size="12">Downtime minutes</text>',
        f'<line x1="{left + 175}" y1="416" x2="{left + 194}" y2="416" stroke="#c05800" stroke-width="3"/>',
        f'<text x="{left + 202}" y="421" font-family="sans-serif" font-size="12">Cumulative share</text>',
        '</svg>',
    ])
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="synthetic shift CSV")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    try:
        metrics = analyze(load_shifts(args.csv))
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.error(str(error))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.md").write_text(report(metrics), encoding="utf-8")
    (args.output_dir / "pareto.svg").write_text(pareto_svg(metrics), encoding="utf-8")
    print(f"Availability {percent(metrics['availability'])}; Performance {percent(metrics['performance'])}; "
          f"Quality {percent(metrics['quality']) if metrics['quality_defined'] else 'undefined'}; OEE {percent(metrics['oee'])}")


if __name__ == "__main__":
    main()
