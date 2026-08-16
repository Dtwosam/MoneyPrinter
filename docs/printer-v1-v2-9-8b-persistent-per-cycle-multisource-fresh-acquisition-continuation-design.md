# Printer V1 V2-9.8B Persistent Per-Cycle Multi-Source Fresh Acquisition Continuation Design

Date: 2026-08-16

Lane: design/specification only.

Predecessor audit: `V2_9_8B_GRADUATED_CANDIDATE_REGISTRY_REPLENISHMENT_READONLY_AUDIT_PASS_REPLENISHMENT_REACHABLE_BUT_STRUCTURALLY_INSUFFICIENT_FOR_PERSISTENT_PER_CYCLE_SUPPLY`.

## Verdict

`V2_9_8B_PERSISTENT_PER_CYCLE_MULTISOURCE_FRESH_ACQUISITION_CONTINUATION_DESIGN_READY`

The repair must extend the existing eligible-supply / Source Governor / Central Scheduler composition. It must not create a second discovery engine, relax candidate evidence, or make the Pump graduated registry the exclusive candidate universe.

## 1. Target behavior

While permanent eligible depth is below four, the same authorized campaign/cycle may repeatedly reopen bounded fresh acquisition. Each delayed opportunity is Central-Scheduler-owned, all provider work is Source-Governed, and cumulative source/duration budgets never reset.

A candidate-local failure removes or suppresses that candidate only. It does not end peer acquisition while another lawful fresh opportunity remains.

The loop stops only on:

- eligible depth >= 4;
- cumulative discovery/source-operation budget exhaustion;
- acquisition deadline with no further canonical refresh interval available;
- operator cancellation or supervision failure;
- attributable terminal source/channel failure that prevents lawful continuation; or
- a durable exhaustion certificate proving no further bounded fresh opportunity remains.

## 2. Fresh-source round

Every delayed refresh reuses the already-approved source owners, categorically and without scoring/ranking/confidence/weights:

1. direct Pump finalized live-tail + exact Pump/PumpSwap verification;
2. DexScreener fresh-profile nomination;
3. GeckoTerminal fresh-pool nomination;
4. existing bounded unknown-liquidity backup where required;
5. existing PumpSwap protocol-confirmation/promotion owner.

No candidate needs Pump lineage merely because it was nominated by DexScreener or GeckoTerminal. Pump/PumpSwap proof remains mandatory only for Pump-specific claims.

Request keys include the refresh ordinal. Exact mint/pool identities already observed in the same cycle are deduplicated; terminal candidate-local failures are not relabelled as new merely because another source repeats them.

## 3. Durable per-refresh ownership

Do **not** rebuild `printer_discovery_work`.

That table is a legacy logical-work graph with `UNIQUE(discovery_batch_id, work_type)` and is referenced by provider-observation and source-link FKs. Rebuilding it solely to permit repeated temporal refresh instances creates disproportionate migration risk.

Instead add one additive table, `printer_pre_lifecycle_discovery_refresh_work`, with one row per claimed refresh wait:

- `refresh_work_id` primary key;
- `wait_id` unique FK to `printer_pre_lifecycle_discovery_refresh_waits`;
- campaign/run/cycle/supervision identity;
- exact Scheduler job ID;
- refresh ordinal;
- `RUNNING|SUCCEEDED|FAILED|CANCELLED` state;
- work deadline, timestamps, immutable first terminal cause.

The sequence remains:

`enqueue -> durable WAITING owner -> due -> exact Scheduler claim -> refresh-work RUNNING -> governed multi-source work -> terminalize refresh-work + Scheduler job + wait`.

`printer_discovery_work` remains untouched for the existing discovery-persistence graph. Campaign active-work/cleanup must recognize both the wait owner and the new refresh-work owner.

## 4. Repeatability and horizon

The current 900-second horizon with the canonical 600-second `DISCOVERY_REFRESH` interval intentionally admits only one delayed refresh and must be replaced for this lane.

Use a bounded 2,400-second acquisition horizon. With the unchanged canonical 600-second cadence and the existing strict `due < deadline` law, this permits at most three delayed refresh opportunities after the campaign-start fresh intake. There is no independent polling interval and no unbounded loop.

This gives four bounded acquisition opportunities in total (campaign-start intake + at most three delayed refreshes), aligned with the permanent four-deep reserve target. Source-operation exhaustion may stop earlier.

No retry/restart/successor semantics are introduced.

## 5. Budget law

