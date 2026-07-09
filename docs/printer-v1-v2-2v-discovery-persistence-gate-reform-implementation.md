# V2-2V — Discovery Persistence Gate Reform Implementation

**Lane:** V2-2V  
**Status:** IMPLEMENTATION_COMPLETE_WITH_BLOCKERS  
**Date:** 2026-07-09  
**Anchors:** V2-2R design `a1257a0`, V2-2T proof `6d616cf`, V2-2U design `fe60ba6`

---

## Summary

Implements the Tier 2 discovery persistence pre-check designed in V2-2U inside `_select_discovery_candidates()` in `src/printer_v1/operator_cli/commands.py`. Replaces the flat existing-mint/pair rejection with a lifecycle-aware gate that allows three resurfacing categories — MIGRATION, REVIVAL, DISTINCT_NEW_EVIDENCE — while preserving all hard blocks.

---

## Files Changed

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/commands.py` | 375 insertions, 76 deletions — 4 new helpers + wiring |
| `tests/test_v2_2v_discovery_persistence_gate_reform.py` | New: 45 targeted tests |
| `docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md` | This document |

---

## Implementation Details

### Constants Added (module level)

```python
_TIER2_MIGRATION_CHANNELS: frozenset[str] = frozenset({
    "PUMPFUN_MIGRATION",
    "PUMPSWAP_GRADUATED",
    "PUMPSWAP_MIGRATION_POOL_REFERENCE",
})
_TIER2_REVIVING_LIFECYCLE_STATES: frozenset[str] = frozenset({"COOLDOWN", "ARCHIVED"})
```

### New Helpers

**`_load_returning_mint_lifecycle_statuses(conn, mints) → dict[str, str]`**  
Batch-loads the most recent `queue_status` for all returning (existing) mints from `printer_tracking_queue` before the main candidate loop. Resolves B2 (per-candidate round-trip problem). Returns `{}` on any DB error; tolerates unknown mints silently.

**`_load_last_discovery_fingerprint(conn, token_mint, pair_address) → dict | None`**  
Loads the most recent `normalized_candidate_payload_json` for a `(token_mint, pair_address)` pair from `printer_discovery_candidates`. Re-computes `primary_bucket` via `assign_bucket()` on the historical payload, then calls `compute_evidence_identity_fingerprint()`. Returns `None` if no record, payload is missing, or JSON is unparseable — safe null-return is the only error handling needed.

**`_fingerprint_change_type(old_fp, new_fp) → str`**  
Categorical label for what changed between two evidence fingerprints (`activity_bucket`, `source_channel`, `primary_bucket_group_crossing`). Used as a reporting field on accepted DISTINCT_NEW_EVIDENCE candidates. Pipe-separated when multiple fields changed; `"unknown"` if none detected.

**`_classify_returning_candidate(candidate, token_mint, pair_address, candidate_primary_bucket, *, existing_pair_addresses, lifecycle_statuses, conn) → dict`**  
Core Tier 2 classifier. Tries each path in order: MIGRATION → REVIVAL → DISTINCT_NEW_EVIDENCE. Returns a dict with `tier2_gate_outcome` (`ALLOWED`, `BLOCKED`, or `NOT_APPLICABLE`), `resurfacing_category`, `resurfacing_reason`, `prior_lifecycle_state`, `fingerprint_change_type`. No DB writes.

**Path logic:**

| Path | Condition | Outcome |
|---|---|---|
| MIGRATION | `source_channel in _TIER2_MIGRATION_CHANNELS` + `pair_address not in existing_pair_addresses` | ALLOWED |
| MIGRATION | migration channel but pair already exists | BLOCKED |
| REVIVAL | `lifecycle_state in _TIER2_REVIVING_LIFECYCLE_STATES` + `derive_activity_bucket(candidate, prior_lifecycle_state=state) == ACTIVITY_REVIVING` | ALLOWED |
| REVIVAL | archived/cooldown but activity not reviving | BLOCKED |
| DISTINCT_NEW_EVIDENCE | same mint+pair + `fingerprint_change_is_meaningful(old_fp, new_fp)` | ALLOWED |
| DISTINCT_NEW_EVIDENCE | no historical fingerprint, unparseable payload, or fingerprint unchanged | BLOCKED |
| fallthrough | non-migration new pair without lifecycle or no conn | NOT_APPLICABLE |

### `_select_discovery_candidates()` Changes

**Signature extended:**
```python
def _select_discovery_candidates(
    normalized_pairs: list[dict[str, Any]],
    *,
    existing_token_mints: set[str],
    existing_pair_addresses: set[str],
    existing_symbol_name_keys: set[str] | None = None,
    max_candidates: int,
    db_path_or_conn: str | Path | sqlite3.Connection | None = None,  # new
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
```

**B2 resolution — connection setup and lifecycle pre-load before loop:**
```python
_conn: sqlite3.Connection | None = None
_own_conn = False
if db_path_or_conn is not None:
    if isinstance(db_path_or_conn, sqlite3.Connection):
        _conn = db_path_or_conn
    else:
        try:
            _conn = sqlite3.connect(str(db_path_or_conn))
            _conn.row_factory = sqlite3.Row
            _own_conn = True
        except Exception:
            _conn = None
_lifecycle_statuses: dict[str, str] = {}
if _conn is not None:
    _returning_mints = [
        c.get("token_mint") for c in normalized_pairs
        if c.get("token_mint") and c.get("token_mint") in existing_token_mints
    ]
    _lifecycle_statuses = _load_returning_mint_lifecycle_statuses(_conn, _returning_mints)
```

**try/finally wraps main loop** to ensure `_conn` is closed when `_own_conn=True`.

**B1 resolution — primary_bucket pre-computed once per iteration:**
```python
_cand_bucket, _cand_bucket_name = assign_bucket(candidate)
```
`_cand_bucket` is passed to `_classify_returning_candidate()` and also reused in the audit-only pool path (eliminating the previous duplicate `assign_bucket()` call there).

**Tier 2 gate replaces flat rejection for returning token_mint:**
```python
elif token_mint in existing_token_mints or pair_address in existing_pair_addresses:
    _tier2_outcome = "NOT_APPLICABLE"
    if token_mint in existing_token_mints:
        _t2 = _classify_returning_candidate(
            candidate, token_mint, pair_address, _cand_bucket,
            existing_pair_addresses=existing_pair_addresses,
            lifecycle_statuses=_lifecycle_statuses,
            conn=_conn,
        )
        _tier2_outcome = _t2["tier2_gate_outcome"]
        if _tier2_outcome == "ALLOWED":
            candidate = {**candidate, <tier2 reporting fields from _t2>}
    if _tier2_outcome != "ALLOWED":
        reject_reason = ...  # duplicate_existing_token_or_pair / _mint / _pair
        rejected.append({...})
        continue
```

### Call Site Update

`build_discover_candidates_once_payload()` now passes `db_path_or_conn=resolved` to `_select_discovery_candidates()`. The `resolved` path (the operator DB path) is already available at that call site.

---

## Backward Compatibility

`db_path_or_conn` defaults to `None`. When omitted:
- `_conn = None`
- `_lifecycle_statuses = {}`
- MIGRATION path still runs (stateless: channel + pair check)
- REVIVAL path skips (no lifecycle statuses → `None not in _TIER2_REVIVING_LIFECYCLE_STATES`)
- DISTINCT_NEW_EVIDENCE path skips (conn is None → NOT_APPLICABLE)
- Pair-only collisions still blocked by flat gate

Existing tests in `test_v2_2m_audit_only_handoff.py` pass unchanged.

---

## Test Coverage (45 tests)

| Class | Cases |
|---|---|
| `TestMigrationAllowed` | New pair + migration channel allowed; reporting fields; all 3 channels |
| `TestMigrationAllowed` | Migration channel but existing pair → blocked; non-migration channel new pair → blocked |
| `TestRevivalAllowed` | ARCHIVED + activity → allowed; COOLDOWN + activity → allowed |
| `TestRevivalAllowed` | QUEUED lifecycle → not eligible; ARCHIVED + dead activity → blocked |
| `TestDistinctNewEvidenceAllowed` | activity_bucket changed → allowed; source_channel changed → allowed |
| `TestDistinctNewEvidenceBlocked` | No historical record; unparseable payload; identical fingerprint → blocked |
| `TestTier1HardBlocksPreserved` | Non-Solana; duplicate recycle; STNP unresolved; pair-only collision |
| `TestSafety` | No rows in 13 forbidden tables across all 3 Tier 2 paths; `token_age_seconds` not synthesized |
| `TestReportingFields` | All 5 reporting fields present on MIGRATION, REVIVAL, DNE accepted candidates |
| `TestBackwardCompatibility` | No DB: existing mint blocked; migration still allowed (stateless); fresh mint accepted |
| `TestLoadReturningMintLifecycleStatuses` | Empty mints; most-recent status; unknown mint absent |
| `TestLoadLastDiscoveryFingerprint` | No record → None; valid payload → fingerprint dict; unparseable → None |
| `TestFingerprintChangeType` | activity_bucket change; source_channel change |
| `TestClassifyReturningCandidateUnit` | Direct unit tests for all 6 `_classify_returning_candidate` branches |

---

## Test Results

```
tests/test_v2_2v_discovery_persistence_gate_reform.py: 45 passed
tests/test_v2_2m_audit_only_handoff.py: passed (backward compat)
tests/test_v2_2c_selection_batch.py: passed
tests/test_v2_2s_selection_cooldown.py: passed
tests/test_v2_2p_pair_age_context.py: passed
tests/test_v2_2h1_discovery_selection_capacity_repair.py: passed
Total across 5 existing suites: 387 passed, 15 subtests passed
```

---

## Blockers (inherited from V2-2U design)

**B-PERSIST-1 — `printer_selection_rotation_state.last_evidence_fingerprint_json` not written**  
V2-2V reads from `printer_discovery_candidates` for DISTINCT_NEW_EVIDENCE historical fingerprints. The `last_evidence_fingerprint_json` column in `printer_selection_rotation_state` (created by migration 026) is not yet written by this lane. This column is reserved for a future write path; the current read path is safe.

**B-PERSIST-2 — V2-2J, V2-3, token-age evidence work remain paused**  
These are pre-existing pauses documented in V2-2U and are not affected by V2-2V.

**B-PROOF-1 — No live integration proof**  
V2-2V has no paper-trading proof run. A proof lane is warranted before the Tier 2 gate is considered fully battle-tested. This is intentional scope for a future lane.

---

## What This Lane Does NOT Do

- No memory rows, retrieval rows, paper decision rows, source calls, scheduler rows
- No live trading, positions, trades, audits, PnL
- No scoring, ranking, confidence, weighted logic
- No token_age_seconds synthesized from pair age
- No writes to `printer_selection_rotation_state`
- No changes to `discovery.py`, `classifier.py`, `selection_batch.py`

---

## Verdict

`IMPLEMENTATION_COMPLETE_WITH_BLOCKERS`

The Tier 2 pre-check is implemented, wired, and tested. The three allowance paths (MIGRATION, REVIVAL, DISTINCT_NEW_EVIDENCE) are live behind `db_path_or_conn`. All hard blocks are preserved. Backward compatibility (no DB → flat gate) is maintained. The three B-PERSIST/B-PROOF blockers are inherited carry-overs, not regressions.
