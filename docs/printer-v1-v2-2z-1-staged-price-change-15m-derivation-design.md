# Printer V1 V2-2Z.1 Staged Price-Change 15m Derivation Design

Status: DESIGN ONLY

Design verdict: `DESIGN_COMPLETE_WITH_BLOCKERS`

V2-2Z.1 produces a formal contract for deriving `price_change_15m` from two
clean governed price snapshots stored in `printer_token_snapshots`. This is a
design lane only. No source code was changed. No tests were modified. No DB was
migrated or mutated. No live source calls were made. No persistent state was
changed. No paper decisions were created.

## Scope

This lane was strictly scoped to:

- Reading V2-2Z findings and all source-stack evidence already in context
- Answering all 11 design requirements below
- Writing this design document
- Committing this document only

This lane did not implement `staged_derivation.py`, create migrations, mutate
the DB, call live sources, touch the scheduler, generate memory, activate
retrieval, create paper decisions, or touch any financial path.

All pauses established before V2-2Z remain in force: V2-3, V2-4, PumpPortal
live transport, PumpSwap, source expansion, runtime/scheduler, memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, and PnL remain paused.

## Prior Anchors

- V2-2Z readiness review: `f68a853` (doc records `e58db54 (amended)` — this is
  a non-functional documentation mismatch; the actual final commit is
  `f68a853` per `git log --oneline`. The V2-2Z report is not edited in this
  lane.)
- V2-2Y bounded live T2 proof: `e6f5723`

## V2-2Z.1 Design: Staged Price-Change 15m Derivation

### 1. Eligible Snapshot-Pair Criteria

A snapshot pair `(start, end)` is eligible for staged `price_change_15m`
derivation when ALL of the following are true:

**Identity requirements (both snapshots must share identical values):**

- `start.token_id = end.token_id` and both are non-null
- `start.pair_id = end.pair_id` and both are non-null
- `start.source_name = end.source_name` (the source that produced both
  snapshots must be the same; no cross-source mixing)

**Quality requirements (evaluated per snapshot, independently):**

- `source_status = 'COMPLETE'` — the governed source call that produced this
  snapshot returned a complete response
- `data_quality_label = 'CLEAN_DATA'` — the normalized payload passed all
  quality checks at recording time

  Critical note: `snapshot_quality_label` is NOT used as the eligibility gate.
  `classify_snapshot_quality()` returns `PARTIAL_SNAPSHOT` for all current live
  snapshots because `volume_15m` and `txns_15m` are always `None` (no current
  source provides them). Using `snapshot_quality_label` would incorrectly
  exclude every eligible real snapshot. The immutable stored `data_quality_label`
  and `source_status` are the correct eligibility signal because they reflect
  the source response quality at recording time and are not re-evaluated later.

**Price requirements:**

- `start.price_usd` is not `None`
- `end.price_usd` is not `None`
- `start.price_usd > 0` (division protection)

**Timestamp requirements:**

- `start.captured_at` is a valid parseable ISO timestamp
- `end.captured_at` is a valid parseable ISO timestamp
- `start.captured_at < end.captured_at` (strict ordering)

**Interval requirement (see section 2 for bounds):**

- `(end.captured_at − start.captured_at)` falls within the approved tolerance
  band

**Chain requirement:**

- Both snapshots belong to the Solana chain. Because this system is Solana-only
  (per AGENTS.md and the clean master spec), no additional chain filter is
  needed beyond the existing token/pair identity system. If non-Solana pairs
  were ever introduced, a chain check would be required here.

**Staleness handling:**

The stored `snapshot_quality_label` of the start snapshot will be
`PARTIAL_SNAPSHOT`, not `STALE_SNAPSHOT`, at derivation time because all live
snapshots are `PARTIAL_SNAPSHOT` (see quality note above). The immutable
`data_quality_label = CLEAN_DATA` stored at recording time is the correct
durability signal. Derivation code must NOT call `classify_snapshot_quality()`
at derivation time — this would incorrectly flag the ~900s-old start snapshot
as stale and reject it. The tolerance band (section 2) controls the age of the
start snapshot implicitly.

### 2. Tolerance Band

**Target interval:** 900 seconds (15 minutes exactly)

**Accepted range:** 720 – 1080 seconds inclusive

**Tolerance:** ±180 seconds (±3 minutes, ±20% of target)

**Justification:**

- 720s minimum (12 minutes): below this, the computed value is not a
  representative 15-minute momentum signal. A 10-minute window labeled as
  "15m price change" would misrepresent the evidence tier.
