# Printer V1 V2-2Z.2 Staged Price-Change 15m Derivation Implementation Proof

Status: IMPLEMENTATION AND FIXTURE PROOF

Implementation verdict: `IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS`

V2-2Z.2 implements the staged `price_change_15m` derivation contract from
V2-2Z.1 and proves it with fixture tests. No live source calls were made. No
source code outside the allowed file set was changed. No DB migrations were
added. No memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, or PnL paths were touched.

## Scope

This lane was strictly scoped to:

- Implementing `src/printer_v1/snapshots/staged_derivation.py` (new file)
- Adding a minimal post-insert hook to `src/printer_v1/snapshots/recorder.py`
- Writing `tests/test_v2_2z1_staged_15m_price_derivation.py` (66 tests)
- Writing this proof report
- Running all required test suites

This lane did not implement migrations, touch source adapters, touch the parser,
touch selection batch, call live sources, activate PumpPortal or PumpSwap,
make Solana RPC or Helius calls, start scheduler or runtime execution, generate
memory, activate retrieval, create paper decisions, or touch any financial path.

All pauses remain in force: V2-3, V2-4, PumpPortal live transport, PumpSwap,
source expansion, runtime/scheduler, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

## Source Stack Read

The following source-stack documents were active context:

- `AGENTS.md` (Printer V1 rules confirmed: paper-trading only, Solana only,
  no scoring/ranking/confidence/weighted logic, no live execution)
- `docs/printer-v1-v2-2z-1-staged-price-change-15m-derivation-design.md`
  (V2-2Z.1 design contract, the formal spec for this implementation)
- `docs/printer-v1-v2-2z-staged-native-15m-evidence-readiness-review.md`
  (V2-2Z readiness background)

## Prior Anchors

- V2-2Z.1 design: `5a47ca6` — confirmed present during preflight
- V2-2Z readiness review: `f68a853`
- V2-2Y bounded proof: `e6f5723`
- V2-2X.2 fixture T2 implementation: `7eae329`

## Files Changed

| File | Status | Description |
| --- | --- | --- |
| `src/printer_v1/snapshots/staged_derivation.py` | NEW | Pure derivation module, DB query helper, post-insert hook |
| `src/printer_v1/snapshots/recorder.py` | MODIFIED | +1 import, +3 lines post-insert hook |
| `tests/test_v2_2z1_staged_15m_price_derivation.py` | NEW | 66 fixture tests |
| `docs/printer-v1-v2-2z-2-staged-price-change-15m-derivation-implementation-proof.md` | NEW | This report |

No other files were changed. Verified by `git diff --stat` and `git diff --name-only`.

## `recorder.py` Change (minimal)

The diff is 4 lines:

```diff
+from printer_v1.snapshots.staged_derivation import apply_staged_derivation
...
-        return True, int(cursor.lastrowid)
+        new_id = int(cursor.lastrowid)
+        apply_staged_derivation(connection, new_id, normalized)
+        return True, new_id
```

`apply_staged_derivation` is called within the same `with connect(...)` block as
the INSERT, sharing the same connection/transaction. If derivation succeeds, the
UPDATE and INSERT are committed atomically. If no eligible start snapshot exists,
`apply_staged_derivation` returns False and no UPDATE is issued. The `record_token_snapshot`
return type is unchanged: `tuple[bool, int]`.

## `staged_derivation.py` — Module Structure

### Constant

```python
DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M = "STAGED_SNAPSHOT_PRICE_CHANGE_15M"
```

### Result Type

```python
@dataclass(frozen=True)
class StagedDerivationResult:
    derived_price_change_15m: float
    provenance: dict
```

### Pure Derivation Function

`derive_price_change_15m(start_snapshot, end_snapshot) -> StagedDerivationResult | None`

Accepts Mapping[str, Any] dicts. Performs no DB writes, no source calls, no
memory/retrieval/paper/trading work. Returns None on any rejection.

### DB Query Helper

`find_eligible_snapshot_pairs(db_conn, token_id, pair_id, source_name, end_snapshot, ...)`

Queries `printer_token_snapshots` for start snapshot candidates. Returns
results sorted by `|interval - 900|` ascending, with later `captured_at` as
tie-break. Does not mutate DB.

**Implementation note:** The interval window is computed using Python timedelta
rather than SQLite `julianday()` to avoid timezone-suffix parsing quirks.
`captured_at >= earliest_start AND captured_at <= latest_start` is a string
comparison over ISO 8601 UTC timestamps (all in `+00:00` format), which is
lexicographically correct. Python-side sort applies the proximity ranking.

`source_name` filtering uses `json_extract(normalized_snapshot_payload_json, '$.source_name')`
because `source_name` is carried in the JSON payload, not a dedicated DB column.

### Post-Insert Integration Hook

`apply_staged_derivation(connection, snapshot_id, normalized) -> bool`

