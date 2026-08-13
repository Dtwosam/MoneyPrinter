# Printer V1 V2-9.8B Four-Token Bounded Capacity Proof Integration Design

## Verdict

`V2_9_8B_FOUR_TOKEN_BOUNDED_CAPACITY_PROOF_INTEGRATION_DESIGN_PASS_READY_FOR_IMPLEMENTATION`

This design freezes the minimum integration required to exercise **four
concurrent through-4h tokens as two staggered exact two-token cycles** inside one
existing authoritative Memory Factory run.

It does not authorize or run the proof. It creates no source calls, DB writes,
memory, 12h/24h runtime, retrieval, decisions, positions, trades, audits, or PnL.

## Authority and baseline

Use the active Printer V1 source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Immediate design baseline:

- scaling implementation closeout:
  `2aec311ce328d6f98a1df98ba32c2699fd3e3130`
- four-token readiness audit:
  `2cc1de6f5df1a1bf1d4497f9b1ee111c20b559b6`
- readiness verdict:
  `V2_9_8B_FOUR_TOKEN_BOUNDED_CAPACITY_PROOF_READINESS_PASS_READY_FOR_PROOF_INTEGRATION_DESIGN_NO_AUTHORIZATION`

## Non-negotiable proof shape

The first scaled proof is exactly:

```text
one campaign
one campaign run
one authoritative factory run

configured through-4h capacity = 4 tokens
configured active cycles = 2
per-cycle fresh admission = exactly 2 tokens
proof total-cycle admission ceiling = 2
minimum admission spacing = 300 seconds

cycle 1 -> slot 1 A + slot 2 B
cycle 2 -> slot 1 C + slot 2 D
```

No fourth token is created by widening one cycle. No second factory runner is
started.

The existing compiled six-token capability remains present but cannot be
exercised by this proof configuration.

## Design decision 1 - optional proof-gated controller, not a new runner

Add an **optional internal four-token proof controller** to the canonical factory
execution path.

The current public two-token path remains the default and must behave identically
when the controller is absent.

The controller owns only:

- the four-token proof configuration (`4 / 2 / total cycles 2`);
- the 300-second next-admission boundary;
- admission/readiness evaluation using the committed multi-cycle capacity policy;
- creation/registration of the second exact cycle through existing ownership;
- scheduling the second pair into the already-existing factory run;
- per-cycle identity lookup and aggregate proof reporting.

It does **not** own:

- source transport;
- discovery logic;
- selection logic;
- Scheduler execution;
- Source Governor;
- snapshot/close implementation;
- memory promotion;
- DB schema;
- terminal cleanup implementation.

Those remain existing owners.

## Design decision 2 - later-cycle discovery uses the same operational owner

The authoritative operational campaign owner must expose an internal callback or
adapter capable of requesting one additional exact two-token cycle for an
already-running campaign/run/factory identity.

Required inputs include:

- campaign id;
- campaign-run id;
- authoritative factory-run id;
- new cycle id / ordinal;
- cycle cutoff / evaluated-at;
- deterministic cycle-specific selection seed;
- the same Source Governor port;
- the same Central Scheduler port;
- current bounded source/Scheduler/admission capacity.

Required output is either:

- exactly two validated selected targets plus the existing discovery/handoff
  evidence needed to persist the cycle; or
- an honest no-admission/defer/block result.

The callback must reuse the existing operational discovery/selection pipeline.
It must not create an independent polling/fetch loop.

The second-cycle discovery action remains Scheduler/Source-Governor governed and
is attributable to cycle 2.

## Design decision 3 - step keys become cycle-namespaced without a migration

`printer_memory_factory_run_steps` has `UNIQUE(run_id, step_key)` and no cycle
column. Reusing first-cycle `t1...` / `t2...` step keys for cycle 2 would collide.

The proof integration therefore uses a backward-compatible step-key namespace.

Cycle 1 may retain existing historical names for maximum compatibility.

Later cycles use:

```text
t1_c0002_<existing-step-suffix>
t2_c0002_<existing-step-suffix>
```

