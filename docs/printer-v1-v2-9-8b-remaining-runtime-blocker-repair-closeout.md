# V2-9.8B Remaining Graduated-Discovery Runtime Blocker Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Remaining Graduated-Discovery Runtime Blocker Repair`

## Verdict

`V2_9_8B_REMAINING_RUNTIME_BLOCKER_REPAIR_PASS`

All four production-path runtime defects were repaired under TDD. Focused offline proof includes campaign-owner paths, not helper-only tests. No providers, discovery runtime, Scheduler runtime, authorization, `WINDOW_15M`, memory, retrieval, decisions, positions, trades, audits, or PnL were run.

## Baseline

| Item | Value |
|---|---|
| Required branch | `grok/v2-9-8b-code-audit-blocker-repair` |
| Required HEAD | `03e65fd25717340ab4b36481b7d1f1a9332eda57` |
| Subject | `Repair graduated discovery audit blockers` |
| Repair branch | `grok/v2-9-8b-remaining-runtime-blocker-repair` |
| Tracked tree at start | clean |
| Untracked preserved | operator-runs authorization/mig050 packages |
| `/private/tmp/mp-preclaim` | not touched |

## Files changed

### Design / closeout

- `docs/printer-v1-v2-9-8b-remaining-runtime-blocker-repair-design.md`
- `docs/printer-v1-v2-9-8b-remaining-runtime-blocker-repair-closeout.md`

### Production

- `src/printer_v1/operator_cli/pilot_input_readiness.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/discovery/eligible_token_supply.py`

### Tests

- `tests/test_v2_9_8b_remaining_runtime_blocker_repair.py` (new)

### Schema

- **No migration 053.** Readiness purpose and memory context persist in existing `source_ledger_json` / payload hash surfaces. Campaign reconciliation is diagnostics/report JSON.

## Defect resolutions

### 1. Separate MEMORY_OBSERVATION readiness from action holder eligibility

| Item | Detail |
|---|---|
| **Failing behavior** | Freeze admitted observation-eligible holder-extreme candidates, but `evaluate_readiness_gates` always required `holder_eligible`, so memory readiness bundles never formed |
| **Owner repaired** | `pilot_input_readiness.py`; campaign call site in `authoritative_live_operational_campaign.run_operational` |
| **Implementation** | Explicit `readiness_purpose` ∈ `{MEMORY_OBSERVATION, FUTURE_ACTION}` (default `FUTURE_ACTION` preserves legacy). MEMORY_OBSERVATION requires market floor, pool/mint, lawful route, and `memory_observation_eligible=True`; does not require holder eligibility. Bundle payload + durable `source_ledger_json` record purpose and truthful holder/memory context. Campaign builds readiness with `MEMORY_OBSERVATION`. Never invents `holder_eligible=True`. |
| **E2E proof** | `TestMemoryObservationReadiness::test_campaign_holder_extreme_memory_readiness_bundle` — campaign permanent path freezes 2+2, holder_eligible false, MEMORY_OBSERVATION bundle succeeds, future_action remains BLOCKED_OR_UNKNOWN. Unit path proves FUTURE_ACTION still BLOCKED_HOLDER. |
| **Remaining risk** | Native goplus path may still mark extreme concentration as holder-evidence-eligible (`eligible=True` with EXTREME label); memory readiness does not depend on that. Future-action policy remains separate. |

### 2. Wire campaign-wide request reconciliation into campaign owner

| Item | Detail |
|---|---|
| **Failing behavior** | Helpers existed but campaign never assembled/enforced reconcile before readiness; `ledger.governed_requests` was treated as authoritative campaign source-call count |
| **Owner repaired** | `assemble_and_reconcile_campaign_source_requests` / collectors in `permanent_discovery_availability.py`; campaign permanent path in `authoritative_live_operational_campaign.py`; supply diagnostics in `eligible_token_supply.py` |
| **Implementation** | Campaign assembles coverage from stage diagnostics (protocol, backup, gecko, market reports, holder, explicit lists), loads durable IDs via stage-known IDs + discovery request_key prefixes (not bare counter), reconciles, fails closed with `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` before readiness/handoff. Durable pre-lifecycle admission exposes full manifest, IDs, missing/extra, counts, transport total. `holder_ledger_governed_requests` is diagnostic only. |
| **E2E proof** | Multi-stage fixture campaign reconciles OK; missing Gecko/backup entry blocks readiness with categorical terminal; duplicate protocol IDs fail closed. |
| **Remaining risk** | Full live multi-stage key-prefix inventory must be complete in integrated fixture/live lanes so durable scrape and stage reports stay aligned. |

