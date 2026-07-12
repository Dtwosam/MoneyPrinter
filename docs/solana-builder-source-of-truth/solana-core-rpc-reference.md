# Solana Core RPC Reference

**Status:** SB-2 CORE MODULE, DOCUMENTATION ONLY. SB-2.1 VERIFIED AND CORRECTED.

---

## 1. Purpose

This module documents the read-only Solana JSON-RPC methods Printer V1 uses or
plans to use for evidence collection. Printer uses Solana RPC exclusively as a
governed evidence source — never for transaction execution, signing, or wallet
operations. The six methods covered here are the only in-scope RPC methods.

---

## 2. Official Upstream Authorities

| Tier | Resource | Canonical URL | Verified date |
|---|---|---|---|
| A3 | Solana RPC HTTP methods index | `https://solana.com/docs/rpc/http` | 2026-07-12 |
| A3 | `getAccountInfo` | `https://solana.com/docs/rpc/http/getaccountinfo` | 2026-07-12 |
| A3 | `getSignaturesForAddress` | `https://solana.com/docs/rpc/http/getsignaturesforaddress` | 2026-07-12 |
| A3 | `getTransaction` | `https://solana.com/docs/rpc/http/gettransaction` | 2026-07-12 |
| A3 | `getBlockTime` | `https://solana.com/docs/rpc/http/getblocktime` | 2026-07-12 |
| A3 | `getTokenLargestAccounts` | `https://solana.com/docs/rpc/http/gettokenlargestaccounts` | 2026-07-12 |
| A3 | `getTokenSupply` | `https://solana.com/docs/rpc/http/gettokensupply` | 2026-07-12 |
| A3 | Solana clusters and endpoints | `https://solana.com/docs/references/clusters` | 2026-07-12 |
| A3 | RPC overview and commitment | `https://solana.com/docs/rpc` | 2026-07-12 |

Pinned upstream commit: not applicable for hosted Solana RPC documentation.
No specific commit hash is pinnable for hosted docs. Later lanes should archive
doc snapshots or reference the Agave release that introduced any changed
behavior.

---

## 3. Last Verified Date and Version

- Verified: 2026-07-12
- Solana runtime generation: Agave / current mainnet
- API protocol: JSON-RPC 2.0 over HTTPS POST
- No specific version identifier in hosted Solana RPC docs

---

## 4. Authority/Status Dimensions

| Dimension | Value |
|---|---|
| `upstream_lifecycle` | `ACTIVE` |
| `printer_readiness` | `PARTIAL_WITH_BLOCKER` (T3 failure provenance must be preserved durably or in an explicit proof artifact before bounded live proof; live proof pending) |
| `printer_role` | `TOKEN_AGE` (T3 mint-age evidence); `SAFETY` (holder concentration context) |
| `access_policy` | `KEYLESS_PUBLIC` (public RPC endpoint; no API key required) |
| `v1_permission` | `ALLOWED_GOVERNED` (governed read-only evidence only; execution prohibited) |

---

## 5. Allowed Capabilities

- `getAccountInfo`: read mint account state (owner, data, size) for T3 validation
  and safety checks.
- `getSignaturesForAddress`: walk transaction history for a mint to find
  initialization signatures. Newest-first pagination only.
- `getTransaction`: retrieve a specific transaction by signature for instruction
  parsing (token-age evidence).
- `getBlockTime`: retrieve block timestamp for a slot as T3 block-time fallback.
- `getTokenLargestAccounts`: retrieve top holders for holder-concentration
  safety context.
- `getTokenSupply`: retrieve token supply data for safety and context.
- All methods: governed, read-only, bounded by Source Governor budgets.
- All methods: redact host information; report host-only in logs and audit rows.

---

## 6. Prohibited Capabilities

- No transaction construction, signing, simulation, or submission.
- No `sendTransaction`, `simulateTransaction`, or any write-path method.
- No wallet connection, private keys, or real fund movement.
- No BUY, SELL, or HOLD decisions.
- No retrieval activation. No paper positions or PnL.
- No scheduling or runtime expansion outside Central Scheduler approval.
- No Source Governor bypass. No independent direct RPC loop from any engine.
- No paid RPC tier dependency. Public endpoint or operator-approved free RPC only.
- No paid Helius tier. Helius free tier remains deferred (`REGISTERED_NOT_READY`).

---

## 7. Authentication and Cost Model

