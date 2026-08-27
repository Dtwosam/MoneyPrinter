# Printer V1 — V2-9.8B Retained-Evidence Pre-Freeze Role / Provenance / Timing Repair Closeout

Status: **CLOSED PASS**

Closeout verdict:

`V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_REPAIR_CLOSEOUT_PASS`

## 1. Scope closed

This closeout terminates the repair chain opened by the real one-shot campaign
whose first terminal cause was:

`RETAINED_EVIDENCE_ROLE_MISSING`

Historical execution:

- execution: `20260826T204317Z-e42d1dc2cb14`
- campaign: `20260826T204317Z-e42d1dc2cb14-campaign`
- run: `20260826T204317Z-e42d1dc2cb14-campaign-run`

The campaign remains immutable historical evidence. It must not be retried,
resumed, restarted, rewritten, or used as successor authority.

## 2. Root cause and repair

Independent triage established a committed select-then-reject defect: a candidate
could consume a neutral seeded freeze slot before the candidate-local retained
evidence contract required by its admission authority was fully proven.

The completed repair now requires, before the four-candidate neutral freeze:

1. canonical admission authority and required-role consistency;
2. candidate-local qualifying request/response evidence;
3. role/source/request-kind correctness;
4. candidate mint/pool binding;
5. exact current CampaignSourceRequestScope;
6. current request-key-root ownership;
7. pre-holder measured manifest membership;
8. exact campaign/run/cycle logical-stage ownership;
9. measured transport-identity ownership;
10. non-empty durable response hash;
11. mandatory valid/current evidence expiry;
12. retained observation time required by selected activation.

Incomplete, historical, provenance-invalid, or timing-invalid candidates are
excluded before seeded selection.

The final activation validator remains fail closed as defense-in-depth.

## 3. Preserved architecture

The repair does not change the approved V1 campaign architecture:

- successful neutral freeze depth remains exactly 4;
- exactly 2 candidates are selected;
- exactly 2 alternates are report-only;
- no automatic alternate substitution;
- no second selector;
- no scoring, ranking, confidence, or weighted decision logic;
- Source Governor remains mandatory;
- Central Scheduler remains mandatory;
- 4/2/2 campaign capacity remains unchanged;
- standard path remains `WINDOW_15M -> WINDOW_1H -> WINDOW_4H -> stop`;
- `WINDOW_12H` and `WINDOW_24H` remain locked;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- retrieval and all financial capability remain locked.

## 4. Implementation/proof baseline

Implementation and bounded-proof HEAD:

`851d92627c3f5b05b1366af0d0dfef2712a330d8`

Authoritative DB SHA before and after bounded proof:

`b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`

Bounded-proof verdict:

`V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_BOUNDED_PROOF_PASS`

Minimum-sufficient proof results:

- retained-evidence focused A-AI suite: **37 passed**;
- directly affected Cycle-1 / remaining-runtime regressions: **19 passed**;
- touched production imports: PASS;
- `git diff --check`: PASS;
- DB integrity: `ok`;
- DB foreign-key violations: `0`;
- DB byte identity: unchanged;
- live Printer runs: `0`;
- provider calls: `0`;
- RPC/WebSocket: `0`;
- Scheduler ticks: `0`;
- authorizations created/consumed during proof: `0`;
- authoritative DB writes during proof: `0`.

## 5. Authorization state

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c`

remains permanently non-reusable.

This closeout does not create, renew, reuse, resume, restart, or authorize a
successor authorization.

## 6. Failure taxonomy disposition

The historical `RETAINED_EVIDENCE_ROLE_MISSING` campaign blocker was ultimately
classified as a committed code defect with associated design/contract gaps in
pre-freeze qualification. The repaired code and bounded proof close those gaps.

No source-scarcity/provider limitation is being rewritten as a code success.

## 7. Current authority after closeout

This closeout supersedes older current-looking V2-9.8B repair/readiness pointers
for this repair chain.

The only next permitted lane is:

`POST-CLOSEOUT FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS / GOVERNANCE ONLY`

That lane is readiness/governance only. It does **not** authorize:

- a fresh authorization by itself;
- a real campaign;
- provider/RPC/WebSocket activity;
- Scheduler execution;
- retry/rerun/resume/restart/successor of any consumed authorization;
- retrieval, BUY/SELL/HOLD, positions, trades, audits, or PnL.

Candidate-acquisition N2/N7 remains deferred and is not a prerequisite for this
post-closeout readiness lane.

## 8. Closeout rule

A future campaign may occur only after the normal gated sequence independently
establishes fresh readiness and, if separately approved later, issues a new
exact-HEAD / exact-DB one-shot authorization.

`V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_REPAIR_CLOSEOUT_PASS`
