# Printer V1 — V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Design

## Verdict

`V2_9_8B_POST_DTW98_PRE_LIFECYCLE_TEMPORAL_PERSISTENCE_DESIGN_PASS`

This design closes the `DESIGN_GAP` proven by the post-DTW98 temporal-persistence audit. It authorizes a narrow implementation lane only. It does not authorize live source access, authoritative DB mutation, a new authorization, or WINDOW_15M runtime.

## Baseline

- audit commit: `77b9168ed160b48b201fe1351e14e135e24bcc2d`
- audit verdict: `V2_9_8B_POST_DTW98_PRE_LIFECYCLE_TEMPORAL_PERSISTENCE_AUDIT_PASS_DESIGN_REQUIRED`
- DTW98 remains permanently consumed and non-reusable
- active Printer V1 source stack and all capability locks remain binding

## Design goal

When ordinary WINDOW_15M preparation has fewer than the required four fresh memory-observation identities and the currently reachable candidate universe is exhausted, Printer must not immediately terminalize merely because no additional candidate is reachable at that instant.

Instead, inside the same authorization/campaign/run/cycle it may enter a bounded, Scheduler-owned temporal acquisition state and wait for a future discovery refresh. It proceeds only when the four-deep freeze is satisfied or a genuine acquisition terminal is reached.

This is not retry/restart/resume/successor behavior.

## Frozen rules that do not change

- required memory-observation freeze depth remains `4`: exactly two selected plus two alternates;
- tracking exclusions remain categorical and binding;
- exact-pool and liquidity-floor rules remain unchanged;
- stale evidence does not count;
- holder evidence remains context and not memory-observation admission authority;
- Source Governor owns every provider request;
- Central Scheduler owns every delayed refresh;
- discovery/source operation ceilings are not raised;
- no independent API, polling, reconnect, or retry loop;
- no scoring/ranking/confidence/weighted logic;
- no WINDOW_1H+ activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallet, keys, signing, or real funds.

## 1. Bounded acquisition horizon

Add an explicit ordinary-run policy field:

`pre_lifecycle_acquisition_duration_seconds = 900`

Rationale: `900s` is the existing bounded discovery-only duration already adopted by Printer. Reusing that duration is the minimum conservative extension and does not invent an unbounded wait.

This horizon is separate from the existing post-supply operational/lifecycle `duration_seconds = 1200` and the `WINDOW_15M = 900s` evidence window.

Therefore:

- acquisition may take at most 900 seconds;
- once four-deep readiness is reached, the existing lifecycle deadline starts from the real post-acquisition time and retains its existing 1200-second envelope;
- total one-shot wall time may therefore increase, but no source-operation or financial capability ceiling increases;
- the new acquisition horizon must be persisted in the immutable campaign configuration and surfaced in authorization/readiness reporting so the longer wall-time envelope is explicit, not hidden.

This 900-second acquisition horizon is not a WINDOW_15M memory window and creates no memory by itself.

## 2. Scheduler cadence and nonterminal state

Use existing `JobKind.DISCOVERY_REFRESH` and the existing resource-governor cadence:

`next_check_interval_seconds(JobKind.DISCOVERY_REFRESH) == 600`

New nonterminal reporting state:

`WAITING_FOR_ELIGIBLE_SUPPLY`

Eligibility to enter waiting requires all of:

1. current fresh eligible reserve count `< 4`;
2. current reachable unique universe exhausted (`ALL_REACHABLE_CANDIDATES_EVALUATED` or `NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE`);
3. acquisition deadline remains in the future;
4. governed discovery operation budget remains;
5. no provider/source terminal failure is controlling;
6. campaign supervision remains active and cancellation not requested;
7. no active pending refresh already exists for this exact campaign/run/cycle.

If the next normal 600-second refresh due time is not strictly before the acquisition deadline, do not enqueue another refresh; terminalize as acquisition duration exhausted.

Under the initial 900-second bound this intentionally permits one normal delayed refresh opportunity. It is the minimum safe temporal-persistence repair; additional cadence/horizon expansion requires later evidence and design, not silent tuning.

## 3. Exact pending-refresh ownership

A delayed Scheduler job must be attributable to the exact campaign before it becomes due, while preserving the approved claim-at-work-start law.

Add forward migration `054_pre_lifecycle_discovery_refresh_wait.sql` with one narrow table:

`printer_pre_lifecycle_discovery_refresh_waits`

Required fields:

- `wait_id` TEXT primary key;
- `campaign_id` TEXT not null;
- `run_id` TEXT not null;
- `cycle_id` TEXT not null;
- `supervision_id` TEXT not null;
- `scheduler_job_id` INTEGER unique not null;
- `refresh_ordinal` INTEGER not null and positive;
- `wait_state` in `WAITING`, `CLAIMED`, `SUCCEEDED`, `FAILED`, `CANCELLED`;
- `scheduled_for` TEXT not null;
- `acquisition_deadline_at` TEXT not null;
- `created_at`, `updated_at`, nullable `terminal_at`;
- nullable categorical `first_terminal_cause`.