- 1080s maximum (18 minutes): above this, the start price is too stale to
  produce honest 15-minute evidence. A 20-minute gap produces "20-minute price
  change" misleadingly labeled as 15m.
- ±180s (±3 minutes) is realistic given governed scheduler latency. Governed
  source requests execute with ~3–5s per batch (confirmed in V2-2K and V2-2Z
  testing logs). Full cycle latency including DB write, quality classification,
  and loop overhead may push actual intervals to 905–915s routinely. The ±3-
  minute band provides headroom without widening the semantic window
  unacceptably.

**Pair selection (when multiple candidates exist):**

When querying `get_snapshots_for_window()` finds more than one eligible end
snapshot for a given start snapshot, prefer the candidate with the smallest
`|interval_seconds − 900|`. If two candidates tie exactly, prefer the later
one (later `captured_at`) to maximize freshness of the end price.

### 3. Derivation Formula

```
price_change_15m = ((price_end - price_start) / price_start) * 100
```

**Convention:**

- Result is a percentage: `+5.0` means +5%, `−3.2` means −3.2%.
- This matches the convention used by `price_change_5m`, `price_change_1h`,
  `price_change_24h` values from GeckoTerminal and DexScreener: those fields
  carry percent values (e.g., `+12.4` for a 12.4% gain) stored as `REAL` in
  `printer_token_snapshots`.

**Precision:**

Round result to 6 decimal places. This matches the float precision used
throughout the snapshot system.

**Rejection guards within the formula:**

- If `price_start is None` or `price_start <= 0`: reject (cannot compute
  denominator)
- If `price_end is None`: reject (cannot compute numerator)
- Do not reject on extreme values (e.g., +1000% or −99%). Memecoins on Solana
  legitimately produce extreme percentage moves within 15 minutes. Extreme
  values are not fabrication — they are honest derivation. The provenance
  record (section 5) preserves the raw start and end prices for audit.

**Positive/negative/zero:**

All three are valid derivation results. `0.0` (unchanged price) is valid and
must not trigger rejection.

### 4. Derived-vs-Native Quality Classification

**Design decision: annotate in `normalized_snapshot_payload_json`, do not add
a new DB column.**

Rationale: adding a new column (`price_change_15m_evidence_kind`) to
`printer_token_snapshots` requires a migration. The existing
`normalized_snapshot_payload_json` column (TEXT, stored per snapshot) can
carry annotation metadata without schema changes.

**Annotation contract:**

When a `price_change_15m` value is written by staged derivation, the
`normalized_snapshot_payload_json` for the **end snapshot** must include:

```json
{
  "price_change_15m_source_kind": "DERIVED_STAGED_SNAPSHOT"
}
```

When `price_change_15m` comes directly from a native source (e.g., a future
GeckoTerminal OHLCV endpoint that provides m15 candles), the annotation should
be:

```json
{
  "price_change_15m_source_kind": "NATIVE_SOURCE"
}
```

When `price_change_15m` is `None` (current live state — no derivation has been
performed), the key is absent from `normalized_snapshot_payload_json`. Absence
means "not yet derived, not natively provided."

**Priority rule:**

Native source data, when available, always supersedes a derived value. A future
source that provides `price_change_15m` directly must write
`"NATIVE_SOURCE"` and must not be overwritten by the staged derivation path.

### 5. Source Trace / Provenance

Every staged derivation must produce a provenance record. This record is stored
in the `normalized_snapshot_payload_json` of the **end snapshot** under the key
`price_change_15m_provenance`. It is a flat dict with the following fields:

| Field | Type | Description |
| --- | --- | --- |
| `derivation_kind` | str | Always `"STAGED_SNAPSHOT_PRICE_CHANGE_15M"` |
| `start_snapshot_id` | int | `printer_token_snapshots.id` of start snapshot |
| `end_snapshot_id` | int | `printer_token_snapshots.id` of end snapshot |
| `token_id` | int | Shared `token_id` of both snapshots |
| `pair_id` | int | Shared `pair_id` of both snapshots |
| `source_name` | str | Shared source name (e.g., `"dexscreener"`) |
| `start_captured_at` | str | ISO timestamp of start snapshot |
| `end_captured_at` | str | ISO timestamp of end snapshot |
| `interval_seconds` | float | `(end_captured_at − start_captured_at)` in seconds |
| `start_price_usd` | float | `price_usd` of start snapshot |
| `end_price_usd` | float | `price_usd` of end snapshot |
| `derived_price_change_15m` | float | Computed result (same value stored in column) |
| `start_data_quality_label` | str | `data_quality_label` of start snapshot |
| `end_data_quality_label` | str | `data_quality_label` of end snapshot |
| `start_source_status` | str | `source_status` of start snapshot |
| `end_source_status` | str | `source_status` of end snapshot |
| `derived_at` | str | ISO UTC timestamp when derivation was computed |

