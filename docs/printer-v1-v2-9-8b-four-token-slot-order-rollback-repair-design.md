# Printer V1 V2-9.8B Four-Token Slot-Order / Rollback Repair Design

Date: 2026-08-14

Audit baseline: `24884644da1401060882d0bb11e3e2efebc2c7f0`

Verdict: `V2_9_8B_FOUR_TOKEN_SLOT_ORDER_ROLLBACK_REPAIR_DESIGN_PASS_READY_FOR_TDD`

## Boundary

Design only. No source fetch, runtime, authoritative DB mutation, memory generation, fresh authorization, proof rerun, retrieval, decision, position, trade, audit, PnL, wallet, signing, or real funds.

## Repair A — Cycle-1 factory targets follow campaign slot ownership

Owner: `src/printer_v1/operator_cli/one_command_15m_factory.py`.

The generic `_selected_targets()` loader remains unchanged because its deterministic lexical order is used by older/non-campaign factory behavior.

For four-token proof mode only, immediately before Cycle-1 `_plan_opening_jobs()`:

1. resolve the exact existing Cycle-1 campaign identity already bound to the factory run;
2. replace the planning target list with `_cycle_targets_for_factory(...)` for that exact campaign/run/cycle;
3. keep `_plan_opening_jobs()` and `_precreate_proof_15m_window()` unchanged so list position 1/2 now matches authoritative `slot_ordinal` 1/2;
4. fail closed if exact two campaign slots are absent or ambiguous.

Cycle 2 keeps its existing `_cycle_targets_for_factory()` path. No slot identity is inferred from mint lexical order in four-token mode.

Must not change selection eligibility, selection randomness, batch persistence, target identities, tracking lanes, source budgets, cycle capacity, or public/default token capacity.

## Repair B — rollback failed pre-commit work before terminal reconciliation

Owner: `src/printer_v1/operator_cli/one_command_15m_factory.py`.

In the outer `except Exception as exc` path that converts unexpected orchestration failures into `STOP_PREFLIGHT` or preserves a proof fault:

- if `conn.in_transaction` is true, call `conn.rollback()` before terminal reconciliation/reporting can run;
- preserve the original exception and `orchestration_error` semantics;
- do not commit failed partial planning writes;
- do not weaken `reconcile_four_token_cycle_terminal()` or its fresh-transaction guard.

The repair is deliberately at the exception boundary, not inside the terminal owner. Terminal reconciliation must continue to reject callers that directly invoke it with an unrelated open transaction.

## TDD order

### RED 1 — slot-order reproduction

Create a focused fixture where:

- selection-batch lexical order is `CAGt...`, `yUme...`;
- authoritative Cycle-1 campaign slots are slot 1 `yUme...`, slot 2 `CAGt...`;
- four-token opening planning reaches proof 15m precreation.

Before repair the first opening plan must fail with the existing proof 15m target/slot identity mismatch. The test must assert the fixture really has opposing batch and slot orders.

GREEN: four-token Cycle 1 plans from campaign slots and preserves exact token/pair identity for both slots.

### RED 2 — dirty exception boundary

Inject a deterministic failure after a write has opened the outer transaction but before the post-opening commit. Observe the terminal reconciliation boundary.

Before repair the connection remains in a transaction and the fresh-transaction guard masks/compounds the original failure.

GREEN: the exception handler rolls back before reconciliation, the original `STOP_PREFLIGHT`/error remains authoritative, and failed partial opening writes are absent.

### Guard regressions

- `_selected_targets()` lexical ordering remains unchanged for non-four-token paths.
- direct terminal reconciliation with an intentionally open transaction still fails closed.
- Cycle 2 still uses campaign slot order.

## Minimum verification

During RED/GREEN: new focused test(s), nearest four-token opening/15m/campaign-slot/terminal tests, `py_compile` for changed Python, `git diff --check`.

At repair closeout, run the broader directly affected four-token/factory/campaign-terminal surface and compare any failures against the exact design baseline rather than expanding into unrelated repository failures.

No live/source-backed proof is allowed in this repair lane.

## Money-usefulness contribution

The repair protects scarce one-shot proof attempts from deterministic internal ordering/cleanup defects and keeps evidence attribution bound to the same slot identity from campaign activation through memory-window creation.

## What improves

- authoritative slot identity survives Cycle-1 factory handoff;
- fail-closed mismatch checks stay meaningful;
- failed pre-commit work cannot poison terminal reconciliation;
- the primary error is retained for diagnosis.

## What remains locked

No capability unlock. Four-token capacity still requires later independent rereadiness, a brand-new authorization, independent authorization review, and one bounded proof. Six tokens and all later financial/retrieval capabilities remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Reloading campaign slots too early would be wrong if slots were not yet durable; implementation must place the reload only after the campaign activation/handoff has established them and immediately before opening-plan creation.
- Broadly changing `_selected_targets()` would risk older selection/factory contracts and is prohibited.
- Rollback must discard only uncommitted failed work; committed campaign/selection authority must remain durable.
- Catching/ignoring reconciliation errors or weakening the fresh-transaction guard is prohibited.
- No historical claim is made that the consumed attempt would otherwise have completed; only these two proven software defects are repaired.