For example:

```text
t1_c0002_snapshot_00
t1_c0002_window_close
t2_c0002_snapshot_00
t2_c0002_window_close
```

Requirements:

- the leading `t1` / `t2` token-slot prefix remains intact so existing slot
  ordinal parsing can remain compatible;
- cycle namespace is deterministic from the durable cycle ordinal;
- cycle namespace participates in every later-cycle step/request/reservation key
  that must be unique inside the factory run;
- cycle 1 names remain unchanged unless a focused compatibility reason proves
  they must also be namespaced;
- no schema migration is introduced solely for step uniqueness.

Any helper that currently treats the first underscore-delimited `t1` / `t2` as a
run-global token identity must receive a cycle-aware proof path. It cannot merge
cycle-1 slot 1 and cycle-2 slot 1 usage.

## Design decision 4 - cycle identity comes from durable Scheduler ownership

Once more than one cycle exists, the original function-level `cycle_id` can no
longer be authoritative for every lifecycle step.

For every claimed Scheduler job in multi-cycle proof mode:

1. resolve the unique stage-scoped
   `printer_memory_factory_campaign_scheduler_work` owner by canonical
   `scheduler_job_id`;
2. require its `factory_run_id` to equal the one authoritative factory run;
3. read its exact `cycle_id`, `token_slot_id`, `window_id`, stage, and target;
4. verify the owning campaign/run/configuration identities;
5. use that resolved cycle identity for all cycle-sensitive continuation,
   barrier, registration, accounting, and terminal operations.

No fallback to the original cycle id is allowed for later-cycle owned work.

Historical/non-campaign test callers may retain the existing behavior where no
stage-scoped campaign owner exists, provided the new proof mode fails closed
when ownership is missing.

## Design decision 5 - opening-job planner accepts a cycle namespace

Generalize the existing opening/cadence planner minimally so a second two-token
pair can be added to the same factory-run ledger.

Inputs added for proof mode:

- cycle id;
- cycle ordinal;
- step-key namespace;
- exact token-slot ownership mapping.

It must still schedule the same approved cadence and use the canonical Scheduler.

A second-cycle admission must never:

- reset the factory run;
- rewrite first-cycle targets;
- replace the first selection batch identity as if only cycle 2 existed;
- cancel healthy first-cycle work;
- change cadence or evidence thresholds.

Factory-run summary/reporting may add an aggregate list of selection batch ids,
but existing one-cycle fields must remain backward compatible.

## Design decision 6 - one event loop, two kinds of wake-up

The canonical factory keeps one execution loop.

In proof mode its next wake boundary is:

```text
min(
  next due canonical lifecycle Scheduler work,
  next lawful cycle-admission opportunity,
  bounded proof stop/deadline
)
```

Rules:

- already-due lifecycle work is evaluated before fresh admission;
- mandatory close work always outranks fresh admission;
- admission is evaluated only at/after the 300-second boundary;
- failed/deferred admission does not affect existing healthy lifecycles;
- no busy-poll loop is added;
- no admission thread/process is added;
- cancellation/lease failure aborts through existing supervision law.

## Design decision 7 - cycle-local two-token continuation barriers

Every otherwise-valid activated token still follows the standard
15m -> 1h -> 4h observation path under the post-DTW100 rule.

The two-token barrier remains **per cycle**.

For cycle 1:

```text
A 15m close + B 15m close -> cycle-1 continuation evaluation
```

For cycle 2:

```text
C 15m close + D 15m close -> cycle-2 continuation evaluation
```

Run-global helpers that count activated tokens or terminal 15m closes must be
extended with the actual cycle identity in multi-cycle proof mode.

The same rule applies to the standard first-hour/4h barrier: a continuation close
must invoke the barrier with the exact cycle resolved from its Scheduler owner.

A later cycle must never delay or change an earlier cycle's already-complete
barrier result.

## Design decision 8 - campaign window projection is per owning cycle

For every lifecycle job in the proof:

