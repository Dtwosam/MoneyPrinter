# Printer V1 V2-2S Cross-Batch Selection Cooldown Implementation

## 1. Executor

Claude Sonnet 4.6 — paper-trading-only, Solana-only system.
No live discovery, source fetching, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallet access, or live execution.

## 2. Source Anchor

- V2-2R design document: `docs/printer-v1-v2-2r-discovery-fair-chance-selection-rotation-design.md`
- V2-2R commit: `a1257a0`

## 3. Files Changed

| File | Change |
|---|---|
| `migrations/026_selection_rotation_state.sql` | New migration — rotation state table and indexes |
| `src/printer_v1/discovery/selection_batch.py` | New rejection constants, 6 new functions, `persist_selection_batch()` wiring |
| `tests/test_v2_2s_selection_cooldown.py` | New focused test suite — 61 tests |
| `docs/printer-v1-v2-2s-cross-batch-selection-cooldown-implementation.md` | This document |

No migration, memory, retrieval, paper-decision, position, trade, audit, or
PnL file changed.

## 4. Behavior Added

### 4.1 Migration 026

`printer_selection_rotation_state` table with columns:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `token_mint` | TEXT NOT NULL | |
| `pair_address` | TEXT NOT NULL | |
| `last_selected_batch_id` | TEXT | batch_id from printer_selection_batches |
| `last_selected_batch_seq` | INTEGER | rowid from printer_selection_batches |
| `last_selected_at` | TEXT | ISO-8601 UTC |
| `last_evidence_fingerprint_json` | TEXT | 4-field categorical fingerprint |
| `selection_count` | INTEGER NOT NULL DEFAULT 0 | increments on each upsert |
| `created_at` | TEXT NOT NULL | |
| `updated_at` | TEXT NOT NULL | |

Unique constraint on `(token_mint, pair_address)`.
Indexes on `token_mint` and `pair_address` individually.

### 4.2 Rejection constants (V2-2S)

```python
REJECTION_TOKEN_SELECTION_COOLDOWN = "TOKEN_SELECTION_COOLDOWN"
REJECTION_PAIR_SELECTION_COOLDOWN  = "PAIR_SELECTION_COOLDOWN"
```

Both are categorical string constants. Not scores, not ranks.

### 4.3 `_bucket_group(bucket_id) -> str | None`

Internal helper. Maps a bucket_id to its group letter (A/B/C/D/E/F) using
the existing frozenset constants. Returns `None` for unrecognized values.
Used by `fingerprint_change_is_meaningful()` for cross-group boundary detection.

### 4.4 `compute_evidence_identity_fingerprint(candidate) -> dict`

Returns a 4-field categorical fingerprint:

| Field | Source |
|---|---|
| `activity_bucket` | `derive_activity_bucket(candidate)` |
| `pair_age_context_label` | `candidate.get("pair_age_context_label")` |
| `source_channel` | `candidate.get("source_channel")` |
| `primary_bucket` | `candidate.get("primary_bucket")` |

No scores, no floats in the fingerprint. Does not mutate the candidate.
`token_age_seconds` and `pair_age_seconds` are not in the fingerprint.

### 4.5 `fingerprint_change_is_meaningful(old_fp, new_fp) -> bool`

Returns `True` when evidence changed enough to be considered distinct evidence,
per V2-2R Section 5.2:

- `activity_bucket` changed → meaningful
- `source_channel` changed → meaningful
- `primary_bucket` changed AND crossed a group boundary → meaningful

Not meaningful:
- Only `pair_age_context_label` changed (pair age grows naturally)
- `primary_bucket` changed within the same group (e.g. A1 → A2)

### 4.6 `check_token_selection_cooldown(db_or_connection, token_mint, current_batch_seq, *, cooldown_window=3) -> tuple[bool, str]`

Looks up the last selected batch seq for `token_mint` in
`printer_selection_rotation_state`. Returns `(False, REJECTION_TOKEN_SELECTION_COOLDOWN)`
when `batches_since < cooldown_window` (strict less-than).

Cooldown proof (window=3):

| Batch | batches_since | Result |
|---|---|---|
| seq 2 (after selection at seq 1) | 2−1 = 1 | 1 < 3 → BLOCKED |
| seq 3 | 3−1 = 2 | 2 < 3 → BLOCKED |
| seq 4 | 4−1 = 3 | 3 < 3 = False → ALLOWED |

Matches V2-2R Proof 1.

### 4.7 `check_pair_selection_cooldown(db_or_connection, pair_address, current_batch_seq, *, cooldown_window=3) -> tuple[bool, str]`

Same semantics as token cooldown but keyed on `pair_address`. Uses
`ORDER BY last_selected_batch_seq DESC LIMIT 1` to get the most recent
selection for that pair. Token and pair cooldowns are independent.

### 4.8 `record_selection_rotation_state(db_or_connection, items, batch_id, batch_seq) -> int`

