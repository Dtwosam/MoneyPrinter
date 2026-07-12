# Solana SPL Token Program

**Status:** SB-2 CORE MODULE, DOCUMENTATION ONLY. SB-2.1 VERIFIED AND CORRECTED.

---

## 1. Purpose

This module documents the legacy SPL Token program's mint-account layout and
mint-initialization instructions as used by Printer V1 for token-age evidence
and safety context. It covers only the mint account and initialization paths;
it does not document token account transfers, burns, or other instructions.

---

## 2. Official Upstream Authorities

| Tier | Resource | Canonical URL | Verified date |
|---|---|---|---|
| A1 | Official SPL Token repository | `https://github.com/solana-program/token` | 2026-07-12 |
| A3 | SPL Token program documentation | `https://www.solana-program.com/docs/token` | 2026-07-12 |

**Key repository paths to pin in a later verification lane:**
- Mint state layout: `token/program/src/state.rs` (struct `Mint`)
- Initialize-mint instruction: `token/program/src/instruction.rs` (variants
  `InitializeMint`, `InitializeMint2`)
- Processor behavior: `token/program/src/processor.rs`

**Historical note:** the repository migrated from `github.com/solana-labs/
solana-program-library` to `github.com/solana-program/token`. SB-1 §3.1
says to avoid the archived `solana-labs/solana-program-library` path as the
canonical module authority. The new `solana-program/token` repository is
authoritative.

**Pinned upstream commit:** not pinned in SB-2.1; requires fetching the current
repository. Later verification lane should pin exact commit and file paths.
Status: `UNKNOWN_REQUIRES_RESEARCH` for the exact commit hash.

---

## 3. Last Verified Date and Version

- Verified: 2026-07-12
- Program generation: current deployed legacy SPL Token program
- Program ID: `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`
- Layout constants: `Mint::LEN = 82` bytes (confirmed by Printer implementation
  and cross-referenced against prior T3 work in V2-2AK)

---

## 4. Authority/Status Dimensions

| Dimension | Value |
|---|---|
| `upstream_lifecycle` | `ACTIVE` (legacy SPL Token program is maintained and deployed) |
| `printer_readiness` | `PARTIAL_WITH_BLOCKER` (T3 fixture-proven 132 tests; not positively live-proven; DB persistence gap V2-2AL.4B) |
| `printer_role` | `TOKEN_AGE` (mint layout and initializeMint evidence for T3); `SAFETY` (mint authority / freeze authority reads) |
| `access_policy` | `KEYLESS_PUBLIC` (mint layout decoding is local; RPC calls use keyless public endpoint) |
| `v1_permission` | `ALLOWED_GOVERNED` (governed read-only evidence only; no minting, transfer, or execution) |

---

## 5. Allowed Capabilities

- Read raw mint account bytes via `getAccountInfo` (base64 encoding) and decode
  the 82-byte `Mint` struct.
- Check account `owner` field against SPL Token program ID.
- Verify `is_initialized` flag.
- Read `mint_authority` (for safety checks) and `freeze_authority`.
- Detect `initializeMint` and `initializeMint2` instructions in parsed
  `getTransaction` responses for the exact requested mint.
- Use `getTokenLargestAccounts` and `getTokenSupply` for holder safety context.
- All uses: governed, read-only, bounded by Source Governor budgets.

---

## 6. Prohibited Capabilities

- No token creation, minting, transfers, approvals, burns, or freezes.
- No signing, wallet access, or transaction submission.
- No live execution or BUY/SELL/HOLD decisions.
- No retrieval activation. No paper positions or PnL.
- No treating a token-list or off-chain source's claim about SPL Token ownership
  as A1-tier evidence. Only on-chain `getAccountInfo.value.owner` is authoritative.

---

## 7. Authentication and Cost Model

- Authentication: none for reading mint state. `getAccountInfo` uses the public
  RPC endpoint (keyless). Local decoding requires no network call.
- Cost model: inherits from `solana-core-rpc-reference.md`. Each `getAccountInfo`
  call counts against the T3 request budget (`_T3_MAX_REQUESTS_PER_TOKEN = 8`).

---

## 8. Programs, Endpoints, Methods, and Request Contracts

### 8.1 Program Identity

| Item | Value | Authority |
|---|---|---|
| Program ID | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | A1: `github.com/solana-program/token` |
| Program type | Upgradeable BPF | A1 |
| Network | Solana mainnet and devnet | A1 |

### 8.2 Mint Account Layout (`Mint` struct, `Mint::LEN = 82` bytes)

The authoritative layout from the SPL Token program source (`state.rs`):

