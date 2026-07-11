# Printer V1 V2-2AL.4A T3 Failure-Provenance Repair

**Lane:** V2-2AL.4A
**Executor:** Claude Sonnet 4.6
**Date:** 2026-07-12
**Verdict:** `REPAIR_PROOF_PASS_WITH_BLOCKERS`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

No live RPC calls. Fixture-only proof. No DB mutation. No page-cap changes.
No A3 work. No V2-3 work.

---

## 1. Repair Target

| Item | Value |
|---|---|
| Anchor | `af78265 Add V2-2AL.4 T3 retry readiness review` |
| V2-2AL.4 finding | `HARD_AUDITABILITY_BLOCKER_REQUIRING_REPAIR_FIRST` |
| Root cause | Bounded T3 failures returned bare `{failure_type, failure_message}` with no partial trace; operators had to infer method progress from failure message text |
| Source of truth | `docs/printer-v1-v2-2al-4-t3-page-cap-provenance-readiness-review.md` Section "Safe Partial Failure Fields Needed" |

---

## 2. Failure Fields Added

All new fields use `t3_*` names. They are audit/trace only. They never
produce `token_created_at`, `token_age_seconds`, `token_age_evidence_tier`,
or any A3-unlocking value.

The constant `_T3_FAIL_PROVENANCE_FIELDS` (exported from `solana_rpc_token_age.py`)
enumerates all 8 fields:

| Field | Type | Meaning |
|---|---|---|
| `t3_requested_mint` | str | Token mint address that was the T3 target |
| `t3_rpc_host_redacted` | str | Redacted RPC hostname (no path, no API key) |
| `t3_rpc_methods_attempted` | list[str] | RPC methods called in order up to failure |
| `t3_request_ids` | list[int] | JSON-RPC request IDs for each method call |
| `t3_pages_fetched` | int | Number of `getSignaturesForAddress` pages completed |
| `t3_tx_calls_attempted` | int | Number of `getTransaction` calls made |
| `t3_block_time_calls_attempted` | int | Number of `getBlockTime` calls made |
| `t3_failure_stage` | str | Pipeline stage at failure (see §3) |

### Failure stages

| Stage value | When set |
|---|---|
| `"account_validation"` | Failure at `getAccountInfo` or mint-state decoding |
| `"signature_history"` | Failure in `getSignaturesForAddress` walk or page-cap exhaustion |
| `"transaction_inspection"` | Failure during `getTransaction` loop or no init instruction found |
| `"block_time_fallback"` | Failure during `getBlockTime` fallback call |
| `"timestamp_derivation"` | Failure parsing timestamps or future block time detected |

---

## 3. Source Changes

### `_T3_FAIL_PROVENANCE_FIELDS` constant (new)

Added to `solana_rpc_token_age.py` after `_T3_ALLOWED_REQUEST_KINDS`:

```python
_T3_FAIL_PROVENANCE_FIELDS = (
    "t3_requested_mint",
    "t3_rpc_host_redacted",
    "t3_rpc_methods_attempted",
    "t3_request_ids",
    "t3_pages_fetched",
    "t3_tx_calls_attempted",
    "t3_block_time_calls_attempted",
    "t3_failure_stage",
)
```

### `_fetch_token_age_data()` — `_pfail()` closure (new)

`pages_fetched = 0`, `tx_calls = 0`, `block_time_calls = 0` moved to the top
of `_fetch_token_age_data()`. A `_pfail()` closure defined after `host_redacted`
captures the current tracking state and returns a failure dict with all 8 provenance fields:

```python
def _pfail(failure_type: str, failure_message: str, *, stage: str) -> Mapping[str, Any]:
    return MappingProxyType({
        "fixture_status": "failure",
        "failure_type": failure_type,
        "failure_message": failure_message,
        "t3_requested_mint": token_mint,
        "t3_rpc_host_redacted": host_redacted,
        "t3_rpc_methods_attempted": list(methods_attempted),
        "t3_request_ids": list(request_ids),
        "t3_pages_fetched": pages_fetched,
        "t3_tx_calls_attempted": tx_calls,
        "t3_block_time_calls_attempted": block_time_calls,
        "t3_failure_stage": stage,
    })
```

