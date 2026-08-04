# V2-9.8B Graduated Discovery Code-Audit Blocker Repair Design

Date: 2026-08-04

Lane: `V2-9.8B — Graduated Discovery Code-Audit Blocker Repair`

Status: `V2_9_8B_GRADUATED_DISCOVERY_CODE_AUDIT_BLOCKER_REPAIR_DESIGN_COMPLETE`

Baseline HEAD: `a8197f09ee25aa0f926f6bc1a365ef92f8cfb433`  
Subject: `Implement graduated discovery and memory eligibility`  
Branch: `grok/v2-9-8b-code-audit-blocker-repair`

This design authorizes only the minimum offline repairs required to close proven graduated-discovery audit blockers. It does **not** authorize providers, discovery runtime, Central Scheduler runtime, authorization creation/consumption, `WINDOW_15M`, memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

Depends on:

- `docs/printer-v1-v2-9-8b-graduated-discovery-liquidity-memory-eligibility-audit.md`
- `docs/printer-v1-v2-9-8b-graduated-discovery-liquidity-memory-eligibility-design.md`
- `docs/printer-v1-v2-9-8b-graduated-discovery-liquidity-memory-eligibility-implementation-closeout.md`

## 1. Objective

Repair eleven code-audit blockers so that:

1. freeze depth is an admission gate, not only a diagnostic;
2. protocol stage-sealing errors fail closed with durable terminal evidence;
3. early and residual protocol reports merge deterministically without overwriting sequence 1;
4. all market-revalidation candidates survive the merge;
5. campaign-wide durable source-request IDs reconcile exactly to a campaign manifest;
6. holder concentration never blocks memory observation admission or handoff;
7. evidence freshness is observation-based, not ingestion-based;
8. direct promotion preserves exact retained quote mint and pool identity;
9. fresh unknown liquidity receives exactly one lawful opposite-source backup;
10. transport counts are never fabricated after measured-identity failure;
11. authoritative diagnostics preserve categorical funnel counts without scoring.

## 2. Non-goals and hard locks

Remain locked:

- flat 30-operation ceiling and stage reservations `3/2/6/7/8/4`;
- `$3,000` liquidity floor;
- Source Governor and Central Scheduler ownership;
- exact PumpSwap owner + base-mint confirmation;
- no scoring, ranking, confidence, weights, retries, resumes, successors, paid APIs;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL;
- no authorization or live campaign execution in this lane.

Prefer existing tables and JSON evidence/report fields. Add migration 053 only if static inspection proves durable required data cannot be represented safely in the current schema.

**Static schema conclusion:** all required repair surfaces fit existing tables and JSON evidence/report fields (`printer_source_requests`, reserve `evidence_json` / `source_provenance_json`, campaign terminal report JSON, diagnostics dicts). **Migration 053 is not required.**

## 3. Finding map

### Finding 1 — Enforce minimum freeze depth

| Item | Detail |
|---|---|
| **Current code owner** | `freeze_eligible_reserve` and `observation_reserve_depth_status` in `permanent_discovery_availability.py`; pre-lifecycle freeze/handoff in `authoritative_live_operational_campaign.py` |
| **Violated invariant** | `MINIMUM_FREEZE_DEPTH = 4` must gate admission. With 0–3 observation-eligible candidates the campaign must emit a durable insufficient-coverage terminal, with zero selected slots, zero alternates, no readiness bundle, and no lifecycle handoff. |
| **Exact repair** | (a) `freeze_eligible_reserve` admits only `memory_observation_eligible=True` (remove `fully_eligible` fallback). (b) When post-filter depth `< 4`, return empty selected and empty alternates. (c) Campaign, after building observation rows, calls `observation_reserve_depth_status`; on `coverage_blocker`, stop before readiness/handoff and persist durable terminal via the existing campaign terminal-report owner with stable categorical first cause `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` (or existing equivalent already used for coverage). (d) Depth 4–7 → freeze 2+2 + `SURPLUS_TARGET_NOT_MET`. Depth ≥8 → 2+2 + `SURPLUS_TARGET_MET`. |
| **Exact focused test** | 3 candidates → durable blocker, no handoff; 4 → 2 selected + 2 alternates; 8 → surplus met; fully_eligible-only rows rejected. |
| **Schema** | No |
| **Remains locked** | No scoring; no budget increase; no paper action unlock |

### Finding 2 — Fail closed on protocol stage-sealing errors

