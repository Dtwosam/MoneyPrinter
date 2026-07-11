# Printer V1 V2-2AJ T3 Solana RPC Token-Age Evidence Design

**Lane:** V2-2AJ
**Type:** Design only — no code, no tests, no RPC calls, no DB mutations
**Verdict:** `DESIGN_COMPLETE_WITH_BLOCKERS`
**Date:** 2026-07-11
**Executor:** Claude Sonnet 4.6

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

A3 remains locked. The staged/native 15m blocker remains `PARTIAL - DEFERRED,
NOT RESOLVED`. No RPC calls were made in this lane.

---

## 1. Source Stack Read

| Document | Role |
|---|---|
| `AGENTS.md` | Highest authority |
| `docs/printer-v1-clean-master-spec.md` | Master specification |
| `docs/printer-v1-memory-growth-build-order-v2.md` | V2 roadmap |
| `docs/printer-v1-v2-2ai-t3-solana-rpc-token-age-readiness-audit.md` | T3 readiness audit; candidate method; provenance requirements |

Architecture precedent inspected:

- `src/printer_v1/sources/solana_rpc_holder.py` — existing RPC adapter pattern
- `src/printer_v1/sources/registry.py` — existing `solana_rpc` source definition

Prior-lane anchors confirmed:

| Anchor | Commit | Content |
|---|---|---|
| V2-2AI readiness audit | prior | T3 readiness; candidate RPC method; 8-request cap; provenance requirements |
| V2-2AG tier implementation | `5c88f26` | OBSERVED_LIVE_LAUNCH implemented; T2 unchanged |
| V2-2AF design | `d976fe1` | OBSERVED_LIVE_LAUNCH design; A3 locked |

---

## 2. Goal and Scope

T3 is a governed Solana RPC enrichment path that derives `token_created_at` from
on-chain mint-initialization evidence for tokens that were NOT observed through
the PumpPortal live stream (where T2 would apply).

T3 is specifically useful for tokens discovered through GeckoTerminal,
DexScreener, or other pair-centric sources that provide pair age but not token
creation time. It allows Printer to distinguish true new launches from STNP
(same-token, new-pair) resurfacing without depending on pair age as a proxy.

Scope of this design lane:
- Define the source contract
- Define the allowed RPC method set
- Define exact per-token request limits
- Define evidence acceptance and rejection rules
- Define provenance fields
- Define all token-age boundary confirmations
- Define future implementation plan

This design does NOT:
- Change any code
- Add tests
- Make RPC calls
- Unlock A3
- Unlock V2-3

---

## 3. Source Contract

### 3.1 Source name and request kind

| Item | Value |
|---|---|
| Source name | `solana_rpc` |
| Request kind | `mint_creation_time_reference` |
| Existing source registry entry | `solana_rpc` already registered |
| Change required in registry | add `"mint_creation_time_reference"` to `allowed_request_kinds` |
| `enabled_by_default` | `False` |
| `requires_governor_context` | `True` |
| `fixture_transport_only` | `False` (live RPC allowed via bounded transport) |
| `supports_network_execution` | `True` |
| `read_only` | `True` |

### 3.2 Existing registry entry (for reference)

```python
"solana_rpc": SourceDefinition(
    source_name="solana_rpc",
    purpose="Solana onchain reference",
    dependency_type="free_or_user_supplied",
    requires_paid_plan=False,
    supports_solana=True,
    allowed_request_kinds=(
        "onchain_reference",
        "mint_account_reference",
        "pool_reference",
        "holder_concentration_reference",
        # V2-2AK will add:
        # "mint_creation_time_reference",
    ),
    default_rate_limit_per_minute=30,
    stale_after_seconds=120,
    retry_after_seconds=60,
    ...
)
```

The implementation lane (V2-2AK) adds `"mint_creation_time_reference"` to the
existing tuple. The rate limit (30/min) and stale threshold (120s) apply to the
new request kind as-is. No new registry entry is needed.

### 3.3 Source Governor boundary

All T3 RPC calls must go through `execute_source_request_with_governor()` with:
- A valid `SourceAdapterContext` with `governor_approved = True`
- `execution_path == GOVERNOR_ONLY_EXECUTION_PATH`
- Source request row recorded in `printer_source_requests` for every call
- Source response row recorded when evidence is complete and clean
- Source failure row recorded for every failure case

