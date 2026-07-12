# Solana Transaction Instruction Parsing

**Status:** SB-2 CORE MODULE, DOCUMENTATION ONLY. SB-2.1 VERIFIED AND CORRECTED.

---

## 1. Purpose

This module documents how Printer must reason about Solana transaction, instruction,
and inner-instruction evidence when parsing `getTransaction` responses. It defines
the precise shapes, failure conditions, and attribution requirements for token-age
evidence. Direct-signature T3 is the primary planned use; the current T3 path
uses `getSignaturesForAddress` history walking.

---

## 2. Official Upstream Authorities

| Tier | Resource | Canonical URL | Verified date |
|---|---|---|---|
| A3 | Solana transaction JSON structures | `https://solana.com/docs/rpc/json-structures` | 2026-07-12 |
| A3 | `getTransaction` reference | `https://solana.com/docs/rpc/http/gettransaction` | 2026-07-12 |
| A3 | Solana transaction concepts | `https://solana.com/docs/core/transactions` | 2026-07-12 |
| A3 | Versioned transactions | `https://solana.com/docs/advanced/versions` | 2026-07-12 |
| A1 | SPL Token program (initializeMint instruction) | `https://github.com/solana-program/token` | 2026-07-12 |
| A1 | Pump.fun bonding-curve program (create instruction with CPI) | `https://github.com/pump-fun/pump-public-docs` | 2026-07-12 |

**Address lookup table (ALT) reference:** exact upstream ALT documentation path
pending pin. Solana docs cover ALTs under `https://solana.com/docs/advanced/lookup-tables`.
Treat this as `UNKNOWN_REQUIRES_RESEARCH` for the specific file-level pin.

Pinned upstream commit: not pinned for hosted Solana RPC documentation. For
SPL Token program instruction definitions, see `solana-spl-token-program.md §2`.

---

## 3. Last Verified Date and Version

- Verified: 2026-07-12
- Solana runtime generation: Agave / current mainnet
- Transaction encoding: `jsonParsed` (as used by Printer T3)
- Versioned transaction format: v0 with ALTs is current on-chain format

---

## 4. Authority/Status Dimensions

| Dimension | Value |
|---|---|
| `upstream_lifecycle` | `ACTIVE` (versioned transaction behavior may evolve with future Agave releases) |
| `printer_readiness` | `READY_BOUNDED` (finalized history-walk T3 path deterministic-test and bounded-live proven; A3 remains separate and paused) |
| `printer_role` | `TOKEN_AGE` (parsing `initializeMint`/`initializeMint2` evidence for T3) |
| `access_policy` | `KEYLESS_PUBLIC` (decoding of `getTransaction` JSON responses requires no separate auth) |
| `v1_permission` | `ALLOWED_GOVERNED` (read-only decoding only; no execution) |

---

## 5. Allowed Capabilities

- Decode `getTransaction` JSON responses in `jsonParsed` encoding.
- Parse top-level `instructions` and `meta.innerInstructions` for the exact
  requested mint's `initializeMint` or `initializeMint2` instruction.
- Validate transaction success (`meta.err == null`).
- Read `blockTime` from the transaction response.
- Read `slot` from the transaction response.
- Resolve program IDs and instruction types from `jsonParsed` structured data.
- Fail closed on any unsupported shape, missing field, or ambiguous attribution.

---

## 6. Prohibited Capabilities

- No transaction building, construction, or modification.
- No signing, simulation, or submission.
- No wallet access, private keys, or real fund movement.
- No BUY, SELL, or HOLD decisions.
- No retrieval activation. No paper positions or PnL.
- Inner instructions are accepted only after exact requested-mint attribution.
- Compiled instructions are accepted only after strict token-program, account
  index, base58 opcode, and exact requested-mint resolution.
- No inferring creation time from anything other than an on-chain initialization
  instruction with a valid block time.

---

## 7. Authentication and Cost Model

