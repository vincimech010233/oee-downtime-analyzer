# Offline downtime event audit

## Purpose and business problem

The existing OEE CLI accepts one downtime cause per shift. Real production shifts can contain several stop reasons. This companion tool lets a manufacturing analyst reconcile individual stops with the shift summary before interpreting the cause Pareto. It does not replace a MES.

SAP OEE already supports event-time data, stop reason codes and splitting events:
https://help.sap.com/docs/SAP_MANUFACTURING_INTEGRATION_AND_INTELLIGENCE/386f983a90564cc8bda9a53dffda9691/8e936a54dc4b054ee10000000a423f68.html

Tulip also documents machine downtime reasons:
https://support.tulip.co/docs/machine-attributes-downtime-reasons-and-states

This project is a narrow, offline data integrity checker. There is no claim of integration with commercial products.

## Requirements, setup and use

Requires Python 3.10 or newer, the existing repository, and no external packages, credentials, network, or elevated access.

From the repository root:

    python3 downtime_event_audit.py data/synthetic_shifts.csv data/synthetic_downtime_events.csv --output-dir results/example-event-audit
    python3 -m unittest discover -s tests -p 'test_*.py' -v

Use a fresh output directory for each invocation. Outputs are event_audit.json and event_audit.md; files are never overwritten.

## Input contract

The original summary CSV has the same schema documented by oee.py.

The event CSV has four fields: shift, start_minute, end_minute, cause. See data/synthetic_downtime_events.csv. Time is a whole-minute offset from the beginning of the named shift; intervals are half-open. Event duration is end minus start. A shift must have a unique name, events must lie within the shift, and adjacent events are valid. Overlapping events, unknown names, malformed labels, duplicate shift names and missing or excess downtime are rejected. All events for each shift must add up to its summary downtime, including zero-duration totals.

Limits: 1 MB per CSV, 1000 summary shifts, 5000 events, 100 event cause labels, up to 1440 planned minutes per shift.

## Synthetic results and verifiable evidence

The fictional five-event sample reconciles 180 minutes across three shifts. Event causes: Material shortage 100 minutes (55.56 percent), Setup 50 minutes (27.78 percent), Maintenance 30 minutes (16.67 percent). Shift-summary OEE remains 73.40 percent. The original one-cause-per-shift data ranked causes 90/60/30 minutes, showing why event attribution is useful without making claims about a real factory.

See examples/event_audit.json and examples/event_audit.md for checked-in, reproducible outputs. Text tables are the verifiable visual artifact; no real plant screenshots are claimed.

## Tests

On 2026-10-12, 14 deterministic companion tests passed locally in an isolated environment using a verification copy of the necessary oee.py functions transcribed from this repository. Tests cover intervals, reconciliation, input validation, output collisions, reproducibility and symlink rejection. The pre-existing tests in test_oee.py were not run in that isolated copy. The new GitHub Actions workflow is configured to run all repository tests on Python 3.10 and 3.12. Do not claim hosted CI success until checks are observed.

## Security and limitations

This runs only against local input. It does not connect to production equipment, collect telemetry, execute input commands or access third-party infrastructure. CSV input is size-bounded; output files are created privately with mode 0600 on POSIX and without overwriting existing files. Run unprivileged in trusted stable directories. Input ancestor symlinks, hostile concurrent filesystem changes, and crash-atomic two-file output are not fully handled.

The model has one synthetic time axis per shift, with no real timestamps, time zones, multi-machine line state, breaks, subminute events or root-cause verification. Reconciliation proves arithmetic consistency, not measurement accuracy or actual causality. Real industrial deployment is not validated.

## License and provenance

MIT, per repository LICENSE. The code and fictional data are original; no third-party code or customer data is bundled. External links are background references, not endorsement or validation.

## LEARN

LEARNING: A single shift cause can hide event-level attribution.
EVIDENCE: Synthetic event ranking 100/50/30 vs summary 90/60/30 minutes; both total 180, OEE unchanged at 73.40 percent.
IMPACT: Reconcile event data before interpreting downtime causes.
CONFIDENCE: HIGH for deterministic synthetic arithmetic; UNRESOLVED for real industrial validity.
CARRY_FORWARD: Add timestamp and equipment semantics only with authorized requirements and reproducible fixtures.