No memory engine, discovery engine, parser, or selection engine may call Solana
RPC directly.

### 3.4 RPC endpoint contract

| Item | Value |
|---|---|
| Default endpoint | `https://api.mainnet-beta.solana.com` |
| Operator override | allowed; operator-supplied free read-only endpoint |
| Paid archive node | NOT allowed — must degrade gracefully if unavailable |
| Helius free tier | allowed as optional operator-supplied endpoint |
| Host redaction | RPC host must be redacted in provenance output |
| Method | HTTP POST, JSON-RPC 2.0 |
| Request timeout | 10.0 seconds per call |
| Retries | 0 — fail closed on first failure |
| 429 behavior | record source failure `solana_rpc_token_age_rate_limited`; leave token age unknown |

---

## 4. Allowed RPC Methods

The T3 path may issue the following JSON-RPC methods only. No other methods
are permitted, including transaction-sending, account-writing, or metered
premium-only methods.

| Method | Purpose | Required/Optional | Max calls per token |
|---|---|---|---|
| `getAccountInfo` | Confirm mint account exists and is owned by SPL Token or Token-2022 program | **Required** — first step | 1 |
| `getSignaturesForAddress` | Walk backward through mint address history to find earliest available signature | **Required** | 3 (one per page) |
| `getTransaction` | Inspect candidate transaction for mint-initialization instruction | **Required** | 3 |
| `getBlockTime` | Optional fallback: query slot block time if transaction `blockTime` is null | Optional | 1 |

---

## 5. Exact Per-Token Request Limits

### 5.1 Request budget

| Parameter | Limit | Rationale |
|---|---|---|
| Max total RPC requests per token | **8** | 1 account + 3 sig pages + 3 tx + 1 blocktime |
| Max `getAccountInfo` calls | 1 | Only validate the target mint once |
| Max `getSignaturesForAddress` pages | 3 | Budget for new tokens (< 48h old); fail closed if history exceeds |
| Signatures per page | 20 | Narrow window; recent tokens have few sigs |
| Max total signatures inspected per page walk | 60 | 3 pages × 20 |
| Max signatures tried as mint-init candidates | 5 | From the oldest available page |
| Max `getTransaction` calls | 3 | Try at most 3 candidate signatures |
| Max `getBlockTime` calls | 1 | Fallback only |
| Per-call timeout | 10 seconds | Hard cutoff; no extension |
| Retries per call | 0 | Fail closed |

### 5.2 Budget enforcement

If any step hits its call cap before mint-initialization evidence is found, T3
fails closed with `solana_rpc_token_age_budget_exhausted`. `token_created_at`,
`token_age_seconds`, and `token_age_evidence_tier` remain `None` / absent.

No automatic fallback to pair age, `captured_at`, migration time, or
`OBSERVED_LIVE_LAUNCH`. The token's age stays unknown.

### 5.3 Timeout policy

Each individual RPC call has its own 10-second timeout. If a call times out:
- Record source failure `solana_rpc_token_age_transport_error`
- Do not retry
- Fail closed

The 10-second timeout per call was chosen to match the existing Solana RPC
holder path (`SOLANA_RPC_TIMEOUT_SECONDS = 10.0`) for consistency.

---

## 6. Evidence Pipeline

