# Printer V1 V2-9.8B Post-Rollover-2 token_slot_id Blocker Repair Implementation

Date: 2026-08-03

Linear: `DTW-20`

Design baseline: `dc7e7a855108fce2c60d8b84b347dd7f6c7de022`

Status: **PASS**

Verdict: `V2_9_8B_POST_ROLLOVER_2_WINDOW_15M_TOKEN_SLOT_ID_BLOCKER_REPAIR_IMPLEMENTATION_PASS`

## Scope

Implemented the approved identity-preserving repair only: `_read_activated_slots()` now projects the already-persisted `s.token_slot_id` and carries it unchanged through the existing row/dict/callback path. The strict public consumer and `SELECTION_HANDOFF_VALIDATED` semantics were not changed.

Changed production file: `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`.

Added focused proof: `tests/test_v2_9_8b_token_slot_id_projection_repair.py`.

No schema, migration, ID synthesis, fallback, optional lookup, consumer weakening, Scheduler owner, Source Governor, wrapper, authorization, runtime, retrieval, decision, financial, or longer-window change was made.

## File identities

- source SHA-256: `e7bf9de5a451f6dfaf984d0d869912d955aee3c1cf466ce7f61012420f729ae1`
- focused-test SHA-256: `ae0e454822b64deafa22baa7ed817e26ce50d0e037d45d08ba6b455778a55ce7`

## Exact source change

```diff
diff --git a/src/printer_v1/operator_cli/origin_lifecycle_campaign.py b/src/printer_v1/operator_cli/origin_lifecycle_campaign.py
index 13fbf26..f240eec 100644
--- a/src/printer_v1/operator_cli/origin_lifecycle_campaign.py
+++ b/src/printer_v1/operator_cli/origin_lifecycle_campaign.py
@@ -252,8 +252,9 @@ def _read_activated_slots(
     """
     rows = connection.execute(
         """
-        SELECT s.slot_ordinal, s.token_row_id, s.pair_row_id, s.mint_identity,
-               s.pair_identity, s.token_state, p.pair_address, t.token_status
+        SELECT s.token_slot_id, s.slot_ordinal, s.token_row_id, s.pair_row_id,
+               s.mint_identity, s.pair_identity, s.token_state,
+               p.pair_address, t.token_status
         FROM printer_memory_factory_campaign_token_slots AS s
         JOIN printer_pairs AS p ON p.id = s.pair_row_id
         JOIN printer_tokens AS t ON t.id = s.token_row_id
```

## Verification status

- compile exit: `0`
- focused proof exit: `0`
- affected regression exit: `0`
- diff-check exit: `0`
- migration-head check exit: `0`

### Migration identity

```text
migration_count=50
migration_head=050_campaign_scheduler_ownership_scope.sql
```

### Compile

```text

```

### Focused proof

```text
.....                                                                    [100%]
5 passed in 8.62s
```

### Directly affected regression set

```text
.................................................................. [ 53%]
.......................................................ss.               [100%]
122 passed, 2 skipped, 6 subtests passed in 79.55s (0:01:19)
```

### Diff check

```text

```

## Safety and evidence boundary

All proof work ran on disposable test databases with frozen or injected evidence. Provider/RPC/WebSocket contact: 0. Authoritative DB access or mutation: 0. Wrapper invocations: 0. Authorization creation/application: 0. Automatic retries, reruns, resumes, restarts, successors: 0. Retrieval, paper decision, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_1H`/`WINDOW_4H`/`WINDOW_12H`/`WINDOW_24H` remained locked.

## Money-usefulness contribution

The repair prevents another bounded authorization and source budget from being consumed by the known deterministic handoff-shape failure and preserves exact campaign-slot attribution. It does not create memory, trading authority or profit.

## What this lane improves

It restores producer-to-consumer shape completeness for exact durable token-slot identity and adds real-composition regression coverage at the driver callback and public accounting boundary.

## What this lane still does not unlock

No authoritative memory run, fresh readiness, authorization, retrieval, decisions, BUY/SELL/HOLD, paper positions, trade events, audits, PnL, wallet, keys, real funds, live execution, paid API, score/rank/confidence/weighted logic, embeddings, vectors or longer window is unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- A one-column repair still depends on the focused real-composition tests staying in the regression set.
- The prior authorization remains consumed and cannot be reused.
- A fresh readiness audit and independent implementation closeout remain required before any future authorization.

## Exact next lane

`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Independent Closeout`

This PASS does not authorize runtime or a fresh authorization.
