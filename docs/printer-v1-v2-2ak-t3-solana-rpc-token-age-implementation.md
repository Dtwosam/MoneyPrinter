# Printer V1 V2-2AK T3 Solana RPC Token-Age Implementation

**Lane:** V2-2AK
**Executor:** Claude Sonnet 4.6
**Date:** 2026-07-11
**Verdict:** `IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

No live RPC calls. Fixture-only proof. No DB mutation.

---

## 1. Design Anchor

| Anchor | Commit | Content |
|---|---|---|
| V2-2AJ design | `e8afefe` | T3 evidence design, request budget, provenance fields |
| V2-2AJ.1 correction | `4ea3e9a` | Mint validation fix (82 bytes), candidate cap fix (3 not 5) |

---

## 2. Files Changed

| File | Change |
|---|---|
| `src/printer_v1/sources/registry.py` | Added `"mint_creation_time_reference"` to `solana_rpc.allowed_request_kinds` |
| `src/printer_v1/sources/solana_rpc_token_age.py` | New T3 adapter module (constants, adapter class, contract builder, fixture transports, live transport, normalizer, pipeline, helpers) |
| `src/printer_v1/discovery/parser.py` | Extended `_derive_token_age_evidence_tier()` with T3 branch for `solana_rpc`/`mint_creation_time_reference` |
| `src/printer_v1/discovery/selection_batch.py` | Added all 15 `t3_*` provenance fields to `_METADATA_FIELDS` |
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | New 84-test fixture proof suite (11 test classes) |
| `docs/printer-v1-v2-2ak-t3-solana-rpc-token-age-implementation.md` | This file |

---

## 3. Request Budget — Constants Locked

| Constant | Value |
|---|---|
| `_T3_MAX_REQUESTS_PER_TOKEN` | 8 |
| `_T3_MAX_SIGNATURE_PAGES` | 3 |
| `_T3_SIGNATURES_PER_PAGE` | 20 |
| `_T3_MAX_INIT_CANDIDATES` | 3 |
| `_T3_MAX_TRANSACTION_CALLS` | 3 |
| `_T3_MAX_BLOCK_TIME_CALLS` | 1 |
| `_T3_RPC_TIMEOUT_SECONDS` | 10.0 |

Max getTransaction calls (3) matches max init candidates (3). Budget constant
matches design Section 5.1 corrected table.

---

## 4. Evidence and Fail-Closed Design

**Accepted only when:**
1. `getAccountInfo` confirms mint owned by SPL Token or Token-2022 program
2. SPL Token mint data is exactly 82 bytes; Token-2022 is ≥ 82 bytes (base + extensions)
3. Signature history end reachable within 3 pages (full history confirmed)
4. `initializeMint` or `initializeMint2` instruction found targeting exact mint
5. Valid, non-future block time derived (from `getTransaction.blockTime` or `getBlockTime`)
6. `token_created_at` ≤ `captured_at` (future block time → fail closed)

**All 14 failure types leave `token_created_at`, `token_age_seconds`, and tier unset:**

| Failure type | Trigger |
|---|---|
| `solana_rpc_token_age_account_not_found` | No account at mint address |
| `solana_rpc_token_age_not_a_mint` | Wrong owner program, short data, decode fail |
| `solana_rpc_token_age_rate_limited` | HTTP 429 from RPC endpoint |
| `solana_rpc_token_age_transport_error` | Network/OS/timeout error |
| `solana_rpc_token_age_no_signatures` | Empty history on first page |
| `solana_rpc_token_age_page_cap_exhausted` | 3 pages fetched, end not reached |
| `solana_rpc_token_age_history_pruned` | Signature history partially unavailable |
| `solana_rpc_token_age_transaction_not_found` | `getTransaction` returned null |
| `solana_rpc_token_age_no_init_instruction` | No matching initializeMint in candidates |
| `solana_rpc_token_age_mint_mismatch` | Init instruction targets different mint |
| `solana_rpc_token_age_null_block_time` | blockTime null, getBlockTime fallback also failed |
| `solana_rpc_token_age_future_block_time` | Derived block time > captured_at |
| `solana_rpc_token_age_budget_exhausted` | 8-call budget exhausted before evidence |
| `solana_rpc_token_age_malformed_response` | Missing/invalid required success fields |

**Prohibited age fallbacks (confirmed blocked by tests):**
- `pair_created_at` / pair age → never becomes `token_created_at`
- `captured_at` / collection time → never becomes `token_created_at`
- Migration time → never becomes `token_created_at`
- `OBSERVED_LIVE_LAUNCH` → remains separate tier; never replaces T3 evidence
- `live_observed_launch` flag → absent from T3 payload

---

## 5. Provenance Fields — All 15 Survive to Metadata

All 15 `t3_*` fields added to `_METADATA_FIELDS` in `selection_batch.py`.
All 15 confirmed present in `extract_candidate_metadata()` output.

| Field | Content |
|---|---|
| `t3_requested_mint` | Token mint address submitted to adapter |
| `t3_rpc_host_redacted` | Hostname only (no key, no path) |
| `t3_rpc_methods_attempted` | List of RPC method names called |
| `t3_request_ids` | Sequential IDs per call |
| `t3_pages_fetched` | Number of signature pages consumed |
| `t3_signatures_inspected` | Number of candidate tx calls made |
| `t3_accepted_signature` | Signature of accepted init transaction |
| `t3_accepted_slot` | Slot of accepted init transaction |
| `t3_block_time_raw` | Unix timestamp from accepted block |
| `t3_block_time_source` | `"getTransaction"` or `"getBlockTime"` |
| `t3_instruction_type` | `"initializeMint"` or `"initializeMint2"` |
| `t3_token_program` | `"spl_token"` or `"token_2022"` |
| `t3_derived_token_created_at` | ISO 8601 derived from block time |
| `t3_derived_token_age_seconds` | Float seconds at capture |
| `t3_captured_at` | ISO 8601 collection time |

---

## 6. Source Governor Contract

- `validate_source_adapter_contract()` passes: `fixture_only=True`,
  `enabled_by_default=False`, `supports_network_execution=False`,
  `requires_governor_context=True`
- Adapter disabled by default; raises `PermissionError` if `enabled=False`
- Adapter raises `PermissionError` if no transport injected
- `_validate_t3_context()` checks `governor_approved=True`, correct
  `execution_path`, correct `source_name`, correct `request_kind`
- Per-token enrichment recording model (matches holder adapter precedent)

**Source Governor blocker:** Per-RPC-call recording would require governor scope
expansion. Current implementation records one enrichment per token (same model
as `holder_concentration_reference`). This is the IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS
blocker — not a test failure.

---

## 7. Parser Extension

`_derive_token_age_evidence_tier()` refactored from a `pumpportal`-only guard
to a branched function:

```python
if source_name == "pumpportal":
    ...  # T2 and OBSERVED_LIVE_LAUNCH unchanged