The provenance record must be written atomically with the derived
`price_change_15m` value. A derivation that produces a value without a
provenance record is rejected.

**Storage alternative (implementation note):**

The above design uses `normalized_snapshot_payload_json` as the provenance
carrier to avoid a DB migration in the implementation lane. A cleaner long-term
design would be a dedicated `printer_staged_15m_evidence` table with typed
columns for each provenance field and FKs to `printer_token_snapshots`. That
design is noted here but deferred to a future migration lane. The
JSON-in-payload approach is the approved interim path.

### 6. Rejection Rules

All of the following conditions cause derivation to be rejected. Rejection
means: return `None` (no derivation result), log the rejection reason, write no
`price_change_15m` value, write no provenance record.

| Rejection condition | Reason |
| --- | --- |
| `start.token_id != end.token_id` | Cross-token derivation is invalid |
| `start.pair_id != end.pair_id` | Cross-pair derivation is invalid |
| Either `pair_id` is `None` | Cannot confirm pair identity |
| Either `token_id` is `None` | Cannot confirm token identity |
| `start.source_name != end.source_name` | Cross-source mixing produces uncontrolled comparison |
| Either `source_status != 'COMPLETE'` | Source did not fully deliver data |
| Either `data_quality_label != 'CLEAN_DATA'` | Dirty, stale, partial, conflicting, or missing data |
| Either `price_usd is None` | Cannot compute numerator or denominator |
| `start.price_usd <= 0` | Division by zero or negative-price nonsense |
| Either `captured_at` is `None` | Cannot compute interval |
| Either `captured_at` is unparseable | Cannot compute interval |
| `end.captured_at <= start.captured_at` | End must be strictly after start |
| `interval_seconds < 720` | Interval too short — not representative 15m evidence |
| `interval_seconds > 1080` | Interval too long — exceeds 15m semantic window |
| No eligible end snapshot found for given start | No pair available; derivation not attempted |

The following are also rejections but require special handling:

- If the start snapshot has a stored `snapshot_quality_label` of
  `DIRTY_SNAPSHOT`, `STALE_SNAPSHOT`, `MISSING_CRITICAL_FIELDS`, or
  `CONFLICTING_SNAPSHOT`, reject even if `data_quality_label = CLEAN_DATA`.
  These labels indicate a deeper structural problem discovered at classification
  time. Note: `PARTIAL_SNAPSHOT` is NOT a rejection — it is the expected label
  for all current live snapshots.
- If the end snapshot has any of the above disqualifying `snapshot_quality_label`
  values, reject.

### 7. Volume / Txns Hard Block

`volume_15m` and `txns_15m` remain `None` after staged derivation. There is no
approximation path.

The following derivations are explicitly forbidden — they produce incorrect,
misleading evidence:

| Forbidden approximation | Why |
| --- | --- |
| `volume_15m = volume_5m_start + volume_5m_mid + volume_5m_end` | Rolling 5m windows overlap; sum ≠ 15m aggregate |
| `volume_15m = volume_1h / 4` | 1h window includes 60 minutes, not 15; ratio is wrong |
| `txns_15m = txns_5m × 3` | Rolling txns windows overlap |
| `txns_15m = txns_1h / 4` | Same problem as volume; 1h ÷ 4 is not 15m aggregate |
| Any sum of rolling-window aggregates | Rolling windows are cumulative/rolling, not additive intervals |

`volume_15m = None` and `txns_15m = None` must be preserved on the end
snapshot row even when `price_change_15m` is derived. These are separate
evidence fields that require a native candle source (e.g., GeckoTerminal OHLCV
m15 endpoint) to fill.

A future lane may wire the GeckoTerminal `/networks/{network}/pools/{address}/ohlcv`
endpoint with a `timeframe=minute&aggregate=15` query. That lane must deliver
`volume_15m`, `txns_15m`, and native `price_change_15m` together from the
OHLCV response and must not use the staged derivation path for those values.