Unique identity: one row per exact campaign/run/cycle/refresh ordinal and one row per Scheduler job.

No source payload, ranking, score, or financial field belongs in this table.

## 4. Enqueue and wait contract

Canonical owner: the authoritative operational orchestration layer, not `eligible_token_supply.py`.

When the supply service asks for a temporal refresh opportunity, the orchestration owner must:

1. prove Source Governor/Central Scheduler owner availability;
2. prove no open SQLite write transaction is held across waiting;
3. calculate the next due time using the canonical `DISCOVERY_REFRESH` interval;
4. enqueue exactly one future `DISCOVERY_REFRESH` job;
5. persist the exact pending-refresh ownership row bound to that job and the active campaign/run/cycle/supervision;
6. publish/report `WAITING_FOR_ELIGIBLE_SUPPLY`;
7. block the same child process using one bounded interruptible wait to the due instant or acquisition deadline, not a polling loop;
8. allow the existing campaign heartbeat thread to continue lease renewal during the wait;
9. after wake, first check heartbeat failure, cancellation/safe-stop state, deadline, and exact Scheduler job identity;
10. claim that exact due Scheduler job once;
11. only after successful claim, create the exact `printer_discovery_work` RUNNING row linked to that same Scheduler job;
12. run one bounded Source-Governed refresh stage;
13. terminalize discovery work, Scheduler job, and wait row consistently.

A timer only suspends the already-authorized child; it does not own work. The persisted Scheduler job remains the authority for whether refresh work may start.

No `time.sleep()` polling loop, `while True`, background refresh worker, subprocess restart, or second child is allowed.

## 5. Active-work and cleanup integration

Extend the existing exact campaign active-work owner so `printer_pre_lifecycle_discovery_refresh_waits.scheduler_job_id` is a valid exact-scope owner for pending temporal refresh jobs.

Required behavior:

- a `WAITING` row makes its PENDING Scheduler job visible to campaign active-work accounting;
- safe stop captures it before cancellation through the existing immutable cleanup-capture path;
- a PENDING wait job cancelled before claim is terminalized as `CANCELLED` without creating a `printer_discovery_work` row;
- after claim, normal discovery-work exact job lineage becomes available and existing `DISCOVERY_SELECTION` ownership projection applies;
- terminal cleanup must leave zero WAITING/CLAIMED wait rows and zero PENDING/RUNNING/COOLDOWN jobs for the campaign.

Do not weaken the corrected Scheduler ownership rule that batch presence alone is insufficient lineage.

## 6. Supply-service integration contract

`eligible_token_supply.py` remains the canonical supply and budget/exhaustion owner but must not own Scheduler calls.

Add a dependency-injected temporal refresh boundary, default `None`, so non-operational consumers preserve existing behavior.

Conceptual shape:

```text
run_persistent_eligible_token_supply(...,
    deadline_at=acquisition_deadline,
    temporal_refresh_owner=<operational callback or object>)
```

When current-universe exhaustion occurs with remaining deadline/budget:

- if no temporal refresh owner is supplied: preserve existing terminal behavior;
- if supplied: request one Scheduler-owned temporal refresh opportunity;
- keep cumulative source-operation usage in the same supply invocation;
- never reset the 30-operation discovery budget after waiting;
- after a claimed refresh, reopen only the bounded lawful discovery/nominations needed to expose newly reachable identities;
- do not relabel old rejected candidates as new.

The same exhaustion certificate owns cumulative initial + temporal-refresh facts.

## 7. Reserve behavior after waiting

Before any retained candidate counts after a temporal wait:

1. mark current campaign reserve candidates stale for refresh evaluation;
2. preserve durable graduation/pool identity facts that are still authoritative;
3. revalidate due market/liquidity/tracking/freshness domains through their existing owners;
4. remove any candidate that no longer passes;
5. evaluate new unique candidates from the refresh;
6. rebuild the fresh reserve count;
7. freeze only if current fresh post-filter depth is at least four.

The prior 3-of-4 state is therefore useful retained evidence, not permanent entitlement to three slots.

## 8. Terminal precedence

During temporal acquisition, controlling terminals are categorical and ordered fail-closed:

1. operator/safe-stop or campaign supervision failure;
2. unsafe Scheduler/DB ownership state;
3. source/provider availability or visibility failure under existing classification rules;
4. true source-operation budget exhaustion;
5. acquisition deadline exhausted;
6. otherwise current-universe exhaustion with a lawful future refresh remains `WAITING_FOR_ELIGIBLE_SUPPLY`, not terminal shortage.

Capacity `>=4` exits acquisition immediately and proceeds to the existing freeze/handoff path.

A terminal exhaustion certificate after temporal persistence must include:

