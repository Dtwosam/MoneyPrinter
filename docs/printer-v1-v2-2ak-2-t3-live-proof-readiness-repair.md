# Printer V1 V2-2AK.2 T3 Live-Proof Readiness Repair

**Lane:** V2-2AK.2
**Executor:** Claude Sonnet 4.6
**Date:** 2026-07-11
**Verdict:** `REPAIR_PROOF_PASS_WITH_BLOCKERS`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

No live RPC calls. Fixture-only proof. No DB mutation.

---

## 1. Repair Target

| Item | Value |
|---|---|
| Base commit | `3d0ef50 Add V2-2AK T3 token-age implementation` |
| Verification doc | `docs/printer-v1-v2-2ak-1-t3-implementation-verification.md` |
| Verification verdict | `VERIFICATION_PARTIAL_WITH_BLOCKER` |
| Mismatches addressed | 1 (metadata), 3 (Token-2022 decoding), counter nuance (block_time_calls) |
| Mismatch 2 disposition | `SAFE_DEFERRED_BLOCKER` — governor recording model approved as per-token |

---

## 2. Repairs Applied

### Repair 1 — Live-Capability Adapter Metadata

**V2-2AK.1 finding:** `SolanaRpcTokenAgeAdapterMetadata` had
`supports_network_execution=False` and `fixture_transport_only=True`,
contradicting V2-2AJ design spec Section 3.1.

**Fix:** Changed both fields in `SolanaRpcTokenAgeAdapterMetadata`:

```python
supports_network_execution: bool = True   # live-capable; bounded transport injected for proof
fixture_transport_only: bool = False       # live transport defined; fixture used until proof lane
```

**Key invariant preserved:** The `SourceAdapterContract` (from
`build_source_adapter_contract()`) still has `fixture_only=True` and
`supports_network_execution=False` — these are the values validated by
`validate_source_adapter_contract()`. Metadata and contract are separate
objects with separate purposes. The contract guards runtime; the metadata
describes self-capability.

---

### Repair 2 — Token-2022 Mint-State Decoding

**V2-2AK.1 finding:** Token-2022 validation used owner-program + length check
only. No AccountType byte or TLV extension structure validation was performed.

**Fix:** Added `import struct` and three new constants:

```python
_SPL_TOKEN_MINT_SIZE = 82
_SPL_MINT_IS_INITIALIZED_OFFSET = 45
_TOKEN_2022_ACCOUNT_TYPE_MINT = 1
_TOKEN_2022_EXTENSION_TLV_HEADER_SIZE = 4
```

Added two new decode functions:

- **`_decode_spl_token_base_mint_state(raw_bytes)`** — validates minimum 82
  bytes and `is_initialized` byte at offset 45 == 1.
- **`_decode_token_2022_mint_state(raw_bytes)`** — calls base decode, then
  checks AccountType byte at offset 82 == 1 (Mint discriminant), then walks
  TLV extension region (each entry: 2-byte type + 2-byte length + data).
  Trailing zero-padding is accepted. Partial TLV headers with non-zero bytes
  are rejected. Buffer overflow in extension data is rejected.

Replaced the old owner+length-only Token-2022 block in `_fetch_token_age_data()`
with calls to the new decode functions. SPL Token path calls
`_decode_spl_token_base_mint_state()`. Token-2022 path calls
`_decode_token_2022_mint_state()`. Both fail closed on any decode error.

No new dependencies — `struct` is Python stdlib.

---

### Repair 3 — getBlockTime Named Counter Enforcement

**V2-2AK.1 finding:** `_T3_MAX_BLOCK_TIME_CALLS` constant existed but no
dedicated counter tracked it — total budget enforced it only implicitly via
loop structure.

**Fix:** Added `block_time_calls = 0` counter at Step 3 initialization, and
changed the getBlockTime fallback guard from:

```python
if slot is not None:
    bt_resp = _call("getBlockTime", [int(slot)])
```