### 6.1 Step 1: Mint account validation (`getAccountInfo`)

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": <request_id>,
  "method": "getAccountInfo",
  "params": [
    "<token_mint_address>",
    {"encoding": "base64", "commitment": "confirmed"}
  ]
}
```

**Accept condition (all must be true):**
1. Response `result.value` is not null
2. `result.value.owner` equals `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`
   (SPL Token) or `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` (Token-2022)
3. `result.value.data` has length consistent with an SPL Mint account layout
   (82 bytes for SPL Token, ≥165 bytes for Token-2022 base extension)

**Reject condition:**
- `result.value` is null → `solana_rpc_token_age_account_not_found`
- owner is neither Token nor Token-2022 program → `solana_rpc_token_age_not_a_mint`
- data length inconsistent with Mint layout → `solana_rpc_token_age_not_a_mint`

### 6.2 Step 2: Earliest signature discovery (`getSignaturesForAddress`)

**Goal:** Find the oldest available signature for the mint address. This is the
likely mint-initialization transaction.

**Strategy:**
- The `getSignaturesForAddress` API returns signatures in reverse chronological
  order (most recent first).
- Paginate backward (using `before` cursor from the last entry of each page)
  until the response returns fewer than `limit` results — indicating we've
  reached the beginning of history for this address.
- Once the end of history is found (page length < page size), the last entry
  on the last page is the oldest signature: the mint-initialization candidate.
- If the page cap (3) is reached before finding the end, fail closed.

**Request (first page):**
```json
{
  "jsonrpc": "2.0",
  "id": <request_id>,
  "method": "getSignaturesForAddress",
  "params": [
    "<token_mint_address>",
    {"limit": 20, "commitment": "confirmed"}
  ]
}
```

**Request (subsequent pages, using `before` cursor):**
```json
{
  "jsonrpc": "2.0",
  "id": <request_id>,
  "method": "getSignaturesForAddress",
  "params": [
    "<token_mint_address>",
    {"limit": 20, "before": "<last_signature_from_previous_page>", "commitment": "confirmed"}
  ]
}
```

**Accept conditions:**
- Response is a non-empty list of signature records
- If list length < 20: this is the last page; take the last N entries (up to 5)
  as mint-init candidates (oldest first = likely the init tx)
- If list length == 20 AND pages used < 3: fetch next page with `before` cursor
- If list length == 20 AND pages used == 3: page cap reached → fail closed

**Reject conditions:**
- Empty first page → `solana_rpc_token_age_no_signatures`
- Page cap (3) reached without finding the end of history →
  `solana_rpc_token_age_page_cap_exhausted`

**Mint-init candidate selection:**
From the oldest available page, try the last 1–5 entries (oldest signatures)
as mint-initialization candidates. Attempt `getTransaction` for each, in
ascending slot order, until one proves to be an init or all candidates are
exhausted.

### 6.3 Step 3: Transaction inspection (`getTransaction`)

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": <request_id>,
  "method": "getTransaction",
  "params": [
    "<candidate_signature>",
    {"encoding": "jsonParsed", "commitment": "confirmed", "maxSupportedTransactionVersion": 0}
  ]
}
```

**Accept conditions (all must be true for T3):**
1. `result` is not null
2. `result.meta.err` is null (transaction succeeded — failed init does not create the mint)
3. `result.blockTime` is not null (or fallback to Step 4)
4. `result.transaction.message.accountKeys` contains the requested mint address
5. At least one instruction satisfies the mint-initialization evidence rule:
   - Program ID = SPL Token (`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`)
     or Token-2022 (`TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`)
   - Instruction type = `initializeMint` or `initializeMint2`
     (from `result.transaction.message.instructions[i].parsed.type`)
   - `result.transaction.message.instructions[i].parsed.info.mint` or equivalent
     first-account field equals the requested mint address

**Reject conditions:**
- `result` is null → `solana_rpc_token_age_transaction_not_found`
- `result.meta.err` is non-null (failed transaction) → reject this signature, try next
- No instruction matches mint-initialization for the requested mint →
  `solana_rpc_token_age_no_init_instruction` (if all candidates exhausted)
- Instruction mint account does not match requested mint →
  `solana_rpc_token_age_mint_mismatch`
- `result.blockTime` is null → attempt Step 4 fallback once

**On transaction success:** record `slot`, `blockTime` (if present),
`signature`, instruction type, token program. Proceed to evidence derivation.

### 6.4 Step 4: Block time fallback (`getBlockTime`) — optional

