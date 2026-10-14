"""Model hypothetical OEE gains from reducing one recorded downtime cause."""

import argparse
import csv
from fractions import Fraction
from pathlib import Path

from oee import analyze, load_shifts, markdown_cell, percent


def recovery_scenarios(metrics, recovery_percent):
    """Return independent, exact-arithmetic what-if rows; None means undefined baseline.

    Performance and quality are held constant. Each cause is evaluated separately;
    the returned OEE values are conditional illustrations, not forecasts.
    """
    if type(recovery_percent) is not int or not 0 <= recovery_percent <= 100:
        raise ValueError("recovery percent must be an integer from 0 to 100")
    if not metrics["performance_defined"] or not metrics["quality_defined"]:
        return None
    fraction = Fraction(recovery_percent, 100)
    effective_yield = metrics["performance"] * metrics["quality"]
    output = []
    for cause, minutes in metrics["pareto"]:
        recovered_minutes = minutes * fraction
        gain = recovered_minutes * effective_yield / metrics["planned"]
        output.append({
            "cause": cause,
            "downtime_minutes": minutes,
            "recovered_minutes": recovered_minutes,
            "oee_gain": gain,
            "conditional_oee": metrics["oee"] + gain,
        })
    return output


def report_scenarios(metrics, recovery_percent):
    """Render a synthetic, reproducible Markdown what-if analysis."""
    scenarios = recovery_scenarios(metrics, recovery_percent)
    lines = [
        "# Synthetic downtime-recovery what-if analysis",
        "",
        "This is a conditional arithmetic illustration using synthetic shifts, not a prediction,",
        "an optimization recommendation, or evidence of recoverable factory capacity.",
        "",
        f"Baseline OEE: **{percent(metrics['oee'])}**. Hypothetical cause-specific downtime reduction: **{recovery_percent}%**.",
        "",
        "## Assumptions",
        "",
        "- Planned production time, ideal cycle time, observed performance and observed quality are fixed.",
        "- Recovered downtime becomes additional running time at those same observed performance and quality rates.",
        "- Each cause is treated **independently**; a scenario does not imply that the change is feasible.",
        "- Fractional recovered minutes and inferred extra good units are continuous planning quantities, not actual counts.",
        "- No labor, material, line-balance, reliability, safety, or cost constraints are modeled.",
        "",
        "For one cause: OEE gain = (recovered minutes / planned minutes) × Performance × Quality.",
        "",
    ]
    if scenarios is None:
        lines.extend([
            "## Not estimable",
            "",
            "Baseline performance or quality is undefined (zero operating minutes or zero total units).",
            "The tool does not replace the missing rate with an invented production forecast.",
            "",
        ])
    elif not scenarios:
        lines.extend(["## No recorded downtime", "", "There are no downtime causes to model.", ""])
    else:
        lines.extend([
            "## One-cause-at-a-time scenarios",
            "",
            "| Cause | Recorded downtime (min) | Hypothetical recovered (min) | OEE gain (percentage points) | Conditional OEE |",
            "| --- | ---: | ---: | ---: | ---: |",
        ])
        for item in scenarios:
            lines.append(
                f"| {markdown_cell(item['cause'])} | {item['downtime_minutes']} | "
                f"{float(item['recovered_minutes']):.2f} | {float(item['oee_gain'] * 100):.2f} | "
                f"{percent(item['conditional_oee'])} |"
            )
        lines.append("")
    lines.append("Inputs and outputs are fictional; validate assumptions against real operating data before decisions.")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="shift CSV in the base analyzer format")
    parser.add_argument("--recovery-percent", type=int, default=50, help="hypothetical per-cause reduction, 0..100 (default: 50)")
    args = parser.parse_args()
    if not 0 <= args.recovery_percent <= 100:
        parser.error("--recovery-percent must be 0..100")
    try:
        metrics = analyze(load_shifts(args.csv))
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        parser.error(str(exc))
    print(report_scenarios(metrics, args.recovery_percent), end="")


if __name__ == "__main__":
    main()
