# Printer V1 V2-2AK.1 T3 Implementation Verification

Status: VERIFICATION ONLY
Lane: V2-2AK.1 - Independent T3 Implementation Verification
Executor/model: Codex, standard/balanced mode
Target commit: `3d0ef50 Add V2-2AK T3 token-age implementation`
Verdict: `VERIFICATION_PARTIAL_WITH_BLOCKER`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This lane did not implement code, change tests, run live RPC, mutate DBs,
generate memory, activate retrieval, unlock A3, or unlock V2-3.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2aj-t3-solana-rpc-token-age-evidence-design.md`
- `docs/printer-v1-v2-2ak-t3-solana-rpc-token-age-implementation.md`

## Files Inspected

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`
- `tests/test_v2_2ag_observed_live_launch_tier.py`
- `tests/test_v2_2c_selection_batch.py`

## Evidence Acceptance Verification

The implementation accepts T3 evidence only on the narrow success path in the
fixture-normalized and live-transport pipeline:

| Requirement | Verification result |
| --- | --- |
| Mint account is owned by SPL Token or Token-2022 | Present in live pipeline owner check |
| Mint-state data decodes from base64 | Present as base64 decode and size checks |
| Matching `initializeMint` / `initializeMint2` targets exact mint | Present in `_is_init_mint_instruction()` and live pipeline |
| Transaction succeeded | Present: `meta.err is None` required before accepting candidate transaction |
| Valid non-future block time exists | Present: `blockTime` or one `getBlockTime` fallback, then non-future check |
| T3 output requires `token_created_at` and `token_age_seconds` | Present in `normalize_solana_rpc_token_age_response()` and parser T3 tier branch |

Result: the positive evidence path is directionally correct and fixture tests
cover the expected success cases.

## Fail-Closed Verification

The focused fixture suite proves failure payloads return `SourceStatus.FAILED`
and `MISSING_CRITICAL_DATA`, with no `token_created_at`, no
`token_age_seconds`, and no T3 tier.

Failure families covered by tests include:

- account not found
- not a mint
- rate limited
- transport error
- no signatures
- page cap exhausted
- history pruned
- transaction not found
- no init instruction
- mint mismatch
- null block time
- future block time
- budget exhausted
- malformed response

Result: `FAIL_CLOSED_CONFIRMED` for fixture-normalized failures.

## Request Limit Verification

Static inspection confirms the requested limits are present:

| Limit | Implementation value | Verification |
| --- | ---: | --- |
| max operations | 8 | `_T3_MAX_REQUESTS_PER_TOKEN = 8` |
| max signature pages | 3 | `_T3_MAX_SIGNATURE_PAGES = 3` |
| max transaction calls | 3 | `_T3_MAX_TRANSACTION_CALLS = 3` |
| max block-time fallback | 1 | `_T3_MAX_BLOCK_TIME_CALLS = 1` |
| timeout | 10 seconds | `_T3_RPC_TIMEOUT_SECONDS = 10.0` |
| retries | 0 | no retry loop found |

Important nuance: `_T3_MAX_BLOCK_TIME_CALLS` exists, but the live helper does
not currently track a separate block-time call counter. Because the total
request cap and loop shape allow at most one `getBlockTime` in practice, this is
not a current safety failure. A future repair/proof lane should either enforce
the named constant directly or document that the total cap plus loop structure
is the enforcement mechanism.

## Prohibited Fallback Verification

The implementation and tests preserve the prohibited fallback boundaries:

| Prohibited fallback | Result |
| --- | --- |
| pair age | not used as `token_created_at` or `token_age_seconds` |
| `captured_at` | not used as token creation time |
| migration time | ignored by T3 normalizer |
| first trade | not accepted; T3 requires mint init instruction |
| `OBSERVED_LIVE_LAUNCH` | remains separate metadata tier and does not become token age |

Result: `PROHIBITED_FALLBACKS_BLOCKED`.

## Metadata Handoff Verification

All 15 required `t3_*` provenance fields are listed in
`selection_batch.py` `_METADATA_FIELDS`, and the focused test suite verifies
they survive through `extract_candidate_metadata()`.

Fields verified:

- `t3_requested_mint`
- `t3_rpc_host_redacted`
- `t3_rpc_methods_attempted`
- `t3_request_ids`
- `t3_pages_fetched`
- `t3_signatures_inspected`
- `t3_accepted_signature`
- `t3_accepted_slot`
- `t3_block_time_raw`
- `t3_block_time_source`
- `t3_instruction_type`
- `t3_token_program`
- `t3_derived_token_created_at`
- `t3_derived_token_age_seconds`
- `t3_captured_at`

Result: `T3_METADATA_HANDOFF_CONFIRMED`.

## T2 / OBSERVED_LIVE_LAUNCH / A3 Safety

Static inspection and tests confirm:

- T2 still takes precedence for PumpPortal launch events with explicit
  timestamp evidence.
- `OBSERVED_LIVE_LAUNCH` still leaves `token_created_at=None` and
  `token_age_seconds=None`.
- PumpPortal migration events still do not become token-age evidence.
- A3 still gates on `token_age_seconds is not None`.
- Failed T3 evidence does not unlock A3.
- A3 can fire only in fixture conditions where real `token_age_seconds` is
  present and other A3 conditions pass.

Result: A3 remains locked for live behavior. Fixture-positive A3 behavior is not
a live unlock.

## Mismatch 1 - Live-Capable Adapter Metadata

Design expectation:

- `fixture_transport_only = False`
- `supports_network_execution = True`
- live-capable bounded adapter for later proof