- Authentication: none. Parsing is local decoding of RPC response JSON.
- Cost model: inherits from `solana-core-rpc-reference.md`. The `getTransaction`
  call is governed under the T3 budget. Decoding is pure computation.

---

## 8. Programs, Endpoints, Methods, and Request Contracts

### 8.1 Transaction Request

See `solana-core-rpc-reference.md §8.4` for the full `getTransaction` contract.
Key points for instruction parsing:

- Use `encoding: "jsonParsed"` to receive structured instruction data.
- Set `maxSupportedTransactionVersion: 0` to support v0 (versioned) transactions.
  Without this, versioned transactions return an error instead of data.
- A `null` response means not found or pruned. Fail closed.

### 8.2 Legacy vs Versioned Transactions

**Legacy transactions:**
- No `version` field in the response.
- `transaction.message.accountKeys`: array of static account pubkey strings.
- Account index 0 to N-1 map directly to `accountKeys[index]`.
- No ALTs.

**Versioned (v0) transactions:**
- `version: 0` in the response.
- `transaction.message.accountKeys`: static account keys only.
- `transaction.meta.loadedAddresses.writable`: loaded writable ALT accounts.
- `transaction.meta.loadedAddresses.readonly`: loaded readonly ALT accounts.
- Full account list for index resolution: `accountKeys + writable + readonly`
  (in that order). ALT-loaded accounts have higher indices than static keys.

### 8.3 Instruction Shapes

| Shape | Source field | Parse method |
|---|---|---|
| Parsed (known programs) | `instruction.parsed.type`, `instruction.parsed.info` | Read `.type` and `.info` fields directly |
| Compiled (unknown programs) | `instruction.programIdIndex`, `instruction.accounts`, `instruction.data` | Resolve program via index; decode data from base58 |
| Inner instructions | `meta.innerInstructions[].instructions[]` | Same shapes; indexed by parent instruction index |
| CPI (inner) from Pump `create` | `meta.innerInstructions[<pump_ix_idx>].instructions[]` | Contains SPL Token `initializeMint` as an inner instruction |

### 8.4 Program-ID Resolution

- For parsed instructions: `instruction.programId` is present as a string.
- For compiled instructions: resolve via `accountKeys[instruction.programIdIndex]`.
  For v0 transactions, the full account list (§8.2) must be used.

### 8.5 Account-Index Resolution

- Compiled instruction `accounts` is an array of indices into the full account list.
- For legacy transactions: index into `accountKeys` directly.
- For v0 transactions: index into `accountKeys + writable + readonly`.
- Exact requested-mint attribution requires resolving the mint account from the
  instruction's account list, not assuming a fixed position.

### 8.6 Slot and BlockTime

- `slot` is always present in a non-null `getTransaction` response.
- `blockTime` may be null even when slot is present. Null block time fails
  closed. If null, try `getBlockTime(slot)` as a fallback (budget: 1 call).
- Reject any block time that is in the future relative to call time.

---

## 9. Response and Field Semantics

- `transaction.message.instructions[]`: top-level instructions, one per entry in
  the transaction's instruction list.
- `meta.innerInstructions[]`: list of `{index, instructions[]}` pairs; `index`
  is the top-level instruction that triggered the CPIs.
- Parsed instruction: `{program, programId, parsed: {type, info: {...}}}`.
- Compiled instruction: `{programIdIndex, accounts: [int,...], data: "<base58>"}`.
- `meta.err`: null on success; JSON object on failure. Never use a failed
  transaction as token-age evidence.
- `meta.logMessages`: optional array of program log strings. Not used for
  evidence attribution; log parsing is error-prone.
- `version`: absent for legacy; `0` for v0.

---

## 10. Nullable/Missing-Field Behavior

| Field | Null/missing behavior |
|---|---|
| `getTransaction` return | null → fail closed; token age unknown |
| `meta` | null → fail closed |
| `meta.err` non-null | failed transaction → fail closed |
| `meta.innerInstructions` | null or missing → treat as empty; check top-level only |
| `blockTime` | null → try getBlockTime fallback; fallback null → fail closed |
| `slot` | always present in a non-null response |
| `version` | absent → legacy transaction; `0` → v0 |
| `meta.loadedAddresses` | absent on legacy transactions → no ALT accounts |

