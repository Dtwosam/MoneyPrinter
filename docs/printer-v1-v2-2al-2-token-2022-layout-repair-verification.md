# Printer V1 V2-2AL.2 Token-2022 Layout Repair Verification

Status: VERIFICATION ONLY
Lane: V2-2AL.2 - Independent Token-2022 Layout Repair Verification
Executor/model: Codex, standard/balanced mode
Target commit: `7aad246 Repair V2-2AL Token-2022 extension layout`
Verdict: `VERIFICATION_PASS_WITH_BLOCKERS`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This lane did not change code, change tests, run live RPC, run discovery, mutate
DBs, generate memory, activate retrieval, create paper decisions, unlock A3, or
unlock V2-3.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2al-bounded-live-t3-token-age-proof.md`
- `docs/printer-v1-v2-2al-1-token-2022-extension-layout-repair.md`

## Files Inspected

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `docs/printer-v1-v2-2al-1-token-2022-extension-layout-repair.md`
- Target commit file list from `git show --name-only --oneline 7aad246`

## Target Commit Scope

Target commit `7aad246` changed only:

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `docs/printer-v1-v2-2al-1-token-2022-extension-layout-repair.md`

No memory, retrieval, paper decision, paper trading, scheduler/runtime,
discovery, migration, BUY/SELL/HOLD, position, trade, audit, or PnL path was
part of the target commit scope.

## Authoritative Layout Result

Result: `PASS`

Static inspection confirms the repaired Token-2022 layout matches the lane's
authoritative contract:

| Region | Expected layout | Verified implementation |
| --- | --- | --- |
| Mint base | bytes `0-81` | `_SPL_TOKEN_MINT_SIZE = 82` |
| Zero padding | bytes `82-164` | padding slice `[82:165]` checked for all-zero bytes |
| AccountType | byte `165` | `_TOKEN_2022_ACCOUNT_TYPE_OFFSET = 165` |
| TLV data | byte `166+` | `_TOKEN_2022_EXTENSION_DATA_START = 166` |

The repaired decoder no longer reads AccountType from byte 82. Byte 82 is now
treated as the first padding byte, which is expected to be zero.

## Decoder Result

Result: `PASS`

Static inspection and focused tests confirm `_decode_token_2022_mint_state()`
now performs the expected five-step validation:

1. Validates the initialized 82-byte base Mint layout through
   `_decode_spl_token_base_mint_state()`.
2. Requires at least 166 bytes for a Token-2022 extended mint.
3. Requires the padding region `raw_bytes[82:165]` to be zero.
4. Requires AccountType at offset 165 to equal AccountType::Mint (`1`).
5. Walks TLV extension entries from byte 166 using 2-byte little-endian type,
   2-byte little-endian length, and extension data.

The test suite verifies:

- Valid minimal 166-byte Token-2022 mint accepted.
- Byte 82 equal to zero accepted as valid padding.
- Valid one-extension and two-extension TLV payloads accepted.
- Trailing zero padding after TLV entries accepted.
- Non-zero padding rejected.
- AccountType `0` and `2` at offset 165 rejected.
- Too-short 165-byte buffers rejected.
- TLV length overflow rejected.
- Partial non-zero TLV headers rejected.
- Uninitialized base mint fails before AccountType checks.
- Base mint shorter than 82 bytes fails before padding/AccountType checks.

Malformed and unsupported layouts still fail closed.

## Previous-Mint Regression Result

Result: `PASS_FOR_REPAIRED_FAILURE_CAUSE`

V2-2AL failed because the live selected mint returned a Token-2022-shaped
account where byte 82 was zero, and the previous decoder incorrectly treated
byte 82 as AccountType. The repaired decoder explicitly accepts byte 82 as
padding and reads AccountType from byte 165.

This means the V2-2AL mint would no longer fail solely because byte 82 is zero.
No live retry was performed in this verification lane, so the mint may still
fail later for a different legitimate reason such as malformed padding,
non-Mint AccountType at byte 165, TLV overflow, page-cap exhaustion, pruned
history, missing transaction, null block time, rate limit, or no matching
mint-init transaction.

## Legacy SPL Token Result

Result: `PASS`

The legacy SPL Token path remains exact and unchanged:

- `_SPL_TOKEN_MINT_SIZE = 82`.
- `_decode_spl_token_base_mint_state()` still validates minimum 82-byte Mint
  layout and `is_initialized` at byte 45.
- The live SPL Token owner path still requires `len(raw_bytes) == 82`.
- The existing `TestSplTokenMintStateDecoding` suite remains in place and
  passes.

The Token-2022 repair does not loosen SPL Token mint validation.

## Request Limits / Source Boundary Result

Result: `PASS`

Static inspection confirms the request limits and Source Governor boundary are
unchanged:

| Rule | Verified value |
| --- | --- |
| Max RPC operations per token | `_T3_MAX_REQUESTS_PER_TOKEN = 8` |
| Max signature pages | `_T3_MAX_SIGNATURE_PAGES = 3` |
| Max transaction calls | `_T3_MAX_TRANSACTION_CALLS = 3` |
| Max `getBlockTime` calls | `_T3_MAX_BLOCK_TIME_CALLS = 1` |
| Per-call timeout | `_T3_RPC_TIMEOUT_SECONDS = 10.0` |
| Retries | No retry loop added |
| Source Governor context | Adapter still requires governed context |
| Direct live activation | Adapter remains disabled by default and requires explicit transport |

No broad source activation was introduced by this verification lane.

## T2 / Observed Live Launch / A3 / Financial Locks

Result: `PASS`

Focused cross-check tests confirm:

- T2 token-age evidence remains unchanged.
- `OBSERVED_LIVE_LAUNCH` remains separate from T3 and still does not fabricate
  `token_created_at` or `token_age_seconds`.
- A3 remains locked unless real `token_age_seconds` exists.
- Pair age, `captured_at`, migration time, first trade time, and
  `OBSERVED_LIVE_LAUNCH` remain prohibited token-age fallbacks.

No retrieval, memory, paper decision, BUY/SELL/HOLD, paper position, trade,
audit, or PnL path was touched.

## Tests / Checks Run

- `python -m pytest tests/test_v2_2ak_t3_solana_rpc_token_age.py -q`
  - Result: `117 passed`
- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py tests/test_v2_2ag_observed_live_launch_tier.py -q`
  - Result: `112 passed`

Both test commands emitted the pre-existing pytest cache warning for
`.pytest_cache` path creation. The tests still passed.

## Remaining Blockers

- No live retry was performed in this verification lane.
- Successful T3 evidence from a real mint is still not proven.
- A3 remains locked until a later approved live proof produces valid
  `token_age_seconds` from T3 or another approved token-age tier.
- The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
- V2-3 remains paused.

## Verdict

`VERIFICATION_PASS_WITH_BLOCKERS`

The Token-2022 layout repair is verified independently. The corrected decoder
now follows the extended mint layout expected by V2-2AL.1, preserves the legacy
82-byte SPL Token path, fails closed on malformed Token-2022 layouts, and does
not weaken T2, `OBSERVED_LIVE_LAUNCH`, A3, Source Governor, request limits, or
financial locks.

## Exact Next Lane

`V2-2AL.3 - Bounded Live T3 Proof Retry`

The next lane may perform one bounded live retry under the existing constraints:
isolated proof DB only, public/free read-only Solana RPC only, no discovery to
find a token, no scheduler/runtime, no memory, no retrieval, no paper decisions,
no BUY/SELL/HOLD, no positions, no trades, no audits, no PnL, no A3 unlock, and
no V2-3 movement.
