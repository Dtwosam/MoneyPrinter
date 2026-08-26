# Printer V1 — V2-9.8B Cycle-1 Historical-Disjointness Repair Closeout

Status: **CLOSED — PASS**

Closeout verdict:

`V2_9_8B_CYCLE1_HISTORICAL_DISJOINTNESS_REPAIR_CLOSEOUT_PASS`

## Scope

This closeout closes the V2-9.8B Cycle-1 historical-disjointness regression repair.

Primary classification resolved:

`COMMITTED_CODE_DEFECT`

The repaired defect caused real Cycle 1 to be misclassified as a later cycle because the production gate used the number of already-persisted campaign-cycle rows as a proxy for prior-cycle existence.

## Proven root cause

Real production ordering persists Cycle 1 before pre-lifecycle freeze selection.

The previous gate used:

`COUNT(*) >= 1`

over campaign-cycle rows.

Because the current Cycle-1 row already existed, Cycle 1 produced a count of 1 and incorrectly enabled campaign historical-disjointness enforcement.

The later-cycle history requirement then correctly failed closed because Cycle 1 has no prior admitted campaign history.

The history loader and campaign persistence ordering were not defective.

## Implemented repair

Implementation commit:

`433e7da1f6ffeb2252716a43a76ea511a823cdfe`

Final documentation-conformance HEAD:

`58f30f92933a8ea9eeb009a36afb3d41a3b12170`

Baseline before repair:

`abe4f5ac7f173fd42c312f068b64d7e84ef68bfa`

The production gate now resolves the exact current campaign cycle by:

- `campaign_id`
- `run_id`
- `cycle_id`

and reads its persisted `cycle_ordinal`.

Enforcement semantics are now:

- `cycle_ordinal == 1` -> historical-disjointness enforcement `False`
- `cycle_ordinal > 1` -> historical-disjointness enforcement `True`
- invalid or unavailable current-cycle identity -> fail closed with `CURRENT_CYCLE_IDENTITY_INVALID`

The obsolete persisted-row-count proxy no longer controls the decision.

## Later-cycle safety preserved

For genuine Cycle 2+:

- campaign historical-disjointness enforcement remains mandatory;
- prior admitted campaign identity sets must load;
- missing or structurally empty required history continues to fail closed with `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`;
- earlier-cycle identities are filtered before seeded freeze selection;
- final admission disjointness remains a defense.

The repair does not use history presence to decide whether safety applies.

## Bounded proof

Proof verdict:

`V2_9_8B_CYCLE1_HISTORICAL_DISJOINTNESS_REPAIR_BOUNDED_PROOF_PASS`

Proof HEAD:

`58f30f92933a8ea9eeb009a36afb3d41a3b12170`

Authoritative DB SHA before and after:

`fa2fd9b5469cade5479fd8c5ef1e854d681d1a90b95dc2bc64b66c17019f7ab8`

Proof results:

- `PERSISTED_CYCLE1_BEFORE_FREEZE_ENFORCEMENT_FALSE_PASS`
- `PERSISTED_CYCLE2_WITH_HISTORY_ENFORCEMENT_TRUE_PASS`
- `CYCLE2_REUSED_IDENTITY_FILTERED_BEFORE_SELECTION_PASS`
- `CYCLE2_MISSING_HISTORY_FAIL_CLOSED_PASS`
- `INVALID_CURRENT_CYCLE_IDENTITY_FAIL_CLOSED_PASS`
- actual production owner run exercised
- actual freeze boundary instrumented
- production caller Cycle 1 enforcement `False` observed
- production caller Cycle 2 enforcement `True` observed
- helper-only proof = false
- targeted repair suite: 5 passed
- authoritative DB integrity check: ok
- foreign key check: zero rows
- authoritative DB writes during proof: 0
- provider/RPC/WebSocket/live Scheduler/Printer runtime during proof: 0

## Historical failed campaign preserved

Failed campaign evidence remains preserved:

- campaign: `20260826T190349Z-fd22410474f7-campaign`
- run: `20260826T190349Z-fd22410474f7-campaign-run`
- cycle: `20260826T190349Z-fd22410474f7-cycle`

Its first terminal cause was:

`INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`

That historical failure is not rewritten or deleted.

## Authorization state

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T185611Z_b861fd4c`

State:

**consumed / terminal / permanently non-reusable**

It must never be retried, rerun, resumed, restarted, or used to create an automatic successor.

This closeout creates no authorization.

## Permanent V1 locks preserved

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence percentages, or weighted decision logic;
- no embeddings/vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval or financial capability before its explicit lane;
- no BUY/SELL/HOLD, paper positions, trade events, paper audits, or PnL before their explicit lanes;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- `WINDOW_12H` and `WINDOW_24H` remain locked.

## Next permitted action

Exactly:

**`POST-REPAIR FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS / GOVERNANCE ONLY`**

This closeout does not itself create a successor authorization.

The next lane must re-bind readiness to the new closeout HEAD and the current authoritative DB state before any fresh one-shot authorization may be considered.

No Printer command is authorized by this closeout.
