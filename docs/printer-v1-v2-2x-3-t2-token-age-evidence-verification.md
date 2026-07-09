# Printer V1 V2-2X.3 T2 Token-Age Evidence Verification

Status: VERIFICATION ONLY

Verification verdict: `VERIFICATION_PASS_WITH_BLOCKERS`

V2-2X.3 independently verified the V2-2X.2 fixture-first T2 token-age
implementation. This lane did not implement code, change tests, add migrations,
mutate persistent data, run live sources, activate PumpPortal, start runtime or
scheduler work, generate memory, activate retrieval, create paper decisions, or
unlock any financial path.

V2-2Y, V2-3, V2-4, live PumpPortal transport, source expansion, runtime,
scheduler, memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, and PnL remain paused.

## Source Stack Read

The verification used these documents together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md`
- `docs/printer-v1-v2-2x-token-age-evidence-source-readiness-review.md`
- `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md`
- `docs/printer-v1-v2-2x-2-t2-token-age-evidence-implementation-fixture-proof.md`
- `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md`

Anchors checked:

- V2-2J closeout: `c6f002a`
- V2-2X readiness review: `5b9f93b`
- V2-2X.1 design: `35b9356`
- V2-2X.2 implementation: `7eae329`
- V2-2P.3 pair-age verification: `be70309`

## Commit Scope Verified

`git show --name-only --oneline --no-renames 7eae329` and
`git diff 7eae329^ 7eae329 --name-only` showed exactly the expected files:

- `src/printer_v1/sources/pumpportal.py`
- `src/printer_v1/discovery/parser.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`
- `docs/printer-v1-v2-2x-2-t2-token-age-evidence-implementation-fixture-proof.md`

No extra production files, migrations, runtime files, scheduler files, memory
files, retrieval files, paper decision files, position/trade/audit/PnL files,
wallet/private-key files, paid API files, embedding/vector files, or unrelated
files were changed by `7eae329`.

## Files Inspected

Static inspection covered:

- `src/printer_v1/sources/pumpportal.py`
- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`
- `docs/printer-v1-v2-2x-2-t2-token-age-evidence-implementation-fixture-proof.md`

## PumpPortal Implementation Verification

`src/printer_v1/sources/pumpportal.py` verifies as follows:

| Requirement | Result |
| --- | --- |
| `_PUMPPORTAL_LAUNCH_STALENESS_THRESHOLD_SECONDS = 3600.0` | PASS |
| Timestamp priority is `tokenCreatedAt`, then `createdTimestamp`, then `timestamp` | PASS |
| `captured_at` is not used as token creation time | PASS |
| Stale events use strict `> 3600.0` rejection | PASS |
| Exactly `3600.0` seconds is accepted | PASS |
| Future timestamps rejected | PASS |
| Zero, negative, empty, and unparseable timestamps rejected | PASS |
| Migration stream does not call launch timestamp extraction | PASS |
| `pumpfun_migration_stream` never populates `token_created_at` | PASS |
| `request_kind` is preserved downstream in the PumpPortal token dict | PASS |
| Adapter remains fixture-transport-only | PASS |
| No live transport, WebSocket, or HTTP behavior introduced | PASS |
| Default source activation unchanged (`enabled_by_default=False`) | PASS |

Static search confirmed:

- `supports_network_execution: bool = False`
- `fixture_transport_only: bool = True`
- no `requests`, `websocket`, `httpx`, `aiohttp`, or live transport code in
  `pumpportal.py`

## Parser Implementation Verification

`src/printer_v1/discovery/parser.py` verifies as follows:

| Requirement | Result |
| --- | --- |
| `_derive_token_age_evidence_tier()` exists | PASS |
| Returns `"T2"` only when `source_name == "pumpportal"` | PASS |
| Requires `request_kind == "pumpfun_launch_stream"` | PASS |
| Requires `token_created_at_raw is not None` | PASS |
| Requires `token_age_seconds is not None` | PASS |
| Non-PumpPortal sources return `None` | PASS |
| Migration events return `None` because they carry no `token_created_at` | PASS |
| `token_age_seconds` still derives only from `token_created_at` | PASS |
| `pair_age_seconds` is never copied to `token_age_seconds` | PASS |
| `pair_created_at` is never copied to `token_created_at` | PASS |
| `derive_age_bucket()` still reads only token age | PASS |
| A3 logic remains in `selection_batch.py` and still gates on real token age | PASS |
| Recent-active logic still derives from token-age bucket | PASS |
| No scoring/ranking/confidence/weighted logic added | PASS |

Static search also confirmed `selection_batch.py` still documents bucket
assignment as categorical and no-score/no-rank/no-confidence/no-weighted logic.

## Test Coverage Verification

`tests/test_v2_2x2_t2_token_age_evidence.py` covers:

- valid `tokenCreatedAt`;
- valid `createdTimestamp`;
- valid fallback `timestamp`;
- priority behavior when the higher-priority value is valid;
- missing timestamp;
- zero timestamp;
- negative timestamp;
- unparseable timestamp;
- future timestamp;
- stale timestamp over 3600 seconds;
- exact 3600-second boundary accepted;
- migration hard block;
- pair-age isolation;
- A3 with real T2 age;
- A3 blocked without token age;
- A3 blocked with pair age only;
- metadata survival for `token_age_evidence_tier`;
- adapter disabled by default;
- fixture-only metadata;
- pure normalization functions with no live calls.