| Item | Detail |
|---|---|
| **Current code owner** | `process_protocol_confirmation_queue._finalize_report` in `permanent_discovery_availability.py` (`except Exception: sealed = None`) |
| **Violated invariant** | Unexpected identity/count/duplicate/sequence/seal errors must become typed accounting blockers, persist in the terminal report, stop promotion/handoff, and never discard stage evidence silently. |
| **Exact repair** | Catch `CampaignSixUnitError` / `MeasuredTransportError` (and seal-specific typed errors) explicitly. On unexpected seal failure: set report fields `accounting_blocker=True`, `accounting_blocker_reason` to the typed cause (or `PROTOCOL_STAGE_SEAL_FAILURE`), attach partial stage evidence already measured, do **not** call sink with fabricated success, and surface the blocker so the campaign terminal owner records it. Expected zero-work (`sealed = None` when no transport and no validations) remains explicit without a broad `except Exception`. |
| **Exact focused test** | Force seal failure → durable accounting blocker; no successful fabricated sealed stage; promotion/handoff stopped when campaign sees blocker. |
| **Schema** | No |
| **Remains locked** | Six-unit ownership; no silent evidence discard |

### Finding 3 — Merge early and residual protocol reports

| Item | Detail |
|---|---|
| **Current code owner** | Residual merge block in `eligible_token_supply.run_persistent_eligible_token_supply` |
| **Violated invariant** | Protocol sequence 1 and 2 evidence must both survive; sealed blocks are an ordered collection; no overwrite of sequence 1 by sequence 2; duplicate request IDs fail closed. |
| **Exact repair** | Create one deterministic owner `merge_protocol_confirmation_reports(early, residual)` in `permanent_discovery_availability.py` that merges: outcomes; remaining_due (residual authoritative for residual due); promoted_observation_eligible (concat + exact mint/pool dedupe preserving order); requires_market_revalidation (union helper); source_request_ids / response_ids / failure_ids (ordered concat, duplicate IDs → blocker); source_requests / transport_operations / local_validation_steps / batch_count / shared_source_failures (sum); outcome_counts (sum per key); source_request_coverage (concat, then fail closed on duplicate request_id); sealed_stage_evidence_blocks as ordered list of non-null sealed blocks from both sequences; legacy single `sealed_stage_evidence` as compatibility view of the last sealed block only (never authoritative). |
| **Exact focused test** | Early+residual outcomes, IDs, coverage, counts, and both sealed blocks survive; duplicate request IDs fail closed. |
| **Schema** | No |
| **Remains locked** | Stage sequences remain 1 then 2 |

### Finding 4 — Preserve every market-revalidation candidate

| Item | Detail |
|---|---|
| **Current code owner** | Residual `confirmed_for_market = residual or protocol_report` selection in `eligible_token_supply.py` |
| **Violated invariant** | Early candidate A and residual candidate B must both appear exactly once, keyed by `(mint, pool, venue)`. |
| **Exact repair** | Replace truthy `A or B` with `union_market_revalidation_candidates(early, residual)` deterministic dedupe by `(mint, pool, venue)` preserving early-then-residual order. Use the same helper inside the merge owner. |
| **Exact focused test** | Early A + residual B → final queue contains A and B exactly once. |
| **Schema** | No |
| **Remains locked** | No invented liquidity; revalidation only when retained evidence expired/missing |

### Finding 5 — Campaign-wide source-request reconciliation

| Item | Detail |
|---|---|
| **Current code owner** | Protocol-only `build_source_request_coverage_manifest` / diagnostics `protocol_confirmation`; campaign pre-lifecycle reporting still derives `campaign_source_calls` from the holder ledger alone |
| **Violated invariant** | `set(all durable campaign source-request IDs) == set(all campaign manifest request IDs)`; each ID once; each entry owns one logical stage; missing/duplicate/unowned → `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`. |
| **Exact repair** | Add `build_campaign_source_request_manifest` / `reconcile_campaign_source_requests` owners that accept explicit coverage entries from every campaign stage that created durable requests (Pump migration/registry intake, DexScreener discovery, GeckoTerminal discovery, market batches, exact-pool reconciliation/backup, PumpSwap protocol confirmation, holder-context, final refresh when present). Each entry: source_name, request_kind, logical_stage_id, terminal_status, transport_identity_count, normalized_member_count. Reconciliation compares the manifest ID set to the union of durable request IDs recorded for the campaign (from stage reports + DB rows when available). Fail closed on missing, duplicate, or unowned IDs. Final durable campaign report exposes complete manifest + reconciliation result. Request count remains separate from transport count. Holder ledger is never the complete campaign source-call owner. |
| **Exact focused test** | Campaign durable IDs equal manifest IDs; missing entry → reconciliation blocker. |
| **Schema** | No (JSON report / diagnostics) |
| **Remains locked** | Source Governor remains request persistence owner |

### Finding 6 — Remove every downstream holder gate from memory observation