- Authentication: none required for the Solana public mainnet RPC endpoint.
- Cost: free public endpoint; subject to documented shared-endpoint limits.
- Public endpoint policy: official Solana cluster documentation describes these
  endpoints as shared public infrastructure and warns that limits may change.
  The limits independently verified in SB-2.3 are:
  - 100 requests per 10 seconds per IP.
  - 40 requests per 10 seconds per IP for one RPC method.
  - 40 concurrent connections per IP.
  - 40 connection attempts per 10 seconds per IP.
  - 100 MB transferred per 30 seconds per IP.
- Printer's Source Governor limits are stricter implementation budgets and do
  not replace upstream public RPC limits.
- Helius free tier (deferred): requires a free dashboard API key (sign-up at
  helius.dev); 1M credits/month; 10 RPC req/s. Not a paid dependency, but
  requires operator sign-up decision. Not a required dependency in V1.
- No API key must ever be stored in Printer payloads, logs, or DB rows.

---

## 8. Programs, Endpoints, Methods, and Request Contracts

### 8.1 Endpoint

**Official upstream (A3, SB-1/SB-2.1 verification date 2026-07-12):** Solana cluster docs listed `https://api.mainnet.solana.com`

**Current Printer implementation (A6):** `https://api.mainnet-beta.solana.com`

**Endpoint-policy conclusion:** official documentation and current Printer code
name different public mainnet endpoints. SB-2.2 classifies this as
`official documentation naming conflict / unresolved compatibility question`.
No SB-2.2 live endpoint test was run, so this module must not claim both
endpoints resolve. Future live proof must use an explicitly operator-approved,
free, read-only endpoint through Source Governor boundaries.

### 8.2 getAccountInfo

- **Method:** POST `{"jsonrpc":"2.0","id":<int>,"method":"getAccountInfo","params":["<pubkey>",{"encoding":"<enc>","commitment":"<level>"}]}`
- **Required parameters:** account pubkey (base58 string)
- **Optional parameters Printer uses:** `encoding` (Printer uses `"base64"` for
  raw mint-state decoding; `"jsonParsed"` for human-readable token accounts),
  `commitment`
- **Response:** `{"value": <AccountInfo>|null}`
- **`value` can be null** if the account does not exist at the queried slot.
- **AccountInfo fields:** `lamports` (u64), `owner` (pubkey string), `data`
  (varies by encoding), `executable` (bool), `rentEpoch` (u64)
- **Token-age use:** read raw mint account bytes (`base64`) for SPL Token / Token-2022
  layout validation. Does not return creation transaction time.
- **Safety use:** read `owner` to confirm token program identity; read account
  existence.

### 8.3 getSignaturesForAddress

- **Method:** POST `{"jsonrpc":"2.0","id":<int>,"method":"getSignaturesForAddress","params":["<pubkey>",{"limit":<n>,"before":"<sig>","until":"<sig>","commitment":"<level>"}]}`
- **Required parameters:** address pubkey
- **Optional parameters Printer uses:** `limit` (max 1000 per page, default 1000),
  `before` (exclusive - returns signatures older than this signature),
  `until` (boundary semantics `UNKNOWN_REQUIRES_RESEARCH` in SB-2.2), `commitment`
- **Pagination direction: NEWEST-FIRST.** The most recent signatures are
  returned first. To page backwards through history, pass the last seen
  signature as `before` in the next call.
- **Response:** array of `{signature, slot, err, memo, blockTime, confirmationStatus}`
- **`err` field:** null on successful transactions; non-null for failed transactions
- **`blockTime` field:** Unix timestamp (i64) or null
- **T3 use:** walk backwards from most recent to find the initialization signature.
  Stop at `_T3_MAX_SIGNATURE_PAGES = 3` pages (current Printer budget).
- **Pruning risk:** public RPC history is pruned. Mints older than the available
  history window will return an empty or truncated list.

### 8.4 getTransaction

- **Method:** POST `{"jsonrpc":"2.0","id":<int>,"method":"getTransaction","params":["<signature>",{"encoding":"jsonParsed","commitment":"<level>","maxSupportedTransactionVersion":0}]}`
- **Required parameters:** transaction signature (base58 string)
- **Optional parameters Printer uses:** `encoding` (Printer uses `"jsonParsed"`),
  `commitment`, `maxSupportedTransactionVersion` (required for v0/versioned
  transactions — must be set to `0` to avoid an error on versioned tx)
- **Response:** `null` if not found or pruned; otherwise transaction object
- **`getTransaction` may return null** (pruned history, not found).
- **Response fields:** `slot` (u64), `blockTime` (i64 or null), `transaction`
  (nested), `meta` (nullable)
- **`meta` can be null** on some responses.
- **`meta.err`:** null on success; non-null for failed transactions. A failed
  transaction cannot produce token-creation evidence.
