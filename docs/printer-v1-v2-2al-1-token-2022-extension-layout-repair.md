# Printer V1 V2-2AL.1 Token-2022 Extension Layout Repair

**Lane:** V2-2AL.1
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
| Anchor commit | `dfb76b6 Add V2-2AL bounded live T3 proof` |
| V2-2AL failure | `solana_rpc_token_age_not_a_mint` — `Token-2022 AccountType byte 0 is not Mint (expected 1)` |
| Root cause | Decoder read AccountType from byte 82, which is the FIRST PADDING BYTE (= 0), not the AccountType |
| Authoritative source | `solana-program-library token/program-2022/src/extension/mod.rs` |

---

## 2. Authoritative Token-2022 Extended-Mint Layout Finding

### Constants from SPL Token-2022 (`extension/mod.rs`)

| Constant | Value | Meaning |
|---|---|---|
| `Mint::LEN` | 82 | Base SPL Token Mint size (bytes [0..82]) |
| `Account::LEN` / `BASE_ACCOUNT_LENGTH` | 165 | Base SPL Token Account size; used as padded base in Token-2022 |
| `ACCOUNT_TYPE_SIZE` | 1 | One byte for AccountType discriminant |
| `BASE_ACCOUNT_AND_TYPE_LENGTH` | 166 | Minimum Token-2022 extended account size |
| AccountType offset | 165 | `BASE_ACCOUNT_LENGTH` — where AccountType is written |
| TLV extension start | 166 | `BASE_ACCOUNT_AND_TYPE_LENGTH` |

### Correct Token-2022 Extended Mint Layout

```
[0..82]:    Base SPL Token Mint (Mint::LEN = 82 bytes)
            Byte [45]: is_initialized = 1 (must be set)
[82..165]:  Padding region (Account::LEN - Mint::LEN = 83 zero bytes)
            Aligns AccountType to BASE_ACCOUNT_LENGTH for backward compatibility
[165]:      AccountType discriminant (= Account::LEN = BASE_ACCOUNT_LENGTH)
            Must be 1 (AccountType::Mint)
[166..]:    Extension TLV entries (2-byte LE type + 2-byte LE length + data)
            Trailing zero bytes acceptable after last valid TLV entry
```

**Minimum valid Token-2022 extended mint: 166 bytes.**

### Why byte 82 = 0 is CORRECT

Byte 82 is the first byte of the 83-byte padding region, which must be all
zeros. The V2-2AK.2 decoder incorrectly read byte 82 as the AccountType,
producing "AccountType byte 0 is not Mint (expected 1)". With the corrected
layout, byte 82 = 0 is the expected padding value.

---

## 3. Decoder Repair

### New constants added to `solana_rpc_token_age.py`

```python
_SPL_TOKEN_ACCOUNT_SIZE = 165           # Account::LEN / BASE_ACCOUNT_LENGTH in Token-2022
_TOKEN_2022_ACCOUNT_TYPE_OFFSET = _SPL_TOKEN_ACCOUNT_SIZE       # = 165 — AccountType position
_TOKEN_2022_EXTENSION_DATA_START = _SPL_TOKEN_ACCOUNT_SIZE + 1  # = 166 — TLV region start
```

The existing constant `_TOKEN_2022_ACCOUNT_TYPE_MINT = 1` is unchanged.

### Updated `_decode_token_2022_mint_state()` — five-step validation

| Step | Check | Fail-closed outcome |
|---|---|---|
| 1 | `_decode_spl_token_base_mint_state(raw_bytes)` — validates 82-byte base and is_initialized | "Too short" or "not initialized" |
| 2 | `len(raw_bytes) >= 166` — minimum for extended mint | "too short" with byte count |
| 3 | `raw_bytes[82:165]` all zeros — padding region valid | "padding region has non-zero byte at offset N" |
| 4 | `raw_bytes[165] == 1` — AccountType = Mint | "AccountType byte N at offset 165 is not Mint" |
| 5 | Walk TLV entries from byte 166 — each entry valid | "overflows" or "Partial TLV header" |

### V2-2AK.2 decoder (incorrect — offset 82)

```python
account_type = raw_bytes[_SPL_TOKEN_MINT_SIZE]  # byte 82 — WRONG (padding byte)
```

### V2-2AL.1 decoder (correct — offset 165)

```python
account_type = raw_bytes[_TOKEN_2022_ACCOUNT_TYPE_OFFSET]  # byte 165 — correct
```

---

## 4. Test Changes

### `_make_token_2022_mint_bytes()` helper — corrected

Old (V2-2AK.2): created `82 + 1 + len(extensions)` bytes (AccountType at byte 82)

New (V2-2AL.1): creates `82 + 83 + 1 + len(extensions) = 166+ bytes` (AccountType at byte 165):

```python
def _make_token_2022_mint_bytes(
    *, is_initialized=1, padding=None, account_type=_TOKEN_2022_ACCOUNT_TYPE_MINT, extensions=b""
) -> bytes:
    base = _make_spl_mint_bytes(is_initialized=is_initialized)  # 82 bytes
    pad = padding if padding is not None else bytes(83)          # 83 zero bytes
    return base + pad + bytes([account_type]) + extensions
```

### `TestToken2022MintStateDecoding` (class 14) — full replacement

All 11 prior tests replaced with 13 corrected tests:

