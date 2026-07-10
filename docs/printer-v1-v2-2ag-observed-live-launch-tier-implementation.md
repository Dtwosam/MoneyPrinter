# Printer V1 V2-2AG OBSERVED_LIVE_LAUNCH Tier Implementation

**Lane:** V2-2AG
**Executor:** Claude Sonnet 4.6
**Date:** 2026-07-10
**Verdict:** `IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

No live source calls in this lane. Fixture-only proof.

---

## 1. Design Anchors

| Anchor | Commit | Content |
|---|---|---|
| V2-2AE diagnostics | `9f9562c` | 4 mint-bearing events observed; 0 explicit timestamps |
| V2-2AF design | `d976fe1` | OBSERVED_LIVE_LAUNCH tier design; T2 preservation rule; A3 unchanged |

---

## 2. Files Changed

| File | Change |
|---|---|
| `src/printer_v1/sources/pumpportal.py` | Added `live_observed_launch` flag logic in `_normalize_pumpportal_event()` |
| `src/printer_v1/discovery/parser.py` | Extended `_derive_token_age_evidence_tier()` to return `"OBSERVED_LIVE_LAUNCH"` |
| `tests/test_v2_2x2_t2_token_age_evidence.py` | Updated 2 tests whose assertions changed with the new tier behavior |
| `tests/test_v2_2ag_observed_live_launch_tier.py` | New 30-test focused proof suite for OBSERVED_LIVE_LAUNCH |
| `docs/printer-v1-v2-2ag-observed-live-launch-tier-implementation.md` | This file |

---

## 3. Implementation Details

### 3.1 `pumpportal.py` — `live_observed_launch` flag

In `_normalize_pumpportal_event()`, after the T2 timestamp extraction block:

```python
token_created_at: str | None = None
live_observed_launch: bool = False
if request_kind == "pumpfun_launch_stream":
    _observation_ref = event.get("captured_at") or _current_iso()
    token_created_at = _extract_launch_timestamp(event, _observation_ref)
    # OBSERVED_LIVE_LAUNCH only when no explicit timestamp field exists at all.
    # A stale, invalid, or zero timestamp still counts as "field present" —
    # only complete absence of all three fields triggers this flag.
    if token_created_at is None and not any(
        k in event for k in ("tokenCreatedAt", "createdTimestamp", "timestamp")
    ):
        live_observed_launch = True
```

The flag is False for:
- Migration events (`request_kind == "pumpfun_migration_stream"` skips the block)
- Events where explicit timestamp fields exist but are stale/invalid (field is
  present → `k in event` is True → `not any(...)` is False)
- Events where T2 evidence is successfully derived (`token_created_at` is set)

The flag is True only when:
- `request_kind == "pumpfun_launch_stream"` (launch, not migration)
- No T2 timestamp was derived (`token_created_at is None`)
- None of `tokenCreatedAt`, `createdTimestamp`, `timestamp` is present as a key
  in the event at all

The field is added to the returned dict as `"live_observed_launch": live_observed_launch`.

### 3.2 `parser.py` — extended `_derive_token_age_evidence_tier()`

```python
def _derive_token_age_evidence_tier(
    source_name: str,
    candidate_payload: Mapping[str, Any],
    token_created_at_raw: Any,
    token_age_seconds: float | None,
) -> str | None:
    if source_name != "pumpportal":
        return None
    if candidate_payload.get("request_kind") != "pumpfun_launch_stream":
        return None
    # T2: explicit source-provided timestamp present and valid.
    if token_created_at_raw is not None and token_age_seconds is not None:
        return "T2"
    # OBSERVED_LIVE_LAUNCH: mint-bearing launch event; no explicit timestamp field.
    if token_created_at_raw is None and candidate_payload.get("live_observed_launch"):
        return "OBSERVED_LIVE_LAUNCH"
    return None