- **`meta.innerInstructions`:** array or null. Inner instructions contain CPIs
  including SPL Token `initializeMint` from Pump `create` calls.
- **`blockTime` can be null.** Null block time fails closed for T3 evidence.
- **T3 use:** retrieve the specific transaction by signature and parse it for
  `initializeMint` or `initializeMint2` targeting the exact requested mint.
  Current Printer budget: `_T3_MAX_TRANSACTION_CALLS = 3`.
- **Version handling:** legacy transactions have no `version` field; v0
  transactions use address lookup tables (ALTs). Without
  `maxSupportedTransactionVersion: 0`, RPC returns an error for v0 transactions.

### 8.5 getBlockTime

- **Method:** POST `{"jsonrpc":"2.0","id":<int>,"method":"getBlockTime","params":[<slot_number>]}`
- **Required parameters:** slot number (u64)
- **Response:** Unix timestamp (i64) or `null`
- **`getBlockTime` may return null** for very recent or unpopulated slots.
- **T3 use:** fallback block-time retrieval when `blockTime` in `getTransaction`
  is null. Current Printer budget: `_T3_MAX_BLOCK_TIME_CALLS = 1`.

### 8.6 getTokenLargestAccounts

- **Method:** POST `{"jsonrpc":"2.0","id":<int>,"method":"getTokenLargestAccounts","params":["<mint_pubkey>",{"commitment":"<level>"}]}`
- **Required parameters:** mint pubkey (base58 string)
- **Optional parameters:** `commitment`
- **Response:** `{"value": [{"address":<pubkey>,"amount":<raw_str>,"decimals":<int>,"uiAmount":<float|null>,"uiAmountString":<str>}, ...]}`
- **Safety use:** top-holder context for concentration analysis. Not a token-age
  evidence source.

### 8.7 getTokenSupply

- **Method:** POST `{"jsonrpc":"2.0","id":<int>,"method":"getTokenSupply","params":["<mint_pubkey>",{"commitment":"<level>"}]}`
- **Required parameters:** mint pubkey (base58 string)
- **Optional parameters:** `commitment`
- **Response:** `{"value": {"amount":<raw_str>,"decimals":<int>,"uiAmount":<float|null>,"uiAmountString":<str>}}`
- **Safety use:** supply context. Not a token-age evidence source.

---

## 9. Response and Field Semantics

- All responses follow JSON-RPC 2.0: `{"jsonrpc":"2.0","id":<int>,"result":<data>}` on success or `{"jsonrpc":"2.0","id":<int>,"error":{"code":<int>,"message":<str>}}` on error.
- `blockTime` is a Unix timestamp in seconds (i64). Printer must reject any
  `blockTime` that is in the future relative to call time.
- `slot` is a monotonically increasing u64 slot counter; it is NOT the same as
  block height or timestamp.
- Account `data` encoding: `base64` returns raw bytes as a base64 string; `base58`
  is limited to small accounts; `jsonParsed` returns structured JSON for known
  program accounts.
- Transaction instruction `parsed` field is present only for well-known programs
  (SPL Token, System Program); other programs return `compiled` instructions.
- `meta.innerInstructions` contains CPI calls in order of execution. Each inner
  instruction carries the calling instruction's index and the CPI instruction list.

---

## 10. Nullable/Missing-Field Behavior

| Field | Null/missing behavior |
|---|---|
| `getAccountInfo.value` | null if account does not exist; Printer fails T3 closed |
| `getTransaction` return | null if not found or pruned; Printer fails T3 closed |
| `getTransaction.meta` | null on some responses; Printer fails T3 closed if meta absent |
| `getTransaction.blockTime` | null is valid upstream; Printer tries `getBlockTime` fallback, then fails closed |
| `getBlockTime` return | null for unpopulated slots; Printer fails T3 closed |
| `getSignaturesForAddress` empty array | no history available; Printer fails T3 closed |
| `meta.err` non-null | failed transaction; Printer must not accept as T3 evidence |

Printer's fail-closed contract: any null, missing, future, or unresolvable
required field must leave `token_created_at = None`, `token_age_seconds = None`,
and no T3 tier. Failure provenance may be preserved separately (see §13).

---

## 11. Rate Limits and Bounded-Use Rules

**Current documented public-endpoint limits:**
- Maximum 100 requests per 10 seconds per IP.
- Maximum 40 requests per 10 seconds per IP for one RPC method.
- Maximum 40 concurrent connections per IP.
- Maximum 40 connection attempts per 10 seconds per IP.
- Maximum 100 MB transferred per 30 seconds per IP.

Solana states that these shared public-endpoint limits are subject to change.
They are upstream limits, not Printer operating budgets.