| Item | Detail |
|---|---|
| **Current code owner** | Campaign observation/freeze path and readiness handoff in `authoritative_live_operational_campaign.py`; freeze admission fallback; residual selection fallback on `holder_facts.eligible`; readiness `holder_eligible=True` hardcode; `atomic_ready` requiring holder count ≥ 2 |
| **Violated invariant** | Memory path uses `MEMORY_OBSERVATION_ELIGIBLE` only. Holder-extreme observation candidates must pass supply → reserve → freeze → readiness → selected/alternate handoff without rejection or false holder-safe labels. |
| **Exact repair** | (a) Freeze admits only `memory_observation_eligible`. (b) Campaign observation rows always carry real `holder_condition` / `holder_evidence_status` / `future_action_eligibility=BLOCKED_OR_UNKNOWN`. (c) Never set `holder_eligible=True` merely to satisfy legacy gates. (d) Readiness candidate field may record actual holder eligibility separately, but selection/handoff does not require holder pass. (e) `atomic_ready` for permanent-discovery memory path keys off freeze depth / selected pair, not holder pass count. (f) `FULLY_ELIGIBLE` layer remains only when holder actually passes, for future action policy only. |
| **Exact focused test** | Holder-extreme observation candidates reach readiness/handoff; future action remains blocked/unknown; no paper unlock. |
| **Schema** | No |
| **Remains locked** | Future action policy; paper decisions |

### Finding 7 — Correct evidence freshness

| Item | Detail |
|---|---|
| **Current code owner** | `record_fresh_pool_nominations` default expiry from `now`; `_coerce_liquidity_usd` partial NaN handling |
| **Violated invariant** | Default expiry = `observed_at + approved freshness interval`. Explicit expiry must not exceed observation-based maximum without explicit contract authorization. Malformed/expired/contradictory timestamps fail closed. Infinity/NaN/negative/non-numeric liquidity rejected. |
| **Exact repair** | (a) Default `item_expires = _liquidity_evidence_expiry(observed_at)` not `now`. (b) If explicit expiry present: parse; if missing tz → fail closed; if `explicit > observed_at + interval` → fail closed (identity/evidence exclusion); if `explicit <= observed_at` → fail closed. (c) `_coerce_liquidity_usd` rejects non-finite values (`math.isfinite`). |
| **Exact focused test** | Old observed_at not refreshed by later ingestion; NaN/infinity rejected. |
| **Schema** | No |
| **Remains locked** | `EXACT_POOL_RECONCILIATION_SECONDS = 1800` |

### Finding 8 — Preserve exact quote mint during direct promotion

| Item | Detail |
|---|---|
| **Current code owner** | `promote_confirmed_with_retained_liquidity` hardcodes WSOL |
| **Violated invariant** | Retained base/quote/venue/pool/contract version/liquidity provenance must continue; base mint must equal candidate mint; missing/conflicting orientation fails closed; no pool/quote substitution or token-wide liquidity borrow. |
| **Exact repair** | Load base_mint, quote_mint, venue, pool, contract_version from retained evidence/provenance. Require base_mint == mint. Require non-empty quote_mint. On conflict/missing → fail closed (`requires_market_revalidation`, not promoted). Pass exact quote/venue into `ExactMarketObservation` and reserve evidence. |
| **Exact focused test** | Non-WSOL quote preserved; quote/base/pool conflicts prevent promotion. |
| **Schema** | No |
| **Remains locked** | Exact-pool identity; no silent substitution |

### Finding 9 — One bounded backup for fresh unknown liquidity

| Item | Detail |
|---|---|
| **Current code owner** | Fresh path leaves `LIQUIDITY_UNKNOWN` without opposite-source exact-pool backup before protocol |
| **Violated invariant** | Fresh missing liquidity gets at most one lawful opposite-source exact-pool backup via Source Governor / stage budget. |
| **Exact repair** | Add `run_bounded_unknown_liquidity_backup` owner: for each fresh `LIQUIDITY_UNKNOWN` nomination not yet backup-attempted, issue exactly one governed opposite-source exact-pool lookup (Dex→Gecko token-pools; Gecko→Dex mint-batch), charge existing reconciliation/market stage capacity (no new ceiling), record `liquidity_backup_attempted=True` and backup provenance in evidence, apply prefilter outcomes: ≥$3000 → protocol due; <$3000 → below-floor; exact pool absent → `EXACT_POOL_NO_MATCH`; identity conflict → `IDENTITY_CONFLICT`; still unknown → remain `LIQUIDITY_UNKNOWN` and defer. Second backup attempt prevented by provenance flag. No protocol confirmation before liquidity proven. No direct provider bypass. |
| **Exact focused test** | Dex-missing → one Gecko backup; Gecko-missing → one Dex backup; second attempt prevented; unresolved defers without protocol. |
| **Schema** | No |
| **Remains locked** | Stage reservations; Source Governor |

