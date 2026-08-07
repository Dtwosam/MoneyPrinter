# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-47 Direct Pump Evidence Bridge Repair Closeout

Date: 2026-08-07

Verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_DIRECT_PUMP_EVIDENCE_BRIDGE_REPAIR_OFFLINE_PASS`

Linear: `DTW-47`

## Controlling lineage

- Consumed C8 proof HEAD: `ecd399ef4f4aeee6cf541e4292bb6a5229c943b2`
- DTW-47 V3 design HEAD: `ea6a856d3386050eb4c84710a0aadf3f8a7a9f9a`
- Repair commit: `986f1b1e839c91203d0781e5f7357f7ee64b7243`
- Repair message: `Repair Checkpoint 8 direct Pump evidence bridge`

GitHub independent comparison confirms the repair is exactly one commit over V3 design HEAD and changes exactly the six approved files.

## Failure evidence that opened DTW-47

The one authorized post-DTW-46 C8 attempt was consumed once and failed before a frozen C8 summary with:

`DIRECT_PUMP_EVIDENCE_MISSING:5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei`

The attempt is historical and may not be retried, resumed, restarted, or reused.

Two deterministic offline REDs then established the repair contract:

1. Exact permanent-supply path reproduced `DIRECT_PUMP_EVIDENCE_MISSING` with `NETWORK_ATTEMPTS=0`.
2. Four-reserve path produced:
   - 4 fixture candidates;
   - 9 direct-discovery governed requests;
   - required capacity 4;
   - eligible reserve 0;
   - `LAWFUL_WORK_REMAINING_WITH_CAPACITY`;
   - `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`;
   - 19 flat operations remaining;
   - `NETWORK_ATTEMPTS=0`.

Static owner tracing resolved the nine requests as five `DIRECT_MIGRATION_INTAKE` requests plus four `DIRECT_MIGRATION_VERIFY` PumpSwap verification requests. Therefore no stage ceiling increase was justified.

## Implemented repair

The approved repair does all of the following without weakening policy:

1. Carries the already-produced exact `direct_pump_evidence` from direct migration discovery through the permanent exact-mint market bridge.
2. Charges direct-migration protocol-confirmation usage from exact existing `source_request_coverage` rows matching PumpSwap `pumpswap_signature_pool_resolution` / `DIRECT_MIGRATION_VERIFY`, rather than `source_requests - 1` arithmetic.
3. Leaves the permanent stage reservation unchanged.
4. Expands deterministic C8 reserve fixture depth from two to four lawful Pump/PumpSwap candidates while preserving canonical neutral final selection at exactly two tokens.
5. Makes lifecycle market fixtures exact-target aware and fail closed on missing/conflicting mint+pool identity.
6. Updates only stale C8 reserve-depth assertions in the two V3-approved tests.

No score, rank, confidence, weighting, provider fallback, admission bypass, Source Governor bypass, Scheduler bypass, or new production owner was introduced.

## Exact changed manifest

- `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
- `tests/test_v2_9_8b_window_15m_checkpoint8_blocked_proof_repair.py`
- `tests/test_v2_9_8b_window_15m_checkpoint8_fixture_response_semantics_gate.py`
- `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

No seventh file changed.

## Minimum sufficient GREEN

Local isolated offline implementation produced:

- changed-file `py_compile`: PASS;
- C8 real-consumer compatibility: `8 passed in 6.48s`;
- nearest Eligible Token Supply architecture: `26 passed in 7.59s`;
- full focused C8 suite: `99 passed in 11.85s`;
- `git diff --check`: PASS;
- exact six-file manifest: PASS;
- zero-provider/network regressions: PASS;
- no controlling C8 proof run.

The focused permanent-supply regression additionally proves:

- `supply.ready is True`;
- terminal is `CANDIDATE_SUPPLY_READY`;
- holder reserve depth is 4;
- final graduated supply remains 2;
- required capacity is 4;
- eligible reserve count is 4;
- direct discovery requests are 9;
- exact direct-migration protocol-confirmation request count is 4;
- terminal discovery reason is `ELIGIBLE_CAPACITY_MET`;
- every reserve candidate carries matching confirmed direct Pump evidence;
- network tripwire count remains zero.

The exact-target lifecycle regression proves both DexScreener-primary and GeckoTerminal-fallback fixtures bind to the requested mint+pool and reject a mismatched mint+pool pair, with zero network attempts.

## Independent GitHub inspection

GitHub inspection confirmed:

- repair commit exists with the expected message;
- base `ea6a856...` -> repair `986f1b1...` is ahead by exactly one commit;
- merge base is exactly V3 design HEAD;
- remote branch tip is identical to repair commit;
- the diff is exactly the six approved files;
- production bridge change is limited to evidence carry-forward, exact verification attribution, and diagnostic exposure;
- fixture changes implement four-reserve depth and exact-target lifecycle behavior;
- stale test changes alter reserve-depth expectations only.

## Safety and lane boundaries

This repair did not:

- contact any provider or network;
- use the authoritative DB;
- run Printer/provider runtime;
- create or consume a new C8 authorization;
- run a new C8 controlling proof;
- change Source Governor or Central Scheduler ownership;
- change migration schema or capability locks;
- enable operational `WINDOW_15M` memory growth;
- enable `WINDOW_1H+`;
- enable retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Money-usefulness contribution

The repair restores truthful graduated-candidate continuity and resilient four-deep reserve readiness without inflating source budgets or activating extra tracked tokens. Printer can preserve enough lawful candidate depth for reliable two-token learning while retaining exact evidence and accounting provenance.

## What the lane improves

- direct Pump evidence continuity through permanent supply;
- truthful protocol-confirmation stage attribution;
- four-reserve resilience;
- exact-target lifecycle fixture fidelity;
- focused C8 proof-model consistency.

## What the lane still does not unlock

- another Checkpoint 8 controlling proof;
- Checkpoint 8 completion;
- operational memory growth;
- provider/network access;
- authoritative DB use;
- any later checkpoint or `WINDOW_1H+` capability;
- retrieval or paper-trading capabilities.

## Proof required before Checkpoint 8 completion

DTW-47 completion is only an offline repair closeout. Checkpoint 8 remains open and still requires a separately authorized fresh one-shot controlling C8 attempt that satisfies the entire approved acceptance law, followed by independent inspection and Checkpoint 8 closeout.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A later controlling proof may expose a new, unrelated contract defect. If so, preserve that attempt and open only the narrow evidence-driven lane required.
2. Four reserve candidates must not be confused with four active lifecycle tokens; final selection remains exactly two.
3. Exact stage attribution now depends on the existing coverage identities remaining truthful and complete; any future owner change must preserve those identities.
4. No broader suite was run because the approved risk-based verification requires only the nearest contract suites and full focused C8 suite for this repair.

DTW-47 offline repair is complete. Stop before any new Checkpoint 8 proof authorization or execution.