Called by `record_token_snapshot` after INSERT. Works within the same connection
transaction. Does not create memory, retrieval, paper decision, or trading rows.
Returns True if an UPDATE was applied, False otherwise.

## Pure Derivation Behavior

### Formula

```
price_change_15m = ((price_end - price_start) / price_start) * 100
```

Rounded to 6 decimal places. Consistent with `price_change_5m`, `price_change_1h`,
`price_change_24h` percentage convention. Positive means price went up.

### Tolerance Band

| Boundary | Value | Behavior |
| --- | --- | --- |
| Target | 900s | Ideal 15-minute interval |
| Minimum | 720s (inclusive) | Accepted |
| Maximum | 1080s (inclusive) | Accepted |
| Below minimum | 719s | Rejected |
| Above maximum | 1081s | Rejected |

### Rejection Rules

All 15 rejection conditions from V2-2Z.1 are enforced:

| Rejection | Reason |
| --- | --- |
| `token_id` mismatch or null | Cross-token derivation invalid |
| `pair_id` mismatch or null | Cross-pair derivation invalid |
| `source_name` mismatch | Cross-source mixing produces uncontrolled comparison |
| Either `source_status != 'COMPLETE'` | Source did not fully deliver data |
| Either `data_quality_label != 'CLEAN_DATA'` | ACCEPTABLE_PARTIAL_DATA, DIRTY_DATA, STALE_DATA, etc. rejected |
| `DIRTY_SNAPSHOT`, `STALE_SNAPSHOT`, `MISSING_CRITICAL_FIELDS`, `CONFLICTING_SNAPSHOT` quality labels | Disqualifying labels at snapshot classification level |
| `PARTIAL_SNAPSHOT` quality label | Explicitly ALLOWED — expected for all current live snapshots |
| Either `price_usd is None` | Cannot compute formula |
| `start.price_usd <= 0` | Division protection |
| Either `captured_at` is None or unparseable | Cannot compute interval |
| `end.captured_at <= start.captured_at` | End must be strictly after start |
| `interval < 720s` | Below tolerance band |
| `interval > 1080s` | Above tolerance band |

Extreme price moves (+1000%, -98%) are NOT rejected — memecoins produce these
legitimately. The formula is applied without a magnitude cap.

## Eligible-Pair Selection Behavior

`find_eligible_snapshot_pairs` queries by:
- `token_id = ?` and `pair_id = ?` (same identity)
- `captured_at` in the acceptable range (string comparison)
- `json_extract(..., '$.source_name') = ?` (if source_name provided)
- `source_status = 'COMPLETE'`
- `data_quality_label = 'CLEAN_DATA'`

Results sorted by `|interval - 900| ASC`, then `-captured_at.timestamp()` as
tie-break (later start wins ties). `apply_staged_derivation` uses the first
candidate and tries `derive_price_change_15m`. If the first candidate fails
the pure derivation check (e.g., disqualifying snapshot_quality_label),
it advances to the next candidate.

## Recorder Integration Behavior

When `record_token_snapshot` is called:

1. Snapshot is normalized via `normalize_snapshot_payload`
2. Quality is classified, labels set
3. `normalized_snapshot_payload_json` serialized (includes `source_name`)
4. Snapshot row is INSERTed; `lastrowid` captured as `new_id`
5. `apply_staged_derivation(connection, new_id, normalized)` is called
6. If a valid start snapshot pair exists, the end snapshot row is UPDATEd:
   - `price_change_15m` column set to the derived float
   - `normalized_snapshot_payload_json` updated with annotation keys

**First snapshot (no prior pair):** `find_eligible_snapshot_pairs` returns [].
`apply_staged_derivation` returns False. `price_change_15m` remains NULL. ✓

**Second snapshot (pair available):** start snapshot found in DB. Derivation
computed. End snapshot UPDATEd. `price_change_15m` populated. ✓

**Start snapshot is not modified:** UPDATE only targets the end snapshot by `id`. ✓

## Provenance Behavior

The `normalized_snapshot_payload_json` of the end snapshot carries two
additional keys after successful derivation:

```json
{
  "price_change_15m_source_kind": "DERIVED_STAGED_SNAPSHOT",
  "price_change_15m_provenance": {
    "derivation_kind": "STAGED_SNAPSHOT_PRICE_CHANGE_15M",
    "start_snapshot_id": <int>,
    "end_snapshot_id": <int>,
    "token_id": <int>,
    "pair_id": <int>,
    "source_name": "<str>",
    "start_captured_at": "<ISO>",
    "end_captured_at": "<ISO>",
    "interval_seconds": <float>,
    "start_price_usd": <float>,
    "end_price_usd": <float>,
    "derived_price_change_15m": <float>,
    "start_data_quality_label": "<str>",
    "end_data_quality_label": "<str>",
    "start_source_status": "<str>",
    "end_source_status": "<str>",
    "derived_at": "<ISO UTC>"
  }
}
```

