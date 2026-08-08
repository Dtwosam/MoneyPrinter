# Printer V1 Post-DTW83 MEMORY_OBSERVATION Activation-Route Repair Design

## 1. Verdict

`V2_9_8B_POST_DTW83_MEMORY_OBSERVATION_ACTIVATION_ROUTE_REPAIR_DESIGN_PASS`

This design is documentation-only. It authorizes no production code, runtime, source fetching, database mutation, authorization package, memory generation, WINDOW_1H+, retrieval, decision, position, trade, audit, PnL, wallet, signing, live execution, real funds, paid API, score/rank/confidence system, embedding, or vector.

## 2. Baseline and confirmed defect

Baseline audit closeout:

- branch `agent/v2-9-8b-post-dtw83-pilot-input-activation-route-audit-closeout`
- commit `bd6317a4250a864c727b6d79a033bbe8256c69b1`
- verdict `V2_9_8B_POST_DTW83_PILOT_INPUT_ACTIVATION_READINESS_AUDIT_PASS_ROUTE_CONTRACT_DRIFT_CONFIRMED`

The exact authorized runtime showed a producer/consumer vocabulary drift:

- the canonical memory-observation activation contract carries source-specific `AdmissionAuthority` values `MARKET_PRESENT_POOL` and `DIRECT_PUMP_PUMPSWAP`;
- `SourceSpecificCandidateAdmission` preserves that authority and, for a market-present candidate without Pump origin proof, exposes `origin_route = admission_authority.value`;
- `pilot_input_readiness.evaluate_readiness_gates()` still uses the legacy-only route set `{GRADUATION_NATIVE, PUMP_CREATE}` for both readiness purposes;
- therefore a lawful MEMORY_OBSERVATION candidate can pass discovery, selection, exact-market and memory-observation gates and then fail deterministically as `PILOT_INPUT_BLOCKED_ACTIVATION`.

Holder budget-bound/failed/unknown state is not the root cause and remains context-only for MEMORY_OBSERVATION. FUTURE_ACTION holder gating remains separate.

## 3. Design decision

Do **not** globally append new strings to the existing `LAWFUL_ROUTES` set.

Instead, make MEMORY_OBSERVATION activation validation purpose-aware and authority-aware using the existing canonical `AdmissionAuthority` model.

### 3.1 Canonical owner

`src/printer_v1/discovery/memory_observation_activation.py` remains the authority owner for source-specific admission semantics.