**Trigger:** Only when Step 3's `getTransaction` returns a valid
mint-initialization transaction BUT `result.blockTime` is null.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": <request_id>,
  "method": "getBlockTime",
  "params": [<slot>]
}
```

**Accept condition:** `result` is a positive integer Unix timestamp

**Reject conditions:**
- `result` is null → `solana_rpc_token_age_null_block_time`; fail closed
- `result` is negative or zero → invalid; fail closed
- `result` is in the future relative to `captured_at` → `solana_rpc_token_age_future_block_time`; fail closed

### 6.5 Step 5: Evidence derivation

When all prior steps succeed, derive and populate:

| Field | Value | Source |
|---|---|---|
| `token_created_at` | ISO-8601 UTC from accepted `blockTime` | `datetime.fromtimestamp(block_time, tz=UTC).isoformat()` |
| `token_age_seconds` | `(captured_at_dt - token_created_at_dt).total_seconds()` | Must be ≥ 0 |
| `token_age_evidence_tier` | `"T3"` | Set explicitly by T3 normalizer |

These three fields flow through the existing parser `NORMALIZED_FIELDS` path
exactly as T2 evidence would.

---

## 7. Evidence Acceptance Rules — Summary Table

| Rule | Condition | Required |
|---|---|---|
| Mint account must exist | `getAccountInfo` result not null | Yes |
| Account must be a mint | owner = Token or Token-2022 program | Yes |
| Signature history must be reachable | Page end found within 3 pages | Yes |
| Transaction must exist | `getTransaction` result not null | Yes |
| Transaction must have succeeded | `meta.err` is null | Yes |
| Instruction type | `initializeMint` or `initializeMint2` | Yes |
| Instruction target mint | must match requested `token_mint` | Yes |
| Block time must be valid | non-null, positive, not future | Yes |
| Block time must be derivable | from `blockTime` or `getBlockTime` fallback | Yes |
| `token_age_seconds` must be non-negative | derived age ≥ 0 | Yes |

Any single requirement failing causes T3 to fail closed. All three output
fields remain `None` / absent.

---

## 8. Failure Taxonomy

| Failure code | Trigger |
|---|---|
| `solana_rpc_token_age_account_not_found` | `getAccountInfo` result is null |
| `solana_rpc_token_age_not_a_mint` | Account owner is not Token/Token-2022, or data too short |
| `solana_rpc_token_age_rate_limited` | HTTP 429 on any request |
| `solana_rpc_token_age_transport_error` | Network error, timeout, or connection failure |
| `solana_rpc_token_age_no_signatures` | First `getSignaturesForAddress` page is empty |
| `solana_rpc_token_age_page_cap_exhausted` | 3 pages exhausted without reaching history end |
| `solana_rpc_token_age_history_pruned` | Signatures available but history appears truncated (not at beginning) |
| `solana_rpc_token_age_transaction_not_found` | `getTransaction` returns null for all candidate signatures |
| `solana_rpc_token_age_no_init_instruction` | No accepted transaction contains an `initializeMint`/`initializeMint2` instruction for the requested mint |
| `solana_rpc_token_age_mint_mismatch` | Instruction found but targets a different mint address |
| `solana_rpc_token_age_null_block_time` | `blockTime` null in transaction AND `getBlockTime` fallback also null |
| `solana_rpc_token_age_future_block_time` | Block time is after `captured_at` |
| `solana_rpc_token_age_budget_exhausted` | Total request cap (8) hit before evidence established |
| `solana_rpc_token_age_malformed_response` | JSON parse failure or unexpected response shape |

---

## 9. Provenance Fields

T3 evidence must carry a complete provenance record in candidate metadata so
the evidence chain can be audited without re-running the RPC calls.

### 9.1 Per-evidence provenance (included in `candidate_metadata_json`)

| Field | Value |
|---|---|
| `t3_requested_mint` | Token mint address that was enriched |
| `t3_rpc_host_redacted` | Redacted RPC host (e.g., `api.mainnet-beta.solana.com` → `<REDACTED>`) |
| `t3_rpc_methods_attempted` | List of RPC methods used, in order |
| `t3_request_ids` | List of JSON-RPC request IDs for audit correlation |
| `t3_pages_fetched` | Number of `getSignaturesForAddress` pages used |
| `t3_signatures_inspected` | Count of signatures on the oldest page that were tried |
| `t3_accepted_signature` | The signature whose transaction confirmed mint init |
| `t3_accepted_slot` | The Solana slot of the accepted transaction |
| `t3_block_time_raw` | Raw `blockTime` integer value (Unix timestamp) |
| `t3_block_time_source` | `"getTransaction"` or `"getBlockTime"` (which method provided the time) |
| `t3_instruction_type` | `"initializeMint"` or `"initializeMint2"` |
| `t3_token_program` | `"spl_token"` or `"token_2022"` |
| `t3_derived_token_created_at` | ISO-8601 UTC string derived from `t3_block_time_raw` |
| `t3_derived_token_age_seconds` | Float seconds from `token_created_at` to `captured_at` |
| `t3_captured_at` | `captured_at` value used as reference time for age derivation |

### 9.2 How provenance is stored

The `t3_*` provenance fields are carried in the normalized candidate dict as
opaque metadata. They pass through the existing `extract_candidate_metadata()`
function into `candidate_metadata_json` during selection batch persistence.

No new DB columns are required — `candidate_metadata_json` already stores
arbitrary metadata as a JSON blob.

The provenance fields do NOT appear in `NORMALIZED_FIELDS` (they are not
selection-relevant) but they MUST be added to `_METADATA_FIELDS` in
`selection_batch.py` so they survive to `candidate_metadata_json`. This is the
same pattern as `pair_age_context_label`.

### 9.3 Failure provenance

When T3 fails, the source failure row (in `printer_source_failures`) must carry:
- `failure_type` — one of the failure codes from Section 8
- `failure_message` — human-readable explanation
- `source_name = "solana_rpc"`
- `request_kind = "mint_creation_time_reference"`

The provenance fields above may be partially populated in the source failure
message or metadata to aid debugging, but no `token_created_at` or T3 tier
may be populated from a failure path.

---

## 10. Token-Age Boundary Confirmations

These invariants are hard rules. All are preserved unchanged by this design.

| Boundary | Rule |
|---|---|
| `pair_age_seconds` / `pair_created_at` | Never becomes `token_created_at` or `token_age_seconds`. Pair age remains T4 diagnostic context only. |
| `captured_at` | Never becomes `token_created_at`. It is only the observation reference time used to compute `token_age_seconds`. |
| Migration time | A PumpPortal `pumpfun_migration_stream` event's timestamp is migration time, not creation time. T3 does not use migration events. |
| First trade time | The first transaction seen for a pair address may be a trade, not the mint init. T3 requires explicit `initializeMint`/`initializeMint2` evidence. |
| `OBSERVED_LIVE_LAUNCH` | This tier proves a live launch event was observed; it does not populate `token_created_at` or `token_age_seconds`. T3 is independent of and does not interact with `OBSERVED_LIVE_LAUNCH`. |
| `token_created_at` from T3 | Only set when all steps in Section 6 succeed and a valid block time is confirmed. Never set from partial evidence. |

---

## 11. A3 Impact

**A3 remains locked** until a future approved implementation lane (V2-2AK) and
bounded live proof (V2-2AL or equivalent) produce real `token_age_seconds` from
T3 evidence.

The A3 gate:
```python
_tok_age_known = candidate.get("token_age_seconds") is not None
```

is not changed by this design. T3 evidence would populate `token_age_seconds`,
which would satisfy the A3 gate. But this is future implementation behavior,
not current behavior.

Nothing in this design document unlocks A3. Unlocking A3 requires:
1. V2-2AK: T3 implementation complete
2. V2-2AL (or equivalent): bounded live proof that T3 produces valid
   `token_age_seconds` from real RPC calls
3. Explicit operator approval to unlock A3 from real T3 evidence

---

## 12. Future Implementation Plan

### 12.1 New module: `src/printer_v1/sources/solana_rpc_token_age.py`

The T3 implementation MUST be in a new dedicated module, separate from the
existing `src/printer_v1/sources/solana_rpc_holder.py`. This maintains clear
separation of concerns: holder concentration evidence is holder-only, and token
creation time evidence is token-age-only.

The new module must include:
- `SOLANA_RPC_TOKEN_AGE_REQUEST_KIND = "mint_creation_time_reference"`
- `_T3_MAX_REQUESTS_PER_TOKEN = 8`
- `_T3_MAX_SIGNATURE_PAGES = 3`
- `_T3_SIGNATURES_PER_PAGE = 20`
- `_T3_MAX_INIT_CANDIDATES = 5`
- `_T3_MAX_TRANSACTION_CALLS = 3`
- `_T3_MAX_BLOCK_TIME_CALLS = 1`
- `_T3_RPC_TIMEOUT_SECONDS = 10.0`
- `_SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"`
- `_TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"`
- `_INIT_MINT_INSTRUCTION_TYPES = frozenset({"initializeMint", "initializeMint2"})`
- `SolanaRpcTokenAgeAdapter` class following the existing holder adapter pattern
- `SolanaRpcTokenAgeAdapterMetadata` dataclass
- `build_solana_rpc_token_age_adapter()` factory function
- `normalize_solana_rpc_token_age_response()` public function
- `_validate_mint_account()` private helper
- `_find_oldest_signature()` private helper (pagination walker)
- `_inspect_transaction_for_mint_init()` private helper
- `_derive_t3_evidence()` private helper
- `_t3_failure_result()` private helper
- `fixture_success_transport()` and `fixture_failure_transport()` for tests

