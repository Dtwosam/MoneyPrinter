# Printer V1 V2-9.8B Four-Token Slot-Order / Rollback Post-Repair Rereadiness Review

Date: 2026-08-14

Review baseline / exact repair closeout HEAD: `35d7db2cb7cee5799f0489a51cf6ff3ccdead1f8`

Verdict: `V2_9_8B_FOUR_TOKEN_SLOT_ORDER_ROLLBACK_POST_REPAIR_REREADINESS_PASS_READY_FOR_FRESH_AUTHORIZATION`

## Boundary

Independent read-only/static rereadiness review only. No production code, tests, migration, schema, source fetch, Printer runtime, authoritative DB mutation, memory generation, authorization artifact, proof run, retrieval, decision, position, trade, audit, PnL, wallet, signing, or real funds are created or executed here.

The consumed four-token authorization remains permanently consumed and may never be reused, resumed, restarted, or treated as successful.

## Independent review findings

1. The repair closeout descends from clean incident baseline `3c8ab8612814d63ab9dcfde4220568302e0a5933`.
2. The permanent net diff from that baseline contains exactly five files: blocker audit, repair design, repair closeout, `src/printer_v1/operator_cli/one_command_15m_factory.py`, and `tests/test_v2_9_8b_four_token_slot_order_rollback_repair.py`.
3. The four-token Cycle-1 production path now preserves the generic selected-target list for ordinary behavior but, when four-token proof control is active, requires exact campaign/run/cycle identity and replaces opening-planning targets with `_cycle_targets_for_factory(...)` before `_plan_opening_jobs()`.
4. `_cycle_targets_for_factory(...)` remains the authoritative campaign-slot path already used for Cycle 2; the repair does not infer slot identity from lexical mint order.
5. The outer `except Exception as exc` boundary now checks `conn.in_transaction` and rolls back before classifying/preserving the original proof/orchestration fault.
6. The terminal reconciliation owner and its fresh-transaction guard were not weakened by the production diff.
7. No migration, schema change, new Source Governor path, new Central Scheduler path, retry, selection-policy change, source-budget change, token-capacity change, public/default widening, or financial/retrieval capability appears in the permanent diff.

## Closeout evidence reviewed

The corrected offline closeout verifier executed the new regression plus the two nearest historical four-token regressions and reported **17 passed in 15.80s**. The changed production module compiled successfully and `git diff --check` passed.

The first temporary verifier attempt did not exercise tests because its import path was incomplete. That verifier-only defect was corrected with `PYTHONPATH=src`; no production change was made for it. The temporary workflow was removed, and its add/fix/delete sequence has zero net file difference from the repaired permanent tree.

This review does not rerun the tests because the closeout evidence is fresh, exact-head, offline, and directly affected; rereadiness is a separate static independence check rather than another implementation/proof lane.

## Rereadiness decision

The two software blockers proven by the consumed attempt are repaired and have sufficient offline closeout evidence for the four-token program to proceed to a **new, separate fresh-authorization preparation lane**.

This verdict does **not** authorize a four-token proof. It authorizes only preparation of a brand-new one-use authorization against the exact future authorized HEAD, followed by a separate independent authorization review. Only a PASS from that review may permit one bounded four-token proof.

## Money-usefulness contribution

Rereadiness restores a controlled path toward proving four-token concurrent memory throughput without sacrificing exact token-slot attribution or terminal cleanup truth. It reduces the chance that another scarce one-shot proof is consumed by the same deterministic internal defects.

## What improves

- Four-token Cycle-1 opening work now follows authoritative campaign slot ownership.
- Failed pre-commit work is cleared before terminal reconciliation.
- Exact fail-closed identity and fresh-transaction guards remain intact.
- The next proof, if separately authorized, can test actual four-token behavior rather than the repaired ordering/transaction defects.

## What remains locked

Four-token operation remains operationally unproven until a later separately authorized bounded proof passes. Six-token proof/capacity advancement remains locked. 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper audits, PnL, wallets, private keys, signing, live execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors remain locked.

## Proof/test required before operational four-token readiness

1. Prepare a brand-new one-use four-token authorization in a separate lane, bound to the exact approved HEAD and immutable proof contract.
2. Independently review that authorization and close PASS.
3. Only then run exactly one bounded four-token proof under the existing Source Governor, Central Scheduler, campaign/factory ownership, budgets, safe-stop, and no-auto-successor rules.
4. Classify and close that consumed attempt from its evidence; do not automatically retry a blocker or failure.

## Functionality Risks / Setbacks / Efficiency Blockers

- Offline repair tests cannot establish external source availability or future end-to-end proof success.
- A fresh proof may expose a different blocker; rereadiness is not a guarantee of proof PASS.
- Any authorization must bind the exact then-current code/tree; intervening production drift invalidates stale authorization assumptions.
- The previous authorization is consumed and cannot be recycled to save time.
- Six-token advancement must not begin from this verdict; the roadmap still requires four-token proof closeout first.

## Next permitted lane

`V2-9.8B Four-Token Fresh Authorization Preparation`, followed by a separate independent authorization review. No proof may run before both steps close PASS.
