# Printer V1 — V2-9.8B `WINDOW_15M` Freeze / Holder-Budget Decoupling Repair Design

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Memory-Observation Freeze / Holder-Budget Decoupling Repair`  
**Design baseline branch:** `agent/v2-9-8b-window-15m-continuous-supply-evidence-repair`  
**Design baseline HEAD:** `4f4bcade3c84771342bb4132cf4cb179d8daf517`  
**Primary prior implementation commit:** `4fca7518bf73d64e49b8163c1aef4e38dca372f4`

## 1. Design verdict

`V2_9_8B_WINDOW_15M_FREEZE_HOLDER_BUDGET_DECOUPLING_REPAIR_DESIGN_PASS`

This design approves one narrow implementation-and-proof lane to remove the confirmed coupling between:

1. the bounded market/protocol-qualified candidate universe used for memory observation; and
2. the smaller holder-context workload that can fit inside the existing campaign operation ceiling.

It does not approve a real authorization, provider contact, authoritative database mutation, or a live `WINDOW_15M` run.

## 2. Roadmap alignment

The lane follows the required V2 pattern:

1. **Audit/readiness:** complete — the continuous proof exposed the exact first blocker.
2. **Design/specification:** this document.
3. **Implementation:** limited to the budget/admission integration defect.
4. **Bounded proof:** focused tests plus the existing single continuous disposable wrapper-to-memory proof.
5. **Closeout:** required before any independent readiness review.

The repair preserves all V1 restrictions and does not add a new discovery engine, Scheduler owner, source owner, memory writer, selection score, confidence system, ranking system, embedding, vector, trading capability, or live execution capability.

## 3. Confirmed current state

The preceding branch successfully repaired the original empty-stage-evidence failure:

- frozen production transports now emit measured identities;
- direct migration and protocol-confirmation stages seal;
- isolated ordinary graduated supply produces four valid candidates;
- the ordinary supply can produce two selected plus two alternates in isolation.

The continuous public path still stops before handoff with:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

The exact integration defect is:

```text
holder-budget-derived candidate_cap
        ↓
truncates graduated admission universe to three
        ↓
only three candidates can reach MEMORY_OBSERVATION_ELIGIBLE conversion
        ↓
MINIMUM_FREEZE_DEPTH=4 cannot be met
```

This is incorrect for the adopted memory architecture because holder evidence is contextual for memory observation and remains a separate future-action gate.

## 4. Non-negotiable design invariants

The repair must preserve these constants and rules:

- operation ceiling remains `45`;
- zero-transport validation charge remains `9`;
- snapshot reservations remain `2 + 4`;
- holder worst-case admission check remains `5` transport operations;
- permanent holder-stage measured-transport ceiling remains `8`;
- `MINIMUM_FREEZE_DEPTH` remains `4`;
- freeze output remains exactly two selected plus two alternates;
- holder pass is not required for `MEMORY_OBSERVATION_ELIGIBLE`;
- holder pass remains required for `FULLY_ELIGIBLE` and any future-action policy;
- request counts and measured transport-operation counts remain separate;
- missing or contradictory transport accounting remains a blocking accounting fault;
- no unknown holder fact may be represented as a holder pass;
- selection remains deterministic, categorical and neutral.

No ceiling may be raised and no admission gate may be lowered merely to make the proof pass.

## 5. Target architecture

### 5.1 Two independent bounded domains

The campaign must maintain two different bounded domains.

#### Domain A — Observation candidate universe

The observation universe contains candidates that have proven:

- Solana mint identity;
- exact PumpSwap pool identity;
- valid graduation/protocol confirmation;
- current exact-pool liquidity at or above the existing floor;
- valid source provenance and evidence expiry;
- no unresolved identity conflict;
- lawful tracking state.

This universe is bounded by the existing operational candidate maximum, not by the holder budget.

The holder ledger must never decide how many candidates exist in this universe.

#### Domain B — Holder-context evaluation workload

Holder evaluation is a best-effort, budget-bounded context collection over Domain A.

The holder workload is bounded by:

- current remaining campaign operations;
- the five-operation worst-case pre-attempt admission rule;
- exact measured transport operations charged after each attempt;
- the permanent holder-stage ceiling of eight measured operations;
- campaign deadline;
- Source Governor and source contract rules.

Budget exhaustion stops additional holder requests. It does not delete candidates from Domain A.

## 6. Exact operation-accounting design

### 6.1 Separate request and transport truth

`CampaignOperationLedger` must continue to expose both:

- `governed_requests`;
- `underlying_transport_operations`.

They must be populated from different authorities:

| Field | Authority |
|---|---|
| `governed_requests` | distinct action-local durable Source Governor request IDs |
| `underlying_transport_operations` | unique measured `TransportOperationIdentity` records from existing six-unit evidence |
| `zero_transport_operations` | existing fixed local-validation charge |
| snapshot reservations | existing fixed reservation constants |

A governed request containing multiple measured transports must not be charged as one transport. A retained-evidence reuse with zero fresh transport must not be charged as a fresh transport.

### 6.2 Pre-holder budget snapshot

Before holder evaluation, construct one immutable pre-holder snapshot from the existing campaign accounting owner.

Recommended logical shape:

```python
@dataclass(frozen=True)
class PreHolderBudgetSnapshot:
    governed_request_ids: tuple[int, ...]
    measured_transport_identity_keys: tuple[tuple[object, ...], ...]
    governed_request_count: int
    measured_transport_count: int
    zero_transport_operations: int
    reserved_snapshot_operations: int
    reserved_snapshot_completion_operations: int