### 8. Integration Boundaries

**Existing schema (no changes required):**

- `price_change_15m` column in `printer_token_snapshots`: exists from
  `migrations/001_database_foundation.sql`. Staged derivation writes to this
  column via a targeted `UPDATE` on the end snapshot row after the original
  `INSERT`.
- `SNAPSHOT_INSERT_FIELDS` in `recorder.py`: includes `price_change_15m`.
  Derivation happens post-insert; the column is `NULL` at initial insert and
  filled by derivation afterward.
- `NORMALIZED_FIELDS` in `parser.py`: includes `price_change_15m`. No change.
- `_METADATA_FIELDS` in `selection_batch.py`: includes `price_change_15m`. No
  change.
- `_CRITICAL_FAST_EVENT_FIELDS` in `selection_batch.py`: includes
  `price_change_15m`. No change. When this field is non-null, the field
  completeness counter for fast-event classification will improve.

**Write path:**

1. Normal snapshot lifecycle: source call → normalize → record → quality
   classify → insert to `printer_token_snapshots` with `price_change_15m = NULL`
2. Post-insert: staged derivation module queries the two most recent eligible
   snapshots for the same `(token_id, pair_id, source_name)` triplet
3. If a valid pair is found: compute `price_change_15m`, build provenance dict,
   merge provenance annotation into `normalized_snapshot_payload_json`, write
   both via `UPDATE printer_token_snapshots SET price_change_15m = ?,
   normalized_snapshot_payload_json = ? WHERE id = ?`
4. If no valid pair is found: leave `price_change_15m = NULL`; do not write
   partial provenance

**Read path (unchanged):**

Selection batch, fast-event classification, and any consumer of
`printer_token_snapshots` reads `price_change_15m` as-is. The column value
is either `NULL` (not yet derived or not derivable) or a float (derived or
native). The `normalized_snapshot_payload_json` `price_change_15m_source_kind`
key distinguishes derived from native for audit; no consumer currently requires
this distinction.

**Safety isolation:**

- Populating `price_change_15m` does NOT create memory rows. Memory generation
  has its own gate and is paused.
- Populating `price_change_15m` does NOT activate retrieval. Retrieval is
  paused.
- Populating `price_change_15m` does NOT create paper decisions. Paper decisions
  are paused.
- Populating `price_change_15m` does NOT unlock BUY/SELL/HOLD. Financial paths
  are paused.
- Populating `price_change_15m` does NOT auto-qualify a token for A3. A3 still
  requires non-null `token_age_seconds` from a trusted source. `price_change_15m`
  is a context field for A1/A2 classification, not a gate condition.

### 9. Implementation Handoff

**New file to create (implementation lane):**

`src/printer_v1/snapshots/staged_derivation.py`

Required exports from that module:

```python
DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M = "STAGED_SNAPSHOT_PRICE_CHANGE_15M"

@dataclass
class StagedDerivationResult:
    derived_price_change_15m: float
    provenance: dict

def derive_price_change_15m(
    start_snapshot: dict,
    end_snapshot: dict,
) -> StagedDerivationResult | None:
    """
    Returns StagedDerivationResult if the pair is eligible, otherwise None.
    start_snapshot and end_snapshot are full snapshot row dicts from
    printer_token_snapshots (keyed by column name).
    Does not touch the DB; pure computation.
    """

def find_eligible_snapshot_pairs(
    db_conn,
    token_id: int,
    pair_id: int,
    source_name: str,
    end_snapshot: dict,
    target_interval_seconds: int = 900,
    tolerance_seconds: int = 180,
) -> list[dict]:
    """
    Queries printer_token_snapshots for eligible start snapshots.
    Returns candidates ordered by |interval - target_interval_seconds| ASC.
    Uses get_snapshots_for_window() from recorder.py or equivalent direct query.
    """
```

**Files NOT to change in the implementation lane:**

- `src/printer_v1/memory/` (all memory generation)
- `src/printer_v1/memory_retrieval/` (retrieval)
- `src/printer_v1/paper_decision/` (paper decisions)
- `src/printer_v1/paper_monitor/` (paper monitor)
- `src/printer_v1/paper_audit/` (paper audit)
- `src/printer_v1/discovery/parser.py` (parser normalization paths already
  handle `price_change_15m`)
- `src/printer_v1/discovery/selection_batch.py` (already includes
  `price_change_15m` in `_METADATA_FIELDS` and `_CRITICAL_FAST_EVENT_FIELDS`)
