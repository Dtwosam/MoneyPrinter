# Printer V1 V2-9.8B Cooperative Later-Cycle Repair Design Authoritative Adoption

Date: 2026-08-20

Lane: `V2-9.8B Cooperative Later-Cycle Repair Design Authoritative Adoption / Review`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_COOPERATIVE_LATER_CYCLE_REPAIR_DESIGN_ADOPTION_PASS`

This PASS makes the existing cooperative later-cycle D4/D5 repair design authoritative for the next implementation lane. It does **not** implement code, weaken frozen RED tests, run Printer, create or reuse an authorization, contact providers, or mutate the authoritative database.

## Adopted design identity

| Item | Value |
|---|---|
| Design document | `docs/printer-v1-v2-9-8b-cooperative-later-cycle-repair-design.md` |
| Supporting plan | `docs/superpowers/plans/2026-08-20-cooperative-later-cycle-repair.md` |
| Source side branch | `origin/agent/v2-9-8b-cooperative-later-cycle-repair` |
| Source tip at copy | `87cfa1e5f3f64d3d606fb3c43732f20ebde52398` |
| Design commit | `057d4c4a6d71885d698fbba61ddf748544a1ab22` |
| Plan commit | `e0362c44b69e8b8797d02196af1fb963c93d44bf` |
| Design/plan bytes vs side branch | identical |

Frozen RED tests remain on the side branch tip and are not landed by this adoption:

- `tests/test_v2_9_8b_cooperative_later_cycle_repair.py` @ `9eaceaeda42d2627dad1be677fb23a98962e3d20`
- temporary proof workflow @ `87cfa1e5f3f64d3d606fb3c43732f20ebde52398`

Those RED tests are the frozen contract for the implementation lane. They must be brought in without weakening.

## Review against Printer law

The adopted design is accepted because it:

1. targets only D4 premature campaign shutdown and D5 later-cycle under-service;
2. keeps one Central Scheduler and one Source Governor;
3. preserves Slice-G / `_later_cycle_acquisition_deadline_conflict()` lifecycle-deadline priority;
4. requires cooperative recheck before stale `pending is None` terminal/sleep;
5. rejects `CLAIMED` or ambiguous refresh-wait ownership;
6. forbids threads, background workers, independent provider loops, and Source Governor bypass;
7. forbids capacity, cadence, retry, or endpoint-rotation increases;
8. leaves retrieval, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets/keys, paid APIs, scoring/ranking/confidence, embeddings/vectors, and 12h/24h locked;
9. permits only offline/disposable proof.

No law conflict requiring redesign was found.

## Preconditions from the authorization block

This adoption follows:

- historical Post-D123 readiness PASS:
  `docs/printer-v1-v2-9-8b-post-d123-two-cycle-four-token-authoritative-readiness.md`
- successor authorization block:
  `docs/printer-v1-v2-9-8b-post-d123-d4-d5-cooperative-coordination-authorization-block.md`
  verdict `V2_9_8B_POST_D123_D4_D5_COOPERATIVE_COORDINATION_AUTHORIZATION_BLOCKED`

New 4/2/2 authorization remains blocked until D4/D5 implementation, bounded proof, and independent closeout complete, and any remaining separate blockers (including GoPlus/Solana-native safety redundancy) are handled.

## Exact next permitted action

`V2-9.8B Cooperative Later-Cycle Repair Implementation`

Minimum implementation surface remains primarily:

`src/printer_v1/operator_cli/one_command_15m_factory.py`

Required behavior remains the frozen contract:

- `attempt_wake_at` on `FourTokenAdmissionBoundaryResult`
- `_active_later_cycle_refresh_wake_at(...)` fail-closed refresh resolver
- `_cooperative_later_cycle_recheck(...)`
- main-loop recheck before stale `pending is None` terminal/sleep

Do not weaken the frozen RED tests to obtain GREEN.
Do not run Printer.
Do not create or reuse an authorization.
Do not contact providers or mutate the authoritative database for proof.

## Locks preserved

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval and financial capabilities remain locked. No Migration 059. No Cycle 3 / six-token activation.

The active Printer V1 source stack wins any conflict with this document.
