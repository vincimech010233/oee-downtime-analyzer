# OEE and Downtime Analyzer

A small, standard-library Python CLI that turns a **synthetic** shift CSV into Availability, Performance, Quality, OEE, a downtime cause ranking, a Markdown report, and a reproducible SVG Pareto chart. The sample does not represent a real plant, and no MES/SCADA data or validation is involved.

## Run

Requires Python 3.10+; no third-party packages or network access.

```bash
python3 oee.py data/synthetic_shifts.csv --output-dir results
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The CLI writes `report.md` and `pareto.svg` to the selected directory. [A checked-in sample report](examples/report.md) and [chart](examples/pareto.svg) can be regenerated with `--output-dir examples`. The SVG contains no timestamps or personal metadata.

## Input and definitions

Each CSV row represents one shift and one downtime cause. Times are whole minutes, the ideal cycle is whole seconds per unit, and production counts are whole units. Every row in one analysis must use the same ideal cycle. Positive downtime requires a cause; zero downtime has an empty cause. A shift may be fully down. A file is limited to 1 MB, 1000 rows and 12 downtime causes so reports remain bounded and readable.

Let `P` be planned minutes, `D` downtime minutes, `O = P − D` operating minutes, `C` ideal cycle seconds per unit, `T` total units and `G` good units. The tool sums these over the included shifts, then calculates:

- Availability = `O / P`
- Performance = `T × C / (O × 60)`
- Quality = `G / T`
- OEE = Availability × Performance × Quality

Validation requires `P > 0`, `0 ≤ D ≤ P`, `0 ≤ G ≤ T`, and `T × C ≤ O × 60` for every shift. Therefore Performance cannot exceed 100% under this chosen ideal-cycle definition. If `O = 0`, Performance is undefined and represented as zero solely to compute OEE; if `T = 0`, Quality is handled the same way. Reports label these cases. Aggregate OEE reduces to `G × C / (P × 60)` because one cycle is shared across rows.

Downtime is summed once from each shift's `D`, grouped by its cause, sorted by descending minutes and then cause name for ties. The Pareto chart shows minutes as bars and cumulative share as a line. A zero-downtime dataset has no ranked causes.

## Hand-checkable sample

One known case has `P=60`, `D=10`, `O=50`, `C=60`, `T=40`, `G=36`. Availability is `50/60 = 83.33%`; Performance is `40/50 = 80%`; Quality is `36/40 = 90%`; OEE is `60%`. The test suite checks the exact fractions.

For the supplied three-shift CSV, totals are `P=1440`, `D=180`, `O=1260`, `T=1095`, `G=1057`. OEE is exactly `1057/1440 = 73.4028…%` at `C=60`. Pareto causes rank as Material shortage 90 min (50%), Setup 60 min (33.33%), Maintenance 30 min (16.67%).

## Limits of interpretation

OEE depends on how planned time, downtime, the ideal cycle and good units are defined. The chosen single-cause-per-shift CSV is deliberately simpler than real event logs; it cannot attribute multiple downtime causes within one shift. Do not treat the sample ranking as a real operational decision, or compare its OEE with another operation without matching definitions. No real production system or MES/SCADA integration was tested.