**Current Printer T3 Source Governor budgets (A6, from `solana_rpc_token_age.py`):**
- `_T3_MAX_REQUESTS_PER_TOKEN = 8` (total RPC operations per mint)
- `_T3_MAX_SIGNATURE_PAGES = 3` (getSignaturesForAddress pages)
- `_T3_MAX_TRANSACTION_CALLS = 3` (getTransaction calls)
- `_T3_MAX_BLOCK_TIME_CALLS = 1` (getBlockTime calls)
- `_T3_RPC_TIMEOUT_SECONDS = 10.0` (per-request timeout)
- Zero retries. No endpoint rotation.

These are implementation facts, not permission to expand live coverage.
Expanding any budget requires an explicit future implementation and proof lane.

---

## 12. Evidence Strength

| Method | Evidence type | Evidence tier |
|---|---|---|
| `getAccountInfo` | Mint-account validation (owner, size) | T3 prerequisite; no age by itself |
| `getSignaturesForAddress` | Signature history walk | T3 locator (locator ≠ proof) |
| `getTransaction` + init instruction + blockTime | Mint initialization proof | T3 (approved) |
| `getBlockTime` | Block timestamp fallback | T3 fallback; null fails closed |
| `getTokenLargestAccounts` | Holder concentration | Safety context; no evidence tier |
| `getTokenSupply` | Supply data | Safety context; no evidence tier |

**Locator vs proof (SB-1 Rule 5):** A signature returned by
`getSignaturesForAddress` is a locator. It becomes T3 proof only when
`getTransaction` independently confirms the exact requested mint appears as
a successful `initializeMint`/`initializeMint2` with a valid block time.

T3 is evidence tier 3. It is below T1 and T2 in the evidence hierarchy. Printer's
adopted T3 evidence contract uses `finalized` commitment for mint validation,
signature history, and transaction inspection. A successful T3 proof does not
itself activate A3; A3 remains a separate paused lane.

---

## 13. Normalization and Failure Rules

- **Success path:** normalized result includes `token_created_at`, `token_age_seconds`,
  `token_age_evidence_tier = "T3"`, the original 15 T3 provenance fields, and
  explicit `t3_commitment = finalized` plus `t3_finality_status = finalized`.
- **Failure path:** normalized result includes 8 T3 failure provenance fields
  (via `_pfail()` closure in `_fetch_token_age_data()`): `t3_requested_mint`,
  `t3_rpc_host_redacted`, `t3_rpc_methods_attempted`, `t3_request_ids`,
  `t3_pages_fetched`, `t3_tx_calls_attempted`, `t3_block_time_calls_attempted`,
  `t3_failure_stage`. Failure provenance must never populate success fields.
- **Failure-provenance preservation requirement:** the 8 failure provenance
  fields are observability hardening. They do not block direct-signature T3
  design or fixture proof. Before bounded live proof, these fields must be
  preserved either durably in the DB or explicitly in the proof artifact.
- **Source status:** FAILED, STALE, MISSING_CRITICAL_DATA.
- **A3 gate:** `assign_bucket()` requires `token_age_seconds is not None`.
  Failure provenance never satisfies this gate. A3 remains locked.

---

## 14. Security/Redaction Rules

- RPC host is redacted to hostname only before storage (`redacted_rpc_host()`
  helper in `solana_rpc_token_age.py`).
- No URL path, query string, API key, credential, or token may appear in any
  stored payload, log, or DB row.
- Example: `https://api.mainnet-beta.solana.com/v1?apikey=secret` becomes
  `api.mainnet-beta.solana.com`.
- All Source Governor traces must use the redacted host.
- Printer must not log raw request URLs containing sensitive components.

---

## 15. Known Upstream Quirks

- **Mainnet endpoint name discrepancy:** prior Solana docs verification listed
  `api.mainnet.solana.com`; Printer uses `api.mainnet-beta.solana.com`. SB-2.2
  did not run a live endpoint compatibility test, so endpoint compatibility
  remains `UNKNOWN_REQUIRES_RESEARCH`.
- **`blockTime` null on recent transactions:** `getTransaction` can return a
  valid transaction with `blockTime = null` for very recent slots. This is
  expected upstream behavior, not an error.
- **History pruning:** the Solana public RPC does not guarantee full history.
  Older mints may return empty or incomplete signature lists.
- **Versioned transaction requirement:** without `maxSupportedTransactionVersion: 0`,
  `getTransaction` returns an error for v0/versioned transactions rather than
  the transaction data.
- **`meta.innerInstructions` ordering:** inner instructions are indexed by the
  top-level instruction that triggered the CPI. The index, not position, maps a
  CPI call to its parent instruction.

