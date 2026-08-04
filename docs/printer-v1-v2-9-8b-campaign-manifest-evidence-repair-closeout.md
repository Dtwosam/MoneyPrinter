# V2-9.8B Campaign Manifest Evidence Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Campaign Manifest Evidence Repair`

## Verdict

`V2_9_8B_CAMPAIGN_MANIFEST_EVIDENCE_REPAIR_PASS`

Synthetic successful coverage entries are no longer invented from bare request IDs. Real stage-owned coverage is required for reconciliation PASS. Offline focused proof includes campaign-owner paths.

## Exact defect

`collect_stage_source_request_coverage()` synthesized `COMPLETED` coverage rows with zero transport and zero members whenever a stage reported a request ID without a coverage entry. That hid missing accounting evidence and could allow reconciliation PASS without stage-produced transport/member measurement.

## Production owners changed

| File | Change |
|---|---|
| `permanent_discovery_availability.py` | Collector no longer synthesizes; separate stage-reported IDs; three-way reconcile; market batch + gecko recon produce real coverage |
| `eligible_token_supply.py` | Diagnostics expose DexScreener locator + direct migration coverage/IDs; campaign coverage list includes intake stages |
| `graduated_supply_front_door.py` | Fresh locator emits real `source_request_coverage` |
| `direct_migration_discovery.py` | Direct pump intake/verify emit real `source_request_coverage` |
| `tests/test_v2_9_8b_campaign_manifest_evidence_repair.py` | New focused proof suite |

## Removal of synthetic coverage

Removed all fallbacks of the form:

```text
if request_id has no coverage → invent COMPLETED zero-transport entry
```

from protocol, backup, gecko, market, and holder collectors.

A request ID without stage-produced coverage remains missing and causes:

`CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`

## Real coverage sources wired

Each of the following now exposes stage-produced coverage when it runs:

| Stage | Surface |
|---|---|
| DexScreener fresh locator | `source_request_coverage` on locator report + `dexscreener_locator` diagnostics |
| Direct Pump discovery/verify | `source_request_coverage` on discovery report/ledger + `direct_migration_discovery` diagnostics |
| GeckoTerminal fresh nomination | existing real coverage (no ID-only fallback) |
| Unknown-liquidity backup | existing real coverage (no ID-only fallback) |
| DexScreener market batches | coverage appended per batch with measured transport count |
| GeckoTerminal reconciliation | coverage appended per fallback request |
| Early/residual protocol | existing real coverage (no ID-only fallback) |
| Holder context | only real `holder_source_request_coverage` accepted |

Lawful zero-transport is allowed only when the stage explicitly produces coverage with `transport_identity_count=0`.

## Reconciliation invariant

```text
set(durable request IDs)
==
set(stage-reported request IDs)
==
set(coverage manifest request IDs)
```

Surfaces:

- `durable_campaign_request_ids`
- `stage_reported_request_ids`
- `stage_produced_coverage_entries`
- `campaign_source_request_manifest`
- `campaign_source_request_reconciliation` (missing/extra/duplicates/ownership gaps)

## Focused tests and counts

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_campaign_manifest_evidence_repair.py` | **15 passed** |
| + remaining-runtime + graduated discovery repair suites | **110 passed** |
| `compileall` | OK |
| `git diff --check` | OK |

Minimum proofs covered:

1–5. Protocol/backup/gecko/locator/direct-pump IDs without coverage are not synthesized  
6. Collector invents no COMPLETED fallbacks  
7. Explicit lawful zero-transport reconciles  
8–9. Duplicate coverage and unknown extra IDs block  
10. Multi-stage real coverage reconciles exactly  
11–12. Campaign path blocks readiness on missing coverage; durable report exposes mismatch  

## Schema

No migration. JSON diagnostics/report fields only.

## Boundaries preserved

Freeze depth 4, surplus 8, $3k floor, ceiling 30, reservations `3/2/6/7/8/4`, MEMORY_OBSERVATION readiness, FUTURE_ACTION holder gate, Source Governor / Scheduler ownership, no trading/retrieval unlock.

## Remaining risks

- Stages that still omit coverage while creating durable requests will now fail closed (intended); full live multi-stage inventory must emit coverage on every governed call  
- Exact duplicate re-export across diagnostic surfaces is collapsed; distinct multi-stage ownership of one ID still fails closed  

## Money-usefulness contribution

Campaign terminals become honest about missing source-call evidence. Operators cannot pass pre-lifecycle readiness with incomplete accounting coverage, improving trust in memory-observation admission reports.

## What remains locked

Providers, live discovery/Scheduler runtime, authorization, WINDOW_15M, memory generation, retrieval, paper decisions, positions, trades, audits, PnL.

## Next proof required

Offline integrated-fixture campaign that walks every governed stage with fixture transports and proves durable == stage-reported == coverage end-to-end without prebuilt synthetic manifests.

## Commit subject

`Repair campaign source manifest evidence`

Do not push. Do not authorize or run a live campaign.
