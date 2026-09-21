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

The natural-memory four-token test exposed and verified a second P1 repair: both
4H close paths now bind exact physical ownership before independent quality
readers. Binding leaves CLOSE_PENDING; only the real quality and terminal owners
can declare success. The offline integration passed through two cycles, four
clean 4H episode/fingerprint pairs, terminal zero-state and released lease without
fixture-driven quality promotion. Related stale close fixtures were corrected.

## Proven blockers and limits

The reproduced cadence and 4H binding blockers are repaired. Full
acquisition-to-canonical-report proof is not yet established: the natural-memory
case still starts from prevalidated selection/candidate evidence. The legacy
fixture is explicitly labeled orchestration-only. See the repair document for
the remaining public-composition proof design and verified boundaries.

Historical primary failure remains LEASE_RENEWAL_SQLITE_LOCKED; the exact lock
holder is NOT PROVEN. The secondary fresh-transaction defect was already repaired.
Historical six-unit evidence is incomplete and must never be reconstructed.
The user reports the dedicated historical cleanup completed; this development
repair has not re-read or modified authoritative operational state. Consumed
operational authorizations remain permanently non-reusable.

## Exact next permitted action

Extend the disposable public-composition fixture through governed acquisition,
natural memory, measured six-unit accounting and accepted canonical report. No
operational launch, provider call, authorization, cleanup, retry or resume is
permitted by this development task.
