# Printer V1 V2-2X.2 T2 Token-Age Evidence Implementation and Fixture Proof

Status: `IMPLEMENTATION + FIXTURE PROOF`

Proof verdict: `IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS`

V2-2Y, V2-3, live PumpPortal runtime, Solana RPC enrichment, source expansion,
memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, and PnL remain paused.

This lane implemented T2 token-age evidence extraction from PumpPortal launch
events and proved the implementation with deterministic fixture tests. It did not
run live discovery, fetch from live sources, mutate the persistent database,
generate memory, activate retrieval, create paper decisions, authorize
BUY/SELL/HOLD, open positions, create trades, create paper trade audits, or
create PnL.

No scoring, ranking, confidence percentage, weighted logic, embeddings, vectors,
wallet, private-key, real-fund, or live-execution behavior was introduced.

## 1. Source Stack and Anchors

The implementation used these documents together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md`
- `docs/printer-v1-v2-2o-token-age-evidence-repair-design.md`
- `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md`
- `docs/printer-v1-v2-2x-token-age-evidence-source-readiness-review.md`
- `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md`

Anchors:

- V2-2J closeout: `c6f002a`
- V2-2X.1 design: `35b9356`

## 2. Files Changed

```text
src/printer_v1/sources/pumpportal.py  — T2 timestamp extraction helpers
src/printer_v1/discovery/parser.py    — T2 tier stamping
tests/test_v2_2x2_t2_token_age_evidence.py  — fixture proof (new file)
docs/printer-v1-v2-2x-2-t2-token-age-evidence-implementation-fixture-proof.md (this file)
```

No other files were changed. No DB migrations were added. No new DB tables,
columns, or schema changes were required.

## 3. Implementation: `pumpportal.py`

### 3.1 New constant

```python
_PUMPPORTAL_LAUNCH_STALENESS_THRESHOLD_SECONDS = 3600.0
```

### 3.2 New helper: `_parse_event_ts(value)`

Parses a PumpPortal event timestamp field to UTC `datetime`, or `None` if
invalid. Handles:

- `None`, `""`, `0`, negative int/float → `None`
- Int/float: if `> 1e10` treats as milliseconds, else as seconds since epoch
- ISO-8601 string (with Z or +00:00)
- All other types → `None`

### 3.3 New helper: `_extract_launch_timestamp(event, observation_iso)`

Extracts and validates the token creation timestamp from a
`pumpfun_launch_stream` event.

Priority order for field selection (first non-empty value wins):
1. `event["tokenCreatedAt"]`
2. `event["createdTimestamp"]`
3. `event["timestamp"]`

Validation rules (rejects any failure):
- Field must be present and non-empty
- Must parse as a valid datetime
- Must not be in the future relative to `observation_iso`
- Must not be stale: staleness `= (obs_dt - event_dt).total_seconds()` must be
  `<= _PUMPPORTAL_LAUNCH_STALENESS_THRESHOLD_SECONDS` (3600.0)

Staleness boundary: `staleness > 3600.0` is rejected; `staleness == 3600.0`
is accepted (strict `>` check).

Returns: ISO-8601 UTC string if valid, `None` otherwise.

Must NOT be called for `pumpfun_migration_stream` events.

### 3.4 Modified: `_normalize_pumpportal_event(event, request_kind)`

Added to returned dict:

- `"request_kind": request_kind` — carries the stream kind downstream to the
  parser for T2 tier stamping
- `"token_created_at": token_created_at` — ISO string for launch events with
  valid timestamps; `None` for migration events and invalid/missing timestamps

For `pumpfun_launch_stream`:
- Computes `_observation_ref = event.get("captured_at") or _current_iso()`
- Calls `_extract_launch_timestamp(event, _observation_ref)`
- Sets `token_created_at` to result (may be `None`)

For `pumpfun_migration_stream`:
- Does NOT call `_extract_launch_timestamp`
- `token_created_at` remains `None` (hard block: migration time ≠ creation time)

The `captured_at` field in the returned dict is unchanged from prior behavior.

## 4. Implementation: `parser.py`

### 4.1 New helper: `_derive_token_age_evidence_tier(...)`

```python
def _derive_token_age_evidence_tier(
    source_name: str,
    candidate_payload: Mapping[str, Any],
    token_created_at_raw: Any,
    token_age_seconds: float | None,
) -> str | None:
```

Returns `"T2"` only when all four conditions hold:
1. `source_name == "pumpportal"`
2. `candidate_payload.get("request_kind") == "pumpfun_launch_stream"`
3. `token_created_at_raw is not None`
4. `token_age_seconds is not None`

All other cases return `None` (T5 unknown). Migration events always return
`None` because they do not set `token_created_at` in `pumpportal.py`.

### 4.2 Modified: `normalize_candidate()`

Replaced the single hardcoded `None`:

```python
# Before
"token_age_evidence_tier": None,

