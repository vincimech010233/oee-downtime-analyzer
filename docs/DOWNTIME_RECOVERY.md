# Downtime-recovery scenario tool

## Industry problem and intended users

Operations analysts, junior manufacturing engineers and industrial software QA engineers need a transparent way to illustrate how fixing one downtime category could affect Overall Equipment Effectiveness (OEE). This offline extension to the existing OEE analyzer computes separate conditional scenarios, one category at a time, using fully fictional data.

Commercial OEE and downtime systems already exist: Evocon (https://evocon.com/downtime-tracking-software/), SAP Digital Manufacturing (https://help.sap.com/docs/sap-digital-manufacturing/insights/oee-calculations) and MachineMetrics (https://www.machinemetrics.com/downtime-tracking-software). This is not claimed to be a new or equivalent commercial product. It is an auditable offline educational/portfolio calculator.

## Installation, requirements and commands

Python 3.10+; Python standard library only, no packages to install and no network access. The source was tested locally on Linux Python 3.13.5. Run from the repository root:

    python3 oee_recovery.py data/synthetic_shifts.csv --recovery-percent 50
    python3 oee_recovery.py data/synthetic_shifts.csv --recovery-percent 100 > /tmp/recovery.md
    python3 -m unittest discover -s tests -p 'test_*.py' -v

The optional percentage is an integer between 0 and 100; default is 50. Input CSV schema, size limits and rejection criteria are inherited directly from oee.py and described in the main README. The script prints Markdown to stdout and never writes files itself; redirects are caller-controlled. The original OEE CLI and CSV remain unchanged.

## Mathematical model and interpretation

For each recorded cause: recovered minutes = downtime for that cause × recovery_fraction.

Conditional OEE gain = (recovered minutes / total planned minutes) × observed Performance × observed Quality.

Conditional OEE = baseline OEE + conditional OEE gain. Calculations use exact Python Fraction arithmetic until display formatting. Causes are analyzed independently; do not add the conditional OEE values across rows.

**Assumptions:** Unchanged planned time, ideal cycle, performance and quality; all hypothetically recovered downtime operates at the baseline effective yield. No actual additional production is observed. A downtime reduction by itself cannot increase measured OEE without producing additional good units. This is **not a forecast**, causal estimate, optimization, production commitment, cost saving, or validated plant decision. No availability of material, staffing, machine constraints, maintenance obligations or feasibility is modeled. Where operating time or total output is zero, the tool abstains because the baseline rate is undefined. Where downtime is zero, no recovery scenario is invented.

## Reproducible fictional example

See examples/recovery_report.md, captured from the 50% CLI command on 2026-10-14. Synthetic baseline OEE 73.40%; the fictional 90-minute Material shortage cause yields a hypothetical reduction of 45.00 minutes, +2.62 percentage points and conditional OEE 76.02%. These are computed numbers, not measured improvement in any company. The example is a Markdown text artifact; no graphical screenshot was produced.

## Security, licensing and verification

MIT license, inherited from this repository; no external Python dependencies. The new script neither reads network resources nor connects to MES/SCADA, third-party infrastructure, telemetry, private company data or credentials. The existing parser bounds CSV size to 1 MB, input rows to 1000 and distinct causes to 12. Source labels in terminal output can be sensitive if real data is voluntarily supplied: avoid publicly exposing them. The project is not a hardened malicious-CSV sandbox.

Local validation on 2026-10-14 against GitHub baseline oee.py blob a107bc044950a68bf73afafdfa9f28764bad251e and unchanged baseline tests blob 27d064164b837c0eeb2d3f4d5d890dba8f5d8187: 14 deterministic tests PASS, Python compilation PASS, with Python 3.13.5 on Linux. Tests include hand-checkable fractions, no-downtime and undefined baselines, zero/full recovery, invalid CLI inputs, deterministic output and original six regression tests. GitHub Actions has read-only permissions and uses pinned checkout commit 11bd71901bbe5b1630ceea73d27597364c9af683. Hosted CI status is **NOT VERIFIED** until checked on the exact PR head. No production or inter-platform validation is claimed.

## LEARN

LEARNING: An OEE scenario requires a clear counterfactual production assumption, not only a promise of less downtime. EVIDENCE: exact-arithmetic model, reproducible synthetic fixture and unit tests. IMPACT: explicitly label results conditional and abstain for undefined rates. CONFIDENCE: high for synthetic arithmetic; no demonstrated accuracy for real production. CARRY_FORWARD: validate industrial inputs, causal assumptions and costs before pursuing decisions.