- acquisition started/deadline/elapsed/remaining seconds;
- temporal refresh opportunities scheduled, claimed, completed, cancelled;
- cumulative source operations used/remaining;
- eligible reserve depth before and after each refresh;
- candidate revalidation outcomes;
- final current-universe state;
- exact controlling shortage classification.

Do not emit `TRUE_MARKET_SUPPLY_SHORTAGE` merely because one instantaneous universe was exhausted before the temporal acquisition deadline.

## 9. Authorization semantics

Temporal persistence remains one invocation:

- same external one-use authorization;
- same application marker;
- same wrapper child;
- same campaign/run/cycle/supervision identities;
- no automatic retry;
- no manual rerun;
- no restart;
- no resume;
- no successor;
- no second authorization.

If the process exits for any reason after marker consumption, that authorization remains permanently consumed.

## 10. Supervision and host-awake behavior

The existing campaign heartbeat already begins before the authoritative operational owner and renews every 30 seconds under a 90-second lease. It remains active while temporal acquisition waits.

A wait must wake/abort promptly when heartbeat failure or cooperative cancellation is observed; it must never wait blindly past known supervision failure.

Future real proof remains host-awake under `caffeinate -dimsu` and the terminal must remain untouched until wrapper return.

## 11. Minimum implementation scope

Expected production files:

- new migration `054_pre_lifecycle_discovery_refresh_wait.sql`;
- `src/printer_v1/discovery/eligible_token_supply.py`;
- `src/printer_v1/operator_cli/graduated_supply_front_door.py` only if signature plumbing is required;
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
- `src/printer_v1/operator_cli/campaign_active_work.py`;
- minimal Scheduler ownership/projection integration only if required for exact claimed-job lineage;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py` for the explicit acquisition policy/config/report field;
- focused tests only.

Do not refactor unrelated source/provider/lifecycle/memory code.

## 12. Focused TDD/proof matrix

Implementation must begin with focused offline RED tests using disposable SQLite/fake clock; no real sleep and no live network.

Minimum cases:

1. 3/4 + current universe exhausted + budget/horizon remain => `WAITING_FOR_ELIGIBLE_SUPPLY`, not terminal.
2. exact future DISCOVERY_REFRESH job and wait row are persisted under same campaign/run/cycle.
3. before due, claim returns NOT_DUE and zero refresh source operations occur.
4. at due, exact claim succeeds before discovery-work RUNNING insertion.
5. claimed refresh reveals fourth candidate; retained three are revalidated; exact 2+2 freeze succeeds.
6. retained candidate fails revalidation; capacity drops truthfully and no stale candidate counts.
7. refresh still yields <4 and no next normal interval fits before 900s horizon => `DURATION_EXHAUSTION`.
8. cumulative discovery budget does not reset across refresh.
9. source/provider failure classification remains unchanged.
10. cancellation while WAITING cancels exact pending job, terminalizes wait row, creates no discovery work, leaves zero active residue.
11. heartbeat/supervision failure during wait aborts without source work.
12. active-work owner includes pending wait job by exact campaign/run/cycle.
13. foreign wait job is excluded.
14. no retry/restart/resume/successor/new authorization behavior.
15. zero forbidden capability-table deltas.
16. existing non-temporal eligible-supply tests remain green.

After focused unit/TDD proof, run only directly affected Scheduler/ownership/supply/ordinary-command suites. Reserve broader regression for repair closeout/pre-live readiness.

## Money-usefulness contribution

This design lets Printer use bounded time rather than repeated one-use authorizations to bridge a temporary 3-of-4 reserve shortage. It improves the chance of producing a valid, current, diverse WINDOW_15M memory set while preserving the evidence and safety gates that make those memories useful later.

## What this design improves

- adds temporal persistence without loosening eligibility;
- makes waiting Scheduler-owned and auditable;
- preserves the current one-use authorization model;
- keeps source budget cumulative and bounded;
- makes prior reserve useful but revalidated;
- turns instantaneous universe exhaustion into a nonterminal state when a lawful future refresh remains.

## What this design still does not unlock

No source/runtime/proof authorization is granted here. WINDOW_1H/4H/12H/24H, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, real funds, live execution, paid APIs, scores/ranks/confidence/weights, embeddings and vectors remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- 900 seconds permits only one normal 600-second delayed refresh; this is intentional minimum scope and may still honestly exhaust.
- total wrapper wall time can increase because acquisition is now explicitly bounded separately from lifecycle collection.
- pending refresh ownership must be exact or safe-stop can leak Scheduler residue.
- reserve revalidation can consume scarce source budget; no budget reset or broad refresh is allowed.
- campaign heartbeat must stay healthy across the wait.
- any use of a private polling/sleep/retry loop is a design violation.
- expanding cadence, acquisition horizon, source ceiling, or eligibility rules to obtain PASS is out of scope.

## Next lane

`V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Implementation`

Implementation is allowed only against this frozen design, starting with focused offline TDD. No live providers, authoritative runtime, authorization, or WINDOW_15M execution.