to:

```python
if slot is not None and block_time_calls < _T3_MAX_BLOCK_TIME_CALLS:
    bt_resp = _call("getBlockTime", [int(slot)])
    block_time_calls += 1
```

`_T3_MAX_BLOCK_TIME_CALLS = 1` is now enforced directly by the named counter,
independent of the total request budget.

---

### Repair 4 — Governor Recording Model Decision (Documentation)

**V2-2AK.1 finding:** Per-operation RPC recording not implemented; per-token
model used (matches holder adapter precedent).

**Disposition:** Operator approved per-token Source Governor row as the
recording model for V2-2AK.2. All 15 `t3_*` provenance fields (including
`t3_rpc_methods_attempted` and `t3_request_ids`) capture per-operation
traceability within the single enrichment row. Per-RPC rows documented as a
deferred blocker for a fully satisfying live-proof claim.

---

## 3. Files Changed

| File | Change |
|---|---|
| `src/printer_v1/sources/solana_rpc_token_age.py` | Metadata repair; `struct` import; new constants; `_decode_spl_token_base_mint_state()`; `_decode_token_2022_mint_state()`; Token-2022 validation block replaced; `block_time_calls` counter added; getBlockTime guard enforced |
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | 4 new test classes (30 tests): `TestLiveCapabilityMetadata`, `TestSplTokenMintStateDecoding`, `TestToken2022MintStateDecoding`, `TestGetBlockTimeLimit` |
| `docs/printer-v1-v2-2ak-2-t3-live-proof-readiness-repair.md` | This file |

---

## 4. New Decode Functions

### `_decode_spl_token_base_mint_state(raw_bytes) -> tuple[bool, str | None]`

Validates:
1. `len(raw_bytes) >= 82` — minimum Mint layout size
2. `raw_bytes[45] == 1` — `is_initialized` flag

Returns `(True, None)` on success; `(False, error_message)` on any failure.

### `_decode_token_2022_mint_state(raw_bytes) -> tuple[bool, str | None]`

Validates:
1. Base SPL Token Mint layout (via `_decode_spl_token_base_mint_state`)
2. `raw_bytes[82] == 1` — AccountType discriminant (must be Mint = 1)
3. TLV extension region starting at byte 83:
   - Each entry: `struct.unpack_from("<HH", ...)` → type, length; then `length` bytes data
   - Trailing zero bytes acceptable (common padding)
   - Partial TLV header (< 4 bytes) with non-zero content → reject
   - Extension data overflowing buffer end → reject

Returns `(True, None)` on success; `(False, error_message)` on any failure.

---

## 5. New Test Classes

### Class 12: `TestLiveCapabilityMetadata` (7 tests)

Verifies the V2-2AK.2 metadata repair:
- `fixture_transport_only == False`
- `supports_network_execution == True`
- `enabled_by_default == False`
- `requires_governor_context == True`
- Metadata and contract are separate objects with different values
- `source_name` matches constant
- `read_only == True`

### Class 13: `TestSplTokenMintStateDecoding` (7 tests)

Verifies `_decode_spl_token_base_mint_state()`:
- Valid 82-byte initialized mint passes
- `is_initialized = 0` rejected with "not initialized" message
- `is_initialized = 2` (non-one, non-zero) rejected
- Too-short buffers (44 bytes, 0 bytes, 81 bytes) rejected with "Too short"
- 83-byte buffer still passes base check (Token-2022 case)

### Class 14: `TestToken2022MintStateDecoding` (11 tests)

Verifies `_decode_token_2022_mint_state()`:
- Valid mint with no extensions passes
- Valid mint with one TLV extension passes
- Valid mint with two TLV extensions passes
- Trailing zero-padding after extensions accepted
- AccountType byte 0 rejected with "AccountType" in message
- AccountType byte 2 rejected
- TLV extension claiming 100 bytes with only 4 available → overflow rejected
- Partial TLV header (3 non-zero bytes) rejected with "Partial TLV header"
- Wrong AccountType proves owner+length-only is not sufficient
- Uninitialized base mint fails before AccountType check
- Too-short base mint fails before AccountType check

