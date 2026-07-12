# Solana Token-2022 Program

**Status:** SB-2 CORE MODULE, DOCUMENTATION ONLY. SB-2.1 VERIFIED AND CORRECTED.

---

## 1. Purpose

This module documents the Token-2022 (Token Extensions) program's extended
mint-account layout, AccountType discriminant, TLV extension structure, and
initialization instructions as used by Printer V1 for token-age evidence.
The layout verified here is authoritative for the T3 decoder as repaired in
V2-2AL.1 and verified in V2-2AL.2. SB-1 requires this module to avoid the
archived `solana-labs/solana-program-library` path; the canonical authority is
`github.com/solana-program/token-2022`.

---

## 2. Official Upstream Authorities

| Tier | Resource | Canonical URL | Verified date |
|---|---|---|---|
| A1 | Official Token-2022 repository | `https://github.com/solana-program/token-2022` | 2026-07-12 |
| A3 | Token-2022 program documentation | `https://www.solana-program.com/docs/token-2022` | 2026-07-12 |

**Key repository paths to pin in a later verification lane:**
- Extension layout and `AccountType` constants: `program-2022/src/extension/mod.rs`
  (confirmed as the layout source from V2-2AL.1 repair; historical path was
  `solana-labs/solana-program-library/blob/master/token/program-2022/src/extension/mod.rs`)
- Mint state: `program-2022/src/state.rs`
- Initialization instructions: `program-2022/src/instruction.rs`

**Canonical repository:** `github.com/solana-program/token-2022`. The archived
`github.com/solana-labs/solana-program-library` path must not be used as the
canonical module authority per SB-1 §3.1.

**Pinned upstream commit:** not pinned in SB-2.1; requires fetching the current
repository at `solana-program/token-2022`. Status: `UNKNOWN_REQUIRES_RESEARCH`.

The V2-2AL.1 repair (`7aad246`) derived the layout from the SPL library source
in the historical `solana-labs` path. The layout constants are consistent across
the repository migration.

---

## 3. Last Verified Date and Version

- Verified: 2026-07-12
- Program generation: current deployed Token-2022 program
- Program ID: `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`
- Layout repair: V2-2AL.1 (`7aad246`), independently verified V2-2AL.2 (`5a4309e`)
- Layout constants: `BASE_ACCOUNT_LENGTH = 165`, `BASE_ACCOUNT_AND_TYPE_LENGTH = 166`
  (from `extension/mod.rs`, confirmed in V2-2AL.1)

---

## 4. Authority/Status Dimensions

| Dimension | Value |
|---|---|
| `upstream_lifecycle` | `ACTIVE` (Token-2022 is deployed and maintained) |
| `printer_readiness` | `PARTIAL_WITH_BLOCKER` (T3 layout repair verified; not positively live-proven; DB persistence gap V2-2AL.4B) |
| `printer_role` | `TOKEN_AGE` (extended mint layout validation for T3); `SAFETY` (mint authority / freeze authority in extended layout) |
| `access_policy` | `KEYLESS_PUBLIC` (mint layout decoding is local; RPC calls use keyless public endpoint) |
| `v1_permission` | `ALLOWED_GOVERNED` (governed read-only evidence only; no minting or execution) |

---

## 5. Allowed Capabilities

- Read raw extended mint account bytes via `getAccountInfo` (base64) and decode
  using the verified 5-step layout.
- Check account `owner` field against Token-2022 program ID.
- Verify base mint fields (bytes 0–81), zero padding (bytes 82–164),
  `AccountType` discriminant (byte 165), and TLV extension headers (byte 166+).
- Detect `initializeMint` and `initializeMint2` instructions in `jsonParsed`
  `getTransaction` responses for the exact requested mint.
- Fail closed on any malformed, unexpected, or unsupported extension layout.
- All uses: governed, read-only, bounded by Source Governor budgets.

---

## 6. Prohibited Capabilities

- No token creation, minting, transfers, approvals, burns, freezes, or
  extension modifications.
- No signing, wallet access, or transaction submission.
- No live execution or BUY/SELL/HOLD decisions.
- No retrieval activation. No paper positions or PnL.
- No broadening the safety interpretation of Token-2022 extensions beyond what
  current Printer tests prove.