```

T2 check moved to a positive condition (both raw and derived values present) to
make precedence explicit. OBSERVED_LIVE_LAUNCH fires only when:
1. `token_created_at_raw is None` — no T2 evidence
2. `live_observed_launch` flag is set in `candidate_payload`

---

## 4. T2 Preservation Proof

T2 is unchanged. The following are confirmed by existing tests (82 T2 tests
pass, unchanged):

- `token_created_at` is set from `tokenCreatedAt → createdTimestamp → timestamp`
  in priority order.
- `token_age_evidence_tier = "T2"` requires `token_created_at_raw is not None`
  AND `token_age_seconds is not None`.
- `captured_at` still never maps to `token_created_at`.
- Stale timestamps (field present but > 3600s old): field IS in event → `k in
  event` is True → `live_observed_launch = False` → tier remains None.
- Zero/negative/invalid timestamps (field present but unparseable): same logic
  → `live_observed_launch = False` → tier remains None.
- Future timestamps: field present → same → tier remains None.
- Migration events: `request_kind` guard prevents both T2 and OBSERVED_LIVE_LAUNCH.

T2 takes explicit precedence in the updated `_derive_token_age_evidence_tier`:
the T2 check runs first. If both T2 evidence and the flag were present
(theoretically impossible via the normalizer but tested directly), T2 wins.

---

## 5. OBSERVED_LIVE_LAUNCH Behavior

For a mint-bearing `pumpfun_launch_stream` event with no explicit timestamp
fields (the V2-2AE payload shape):

| Field | Value |
|---|---|
| `token_created_at` | `None` |
| `token_age_seconds` | `None` |
| `token_age_evidence_tier` | `"OBSERVED_LIVE_LAUNCH"` |
| `captured_at` | Source Governor receipt time (observation timestamp) |
| `live_observed_launch` | `True` (in pumpportal-normalized event, not in NORMALIZED_FIELDS) |

`live_observed_launch` is an internal pumpportal-to-parser signal. It flows
through `candidate_payload` in `normalize_candidate()` but is not in
`NORMALIZED_FIELDS`, so it does not appear in the selection-batch-persisted
output. Only `token_age_evidence_tier = "OBSERVED_LIVE_LAUNCH"` is persisted.

---

## 6. A3 Lock Confirmation

A3 is not unlocked by `OBSERVED_LIVE_LAUNCH`.

`token_age_seconds` remains `None` for all `OBSERVED_LIVE_LAUNCH` candidates.
The A3 gate:

```python
_tok_age_known = candidate.get("token_age_seconds") is not None
```

evaluates to `False`. A3 does not fire. Confirmed by three dedicated tests:
- `test_a3_does_not_fire_when_token_age_seconds_is_none`
- `test_age_bucket_is_age_unknown_for_observed_live_launch`
- `test_assign_bucket_does_not_assign_a3_for_observed_live_launch`

`derive_age_bucket` returns `AGE_UNKNOWN` when `token_age_seconds is None`,
so `derive_recent_active_tier` returns `UNKNOWN_TIER_5`. This is unchanged.

---

## 7. Existing Test Updates (2 tests)

Two tests in `test_v2_2x2_t2_token_age_evidence.py` asserted that a
no-timestamp launch event produces `tier=None`. This was correct before V2-2AG.
After V2-2AG, a no-timestamp launch event correctly produces
`OBSERVED_LIVE_LAUNCH`. The tests were updated:

| Test | Old assertion | New assertion |
|---|---|---|
| `test_no_timestamp_fields_no_t2` | `assertIsNone(tier)` | `assertEqual(tier, "OBSERVED_LIVE_LAUNCH")` |
| `test_no_t2_candidate_has_none_tier_in_metadata` (renamed) | `assertIsNone(meta tier)` | `assertEqual(meta tier, "OBSERVED_LIVE_LAUNCH")` |

Both tests also assert `token_created_at is None` and `token_age_seconds is
None` — those assertions remain and still pass.

---

## 8. Tests and Checks Run

### New test suite

| File | Tests | Result |
|---|---|---|
| `tests/test_v2_2ag_observed_live_launch_tier.py` | 30 | PASS |

Test classes:
- `TestPumpPortalNormalizerLiveObservedLaunchFlag` (7 tests)
- `TestObservedLiveLaunchTierFullPipeline` (4 tests)
- `TestT2TakesPrecedenceOverObservedLiveLaunch` (4 tests)
- `TestMigrationEventNeverGetsObservedLiveLaunch` (3 tests)
- `TestA3NotUnlockedByObservedLiveLaunch` (3 tests)
- `TestObservedLiveLaunchTierSurvivesToMetadata` (4 tests)
- `TestDeriveTokenAgeEvidenceTierDirectly` (5 tests)

### Focused existing suites

| Command | Result |
|---|---|
| `python -m pytest tests/test_v2_2ag_observed_live_launch_tier.py tests/test_v2_2x2_t2_token_age_evidence.py tests/test_v2_2ab_pumpportal_live_transport.py tests/test_v2_2c_selection_batch.py -q` | **275 passed** in 120.42s |

### Git checks

| Check | Result |
|---|---|
| `git diff --check` | LF→CRLF warnings only; no whitespace errors |
| `git status --short` | 3 M (tracked), 1 ?? new test file, ?? unrelated untracked files |
| `git diff --stat` | 3 files, 32 insertions, 11 deletions |
| `git diff --name-only` | `src/printer_v1/discovery/parser.py`, `src/printer_v1/sources/pumpportal.py`, `tests/test_v2_2x2_t2_token_age_evidence.py` |

---

## 9. Safety Confirmations

- No live network calls — all tests use fixture transports
- `token_created_at` never set from `captured_at` — confirmed by test
- `token_age_seconds` never computed from `captured_at` — confirmed by test
- T2 contract unchanged — 82 T2 tests pass
- A3 not unlocked — `token_age_seconds is None` for all OBSERVED_LIVE_LAUNCH candidates
- Migration events excluded — `request_kind` guard enforces this
- No new columns or schema migrations — `token_age_evidence_tier` already in `_METADATA_FIELDS`
- `enabled_by_default = False` — unchanged
- `pumpfun_migration_stream` remains `NOT_READY` — unchanged
- No BUY/SELL/HOLD, paper decisions, memory, retrieval, scheduler, PumpSwap
- No scoring, ranking, confidence, weighted, embeddings, or vectors
- `live_observed_launch` field does not appear in `NORMALIZED_FIELDS` — it is
  an internal transport-to-parser signal only

---

## 10. Remaining Blockers

| Blocker | Status |
|---|---|
| T2 unavailable for live PumpPortal events (no explicit timestamps in observed payload) | CONFIRMED (V2-2AE); OBSERVED_LIVE_LAUNCH is the workaround |
| Live proof with OBSERVED_LIVE_LAUNCH not yet run | DEFERRED — needs another bounded live call to confirm tier is set on real events |
| `pumpfun_migration_stream` remains `NOT_READY` | INTENTIONAL |
| V2-3 remains paused | INTENTIONAL |

---

## 11. Exact Next Recommended Lane

**V2-2AH — OBSERVED_LIVE_LAUNCH Live Proof**

Scope:
1. Run one bounded live PumpPortal `pumpfun_launch_stream` call (max 5 events,
   30s, through Source Governor, isolated proof DB only).
2. Confirm that received events produce `token_age_evidence_tier =
   "OBSERVED_LIVE_LAUNCH"` in normalized candidates.
3. Confirm `token_created_at` and `token_age_seconds` remain None.
4. Confirm persistent DB is unchanged.
5. Proof report: `docs/printer-v1-v2-2ah-observed-live-launch-live-proof.md`

Pre-conditions:
- V2-2AG committed (this lane).
- Operator approval for bounded live call.
- No paper decisions, memory, retrieval, or BUY/SELL/HOLD.

Alternatively, if the operator prefers to defer live proof, the next design
scope is broader token-age discovery (T3/enrichment path design) or PumpPortal
timestamp source investigation.

---

## 12. V2-3 Status

**V2-3 remains PAUSED.**

No retrieval, no memory generation, no scheduling, no scoring, no paper
decisions, no BUY/SELL/HOLD were introduced or enabled.
