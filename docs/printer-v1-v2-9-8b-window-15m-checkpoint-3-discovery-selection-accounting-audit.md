# Printer V1 — WINDOW_15M Checkpoint 3 Audit

Issue: `DTW-29`

Baseline: `dceb63274d4633486c5cfecafbbd9470a09f8bee`

Branch: `agent/v2-9-8b-window-15m-checkpoint-3-discovery-selection-accounting`

## Boundary

Audit-only inspection covered the ordinary `WINDOW_15M` path through discovery entry and ownership, candidate observation/validation, deterministic selection, atomic two-slot handoff, Source Governor scope, Central Scheduler claims, source request/response/failure accounting, action-local/campaign-local accounting, ceilings, retries, cooldowns, exhaustion, and terminal propagation.

No Printer command, provider/RPC call, authorization use or creation, authoritative-database mutation, memory generation, retrieval, decision, BUY/SELL/HOLD, position, trade, audit, or PnL work was performed.

## Confirmed existing readiness

- Ordinary runtime composition enters the authoritative operational owner and retains Source Governor and Central Scheduler ownership.
- Every discovery work unit follows enqueue -> exact claim -> claimed-identity verification -> RUNNING work insertion before governed work.
- Discovery work terminal state is propagated through the Scheduler owner.
- Initial two-slot handoff remains savepoint-atomic and rolls back both slots when either handoff fails.
- Selection remains deterministic, categorical, non-scored, and capped at two handoffs.
- Graduation-native candidates carry source-local migration evidence and exact PumpSwap pool authority without fabricating a Pump create-origin row. A second registry confirmation is not required at this activation boundary.
- Automatic retries remain zero; source, Scheduler, handoff, storage, observation, unique-mint, failure, and duration ceilings remain bounded.
- Existing terminal reconciliation preserves the first terminal cause and no automatic successor/restart is created.

## Proven blockers

RED commit: `e4d7fac36c14a3a42669f5fc097d38fbf1b4dc11`

Disposable focused proof: `3 failed` for the intended reasons.

1. `PAIR_TOKEN_IDENTITY_MISMATCH`
   - `_handoff_one_slot` reuses an existing `printer_pairs.pair_address` row without proving its `token_id` and `base_token_mint` belong to the selected candidate.
   - The mismatch is encountered later as an integrity fault and is translated to the generic `HANDOFF_DURING_SECOND`, hiding the exact identity blocker.

2. `SOURCE_FAILURE_BEFORE_REQUEST`
   - The injected direct-provider failure branch writes `printer_source_failures` before creating the governed `printer_source_requests` row.
   - This weakens request/failure causality and makes a fault possible before its durable governed request identity exists.

3. `CAMPAIGN_SOURCE_SCOPE_PREFIX_COLLISION`
   - `request_key_belongs_to_root()` treats any string beginning with the root as owned by the campaign.
   - A sibling such as `<root>shadow` is therefore accepted even though it is not the root and is not a delimiter-derived child key.

## Money-usefulness contribution

The checkpoint protects future learning quality by ensuring selected pair identity cannot silently bind to another token, every source failure remains tied to a prior governed request, and campaign accounting cannot absorb unrelated request rows through a prefix collision.

## What this checkpoint improves

- exact selected mint/pair ownership;
- source request/failure causality;
- invocation-local request-scope isolation;
- clearer terminal blocker reporting;
- trustworthy campaign/action-local accounting inputs.

## What this checkpoint still does not unlock

Memory generation, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, PnL, live execution, wallet/private-key/signing logic, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, vectors, `WINDOW_1H`, or Checkpoint 4.

## Functionality Risks / Setbacks / Efficiency Blockers

- Repairing pair identity too late would still permit partial handoff mutation; it must fail before queue/job/slot creation for that candidate.
- Reordering request/failure persistence must not add a retry, source call, response, or separate accounting owner.
- Request-scope separation must retain the canonical root itself and hyphen-delimited child keys while rejecting adjacent-prefix siblings.
- Broad refactoring would risk Scheduler, handoff, and campaign-accounting drift; only three narrow repairs are justified.

## Audit verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_3_AUDIT_CONFIRMED_THREE_BLOCKERS`

Proceed to narrow design and test-first repair only. Do not begin Checkpoint 4.