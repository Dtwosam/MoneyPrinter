# Printer V1 V2-9.8B Four-Token Slot-Order / Rollback Blocker Audit

Date: 2026-08-14

Baseline: `3c8ab8612814d63ab9dcfde4220568302e0a5933`

Verdict: `V2_9_8B_FOUR_TOKEN_SLOT_ORDER_ROLLBACK_BLOCKER_AUDIT_PASS_REPAIR_REQUIRED`

## Boundary

Read-only/static incident audit. The consumed proof authorization remains permanently consumed. This audit authorizes no proof rerun, fresh authorization, Printer runtime, source fetching, authoritative DB mutation, memory generation, retrieval, decision, position, trade, audit, PnL, wallet, signing, or real-funds capability.

Use this audit inside the active Printer V1 source stack, including `AGENTS.md`, the Clean Master Spec, Post-RC Build Order, Memory Factory Guide, current-state memory-growth audit, active V2 memory-growth build order, Python Builder Guide, and the existing V2-9.8B four-token design/closeout stack.

## Incident evidence

Operator read-only SQLite evidence from the consumed attempt showed the same two Cycle-1 targets in two different orders:

- authoritative campaign slots: slot 1 = `yUmeQo96g6MurikjHiMg7u23X5yQXJ9SQpoJPcbpump`, slot 2 = `CAGtwKrcnwgLABdg5o16oMczxUV6i1pj973K9XWQpump`;
- generic factory reload: `CAGt...pump`, then `yUme...pump`.

The first proof 15m precreation then failed with target/slot identity mismatch. The later terminal path reported a fresh-transaction error and left campaign ownership unreconciled.

## Finding 1 — authoritative slot order is destroyed before Cycle-1 opening work

`one_command_15m_factory._selected_targets()` loads selected batch items and explicitly orders them by `lower(i.token_mint), lower(i.pair_address)`.

`_plan_opening_jobs()` does not receive a durable slot ordinal. It derives `slot_ordinal = target_index + 1` from that list position. In four-token mode it immediately calls `_precreate_proof_15m_window()` with the derived ordinal.

`_precreate_proof_15m_window()` correctly resolves the authoritative campaign cycle/slot and rejects a token/pair mismatch. The guard is correct; the caller ordering is wrong.

The same module already has `_cycle_targets_for_factory()`, which loads the exact campaign token-slot rows ordered by `s.slot_ordinal`. Cycle 2 already uses that canonical helper before `_plan_opening_jobs()`.

Root cause: Cycle 1 still feeds the generic lexicographically ordered selection-batch reload into a proof path whose slot identity is owned by campaign token slots.

Classification: `COMMITTED_CODE_DEFECT`.

## Finding 2 — the primary identity exception leaves an uncommitted write transaction

Before initial opening work, the factory persists handoff/cancellation metadata. The enclosing flow calls `_plan_opening_jobs()` and commits only after it returns.

When `_precreate_proof_15m_window()` raises the legitimate fail-closed identity exception, control reaches the outer `except Exception` branch. That branch records `STOP_PREFLIGHT` / `orchestration_error` but does not rollback the open SQLite transaction.

Four-token terminal reconciliation intentionally rejects `connection.in_transaction` with `cycle terminal reconciliation requires a fresh transaction`.

Root cause: exceptional pre-commit planning exits do not release the failed unit of work before terminal reconciliation begins. The fresh-transaction guard is correct and must not be weakened.

Classification: `COMMITTED_CODE_DEFECT`.

## Scope decision

A narrow two-part repair is justified:

1. for four-token Cycle 1 only, load opening targets from the already-authoritative campaign cycle slots in `slot_ordinal` order before planning opening jobs; preserve `_selected_targets()` semantics for non-four-token paths;
2. on an exception handled by the outer factory terminal path, rollback any open SQLite transaction before terminal reconciliation/reporting continues.

No migration, new owner, new Scheduler path, new Source Governor path, retry, capacity widening, or identity-guard weakening is justified.

## Money-usefulness contribution

This repair lets a future separately authorized four-token proof measure actual concurrent memory-factory behavior instead of consuming one-shot authority on an ordering artifact, while preserving fail-closed identity and transaction ownership.

## What improves

- Cycle-1 factory ordering becomes identical to campaign slot ownership.
- The original fail-closed error remains visible instead of being masked by a dirty-connection error.
- Terminal cleanup can begin from the transaction state its owner requires.

## What remains locked

Four-token capacity remains unproven. Six-token proof, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper audits, PnL, wallets, signing, live execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors remain locked.

## Proof/test required

TDD must first reproduce both defects offline, then prove:

- Cycle-1 selection-batch lexical order may differ from campaign slot order, but four-token opening work uses exact slot 1/2 ownership;
- non-four-token target loading/order is unchanged;
- a pre-opening exception with `conn.in_transaction == True` is rolled back before terminal reconciliation;
- the existing fresh-transaction guard still rejects genuinely dirty direct calls;
- the original exception/stop cause is not replaced by cleanup failure.

Use only focused/directly affected tests, compile checks, and diff checks during implementation. No live proof or authorization is part of this repair.