### 12.2 Files to change in V2-2AK

| File | Change |
|---|---|
| `src/printer_v1/sources/solana_rpc_token_age.py` | **New file** — T3 adapter, normalizer, helpers |
| `src/printer_v1/sources/registry.py` | Add `"mint_creation_time_reference"` to `solana_rpc` `allowed_request_kinds` |
| `src/printer_v1/discovery/parser.py` | Extend `_derive_token_age_evidence_tier()` to return `"T3"` for `source_name == "solana_rpc"` and `request_kind == "mint_creation_time_reference"` and `token_created_at_raw is not None` and `token_age_seconds is not None` |
| `src/printer_v1/discovery/selection_batch.py` | Add `t3_*` provenance field names to `_METADATA_FIELDS` |

### 12.3 Files NOT to change

- `src/printer_v1/sources/solana_rpc_holder.py` — holder logic is unrelated
- `src/printer_v1/discovery/classifier.py` — A3 gate unchanged
- `src/printer_v1/operator_cli/commands.py` — no CLI change until proof lane
- Any memory, retrieval, paper decision, financial, scheduler, or runtime path
- DB schema — `candidate_metadata_json` already carries arbitrary metadata

### 12.4 Fixture tests required in V2-2AK

| Test class | Coverage |
|---|---|
| `TestMintAccountValidation` | Account found; account not found; not a mint; wrong program |
| `TestSignaturePageWalker` | Reaches end in 1 page; reaches end in 2 pages; page cap hit; empty history |
| `TestTransactionInspection` | Init found; init missing; failed transaction; mint mismatch; transaction not found |
| `TestBlockTimeFallback` | blockTime present; blockTime null + fallback succeeds; blockTime null + fallback null → fail closed |
| `TestT3EvidenceDerivation` | Valid evidence → token_created_at, token_age_seconds, T3 tier set; age non-negative |
| `TestT3FailureCases` | Each failure code from Section 8 produces correct failure result and leaves token age unknown |
| `TestT3BoundaryViolations` | pair_age never becomes token_age; captured_at never becomes token_created_at; OBSERVED_LIVE_LAUNCH never becomes T3; migration time rejected |
| `TestA3LockedForT3` | A3 does not fire unless token_age_seconds is not None from T3 evidence |
| `TestT3ProvenanceSurvives` | t3_* fields survive to extract_candidate_metadata |
| `TestBudgetEnforcement` | Budget exhausted at each step → fail closed; total never exceeds 8 calls |

