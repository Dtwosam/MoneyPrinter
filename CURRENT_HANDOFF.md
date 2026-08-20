# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B Cooperative Later-Cycle Repair Design Authoritative Adoption / Review`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_COOPERATIVE_LATER_CYCLE_REPAIR_DESIGN_ADOPTION_PASS`

The cooperative later-cycle D4/D5 repair design is now authoritative. Implementation is the next permitted lane. New 4/2/2 authorization remains blocked until implementation, bounded offline proof, and independent closeout complete.

## Adopted design authority

Design:

`docs/printer-v1-v2-9-8b-cooperative-later-cycle-repair-design.md`

Supporting plan:

`docs/superpowers/plans/2026-08-20-cooperative-later-cycle-repair.md`

Adoption closeout:

`docs/printer-v1-v2-9-8b-cooperative-later-cycle-repair-design-adoption.md`

Source side branch tip copied from:

`origin/agent/v2-9-8b-cooperative-later-cycle-repair` @ `87cfa1e5f3f64d3d606fb3c43732f20ebde52398`

Frozen RED tests remain the implementation contract and must be landed/used without weakening:

`tests/test_v2_9_8b_cooperative_later_cycle_repair.py`

## Preserved prior states

Historical Post-D123 readiness PASS remains valid for the D123 checklist only:

`docs/printer-v1-v2-9-8b-post-d123-two-cycle-four-token-authoritative-readiness.md`

Successor authorization block remains in force until D4/D5 closeout:

`docs/printer-v1-v2-9-8b-post-d123-d4-d5-cooperative-coordination-authorization-block.md`

Verdict still controlling for authorization posture:

`NOT READY FOR NEW 4/2/2 AUTHORIZATION`

## Exact adopted executable baseline for the repair

Product branch:

`agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation`

Adopted D123 executable merge:

`8709a971cb463a258525831e82c3672865d21b47`

Design baseline named by the repair design:

`91535856be9e335ede15308c3b422b5e8a4e8bec`

## Exact next permitted action

`V2-9.8B Cooperative Later-Cycle Repair Implementation`

Apply the minimum coordinator repair primarily in:

`src/printer_v1/operator_cli/one_command_15m_factory.py`

Frozen contract:

- `attempt_wake_at` boundary field
- refresh-wait resolver rejecting `CLAIMED` / ambiguous ownership
- cooperative later-cycle recheck before stale `pending is None` terminal/sleep
- preserve Central Scheduler ownership and lifecycle-deadline priority
- no independent provider loop, thread, background scheduler, or Source Governor bypass

Then: bounded offline proof → independent closeout → only then reconsider fresh 4/2/2 authorization readiness.

GoPlus / Solana-native safety redundancy remains a separate residual blocker before another authoritative 4/2/2 campaign unless separately closed.

Do **not** weaken frozen RED tests.
Do **not** create a new authorization from this handoff.
Do **not** run Printer from this handoff.
Do **not** reuse any consumed authorization or historical application artifact.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The 4/2/2 contract remains: 4 total tokens; 2 cycles; 2 tokens per cycle; Cycle 2 fresh/disjoint from Cycle 1; freeze minimum depth 4; exact-pool liquidity floor `$3,000`; minimum spacing `300s`; `WINDOW_15M` root; lawful token-local `15m -> 1h -> 4h`; retries `0`; endpoint rotation `false`; one-shot only; no rerun/resume/restart/successor.

The active authority stack wins any conflict with this handoff.