if source_name == "solana_rpc":
    if candidate_payload.get("request_kind") != "mint_creation_time_reference":
        return None
    if token_created_at_raw is not None and token_age_seconds is not None:
        return "T3"
    return None
return None
```

T2 and OBSERVED_LIVE_LAUNCH behavior preserved exactly (confirmed by 30+30
existing tests passing). T3 branch requires both `token_created_at_raw` and
`token_age_seconds` to be non-None — fail-closed by design.

---

## 8. Tests Run

### New focused suite

| File | Tests | Result |
|---|---|---|
| `tests/test_v2_2ak_t3_solana_rpc_token_age.py` | 84 | PASS |

Test classes:
- `TestT3AdapterContractAndGovernance` (8 tests)
- `TestT3NormalizerSplTokenSuccess` (9 tests)
- `TestT3NormalizerToken2022Success` (6 tests)
- `TestT3FailureCases` (19 tests)
- `TestT3ProvenancePersistence` (10 tests)
- `TestT3ParserTierDerivation` (7 tests)
- `TestT3BlockTimeFallback` (4 tests)
- `TestT3BoundaryViolations` (5 tests)
- `TestT2AndObservedLiveLaunchUnchanged` (5 tests)
- `TestA3LockedOnFailedT3` (4 tests)
- `TestT3FixtureTransportHelpers` (7 tests)

### Cross-check suites

| Suite | Tests | Result |
|---|---|---|
| `tests/test_v2_2x2_t2_token_age_evidence.py` | (included in 232) | PASS |
| `tests/test_v2_2ag_observed_live_launch_tier.py` | (included in 232) | PASS |
| `tests/test_v2_2c_selection_batch.py` | (included in 232) | PASS |
| Combined cross-check run | 232 | PASS |

### Git checks

| Check | Result |
|---|---|
| `git diff --check` | LF→CRLF warnings only; no whitespace errors |
| `git status --short` | 3 M (tracked), 2 ?? new files |
| `git diff --stat HEAD` | 3 files changed, 36 insertions, 8 deletions |
| New files | `solana_rpc_token_age.py`, `test_v2_2ak_t3_solana_rpc_token_age.py` |

---

## 9. Safety Confirmations

- No live RPC calls — all tests use fixture transports
- `token_created_at` never set from `captured_at` — confirmed by test
- `token_created_at` never set from pair age — confirmed by test
- `token_created_at` never set from migration time — confirmed by test
- `OBSERVED_LIVE_LAUNCH` not in T3 payload — confirmed by test
- T2 contract unchanged — 82+ T2 tests pass
- `OBSERVED_LIVE_LAUNCH` unchanged — 30 tier tests pass
- A3 not unlocked — `token_age_seconds is None` when T3 fails; confirmed by 4 A3 tests
- A3 WOULD fire with real T3 evidence when conditions met — confirmed by positive test
- All 15 `t3_*` fields in `_METADATA_FIELDS` — confirmed by test
- Adapter disabled by default — confirmed by test
- No DB mutation, no memory generation, no retrieval
- No BUY/SELL/HOLD, paper decisions, positions, trades, audits, or PnL
- No scoring, ranking, confidence, weighted, embeddings, or vectors
- A3 gate (`token_age_seconds is not None`) unchanged — confirmed

---

## 10. Remaining Blockers

| Blocker | Status |
|---|---|
| Per-RPC-call Source Governor recording | DEFERRED — requires scope expansion; per-token recording used instead (matches holder precedent) |
| Live network proof (V2-2AL) | NOT YET RUN — requires bounded live proof lane with operator approval |
| A3 not yet live | INTENTIONAL — requires live proof before A3 can be enabled for T3 evidence |
| Staged/native 15m blocker | PARTIAL - DEFERRED, NOT RESOLVED |
| V2-3 | PAUSED |

---

## 11. Exact Next Recommended Lane

**V2-2AK.1 — Independent T3 Implementation Verification**

Scope: Independent review of V2-2AK implementation for correctness, boundary
adherence, and completeness against V2-2AJ design spec. Read only.

---

## 12. Final Summary

```text
VERDICT: IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS
ANCHOR: 4ea3e9a (V2-2AJ.1 corrected design)
NEW_FILES: src/printer_v1/sources/solana_rpc_token_age.py
           tests/test_v2_2ak_t3_solana_rpc_token_age.py
           docs/printer-v1-v2-2ak-t3-solana-rpc-token-age-implementation.md
MODIFIED_FILES: src/printer_v1/sources/registry.py
                src/printer_v1/discovery/parser.py
                src/printer_v1/discovery/selection_batch.py
REQUEST_BUDGET: max 8 RPC calls per token (1 account + 3 sig pages + 3 tx + 1 blocktime)
EVIDENCE_RESULT: fail-closed on all 14 failure types; T3 accepted only with initializeMint + valid block time
FAIL_CLOSED: CONFIRMED - all 14 failure types leave token_created_at/token_age_seconds/tier unset
FIXTURE_TESTS: 84 PASS (new) + 232 PASS (cross-check)
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
T2_UNCHANGED: CONFIRMED
OBSERVED_LIVE_LAUNCH_UNCHANGED: CONFIRMED
A3_GATE_UNCHANGED: token_age_seconds is not None
A3_STATUS: LOCKED (fixture only; live proof required before A3 can be enabled for T3)
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
NEXT_LANE: V2-2AK.1 — Independent T3 Implementation Verification
```
