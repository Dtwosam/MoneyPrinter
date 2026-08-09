# Printer V1 — V2-9.8B Post-DTW98 Temporal Persistence Implementation Review

## Verdict

`V2_9_8B_POST_DTW98_TEMPORAL_PERSISTENCE_IMPLEMENTATION_REVIEW_BLOCKED_LIVE_WIRING_INCOMPLETE`

The implementation commit `078e2e83db4d9fcbb6cd32f1774eeb6bfea67279` is one exact commit over the frozen design baseline `d459057752da229cdd33838cdad7c8adcf3fae6e`. Its schema, temporal-acquisition contract, Scheduler-owned wait owner, eligible-supply integration boundary, active-work integration, and focused offline tests are retained as valid partial implementation work.

The implementation is not ratified as complete because ordinary Printer runtime does not construct or inject the temporal refresh owner or a live Source-Governed refresh stage/discovery-batch resolver. Therefore the production path still defaults `pre_lifecycle_temporal_refresh_owner=None`, and current-universe exhaustion retains the old immediate-terminal behavior.

## Controlling evidence

- `AuthoritativeLiveOperationalCampaignOwner.run_operational(...)` adds `pre_lifecycle_temporal_refresh_owner: Any | None = None`.
- Deadline binding and `temporal_refresh_owner` supply wiring occur only when that value is non-null.
- The implementation commit contains no production construction of `PreLifecycleTemporalRefreshOwner`; the constructions are test-side.
- The implementation report itself lists as still required: “a live Source-Governed refresh stage and discovery-batch resolver for the operational wiring”.

This is a missing production integration boundary, not evidence that the temporal owner itself should be discarded.

## What remains accepted

- migration 054 is additive and forward-only;
- four-deep 2+2 freeze remains unchanged;
- tracking exclusions, exact-pair law and liquidity floor remain unchanged;
- `WAITING_FOR_ELIGIBLE_SUPPLY` is nonterminal when the temporal owner is actually supplied;
- Scheduler cadence remains canonical `DISCOVERY_REFRESH` / 600 seconds;
- pending wait ownership is exact campaign/run/cycle ownership before claim;
- claim-at-work-start remains `enqueue -> due -> exact claim -> discovery work RUNNING -> governed work -> terminalization`;
- cumulative discovery budget does not reset;
- retained candidates must revalidate before counting;
- safe-stop/active-work integration remains fail-closed;
- no retry/restart/resume/successor/second authorization behavior was added.

## Required implementation-completion repair

Complete the already-frozen design by wiring the temporal owner into the actual ordinary WINDOW_15M operational composition.

The repair must:

1. construct exactly one `PreLifecycleTemporalRefreshOwner` for the same authorized campaign/run/cycle/supervision;
2. bind the existing heartbeat/cancellation state to its supervision probe and abort boundary;
3. use the canonical Source Governor and Central Scheduler already owned by the operational command;
4. build one bounded live refresh-stage composition only from already-approved free-public discovery owners/adapters and current source-governance contracts;
5. build/resolve the refresh discovery batch without colliding with an existing `(cycle_id)` or `(discovery_batch_id, work_type)` owner;
6. pass the constructed owner into `run_operational` on the ordinary `run` path;
7. preserve all existing source-operation ceilings and exact request accounting;
8. prove that a normal ordinary-run composition with a 3/4 exhausted instantaneous universe reaches `WAITING_FOR_ELIGIBLE_SUPPLY` rather than immediate terminalization, without using live providers in the implementation test;
9. prove that the due refresh can expose a fourth candidate through the real production composition boundary and that post-wait reserve revalidation/freeze still obeys the frozen design;
10. leave migration 054 unapplied to the authoritative database in this completion lane.

Do not weaken the pre-authorization migration guard. Do not apply migration 054, create an authorization, or run WINDOW_15M in this lane.

## Migration sequencing

Migration 054 is required by the completed production wiring but must not be applied yet. First complete and prove the production integration on disposable SQLite. After implementation completion and bounded disposable proof/closeout pass, perform a separate authoritative migration-054 readiness/application/proof/closeout lane. Only after authoritative schema count/head match the canonical 54-migration catalogue may post-repair rereadiness and a new authorization be considered.

## Money-usefulness contribution

This review prevents a false “fixed” state where the tested temporal machinery exists but the actual Printer command would still stop at 3/4. Completing the production integration is necessary before another one-use authorization can benefit from the new bounded persistence behavior.

## What this review improves

- preserves the valid implementation work;
- identifies the exact missing live composition boundary before migration/runtime;
- avoids spending another authorization on unchanged ordinary behavior;
- keeps migration and proof sequencing fail-closed.

## What this review still does not unlock

No authoritative migration, source run, discovery runtime, memory generation, WINDOW_15M execution, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, funds, paid APIs, scoring/ranking/confidence/weighted systems, embeddings or vectors are unlocked.

## Proof needed before completion

Minimum sufficient proof is a focused disposable integration test that invokes the actual ordinary operational composition boundary (not direct construction only), proves the temporal owner is non-null and exact-scope bound, proves one delayed Scheduler refresh path through injected source transports, and proves zero forbidden capability deltas and zero active residue. Then run the directly affected temporal/supply/Scheduler/active-work/ordinary-command tests only.

## Functionality Risks / Setbacks / Efficiency Blockers

- live refresh composition must not create a second discovery engine;
- refresh batch/work identity must not collide with the existing unique cycle/batch constraints;
- source accounting must remain cumulative and request-identical across the wait;
- a future-dated pending job must remain visible to exact cleanup ownership;
- migration 054 will block authorization until separately applied to the authoritative DB;
- no migration application should occur before the completed production wiring is proven on disposable SQLite.

## Next lane

`V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Implementation Completion`

This is implementation-only. Stop before bounded proof, authoritative migration application, rereadiness, authorization, or WINDOW_15M runtime.