# After
"token_age_evidence_tier": _derive_token_age_evidence_tier(
    source_name,
    candidate_payload,
    _token_created_at_raw,
    _safe_age_seconds(_token_created_at_raw, _now),
),
```

This is the only functional change in `parser.py`. All other parser behavior
is unchanged.

### 4.3 Parser data flow for T2

The full T2 data flow through the parser:

1. `_token_created_at_raw = first_present(candidate_payload, attributes, keys=("token_created_at", "tokenCreatedAt"))` — reads `token_created_at` from the PumpPortal token dict
2. `"token_created_at": str(_token_created_at_raw) if _token_created_at_raw is not None else None` — stored as ISO string
3. `"token_age_seconds": _safe_age_seconds(_token_created_at_raw, _now)` — derived age in seconds at normalization time
4. `"token_age_evidence_tier": _derive_token_age_evidence_tier(...)` — `"T2"` when all conditions met

Steps 1–3 were already present in the parser before V2-2X.2. Only step 4
changed.

## 5. No DB Migration

No migration was added. Fields `token_created_at`, `token_age_seconds`,
`token_age_evidence_tier`, and `pair_age_context_label` were already in
`NORMALIZED_FIELDS` and `_METADATA_FIELDS`. The implementation required no
schema changes.

## 6. Fixture Proof: Tests Written

Test file: `tests/test_v2_2x2_t2_token_age_evidence.py`

| Group | Focus | Count |
|---|---|---|
| A. TestParseEventTs | `_parse_event_ts` unit tests | 12 |
| B. TestExtractLaunchTimestamp | `_extract_launch_timestamp` unit tests | 13 |
| C. TestT2TimestampMapping | Full pipeline priority field mapping | 8 |
| D. TestT2InvalidTimestamps | Invalid timestamp rejection | 9 |
| E. TestMigrationHardBlock | Migration events never get T2 | 6 |
| F. TestPairAgeIsolation | Pair age never assigned to token age or gates | 7 |
| G. TestA3Behavior | A3 with and without T2 evidence | 5 |
| H. TestMetadataSurvival | Tier and context label survive to metadata | 12 |
| I. TestSafety | No live calls, pure-function properties | 10 |

**Total: 82 tests, 82 passed**

## 7. Test Results

### 7.1 New test suite

```text
python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -v
82 passed in 0.16s
```

### 7.2 Regression suites

```text
python -m pytest tests/test_v2_2h3_field_normalization_fast_events.py tests/test_v2_2p_pair_age_context.py tests/test_v2_2c_selection_batch.py -q
254 passed, 48 subtests passed in 84.19s