- No assuming extension semantics imply a specific safety classification.

---

## 7. Authentication and Cost Model

- Authentication: none for reading mint state. `getAccountInfo` uses the public
  RPC endpoint (keyless). Local decoding requires no network call.
- Cost model: inherits from `solana-core-rpc-reference.md`. Each `getAccountInfo`
  call for Token-2022 mint validation counts against the T3 request budget.

---

## 8. Programs, Endpoints, Methods, and Request Contracts

### 8.1 Program Identity

| Item | Value | Authority |
|---|---|---|
| Program ID | `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` | A1: `github.com/solana-program/token-2022` |
| Program type | Upgradeable BPF | A1 |
| Network | Solana mainnet and devnet | A1 |

### 8.2 Extended Mint Account Layout (authoritative from V2-2AL.1 + V2-2AL.2)

The full verified layout for a Token-2022 extended mint account:

| Region | Byte range | Size | Description |
|---|---|---|---|
| Base SPL Token mint | `[0, 82)` | 82 bytes | Identical to SPL Token `Mint` struct (see `solana-spl-token-program.md §8.2`) |
| Padding | `[82, 165)` | 83 bytes | Zero-filled padding; `Account::LEN - Mint::LEN = 165 - 82 = 83` |
| `AccountType` | `[165]` | 1 byte | Discriminant: `0` = `Uninitialized`, `1` = `Mint`, `2` = `Account` |
| TLV extension data | `[166, ...)` | variable | TLV-encoded extension entries (see §8.3) |

**Minimum valid extended mint length: 166 bytes** (`BASE_ACCOUNT_AND_TYPE_LENGTH = 166`
from `extension/mod.rs`). An account with fewer than 166 bytes cannot be a valid
Token-2022 extended mint and must fail closed.

**`AccountType` at byte 165 must be `1` (Mint).** Values `0` (Uninitialized) or
`2` (Account) must fail closed.

**Byte 82 is padding (expected to be zero), NOT AccountType.** This was the
historical Printer bug repaired in V2-2AL.1 (`7aad246`): the decoder was reading
AccountType at byte 82 (the first padding byte) instead of byte 165.

### 8.3 TLV Extension Header Format

Each TLV entry in the extension data region (`[166, ...)`) has the form:

| Field | Size | Type | Description |
|---|---|---|---|
| Type | 2 bytes | `u16` LE | Extension type discriminant |
| Length | 2 bytes | `u16` LE | Byte length of the extension data body |
| Data | `length` bytes | bytes | Extension-specific data |

A valid TLV walk must:
1. Start at byte 166.
2. Read 4-byte header (type + length).
3. Skip `length` bytes of body.
4. Repeat until the account data is exhausted.
5. Fail closed if the remaining bytes are insufficient for a complete header
   (partial header) or if the declared length would overflow the account data.

Unsupported extension types are acceptable only if the TLV walk remains
structurally valid and the base mint/AccountType checks pass.

### 8.4 Initialize-Mint Instructions

Token-2022 uses the same instruction variants as SPL Token (`initializeMint`,
`initializeMint2`) with additional Token-2022-specific variants for extension
initialization. Printer T3 recognizes `initializeMint` and `initializeMint2`
as token-age evidence; additional extension-specific initialization instructions
are not used as T3 evidence sources.

In `jsonParsed` encoding:
```json
{
  "parsed": {
    "type": "initializeMint",
    "info": {
      "mint": "<mint_pubkey>",
      "mintAuthority": "<authority>",
      "decimals": <int>
    }
  },
  "program": "spl-token-2022",
  "programId": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
}
```

The `program` field is `"spl-token-2022"` to distinguish from legacy SPL Token.

---

## 9. Response and Field Semantics

- `getAccountInfo.value.owner`: must equal `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`
  for a Token-2022 account.
- `getAccountInfo.value.data`: raw bytes (base64); must be decoded using the
  extended layout above.
- Account data length must be ≥ 166 bytes for a valid extended mint.
- Padding bytes 82–164 must all be zero. Non-zero padding fails closed.
- `AccountType` at byte 165 must be `1` (Mint).
- TLV walk (bytes 166+) must be structurally valid.
- `initializeMint.info.mint` in parsed form: must match the exact requested mint.

---

