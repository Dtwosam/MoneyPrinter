# Printer V1 V2-9.8B Four-Token Slot-Order / Rollback Repair Closeout

Date: 2026-08-14

Verdict: `V2_9_8B_FOUR_TOKEN_SLOT_ORDER_ROLLBACK_REPAIR_CLOSEOUT_PASS_READY_FOR_INDEPENDENT_REREADINESS_REVIEW`

## Scope and anchors

- Clean incident baseline: `3c8ab8612814d63ab9dcfde4220568302e0a5933`
- Blocker audit: `24884644da1401060882d0bb11e3e2efebc2c7f0`
- Repair design: `45314f5a...`
- Corrected RED: `3e42df1f232e49f5f54d9839c713907c82f93863`
- GREEN production repair: `2dc3fe907c3d21c2f9acab3a906ade7889a20622`
- Repaired permanent tree anchor before closeout verification: `20363a489b93bba696f279543a1e1bff72b500d0`
- Corrected temporary closeout verifier commit: `314d741dc22bf7be7869142f3962e789471e3846`
- Temporary verifier removed at: `699778425ee7683ac395c7b3d18cd3eaf83f58ab`

The consumed four-token authorization remains permanently consumed. This closeout creates no fresh authorization and authorizes no proof rerun, Printer runtime, source fetch, authoritative DB mutation, memory generation, retrieval, decision, position, trade, audit, PnL, wallet, signing, or real funds.

## Repair closed

1. Four-token Cycle 1 reloads its opening targets from the exact authoritative campaign cycle slots before `_plan_opening_jobs()`, preserving `slot_ordinal` ownership through proof 15m precreation.
2. Generic `_selected_targets()` lexical ordering remains unchanged for non-four-token behavior.
3. Cycle 2 retains its existing authoritative campaign-slot path.
4. The outer factory exception boundary rolls back an open SQLite transaction before terminal reconciliation.
5. `reconcile_four_token_cycle_terminal()` and its fresh-transaction guard remain unchanged and fail closed for genuinely dirty direct calls.
6. The primary exception / `STOP_PREFLIGHT` semantics are not weakened or replaced by cleanup failure.

No migration, schema change, new owner, Source Governor change, Central Scheduler change, retry, selection-policy change, capacity widening, or capability unlock was introduced.

## Closeout verification

A temporary offline GitHub Actions verifier ran only directly affected tests and static checks. The first verifier attempt failed during collection solely because `PYTHONPATH=src` was omitted; no test executed. The verifier environment was corrected without production changes.

Corrected result:

- `tests/test_v2_9_8b_four_token_slot_order_rollback_repair.py`
- `tests/test_v2_9_8b_four_token_consumed_proof_blocker_tdd.py`
- `tests/test_v2_9_8b_pre_admission_later_cycle_callback.py`
- Result: **17 passed in 15.80s**
- `python -m py_compile src/printer_v1/operator_cli/one_command_15m_factory.py`: PASS
- `git diff --check 3c8ab8612814d63ab9dcfde4220568302e0a5933...HEAD`: PASS

After verification, the temporary workflow was removed. Comparing `20363a489b93bba696f279543a1e1bff72b500d0` to `699778425ee7683ac395c7b3d18cd3eaf83f58ab` shows zero net changed files.

## Money-usefulness contribution

The repair prevents scarce one-shot four-token proof authority from being consumed by deterministic internal slot-order corruption and preserves exact token/pair attribution from campaign ownership into window creation. It also preserves the real first failure instead of masking it with transaction-cleanup noise.

## What improves

- Cycle-1 slot identity now follows authoritative campaign ownership.
- Exact identity guards remain meaningful and fail closed.
- Failed pre-commit work no longer contaminates terminal reconciliation.
- Diagnosis retains the primary failure cause.

## What remains locked

Four-token concurrent operation is still not operationally proven by this offline repair closeout. Six-token proof, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper audits, PnL, wallets, signing, live execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors remain locked.

## Proof/test still needed

Before any new four-token proof, a separate independent rereadiness review must PASS. Only afterward may a separate lane prepare a brand-new authorization, which must itself be independently reviewed before one bounded proof can be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

- Offline regression evidence proves the repaired contracts, not future external-source availability or end-to-end proof success.
- No claim is made that the consumed attempt would otherwise have completed successfully.
- A future proof can expose unrelated blockers; such a result must be classified rather than bypassed or retried automatically.
- The consumed authorization must never be reused, resumed, or treated as successful.

## Next permitted lane

`V2-9.8B Four-Token Slot-Order / Rollback Independent Post-Repair Rereadiness Review` only.