- `src/printer_v1/operator_cli/commands.py`
- `src/printer_v1/sources/` (all source adapters)
- Any existing migration files

**Files that MAY require minor changes in the implementation lane:**

- `src/printer_v1/snapshots/recorder.py`: the `record_snapshot()` call site
  in the governed cycle must be extended to call staged derivation
  post-insert. This requires adding a call to the new module after the
  existing DB insert, within the same connection transaction where possible.

**Optional migration (not required for interim design):**

`027_staged_15m_evidence.sql` — creates a typed `printer_staged_15m_evidence`
table as the long-term home for provenance records. Not required in the
implementation lane. The JSON-in-payload approach (section 5) is sufficient for
the first implementation. This migration is deferred until the operator decides
to harden provenance storage.

### 10. Proof / Test Plan

**New test file:** `tests/test_v2_2z1_staged_15m_price_derivation.py`

The test file must be self-contained. It must use an isolated in-memory or
temp-file SQLite DB. It must not read or write the live DB, call any live
source, generate memory, activate retrieval, or create paper decisions.

**Required test cases (32 total):**

| # | Test name | What it pins |
| --- | --- | --- |
| 1 | `test_valid_900s_interval_produces_correct_result` | Exact 900s, both CLEAN_DATA/COMPLETE, positive change |
| 2 | `test_lower_tolerance_boundary_accepted` | 720s is accepted (not rejected) |
| 3 | `test_upper_tolerance_boundary_accepted` | 1080s is accepted (not rejected) |
| 4 | `test_below_lower_tolerance_rejected` | 719s is rejected |
| 5 | `test_above_upper_tolerance_rejected` | 1081s is rejected |
| 6 | `test_token_id_mismatch_rejected` | Different `token_id` → None |
| 7 | `test_pair_id_mismatch_rejected` | Different `pair_id` → None |
| 8 | `test_source_name_mismatch_rejected` | Different `source_name` → None |
| 9 | `test_null_pair_id_rejected` | Either `pair_id` is None → None |
| 10 | `test_null_token_id_rejected` | Either `token_id` is None → None |
| 11 | `test_dirty_data_label_rejected` | `DIRTY_DATA` → None |
| 12 | `test_stale_data_label_rejected` | `STALE_DATA` → None |
| 13 | `test_acceptable_partial_data_rejected` | `ACCEPTABLE_PARTIAL_DATA` → None (only CLEAN_DATA allowed) |
| 14 | `test_failed_source_status_rejected` | `source_status = FAILED` → None |
| 15 | `test_partial_source_status_rejected` | `source_status = PARTIAL` → None |
| 16 | `test_null_start_price_rejected` | `start.price_usd = None` → None |
| 17 | `test_null_end_price_rejected` | `end.price_usd = None` → None |
| 18 | `test_zero_start_price_rejected` | `start.price_usd = 0` → None |
| 19 | `test_negative_start_price_rejected` | `start.price_usd = -0.001` → None |
| 20 | `test_end_before_start_rejected` | `end.captured_at < start.captured_at` → None |
| 21 | `test_equal_timestamps_rejected` | `end.captured_at = start.captured_at` → None |
| 22 | `test_null_captured_at_rejected` | Either `captured_at = None` → None |
| 23 | `test_formula_positive_price_change` | Price went up; result > 0 |
| 24 | `test_formula_negative_price_change` | Price went down; result < 0 |
| 25 | `test_formula_zero_price_change` | Price unchanged; result == 0.0 |
| 26 | `test_formula_precision_6_decimal_places` | Result rounded to 6 dp |
| 27 | `test_extreme_positive_change_accepted` | +2000% result is not rejected |
| 28 | `test_extreme_negative_change_accepted` | -98% result is not rejected |
| 29 | `test_provenance_all_fields_present` | All 16 provenance keys present in result |
| 30 | `test_volume_15m_remains_none` | `volume_15m` is not set by derivation |
| 31 | `test_txns_15m_remains_none` | `txns_15m` is not set by derivation |
| 32 | `test_closest_eligible_pair_selected` | When multiple candidates exist, smallest |interval - 900| wins |

**Regression suites (implementation lane must run and pass):**

- `tests/test_v2_2h3_field_normalization_fast_events.py` — 15m fields remain
  None from standard sources