**Provenance field count:** 17 fields (the V2-2Z.1 design listed 16 + noted
`derived_at` making 17; this implementation preserves all 17). Verified by
test `test_provenance_all_17_fields_present`.

**Native-source protection:** If `price_change_15m_source_kind` is already
`"NATIVE_SOURCE"` in the JSON when `apply_staged_derivation` is called,
derivation is skipped and the existing annotation is preserved.

## Derived-vs-Native Annotation

| Scenario | `price_change_15m_source_kind` |
| --- | --- |
| Staged derivation applied | `"DERIVED_STAGED_SNAPSHOT"` |
| Future native OHLCV source (not implemented) | `"NATIVE_SOURCE"` |
| No derivation (no eligible pair) | Key absent from JSON |

## Volume / Txns 15m Hard-Block Proof

`volume_15m` and `txns_15m` are NOT set by staged derivation. The `UPDATE`
statement writes only `price_change_15m` and `normalized_snapshot_payload_json`.
No approximation (`volume_5m × 3`, `volume_1h / 4`, or any rolling sum) is
computed or stored. Verified by:

- `test_volume_15m_remains_none_after_derivation` — queries the DB column
- `test_txns_15m_remains_none_after_derivation` — queries the DB column
- `test_volume_15m_not_set_by_derivation` — pure function result check
- `test_txns_15m_not_set_by_derivation` — pure function result check

## Fixture vs. Live Distinction

All tests use:
- Isolated temp file SQLite DBs (via `tempfile.TemporaryDirectory` + `apply_migrations`)
- Inline dict payloads (pure function tests require no DB at all)
- No live source calls
- No production DB (`data/` directory untouched)
- `PRAGMA foreign_keys = OFF` for direct-insert tests to avoid FK setup overhead

All recorder integration tests insert real `printer_tokens` and `printer_pairs`
rows via the standard schema and call `record_token_snapshot` normally.

## Tests and Checks Run

### New test suite

```
python -m pytest tests/test_v2_2z1_staged_15m_price_derivation.py -q
66 passed in 29.43s
```

Tests included:

**Pure function tests (A — `TestDerivePrice15mPure`):**
- Valid 900s derivation produces result
- Positive, negative, zero price change formula
- 6 decimal place precision
- 720s lower boundary accepted
- 1080s upper boundary accepted
- 719s below lower boundary rejected
- 1081s above upper boundary rejected
- Token/pair/source mismatch rejected
- Null pair_id start/end rejected
- Null token_id start/end rejected
- DIRTY_DATA, STALE_DATA, ACCEPTABLE_PARTIAL_DATA rejected
- FAILED, PARTIAL source_status rejected
- DIRTY_SNAPSHOT, STALE_SNAPSHOT, MISSING_CRITICAL_FIELDS, CONFLICTING_SNAPSHOT rejected
- PARTIAL_SNAPSHOT explicitly allowed
- Null start/end price rejected
- Zero start price rejected
- Negative start price rejected
- End before start rejected
- Equal timestamps rejected
- Null captured_at (start/end) rejected
- Extreme positive (+2000%) accepted
- Extreme negative (-98%) accepted
- All 17 provenance fields present
- Provenance derivation_kind constant correct
- Provenance interval_seconds correct
- Provenance prices preserved
- volume_15m not set by derivation
- txns_15m not set by derivation

**DB query tests (B — `TestFindEligiblePairs`):**
- Empty when no candidates
- Returns 900s candidate
- Excludes outside-tolerance candidate
- Excludes dirty-data candidate
- Excludes failed-source-status candidate
- Excludes wrong source_name
- Closest pair (850s) selected first from 730/850/1050 candidates
- Tie-break: later captured_at wins (720s beats 1080s)
- Empty when end captured_at is None

**Recorder integration tests (C — `TestApplyStagedDerivation`):**
- First snapshot has no derivation (price_change_15m = None)
- End snapshot gets derivation (price_change_15m populated)
- Annotation in normalized_snapshot_payload_json
- All 17 provenance fields in JSON
- Update writes to end snapshot only (start unchanged)
- volume_15m remains None after derivation
- txns_15m remains None after derivation
- NATIVE_SOURCE annotation not overwritten
- No printer_memory_windows rows created
- No printer_paper_decisions rows created
- Interval outside tolerance produces no derivation
- Duplicate snapshot skipped without crash

**Module constants (D — `TestModuleConstants`):**
- Constant value correct
- StagedDerivationResult is dataclass
- StagedDerivationResult is frozen

### Regression suites

