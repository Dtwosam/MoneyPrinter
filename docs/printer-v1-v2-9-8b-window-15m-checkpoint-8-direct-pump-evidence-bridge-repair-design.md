# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Direct Pump Evidence Bridge Repair Design

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_DIRECT_PUMP_EVIDENCE_BRIDGE_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

Audit HEAD: `399f46926ff65728535dbfabc8eb9c90800005cf`
Linear: `DTW-47`

## Goal

Repair the consumed C8 failure without weakening any production admission rule, then align the deterministic C8 fixture with the already-active permanent eligible-supply contract so the next readiness review can assess one coherent proof model.

No controlling proof is authorized by this design.

## Approved implementation surface

Only these files may change during implementation unless deterministic RED/static inspection proves an inseparable same-contract dependency:

1. `src/printer_v1/discovery/eligible_token_supply.py`
2. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
3. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
4. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

No migration, Scheduler, Source Governor, admission-owner, memory, retrieval, decision, position, trade, audit, or PnL file is approved.

## 1. Preserve carried direct-Pump authority through the permanent supply bridge

At the exact-mint join from `discovery.candidate_mix` into a market-resolved candidate, carry the existing direct owner's `direct_pump_evidence` forward.

Required behavior:

```python
carried = direct.get("direct_pump_evidence")
if isinstance(carried, Mapping):
    candidate["direct_pump_evidence"] = dict(carried)
```

Do not synthesize evidence if missing or malformed. In that case the downstream `_source_specific_admission_for()` must continue to fail closed.

Do not consult the graduated registry from admission and do not weaken the direct-evidence identity checks.

## 2. Align C8 deterministic supply with permanent four-reserve capacity

Permanent availability deliberately requires at least four eligible reserve members: exactly two selected slots plus one eligible alternate per slot.

C8 therefore needs four deterministic lawful Pump/PumpSwap supply candidates, for example:

- alpha
- bravo
- charlie
- delta

The fixture success-semantics gate and pre-run execution gate must require four distinct, non-infrastructure supply candidates.

This does **not** change active capacity. The canonical neutral selector still selects exactly two candidates, and C8 success still requires exactly two terminal `WINDOW_15M` windows.

Do not reduce the production reserve requirement to make the proof pass.

## 3. Make lifecycle market fixtures exact-target aware

For the C8 lifecycle DexScreener primary and GeckoTerminal fallback factory seams:

- resolve the requested `token_mint` and `pool_address` to the matching deterministic candidate;
- require exact mint+pool correspondence when both are supplied;
- reject unknown or conflicting identities fail-closed;
- build the fixture payload from that resolved candidate, not `candidates[0]`.

General context fixtures may remain candidate-independent where their real contract is candidate-independent.

## 4. Update proof-only real-consumer compatibility expectations

The compatibility owner must expect four Pump-origin and four direct-migration supply identities from the deterministic fixture.

It must continue to exercise the real consumer boundaries and preserve:

- exact 20-label composition coverage;
- provider fallback false;
- no generic ready placeholders;
- zero network attempts under the tripwire.

Final selection/lifecycle is still two-token only.

## 5. Required deterministic regressions

Add focused tests that prove:

1. baseline permanent C8 supply fails RED at `DIRECT_PUMP_EVIDENCE_MISSING` before the production bridge repair;
2. after repair, direct evidence carried by exact mint reaches source-specific admission and the permanent supply is READY;
3. holder/eligible reserve contains four lawful candidates while final selected/graduated supply contains exactly two;
4. the selected two remain the canonical neutral selection output, with no score/rank/confidence/weight;
5. lifecycle primary/fallback fixture factories return the exact requested candidate for at least two distinct candidate identities;
6. unknown or conflicting lifecycle target identity fails closed;
7. tripwire network attempt count remains zero.

The test may use the existing C8 disposable migrated DB and fixture composition. It must not invoke the public campaign or claim a C8 controlling sentinel.

## Minimum sufficient GREEN

- deterministic RED for the consumed defect;
- `py_compile` for all changed Python files;
- focused `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`;
- nearest production Eligible Token Supply contract tests: `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py`;
- explicit zero network-tripwire assertions in new C8 regressions;
- `git diff --check`;
- exact approved changed-file manifest.

No broad repository suite is required.

## Stop conditions

Stop implementation and do not improvise if:

- RED does not reproduce the direct-evidence omission;
- a required change reaches outside the four approved files;
- the production admission owner would need weakening;
- the four-reserve production law would need weakening;
- provider/network/runtime/authoritative DB activity would be required;
- focused GREEN exposes a distinct production defect outside this contract.

Any such condition returns to audit/design before implementation continues.

## Money-usefulness contribution

This repair preserves exact Pump/PumpSwap provenance through the active intake path, proves reserve resilience without changing the two-token learning capacity, and prevents wrong-token lifecycle data from contaminating clean 15m memory.

## What this improves

- exact source-authority continuity;
- permanent eligible-reserve proof realism;
- selected-token lifecycle target correctness;
- C8 forward-readiness coverage.

## What this still does not unlock

- another Checkpoint 8 proof;
- operational memory growth;
- provider/network access;
- authoritative DB use;
- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **False lineage by reconstruction:** mitigated by carrying only exact current-owner evidence.
2. **Four reserve mistaken for four active tokens:** mitigated by preserving canonical exactly-two selection and C8 exactly-two window acceptance.
3. **Wrong-token lifecycle fixture data:** mitigated by exact mint+pool resolution and fail-closed mismatch handling.
4. **Proof-only model drifting from production:** mitigated by preserving permanent policy and real-consumer compatibility checks.
5. **Scope expansion:** implementation is limited to the four named files and minimum focused proof.