| Field | Offset | Size | Type | Description |
|---|---|---|---|---|
| `mint_authority` | 0 | 36 | `COption<Pubkey>` | 4-byte tag (0=None, 1=Some) + 32-byte pubkey |
| `supply` | 36 | 8 | `u64` LE | Total token supply |
| `decimals` | 44 | 1 | `u8` | Decimal places |
| `is_initialized` | 45 | 1 | `bool` | Must be 1 for valid mint |
| `freeze_authority` | 46 | 36 | `COption<Pubkey>` | 4-byte tag + 32-byte pubkey |
| Total | — | 82 | — | `Mint::LEN = 82` |

**`Mint::LEN = 82` bytes.** An SPL Token mint account must be exactly 82 bytes.
Any account whose owner is `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` with
a data length ≠ 82 is malformed and must fail T3 validation.

**`is_initialized` must be 1 (true).** An uninitialized mint account must fail T3.

### 8.3 Initialize-Mint Instructions

| Instruction | Discriminant index | Description |
|---|---|---|
| `InitializeMint` | 0 | First-generation initialize-mint; requires `rent_sysvar` account |
| `InitializeMint2` | 20 | Does not require `rent_sysvar`; otherwise equivalent for Printer's purposes |

In `jsonParsed` encoding, these appear as:
```json
{
  "parsed": {
    "type": "initializeMint",
    "info": {
      "mint": "<mint_pubkey>",
      "mintAuthority": "<authority>",
      "decimals": <int>,
      "freezeAuthority": "<authority_or_null>"
    }
  },
  "program": "spl-token",
  "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
}
```
or `"type": "initializeMint2"` for variant 20.

For compiled instructions, discriminant byte 0 = `InitializeMint`,
discriminant byte 20 = `InitializeMint2`. Full account layout differs between
variants but Printer's T3 focus is the `mint` account attribution, not full
instruction decoding.

**Pump.fun `create` CPI:** Pump's bonding-curve `create` instruction calls
SPL Token's `initializeMint` as an inner instruction (CPI). The `initializeMint`
appears in `meta.innerInstructions`, not in the top-level `instructions` array.
See `solana-transaction-instruction-parsing.md §8.3`.

---

## 9. Response and Field Semantics

- `getAccountInfo.value.owner`: must equal `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`
  for an SPL Token account.
- `getAccountInfo.value.data`: raw bytes (base64); must be decoded to the 82-byte
  layout above.
- Parsed `initializeMint.info.mint`: the mint address this instruction initialized.
  Must match the exact requested mint.
- `supply` field in the mint state: u64 little-endian; reflects current total supply
  as of the queried slot, not at creation time.
- `mint_authority` `COption` encoding: first 4 bytes encode the presence tag
  (little-endian `u32`; 0 = None, 1 = Some); next 32 bytes are the pubkey
  (ignored if tag is 0). A None mint authority means the mint is frozen (supply
  is fixed).

---

## 10. Nullable/Missing-Field Behavior

| Field | Null/missing behavior |
|---|---|
| `getAccountInfo.value` | null → account not found → T3 fail closed |
| Account owner ≠ SPL Token program ID | → T3 fail closed (wrong program) |
| Account data length ≠ 82 bytes | → T3 fail closed (malformed mint) |
| `is_initialized == 0` | → T3 fail closed (uninitialized mint) |
| `initializeMint.info.mint` ≠ requested mint | → T3 fail closed (wrong mint) |
| `mint_authority` tag = None | → No mint authority; valid for evidence; safety implication depends on context |
| `freeze_authority` tag = None | → No freeze authority; valid for evidence |

---

## 11. Rate Limits and Bounded-Use Rules

Inherits from `solana-core-rpc-reference.md §11`. The `getAccountInfo` call for
mint validation counts against the T3 budget. Current budget: 1 call for account
validation (included in `_T3_MAX_REQUESTS_PER_TOKEN = 8`).

Local mint-layout decoding (parsing the 82-byte struct) adds no network cost.

---

## 12. Evidence Strength

- Successful `initializeMint` or `initializeMint2` for the exact requested mint
  in a successful transaction with a valid non-future block time: **T3 evidence**.
- Mint state decoded from `getAccountInfo` (owner, size, initialized flag):
  **T3 prerequisite validation** — confirms the account is a valid, initialized
  SPL Token mint before walking signature history.
- `mint_authority` and `freeze_authority` reads from `getAccountInfo`:
  **safety context** (not an evidence tier for token age).
- `getTokenLargestAccounts` and `getTokenSupply`: **safety context** (not an
  evidence tier).

---

## 13. Normalization and Failure Rules

- Mint validation failure (wrong owner, wrong size, not initialized) sets
  `t3_failure_stage = "account_validation"` and preserves 8 failure provenance
  fields via `_pfail()`.
- Success path: if `initializeMint` is found with correct mint, successful
  transaction, and valid block time, the normalizer outputs `token_created_at`,
  `token_age_seconds`, `token_age_evidence_tier = "T3"`.
- A3 gate: `assign_bucket()` requires `token_age_seconds is not None`. Failure
  provenance never satisfies this gate.