Implementation finding:

- `SolanaRpcTokenAgeAdapterMetadata.fixture_transport_only = True`
- `SolanaRpcTokenAgeAdapterMetadata.supports_network_execution = False`
- adapter execution still requires an explicit injected transport
- `build_solana_rpc_token_age_transport()` exists, but the adapter metadata and
  constructor do not make this a live-capable Source Governor adapter by default

Classification: `IMPLEMENTATION_DEFECT_REQUIRING_REPAIR_BEFORE_LIVE_PROOF`

Rationale: This is safe for fixture-only V2-2AK, but it contradicts the V2-2AJ
live-capable adapter expectation and will block or confuse a bounded live T3
proof lane. Repair should happen before any live RPC proof.

## Mismatch 2 - Source Governor Recording Granularity

Design expectation:

- every RPC operation is governed/auditable, or every operation is traceable
  through an approved equivalent provenance model

Implementation finding:

- implementation follows one enrichment per token, matching the holder adapter
  precedent
- per-operation RPC method names and request IDs are recorded in `t3_*`
  provenance
- individual RPC operations are not modeled as separate Source Governor rows

Classification: `SAFE_DEFERRED_BLOCKER`

Rationale: This is not a fixture-stage safety failure because no live RPC ran,
and the per-token model is consistent with current holder evidence precedent.
Before live proof, the operator should explicitly approve either:

1. per-token Source Governor request row with complete `t3_*` operation
   provenance, or
2. a repair that records each RPC operation as its own governed source row.

Until that decision, this remains a blocker for a fully satisfying live-proof
claim, but not a reason to reject fixture implementation outright.

## Mismatch 3 - Token-2022 Mint-State Decoding

Design expectation:

- Token-2022 validation must perform real mint-state/extension decoding, not
  owner plus length-only validation.

Implementation finding:

- live pipeline verifies owner is SPL Token or Token-2022
- base64 decoding is attempted
- SPL Token requires exactly 82 bytes
- Token-2022 accepts decoded data length greater than or equal to 82 bytes
- no real Token-2022 mint-state or extension decoding was found beyond owner
  and length checks

Classification: `IMPLEMENTATION_DEFECT_REQUIRING_REPAIR_BEFORE_LIVE_PROOF`

Rationale: This is the strongest blocker. Owner plus length is not the design's
required real mint-state/extension decoding. The fixture tests prove desired
labels, but they do not prove robust live Token-2022 validation. A live proof
must not proceed until Token-2022 validation is either repaired or explicitly
limited to SPL Token only for the proof lane.

## Tests Run

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_v2_2ak_t3_solana_rpc_token_age.py -q` | PASS: 84 passed, 1 cache warning |
| `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q` | PASS: 82 passed, 1 cache warning |
| `python -m pytest tests/test_v2_2ag_observed_live_launch_tier.py -q` | PASS: 30 passed, 1 cache warning |
| `python -m pytest tests/test_v2_2c_selection_batch.py -q` | PASS: 120 passed, 1 cache warning |

Warnings were pytest cache path warnings only. No live RPC was run.

## Safety Confirmations

- no implementation changes
- no test changes
- no live RPC
- no DB mutation
- no migrations
- no source fetching
- no scheduler/runtime
- no memory generation
- no retrieval activation
- no paper decisions
- no BUY/SELL/HOLD
- no positions, trades, audits, or PnL
- no wallet/private-key/signing/live-execution logic
- no paid API dependency
- no scoring/ranking/confidence/weighted logic
- no embeddings/vectors

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| Live-capable adapter metadata contradicts design | repair before live proof |
| Token-2022 validation lacks real mint-state/extension decoding | repair before live proof |
| Per-operation Source Governor recording not implemented | safe deferred blocker; requires operator decision before live-proof claim |
| Bounded live T3 proof not run | still required |
| A3 live unlock | blocked until approved live T3 proof produces real `token_age_seconds` |
| Staged/native 15m | `PARTIAL - DEFERRED, NOT RESOLVED` |
| V2-3 | paused |

## Exact Next Lane

`V2-2AK.2 - T3 Live-Proof Readiness Repair`

Recommended scope:

1. repair live-capability metadata/adapter construction so the future bounded
   proof path is honest
2. repair or explicitly restrict Token-2022 validation before live proof
3. decide the Source Governor recording model for multi-operation T3 enrichment
4. keep all tests fixture-only unless a later lane explicitly approves live RPC
5. keep A3 and V2-3 paused

## Final Summary

```text
VERDICT: VERIFICATION_PARTIAL_WITH_BLOCKER
TARGET_COMMIT_VERIFIED: 3d0ef50
EVIDENCE_ACCEPTANCE: DIRECTIONALLY_CORRECT
FAIL_CLOSED_RESULT: CONFIRMED_BY_TESTS
REQUEST_LIMITS: CONFIRMED_WITH_BLOCK_TIME_COUNTER_NUANCE
PROHIBITED_FALLBACKS: BLOCKED
T3_METADATA_FIELDS: 15/15 PRESERVED
LIVE_CAPABILITY_FINDING: IMPLEMENTATION_DEFECT_REQUIRING_REPAIR_BEFORE_LIVE_PROOF
GOVERNOR_RECORDING_FINDING: SAFE_DEFERRED_BLOCKER
TOKEN_2022_DECODING_FINDING: IMPLEMENTATION_DEFECT_REQUIRING_REPAIR_BEFORE_LIVE_PROOF
A3_STATUS: PAUSED
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
NEXT_LANE: V2-2AK.2 - T3 Live-Proof Readiness Repair
```
