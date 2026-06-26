# Printer V1 Lane C Source Budget and Source Governor Verification

## 1. Status

This is Post-Lane 10 Proposed Lane C - Source Budget and Source Governor Verification.

Lane C is documentation/static verification only.

Lane C does not implement Memory Factory.

Lane C does not run source fetching, runtime, scheduler jobs, snapshot collection, memory creation, retrieval, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper audits, or PnL.

Lane C does not authorize wallet logic, private keys, signing, live trading, real funds, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

## 2. Source-of-Truth Documents Checked

This verification is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`
- `docs/printer-v1-post-lane10-lane-a-adoption-checkpoint.md`
- `docs/printer-v1-lane-b-conservative-15m-memory-factory-readiness-review.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`
- `docs/printer-v1-paper-position-reactivation-review.md`

The current active roadmap extension is:

- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

## 3. Purpose of Lane C

Lane C verifies, by static inspection only, whether the existing Source Governor, source registry, source recording, and governed adapter boundaries appear ready for a later bounded 15m Memory Factory cycle.

Lane C must not collect source data.

Lane C must not mutate the persistent DB.

Lane C must not start implementation.

## 4. Current Locked Capabilities

The following remain locked:

- BUY
- SELL
- HOLD
- paper positions
- trade events
- paper audits
- PnL
- runtime expansion
- source fetching
- snapshot creation
- memory creation
- retrieval activation
- paper decision creation
- wallet logic
- private keys
- signing
- live trading
- real funds
- paid API dependencies
- scoring systems
- ranking systems
- confidence percentage systems
- weighted decision logic
- embeddings
- vectors

The first Memory Factory implementation must keep paper decisions off.

The 5m window remains support-only.

15m remains the first main Memory Factory target.

A Memory Factory cycle may validly produce zero clean memories if evidence fails.

Clean memory must never be forced.

## 5. Read-Only Inspection Commands Used

Static inspection used only read-only commands:

- `git status --short`
- `rg -n "Lane C|Source Budget|Source Governor|source budget|source request|source response|source failure|Memory Factory|5m|15m|paper decisions|BUY|SELL|HOLD|position|PnL" AGENTS.md docs\printer-v1-post-lane10-proposed-next-build-order.md docs\printer-v1-post-lane10-lane-a-adoption-checkpoint.md docs\printer-v1-lane-b-conservative-15m-memory-factory-readiness-review.md`
- `Get-Content docs\printer-v1-memory-factory-guide.md | Select-Object -Skip 500 -First 230`
- `Get-Content docs\printer-v1-buy-unlock-preconditions.md | Select-Object -First 80`
- `Get-Content docs\printer-v1-paper-position-reactivation-review.md | Select-Object -First 80`
- `rg --files src tests migrations docs | rg "source|sources|governor|adapter|dexscreener|coingecko|defillama|alternative|jupiter|goplus|solana_rpc|rate|budget|safety|quote"`
- `rg -n "Source Governor|SourceGovernor|source_governor|source request|source_response|source_failure|printer_source_requests|printer_source_responses|printer_source_failures|rate limit|rate_limit|budget|quota|direct API|requests\.get|httpx|urllib|aiohttp|fetch" src tests migrations`
- `Get-ChildItem src\printer_v1\sources`
- `Get-ChildItem src\printer_v1`
- `Get-Content src\printer_v1\sources\governor.py | Select-Object -First 220`
- `Get-Content src\printer_v1\sources\governed_execution.py | Select-Object -First 240`
- `Get-Content src\printer_v1\sources\recording.py | Select-Object -First 220`
- `Get-Content src\printer_v1\sources\registry.py | Select-Object -First 220`
- `rg -n "requests|urllib|urlopen|httpx|aiohttp|urlretrieve|socket|execute_source_request_with_governor|SourceAdapterContext|governor_approved|GOVERNOR_ONLY_EXECUTION_PATH|rate_limit|default_rate_limit|stale_after|retry_after" src\printer_v1\sources tests\test_phase23_source_adapter_execution_contract.py tests\test_phase24_dexscreener_adapter_disabled.py tests\test_phase25_one_shot_real_source_smoke_check.py tests\test_post_rc_governed_public_broad_context_source_adapters.py`
- `Get-Content tests\test_phase23_source_adapter_execution_contract.py | Select-Object -First 240`
- `Get-Content tests\test_phase2_source_registry_governor.py | Select-Object -First 260`
- `Get-Content tests\test_post_rc_governed_public_broad_context_source_adapters.py | Select-Object -First 260`
- `Get-Content tests\test_phase23_source_adapter_execution_contract.py | Select-Object -Skip 220 -First 90`
- `Get-Content src\printer_v1\sources\contracts.py | Select-Object -First 180`
- `Get-Content migrations\002_source_registry_governor.sql | Select-Object -First 220`
- `Get-Content migrations\001_database_foundation.sql | Select-Object -Skip 28 -First 45`

## 6. Existing Source Governor Files and Components Found

Static inspection found:

- `src/printer_v1/sources/governor.py`
- `src/printer_v1/sources/contracts.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/sources/governed_execution.py`
- `src/printer_v1/sources/recording.py`
- `migrations/002_source_registry_governor.sql`
- `migrations/001_database_foundation.sql`

The source registry defines free/public or optional free-tier source definitions, allowed request kinds, default rate limits, stale-after windows, retry delays, max retries, priority classes, and restrictions.

`governor.py` validates source names, paid-plan rejection, request kinds, token-level versus broad-context usage, Jupiter quote paper-only restriction, rate-limit rejection, stale classification, and source priority.

`contracts.py` defines the governed execution path as `source_governor_record_then_adapter_boundary` and requires `SourceAdapterContext` with `governor_approved`.

`governed_execution.py` records source requests before adapter execution, records failures when Source Governor rejects a request, records source responses on complete/partial/stale results, and records failures on failed results.

## 7. Existing Governed Source Adapter Files and Components Found

Static inspection found governed source adapter modules:

- `src/printer_v1/sources/dexscreener.py`
- `src/printer_v1/sources/geckoterminal.py`
- `src/printer_v1/sources/pumpportal.py`
- `src/printer_v1/sources/pumpswap.py`
- `src/printer_v1/sources/alternative_me.py`
- `src/printer_v1/sources/coingecko.py`
- `src/printer_v1/sources/defillama.py`
- `src/printer_v1/sources/goplus.py`
- `src/printer_v1/sources/jupiter_quote.py`
- `src/printer_v1/sources/solana_rpc_holder.py`

The registry includes:

- `dexscreener`
- `geckoterminal`
- `pumpportal`
- `pumpswap`
- `alternative_me`
- `coingecko`
- `defillama`
- `goplus`
- `solana_rpc`
- `helius_free`
- `jupiter_quote`

These sources are registered as free/public, free/public-or-limited, free-or-user-supplied, or optional free tier. No registered source requires a paid plan.

## 8. Existing Source Recording and Trace Components Found

Static inspection found source trace tables in `migrations/001_database_foundation.sql`:

- `printer_source_requests`
- `printer_source_responses`
- `printer_source_failures`

Static inspection found source registry/governor tables in `migrations/002_source_registry_governor.sql`:

- `printer_source_registry`
- `printer_source_health`
- `printer_source_rate_limits`

Static inspection found recording helpers in `src/printer_v1/sources/recording.py`:

- `record_source_request`
- `record_source_response`
- `record_source_failure`

The recording helpers store request kind, source status, data quality label, normalized response payload hash, normalized payload JSON, failure type, failure message, and retry-after timing.

## 9. Existing Source Budget and Rate-Limit Components Found

Static inspection found:

- per-source `default_rate_limit_per_minute` values in `src/printer_v1/sources/registry.py`
- per-source `stale_after_seconds`
- per-source `retry_after_seconds`
- per-source `max_retries`
- `can_request_source(...)` rate-limit rejection in `src/printer_v1/sources/governor.py`
- `get_retry_after(...)` and `should_cooldown_source(...)` in `src/printer_v1/sources/governor.py`
- `printer_source_rate_limits` schema in `migrations/002_source_registry_governor.sql`

Static inspection did not prove that a future 15m Memory Factory command already calculates aggregate per-cycle budgets. That remains a Lane C unresolved question for later implementation planning.

## 10. Existing Tests Related to Source Governor, Source Contracts, Recording, and Safety

Static inspection found tests covering relevant source behavior:

- `tests/test_phase2_source_registry_governor.py`
- `tests/test_phase23_source_adapter_execution_contract.py`
- `tests/test_phase24_dexscreener_adapter_disabled.py`
- `tests/test_phase25_one_shot_real_source_smoke_check.py`
- `tests/test_post_rc_governed_public_broad_context_source_adapters.py`
- `tests/test_post_rc_geckoterminal_discovery_adapter.py`
- `tests/test_post_rc_pumpportal_discovery_adapter.py`
- `tests/test_post_rc_pumpswap_confirmation_adapter.py`
- `tests/test_post_rc_solana_rpc_safety_evidence_fixture_normalizer.py`
- `tests/test_post_rc_jupiter_paper_quote_evidence_fixture_normalizer.py`
- `tests/test_post_rc_controlled_governed_evidence_fill_path.py`

Representative tests assert:

- registered sources are expected and not paid-plan dependent
- unknown and paid sources are rejected
- allowed request kinds are enforced
- Jupiter quote is restricted to paper quote realism
- rate-limit rejection records failure without adapter calls
- source requests, responses, and failures are recorded
- adapter execution requires Source Governor context
- engine modules do not import the governed adapter execution boundary
- broad-context adapters record source rows without downstream unlocks
- tests scan for forbidden fragments such as direct requests/httpx usage, wallet, confidence, and weighted logic

## 11. Static Direct Bypass Risk Review

No obvious direct engine/source bypass risk was visible from the inspected tests and files.

The strongest existing guardrails found are:

- adapter execution requires `governor_approved=True`
- adapter execution requires `GOVERNOR_ONLY_EXECUTION_PATH`
- request kinds are validated by source definition
- paid dependency is rejected
- rate-limit rejection records failure without adapter call
- source request is recorded before adapter execution
- failure and stale data are recorded honestly
- tests assert engine modules do not import `execute_source_request_with_governor`

Important caveat:

Several adapter modules include `urllib.request.urlopen` transport functions. This is not automatically a bypass if the only allowed execution path remains Source Governor controlled. A future implementation lane must prove no engine calls those transports directly and no operator command bypasses source request recording.

## 12. Suitability for a Later Bounded 15m Memory Factory Cycle

Current source paths appear directionally suitable for a later bounded 15m Memory Factory cycle if that future lane:

- uses only Source Governor approved requests
- records every request, response, and failure
- respects per-source rate limits and stale windows
- keeps token-level snapshots higher priority than broad context
- keeps Jupiter quote evidence paper-only
- keeps Solana RPC read-only
- keeps paid dependencies rejected
- keeps paper decisions off
- accepts zero clean memories when evidence fails

Lane C does not prove live source capacity. It only verifies static readiness.

## 13. Source Budget Questions Still Unresolved

Before implementation, the operator still needs answers to:

- What is the exact per-cycle source request budget for a conservative 15m run?
- How many TRACK_FAST and TRACK_NORMAL tokens can be active at once?
- What is the maximum broad-context request count per cycle?
- What failure rate stops the cycle?
- What stale response rate stops the cycle?
- How are rate-limit windows counted across multiple sources?
- How does a future command read or update `printer_source_rate_limits`?
- What operator report field summarizes source budget use?
- What dry-run will prove budgets before persistent collection?

## 14. Source Governor Questions Still Unresolved

Before implementation, the operator still needs answers to:

- Which exact request kinds are required for a 15m Memory Factory cycle?
- Which adapters are allowed in the first implementation lane?
- Which adapters are fixture-only versus network-capable under operator approval?
- How is operator approval represented for a future source run?
- How does the future implementation prevent direct use of adapter transports?
- How are source failures grouped by token/pair/window?
- How are retries bounded?
- How is source cooldown reported?
- How are stale or partial results prevented from clean memory use?

## 15. Risks and Gaps Before Implementation

Risks before implementation:

- per-cycle source budgets are not yet expressed as an operator-ready configuration
- network-capable transports exist and must remain gated by Source Governor context
- broad context sources must not compete with token-level snapshots
- Jupiter quote must remain paper realism only
- Solana RPC must remain read-only and free/operator-supplied
- source failures must remain visible instead of being hidden behind retries
- rate-limit failures must not trigger loops or provider rotation
- first Memory Factory implementation must not drift into paper decisions

## 16. Stop Conditions for Future Implementation

A future implementation lane must stop if:

- a source request would bypass Source Governor
- a source response or failure would not be recorded
- a paid API dependency is required
- an API key becomes mandatory for the baseline path
- source rate limits are exceeded without honest failure recording
- source failures are hidden
- retry behavior becomes unbounded
- source fetching runs outside an operator-approved bounded lane
- token-level snapshots are starved by broad context
- clean memory would be forced from missing, stale, failed, dirty, partial, mismatched, or conflicting evidence
- paper decisions are created during first Memory Factory implementation
- BUY, SELL, HOLD, positions, trade events, paper audits, or PnL are created

## 17. What Must Not Be Built Yet

Do not build in Lane C:

- Memory Factory implementation
- source fetching
- scheduler execution
- runtime
- snapshot collection
- memory creation
- retrieval
- paper decisions
- BUY, SELL, or HOLD
- paper positions
- trade events
- paper audits
- PnL
- wallet logic
- private-key logic
- signing or transaction logic
- paid API dependencies
- scoring, ranking, confidence percentages, or weighted logic
- embeddings or vectors

## 18. Lane C Acceptance Checklist

Lane C is accepted when:

- source-of-truth documents checked are listed
- active roadmap extension is identified
- Lane C is confirmed as documentation/static verification only
- existing Source Governor files/components are listed
- existing governed adapter files/components are listed
- existing source trace/recording files/components are listed
- existing source budget/rate-limit files/components are listed
- relevant tests are listed
- static bypass risk is assessed
- suitability for later bounded 15m Memory Factory is stated with caveats
- unresolved source budget and Source Governor questions are documented
- stop conditions are documented
- BUY, SELL, HOLD, positions, trade events, paper audits, and PnL remain locked

## 19. Next Recommended Lane

The next recommended lane after Lane C is:

Proposed Lane D - Scheduler, Tracking Queue, and Window-Close Readiness.

Lane D should remain readiness-focused unless the operator explicitly authorizes a narrower implementation task.