Minor coverage note:

- The suite proves priority with valid high-priority and absent high-priority
  cases. It does not include a dedicated edge test for an invalid high-priority
  timestamp with a valid lower-priority timestamp. The implementation uses
  first non-empty wins and rejects the invalid first field, which is safe and
  conservative. Add an explicit no-fallthrough edge test in V2-2Y or the next
  T2 hardening lane if the operator wants that case pinned down.

This is not a functional blocker for V2-2Y because the current behavior is
conservative: invalid age evidence becomes unknown rather than fabricated.

## Safety and Lock Verification

Static inspection and commit scope confirmed V2-2X.2 did not change:

- source registry activation/defaults;
- Source Governor boundaries;
- Central Scheduler boundaries;
- scheduler/runtime;
- discovery runtime defaults;
- memory generation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL paths;
- wallet/private-key/live execution paths;
- paid API dependencies;
- embeddings/vectors.

The implementation remained fixture-first. No live PumpPortal WebSocket, live
HTTP call, Solana RPC call, Helius call, PumpSwap activation, scheduler job,
memory row, retrieval row, paper decision, position, trade event, audit, or PnL
path was introduced.

## Tests and Checks Run

Focused tests:

- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q`
  - `82 passed`
- `python -m pytest tests/test_v2_2h3_field_normalization_fast_events.py -q`
  - `67 passed, 48 subtests passed`
- `python -m pytest tests/test_v2_2p_pair_age_context.py -q`
  - `67 passed`
- `python -m pytest tests/test_v2_2c_selection_batch.py -q`
  - `120 passed`
- `python -m pytest tests/test_v2_2s_selection_cooldown.py -q`
  - `80 passed`
- `python -m pytest tests/test_v2_2v_discovery_persistence_gate_reform.py -q`
  - `45 passed, 42 subtests passed`
- `python -m pytest tests/test_post_rc_controlled_discovery_cycle.py -q`
  - `8 passed`

Total targeted result:

- `469 passed`
- `90 subtests passed`
- `0 failed`

Warnings observed:

- Pytest emitted `PytestCacheWarning` because it could not create the
  `.pytest_cache` nodeids path when it already existed.
- The test harness printed local `gltest` default configuration notices and
  artifact-directory messages.

Static checks/searches:

- `git show --name-only --oneline --no-renames 7eae329`
- `git diff 7eae329^ 7eae329 --name-only`
- `git show --stat --patch --no-ext-diff --unified=20 7eae329 -- src/printer_v1/sources/pumpportal.py src/printer_v1/discovery/parser.py`
- `rg` searches for `supports_network_execution`, `fixture_transport_only`,
  `token_age_evidence_tier`, `pair_age_seconds`, `token_age_seconds`,
  `derive_age_bucket`, A3, recent-active logic, live transport terms, wallet,
  private key, signing, paid, scoring, ranking, confidence, weighted,
  embedding, and vector terms.

One broad `rg` command had a quoting error. It was replaced with smaller
targeted searches that completed successfully and provided the verification
evidence above.

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| Live bounded PumpPortal proof has not run | BLOCKED UNTIL V2-2Y |
| PumpPortal live transport remains paused | INTENTIONAL |
| PumpSwap activation remains paused | INTENTIONAL |
| Solana RPC / Helius T3 enrichment remains unimplemented | BLOCKED |
| V2-3 remains paused | INTENTIONAL |
| V2-4 remains paused | INTENTIONAL |
| Memory generation remains paused | INTENTIONAL |
| Retrieval remains locked | INTENTIONAL |
| Paper decisions remain locked | INTENTIONAL |
| BUY/SELL/HOLD remain locked | INTENTIONAL |
| Positions, trades, audits, and PnL remain locked | INTENTIONAL |

## Whether V2-2Y Is Allowed

V2-2Y is allowed as the next bounded proof lane if the operator approves it.

V2-2Y must remain narrowly scoped to a bounded live T2 proof through existing
Source Governor rules. It must not activate runtime, scheduler expansion,
memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, live execution, wallet/private-key logic, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings, or vectors.

The minor priority-edge coverage note above can be added to V2-2Y acceptance
criteria without reopening V2-2X.2.

## Whether V2-3 Remains Paused

V2-3 remains paused. V2-2X.3 verifies fixture-first T2 behavior only. It does
not close live-source proof, T3 enrichment, or source expansion blockers, and
it does not move the roadmap into memory generation or retrieval work.

## Final Verdict

`VERIFICATION_PASS_WITH_BLOCKERS`

V2-2X.2 correctly implemented fixture-first T2 token-age evidence from
PumpPortal launch events, kept migration events blocked from T2, preserved
pair-age isolation, preserved A3/recent-active token-age requirements, and did
not touch source activation, scheduler/runtime, memory, retrieval, paper, or
financial paths.

## Exact Next Recommended Lane

`V2-2Y - Bounded Live T2 Token-Age Proof`
