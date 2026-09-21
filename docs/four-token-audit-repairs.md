# Four-token audit repairs — 2026-09-21

The post-audit user request authorizes engineering repairs, using disposable state
and offline adapters only. No operational or historical state is changed.

## F-01 — P1: lane-specific acceptance

The final gate required an aggregate 16 non-close snapshots, rejecting valid FAST
and mixed lanes. The replacement reads the authoritative frozen-lane cadence:
8 NORMAL or 15 FAST non-close snapshots per token. Expected, planned and actual
counts must each match; require complete coverage, zero missing observations and
one succeeded close. The selected and cadence lanes must agree. A missing snapshot
on one token cannot be hidden by an extra snapshot on another.

The initial regression reproduced 20 failures and nine passes before repair.
Focused cadence plus durable finalizer tests passed (51 tests, six subtests).
Related accounting, SQLite attribution and lease-contention verification passed
(123 tests, six subtests). Durable tests seed terminal evidence and do not claim
natural acquisition or memory-production coverage. Diff review confirmed the
change is confined to acceptance; no cadence, budget or execution policy changed.

## Remaining repair work

- F-03: qualify the SQLite heartbeat test's sibling import and verify default
  interpreter invocation without a custom PYTHONPATH.
- F-02: label legacy orchestration coverage honestly and exercise natural memory
  producers without injected promotion, safety, Scheduler or health outcomes.
- The stronger test exposed a 4H binding-before-quality defect; preserve exact
  physical ownership before the independent reader, with success still conditional
  on all quality gates. Record its complete verification before claiming repair.

A memory-only integration is not a full nomination/holder acquisition, measured
six-unit accounting and canonical accepted-report proof. That limit must remain
explicit. Historical lock-holder attribution remains NOT PROVEN.