### 12.5 Bounded live proof requirements (V2-2AL)

After V2-2AK fixture implementation:
1. Select 1-3 known live Pump.fun token mints (recently launched, confirmed on-chain)
2. Run bounded T3 enrichment via Source Governor, isolated proof DB
3. Confirm `token_age_evidence_tier = "T3"` set, `token_created_at` populated, `token_age_seconds ≥ 0`
4. Confirm provenance fields correct
5. Confirm persistent DB unchanged
6. Confirm source request/response/failure rows recorded correctly
7. Proof report: `docs/printer-v1-v2-2al-t3-bounded-live-proof.md`

---

## 13. Architecture Notes

### 13.1 Precedence ordering

When a candidate has evidence from multiple tier sources, the following precedence applies:

```
T1 > T2 > T3 > OBSERVED_LIVE_LAUNCH > None
```

T1, T2, and T3 all populate `token_created_at`. T3 should only be applied when
T2 evidence is absent. The parser's `_derive_token_age_evidence_tier()` logic
should check `source_name == "solana_rpc"` for T3 — since T3 enrichment is
from a separate source entirely, there is no natural precedence conflict within
a single candidate.

However, when a PumpPortal candidate is enriched by a separate T3 call and
merged (future join logic), T2 from the launch event must still win if
`tokenCreatedAt` was present in the original event.

For V2-2AK's immediate scope, T3 applies to candidates discovered through
pair-centric sources (GeckoTerminal, DexScreener) that have no T2 evidence.
Join logic is deferred.

