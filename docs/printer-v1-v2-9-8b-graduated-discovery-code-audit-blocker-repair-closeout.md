# V2-9.8B Graduated Discovery Code-Audit Blocker Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Graduated Discovery Code-Audit Blocker Repair`

## Verdict

`V2_9_8B_GRADUATED_DISCOVERY_CODE_AUDIT_BLOCKER_REPAIR_PASS`

Every required audit blocker was repaired under strict red-green TDD. Focused offline proof passed. No providers, discovery runtime, Central Scheduler runtime, authorization, `WINDOW_15M`, memory generation, retrieval, paper decisions, positions, trades, audits, or PnL were run.

## Baseline

| Item | Value |
|---|---|
| Repository | `MoneyPrinter` |
| Required baseline HEAD | `a8197f09ee25aa0f926f6bc1a365ef92f8cfb433` |
| Baseline subject | `Implement graduated discovery and memory eligibility` |
| Repair branch | `grok/v2-9-8b-code-audit-blocker-repair` |
| Tracked tree at start | clean |
| Untracked preserved | `operator-runs/v2-9-8b-authoritative-mig050/`, `operator-runs/v2-9-8b-window-15m-final-authorization/...` |
| `/private/tmp/mp-preclaim` | not touched |

## Files changed

### Design / closeout

- `docs/printer-v1-v2-9-8b-graduated-discovery-code-audit-blocker-repair-design.md`
- `docs/printer-v1-v2-9-8b-graduated-discovery-code-audit-blocker-repair-closeout.md`

### Production

- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

### Tests

- `tests/test_v2_9_8b_graduated_discovery_code_audit_blocker_repair.py` (new)
- `tests/test_v2_9_8b_graduated_discovery_liquidity_memory_eligibility.py` (freshness fixture alignment)
- `tests/test_v2_9_8b_permanent_discovery_availability.py` (freeze admission uses `memory_observation_eligible`)

### Schema

- **No migration 053.** Existing tables and JSON evidence/report fields are sufficient.

## Audit findings and exact resolutions

### 1. Minimum freeze depth as admission gate

**Resolution:** `freeze_eligible_reserve` admits only `memory_observation_eligible is True` (removed `fully_eligible` fallback). Depth `< 4` returns empty selected/alternates with coverage authority. Campaign records `observation_reserve` / `freeze_depth_enforcement`, stops readiness/handoff, and surfaces `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`. Depth 4–7 → 2+2 + `SURPLUS_TARGET_NOT_MET`; ≥8 → `SURPLUS_TARGET_MET`.

### 2. Protocol stage-sealing fail-closed

**Resolution:** Removed broad `except Exception: sealed = None`. Catch `CampaignSixUnitError` / `MeasuredTransportError` / type errors; set `accounting_blocker` + `PROTOCOL_STAGE_SEAL_FAILURE:...`; do not fabricate sealed success or call the sink with invented evidence. Expected zero-work remains explicit `sealed = None`.

### 3. Early/residual protocol merge owner

**Resolution:** Added `merge_protocol_confirmation_reports`. Merges outcomes, remaining due, promotions, revalidation candidates, request/response/failure IDs, counts, coverage, and ordered `sealed_stage_evidence_blocks`. Legacy `sealed_stage_evidence` is last-block compatibility view only. Duplicate request IDs fail closed.

### 4. Market-revalidation union

**Resolution:** Added `union_market_revalidation_candidates` keyed by `(mint, pool, venue)`. Replaced truthy `A or B` residual selection in eligible supply.

### 5. Campaign-wide source-request reconciliation

**Resolution:** Added `build_campaign_source_request_manifest` and `reconcile_campaign_source_requests` with invariant equality of durable ID set and manifest ID set. Missing/duplicate/unowned → `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`. Request count remains separate from transport totals. Holder ledger is not the complete campaign source-call owner.

### 6. Holder gates removed from memory path

**Resolution:** Freeze ignores holder/`fully_eligible`. Campaign observation rows preserve real holder condition; never invent `holder_eligible=True` for memory admission. Readiness records actual holder eligibility. Permanent-discovery atomic readiness keys off freeze selection, not holder pass. `FULLY_ELIGIBLE` remains future-action-only. Future action stays `BLOCKED_OR_UNKNOWN`.

### 7. Evidence freshness

**Resolution:** Default expiry = `observed_at + EXACT_POOL_RECONCILIATION_SECONDS`. Explicit expiry validated (timezone-aware, after observed_at, ≤ observation max). Contradictions fail closed. `_coerce_liquidity_usd` rejects NaN, ±infinity, negative, non-numeric via `math.isfinite`.

### 8. Exact quote mint on promotion

**Resolution:** `promote_confirmed_with_retained_liquidity` loads retained base/quote/venue/pool/contract version. Requires base == mint and non-empty quote; pool conflicts fail closed. No hardcoded WSOL substitution.

### 9. Bounded unknown-liquidity backup