Upserts one row per `SELECTED` item in `printer_selection_rotation_state`.
Uses `INSERT ... ON CONFLICT(token_mint, pair_address) DO UPDATE SET ...`
to increment `selection_count` on reselection. Items missing `token_mint`
or `pair_address` are skipped. Returns the number of rows upserted.

Fingerprint is computed by reconstructing a candidate snapshot from:
- `candidate_metadata_json` (parsed JSON — contains liquidity, volume, pair_age_context_label, etc.)
- `primary_bucket` from the item directly
- `source_channel` from the item directly

### 4.9 `persist_selection_batch()` wiring

After the batch header INSERT:
- Captures `last_insert_rowid()` as `_batch_rowid` (monotonically increasing; used as `batch_seq`)

After all item INSERTs:
- Checks if `printer_selection_rotation_state` exists in `sqlite_master` (backward-compatible)
- If yes: calls `record_selection_rotation_state(conn, items, _batch_id, _batch_rowid)`
- Return dict now includes `rotation_state_recorded: bool`

All existing `persist_selection_batch()` tests use `_make_db()` which applies
ALL migrations including 026, so the rotation state table is always present
in test DBs.

## 5. Tests Run

### V2-2S focused suite

```
tests/test_v2_2s_selection_cooldown.py — 61 passed
```

Test classes and coverage:

| Class | Tests | Coverage |
|---|---|---|
| `TestTokenSelectionCooldown` | 8 | Blocked at 2+3, allowed at 4, independent mints, custom window, window=1, return type |
| `TestPairSelectionCooldown` | 7 | Blocked, allowed after window, new pair free, token+pair independence, return type |
| `TestEvidenceIdentityFingerprint` | 10 | 4-field structure, no floats, no age fields, activity bucket, source/bucket/label fields, None-safe, no mutation |
| `TestFingerprintChangeMeaningful` | 10 | Identical not meaningful, activity change, source change, cross-group, within-group, pair-age-only not meaningful, two unknown buckets, activity override |
| `TestRecordSelectionRotationState` | 10 | Selected written, rejected not written, count starts at 1, count increments, batch ID updated, fingerprint JSON, skip empty mint/pair, empty list, multi-item |
| `TestPersistSelectionBatchRotationStateWiring` | 7 | Rotation written via persist, return field present, rejected not written, count increment via persist, seq increases, cooldown blocked after persist, cooldown allowed after window |
| `TestRotationStateSafety` | 9 | Constants are strings, constants distinct, no numeric score in fingerprint, no paper decisions, token age not modified, pair age not written to token age, fields categorical, no tracking table mutation, table separation |

### Regression suites

| Test suite | Result |
|---|---|
| `tests/test_v2_2s_selection_cooldown.py` | 61 passed |
| `tests/test_v2_2c_selection_batch.py` | 120 passed |
| `tests/test_v2_2p_pair_age_context.py` | 67 passed |
| `tests/test_v2_2m_audit_only_handoff.py` | 95 passed |
| `tests/test_post_rc_controlled_discovery_cycle.py` | 8 passed |

**Total: 351 tests passed.**

## 6. Git Checks

- `git diff --check`: LF→CRLF line-ending warning only (Windows git config). No whitespace errors.
- `git status --short`: 1 modified file + 2 new untracked files (intended)
- `git diff --name-only`: `src/printer_v1/discovery/selection_batch.py`
- Untracked: `migrations/026_selection_rotation_state.sql`, `tests/test_v2_2s_selection_cooldown.py`

No stray changes.

## 7. Safety Confirmations

- No live discovery, source fetching, memory generation, or retrieval path changed.
- No paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL path changed.
- `pair_age_seconds` is not written to `token_age_seconds` anywhere in new code.
- A3 gate (`_tok_age_known`) is not touched.
- `token_age_evidence_tier` remains `None` — no T1/T2/T3 source activated.
- WATCH_ONLY promotion gate is not touched.
- D1/dead token behavior is not changed.
- No scoring, ranking, confidence, or weighted logic added.
- No embeddings or vectors added.
- Fingerprint contains only categorical string fields (4 fixed keys).
- `persist_selection_batch()` backward-compatible: rotation state call is guarded
  by table-existence check; old DBs without migration 026 are unaffected.
- All new functions accept `db_or_connection` and use `_connect()` pattern.
- V2-2J, V2-3, V2-2Q, V2-2S.1 verification remain paused/not activated.

## 8. Verdict

`IMPLEMENTATION_COMPLETE_WITH_BLOCKERS`

Implementation complete: migration 026, two rejection constants, 6 new functions,
`persist_selection_batch()` wiring, 61 focused tests, 351 total tests passing.

Blockers (pre-existing, not introduced by V2-2S):

1. `token_age_seconds` is unavailable until a T1/T2/T3 source is separately
   approved and activated. A3 and recent-active tiers remain inaccessible.
2. V2-2J, V2-3, V2-2Q remain paused.
3. The cooldown checks and `record_selection_rotation_state()` are callable
   helpers; they are not wired into the live selection gate loop (no live
   selection gate loop exists in paper-trading-only scope).
4. V2-2S.1 verification has not been run and is not activated in this lane.