The existing cumulative `discovery_operation_budget` remains the outer authority. Every refresh receives only `source_operations_remaining` and reports exact operations consumed.

A sub-stage may run only when its bounded worst-case/source-owner contract fits the remaining budget. A stage may be skipped for budget insufficiency, but the budget is never reset after waiting.

Provider failure and candidate-local evidence failure remain distinct.

## 6. Source fairness

No source score, weight, confidence, quota, or liquidity-ranked preference is permitted.

Use one fixed categorical source order for the first refresh and rotate that order by refresh ordinal only to prevent deterministic last-source starvation under a nearly exhausted budget. Rotation is ordinal-only; candidate values never influence source order.

## 7. Persistence / dedup

Existing durable stores remain authoritative for candidate evidence:

- Pump/PumpSwap graduated registry for proven Pump migration lineage;
- fresh-pool nomination and exact-market state tables for aggregator candidates;
- eligible reserve for current eligible survivors;
- source request/response/failure tables for Source-Governor facts;
- refresh wait/work rows for delayed-round ownership.

Dedup is exact identity based, never score based. Repeated source observations may refresh evidence but may not create duplicate eligible capacity.

## 8. Exhaustion certificate

The existing acquisition ledger is extended to record, per refresh:

- refresh ordinal;
- channels attempted;
- channels skipped and categorical reason;
- source operations consumed;
- provider failures;
- newly observed exact identities;
- promoted eligible identities;
- reserve depth before/after.

Terminal `ALL_REACHABLE_CANDIDATES_EVALUATED` / `NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE` is valid only after the owner has no lawful delayed refresh window or no source budget left. Instantaneous current-universe exhaustion while a refresh remains is nonterminal.

## 9. Money-usefulness contribution

This repair makes Printer replace stale/dead candidates with fresh Solana memecoin candidates instead of weakening evidence gates or repeatedly depending on a decaying historical registry. It improves the probability that each cycle reaches a tradeable, evidence-clean four-deep observation reserve.

## 10. What improves / what remains locked

Improves:

- persistent candidate replenishment inside one authorized cycle;
- fresh-source breadth after initial shortage;
- durable per-refresh Scheduler ownership;
- candidate-local failure isolation;
- honest shortage/exhaustion evidence.

Still locked:

- another live four-token proof;
- authoritative DB mutation in this implementation lane;
- memory generation beyond already-approved existing behavior;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper audits, PnL;
- live wallet/private keys/real funds/live execution;
- paid APIs;
- scoring/ranking/confidence/weights;
- embeddings/vectors;
- `WINDOW_4H/12H/24H` activation changes.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## 11. Minimum implementation proof

Use RED/GREEN focused tests only:

1. schema permits multiple refresh-work rows in one cycle, each bound to a distinct wait/Scheduler job;
2. a completed first refresh does not block refresh ordinal 2;
3. capacity short + lawful window causes another Scheduler-owned refresh;
4. refresh composition exposes Pump, DexScreener and GeckoTerminal fresh channels under existing Source-Governed owners;
5. candidate-local failure does not mark the source terminal or stop peer acquisition;
6. source-operation budget and acquisition deadline never reset;
7. exact mint/pool duplicates do not increase eligible depth;
8. capacity four stops immediately;
9. exhaustion is terminal only when no lawful bounded refresh remains;
10. campaign cleanup sees refresh-work residue;
11. bounded fixture-only disposable proof demonstrates at least two refresh ordinals and zero live/provider calls.

Broad/full regression is reserved for lane closeout because this change touches Scheduler ownership and persistence.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
| --- | --- |
| Infinite candidate polling | 2,400s horizon + unchanged Scheduler cadence + cumulative operation budget |
| Discovery-work FK breakage | additive refresh-work table; no legacy table rebuild |
| Source starvation | ordinal-only categorical source rotation |
| Budget overrun by a sub-stage | require sufficient remaining budget before invoking bounded stage; fail closed on mismatch |
| Duplicate capacity from repeated observations | exact mint/pool/campaign dedup |
| Candidate failure kills channel | candidate-local and provider-terminal classifications remain separate |
| Evidence-gate weakening to improve yield | prohibited; replenish instead |
| Runtime drift into financial features | all financial/retrieval capabilities remain locked |

## 13. Implementation boundary

Implementation may now add the additive ownership migration, repeated temporal owner semantics, reusable multi-source refresh composition, active-work cleanup support, and focused tests/fixture proof only.

Do not run live discovery, create a new authorization, mutate the authoritative DB, or rerun the four-token proof in this lane.