### Finding 10 — Remove fabricated accounting fallbacks

| Item | Detail |
|---|---|
| **Current code owner** | Protocol queue `transport_operations += int(delta or 1)` and `MeasuredTransportError` → count 1 |
| **Violated invariant** | Transport counts come only from successfully accepted measured identities; missing/malformed identities create accounting blockers; never invent counts. |
| **Exact repair** | On successful parse: add only measured `delta` (including 0). On `MeasuredTransportError`: set accounting blocker `TRANSPORT_IDENTITY_MEASUREMENT_FAILED` (or existing equivalent), leave transport count un-incremented by fabrication, keep request count from durable request ID, surface blocker in report/coverage terminal_status. |
| **Exact focused test** | After measured-identity failure, transport count is not fabricated; request count still recorded. |
| **Schema** | No |
| **Remains locked** | Six-unit measured transport contract |

### Finding 11 — Complete diagnostic consistency

| Item | Detail |
|---|---|
| **Current code owner** | Supply diagnostics and campaign pre-lifecycle admission surfaces |
| **Violated invariant** | Authoritative diagnostics must count and preserve categorical funnel outcomes without using them as scores/rankings. |
| **Exact repair** | Ensure diagnostics expose: above-floor nominations; below-floor; liquidity unknown; exact-pool no match; identity conflict; unsupported venue; protocol owner mismatch; base-mint mismatch; promoted observation-eligible; requires market revalidation; freeze-depth result; surplus-target result; source-request reconciliation result. Populate from existing prefilter_counts, protocol outcome_counts, observation_reserve_depth_status, and campaign reconciliation. |
| **Exact focused test** | Covered by aggregate diagnostics assertions in the new repair suite. |
| **Schema** | No |
| **Remains locked** | No scoring/ranking use of categories |

## 4. Repair order (TDD)

Strict red-green-refactor, one defect at a time:

1. Freeze admission + depth gate (Finding 1, partial 6)
2. Stage-seal fail-closed (Finding 2)
3. Protocol merge owner + revalidation union (Findings 3, 4)
4. Campaign-wide request reconciliation (Finding 5)
5. Holder-independent handoff (Finding 6 remainder)
6. Freshness + liquidity coercion (Finding 7)
7. Exact quote promotion (Finding 8)
8. Unknown-liquidity backup (Finding 9)
9. Transport non-fabrication (Finding 10)
10. Diagnostics consistency (Finding 11)
11. Campaign durable terminal wiring for depth and accounting blockers

## 5. Focused proof inventory (minimum)

Temporary databases and fixture transports only. New file:

`tests/test_v2_9_8b_graduated_discovery_code_audit_blocker_repair.py`

Must prove items 1–26 from the lane instruction (depth gates, seal blocker, merge survival, revalidation union, campaign reconciliation, holder handoff, freshness, NaN/inf, quote preservation, backups, transport non-fabrication, ceilings, ownership locks, no retrieval/decision/position/trade/audit/PnL unlock).

Verification commands only:

1. each new test during red-green;
2. new repair test file;
3. directly affected discovery/protocol/accounting/readiness/handoff/campaign-report tests;
4. no migration suite (053 not added);
5. `python -m compileall` on changed modules;
6. `git diff --check`.

## 6. Money-usefulness contribution

These repairs convert proven live attrition and silent accounting failures into honest, durable terminals and restore the intended memory-observation funnel so Printer can lawfully freeze two selected + two alternate observation candidates when the market produces them — without unlocking trading or weakening safety.

## 7. What remains locked / proof still required

Locked: live providers, authorization, WINDOW_15M, memory generation, retrieval, decisions, positions, trades, audits, PnL.

Still required after this lane: narrowest offline integrated-fixture campaign proof that walks intake → backup → protocol → freeze → durable terminal with fixture transports only, then a separate authorized live re-proof lane.

## 8. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Mitigation |
|---|---|
| Campaign terminal cause taxonomy drift | Reuse existing `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` and `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` / six-unit blocker strings |
| Backup path accidentally consuming protocol budget | Charge only reconciliation/market existing stages; never protocol before liquidity proven |
| Merge duplicate-ID fail-closed flapping on legitimate re-reads | Deduplicate only after detecting true dual emission of the same durable request_id across early/residual |
| Holder-path readiness field semantics | Preserve actual holder facts as context; do not invent holder_eligible=True |

## Verdict readiness

Implementation may begin only after this mapping is complete.  
This design is complete for implementation under TDD.

`V2_9_8B_GRADUATED_DISCOVERY_CODE_AUDIT_BLOCKER_REPAIR_DESIGN_COMPLETE`