```

This is not a second accounting owner. It is a frozen projection of the existing Source Governor manifest and campaign six-unit evidence.

The snapshot must fail closed when:

- a request ID is missing from campaign ownership;
- a measured identity is duplicated;
- a stage reports a transport count without identities;
- request coverage and durable request IDs disagree;
- the existing stage evidence cannot prove the pre-holder transport count.

### 6.3 Ledger construction

Replace any call that implicitly sets request count equal to transport count on the permanent operational path.

The ledger constructor must receive exact independent values:

```python
build_ledger_from_exact_counts(
    governed_request_count=...,
    underlying_transport_operations=...,
    deadline_at=...,
)
```

A compatibility wrapper may remain for older paths only where equality is explicitly proven and tested.

`charged_operations` remains:

```text
underlying_transport_operations + zero_transport_operations
```

Governed request count remains reporting and reconciliation truth; it is not independently added to the operation charge.

## 7. Candidate admission design

### 7.1 Permanent memory mode

For permanent memory-observation mode, `_graduated_admission()` must receive the bounded market/protocol candidate maximum, not `ledger.candidate_cap()`.

The cap must be derived from existing limits, for example the smaller of:

- the existing graduated-supply operational maximum;
- the existing overall candidate maximum;
- the actual unique candidate count.

No new numeric policy is introduced.

### 7.2 Legacy modes

Legacy non-permanent modes may retain their current holder-coupled admission behavior where holder eligibility is part of that mode’s actual admission contract.

The repair must be scoped explicitly to permanent memory-observation operation. It must not silently change readiness or future-action semantics elsewhere.

## 8. Incremental holder-context collection

### 8.1 Non-throwing pre-attempt decision

Add a non-mutating admission decision beside the existing strict `admit_candidate()` behavior.

Recommended shape:

```python
@dataclass(frozen=True)
class HolderAttemptAdmission:
    allowed: bool
    reason: str | None
    available_before_reservation: int
    required_worst_case_operations: int
    permanent_stage_operations_used: int
    permanent_stage_operations_remaining: int