**Resolution:** Added `run_bounded_unknown_liquidity_backup` — one opposite-source exact-pool lookup via Source Governor + reconciliation budget. Dex→Gecko, Gecko→Dex. Provenance `liquidity_backup_attempted` prevents loops. Outcomes: above-floor → protocol due; below-floor; `EXACT_POOL_NO_MATCH`; `IDENTITY_CONFLICT`; still unknown → defer. No protocol before liquidity proven. Wired into permanent supply before early protocol.

### 10. No fabricated transport counts

**Resolution:** Removed `delta or 1` and MeasuredTransportError→1 fallbacks. Measurement failure sets accounting blocker `TRANSPORT_IDENTITY_MEASUREMENT_FAILED`; transport count stays measured-only; request count still recorded from durable ID.

### 11. Diagnostic consistency

**Resolution:** Diagnostics expose prefilter categories, protocol outcome/coverage/seal/blocker surfaces, liquidity backup summary, freeze-depth/surplus, and reconciliation helpers. Categories remain counts, not scores/ranks.

## Red tests observed

Strict red-green-refactor was applied. New suite initially exercised missing behaviors (depth gate empty selection, seal blocker, merge survival, revalidation union, reconciliation mismatch, freshness non-extension, NaN rejection, quote preservation, backup, transport non-fabrication). Existing suites then failed after admission/freshness tightening until fixtures were aligned to `memory_observation_eligible` and lawful observation-based expiry (not weakened ceilings).

## Focused proof results

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_graduated_discovery_code_audit_blocker_repair.py` | **28 passed** |
| `tests/test_v2_9_8b_graduated_discovery_liquidity_memory_eligibility.py` | passed |
| `tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py` | passed |
| `tests/test_v2_9_8b_permanent_discovery_conversion_repair.py` | passed |
| `tests/test_v2_9_8b_permanent_discovery_availability.py` | passed |
| `tests/test_v2_9_8b_multi_round_market_batch_six_unit_sequencing.py` | passed |
| Combined affected | **114 passed** |
| `python -m compileall` on changed modules | OK |
| `git diff --check` | OK |

## Freeze-depth enforcement

- `MINIMUM_FREEZE_DEPTH = 4` is an admission gate in freeze and campaign handoff.
- 0–3 → no selected, no alternates, coverage terminal, no readiness bundle, no lifecycle handoff.
- 4–7 → 2 selected + 2 alternates, `SURPLUS_TARGET_NOT_MET`.
- ≥8 → 2+2, `SURPLUS_TARGET_MET`.

## Durable blocker behavior

- Insufficient freeze depth → durable categorical terminal surface `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` via existing campaign terminal owner path (not an in-memory-only dict).
- Protocol seal / transport measurement / merge duplicate IDs / reconciliation mismatch → typed `accounting_blocker` fields for terminal report ingestion.
- Zero lifecycle/memory/retrieval/decision/position/trade/audit/PnL effects proven by scope and static lock test.

## Early/residual merge result

Both protocol sequences survive as ordered sealed blocks; IDs, counts, coverage, outcomes, promotions, and revalidation candidates are merged deterministically without overwriting sequence 1.

## Campaign-wide request reconciliation

Manifest + reconcile owners enforce exact ID-set equality and fail closed on missing/duplicate/unowned requests. Request vs transport counts remain separate surfaces.

## Holder-independent handoff proof

Holder-extreme observation candidates freeze to 2+2 with `future_action_eligibility=BLOCKED_OR_UNKNOWN` and without requiring holder pass.

## Freshness and exact-quote preservation

Old `observed_at` is not refreshed by later ingestion. Non-WSOL quote mints are preserved through direct promotion; base/quote/pool conflicts block promotion.

## Unknown-liquidity backup behavior

One governed opposite-source backup; second attempt prevented; unresolved defers without protocol confirmation.

## Schema result

No migration 053. Migration 052 remains the head for memory-observation layers.

## Money-usefulness contribution

Repairs convert silent attrition and accounting discards into honest durable terminals and restore the intended memory-observation freeze funnel so lawful surplus candidates can become two selected + two alternate observation slots — without unlocking trading.

## What remains locked

- Providers / live discovery / Central Scheduler runtime
- Authorization create/consume
- `WINDOW_15M`, memory generation, retrieval
- Paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- Flat 30 ceiling and `3/2/6/7/8/4` reservations
- Source Governor ownership
- Scoring/ranking/confidence systems

## Proof still required

Narrowest next offline integrated-fixture proof lane:

1. Fixture campaign walk: intake → unknown-liquidity backup → early+residual protocol → freeze depth gate (pass and fail) → durable terminal report with full source-request reconciliation.
2. Separate authorized live re-proof only after offline integrated fixture PASS.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Notes |
|---|---|
| Campaign-wide manifest assembly at full runtime | Helpers are proven offline; full campaign owner must still assemble every stage’s coverage entries into the reconcile input in the integrated-fixture lane |
| Backup pair normalization variance | Fixture pair shapes may yield EXACT_POOL_NO_MATCH vs above-floor; both are fail-closed and single-attempt |
| ReadinessCandidate.holder_eligible field | Still present for bundle schema; now records actual holder fact, not forced True |
| No pre-existing failures in the focused affected suite | 114/114 passed |

## Commit subject

`Repair graduated discovery audit blockers`

Do not push. Do not create authorization. Do not run a live campaign.