```
python -m pytest tests/test_v2_2h3_field_normalization_fast_events.py \
    tests/test_v2_2c_selection_batch.py \
    tests/test_v2_2x2_t2_token_age_evidence.py \
    tests/test_v2_2p_pair_age_context.py \
    tests/test_post_rc_controlled_discovery_cycle.py -q

344 passed, 48 subtests passed in 108.46s
```

0 failures. All pre-existing regression suites pass.

### Safety checks

```
git diff --check       → no whitespace errors
git diff --stat        → recorder.py: 4 insertions(+), 1 deletion(-)
git diff --name-only   → src/printer_v1/snapshots/recorder.py (only tracked change)
```

Untracked new files:
- `src/printer_v1/snapshots/staged_derivation.py`
- `tests/test_v2_2z1_staged_15m_price_derivation.py`

No source adapters, no parser, no selection batch, no migrations, no memory/
retrieval/paper/trading files changed.

## Safety Confirmations

| Check | Result |
| --- | --- |
| No live source calls | CONFIRMED — pure Python, no HTTP/WebSocket |
| No memory generation | CONFIRMED — no printer_memory_windows rows created (test) |
| No retrieval | CONFIRMED — no retrieval module imported or called |
| No paper decisions | CONFIRMED — no printer_paper_decisions rows created (test) |
| No BUY/SELL/HOLD signals | CONFIRMED — no financial action anywhere |
| No positions/trades/audits/PnL | CONFIRMED — not touched |
| No scoring/ranking/confidence/weighted logic | CONFIRMED — not present in module |
| No embeddings/vectors | CONFIRMED — not present in module |
| volume_15m not derived | CONFIRMED — hard block enforced; column remains NULL |
| txns_15m not derived | CONFIRMED — hard block enforced; column remains NULL |
| No DB migration added | CONFIRMED — JSON-in-payload approach per V2-2Z.1 design |
| No paid API dependencies | CONFIRMED |
| No private keys/wallet | CONFIRMED |
| Start snapshot not modified | CONFIRMED — UPDATE targets end snapshot id only |
| No other production files changed | CONFIRMED — git diff shows recorder.py only |

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| `volume_15m` remains None | INTENTIONAL — requires native OHLCV candle source |
| `txns_15m` remains None | INTENTIONAL — requires native OHLCV candle source |
| GeckoTerminal OHLCV m15 endpoint not wired | BLOCKED — future lane |
| Long-term provenance table (`printer_staged_15m_evidence`) not created | INTENTIONAL — JSON-in-payload is interim; migration deferred per V2-2Z.1 |
| Memory generation remains paused | INTENTIONAL |
| Retrieval remains locked | INTENTIONAL |
| Paper decisions remain locked | INTENTIONAL |
| BUY/SELL/HOLD remain locked | INTENTIONAL |
| Positions, trades, audits, and PnL remain locked | INTENTIONAL |
| V2-3 remains paused | INTENTIONAL |
| V2-4 remains paused | INTENTIONAL |

## Whether V2-3 Remains Paused

**YES. V2-3 remains paused.**

V2-2Z.2 populates `price_change_15m` from staged snapshot derivation. This does
not unblock V2-3. V2-3 requires operator approval and memory generation,
retrieval, and paper decision infrastructure that remains locked. Filling
`price_change_15m` is a prerequisite quality improvement for richer memory
fingerprints, not an authorization to proceed to V2-3.

## Exact Next Recommended Lane

`V2-2Z.3 — Staged 15m Derivation Coverage Audit`

Objective: run a bounded audit against the existing operator DB to measure what
fraction of live snapshots now have `price_change_15m` populated from staged
derivation vs. still None. Answer: how many token/pair observations have
eligible pairs at 900±180s spacing? What is the current fill rate? Document the
evidence and blockers. No new derivation code. No new source calls. Audit only.

Alternatively, if the operator prefers to wire native OHLCV:

`V2-2AA — GeckoTerminal OHLCV 15m Native Source Integration`

Objective: wire the GeckoTerminal `/networks/{network}/pools/{address}/ohlcv`
endpoint with `timeframe=minute&aggregate=15` to populate `price_change_15m`,
`volume_15m`, and `txns_15m` natively. This would supersede staged derivation
for tokens with sufficient GeckoTerminal coverage.

## Final Verdict

`IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS`

`staged_derivation.py` is implemented, tested, and integrated into
`record_token_snapshot`. All 66 fixture tests pass. All 5 regression suites
pass (344 tests, 48 subtests). The implementation matches the V2-2Z.1 design
contract exactly: correct eligibility criteria, tolerance band, formula,
provenance, rejection rules, volume/txn hard block, annotation approach, and
integration boundary. Remaining blockers are intentional scope limits
(volume_15m/txns_15m require native OHLCV, provenance table deferred) and
paused financial paths.

## Executor

Executor: Claude (claude-sonnet-4-6)

## Git Anchor

V2-2Z.2 commit: (see `git log --oneline` for final hash)