- Source status on failure: `FAILED` or `MISSING_CRITICAL_DATA`.

---

## 14. Security/Redaction Rules

- RPC host redaction: see `solana-core-rpc-reference.md §14`.
- Mint address and program ID are public blockchain identifiers; they are safe
  to store in logs and DB rows.
- `mint_authority` and `freeze_authority` are public on-chain keys; no
  redaction needed, but they must never be treated as wallet private keys.
- Do not store instruction data bytes from compiled instructions unless they
  have been validated as non-sensitive.

---

## 15. Known Upstream Quirks

- **`COption` encoding:** Borsh-style `COption<Pubkey>` uses 4 bytes for the
  discriminant, not 1 bit. Some third-party tools incorrectly read this field.
  The Printer decoder must use the correct 4-byte tag at offset 0 for
  `mint_authority` and offset 46 for `freeze_authority`.
- **`supply` is not creation supply:** the `supply` field in `getAccountInfo`
  reflects the current total supply, not the supply at creation time. It changes
  as tokens are minted or burned.
- **Pump `create` CPI depth:** Pump's `create` instruction internally calls
  `initializeMint`. The `initializeMint` appears in inner instructions, not at
  the top level. See `solana-transaction-instruction-parsing.md §15`.
- **`initializeMint` vs `initializeMint2`:** both are valid initialization
  instructions; Printer accepts both. `initializeMint2` does not require the
  rent sysvar account and is more common in recent Pump deploys.

---

## 16. Known Printer Mistakes

| Mistake | Lane documented | Status |
|---|---|---|
| Token-2022 byte-82 misread (reading AccountType at byte 82 instead of byte 165) | V2-2AL.1 (`7aad246`), V2-2AL.2 (`5a4309e`) | Fixed. This mistake was in the Token-2022 decoder, not the SPL Token decoder, but the root cause (confusion between `Mint::LEN = 82` and `AccountType offset`) is worth preserving here as a cross-module lesson. |
| Compiled `initializeMint` decode not adopted | SB-2, SB-2.1 | Implementation gap; current tests cover only `jsonParsed` path |

---

## 17. Required Fixtures/Proofs

Before any new SPL Token path is adopted:

1. Existing 132 T3 fixture tests must remain passing
   (`tests/test_v2_2ak_t3_solana_rpc_token_age.py`).
2. 82 T2 fixture tests must remain passing (SPL Token does not change T2 path
   but any account-layout change would cross the same code).
3. Any compiled-instruction decode requires a dedicated test class proving exact
   mint attribution, mismatch rejection, and fail-closed behavior.
4. Pin exact SPL Token repository commit and file paths before adopting this
   module as implementation guidance.
5. V2-2AL.5 live proof required before T3 satisfies A3.

---

## 18. Code and DB Integration Points

**Adapter file:** `src/printer_v1/sources/solana_rpc_token_age.py`

**Key decoding functions:** inline mint-state validation within
`_fetch_token_age_data()`.

**Program ID constant:** defined in `solana_rpc_token_age.py` (search for
`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`).

**Safety use:** `src/printer_v1/sources/solana_rpc_holder.py` uses
`getTokenLargestAccounts` and `getTokenSupply` for holder concentration checks.

**Test files:**
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py` (132 tests)
- `tests/test_v2_2x2_t2_token_age_evidence.py` (82 T2 tests; cross-check)

**DB tables:** inherited from `solana-core-rpc-reference.md §18`. No
SPL-Token-specific DB tables beyond Source Governor and failure rows.

---

## 19. Unresolved Questions

| Item | Status |
|---|---|
| Exact upstream repo commit and file paths for SPL Token `state.rs`, `instruction.rs`, `processor.rs` | `UNKNOWN_REQUIRES_RESEARCH` — pin in later verification lane |
| Compiled `initializeMint` instruction decoding coverage | `DEFERRED` — not adopted; requires explicit future lane |
| `initializeMint` account ordering in compiled form | `UNKNOWN_REQUIRES_RESEARCH` — standard SPL Token position for mint account is index 0 in accounts list, but requires reverification from A1 source |
| SB-6 finality contract | `UNKNOWN_REQUIRES_RESEARCH` — reserved for SB-6 |

---

## 20. Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | SB-2: module authored; 20 sections, original structure | Claude Opus 4.8 / SB-2 |
| 2026-07-12 | SB-2.1: restructured to exact 20-section template; `Mint` struct layout pinned with field-level byte offsets; `Mint::LEN = 82` made explicit; `initializeMint`/`initializeMint2` discriminants documented; `COption<Pubkey>` encoding documented; jsonParsed vs compiled instruction shapes documented; cross-module note on Token-2022 byte-82 mistake added; status dimensions updated to SB-1 §6 vocabulary | Claude Sonnet 4.6 / SB-2.1 |