```text
factory step
  <-> canonical Scheduler job
  <-> stage-scoped campaign Scheduler work
  <-> campaign window
  <-> token slot
  <-> cycle
```

must reconcile exactly.

Window registration helpers must receive a cycle-specific ownership context
constructed from the durable Scheduler row rather than reuse one global context.

Any ambiguity, duplicate owner, wrong token/pair, wrong window kind, or wrong
factory-run id fails closed.

## Design decision 9 - preserve two-token full-run accounting per cycle

Do not widen `OperationalLifecycleOwnershipContext.expected_token_capacity` from
2 to 4.

Do not rewrite `REQUIRED_LIFECYCLE_STAGE_KINDS` into a four-token stage set.

Instead add a **multi-cycle accounting adapter** that builds one existing-style
cycle accounting context per admitted cycle:

```text
context cycle 1 -> expected token capacity 2
context cycle 2 -> expected token capacity 2
```

The adapter must scope factory-run steps to a cycle by joining through the
existing canonical Scheduler job -> stage-scoped campaign Scheduler-work
ownership relation. It must not query every lifecycle step in the factory run
and compare that set against only one cycle.

The cycle-local accounting result must retain:

- exact selected pair;
- exact WINDOW_15M / WINDOW_1H / WINDOW_4H owned Scheduler correspondence as
  applicable to the standard campaign;
- two-token stage/accounting evidence;
- quality consistency;
- slot disposition;
- cycle-local source/Scheduler attribution;
- exact cycle id and shared factory-run id.

Then one aggregate proof acceptance combines the two cycle results with shared
campaign-level facts.

## Design decision 10 - one aggregate four-token acceptance gate

The aggregate proof PASS requires both admitted cycles to be structurally safe.
Memory quality remains honest and is not converted into a clean quota.

Shared checks include:

- exactly one campaign;
- exactly one campaign run;
- exactly one authoritative factory run;
- exactly two admitted cycles;
- exactly four distinct token/pair targets;
- exactly two slots per cycle;
- admission spacing >=300s;
- maximum active through-4h count <=4;
- both cycle accounting packages structurally complete;
- aggregate Scheduler/source budgets within the four-token contract;
- provider rate ceilings unchanged;
- terminal supervision/lease cleanup complete;
- zero active/orphan work across both cycles;
- zero forbidden capability deltas;
- no automatic retry/restart/resume/successor;
- no 12h/24h work.

A dirty memory in one cycle does not automatically make the structural proof
fail if the lifecycle closes lawfully and quality is reported honestly. An
accounting/ownership/identity/close/safety defect does fail the proof.

The report must keep these axes separate:

1. runtime/lifecycle integrity;
2. memory quality outcomes;
3. capacity/fairness/budget proof result.

## Design decision 11 - budget authority stays derived

Use:

`scaled_standard_four_hour_capacity_contract(4)`

for the simultaneous four-token proof envelope.

The proof configuration must not copy or independently redefine the canonical
`2 / 236 / 117 / 210` numbers.

The aggregate envelope is derived from two canonical two-token cycles.

Provider per-minute/rate ceilings remain unchanged.

The admission controller must defer the second cycle if the real shared capacity
state cannot preserve:

- source-request reserve;
- provider-specific reserve;
- Scheduler-work reserve;
- mandatory close reserve;
- DB/lease health;
- protected future-work reserve contract.

No new automatic retry is permitted.

## Design decision 12 - terminal cleanup composes existing owner per cycle

Do not call the current single-cycle `reconcile_campaign_terminal(...)` twice in
a way that terminalizes the shared run/campaign after cycle 1.

Add a small multi-cycle terminal coordinator with two phases.

### Phase A - cycle-local reconciliation

For each admitted cycle:

- reconcile discovery Scheduler parity for that cycle;
- cancel only remaining owned work as required through Central Scheduler;
- reconcile that cycle's token slots/queues;
- terminalize that cycle's remaining owned windows/work;
- transition the cycle itself to the lawful terminal state.

Do **not** terminalize the shared campaign run/campaign yet.