- `tests/test_v2_2c_selection_batch.py` — selection and fast-event classification
- `tests/test_v2_2x2_t2_token_age_evidence.py` — T2 token age is unaffected
- `tests/test_v2_2p_pair_age_context.py` — pair-age isolation is unaffected
- `tests/test_post_rc_controlled_discovery_cycle.py` — discovery cycle regression

### 11. Money-Usefulness Contribution

`price_change_15m` from staged derivation provides the following honest
evidence contributions:

**What it adds:**

- 15-minute momentum signal: did the token's price go up or down in the
  15-minute observation window? This is currently a 100%-missing field (V2-2K,
  V2-2Z confirmed).
- Distinguishes momentum profiles: a token with strong `price_change_5m = +40%`
  but `price_change_15m = −5%` shows a fast pump followed by reversal. A token
  with `price_change_5m = +40%` and `price_change_15m = +38%` shows sustained
  momentum. These are meaningfully different fast-event profiles.
- Fills `_CRITICAL_FAST_EVENT_FIELDS` entry for `price_change_15m`: improves
  field completeness for fast-event classification without fabricating evidence.
- Expands diversity across A1/A2 fast-event buckets: A1 (fast-movers) and A2
  (reversal candidates) context is richer when the 15m window is available.

**What it does not add:**

- It does not make trading decisions. BUY/SELL/HOLD remain locked.
- It does not fill `volume_15m` or `txns_15m`. Those require a native candle
  source.
- It does not unlock A3 (still requires `token_age_seconds` from a trusted
  source — missing for most candidates).
- It does not create memory rows. Memory generation is paused.
- It does not activate retrieval. Retrieval is paused.
- It does not create paper decisions. Paper decisions are paused.
- It does not produce scoring, ranking, confidence, or weighted logic.

**Honest limitation:**

The derived `price_change_15m` reflects the price change observed between two
governed snapshots taken roughly 15 minutes apart. It is not a canonical candle
close. Between the two snapshot moments, the price may have spiked and
recovered without being captured. The value is honest evidence of point-to-point
price change at governed observation frequency, not a OHLCV close. This
limitation must be documented in the implementation and test comments.

## Design Blockers

| Blocker | Status | Path to unblock |
| --- | --- | --- |
| `staged_derivation.py` not yet implemented | BLOCKED for production use | Implementation lane (V2-2Z.2 or equivalent) |
| No `UPDATE` call in existing `record_snapshot()` post-insert path | BLOCKED | Implementation lane: extend `record_snapshot()` or add post-insert hook |
| `volume_15m` and `txns_15m` remain None | INTENTIONAL — no native candle source | Future GeckoTerminal OHLCV lane |
| Memory generation remains paused | INTENTIONAL | Operator decision |
| Retrieval remains locked | INTENTIONAL | Operator decision |
| Paper decisions remain locked | INTENTIONAL | Operator decision |
| V2-3 and V2-4 remain paused | INTENTIONAL | Operator decision |

## Design Is Not Implementation

This document defines the contract. Nothing in the codebase has been changed.
The design is complete enough to hand to an implementation lane that can:

1. Create `staged_derivation.py` with the specified exports
2. Extend the post-insert recorder path to call staged derivation
3. Write all 32 test cases
4. Run all regression suites
5. Commit the implementation with a commit scope of:
   - `src/printer_v1/snapshots/staged_derivation.py` (new)
   - `src/printer_v1/snapshots/recorder.py` (minor extension at post-insert
     call site only)
   - `tests/test_v2_2z1_staged_15m_price_derivation.py` (new)

No other files should change in the implementation lane.

## Final Verdict

`DESIGN_COMPLETE_WITH_BLOCKERS`

The staged price-change 15m derivation contract is fully specified. All 11
design requirements are answered. The design is unambiguous about eligibility
criteria (uses `data_quality_label` and `source_status`, not
`snapshot_quality_label`), the tolerance band (720–1080s), the formula
(`((price_end − price_start) / price_start) × 100`), the annotation
strategy (JSON in `normalized_snapshot_payload_json`), the provenance schema
(16 named fields), the rejection rules (15 conditions), the volume/txn hard
block (no rolling-window approximation), the integration boundaries (no
schema changes, UPDATE post-insert), the implementation handoff (new module
only), the proof plan (32 test cases + 5 regression suites), and the
money-usefulness contribution (honest 15m momentum evidence, does not create
trading signals or unblock paused financial paths).

Remaining blockers are implementation gaps, not design gaps. The design is
ready to hand to an implementation lane.

## Git Anchor

V2-2Z.1 commit: (see `git log --oneline` for final hash)
