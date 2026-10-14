# Synthetic downtime-recovery what-if analysis

This is a conditional arithmetic illustration using synthetic shifts, not a prediction,
an optimization recommendation, or evidence of recoverable factory capacity.

Baseline OEE: **73.40%**. Hypothetical cause-specific downtime reduction: **50%**.

## Assumptions

- Planned production time, ideal cycle time, observed performance and observed quality are fixed.
- Recovered downtime becomes additional running time at those same observed performance and quality rates.
- Each cause is treated **independently**; a scenario does not imply that the change is feasible.
- Fractional recovered minutes and inferred extra good units are continuous planning quantities, not actual counts.
- No labor, material, line-balance, reliability, safety, or cost constraints are modeled.

For one cause: OEE gain = (recovered minutes / planned minutes) × Performance × Quality.

## One-cause-at-a-time scenarios

| Cause | Recorded downtime (min) | Hypothetical recovered (min) | OEE gain (percentage points) | Conditional OEE |
| --- | ---: | ---: | ---: | ---: |
| Material shortage | 90 | 45.00 | 2.62 | 76.02% |
| Setup | 60 | 30.00 | 1.75 | 75.15% |
| Maintenance | 30 | 15.00 | 0.87 | 74.28% |

Inputs and outputs are fictional; validate assumptions against real operating data before decisions.