`src/printer_v1/operator_cli/pilot_input_readiness.py` remains the readiness gate owner and consumes that canonical authority. It must not define a competing source-specific route vocabulary.

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` remains the composition owner that projects the selected candidate's exact admission authority into the readiness carrier.

No second selector, activation executor, Source Governor owner, Scheduler owner, or registry gate is introduced.

### 3.2 Readiness carrier

Extend `ReadinessCandidate` compatibly with an optional explicit field:

`admission_authority: str | None = None`

Rules:

- source-specific MEMORY_OBSERVATION candidates populate it from the exact `SourceSpecificCandidateAdmission.admission_authority.value` / frozen memory-activation contract;
- legacy callers may leave it `None`;
- the field is reporting/validation context only and does not become selection authority;
- include it in `_candidate_surface()` and therefore existing JSON bundle/source-ledger surfaces; no schema migration is required.

### 3.3 Purpose-scoped activation validation

Introduce one narrow readiness helper, preferably in `pilot_input_readiness.py`, that validates the candidate under the requested readiness purpose.

#### FUTURE_ACTION

Preserve current behavior unchanged:

- holder eligibility remains required;
- current legacy activation-route law remains unchanged;
- this repair must not use the new MEMORY_OBSERVATION authority rules to broaden FUTURE_ACTION eligibility.

#### MEMORY_OBSERVATION

Validate source-specific authority through the canonical `AdmissionAuthority` enum, not through a duplicated free-form list.

Allowed source-specific cases:

1. `MARKET_PRESENT_POOL`
   - `admission_authority == MARKET_PRESENT_POOL`;
   - activation route must truthfully represent the same present-pool authority;
   - exact mint/pool/market identity and retained governed evidence must already have passed the existing memory activation contract;
   - no Pump-origin or migration-registry claim may be invented.

2. `DIRECT_PUMP_PUMPSWAP`
   - `admission_authority == DIRECT_PUMP_PUMPSWAP`;
   - the candidate must retain its genuine carried direct activation route from the canonical direct carrier;
   - existing lawful legacy direct routes remain valid only when actually carried by that candidate; do not manufacture `GRADUATION_NATIVE` or `PUMP_CREATE` from the authority name.

Legacy MEMORY_OBSERVATION candidates with no explicit source-specific authority retain the existing legacy route validation for compatibility.

Any unknown authority, unsupported route, or authority/route contradiction returns the existing `PILOT_INPUT_BLOCKED_ACTIVATION` fail-closed terminal.

### 3.4 No redundant registry confirmation

The repair must not query or re-check the graduated registry after candidate discovery/selection.

A market-present candidate already admitted through exact governed present-pool evidence must not be rejected merely because it lacks a Pump migration-registry row. Direct Pump/PumpSwap candidates continue to rely on their already-carried exact direct evidence.

## 4. Minimal production surface for later implementation

Expected production files:

1. `src/printer_v1/operator_cli/pilot_input_readiness.py`
   - compatible readiness-carrier field;
   - purpose-scoped authority-aware activation validator;
   - candidate-surface reporting.

2. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
   - project exact admission authority into the readiness candidate without changing selection, holder, source or Scheduler ownership.

3. `src/printer_v1/discovery/memory_observation_activation.py`
   - only if a tiny reusable canonical validation/helper is needed to avoid duplicating `AdmissionAuthority` semantics. Do not refactor unrelated activation behavior.

No migration, wrapper, authorization, source adapter, Source Governor, Scheduler, liquidity floor, holder budget, discovery budget, selection authority, memory closeout, retrieval or financial file is required by this design.

## 5. Focused implementation tests required

Use TDD and minimum sufficient deterministic tests. No live network and no authoritative DB mutation.

Required cases:

1. MEMORY_OBSERVATION + truthful `MARKET_PRESENT_POOL` authority/route + all other gates pass => `PILOT_INPUT_READY`.
2. MEMORY_OBSERVATION + truthful direct `DIRECT_PUMP_PUMPSWAP` carrier with its genuine lawful direct route => `PILOT_INPUT_READY`.
3. MEMORY_OBSERVATION legacy candidate with no explicit admission authority continues to follow existing legacy route behavior.
4. Unknown admission authority => `PILOT_INPUT_BLOCKED_ACTIVATION`.
5. Known authority with contradictory route => `PILOT_INPUT_BLOCKED_ACTIVATION`.
6. Market-present candidate must not require or fabricate Pump migration/registry evidence.
7. Holder false / unavailable / budget-bound unknown remains non-blocking for MEMORY_OBSERVATION when accounting/evidence is otherwise valid.
8. The same holder condition remains blocking under FUTURE_ACTION according to existing behavior.
9. FUTURE_ACTION legacy route behavior remains byte/semantic compatible with the pre-repair contract.
10. Ordered two-candidate readiness surface preserves exact slot order and admission authority.

Nearest existing focused suites should be extended rather than creating a broad new harness, especially:

- `tests/test_v2_9_7e_45_pilot_input_readiness.py`
- `tests/test_v2_9_8b_remaining_runtime_blocker_repair.py`
- the existing focused memory-observation activation tests that own `FrozenMemoryActivationCandidate` / `AdmissionAuthority`, if present in the implementation baseline.

Run only these nearest suites plus compile/diff checks in the implementation lane. A broader suite is deferred to the later bounded proof/major closeout if risk warrants it.

## 6. Bounded proof required after implementation

Proof must be offline/deterministic and stop before lifecycle/runtime activation.

It must prove:

- source-specific market-present selected pair reaches MEMORY_OBSERVATION readiness;
- direct source-specific carrier remains valid;
- contradictory/unknown authority blocks;
- FUTURE_ACTION remains unchanged;
- holder-context separation remains intact;
- no source request/response/failure is created by the readiness repair;
- no Scheduler runtime work is created by the readiness repair;
- no authoritative DB is mutated;
- no registry membership recheck occurs;
- no memory window, retrieval, decision, position, trade, audit or PnL row is created.

Only after implementation PASS, bounded proof PASS, closeout, and a fresh authoritative DB/operational rereadiness audit may a new real ordinary WINDOW_15M authorization be considered.

## 7. Money-usefulness contribution

This repair allows lawful exact-market Solana memecoin candidates to reach observation memory instead of being discarded by a stale vocabulary gate. That preserves useful examples across holder states and market conditions while keeping action eligibility separate and locked.

## 8. What the repair improves

- Removes deterministic source-specific activation-route drift at the MEMORY_OBSERVATION readiness boundary.
- Makes the consumer explicitly depend on the canonical admission-authority contract.
- Preserves truthful market-present versus direct Pump/PumpSwap lineage.
- Prevents another authorization from being spent on the same deterministic blocker after proof/rereadiness.

## 9. What remains locked / not proven

This design does not prove that a subsequent live 15m run will succeed. Provider availability, fresh candidate supply, holder evidence/accounting, tracking feasibility, retained-evidence integrity, Scheduler work, 15m collection and clean-memory closeout remain independent runtime gates.

Still locked:

- WINDOW_1H / 4H / 12H / 24H;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- live wallet/private keys/signing/real funds/live execution;
- paid APIs;
- scores/rankings/confidence/weights;
- embeddings/vectors.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Control |
|---|---|
| Global allowlist expansion accidentally broadens FUTURE_ACTION | Purpose-scoped validation; FUTURE_ACTION remains unchanged |
| Source-specific authority and route become two contradictory truths | Explicit authority/route consistency validation |
| Direct candidates are forced to use the authority enum string instead of genuine carried route | Preserve direct carrier's existing activation route and validate pairing |
| Market-present candidates are forced through Pump registry/migration proof | Explicit no-registry-recheck rule |
| Unknown authority is silently accepted | Enum parse / exact typed validation fails closed |
| Holder state becomes action authority in memory mode | Preserve holder as MEMORY_OBSERVATION context only |
| New selector or executor duplicates ownership | Existing campaign/readiness/memory-activation owners only |
| Broad regression work slows narrow repair | TDD + nearest focused suites; broader proof only at closeout |
| Another live authorization is spent before deterministic closure | No authorization until implementation + bounded proof + closeout + rereadiness PASS |

## 11. Stop conditions

Stop the later implementation as BLOCKED if:

- the current repository no longer matches this audited producer/consumer path;
- supporting `MARKET_PRESENT_POOL` requires fabricating Pump-origin or registry evidence;
- a new source call, source owner, Scheduler owner, selector, migration, or activation executor is required;
- FUTURE_ACTION must be weakened to make MEMORY_OBSERVATION pass;
- unknown authority cannot remain fail-closed;
- focused tests reveal a separate architecture blocker outside this repair.