### Phase B - shared terminal reconciliation

After every admitted cycle is terminal:

- reconcile/cancel any remaining shared attributable work;
- terminalize the authoritative factory-run ledger;
- terminalize the shared campaign run and campaign exactly once;
- cleanup/release supervision/lease exactly once;
- prove zero active work across the whole campaign/run/factory;
- preserve first-terminal-cause law;
- record no restart or successor.

Where possible, factor existing terminal logic into reusable internal helpers
rather than duplicate SQL/state-transition policy.

## Design decision 13 - proof-only authority surface

The four-token integration is not added as a normal public mode.

Implementation must define an internal proof policy/configuration that is valid
only when all of the following are exact:

```text
configured_through_4h_tokens = 4
configured_active_cycles = 2
total_cycle_admission_ceiling = 2
minimum_admission_spacing_seconds >= 300
per_cycle_token_capacity = 2
standard_four_hour_campaign = true
```

A value of 6/3 is rejected in this proof lane even though the compiled scaling
foundation supports it.

Normal production/public standard-four-hour behavior remains exactly two-token
until a later activation lane.

A fresh four-token authorization format/wrapper is designed only after
implementation/readiness passes. This implementation design does not create one.

## Design decision 14 - source/discovery accounting is cumulative and cycle-local

Each cycle's discovery action must retain its own:

- cycle id;
- selection/discovery batch identity;
- governed source-operation identities;
- Scheduler work identities;
- first-terminal cause if it blocks before lifecycle.

The aggregate proof report sums the actual attributable operations without
inventing a second accounting path.

The second discovery result cannot replace the first cycle's report state.

If cycle 2 cannot produce an eligible exact pair, the four-token proof ends as
an honest blocked capacity proof; Printer does not start a single token or lower
eligibility standards.

## Design decision 15 - exact proof tests before any runtime authorization

Implementation uses TDD and focused tests only.

Required test groups:

### A. Controller / capacity tests

- 4/2/2 proof policy accepted;
- 6/3 rejected by four-token proof authority;
- cycle 2 before 300s rejected/deferred;
- cycle 2 at/after 300s can be admitted only when every gate passes;
- at most four active through-4h tokens;
- no third cycle;
- no single-token fresh admission.

### B. Step-key / factory ledger tests

- cycle-1 historical step keys remain valid;
- cycle-2 step keys are unique under the same factory run;
- `t1`/`t2` slot parsing remains correct;
- accounting/budget grouping distinguishes cycle-1 t1 from cycle-2 t1;
- request/reservation identities do not collide.

### C. Same-factory ownership tests

- one factory-run row only;
- campaign run bound to that one factory run only;
- two campaign cycles exist beneath the same run;
- every cycle has exactly two slots;
- no duplicate active pair across cycles.

### D. Scheduler/fairness tests

- due cycle-1 close outranks cycle-2 admission;
- earliest mandatory close across cycles wins;
- ordinary work fair across four tokens;
- shared Scheduler ceiling blocks/defer safely;
- every claimed job resolves one exact cycle owner.

### E. Continuation tests

- cycle-1 15m barrier ignores cycle-2 tokens;
- cycle-2 15m barrier ignores cycle-1 tokens;
- cycle-1 and cycle-2 can independently reach 1h/4h;
- standard 4h barrier receives the exact owning cycle;
- token-local failure does not corrupt the peer cycle.

### F. Accounting/terminal tests

- one existing two-token accounting package per cycle;
- cycle-local Scheduler correspondence does not see peer-cycle steps as missing
  or extra ownership;
- aggregate acceptance sees exactly two cycle packages;
- dirty memory remains honestly dirty without identity drift;
- both cycles terminal before shared campaign/run terminal;
- zero active/orphan work across both cycles;
- one cleanup/lease release;
- no retry/restart/resume/successor.

### G. Lock tests

- current public `TOKEN_CAPACITY == 2` unchanged;
- canonical two-token `2 / 236 / 117 / 210` unchanged;
- provider ceilings unchanged;
- no migrations unless a later proven implementation blocker explicitly forces
  reconsideration;
