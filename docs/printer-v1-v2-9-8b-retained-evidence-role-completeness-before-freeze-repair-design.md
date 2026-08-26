# V2-9.8B Retained-Evidence Role Completeness Before Freeze Repair Design

**Design verdict:** `V2_9_8B_RETAINED_EVIDENCE_ROLE_COMPLETENESS_BEFORE_FREEZE_REPAIR_DESIGN_PASS`

**Governing triage:** `V2_9_8B_RETAINED_EVIDENCE_ROLE_MISSING_INDEPENDENT_TRIAGE_AUDIT_PASS`

**Primary classification:** `COMMITTED_CODE_DEFECT`

**Secondary findings:** `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`, `DESIGN_GAP`

---

## 1. Governing evidence

Repository:

`/Users/Dtwo1/Developer/MoneyPrinter`

Required branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Baseline HEAD at design/implementation start:

`484f56ccef9fb5bb53003687c80948f62e06d348`

Authoritative DB:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

Required current authoritative DB SHA:

`b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`

No authoritative WAL/SHM/journal is permitted at the design or implementation
boundary.

Failed campaign evidence to preserve:

- execution: `20260826T204317Z-e42d1dc2cb14`
- campaign: `20260826T204317Z-e42d1dc2cb14-campaign`
- run: `20260826T204317Z-e42d1dc2cb14-campaign-run`
- cycle: `20260826T204317Z-e42d1dc2cb14-cycle`
- first terminal cause: `RETAINED_EVIDENCE_ROLE_MISSING`