| Test | Coverage |
|---|---|
| `test_valid_no_extensions_passes` | 166-byte minimal mint accepted |
| `test_v2_2al_byte_82_is_zero_and_is_valid_padding` | Byte 82 = 0 is correct padding — must NOT fail (root cause test) |
| `test_valid_with_one_extension_passes` | Mint with one TLV extension accepted |
| `test_valid_with_two_extensions_passes` | Mint with two TLV extensions accepted |
| `test_trailing_zero_padding_after_extensions_allowed` | Trailing zeros after last TLV accepted |
| `test_invalid_padding_byte_rejected` | Non-zero in padding [82..165] → rejected |
| `test_wrong_account_type_byte_0_rejected` | AccountType=0 at offset 165 → rejected (error references offset 165) |
| `test_account_type_2_rejected` | AccountType=2 (Token Account) at offset 165 → rejected |
| `test_too_short_missing_account_type_rejected` | 165 bytes (missing AccountType) → rejected |
| `test_tlv_overflow_rejected` | TLV length overflows buffer → rejected |
| `test_partial_tlv_header_with_non_zero_bytes_rejected` | Partial TLV header (non-zero) → rejected |
| `test_uninitialized_base_mint_fails_before_account_type_check` | is_initialized=0 fails first |
| `test_base_mint_too_short_fails_before_account_type_check` | 81-byte buffer fails at base check |
| `test_account_type_offset_is_165` | Constants sanity check: offset=165, start=166 |

New imports added to test file: `_SPL_TOKEN_ACCOUNT_SIZE`, `_TOKEN_2022_ACCOUNT_TYPE_OFFSET`,
`_TOKEN_2022_EXTENSION_DATA_START`.

---

## 5. SPL Token (82-byte) Behavior Unchanged

- `_decode_spl_token_base_mint_state()` unchanged — still validates exactly 82 bytes + byte 45
- The SPL Token path in `_fetch_token_age_data()` still requires `len(raw_bytes) == 82`
- `TestSplTokenMintStateDecoding` (7 tests) unchanged and still pass
- The V2-2AL.1 fix only touches `_decode_token_2022_mint_state()` and associated tests

---

## 6. Tests Run

| Suite | Tests | Result |
|---|---|---|
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | 117 | PASS |
| `tests/test_v2_2x2_t2_token_age_evidence.py` | 82 | PASS |
| `tests/test_v2_2ag_observed_live_launch_tier.py` | 30 | PASS |

Warnings: LF→CRLF only. No whitespace errors.

---

## 7. Files Changed

| File | Change |
|---|---|
| `src/printer_v1/sources/solana_rpc_token_age.py` | Added 3 constants (`_SPL_TOKEN_ACCOUNT_SIZE`, `_TOKEN_2022_ACCOUNT_TYPE_OFFSET`, `_TOKEN_2022_EXTENSION_DATA_START`); replaced `_decode_token_2022_mint_state()` with 5-step validation using correct offsets (165/166) |
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | Updated imports (+3 constants); corrected `_make_token_2022_mint_bytes()` helper; replaced `TestToken2022MintStateDecoding` (11 → 13 tests using correct layout) |
| `docs/printer-v1-v2-2al-1-token-2022-extension-layout-repair.md` | This file |

---

## 8. Safety Confirmations

- No live RPC calls — all tests use fixture transports
- No new external dependencies — only stdlib `struct`
- Legacy SPL Token Mint path (82 bytes) unchanged and tested
- T2 unchanged — 82 T2 tests pass
- OBSERVED_LIVE_LAUNCH unchanged — 30 tier tests pass
- A3 not unlocked — unchanged
- No DB mutation, no memory generation, no retrieval
- No BUY/SELL/HOLD, paper decisions, positions, trades, audits, or PnL

---

## 9. Remaining Blockers

| Blocker | Status |
|---|---|
| Live network proof | NOT YET RETRIED — requires V2-2AL.2 (independent verification) then a live retry lane |
| Per-RPC-call Source Governor recording | DEFERRED (per-token model in use) |
| A3 not live | INTENTIONAL — requires successful live T3 proof |
| Staged/native 15m blocker | PARTIAL - DEFERRED, NOT RESOLVED |
| V2-3 | PAUSED |

---

## 10. Final Summary

```text
VERDICT: REPAIR_PROOF_PASS_WITH_BLOCKERS
ANCHOR: dfb76b6 Add V2-2AL bounded live T3 proof
ROOT_CAUSE: Decoder read AccountType from byte 82 (padding zero), not byte 165 (AccountType)
AUTHORITATIVE_LAYOUT: SPL token-2022 extension/mod.rs BASE_ACCOUNT_LENGTH=165, BASE_ACCOUNT_AND_TYPE_LENGTH=166
ACCOUNT_TYPE_OFFSET: 165 (was: 82)
EXTENSION_DATA_START: 166 (was: 83)
PADDING_REGION: bytes [82..165] = 83 zero bytes (Account::LEN - Mint::LEN)
MIN_VALID_TOKEN_2022_MINT_SIZE: 166 bytes
BYTE_82_STATUS: PADDING (zero expected) — no longer treated as AccountType
SPL_TOKEN_UNCHANGED: exact 82-byte path unaffected
FOCUSED_TESTS: 117 PASS (3 net new tests)
CROSS_CHECK_TESTS: 112 PASS (T2 + OBSERVED_LIVE_LAUNCH)
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
T2_UNCHANGED: CONFIRMED
OBSERVED_LIVE_LAUNCH_UNCHANGED: CONFIRMED
A3_STATUS: LOCKED (live proof required)
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
NEXT_LANE: V2-2AL.2 — Independent Token-2022 Layout Repair Verification
```