## 10. Nullable/Missing-Field Behavior

| Field | Null/missing behavior |
|---|---|
| `getAccountInfo.value` | null → account not found → T3 fail closed |
| Account owner ≠ Token-2022 program ID | → T3 fail closed (wrong program) |
| Account data length < 166 bytes | → T3 fail closed (truncated extended mint) |
| Non-zero byte in padding region [82, 165) | → T3 fail closed (invalid padding) |
| `AccountType` at byte 165 ≠ 1 | → T3 fail closed (not a mint account) |
| Partial TLV header (< 4 bytes remaining) | → T3 fail closed (malformed TLV) |
| TLV length overflows account data | → T3 fail closed (TLV length overflow) |
| `initializeMint.info.mint` ≠ requested mint | → T3 fail closed (wrong mint) |
| `meta.err` non-null in transaction | → T3 fail closed (failed transaction) |
| `blockTime` null or future | → T3 fail closed |

---

## 11. Rate Limits and Bounded-Use Rules

Inherits from `solana-core-rpc-reference.md §11`. The `getAccountInfo` call for
Token-2022 mint validation counts against the same T3 budget as SPL Token
validation. Local decoding adds no network cost.

---

## 12. Evidence Strength

- Successful `initializeMint` or `initializeMint2` for the exact requested mint
  in a successful transaction with valid block time: **T3 evidence** (same tier
  as SPL Token T3 evidence).
- Token-2022 extended-mint layout validation via `getAccountInfo`: **T3
  prerequisite** — validates account type and structure before history walk.
- Extension data in the TLV region: **not used as T3 evidence**. Layout
  validity is a gate, not an evidence source.
- Safety context from `mint_authority` / `freeze_authority` within the base
  mint region: same as SPL Token safety context.

---

## 13. Normalization and Failure Rules

- **5-step validation before evidence acceptance:**
  1. Verify account owner = Token-2022 program ID.
  2. Verify data length ≥ 166 bytes.
  3. Verify padding bytes 82–164 are all zero.
  4. Verify `AccountType` at byte 165 = 1 (Mint).
  5. Verify TLV walk from byte 166 is structurally valid.
- **Any step failure:** `t3_failure_stage = "account_validation"` via `_pfail()`;
  fail closed; 8 failure provenance fields preserved.
- **Success path after validation:** proceed to signature history walk and
  transaction parsing (same normalizer path as SPL Token).
- **A3 gate:** same as SPL Token. Failure provenance never satisfies the gate.

---

## 14. Security/Redaction Rules

- Same as `solana-core-rpc-reference.md §14`. RPC host redacted to hostname only.
- Token-2022 extension data may include arbitrary byte payloads in TLV bodies.
  These must not be logged or stored without sanitization. Extension bodies
  are structurally validated (length check) but their content is not inspected
  by Printer beyond structural TLV walk.

---

## 15. Known Upstream Quirks

- **`AccountType` position:** byte 165 (index 165), not byte 82. This is the
  root cause of the historical Printer bug. The padding region from 82 to 164
  is expected to be all zeros; confusing padding byte 82 with `AccountType` was
  the exact bug.
- **TLV ordering:** extensions in the TLV region are not required to appear in
  any specific order by the program. Printer's TLV walk only validates structure,
  not semantic content or extension ordering.
- **Non-zero padding as signal:** while valid Token-2022 mints must have zero
  padding, some very early or malformed mints from before the layout was
  standardized may have non-zero padding. These fail closed in Printer, which is
  the correct conservative behavior.
- **Account size growth:** Token-2022 extensions can increase account size beyond
  the base 166 bytes. Valid TLV data ends at the actual account data boundary.
- **`spl-token-2022` vs `spl-token` in jsonParsed:** the `program` field in
  parsed instructions distinguishes Token-2022 from legacy SPL Token. Both can
  issue `initializeMint` instructions, but the `programId` is different.

---

## 16. Known Printer Mistakes