---

## 11. Rate Limits and Bounded-Use Rules

Inherits from `solana-core-rpc-reference.md §11`. Current Printer budget:
- `_T3_MAX_TRANSACTION_CALLS = 3` per token
- `_T3_MAX_BLOCK_TIME_CALLS = 1` per token
- 10-second timeout per request

Parsing is local computation; it adds no network cost beyond the `getTransaction`
call.

---

## 12. Evidence Strength

- A successfully parsed `initializeMint` or `initializeMint2` for the exact
  requested mint in a successful transaction with a valid non-future block time
  constitutes **T3 evidence** (evidence tier 3).
- T3 is below T1 and T2 in the evidence hierarchy.
- T3 uses finalized evidence and has passed one bounded live proof. This does
  not activate A3; A3 remains a separate paused lane.
- Pair age, capture time, migration time, first trade time, and
  `OBSERVED_LIVE_LAUNCH` cannot be substituted for T3 evidence.
- PumpPortal-provided signatures are **locator evidence only** (SB-1 Rule 5).
  The PumpPortal signature is not proof until `getTransaction` independently
  confirms the exact initialization instruction.

---

## 13. Normalization and Failure Rules

- **Success path:** parsed instruction confirms exact mint, valid block time,
  successful transaction → outputs `token_created_at`, `token_age_seconds`,
  `token_age_evidence_tier = "T3"`, the 15 original success provenance fields,
  and explicit finalized commitment/finality fields.
- **Failure conditions (all fail closed):**
  - `getTransaction` returns null.
  - `meta` is null or `meta.err` is non-null.
  - No `initializeMint`/`initializeMint2` found for the exact requested mint.
  - Mint in instruction does not match requested mint.
  - Malformed or unresolved compiled instruction/account index.
  - More than one matching initialization instruction or transaction.
  - Unresolved account lookup table index.
  - `blockTime` is null or in the future.
  - Page-cap or request-budget exhaustion.
  - Pruned history (empty signature list).
- **Failure provenance:** 8 audit fields captured via `_pfail()` closure; see
  `solana-core-rpc-reference.md §13`.
- **A3 gate:** failure provenance must never populate success fields. A3 remains
  locked until approved T3 or T1/T2 evidence provides real `token_age_seconds`.

---

## 14. Security/Redaction Rules

- Parsing is local; no additional secrets are involved beyond RPC host.
- See `solana-core-rpc-reference.md §14` for RPC host redaction rules.
- Transaction signatures may appear in audit logs as locator evidence only.
  They must not be treated as authorization tokens.
- Never store raw instruction data containing private key material. Solana
  transactions cannot contain private keys in instruction data; if ever observed,
  it is a compromise signal, not a legitimate field.

---

## 15. Known Upstream Quirks

- **ALT account-index ordering:** the full account list for index resolution in
  v0 transactions is `accountKeys + writable ALT accounts + readonly ALT accounts`.
  This ordering is critical for correct program-ID and target-mint resolution.
- **Inner instruction index vs position:** `meta.innerInstructions[i].index` is
  the index of the top-level instruction that triggered the CPI, not the array
  position in `meta.innerInstructions`.
- **Pump `create` as CPI:** Pump.fun's `create` instruction is a CPI that calls
  SPL Token's `initializeMint` as an inner instruction. The top-level Pump program
  call appears in `instructions[]`; the `initializeMint` appears in
  `meta.innerInstructions[]`.
- **jsonParsed coverage:** `jsonParsed` only returns structured `parsed` objects
  for well-known programs (SPL Token, System Program, etc.). For unknown programs
  (e.g., a custom or obscure CPI caller), the instruction falls back to compiled
  format even in `jsonParsed` encoding.