```

The existing raising method may remain for strict legacy callers.

The permanent memory path uses the decision method before each candidate.

### 8.2 Loop behavior

For candidates in the existing deterministic order:

1. Check campaign deadline.
2. Check whether five worst-case operations can still be admitted.
3. Check whether the permanent holder-stage ceiling still permits another attempt.
4. When admitted, run the existing governed holder bundle.
5. Charge the exact measured transport count returned by the holder persistence owner.
6. Preserve request IDs, coverage entries, transport identities and source outcome.
7. Continue while budget permits.
8. When budget does not permit another attempt, stop without raising an accounting exception.

The categorical result is:

`HOLDER_CONTEXT_BUDGET_EXHAUSTED`

This is a bounded completion state, not an accounting failure.

### 8.3 Stage sealing

When at least one holder request was attempted:

- seal the holder stage with its real measured evidence;
- preserve all attempted source outcomes;
- include evaluated and unattempted candidate identities;
- report `budget_exhausted=true` where applicable.

When no holder request can lawfully start:

- create no governed request;
- either omit the source stage through the existing no-operation path or use the existing `PRE_OPERATION_NO_WORK` contract;
- use reason `HOLDER_CONTEXT_BUDGET_UNAVAILABLE_AFTER_DISCOVERY`;
- never seal an empty started stage.

An attempted holder request with missing or contradictory measured evidence remains an accounting blocker. This design changes only clean budget exhaustion before a new request begins.

## 9. Holder result contract

Extend the existing holder result/report surface without adding a schema migration.

Required fields:

```text
holder_facts
evaluated_candidate_mints
unattempted_candidate_mints
budget_exhausted
budget_exhaustion_reason
ledger_before_holder
ledger_after_holder
governed_request_count
measured_transport_count
source_request_ids
source_request_coverage
accounting_blocker
accounting_blocker_reason
```

For each unattempted candidate, create an in-memory context fact:

```text
eligible = false
holder_condition = UNKNOWN
holder_evidence_status = SOURCE_NOT_EVALUATED_BUDGET_BOUND
future_action_eligibility = BLOCKED_OR_UNKNOWN
source_name = null
source_request_ids = []
```

This context must create no source rows and must never become `FULLY_ELIGIBLE`.

## 10. Memory-observation conversion

Build observation rows from the full Domain A universe, not only from candidates with holder facts.

For each candidate:

- preserve exact mint and pool;
- preserve current liquidity/protocol evidence and expiry;
- attach actual holder context when evaluated;
- attach categorical budget-bound unknown context when unattempted;
- set `memory_observation_eligible=true`;
- set `fully_eligible=true` only when the actual holder result passed;
- preserve `future_action_eligibility=BLOCKED_OR_UNKNOWN` unless the explicit future-action policy is satisfied.

Holder source failure, rate limiting, extreme concentration or unattempted budget-bound state may reduce context completeness but must not erase an otherwise valid memory-observation candidate.

Missing or contradictory market/protocol evidence still blocks that candidate.

## 11. Freeze and handoff design

The existing `freeze_eligible_reserve()` remains the sole freeze owner.

Its inputs must contain all valid observation rows from Domain A.

Acceptance:

- exactly four fresh, distinct, unexpired observation candidates;
- distinct mint and pool identities;
- deterministic neutral freeze;
- exactly two selected;
- exactly two alternates;
- no overlap;
- selection does not consider holder pass, holder availability, liquidity magnitude above the floor, provider order, popularity or source count;
- exact selected token/pair identities flow into the existing atomic handoff.

The freeze depth and selection algorithm are not changed.

## 12. Terminal and reporting semantics

The campaign must distinguish:

| Condition | Campaign effect |
|---|---|
| Holder budget exhausted before another attempt | memory may continue; future action remains blocked/unknown |
| Holder source unavailable with complete accounting | memory may continue with truthful context |
| Holder concentration fails policy with complete accounting | memory may continue; `FULLY_ELIGIBLE` false |
| Holder transport accounting missing/contradictory | accounting blocker; no handoff |
| Fewer than four valid market/protocol observation candidates | `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` |
| Four valid observation candidates but fewer holder checks than candidates | freeze may proceed with unknown context for unattempted candidates |

The report must include budget state before and after each holder attempt.

## 13. Schema impact

No migration is expected.

Use existing:

- holder attempt tables;
- source request/response/failure tables;
- campaign diagnostics/report JSON;
- reserve-layer evidence JSON;
- campaign six-unit stage evidence;
- source coverage manifests.

A schema migration is forbidden unless implementation proves an exact required durable fact cannot be represented by an existing canonical surface. In that case the lane must stop BLOCKED for a separate design review.

## 14. Focused verification

Minimum required focused tests:

1. Exact request count and measured transport count are separate.
2. The measured count, not request count, drives operation charging.
3. Four market/protocol candidates survive when holder `candidate_cap()` would be three.
4. Permanent observation admission does not call `_graduated_admission()` with the holder cap.
5. Low-cost holder evidence can evaluate four when actual budget allows.
6. Higher-cost holder evidence stops after two or three without an exception.
7. Unattempted candidates create zero source requests.
8. Unattempted candidates receive exact budget-bound unknown context.
9. Actual holder failures remain context when accounting is complete.
10. Missing holder transport evidence still blocks.
11. Only actual holder passes create `FULLY_ELIGIBLE`.
12. Four observation rows freeze to two selected plus two alternates.
13. Fewer than four market/protocol-qualified rows still block.
14. Legacy non-permanent behavior remains unchanged.
15. Holder-stage and campaign-wide request/transport reconciliation remains exact.
16. Replay reconstructs the same counts and identities.

## 15. Continuous proof

After focused tests pass, rerun the existing single continuous disposable proof:

```text
one-shot wrapper
→ real operational child
→ activation preflight
→ ordinary measured discovery
→ four market/protocol-qualified candidates
→ budget-bounded holder context
→ four MEMORY_OBSERVATION_ELIGIBLE rows
→ two selected + two alternates
→ atomic handoff
→ Central Scheduler
→ two logical 900-second WINDOW_15M lifecycles
→ Lane K
→ two clean episodes
→ two exact canonical fingerprints
```

The proof must use:

- disposable Migration-052 database;
- disposable Git/evidence package;
- frozen lawful production transport seams;
- controlled clock only for the 900-second lifecycle;
- zero external network;
- no patched-out preflight;
- no replacement campaign owner;
- no preassembled graduation proofs;
- no Source Governor or Scheduler bypass.

PASS requires:

- one authorization consumed exactly once;
- one child invocation;
- no retry, resume, restart or successor;
- four unique observation candidates;
- two selected and two alternates;
- exact evaluated and unattempted holder identities;
- operation ceiling never exceeded;
- two token slots;
- two windows spanning at least 900 logical seconds;
- clean cadence, anchors, context and E2Q;
- exactly two current-run `CLEAN_MEMORY` episodes;
- exactly two exact-linked fingerprints;
- `operational_lifecycle_pass=true`;
- `clean_memory_outcome_pass=true`;
- zero unrelated promotion;
- exact source/stage/mutation truth;
- zero active or locked residue;
- stable zero-source report-only replay;
- zero forbidden capability deltas;
- authoritative DB byte-identical.

Run one repository-approved broad regression only after the continuous proof passes.

## 16. Money-usefulness contribution

The repair allows Printer V1 to preserve a useful four-candidate memory-observation reserve even when the remaining campaign budget cannot collect holder context for every candidate.

This improves money usefulness by:

- retaining more valid market/protocol observations;
- preserving two alternates instead of prematurely collapsing the pool;
- preventing holder-source availability from becoming a false memory gate;
- keeping future-action safety fully blocked when holder evidence is missing;
- producing more truthful memories without inventing safety evidence.

## 17. What this lane still does not unlock

Even after PASS, this lane does not unlock:

- a real authorization;
- live source execution;
- `WINDOW_1H`, 4h, 12h or 24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallet, private-key, signing or real-fund capability.

The next permitted step after PASS is an independent read-only readiness review.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- A malformed pre-holder accounting snapshot could undercharge the holder stage. Mitigation: identity-based fail-closed reconciliation.
- Selected candidates may have unknown holder context. This is intended for memory only; future action remains blocked.
- A compatibility caller may still rely on request=transport equality. Mitigation: explicit compatibility tests and no silent inference.

### Setbacks

- Actual measured pre-holder transport usage may permit only zero, two or three holder evaluations.
- This is acceptable for memory observation but means holder-context completeness can vary by campaign.

### Efficiency blockers

- Repeated full continuous runs are expensive compared with focused tests.
- Use focused budget and holder-loop tests first; run the continuous proof only after all deterministic checks pass.
- Do not run the broad suite until the continuous proof succeeds.

## 19. Implementation scope

Expected production scope is narrow:

- `holder_reliability_budget_control.py`;
- `authoritative_live_operational_campaign.py`;
- holder result/report carrier where required;
- focused tests;
- continuous proof assertions;
- design and closeout documents.

Do not modify the freeze owner, fingerprint owner, Scheduler owner, Source Governor, memory promotion owner or database schema unless a directly proven integration requirement makes it unavoidable.

## 20. Final design decision

The correct repair is not to lower freeze depth, raise the operation ceiling, reduce truthful measured transport charges, or fabricate holder evidence.

The correct repair is:

```text
preserve the bounded four-candidate market/protocol observation universe
+
collect as much truthful holder context as the existing budget permits
+
mark the remainder unknown and future-action blocked
+
freeze memory candidates independently
```

Final design verdict:

`V2_9_8B_WINDOW_15M_FREEZE_HOLDER_BUDGET_DECOUPLING_REPAIR_DESIGN_PASS`
