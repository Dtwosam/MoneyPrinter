# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Direct Pump Evidence Bridge Repair Design V2

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_DIRECT_PUMP_EVIDENCE_BRIDGE_REPAIR_V2_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

Baseline HEAD: `ecb8fca30e3953b02aec06424c8832e6068d63b6`
Linear: `DTW-47`

## Why V2 is required

The original DTW-47 design correctly identified the carried `direct_pump_evidence` omission and C8 proof-model drift, but the deterministic four-reserve RED exposed an additional same-contract stage-attribution defect before implementation.

Observed offline RED:

- four deterministic direct candidates;
- direct-discovery governed requests = 9;
- permanent required reserve capacity = 4;
- eligible reserve = 0;
- terminal `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL`;
- last stop `LAWFUL_WORK_REMAINING_WITH_CAPACITY`;
- shortage `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`;
- 19 flat governed operations remained;
- zero network attempts.

Static owner trace proves the 9 requests are:

- 1 finalized migration signature-page request;
- 4 finalized migration transaction requests;
- 4 governed PumpSwap verification requests.

`direct_migration_discovery.source_request_coverage` already classifies those requests as `DIRECT_MIGRATION_INTAKE` versus `DIRECT_MIGRATION_VERIFY`.

The permanent supply bridge currently computes `protocol_calls = source_requests - 1`, which yields 8 and incorrectly charges the 4 migration transaction lookups to the `protocol_confirmation` stage. This is attribution error, not real budget exhaustion.

## Approved implementation surface

Only these four files may change:

1. `src/printer_v1/discovery/eligible_token_supply.py`
2. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
3. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
4. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

No migration, Source Governor, Central Scheduler, admission-owner, memory, retrieval, decision, position, trade, audit, PnL, workflow, or provider file is approved.

## Repair 1 — preserve carried direct-Pump authority

At the exact-mint join from `discovery.candidate_mix` into the market-resolved candidate, copy `direct_pump_evidence` only when the direct owner supplied it as a mapping.

Do not synthesize missing evidence. Do not consult the graduated registry from admission. `_source_specific_admission_for()` remains fail-closed and unchanged.

## Repair 2 — correct protocol-stage attribution

Replace the arithmetic `source_requests - 1` protocol charge with an exact count derived from `discovery.source_request_coverage`.

Count only rows whose direct-discovery coverage identifies the governed PumpSwap verification request, i.e. the existing `DIRECT_MIGRATION_VERIFY` / `pumpswap_signature_pool_resolution` owner classification.

For the four-candidate C8 fixture this must yield exactly 4 protocol-confirmation governed requests, not 8.

Do not raise `STAGE_RESERVATIONS`, the flat 45-operation ceiling, or any provider/source budget.

Do not change direct-migration request accounting; all nine governed requests remain counted in flat source accounting and six-unit evidence exactly once.

## Repair 3 — align C8 deterministic reserve depth

C8 deterministic supply must contain four distinct lawful Pump/PumpSwap candidates (`alpha`, `bravo`, `charlie`, `delta`) because permanent availability requires two selected candidates plus one eligible alternate per slot.

This changes reserve depth only. Canonical selection remains exactly two, and Checkpoint 8 success still requires exactly two terminal `WINDOW_15M` windows.

Update the C8 preparation and execution-entry fixture-count gates from two to four.

## Repair 4 — exact-target lifecycle market fixtures

The lifecycle DexScreener primary and GeckoTerminal fallback factories must resolve the requested `token_mint` / `pool_address` to the matching deterministic candidate.

Unknown or conflicting target identity must fail closed. Do not default lifecycle market evidence to `candidates[0]`.

## Repair 5 — update proof-only real-consumer expectations

The compatibility owner must expect four Pump-origin and four direct-migration fixture identities, while still validating the same exact 20 composition labels and zero provider fallback.

## Deterministic proof required

Minimum sufficient GREEN:

- preserve both already-proven REDs as historical evidence;
- `py_compile` all four changed Python files;
- focused `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`;
- nearest production `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py`;
- explicit regression proving the permanent four-candidate C8 supply is READY with four reserve members and exactly two selected members;
- explicit regression proving protocol-stage attribution is 4, not 8, without changing the flat nine-request discovery accounting;
- exact-target lifecycle fixture regression for at least two distinct candidates plus mismatch fail-close;
- zero network-tripwire attempts;
- `git diff --check`;
- exact four-file manifest.

No broad repository suite is required.

## Stop conditions

Stop and return to audit if:

- exact coverage classification cannot distinguish intake from verify requests;
- any ceiling/floor would need weakening;
- admission validation would need weakening;
- a fifth implementation file becomes necessary;
- focused GREEN exposes a distinct owner defect outside this contract;
- provider/network/runtime/authoritative DB activity would be required.

## Money-usefulness contribution

This repair preserves truthful Pump/PumpSwap provenance into the memory intake path, keeps the four-deep reserve resilient, prevents stage-budget false shortage, and ensures lifecycle market evidence is bound to the actually selected token.

## What this still does not unlock

No new Checkpoint 8 proof, operational memory growth, provider access, authoritative DB use, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Budget inflation masquerading as repair:** prohibited; attribution is corrected from existing coverage and ceilings stay frozen.
2. **Double counting:** flat discovery accounting remains all nine governed requests; stage attribution counts only the four verify requests.
3. **Fabricated authority:** direct evidence is carried only when already supplied by the direct owner.
4. **Reserve/selection confusion:** four reserve candidates remain exactly two selected lifecycle candidates.
5. **Wrong-token lifecycle evidence:** exact-target fixture resolution is mandatory and mismatch fails closed.