- **Pruned history depth:** the public RPC prunes transaction history. The depth
  available varies by validator and load. Older mints may be unreachable.

---

## 16. Known Printer Mistakes

| Mistake | Lane documented | Status |
|---|---|---|
| Current T3 history walk relies on `getSignaturesForAddress` pagination rather than direct-signature lookup | SB-1 §13 | Bounded history-walk T3 is live-proven; direct-signature lookup remains a future efficiency improvement. |
| T3 path did not handle v0/versioned transaction ALT account resolution | SB-2, SB-2.1 | Fixed in the real T3 lane with compiled/ALT and inner-instruction deterministic coverage. |
| Page-cap exhaustion for older mints (V2-2AL.3) | V2-2AL.3 (`f0935f0`) | Known live failure mode; documented in V2-2AL.4 readiness review |

---

## 17. Required Fixtures/Proofs

Before any parser expansion is adopted:

1. Existing 132 T3 fixture tests must remain passing.
2. New parser branches (compiled instruction decode, ALT resolution, versioned tx)
   require dedicated test classes proving exact requested-mint attribution,
   failure on mint mismatch, and fail-closed on malformed shapes.
3. Failure provenance must remain durable in governed failure rows.
4. The bounded live proof must preserve every downstream lock.
5. A3 remains a separate operator-approved lane even after T3 succeeds.

---

## 18. Code and DB Integration Points

**Adapter file:** `src/printer_v1/sources/solana_rpc_token_age.py`

**Key functions:**
- `_fetch_token_age_data()`: orchestrates the T3 pipeline including history walk
  and instruction parsing.
- `_pfail()`: closure that captures T3 failure provenance.
- `_extract_failure_provenance()`: copies only `_T3_FAIL_PROVENANCE_FIELDS` into
  normalizer output.
- `normalize_solana_rpc_token_age_response()`: normalizer entry point.

**Test files:** `tests/test_v2_2ak_t3_solana_rpc_token_age.py` and
`tests/test_real_t3_token_age_evidence.py`.

**DB tables:**
- `printer_source_failures` — failure audit rows (failure provenance must be
  DB-durable or explicitly preserved in the bounded proof artifact before live
  proof)
- Source Governor tables

**No additional parser file exists.** All parsing is inline in
`solana_rpc_token_age.py`. Any future instruction parser should be extracted
into a dedicated module to improve testability.

---

## 19. Unresolved Questions

| Item | Status |
|---|---|
| Direct-signature T3 design | `DEFERRED` - undesigned; intended sequence is source-stack modules, SB-6 direct-signature design, approved implementation and fixture proof, bounded live proof, then A3 readiness review |
| v0/versioned transaction ALT account resolution | Implemented and deterministic-test proven for static plus loaded writable and readonly ordering |
| Compiled instruction `initializeMint` decode | Implemented with strict token-program, base58 opcode, account-index, and exact-mint checks |
| History walk depth for mints older than public RPC retention | `UNKNOWN_REQUIRES_RESEARCH` — pruning behavior not formally documented |
| Inner instruction coverage for non-Pump CPI callers | `UNKNOWN_REQUIRES_RESEARCH` — Pump `create` is the known case; other callers require explicit research |
| T3 finality contract | Resolved for T3: `finalized`; A3 remains separately paused |

---

## 20. Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | SB-2: module authored; 20 sections, original structure | Claude Opus 4.8 / SB-2 |
| 2026-07-12 | SB-2.1: restructured to exact 20-section template; legacy vs versioned transaction paths documented; ALT account-index resolution rules added; inner instruction structure (CPI from Pump create) documented; known Printer mistakes (ALT gap, direct-signature undesigned) added; status dimensions updated to SB-1 section 6 vocabulary | Claude Sonnet 4.6 / SB-2.1 |
| 2026-07-12 | SB-2.2: corrected T3 sequencing so failure-provenance persistence is observability hardening, not a blocker for direct-signature T3 design or fixture proof; preserved proof-time provenance requirement | Codex standard/balanced / SB-2.2 |
