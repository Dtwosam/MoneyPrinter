# Printer V1 V2-2AK.3 T3 Readiness Repair Verification

Status: VERIFICATION ONLY
Lane: V2-2AK.3 - Independent T3 Readiness Repair Verification
Executor/model: Codex, standard/balanced mode
Target commit: `bbf6f20 Repair V2-2AK T3 live-proof readiness`
Verdict: `VERIFICATION_PASS_WITH_BLOCKERS`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This lane did not change code, change tests, run live RPC, mutate DBs, generate
memory, activate retrieval, unlock A3, or unlock V2-3.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-v2-2aj-t3-solana-rpc-token-age-evidence-design.md`
- `docs/printer-v1-v2-2ak-1-t3-implementation-verification.md`
- `docs/printer-v1-v2-2ak-2-t3-live-proof-readiness-repair.md`

## Files Inspected

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/contracts.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`
- `tests/test_v2_2ag_observed_live_launch_tier.py`

## Governed Live-Path Result

Result: `LIVE_PROOF_READY_WITH_CONSERVATIVE_CONTRACT_BLOCKER`

The repaired adapter metadata now reports live capability:

- `supports_network_execution=True`
- `fixture_transport_only=False`
- `enabled_by_default=False`
- `requires_governor_context=True`
- `read_only=True`

Static inspection confirms the adapter can execute through its governed adapter
path when the operator provides an explicit bounded transport. The adapter still
requires a caller-supplied transport and still fails closed if no transport is
provided. This is safe for the first bounded live proof because it avoids hidden
network execution and requires explicit operator-controlled wiring.

The adapter is not ready for broad automated source activation. The first live
proof must remain bounded, operator-approved, Source Governor controlled, and
isolated from memory, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, and PnL.

## Metadata / Contract Finding

Result: `ACCEPTABLE_FOR_FIRST_BOUNDED_PROOF_WITH_BLOCKER`

The metadata/contract mismatch is real and intentionally conservative:

| Item | Value |
| --- | --- |
| Adapter metadata `supports_network_execution` | `True` |
| Adapter metadata `fixture_transport_only` | `False` |
| `SourceAdapterContract.supports_network_execution` | `False` |
| `SourceAdapterContract.fixture_only` | `True` |

`SourceAdapterContract` remains generated through
`build_source_adapter_contract()` and the default contract validator still
expects fixture-only/no-network values. The focused tests explicitly preserve
the distinction between adapter metadata and contract guardrails.

This is acceptable for the first bounded live proof only because the proof path
uses explicit operator approval and a bounded transport. It remains a carry-
forward blocker before any wider runtime/source automation can treat T3 as a
normal live source path.

## Token-2022 Decoding Result

Result: `PASS`

Static inspection and focused tests confirm V2-2AK.2 repaired Token-2022
validation beyond owner plus length checks:

- SPL Token mint-base decode requires at least 82 bytes.
- SPL Token mint-base decode checks the initialized byte at offset 45.
- Token-2022 decode first validates the same 82-byte mint base.
- Token-2022 decode checks AccountType byte at offset 82 equals the mint
  discriminant.
- Token-2022 decode walks TLV extensions with type/length headers.
- Trailing zero padding is accepted.
- Partial non-zero TLV headers fail closed.
- TLV length overflow fails closed.
- Malformed extension data fails closed.

The repair satisfies the first bounded proof requirement that Token-2022
validation perform real mint-state and extension-shape decoding before accepting
T3 token-age evidence.

## Request-Limit Result

Result: `PASS`

Static inspection confirms the bounded request rules are present:

| Limit | Verification result |
| --- | --- |
| Max RPC operations per token | `_T3_MAX_REQUESTS_PER_TOKEN = 8` |
| Max signature pages | `_T3_MAX_SIGNATURE_PAGES = 3` |
| Max transaction calls | `_T3_MAX_TRANSACTION_CALLS = 3` |
| Max `getBlockTime` fallback calls | `_T3_MAX_BLOCK_TIME_CALLS = 1` |
| RPC timeout | `_T3_RPC_TIMEOUT_SECONDS = 10.0` |
| Retries | No retry loop found in the inspected T3 adapter path |

The implementation counts total RPC operations through `_call()`, bounds
signature pages, bounds accepted transaction inspection, and bounds block-time
fallback to one call.

## Governor / Provenance Decision

Result: `SUFFICIENT_FOR_FIRST_BOUNDED_LIVE_PROOF_WITH_DEFERRED_TRACE_BLOCKER`

The implementation still records one governed enrichment per token rather than
one Source Governor row per RPC operation. V2-2AK.2 documented this as an
operator-approved safe deferred blocker.

For the first bounded live proof, this is sufficient if the proof report records
the single governed per-token source row, the redacted RPC host, operation list,
request IDs, page counts, accepted signature/slot, block-time source, token
program, and derived token-age fields.

All 15 `t3_*` provenance fields are present in the success path:

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

Per-RPC Source Governor rows remain a future hardening question before broad
source automation. They are not required to run the first bounded proof.

## Preservation Checks

Result: `PASS`

Focused tests and static inspection confirm:

- T2 token-age evidence remains preserved and higher priority when timestamp
  fields exist.
- `OBSERVED_LIVE_LAUNCH` remains distinct from T3 and does not fabricate
  `token_created_at` or `token_age_seconds`.
- A3 remains locked unless real `token_age_seconds` exists.
- Pair age, captured time, migration time, first trade time, and observed-live
  launch time remain prohibited T3 fallbacks.
- No memory, retrieval, paper decision, BUY/SELL/HOLD, paper position, trade,
  audit, or PnL path was changed in this verification lane.

## Tests / Checks Run

- `python -m pytest tests/test_v2_2ak_t3_solana_rpc_token_age.py -q`
  - Result: `114 passed`
- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py tests/test_v2_2ag_observed_live_launch_tier.py -q`
  - Result: `112 passed`

Both test commands emitted the pre-existing pytest cache warning for
`.pytest_cache` path creation. The tests still passed.

## Remaining Blockers

- The `SourceAdapterContract` remains fixture-only/no-network while adapter
  metadata is live-capable. This is acceptable for the first bounded proof, but
  it must be resolved or deliberately documented again before any broader live
  source activation.
- Per-token Source Governor recording is accepted for the first bounded proof,
  but per-RPC operation rows remain a possible future audit-hardening need.
- No live T3 proof has run yet.
- A3 remains locked until valid T3 evidence or another approved token-age tier
  produces real `token_age_seconds`.
- The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
- V2-3 remains paused.

## Verdict

`VERIFICATION_PASS_WITH_BLOCKERS`

V2-2AK.2 repaired the live-readiness blockers enough to proceed to the first
bounded, operator-approved T3 live proof. The live proof must stay isolated,
Source Governor controlled, read-only, capped, and non-unlocking.

## Exact Next Lane

`V2-2AL - Bounded Live T3 Solana RPC Token-Age Proof`

The next lane should run a single bounded live proof against an isolated proof
DB only, with no A3 unlock, no V2-3 movement, no memory generation, no
retrieval, no paper decisions, no BUY/SELL/HOLD, no positions, no trades, no
audits, and no PnL.
