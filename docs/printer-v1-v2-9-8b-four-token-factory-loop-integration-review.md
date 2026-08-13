# Printer V1 V2-9.8B Four-Token Factory-Loop Integration Review

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_FACTORY_LOOP_INTEGRATION_REVIEW_PASS_READY_FOR_FINAL_INTEGRATION_IMPLEMENTATION`

This is a static/read-only integration review. It authorizes no runtime, source
fetch, Scheduler execution, operational DB mutation, migration application,
memory generation, proof run, retrieval, decision, position, trade, audit, or
PnL capability.

## Baseline

- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Reviewed HEAD: `175d8b73a0bd3f64a3579e9e88cf56c81f67c2fd`
- Active design: `docs/printer-v1-v2-9-8b-four-token-bounded-capacity-proof-integration-design.md`
- Pre-admission prerequisite reclose: accepted at the reviewed HEAD.
- Migration `055_pre_admission_discovery_attempt_ownership.sql` remains intentionally unapplied to the authoritative operational DB.

## Review conclusion

The existing canonical factory can host the exact 4/2/2 proof without a second
runner, second Scheduler, second factory, or another schema migration. The final
implementation must, however, integrate the already-built controller and
pre-admission seam across the following exact owners. These are one coordinated
implementation boundary, not independent optional changes.

## 1. One existing event loop is the integration owner

`run_one_command_15m_factory(...)` already accepts the proof controller and
later-cycle callback, but they are currently preflight-only inputs and are not
used by the execution loop.

The existing loop remains the sole loop. In proof mode it must choose between:

1. cancellation / lease / DB / shared-terminal safe stop;
2. already-due lifecycle work;
3. proof deadline;
4. due cycle-2 admission work;
5. the earliest authoritative future lifecycle/admission/deadline boundary.

No admission thread, second runner, busy polling, `sleep(1)` retry loop, or
independent discovery loop is allowed.

## 2. Admission health is projected twice around discovery

A fresh authoritative 12-field projection is required before spending the
one-shot cycle-2 discovery opportunity.

If that discovery returns `PAIR_READY`, discovery has itself consumed governed
source/Scheduler capacity. Therefore a second fresh authoritative projection is
required before `admit_two_token_cycle_from_attempt(...)`.

The post-discovery projection, not the stale pre-discovery projection, is the
health authority used by the atomic cycle-2 consumption transaction.

If the second projection defers or blocks admission, the frozen pair remains
unconsumed and discovery is never rerun.

After cycle 2 is admitted there is no further fresh-cycle opportunity under the
2-cycle ceiling, so pre-admission health projection must not continue and must
not misclassify lawful cycle-2 jobs as first-cycle orphans.

## 3. Later-cycle production supply reuses the existing GraduatedSupply owner

The operational callback is already one-shot and durable, but its production
candidate-supply dependency is intentionally unwired.

Final integration must factor/reuse the same permanent `build_graduated_supply`
composition already used by the authoritative FULL_PILOT path. It must not add a
second discovery, gate, holder, liquidity-floor, selection, retry, or provider
policy.

Permanent GraduatedSupply already owns a unique campaign source-request scope
and collision-checks the request-key root before provider I/O. Cycle-2 source
lineage must be read back from the exact durable request/response/failure rows
under that unique cycle-2 scope and passed to the existing pre-admission source
links. Do not infer lineage from global row deltas.

## 4. Neutral base token/pair identity projection is required before PAIR_READY

Migration 055 correctly foreign-keys the frozen pair to `printer_tokens` and
`printer_pairs`. Disposable tests preseeded these rows, while a genuinely fresh
GraduatedSupply candidate may not have them yet.

The database foundation permits a neutral token identity because
`printer_tokens.token_status` is nullable. Therefore no schema change is needed.

Factor one identity-only persistence owner from the existing combined handoff:

- find or create token by exact mint;
- keep newly created `token_status` NULL;
- find or create pair by exact pair address;
- require the pair's canonical token owner/base mint to match the candidate;
- return exact token/pair row ids;
- create no tracking-queue row;
- set no TRACK_NORMAL state;
- enqueue no Scheduler job;
- create no cycle/window/memory state.

The existing handoff should reuse this factored identity owner before it performs
its later tracking activation, so there is one token/pair identity policy.

## 5. Cycle-aware step namespace is mandatory

The current opening planner still uses run-global `t1_*` / `t2_*` keys. In proof
mode it must use the committed `cycle_step_key(...)` owner:

- cycle 1 remains legacy `t1_*`, `t2_*`;
- cycle 2 uses `t1_c0002_*`, `t2_c0002_*`.

The anchored 15m planner already derives later keys from the opening prefix, so
once the opening key is correct the rest of the 15m cadence remains naturally
namespaced.

`_token_prefix(...)` must also become cycle-aware in proof mode. It currently
collapses both cycle-1 t1 and cycle-2 t1 to `t1`, corrupting token-local source
budgeting, support-5m identity, continuation identity, and reporting. Reuse
`parse_cycle_step_key(...)`; do not create another parser.

Governed lifecycle request keys already include the factory step key, so correct
cycle step namespaces also make cycle-2 request identities distinct without a
schema migration.

## 6. Proof Scheduler ceiling uses the derived 4-token envelope

`_insert_step_and_job(...)` currently selects legacy single/two-token Scheduler
ceilings. Proof mode needs a dedicated branch derived from
`scaled_standard_four_hour_capacity_contract(4)`.

Do not copy `236/117/210` or invent a four-token constant. Public two-token
standard-four-hour arithmetic and `TOKEN_CAPACITY == 2` remain unchanged.

## 7. Every proof lifecycle job gets exact stage-scoped campaign ownership

The proof design requires:

`factory step <-> Scheduler job <-> V2 stage-scoped Scheduler work <-> campaign window <-> token slot <-> cycle`.

The current factory already projects 1h/4h continuation ownership, but opening
15m jobs are not yet projected this way.

Proof mode must pre-create one deterministic PLANNED `WINDOW_15M` campaign window
per admitted cycle slot before its opening job is enqueued. Every 15m
snapshot/close job must then use `project_campaign_scheduler_job(...)` with
`work_scope=WINDOW_LIFECYCLE`, `stage_id=WINDOW_15M`, the one authoritative
factory run, exact token slot, exact cycle, and that window.

The legacy `persist_15m_campaign_window(...)` currently derives its window id
from the eventual memory-window row id, so it is too late for proof opening
ownership. Add a proof-only precreated-window path that later binds the real
memory-window row into that same window at close. Do not create a second window
for the same cycle/slot.

Proof window states must advance truthfully with actual lifecycle progress; do
not fabricate a closed/auditing state at opening.

## 8. Claimed lifecycle job identity comes from the Scheduler owner

The committed `resolve_owned_cycle_for_scheduler_job(...)` is the proof owner.
For every proof lifecycle job, require exactly one stage-scoped owner under the
same campaign/run/factory and use its cycle/window/slot identity for all
cycle-sensitive work.

No later-cycle fallback to the original function/config `cycle_id` is allowed.
Historical/non-proof callers retain their current behavior.

## 9. The 15m and 1h/4h barriers become cycle-local

Current operational-natural 15m helpers count activated tokens and terminal
closes across the whole factory run. In four-token proof mode that would make
cycle 1 wait for cycle 2 and merge the two barriers.

Proof mode must scope barrier inputs to the exact owning cycle resolved from
Scheduler ownership:

- A+B close -> cycle-1 evaluation only;
- C+D close -> cycle-2 evaluation only.

The same law applies to standard first-hour / four-hour continuation barriers.
A completed earlier cycle must not be reopened or delayed by a later cycle.

## 10. Standard 4h budget/accounting remains two-token per cycle

`_standard_four_hour_cumulative_budget_for_run(...)` currently reads one
`config[cycle_id]`. Preserve that legacy behavior outside proof mode.

Proof mode must use the owning cycle and build one canonical standard two-token
budget/accounting package per cycle. Reuse `cycle_scoped_factory_step_ids(...)`
and the existing standard-four-hour eligibility/accounting owners.

Aggregate proof budgeting uses the derived four-token envelope. Do not widen
`OperationalLifecycleOwnershipContext.expected_token_capacity` from 2 to 4 and
do not rewrite the canonical two-token stage set.

## 11. Terminal cleanup must be two-phase

`reconcile_campaign_terminal(...)` is intentionally run-wide: it can terminalize
all campaign/run windows and the shared factory run/campaign. It cannot be used
to close cycle 1 while cycle 2 is still live.

Add a small proof-only multi-cycle terminal coordinator:

Phase A, cycle-local:
- reconcile/cancel only work attributable to that cycle through existing owners;
- terminalize that cycle's owned windows/slots/work and cycle state;
- do not terminalize shared factory run, campaign run, campaign, or shared lease.

Phase B, shared:
- only after every admitted cycle is terminal, invoke/compose the existing shared
  terminal authority once;
- reconcile remaining shared work;
- terminalize factory run/campaign run/campaign once;
- cleanup supervision/lease once;
- prove zero active/orphan work and preserve first-terminal-cause law.

No restart, retry, resume, or successor is permitted.

## 12. Factory duration remains independently bounded

The controller's proof deadline must never extend the factory's existing
monotonic duration authority. Implementation should use the earlier of the
proof-controller deadline and the factory duration boundary. Whether the future
bounded proof duration is sufficient for cycle 2 to complete its legitimate 4h
close after the >=300s stagger is a later proof-readiness decision, not an
implementation shortcut.

## Required implementation gates

Use strict TDD with focused RED -> GREEN commits for:

A. neutral token/pair identity projection + real GraduatedSupply later-cycle adapter;
B. cycle-aware opening keys, token prefixes, request identities and derived Scheduler budget;
C. precreated 15m campaign windows + exact stage-scoped ownership;
D. single-loop wake/disposition integration, including pre/post-discovery health projection;
E. cycle-local 15m and long-window barriers using Scheduler-owned cycle identity;
F. cycle-local standard-4h budget/accounting and aggregate four-token acceptance;
G. two-phase terminal reconciliation;
H. integrated disposable same-factory 4/2/2 implementation proof and closeout.

A real source/runtime proof is forbidden in this implementation batch.

## Money-usefulness contribution

This integration lets one proven factory observe four overlapping Solana
memecoin trajectories without merging their ownership, budgets or continuation
barriers. The value is more diverse memory production per wall-clock period
while preserving exact source lineage and two-token lifecycle quality.

## What this lane improves

- makes the already-built proof controller operationally composable with the one
  canonical factory;
- preserves one Source Governor, one Scheduler and one factory run;
- gives each cycle exact source/Scheduler/window/accounting ownership;
- preserves lawful protected work before fresh admission;
- prevents stale pre-discovery budget state from authorizing cycle 2;
- preserves public two-token behavior when the proof controller is absent.

## What this lane still does not unlock

- no operational migration-055 application;
- no four-token runtime or proof authorization;
- no 12h/24h activation;
- no retrieval;
- no paper decisions or BUY/SELL/HOLD;
- no paper positions, trade events, audits or PnL.

## Proof/test required before implementation closeout

Minimum integrated implementation evidence must prove:

- exactly one factory run and event loop;
- exactly two admitted cycles and four distinct targets;
- cycle 2 cannot be admitted before 300s;
- due/mandatory lifecycle work beats admission;
- pre- and post-discovery health checks are both honored;
- one discovery attempt only;
- exact cycle-aware run-step/request identities;
- every proof lifecycle job resolves one exact cycle owner;
- cycle-local 15m/1h/4h barriers;
- one two-token accounting package per cycle;
- aggregate budgets remain within the derived four-token contract;
- both cycles terminal before shared terminalization;
- one shared cleanup/lease release;
- no retry/restart/resume/successor;
- public `TOKEN_CAPACITY == 2`, two-token standard contract and provider ceilings unchanged;
- zero 12h/24h/retrieval/financial capability activation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Migration 055 remains unapplied operationally and must pass a separate migration/readiness boundary before any runtime authorization.
- The current production later-cycle supply must be projected from the existing GraduatedSupply owner; a parallel discovery composition would be architectural drift.
- The current run-global `_token_prefix`, 15m barrier and standard-4h budget helpers are unsafe for two cycles unless the proof path is explicitly cycle-scoped.
- The current unified terminal reconciler is intentionally run-wide; calling it per cycle would prematurely close the peer cycle/shared run.
- No GitHub Actions verification exists for the reviewed lifecycle repair HEAD; the committed code/tests were statically reviewed, while prior focused test counts remain Codex-local evidence.

## Stop boundary

Implementation may proceed only through the focused integrated implementation
closeout. Stop before migration application, operational readiness/proof
authorization, source fetching, or any real four-token run.