python -m pytest tests/test_v2_2s_selection_cooldown.py tests/test_v2_2v_discovery_persistence_gate_reform.py tests/test_post_rc_controlled_discovery_cycle.py -q
133 passed, 42 subtests passed in 134.04s
```

### 7.3 Total targeted result

```text
469 passed
90 subtests passed
0 failed
```

## 8. Key Proof Findings

### 8.1 T2 priority mapping

Priority order is enforced:
- If `tokenCreatedAt` is present and valid, it is used exclusively.
- If `tokenCreatedAt` is absent or invalid, `createdTimestamp` is tried.
- If neither is present, `timestamp` is tried last.
- Once the first present field is found, it is either accepted or rejected
  (no fallthrough to a lower-priority field on rejection).

All three fields produce valid `token_age_evidence_tier = "T2"` and correct
`token_age_seconds` derivation from the parser.

### 8.2 Staleness boundary

- `staleness = 3600.0s` exactly → accepted (boundary case; `> 3600.0` is False)
- `staleness = 3601.0s` → rejected
- `staleness = 0s` (event has just been captured) → accepted
- future timestamps → rejected

### 8.3 Migration hard block

`pumpfun_migration_stream` events:
- `_extract_launch_timestamp` is never called
- `token_created_at` is never set in the normalized token dict
- `token_age_seconds` remains `None` in the parser output
- `token_age_evidence_tier` remains `None`
- Migration pair address is still correctly extracted

Even if a migration event carries `timestamp`, `tokenCreatedAt`, or
`createdTimestamp` fields, none of them produce T2 evidence.

### 8.4 Pair-age isolation

- `pair_age_seconds` is present for candidates with `pair_created_at`
- `token_age_seconds` is `None` when `token_created_at` is absent
- `pair_age_seconds` is NOT copied to `token_age_seconds`
- `derive_age_bucket` returns `AGE_UNKNOWN` when `token_age_seconds is None`
- `derive_recent_active_tier(AGE_UNKNOWN, ACTIVITY_HIGH)` returns `UNKNOWN_TIER_5`
- A3 is not assigned when `token_age_seconds is None` (even with negative `price_change_1h`)

### 8.5 A3 behavior with T2 evidence

A3 fires correctly when:
- Fast tier: `liquidity >= 5000`, `volume_5m >= 1000` (or `txns_5m >= 10`)
- `_tok_age_known`: `token_age_seconds is not None` (requires T2 evidence)
- `_pc1h_known`: `price_change_1h is not None`
- `token_age >= 3600.0`
- `price_change_1h < 0`

A3 is blocked when any of these conditions is absent.

Young T2 token (age = 120s) with fast tier + negative `price_change_1h` →
A1, not A3 (token_age < 3600s threshold).

Old T2 token (age = 10800s, captured freshly 60s after creation) with fast
tier + negative `price_change_1h` → A3 correctly.

### 8.6 Metadata survival

Both `token_age_evidence_tier` and `pair_age_context_label` are in
`NORMALIZED_FIELDS` and `_METADATA_FIELDS`. They survive through
`extract_candidate_metadata()`. The `"T2"` tier value flows correctly.

`request_kind` is NOT in `NORMALIZED_FIELDS` and does not appear in the final
normalized candidate dict.

### 8.7 Safety

- `PumpPortalAdapter.metadata.fixture_transport_only == True`
- `PumpPortalAdapter.metadata.supports_network_execution == False`
- `normalize_pumpportal_payload` is a pure function (no network, no DB, no IO)
- `normalize_candidate` is a pure function (no network, no DB, no IO)
- No `SourceAdapterContext` was constructed in V2-2X.2 tests (no DB writes to
  `printer_source_requests`, `printer_source_responses`, or `printer_source_failures`)
- No scheduler jobs, memory windows, retrieval rows, paper decisions, positions,
  trade events, audits, or PnL rows were created

## 9. Fixture vs Live Distinction

This was a deterministic fixture proof only.

All tests use injected fixture event dicts, `_FIXED_NOW` as a deterministic
normalization reference time, and `_FIXED_NOW_ISO` as the injected `captured_at`
observation reference.

No live PumpPortal WebSocket connection was established. No live HTTP request
was made. The PumpPortal adapter remains `fixture_transport_only = True` and
`enabled = False` by default.

The persistent database at `data/printer_v1.sqlite3` was not touched.

## 10. Regression Safety

All 6 required regression suites pass with zero failures:

- `test_v2_2h3_field_normalization_fast_events.py`: existing A1/A2/A3/A4 and
  field normalization behavior is unchanged for GeckoTerminal/DexScreener sources
- `test_v2_2p_pair_age_context.py`: pair-age labels, `token_age_evidence_tier`,
  and A3 safety from pair age are unchanged
- `test_v2_2c_selection_batch.py`: bucket assignment, age buckets, and
  activity buckets are unchanged
- `test_v2_2s_selection_cooldown.py`: selection cooldown logic is unchanged
- `test_v2_2v_discovery_persistence_gate_reform.py`: Tier 1 and Tier 2
  discovery gates are unchanged
- `test_post_rc_controlled_discovery_cycle.py`: full controlled discovery
  cycle behavior is unchanged

The `token_age_evidence_tier` field now returns `None` for all GeckoTerminal
and DexScreener candidates (because `source_name != "pumpportal"`), which
matches the prior hardcoded `None` behavior exactly.

## 11. Git Checks

```text
git diff --check
  CRLF warnings only (non-failing, pre-existing repo line-ending policy)
  No whitespace errors