### Class 15: `TestGetBlockTimeLimit` (5 tests)

Verifies the `block_time_calls` counter enforcement:
- `_T3_MAX_BLOCK_TIME_CALLS == 1`
- `block_time_source = "getTransaction"` accepted by normalizer
- `block_time_source = "getBlockTime"` accepted by normalizer
- Null block time with budget exhausted fails closed
- `_T3_MAX_BLOCK_TIME_CALLS < _T3_MAX_TRANSACTION_CALLS < _T3_MAX_REQUESTS_PER_TOKEN`

---

## 6. Tests Run

### Focused suite

| File | V2-2AK tests | V2-2AK.2 new tests | Total | Result |
|---|---|---|---|---|
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | 84 | 30 | 114 | PASS |

### Cross-check suites

| Suite | Tests | Result |
|---|---|---|
| `tests/test_v2_2x2_t2_token_age_evidence.py` | 82 | PASS |
| `tests/test_v2_2ag_observed_live_launch_tier.py` | 30 | PASS |
| Combined cross-check | 112 | PASS |

Warnings: LF→CRLF conversion warnings only. No whitespace errors. No live RPC.

---

## 7. Safety Confirmations

- No live RPC calls — all tests use fixture transports
- No new external dependencies — `struct` is Python stdlib
- `token_created_at` never set from `captured_at` — confirmed by existing tests
- `token_created_at` never set from pair age — confirmed by existing tests
- T2 contract unchanged — 82 T2 tests pass
- `OBSERVED_LIVE_LAUNCH` unchanged — 30 tier tests pass
- A3 not unlocked — unchanged
- No DB mutation, no memory generation, no retrieval
- No BUY/SELL/HOLD, paper decisions, positions, trades, audits, or PnL
- No scoring, ranking, confidence, weighted, embeddings, or vectors
- A3 gate (`token_age_seconds is not None`) unchanged

---

## 8. Remaining Blockers

| Blocker | Status |
|---|---|
| Per-RPC-call Source Governor recording | DEFERRED — per-token recording approved for V2-2AK.2; per-RPC rows still deferred before live-proof claim |
| Live network proof (V2-2AL) | NOT YET RUN — requires bounded live proof lane with operator approval |
| A3 not yet live | INTENTIONAL — requires live proof before A3 can be enabled for T3 evidence |
| Staged/native 15m blocker | PARTIAL - DEFERRED, NOT RESOLVED |
| V2-3 | PAUSED |

---

## 9. Final Summary

```text
VERDICT: REPAIR_PROOF_PASS_WITH_BLOCKERS
BASE_COMMIT: 3d0ef50 Add V2-2AK T3 token-age implementation
REPAIR_1_METADATA: COMPLETE — fixture_transport_only=False, supports_network_execution=True
REPAIR_2_TOKEN_2022: COMPLETE — AccountType byte + TLV walk in _decode_token_2022_mint_state()
REPAIR_3_BLOCK_TIME_COUNTER: COMPLETE — block_time_calls counter enforced against _T3_MAX_BLOCK_TIME_CALLS
REPAIR_4_GOVERNOR_MODEL: APPROVED — per-token recording model documented; per-RPC rows deferred
NEW_TESTS: 30 (4 new classes; 114 total in suite)
CROSS_CHECK_TESTS: 112 PASS (T2 + OBSERVED_LIVE_LAUNCH)
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
T2_UNCHANGED: CONFIRMED
OBSERVED_LIVE_LAUNCH_UNCHANGED: CONFIRMED
A3_GATE_UNCHANGED: token_age_seconds is not None
A3_STATUS: LOCKED (fixture only; live proof required)
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
NEXT_LANE: V2-2AL — Bounded Live T3 Proof (operator approval required)
```
