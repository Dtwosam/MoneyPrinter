# Printer V1 Handoff

## Current capability

Printer remains Solana-only, memecoin-only and paper-only. Source Governor and
Central Scheduler retain sole ownership. Clean-memory, identity, provenance,
capability and one-shot operational authorization gates remain fail-closed.
WINDOW_5M is support-only; WINDOW_12H/24H and decision/trading surfaces stay locked.

## Latest meaningful result

The four-token audit found a final acceptance gate hardcoded to two NORMAL lanes.
It now validates exact per-token 15m cadence from the frozen lane policy, including
FAST and mixed lanes. Missing, extra or conflicting evidence still blocks PASS.
Disposable regressions cover all lane combinations, negative evidence and durable
mixed/FAST finalizer acceptance. See `docs/four-token-audit-repairs.md`.
The SQLite reader-contention regression also uses a package-qualified import and
passes under the default interpreter invocation without custom PYTHONPATH.

## Proven blockers and limits

A stronger natural-memory test exposed a separate 4H quality-reader ordering
blocker: the physical memory row was linked to its campaign only after quality
validation required that link. Its repair and integration verification are in
progress. Full acquisition-to-canonical-report proof is not yet established.

Historical primary failure remains LEASE_RENEWAL_SQLITE_LOCKED; the exact lock
holder is NOT PROVEN. The secondary fresh-transaction defect was already repaired.
Historical six-unit evidence is incomplete and must never be reconstructed.
The user reports the dedicated historical cleanup completed; this development
repair has not re-read or modified authoritative operational state. Consumed
operational authorizations remain permanently non-reusable.

## Exact next permitted action

Complete disposable four-token natural-memory and reporting-boundary verification,
review the repairs and commit each meaningful change with its regression. No
operational launch, provider call, authorization, cleanup, retry or resume is
permitted by this development task.
