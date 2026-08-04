# V2-9.8B Remaining Graduated-Discovery Runtime Blocker Repair Design

Date: 2026-08-04

Lane: `V2-9.8B — Remaining Graduated-Discovery Runtime Blocker Repair`

Status: `V2_9_8B_REMAINING_RUNTIME_BLOCKER_REPAIR_DESIGN_COMPLETE`

Baseline HEAD: `03e65fd25717340ab4b36481b7d1f1a9332eda57`  
Subject: `Repair graduated discovery audit blockers`  
Branch: `grok/v2-9-8b-remaining-runtime-blocker-repair`

Four production-path runtime defects only. No providers, discovery runtime, Scheduler runtime, authorization, `WINDOW_15M`, memory, retrieval, decisions, positions, trades, audits, or PnL.

## Finding map

### Repair 1 — Separate MEMORY_OBSERVATION readiness from action holder eligibility

| Item | Detail |
|---|---|
| **Current owner** | `pilot_input_readiness.evaluate_readiness_gates` / `build_pilot_input_ready_bundle`; campaign call site in `authoritative_live_operational_campaign.run_operational` |
| **Violated invariant** | Memory freeze admits holder-extreme observation candidates, but readiness always requires `holder_eligible`, so concentrated tokens never form the final memory-lifecycle readiness bundle |
| **Minimum repair** | Explicit `readiness_purpose` ∈ `{MEMORY_OBSERVATION, FUTURE_ACTION}` (default `FUTURE_ACTION` preserves legacy). `MEMORY_OBSERVATION` requires exact mint/pool, liquidity ≥ $3k, lawful route, `memory_observation_eligible=True`; does **not** require holder eligibility. Persist purpose + truthful holder/memory context in durable bundle JSON (`source_ledger_json` / payload / holder_evidence). Never invent `holder_eligible=True`. |
| **End-to-end test** | Campaign permanent path: 4 observation candidates with holder-extreme (`holder_eligible=False`) → freeze 2+2 → MEMORY_OBSERVATION readiness succeeds → future action remains blocked. Legacy FUTURE_ACTION still BLOCKED_HOLDER. |
| **Schema** | No migration if purpose/context fit existing JSON columns (preferred). |
| **Locked** | Future action safety; paper unlock; bundle immutability/hash determinism |

### Repair 2 — Wire campaign-wide request reconciliation into campaign owner

| Item | Detail |
|---|---|
| **Current owner** | Helpers exist in `permanent_discovery_availability`; campaign still uses `ledger.governed_requests` as authoritative `campaign_source_calls` and never assembles/enforces reconcile before handoff |
| **Violated invariant** | `set(durable campaign request IDs) == set(manifest request IDs)` before readiness/lifecycle |
| **Minimum repair** | Campaign assembles coverage from every stage that ran (intake, Dex/Gecko fresh, backup, market, recon, early/residual protocol, holder, final refresh). Query durable IDs via Source Governor request rows linked by campaign request_key / stage reports (not a bare counter). Call `reconcile_campaign_source_requests`. Fail closed with `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` before readiness/handoff. Expose full reconciliation surface on durable pre-lifecycle/terminal report. `ledger.governed_requests` becomes diagnostic comparison only. |
| **End-to-end test** | Multi-stage fixture campaign reconciles; missing Gecko/backup entry blocks; duplicate protocol ID blocks; blocker prevents readiness and still writes durable blocked report. |
| **Schema** | No (JSON diagnostics/report). |
| **Locked** | Source Governor ownership |

### Repair 3 — Post-filter freeze depth is sole admission authority

| Item | Detail |
|---|---|
| **Current owner** | Campaign calls `observation_reserve_depth_status(len(observation_rows))` before/alongside freeze |
| **Violated invariant** | Raw row count can claim depth ≥4 while freeze keeps only 3 valid fresh unique rows |
| **Minimum repair** | Expand freeze `selection_authority` with input/valid/stale/duplicate-mint/duplicate-pool/malformed counts + depth/surplus/coverage. Campaign derives admission only from freeze post-filter valid depth. Remove raw-count authority. |
| **End-to-end test** | Campaign path: 4 raw − 1 stale → blocker, no readiness; 6 raw − 2 duplicate identities → 2+2, SURPLUS_TARGET_NOT_MET. |
| **Schema** | No. |
| **Locked** | MINIMUM_FREEZE_DEPTH=4; no scoring |

### Repair 4 — Measure fresh nomination and backup transports

| Item | Detail |
|---|---|
| **Current owner** | `run_geckoterminal_fresh_nomination` swallows measurement exceptions; `run_bounded_unknown_liquidity_backup` leaves transport_identity_count=0 without measuring |
| **Violated invariant** | Measured transport identities must be recorded or produce typed accounting blockers; never fabricate counts; request count separate |
| **Minimum repair** | Gecko: catch `MeasuredTransportError` → accounting blocker, preserve request ID, no successful stage claim. Backup: MeasuredTransportLedger per request; coverage uses measured counts; measurement failure → blocker; feed coverage into campaign reconciliation. |
| **End-to-end test** | Successful Dex↔Gecko backup measured counts; measurement failure preserves request ID, blocks promotion/handoff; Gecko failure not swallowed; request ≠ transport counts. |
| **Schema** | No. |
| **Locked** | Six-unit measured transport contract |

## Integration proof

One offline production-composition fixture walk through campaign stop-before-lifecycle, plus a 3-valid-candidate coverage-blocker fixture.

## Schema conclusion

Prefer existing JSON. **Migration 053 not required** unless static inspection during implementation proves otherwise.

`V2_9_8B_REMAINING_RUNTIME_BLOCKER_REPAIR_DESIGN_COMPLETE`