Consumed authorization (permanently dead / non-reusable):

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c`

Authorization SHA:

`1ca42e9ecc383c13a623ef75ab3abd952259a37a71ea00cf837136c03e770982`

That authorization must never be retried, resumed, restarted, reused, or used
as successor authority. This design creates no fresh authorization.

---

## 2. Proven defect

Production permitted a candidate to reach the neutral seeded freeze while its
candidate-local retained-evidence role contract was already known incomplete.

Canonical authority matrix:

- `MARKET_PRESENT_POOL` requires `MARKET_OBSERVATION`
- `DIRECT_PUMP_PUMPSWAP` requires `ORIGIN_LINEAGE` + `PUMPSWAP_CONFIRMATION` +
  `MARKET_OBSERVATION`

Historical failing selected candidate:

- mint: `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump`
- authority: `DIRECT_PUMP_PUMPSWAP`
- present: `MARKET_OBSERVATION`
- missing before freeze: `ORIGIN_LINEAGE`, `PUMPSWAP_CONFIRMATION`

Causal chain:

1. market/supply eligibility admitted the candidate;
2. neutral seeded freeze received the incomplete DIRECT_PUMP nominee;
3. frozen activation construction then raised `RETAINED_EVIDENCE_ROLE_MISSING`;
4. lifecycle never started.

That is select-then-reject ordering.

Report-only alternates were also hard-built through selected activation role
construction, which incorrectly lets alternate role resolution terminalize an
otherwise valid selected pair.

---

## 3. Repair invariant

A candidate must not enter the neutral seeded freeze unless the exact
candidate-local retained-evidence role contract required by its admission
authority is complete with **qualifying governed candidate-local** retained
evidence.

Target flow:

```text
market/supply eligibility
-> existing tracking/campaign-history gates
-> determine canonical required roles
-> qualifying candidate-local retained-role completeness
-> exclude incomplete candidates
-> neutral four-candidate seeded freeze
-> exactly two selected + two report-only alternates
-> frozen activation construction
-> final retained-role validator
-> handoff/lifecycle
```

Do not add a second selector.

---

## 4. Canonical required-role owner

`admission_authority` is the canonical required-role authority for both:

- pre-freeze completeness
- final selected activation validation

Shared helpers must derive the matrix from admission authority:

- `MARKET_PRESENT_POOL` -> `MARKET_OBSERVATION`
- `DIRECT_PUMP_PUMPSWAP` -> `ORIGIN_LINEAGE` + `PUMPSWAP_CONFIRMATION` +
  `MARKET_OBSERVATION`

Legacy `claims_pump_origin` / `claims_pumpswap_graduation` may remain for
provenance/reporting only. They must be consistent with admission_authority or
derived from it. They must not independently weaken or change the required-role
set. Contradiction fails closed.

Missing or malformed admission authority remains fail-closed.

Do not duplicate the matrix in independent owners.

---

## 5. Qualifying candidate-local retained evidence

A required role counts as present only when the existing authoritative
retained-evidence truth contract can establish qualifying evidence for that
exact candidate.

Reuse/factor existing retained-reference validation owners. Do not create a
second weaker evidence truth system. Do not reduce qualification to
`request_id is not None and response_id is not None`.

Where the existing contract provides the data at the pre-freeze stage,
qualification must establish:

- source request exists
- source response exists
- response belongs to request
- source failure is not presented as success
- expected source/request kind integrity with the retained role binding
- exact evidence role
- exact candidate mint
- exact pool/pair where applicable
- current/unexpired candidate evidence boundary
- payload identity / mint+pool binding using existing market or non-market
  retained-response helpers

Manifest membership and measured transport-identity set ownership are assembled
after freeze in the current production path. They remain final-validator owned
when not already available at the pre-freeze stage. That is not a reduction of
qualifying evidence to ID presence; it is an architectural availability
boundary. If a later lane moves manifest ownership before freeze, pre-freeze
qualification must absorb those checks rather than inventing a weaker parallel
system.

Not allowed as substitutes:

- evidence count
- `bool(retained_evidence)`
- another candidate's evidence
- registry hash / migration signature alone
- scoring / ranking / confidence / weights
- fake/nonexistent request/response IDs

---

## 6. Authority-specific behavior

### MARKET_PRESENT_POOL

Require only qualifying `MARKET_OBSERVATION`.

Do not require `ORIGIN_LINEAGE` or `PUMPSWAP_CONFIRMATION`.

### DIRECT_PUMP_PUMPSWAP

Require qualifying:

- `ORIGIN_LINEAGE`
- `PUMPSWAP_CONFIRMATION`
- `MARKET_OBSERVATION`

If current-cycle governed retained references already exist, reuse exact
request/response IDs. Otherwise exclude/defer before freeze.

Do not invent evidence, synthesize source rows, call providers, or downgrade
DIRECT_PUMP to MARKET_PRESENT_POOL.

---

## 7. Pre-freeze location

Place the gate at the latest point before `freeze_eligible_reserve(...)` /
`freeze_eligible_reserve_for_campaign(...)` where production already knows:

- exact candidate identity
- admission authority
- candidate-local retained evidence
- disposable/live connection needed to qualify governed rows

The neutral freeze must never see a role-incomplete candidate.

---

## 8. Four-candidate freeze remains locked

Existing four-candidate freeze architecture is preserved.

When freeze succeeds:

- freeze depth remains four candidates
- exactly two selected
- exactly two report-only alternates
- seeded neutral selection remains unchanged

If role filtering leaves fewer than required freeze depth:

fail honestly before freeze with the existing coverage terminal family:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

Do not shrink freeze. Do not fill with incomplete candidates.

Retained-role completeness is binary eligibility, not preference. No scoring,
ranking, confidence, weighting, or authority preference.

---

## 9. Report-only alternate semantics

Alternates remain report/diagnostic only. They are not activation authority and
must not be auto-substituted or promoted.

When freeze succeeds, all four freeze candidates should already have passed the
role-completeness gate. Downstream construction must still preserve authority
separation:

- selected pair = activation authority
- alternates = report/diagnostic evidence

Narrow soft handling may prevent missing selected-only retained references on a
report-only alternate from independently terminalizing an otherwise valid
selected activation pair.

Soft handling must not:

- swallow arbitrary integrity failures
- falsify admission authority
- downgrade unknown/unsupported authority to `MARKET_PRESENT_POOL`
- invent retained evidence
- erase the exact diagnostic reason

Unsupported alternate authority / identity corruption must preserve/report the
exact fail-closed state.

---

## 10. Final fail-closed validator

Keep `RETAINED_EVIDENCE_ROLE_MISSING` / `RETAINED_EVIDENCE_MISSING` and related
contract mismatch codes as fail-closed defense against malformed frozen data,
regression, identity mismatch, manifest/transport drift, and post-freeze
invalidation.

The pre-freeze gate prevents known-incomplete candidates from selection. The
final validator remains mandatory defense-in-depth.

---

## 11. Holder semantics

Do not turn holder context into a memory activation gate.

Holder pass/fail/unavailable/budget-bound unknown remains contextual according
to existing design. `FULLY_ELIGIBLE` and future-action eligibility remain honest.

This repair is retained-evidence role completeness only.

---

## 12. Tracking / history composition

Preserve:

- current tracking feasibility pre-freeze gate
- tracking revalidation at handoff
- Cycle-1 current-cycle ordinal repair
- Cycle-2+ historical-disjointness enforcement
- pre-selection campaign-history filtering
- token/pair identity freshness
- final admission defenses

The new gate composes with existing gates. It does not replace or bypass them.

---

## 13. Observability

Project excluded role-incomplete candidates with at least:

- mint
- admission authority
- missing retained role(s) and/or qualification failure detail
- disposition `RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE`

Also project existing `memory_activation_contract.detail` (`mint:missing_role`)
into terminal/report evidence when present.

Observability must not change selection semantics.

---

## 14. Implementation boundary

Expected owners:

- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- focused repair tests
- this design document

No migration expected. If schema cannot represent required retained references,
stop with `DESIGN_GAP` / `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` rather than
adding an unapproved migration.

---

## 15. Cases A–K bounded proof matrix

- **A** MARKET_PRESENT complete passes pre-freeze
- **B** DIRECT_PUMP complete passes pre-freeze
- **C** DIRECT_PUMP incomplete excluded before freeze
- **D** insufficient role-complete freeze depth -> coverage blocker
- **E** report-only alternate does not terminalize selected pair
- **F** final validator still fails `RETAINED_EVIDENCE_ROLE_MISSING`
- **G** nonexistent request/response IDs fail pre-freeze
- **H** mismatched request/response pairing fails pre-freeze
- **I** wrong-candidate mint/pool evidence fails pre-freeze
- **J** contradictory admission_authority vs claims fails closed; roles follow
  admission_authority
- **K** alternate missing selected-only refs does not terminalize selected pair;
  unsupported alternate authority is not rewritten to MARKET_PRESENT_POOL

Production-caller coverage must exercise:

`AuthoritativeLiveOperationalCampaignOwner.run`
-> pre-lifecycle preparation
-> retained-role completeness
-> `freeze_eligible_reserve(...)`
and prove incomplete DIRECT_PUMP is removed before the freeze selector.

Fixture rule: role-complete fixtures must create the minimum real disposable-DB
request/response evidence required by the same pre-freeze contract. Fake numeric
IDs alone are not qualifying evidence.

---

## 16. Failure semantics

- incomplete qualifying roles -> exclude before freeze
- after exclusion, depth < 4 ->
  `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`
- forced incomplete selected frozen candidate ->
  `RETAINED_EVIDENCE_ROLE_MISSING`
- authority/claims contradiction -> fail closed
- unsupported alternate authority -> preserve exact diagnostic; no rewrite

---

## 17. Explicit non-goals

This repair does not:

- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  or PnL;
- change 4/2/2 capacity or 15m -> 1h -> 4h -> stop;
- unlock WINDOW_12H / WINDOW_24H;
- weaken holder-as-context memory semantics;
- weaken tracking feasibility or Cycle-1/Cycle-2 historical-disjointness;
- create or reuse authorization;
- mutate the authoritative DB during implementation/proof fixtures;
- add a second selector;
- auto-promote or substitute alternates.

---

## 18. Implementation verification

Minimum sufficient checks:

- focused repair module
- directly affected Cycle-1/runtime regressions
- syntax/import
- `git diff --check`

Authoritative DB SHA must remain unchanged. No Printer/provider/Scheduler/auth
activity during implementation.

---

## 19. Implementation acceptance conditions

PASS only when:

1. qualifying evidence, not ID presence, gates freeze input;
2. admission_authority owns required roles for pre-freeze and final validation;
3. alternate soft handling is narrow and does not rewrite authority;
4. Cases A–K pass;
5. production-caller coverage proves incomplete DIRECT_PUMP never reaches freeze;
6. authoritative DB SHA unchanged.

---

## 20. Next lane

After implementation correction PASS:

`INDEPENDENT CUMULATIVE IMPLEMENTATION DIFF REVIEW`

Do not run bounded proof, create authorization, or run Printer from the
implementation lane alone.