### 3. Post-filter freeze depth as sole authority

| Item | Detail |
|---|---|
| **Failing behavior** | Campaign used `observation_reserve_depth_status(len(observation_rows))` (raw count) so 4 raw with 1 stale could claim freeze-ready |
| **Owner repaired** | `freeze_eligible_reserve` selection_authority; campaign permanent path |
| **Implementation** | Freeze always reports input/valid/stale/duplicate-mint/duplicate-pool/malformed counts + depth/surplus/coverage. Campaign freezes first, then admits solely from freeze post-filter valid depth. No raw-count authority. |
| **E2E proof** | Campaign: 4 raw − 1 stale → coverage blocker, no readiness; 6 raw with duplicate identities → 4 valid, 2 selected + 2 alternates, SURPLUS_TARGET_NOT_MET. |
| **Remaining risk** | None material offline; clock for freeze uses real `datetime.now` so tests must use far-future expiry (documented). |

### 4. Measure fresh nomination and liquidity-backup transports

| Item | Detail |
|---|---|
| **Failing behavior** | Gecko fresh swallowed measurement exceptions; backup left transport_identity_count=0 without measuring |
| **Owner repaired** | `run_geckoterminal_fresh_nomination`; `run_bounded_unknown_liquidity_backup` |
| **Implementation** | Gecko: catch `MeasuredTransportError` → accounting blocker, preserve request ID, no successful stage claim, coverage entry exposed. Backup: MeasuredTransportLedger per request; measured counts in coverage; measurement failure blocks protocol promotion path; coverage feeds campaign reconciliation. Never fabricate transport count after failure. |
| **E2E proof** | Successful Dex→Gecko and Gecko→Dex backup measured transport=1; measurement failure preserves request ID, transport=0, accounting blocker; Gecko failure not swallowed; request count separate from transport count. |
| **Remaining risk** | Fixtures must declare measured identities when asserting non-zero transport; zero-transport remains lawful when the source contract declares none. |

## Integration fixtures

1. Full MEMORY_OBSERVATION composition: freeze depth ≥4, 2+2, holder-extreme not holder-safe, readiness bundle, future action blocked, recon OK, lifecycle not started, zero forbidden capability rows.
2. Three valid candidates: durable coverage blocker terminal, no readiness.

## Schema result

No migration 053.

## Exact test counts

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_remaining_runtime_blocker_repair.py` | **14 passed** |
| + pilot readiness + prior graduated discovery repair suites | **69 passed** |
| `compileall` changed modules | OK |
| `git diff --check` | OK |

## Campaign manifest result

Campaign owner builds and enforces `durable_campaign_request_ids`, `campaign_source_request_manifest`, and `campaign_source_request_reconciliation` before readiness. Mismatch terminal: `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`.

## Holder-independent readiness result

MEMORY_OBSERVATION readiness succeeds with `holder_eligible=false`, preserves EXTREME condition context, keeps `future_action_eligibility=BLOCKED_OR_UNKNOWN`. FUTURE_ACTION purpose still blocks.

## Post-filter freeze result

Admission uses only freeze `valid_fresh_unique_observation_depth`.

## Measured transport result

Gecko and backup no longer swallow measurement failures; successful backups record measured transport identity counts; request counts remain separate.

## Money-usefulness contribution

Concentrated tokens that are lawful memory-observation candidates can now form a durable pre-lifecycle MEMORY_OBSERVATION readiness bundle without being falsely blocked by action-holder gates, while campaign accounting integrity is enforced before handoff.

## What remains locked

Providers, live discovery/Scheduler runtime, authorization, WINDOW_15M, memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, flat 30 ceiling, reservations `3/2/6/7/8/4`, Source Governor ownership, scoring/ranking.

## Next proof required

Narrowest offline integrated-fixture lane that walks real fixture transports through:

```text
fresh discovery → unknown-liquidity backup → early+residual protocol
→ holder-extreme observation → post-filter freeze
→ campaign-wide reconciliation → MEMORY_OBSERVATION readiness
→ stop before lifecycle
```

using complete stage-owned request_key prefixes end-to-end (not prebuilt GraduatedSupply only). Then a separate authorized live re-proof.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Notes |
|---|---|
| Native holder extreme still labeled eligible by goplus path | Memory readiness does not require holder pass; action purpose still gated |
| Broad campaign_id DB scrape intentionally avoided | Prefer stage-reported IDs + discovery request_key prefix |
| Freeze uses wall-clock now | Operators/tests must supply far-future evidence expiry for permanent fixtures |

## Commit subject

`Repair remaining graduated discovery runtime blockers`

Do not push. Do not authorize or run a live campaign.