git status --short
  M src/printer_v1/discovery/parser.py
  M src/printer_v1/sources/pumpportal.py
  ?? tests/test_v2_2x2_t2_token_age_evidence.py
  [untracked: data/, operator-runs/, lane output txt files — all pre-existing]

git diff --stat
  src/printer_v1/discovery/parser.py   | 33 ++++++++++++--
  src/printer_v1/sources/pumpportal.py | 74 ++++++++++++++++++++++++++++++++
  2 files changed, 103 insertions(+), 4 deletions(-)

git diff --name-only
  src/printer_v1/discovery/parser.py
  src/printer_v1/sources/pumpportal.py
```

## 12. Remaining Blockers

The following blockers are unchanged from V2-2X and V2-2X.1:

| Blocker | Status | Impact |
|---|---|---|
| PumpPortal live source not active | CONFIRMED | T2 works in fixture proof only; live proof requires a bounded governed collection lane |
| A3 requires fast-tier candidates | CONFIRMED | Fast-tier candidates are not common in current GeckoTerminal/DexScreener live data |
| Solana RPC / Helius T3 not implemented | CONFIRMED | T3 remains future work |
| V2-3 paused | CONFIRMED | Blocked pending V2-2 closeout acceptance |
| Source expansion paused | CONFIRMED | PumpPortal/PumpSwap runtime not started |

New T2-specific observation:

- PumpPortal raw launch events do not carry `volume_5m`, `txns_5m`, or
  `price_change_*` fields. A3 requires fast-tier conditions (liquidity +
  volume/txns) that can only be confirmed from a secondary enrichment source
  or from a combined launch + trading-stats payload shape. The T2 timestamp
  extraction is correct, but reaching A3 from T2 evidence alone requires the
  candidate to also satisfy the fast-tier gate from additional market data.

## 13. Safety Confirmations

Confirmed:

- No live discovery run.
- No live source fetching run.
- No Source Governor bypass.
- No Central Scheduler bypass.
- No scheduler/runtime job created.
- No memory generation.
- No memory window creation.
- No retrieval activation.
- No paper decision creation.
- No BUY/SELL/HOLD unlock.
- No paper position creation.
- No trade, paper audit, or PnL creation.
- No wallet, private-key, real-fund, signing, or live-execution logic.
- No paid API dependency.
- No scoring, ranking, confidence, or weighted logic.
- No embeddings or vectors.
- No pair age assigned to token age.
- Pair age does not drive `derive_age_bucket`.
- Pair age does not unlock A3.
- Pair age does not unlock recent-active tiers.
- `derive_age_bucket` still reads only `token_age_seconds`.
- `captured_at` was not used as `token_created_at`.
- Migration events do not produce T2 evidence.
- `token_age_evidence_tier` is `None` for all non-PumpPortal sources.

## 14. Final Verdict

```text
IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS

TESTS_PASS: YES (82 new + 387 regression = 469 total, 0 failed)
LIVE_DB_MUTATED: NO
LIVE_DISCOVERY_RUN: NO
SOURCE_FETCHING_RUN: NO
SCHEDULER_RUNTIME_RUN: NO
MEMORY_GENERATION_RUN: NO
RETRIEVAL_ACTIVATED: NO
PAPER_DECISIONS_CREATED: NO
BUY_SELL_HOLD_UNLOCKED: NO
POSITIONS_TRADES_AUDITS_PNL_CREATED: NO
DB_MIGRATION_ADDED: NO
FILES_CHANGED: 2 (pumpportal.py, parser.py)
FILES_ADDED: 2 (test_v2_2x2_t2_token_age_evidence.py, this doc)
PAIR_AGE_USED_AS_TOKEN_AGE: NO
MIGRATION_EVENTS_GET_T2: NO
NEXT_RECOMMENDED_LANE: V2-2Y (live bounded T2 proof) or V2-3 design-only (operator decision)
```