- no 12h/24h runtime;
- no retrieval/financial table deltas or capability code path.

Do not run a live proof during implementation tests.

## Proof-readiness evidence after implementation

Before a four-token authorization can be prepared, a separate readiness review
must confirm:

- exact implementation Git head;
- focused tests PASS;
- DB integrity/FK and migration ledger exact;
- no active Printer process/lease/sidecar/work;
- public two-token mode remains unchanged;
- four-token proof mode is bounded to exactly 4/2/2;
- six is not exercisable by that authority;
- source/provider/Scheduler ceilings and stop rules are exact;
- proof duration is enough for cycle 2 to complete its legitimate 4h boundary
  after the >=300s stagger;
- terminal/report artifacts are deterministic and bounded;
- all old authorizations remain non-reusable.

Only then may a fresh authorization be prepared and independently reviewed.

## Money-usefulness contribution

This design tests the smallest concurrency increase that can materially improve
daily corpus diversity while preserving the quality of each individual token
trajectory. It allows Printer to learn from four overlapping Solana memecoin
paths without sacrificing exact pair evidence, close timing, failure examples,
or future paper-work headroom.

It improves future money-usefulness only if the extra concurrency remains cleanly
attributable and does not turn source/Scheduler pressure into dirty memory.

## What this design improves

- converts the generic six-capable foundation into an exact four-token proof
  integration plan;
- preserves two-token discovery and accounting semantics;
- avoids multiple factory runners;
- avoids a schema migration for cycle identity solely by using existing
  Scheduler ownership plus cycle-namespaced step keys;
- defines cycle-local continuation/barrier/accounting behavior;
- defines one aggregate four-token acceptance gate;
- defines safe terminal ordering for multiple cycles;
- keeps public runtime frozen until proof.

## What remains locked

This design does not unlock:

- four-token runtime or authorization;
- six-token runtime;
- 24h continuous intake;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet/private keys/real funds/live execution;
- paid APIs;
- provider-ceiling increases;
- automatic retries/endpoint rotation;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Required response | Stop condition |
|---|---|---|
| Cycle-2 step-key collision | Cycle namespace later-cycle step/request keys | Any duplicate `(run_id, step_key)` |
| Slot parser broken by namespace | Keep leading t1/t2 prefix and focused tests | Slot ordinal cannot be proven |
| Per-token budget groups merge t1 across cycles | Use cycle-aware grouping in proof path | Usage cannot be attributed to exact cycle/token |
| Second discovery creates another factory run | Reuse same canonical factory loop and owner | More than one authoritative factory run |
| Later-cycle work inherits cycle 1 | Resolve by canonical Scheduler ownership | Missing/ambiguous/wrong cycle owner |
| Run-global continuation barrier | Scope barrier to cycle | One cycle waits on or changes peer-cycle decision |
| Cycle-local accounting reads peer steps | Join factory steps through cycle-owned Scheduler rows | Missing/extra ownership caused by peer cycle |
| Shared terminal happens after first cycle | Separate cycle-local and shared terminal phases | Run/campaign terminal while another cycle active |
| Admission starves close | Due close always before admission | Close miss/late evidence attributable to admission |
| Aggregate budget copied manually | Derive from canonical 2-token contract | Independent duplicated capacity constants |
| Cycle-2 eligible pool empty | Honest blocked proof; no single-token degradation | One-token admission or weakened gates |
| Six accidentally enabled | Four-token proof authority hard-rejects 6/3 | >4 active token state |
| DB contention rises | Short transactions/no network under write lock | New lock/heartbeat blocker |
| Long-window drift | Explicit lock scan | Any 12h/24h runtime activation |

## Closeout

The design is implementation-ready provided implementation stays within these
boundaries.

Next permitted lane:

`FOUR_TOKEN_BOUNDED_CAPACITY_PROOF_INTEGRATION_IMPLEMENTATION`

Implementation must be test-first and must stop before creating any proof
authorization or running Printer.