### 13.2 Rate limit interaction

The `solana_rpc` source registry has `default_rate_limit_per_minute = 30`.
T3 uses up to 8 RPC requests per token. At full concurrency, this allows
approximately 3-4 tokens per minute at 8 requests each. In practice, most
tokens will use fewer requests (3-5), allowing slightly higher throughput.

The existing Source Governor rate-limit tracking applies to `solana_rpc` as a
whole. If the holder concentration path is also active, request budgets are
shared across request kinds within the same source.

### 13.3 Public RPC reliability

Public Solana RPC (`api.mainnet-beta.solana.com`) is rate-limited and
occasionally unavailable. T3 is designed to fail gracefully:
- Every failure maps to a specific failure code (Section 8)
- No failure causes fake token-age evidence
- The candidate proceeds normally with `token_age_evidence_tier = None` (or
  `OBSERVED_LIVE_LAUNCH` if that was set by PumpPortal)

If the operator provides a free Helius endpoint (not paid), T3 should use it
preferentially. The endpoint is configurable at the adapter level; no code
change is needed per-endpoint.

---

## 14. Remaining Blockers

| Blocker | Status |
|---|---|
| T3 implementation not built | DEFERRED — requires V2-2AK lane |
| Registry `mint_creation_time_reference` not added | DEFERRED |
| Fixture tests not written | DEFERRED |
| Bounded live proof not run | DEFERRED — after V2-2AK |
| A3 locked until live proof proves real `token_age_seconds` | INTENTIONAL |
| Staged/native 15m blocker | `PARTIAL - DEFERRED, NOT RESOLVED` (unchanged) |
| V2-3 remains paused | INTENTIONAL |

---

## 15. Exact Next Recommended Lane

**V2-2AK — T3 Solana RPC Token-Age Evidence Implementation**

Scope:
1. Create `src/printer_v1/sources/solana_rpc_token_age.py` per Section 12.1
2. Add `"mint_creation_time_reference"` to `solana_rpc` registry entry
3. Extend `parser.py` `_derive_token_age_evidence_tier()` for T3
4. Add `t3_*` provenance fields to `selection_batch.py` `_METADATA_FIELDS`
5. Write all test classes from Section 12.4
6. Run focused tests: `test_v2_2aj_t3_solana_rpc_token_age.py`,
   `test_v2_2x2_t2_token_age_evidence.py`, `test_v2_2ag_observed_live_launch_tier.py`
7. Git diff/status checks
8. Proof report: `docs/printer-v1-v2-2ak-t3-solana-rpc-token-age-implementation.md`
9. Commit only intended files: `Add V2-2AK T3 token-age implementation`

Pre-conditions:
- V2-2AJ committed (this document)
- No live RPC calls in implementation lane
- No A3 unlocking
- No V2-3 work

---

## 16. V2-3 Status

**V2-3 remains PAUSED.**

No retrieval, no memory generation, no scheduling, no scoring, no paper
decisions, no BUY/SELL/HOLD were introduced or planned by this design.

Staged/native 15m blocker status: `PARTIAL - DEFERRED, NOT RESOLVED`.
This blocker is unaffected by the T3 design.

---

## 17. Final Verdict

`DESIGN_COMPLETE_WITH_BLOCKERS`

V2-2AJ defines the complete T3 architecture:

1. **Source contract**: `solana_rpc` / `mint_creation_time_reference`, disabled
   by default, Source Governor required.
2. **Allowed methods**: `getAccountInfo` (1), `getSignaturesForAddress` (≤3),
   `getTransaction` (≤3), `getBlockTime` (≤1). Total max: **8 requests/token**.
3. **Evidence rule**: mint account confirmed → history end reachable in ≤3 pages
   → oldest candidate transaction contains `initializeMint`/`initializeMint2`
   for exact requested mint → valid `blockTime` derived → T3 tier set.
4. **Fail-closed design**: any missing step or exceeded budget leaves token age
   unknown. No fallback to pair age, `captured_at`, migration time, or
   `OBSERVED_LIVE_LAUNCH`.
5. **Provenance**: 14 `t3_*` fields preserved in `candidate_metadata_json`.
6. **A3 locked**: unchanged; requires future implementation lane + live proof.
7. **V2-3 paused**: unchanged.