---

## 16. Known Printer Mistakes

| Mistake | Lane fixed | Fix |
|---|---|---|
| Mainnet endpoint mismatch: Printer uses `api.mainnet-beta.solana.com`; prior upstream docs verification showed `api.mainnet.solana.com` | No production fix in SB-2.2; documented as implementation gap | Treat as official documentation naming conflict / unresolved compatibility question until a later approved live-test or official source resolves it |
| T3 failure paths returned bare `{failure_type, failure_message}` with no partial trace | V2-2AL.4A (`11c6cf1`) | `_pfail()` closure now threads 8 audit fields into every failure return |
| T3 failure provenance survived normalizer but not DB persistence | V2-2AL.4B (`538ce82`) verified gap | Fixed by migration 027 and governed failure recording in the real T3 lane |

---

## 17. Required Fixtures/Proofs

Before live T3 evidence is accepted by A3:

1. All 132 T3 fixture tests pass (`tests/test_v2_2ak_t3_solana_rpc_token_age.py`).
2. 112 T2 + OBSERVED_LIVE_LAUNCH cross-check tests pass.
3. Failure provenance preserved either durably in DB rows or explicitly in the
   bounded proof artifact.
4. Bounded live proof passes on an approved mint
   (`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`).
5. Finalized commitment and exact transaction attribution pass. A3 activation
   remains separately operator-approved and is not implied by T3 evidence.

No live RPC call should be made without meeting all of the above.

---

## 18. Code and DB Integration Points

**Adapter file:** `src/printer_v1/sources/solana_rpc_token_age.py`

**Request kinds:** `mint_creation_time_reference`

**Key constants:**
- `_T3_MAX_REQUESTS_PER_TOKEN = 8`
- `_T3_MAX_SIGNATURE_PAGES = 3`
- `_T3_MAX_TRANSACTION_CALLS = 3`
- `_T3_MAX_BLOCK_TIME_CALLS = 1`
- `_T3_RPC_TIMEOUT_SECONDS = 10.0`
- `_T3_FAIL_PROVENANCE_FIELDS` (8 audit fields)

**Supporting files:**
- `src/printer_v1/sources/governed_execution.py` — Source Governor execution
- `src/printer_v1/sources/recording.py` — Source Governor recording
- `src/printer_v1/sources/contracts.py` — `NormalizedSourceResult`, evidence contracts
- `src/printer_v1/sources/solana_rpc_holder.py` — holder-concentration use of
  `getTokenLargestAccounts` and `getTokenSupply`

**DB tables:**
- `printer_source_failures` — failure audit rows (failure provenance must be
  DB-durable or explicitly preserved in the bounded proof artifact before live
  proof)
- Source Governor tables (governed execution records)

**Test files:**
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py` (132 tests)
- `tests/test_post_rc_real_evidence_collection.py`

---

## 19. Unresolved Questions

| Item | Status |
|---|---|
| Official current public mainnet endpoint (`mainnet` vs `mainnet-beta`) | `UNKNOWN_REQUIRES_RESEARCH` - no live compatibility claim in SB-2.2 |
| Solana public RPC rate limits for the public endpoint | Resolved in SB-2.3: numeric shared-endpoint limits are published but explicitly subject to change |
| T3 commitment level and minimum-finality rule | Resolved for T3: `finalized`; A3 remains separately paused |
| Failure-provenance preservation path | DB-durable in governed failure rows through migration 027 |
| Bounded live proof on approved mint | Passed on 2026-07-12; see real T3 closeout |
| History pruning behavior under heavy load | `UNKNOWN_REQUIRES_RESEARCH` — behavior not formally documented for public endpoint |

---

## 20. Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | SB-2: module authored; 19 sections, original structure | Claude Opus 4.8 / SB-2 |
| 2026-07-12 | SB-2.1: restructured to exact 20-section template; method-level request/response contracts added for all 6 methods; mainnet endpoint gap documented; failure provenance and DB persistence blocker clarified; status dimensions updated to SB-1 section 6 vocabulary | Claude Sonnet 4.6 / SB-2.1 |
| 2026-07-12 | SB-2.2: corrected public RPC endpoint wording, removed unsupported endpoint-resolution claim, changed `until` inclusivity to `UNKNOWN_REQUIRES_RESEARCH`, separated upstream public-RPC warnings from Printer Source Governor budgets, and corrected T3 failure-provenance sequencing | Codex standard/balanced / SB-2.2 |

| 2026-07-12 | SB-2.3: independently verified public RPC numeric limits and preserved endpoint naming as an official-documentation conflict | Manual independent verification / SB-2.3 |
