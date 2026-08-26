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
authority is complete.

Target flow:

```text
market/supply eligibility
-> existing tracking/campaign-history gates
-> determine canonical required roles
-> candidate-local retained-role completeness
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

Semantic authority remains:

`required_evidence_roles_for_candidate(...)`

Implementation may factor shared helpers so pre-freeze gating and final
activation validation use exactly the same role matrix:

- `MARKET_PRESENT_POOL` -> `MARKET_OBSERVATION`
- `DIRECT_PUMP_PUMPSWAP` -> `ORIGIN_LINEAGE` + `PUMPSWAP_CONFIRMATION` +
  `MARKET_OBSERVATION`

Missing or malformed admission authority remains fail-closed (defaults to the
existing DIRECT_PUMP matrix / unsupported authority exclusion).

Do not duplicate the matrix in independent owners.

---

## 5. Completeness predicate

```text
required_roles = required roles for admission authority
present_roles = candidate-local retained roles with request_id + response_id
complete = every required role is present
```

Not allowed as substitutes:

- evidence count
- `bool(retained_evidence)`
- another candidate's evidence
- registry hash / migration signature alone
- scoring / ranking / confidence / weights

Pre-freeze completeness is candidate-local ID presence for required roles.
Final activation validation remains the full fail-closed defense for DB rows,
manifest binding, transport identity, freshness, and payload hash.

---

## 6. Authority-specific behavior

### MARKET_PRESENT_POOL

Require only `MARKET_OBSERVATION`.

Do not require `ORIGIN_LINEAGE` or `PUMPSWAP_CONFIRMATION`.

### DIRECT_PUMP_PUMPSWAP

Require all three roles. If current-cycle governed retained references already
exist, reuse exact request/response IDs. Otherwise exclude/defer before freeze.

Do not invent evidence, synthesize source rows, call providers, or downgrade
DIRECT_PUMP to MARKET_PRESENT_POOL.

---

## 7. Pre-freeze location

Place the gate at the latest point before `freeze_eligible_reserve(...)` /
`freeze_eligible_reserve_for_campaign(...)` where production already knows:

- exact candidate identity
- admission authority
- candidate-local retained evidence

The neutral freeze must never see a role-incomplete candidate.

---

## 8. Four-candidate freeze remains locked

When freeze succeeds:

- freeze depth remains four candidates
- exactly two selected
- exactly two report-only alternates
- seeded neutral selection remains unchanged

If role filtering leaves fewer than required freeze depth:

fail honestly before freeze with the existing coverage terminal family:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

Do not shrink freeze. Do not fill with incomplete candidates.

Retained-role completeness is binary eligibility, not preference.

---

## 9. Report-only alternates

Alternates remain report/diagnostic only. They are not activation authority and
must not be auto-substituted.

When freeze succeeds, all four freeze candidates should already have passed the
role-completeness gate. Downstream construction must still preserve authority
separation:

- selected pair = activation authority
- alternates = report/diagnostic evidence

Hard selected-role construction over alternates must not independently
terminalize an otherwise valid selected activation pair.

---

## 10. Final validator remains

Keep `RETAINED_EVIDENCE_ROLE_MISSING` / `RETAINED_EVIDENCE_MISSING` as fail-closed
defense against malformed frozen data, regression, identity mismatch, and
post-freeze invalidation.

---

## 11. Non-goals / locks

This repair does not:

- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  or PnL;
- change 4/2/2 capacity or 15m -> 1h -> 4h -> stop;
- unlock WINDOW_12H / WINDOW_24H;
- weaken holder-as-context memory semantics;
- weaken tracking feasibility or Cycle-1/Cycle-2 historical-disjointness;
- create or reuse authorization;
- mutate the authoritative DB during implementation/proof fixtures.

---

## 12. Observability

Project excluded role-incomplete candidates with at least:

- mint
- admission authority
- missing retained role(s)
- disposition `RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE`

Also project existing `memory_activation_contract.detail` (`mint:missing_role`)
into terminal/report evidence when present.

Observability must not change selection semantics.

---

## 13. Expected owners

- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- focused repair tests
- this design document

No migration expected. If schema cannot represent required retained references,
stop with DESIGN_GAP / MISSING_APPROVED_IMPLEMENTATION_BOUNDARY rather than
adding an unapproved migration.