All bare `return MappingProxyType({...})` failure returns replaced with `_pfail(...)` calls at each failure point.

### `_extract_failure_provenance()` helper (new)

Copies only `_T3_FAIL_PROVENANCE_FIELDS` from a failure payload. Never copies
success-path fields. Returns `None` for bare payloads with no provenance fields.

### `normalize_solana_rpc_token_age_response()` — failure branch updated

```python
# before
return _t3_failure_result(request_kind, failure_type, failure_message)

# after
return _t3_failure_result(
    request_kind, failure_type, failure_message,
    failure_provenance=_extract_failure_provenance(payload),
)
```

### `_t3_failure_result()` — `failure_provenance` kwarg (new)

```python
def _t3_failure_result(
    request_kind: str,
    failure_type: str,
    failure_message: str,
    *,
    failure_provenance: Mapping[str, Any] | None = None,
) -> NormalizedSourceResult:
    payload: dict[str, Any] = dict(failure_provenance) if failure_provenance else {}
    return NormalizedSourceResult(
        ...
        normalized_payload=MappingProxyType(payload),
    )
```

### `fixture_t3_failure_transport()` — `failure_provenance` kwarg (new)

```python
def fixture_t3_failure_transport(
    failure_type: str,
    failure_message: str = "T3 fixture failure",
    *,
    failure_provenance: Mapping[str, Any] | None = None,
) -> ...:
```

Accepts optional partial provenance for test fixtures.

---

## 4. Fail-Closed / A3 Safety

| Guarantee | Status |
|---|---|
| `token_created_at` absent on every failure | CONFIRMED — never set by `_t3_failure_result()` |
| `token_age_seconds` absent on every failure | CONFIRMED |
| `token_age_evidence_tier` absent on every failure | CONFIRMED |
| A3 does not fire from failure provenance | CONFIRMED — `assign_bucket()` requires `token_age_seconds is not None` |
| `_extract_failure_provenance()` never copies success-path fields | CONFIRMED — only copies `_T3_FAIL_PROVENANCE_FIELDS` |
| Bare failures (no provenance in input) → empty normalized_payload | CONFIRMED — backward compatible |

---

## 5. Success-Path Regression

All 15 success-path `t3_*` provenance fields unchanged. Success path still
produces `token_created_at`, `token_age_seconds`, `token_age_evidence_tier = "T3"`.

---

## 6. Tests

### Test counts

| Suite | Tests | Result |
|---|---|---|
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | 132 | PASS |
| `tests/test_v2_2x2_t2_token_age_evidence.py` | 82 | PASS |
| `tests/test_v2_2ag_observed_live_launch_tier.py` | 30 | PASS |

Net new: 15 tests in `TestT3FailureProvenance` (Class 16).

### New test class — `TestT3FailureProvenance` (15 tests)

| Test | Scenario |
|---|---|
| `test_mint_validation_failure_carries_partial_provenance` | Account validation failure — all 8 provenance fields present |
| `test_rate_limit_failure_carries_partial_provenance` | Rate limit failure carries t3_requested_mint and t3_failure_stage |
| `test_page_cap_exhaustion_carries_pages_fetched` | pages_fetched=3, stage=signature_history |
| `test_transaction_no_init_failure_carries_tx_calls_attempted` | tx_calls_attempted=2, stage=transaction_inspection |
| `test_null_block_time_failure_carries_block_time_calls_attempted` | block_time_calls_attempted=1, stage=block_time_fallback |
| `test_budget_exhausted_failure_carries_exact_method_count` | 8 methods, 3 tx calls, 1 bt call |
| `test_failure_provenance_carries_redacted_rpc_host` | No http://, no ?, no apikey in host field |
| `test_failure_stage_field_present_and_non_empty` | All stage values are non-empty strings |
| `test_failure_provenance_never_sets_token_age_fields` | token_created_at/age_seconds/tier absent on every failure |
| `test_failure_provenance_never_unlocks_a3` | assign_bucket() never returns BUCKET_A3 from failure provenance |
| `test_success_path_unchanged_after_provenance_repair` | Success path regression — all 15 t3_* fields still present |
| `test_bare_failure_no_provenance_fields_has_empty_payload` | Bare fixture failure → empty normalized_payload (backward compat) |
| `test_fixture_failure_transport_with_provenance_kwarg` | fixture_t3_failure_transport(failure_provenance=...) propagates correctly |
| `test_fail_provenance_constant_has_all_required_fields` | _T3_FAIL_PROVENANCE_FIELDS has exactly the 8 required fields |
| `test_failure_provenance_methods_list_reflects_actual_calls` | Account validation failure → only getAccountInfo in methods list |