| Mistake | Lane documented/fixed | Description |
|---|---|---|
| `AccountType` read at byte 82 instead of byte 165 | V2-2AL.1 (`7aad246`) repair; V2-2AL.2 (`5a4309e`) verification | Byte 82 is the first padding byte (expected zero). `AccountType` is at byte 165 (`BASE_ACCOUNT_LENGTH = Account::LEN = 165`). This caused T3 to fail for all Token-2022 mints in the V2-2AL live proof. |
| Test fixture for Token-2022 used wrong byte offset | V2-2AL.1 (`7aad246`) | `_make_token_2022_mint_bytes()` repaired to produce 83 correct padding bytes and 166+ total. `TestToken2022MintStateDecoding` replaced with correct tests including `test_v2_2al_byte_82_is_zero_and_is_valid_padding`. |

---

## 17. Required Fixtures/Proofs

Before any Token-2022 parser change is adopted:

1. All 132 T3 fixture tests must pass (includes Token-2022 test class
   `TestToken2022MintStateDecoding`).
2. Repaired tests must cover:
   - Legacy SPL Token exact 82-byte path unchanged.
   - Token-2022 extended layout accepted (≥ 166 bytes).
   - Non-zero padding rejected.
   - Wrong `AccountType` rejected.
   - TLV length overflow rejected.
   - Partial TLV header rejected.
   - T3 failure provenance remains fail-closed.
3. Pin exact upstream commit and file path in `solana-program/token-2022` before
   adopting this module as implementation guidance.
4. V2-2AL.5 live proof must pass on approved mint before T3 satisfies A3.

---

## 18. Code and DB Integration Points

**Adapter file:** `src/printer_v1/sources/solana_rpc_token_age.py`

**Key functions:**
- `_decode_token_2022_mint_state()`: 5-step validated decoder (rewritten in V2-2AL.1)
- `_make_token_2022_mint_bytes()`: test fixture helper (repaired in V2-2AL.1)

**Constants added in V2-2AL.1:**
- `_SPL_TOKEN_ACCOUNT_SIZE = 165` (Account::LEN = BASE_ACCOUNT_LENGTH)
- `_TOKEN_2022_ACCOUNT_TYPE_OFFSET = 165` (AccountType byte position)
- `_TOKEN_2022_EXTENSION_DATA_START = 166` (TLV start position)

**Program ID constants:** `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` (SPL Token)
and `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` (Token-2022) defined in
`solana_rpc_token_age.py`.

**Test file:** `tests/test_v2_2ak_t3_solana_rpc_token_age.py` (132 tests;
class `TestToken2022MintStateDecoding` covers the repaired layout).

**DB tables:** inherited from `solana-core-rpc-reference.md §18`.

---

## 19. Unresolved Questions

| Item | Status |
|---|---|
| Exact upstream commit and file path for `extension/mod.rs` in `solana-program/token-2022` | `UNKNOWN_REQUIRES_RESEARCH` — pin in later verification lane; historical path was `solana-labs/solana-program-library/token/program-2022/src/extension/mod.rs` |
| Extension type registry (valid `u16` type codes and their semantics) | `DEFERRED` — not needed for T3 structural walk; relevant only if future lanes interpret extension content |
| Very early Token-2022 mints with non-standard padding behavior | `UNKNOWN_REQUIRES_RESEARCH` — fail-closed is the conservative behavior; extent of affected mints unknown |
| SB-6 finality contract | `UNKNOWN_REQUIRES_RESEARCH` — reserved for SB-6 |
| Token-2022 extension-specific `initializeMint` variants | `UNKNOWN_REQUIRES_RESEARCH` — current T3 accepts only `initializeMint`/`initializeMint2`; other extension-init instructions are not evaluated |

---

## 20. Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | SB-2: module authored; 20 sections, original structure | Claude Opus 4.8 / SB-2 |
| 2026-07-12 | SB-2.1: restructured to exact 20-section template; layout byte ranges made explicit with table; minimum 166-byte requirement stated explicitly; TLV header format (2-byte type + 2-byte length) documented; 5-step validation sequence documented; V2-2AL.1/V2-2AL.2 repair verified and cross-referenced; `BASE_ACCOUNT_LENGTH = 165` and `BASE_ACCOUNT_AND_TYPE_LENGTH = 166` cited from `extension/mod.rs`; `AccountType` = 1 (Mint) requirement explicit; status dimensions updated to SB-1 §6 vocabulary; `UNKNOWN_REQUIRES_RESEARCH` for upstream commit pin preserved | Claude Sonnet 4.6 / SB-2.1 |
