# V2-9.8B Durable Request Identity and Stage Accounting Blocker Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Durable Request Identity and Stage Accounting Blocker Repair`

## Verdict

`V2_9_8B_DURABLE_ID_AND_STAGE_BLOCKER_REPAIR_PASS`

Both defects are closed through production-path offline tests. No providers, discovery runtime, Scheduler runtime, authorization, `WINDOW_15M`, memory, retrieval, decisions, positions, trades, audits, or PnL were run.

## Exact two defects

1. **False durable IDs** — `load_durable_campaign_source_request_ids()` copied stage-reported IDs into the durable set without proving a `printer_source_requests` row exists.
2. **Incomplete accounting-blocker propagation** — campaign reconciliation only checked protocol, liquidity backup, and Gecko nomination for accounting blockers; locator (and other stages) could fail measurement while still looking successful.

## Production owners changed

| File | Change |
|---|---|
| `permanent_discovery_availability.py` | Database-proven durable IDs; generic `collect_stage_accounting_blockers`; assemble exposes three ID sets + categorical detail; market-batch measurement failure sets accounting blocker |
| `graduated_supply_front_door.py` | Locator measurement failure uses typed `MeasuredTransportError`, sets accounting blocker, returns zero mints/observations, blocks stage |
| `eligible_token_supply.py` | Locator and direct-migration diagnostics carry accounting blocker / safe-stop surfaces |
| `tests/test_v2_9_8b_durable_id_and_stage_blocker_repair.py` | New focused proofs |
| Closeout | this document |

## Database-proven durable-ID behavior

- Stage-reported IDs and durable DB IDs remain independent.
- Candidate stage IDs are queried via `WHERE id IN (...)` against `printer_source_requests`.
- Only existing rows enter `durable_campaign_request_ids`.
- Prefix lookup may add other genuine durable rows.
- Stage-reported ID with no DB row → `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` with `STAGE_REPORTED_REQUEST_NOT_DURABLE`.
- No insert of missing rows during reconciliation.

Exposed:

```text
stage_reported_request_ids
durable_campaign_request_ids
stage_reported_not_durable
durable_not_stage_reported
coverage_request_ids
```

Invariant:

```text
database-proven durable IDs
== stage-reported IDs
== coverage manifest IDs
```

## All-stage accounting-blocker propagation

`collect_stage_accounting_blockers()` scans:

- DexScreener locator
- direct migration (including `campaign_safe_stop` / `accounting_block_reason`)
- Gecko fresh nomination
- unknown-liquidity backup
- market batch reports
- protocol confirmation
- holder context
- final refresh
- other diagnostic maps with `accounting_blocker` / safe-stop flags

Any such blocker forces campaign reconciliation BLOCKED before readiness/handoff.

Locator measurement failure specifically:

- typed `MeasuredTransportError` catch
- durable request ID preserved
- `accounting_blocker=True` + reason
- coverage `BLOCKED`
- zero matched mints, zero pool observations
- stage terminal BLOCKED

Ordinary candidate-local outcomes (owner mismatch, below-floor, exact-pool no-match) are not treated as accounting blockers unless the stage already sets that surface.

## Exact tests and counts

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_durable_id_and_stage_blocker_repair.py` | **15 passed** |
| + campaign manifest evidence + remaining-runtime suites | **44 passed** |
| `compileall` | OK |
| `git diff --check` | OK |

## Schema result

No migration. Existing `printer_source_requests` and diagnostics JSON.

## Money-usefulness contribution

Pre-lifecycle admission cannot claim PASS with invented durable request identity or silent stage accounting failures. Operators get honest blocked terminals before memory readiness, protecting the integrity of the observation pipeline.

## What remains locked

Freeze depth 4, surplus 8, $3k floor, ceiling 30, reservations `3/2/6/7/8/4`, MEMORY_OBSERVATION readiness, FUTURE_ACTION holder gate, Source Governor / Scheduler ownership, retrieval, trading, PnL, authorization, live providers.

## Remaining risks

- Stages that still omit `accounting_blocker` while failing measurement may need per-stage wiring as they are extended
- Full live multi-stage fixture walk remains the next proof, not a prebuilt GraduatedSupply-only path

## Next offline proof

Integrated fixture-transport campaign:

```text
locator → direct pump → gecko → backup → market → protocol
→ durable/stage/coverage ID equality
→ all-stage accounting blockers (pass and fail paths)
→ MEMORY_OBSERVATION readiness or durable mismatch terminal
→ stop before lifecycle
```

## Commit subject

`Repair durable request identity and stage blockers`

Do not push. Do not authorize or run a live campaign.