### Limits unchanged (static verification)

All existing limit constants unchanged:
- `_T3_MAX_REQUESTS_PER_TOKEN = 8`
- `_T3_MAX_SIGNATURE_PAGES = 3`
- `_T3_MAX_TRANSACTION_CALLS = 3`
- `_T3_MAX_BLOCK_TIME_CALLS = 1`
- `_T3_RPC_TIMEOUT_SECONDS = 10.0`

---

## 7. Files Changed

| File | Change |
|---|---|
| `src/printer_v1/sources/solana_rpc_token_age.py` | Added `_T3_FAIL_PROVENANCE_FIELDS`; `_pfail()` closure in `_fetch_token_age_data()`; `_extract_failure_provenance()` helper; `failure_provenance` kwarg on `_t3_failure_result()` and `fixture_t3_failure_transport()`; updated normalizer failure branch |
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | Added `_T3_FAIL_PROVENANCE_FIELDS` import; 4 fixture provenance dicts; `TestT3FailureProvenance` class (15 tests) |
| `docs/printer-v1-v2-2al-4a-t3-failure-provenance-repair.md` | This file |

---

## 8. Safety Confirmations

- No live RPC calls — all tests use fixture transports
- No page-cap changes — all limits unchanged
- No A3 changes — `_tok_age_known` gate in `classifier.py` unchanged
- No new external dependencies
- T2 unchanged — 82 T2 tests pass
- OBSERVED_LIVE_LAUNCH unchanged — 30 tier tests pass
- No DB mutation, no memory generation, no retrieval
- No BUY/SELL/HOLD, paper decisions, positions, trades, audits, or PnL
- V2-3: PAUSED
- Staged/native 15m blocker: PARTIAL - DEFERRED, NOT RESOLVED

---

## 9. Remaining Blockers

| Blocker | Status |
|---|---|
| Live network proof | NOT YET RETRIED — V2-2AL.4B independent verification required first |
| Approved AL.5 retry mint | `6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump` (approved in V2-2AL.4) |
| A3 not live | INTENTIONAL — requires successful live T3 proof |
| Staged/native 15m blocker | PARTIAL - DEFERRED, NOT RESOLVED |
| V2-3 | PAUSED |

---

## 10. Final Summary

```text
VERDICT: REPAIR_PROOF_PASS_WITH_BLOCKERS
ANCHOR: af78265 Add V2-2AL.4 T3 retry readiness review
ROOT_CAUSE: T3 failures returned bare failure_type/message; partial RPC trace was lost
REPAIR: _pfail() closure threads 8 t3_* provenance fields into every failure return
NEW_FIELDS: t3_requested_mint, t3_rpc_host_redacted, t3_rpc_methods_attempted,
            t3_request_ids, t3_pages_fetched, t3_tx_calls_attempted,
            t3_block_time_calls_attempted, t3_failure_stage
FAIL_CLOSED: CONFIRMED — token_created_at/age_seconds/tier never in failure payload
A3_STATUS: LOCKED — failure provenance never satisfies token_age_seconds is not None
SUCCESS_PATH: UNCHANGED — 15 t3_* fields still present on success
FOCUSED_TESTS: 132 PASS (+15 new in TestT3FailureProvenance)
CROSS_CHECK_TESTS: 112 PASS (T2 + OBSERVED_LIVE_LAUNCH)
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
PAGE_CAP_UNCHANGED: CONFIRMED
T2_UNCHANGED: CONFIRMED
OBSERVED_LIVE_LAUNCH_UNCHANGED: CONFIRMED
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
APPROVED_AL5_MINT: 6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump
NO_LIVE_RETRY_YET: confirmed — V2-2AL.4B must verify first
NEXT_LANE: V2-2AL.4B — Independent T3 Failure-Provenance Verification
```
