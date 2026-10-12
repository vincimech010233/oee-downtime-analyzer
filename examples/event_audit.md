# Synthetic downtime event reconciliation

**Status:** RECONCILED against the supplied shift totals; not field-validated.

Events: 5; downtime: 180 min; shift-summary OEE: 73.40% (unchanged).

## Event-level downtime Pareto

| Cause | Minutes | Share | Cumulative |
| --- | ---: | ---: | ---: |
| Material shortage | 100 | 55.56% | 55.56% |
| Setup | 50 | 27.78% | 83.33% |
| Maintenance | 30 | 16.67% | 100.00% |

## Shift reconciliation

| Shift | Expected min | Event min | Events |
| --- | ---: | ---: | ---: |
| Afternoon | 30 | 30 | 1 |
| Morning | 60 | 60 | 2 |
| Night | 90 | 90 | 2 |

Only one continuous time axis per named shift is modeled. Events must not overlap.
The summary CSV's single cause label is intentionally not used for the event-level ranking.
All inputs are synthetic; this output makes no claim about a real factory, causal attribution, or validated MES/SCADA integration.
