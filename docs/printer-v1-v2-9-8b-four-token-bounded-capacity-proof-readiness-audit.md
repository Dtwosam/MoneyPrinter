# Printer V1 V2-9.8B Four-Token Bounded Capacity Proof Readiness Audit

## Verdict

`V2_9_8B_FOUR_TOKEN_BOUNDED_CAPACITY_PROOF_READINESS_PASS_READY_FOR_PROOF_INTEGRATION_DESIGN_NO_AUTHORIZATION`

The six-capable Memory Factory scaling foundations are ready for a separate,
narrow four-token proof-integration design.

Printer is **not yet ready to execute four concurrent through-4h tokens**. The
canonical factory entry point remains intentionally one-cycle/two-token. A
proof-gated integration is required first so that a second exact two-token cycle
can enter the **same authoritative factory run** without creating a second
lifecycle owner.

This audit is static/read-only. It creates no authorization, runs no discovery,
fetches no source, mutates no database, generates no memory, activates no 12h or
24h runtime, and unlocks no retrieval or financial capability.

## Source stack and baseline

Active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of the source stack, not the
sole authority.

Immediate durable baseline:

- implementation branch:
  `agent/v2-9-8b-memory-throughput-capacity-scaling-implementation`
- implementation closeout:
  `2aec311ce328d6f98a1df98ba32c2699fd3e3130`
- implementation verdict:
  `V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_SCALING_IMPLEMENTATION_PASS_READY_FOR_FOUR_TOKEN_BOUNDED_PROOF`

Fresh operator verification before that closeout established:

- 12 multi-cycle coordinator tests PASS;
- 20 scaling foundation tests + 23 subtests PASS;
- 6 existing campaign-ownership tests PASS;
- 14 existing atomic two-slot handoff tests PASS;
- current public runtime token capacity remains `2`;
- canonical two-token standard-four-hour contract remains `2 / 236 / 117 / 210`;
- compiled scaling maximum is `6 tokens / 3 active cycles`;
- whole-session compiled ceiling is `15 cycles / 30 new tokens`;
- `WINDOW_12H` and `WINDOW_24H` remain locked;
- no migration changed.

## Audit question

What is the minimum safe integration required to exercise **four concurrent
through-4h tokens as two staggered exact two-token cycles**, while preserving the
existing one-machine architecture and every two-token safety/quality contract?

## Current architecture that must remain

The existing persistent ownership graph already supports the required shape:

```text
one campaign
  -> one campaign run
       -> one authoritative factory run
       -> cycle 1 -> exactly two token slots
       -> cycle 2 -> exactly two token slots
```

`printer_memory_factory_campaign_runs.authoritative_run_id` is a one-shot bind.
The four-token proof therefore must not invoke the canonical factory twice.

The existing `create_cycle_with_two_slots(...)` owner already permits additional
cycles beneath one campaign run and requires every cycle to contain exactly slot
ordinals 1 and 2. No schema widening is required merely to represent two active
cycles.

The new `multi_cycle_campaign_coordinator.py` already validates and persists the
multi-cycle session shape without source fetching or lifecycle execution.

## Primary readiness blocker: canonical factory is still one-cycle at entry

`run_one_command_15m_factory(...)` currently:

1. creates one factory-run ledger row;
2. binds the campaign run to that one factory run;
3. performs one discovery/selection action;
4. plans opening lifecycle work for that selected pair;
5. enters one Scheduler-driven lifecycle loop;
6. closes and reports the run.

That is correct for the current public two-token runtime.

The four-token proof must **not** solve this by:

- setting one cycle's `max_selected_tokens` to 4;
- widening a cycle to four slots;
- launching `run_one_command_15m_factory(...)` twice;
- starting another campaign process five minutes later;
- starting another Scheduler or Source Governor;
- creating a second authoritative factory run;
- copying the old V2-5 three-token runner into the active path.

The correct integration is an optional proof-gated multi-cycle admission hook in
the existing canonical factory run.

## Four-token proof shape

The initial proof is deliberately smaller than the compiled six-token capability:

```text
configured through-4h token maximum = 4
configured active-cycle maximum = 2
per-cycle token count = 2
proof total-cycle admission ceiling = 2
minimum cycle spacing = 300 seconds
```

Example:

```text
T+00:00  cycle 1 -> A + B
T+05:00 or later, only if admission gates pass:
          cycle 2 -> C + D

A-D may then overlap through 15m -> 1h -> 4h.
```

The four-token proof is not a 24h throughput run. It should admit exactly two
cycles at most, establish safe overlap, drain them to terminal state, and stop.

The 15-cycle / 30-token whole-session ceiling belongs to the later continuous
session program and must not be exercised in this first proof.

## Minimum proof-integration design surface

### 1. One optional multi-cycle session controller inside the canonical factory

The canonical factory retains exactly one factory-run identity.

The proof-gated controller may request one later cycle admission when:

- the configured proof capacity allows it;
- at least 300 seconds have elapsed since the prior cycle admission;
- intake for the bounded proof remains open;
- source/provider/Scheduler/close/DB/supervision gates remain healthy;
- no shared terminal/cancellation condition exists.

The controller must consume the committed `MultiCycleCapacityPolicy` /
coordinator contracts rather than introduce a second capacity model.

Current public two-token operation must take the legacy path with the controller
disabled.

### 2. Later-cycle discovery remains inside the same owners

A later cycle needs a fresh exact two-token discovery/selection/handoff action.
It must use the same campaign, campaign run, Source Governor, Central Scheduler,
and authoritative database ownership.

The new cycle receives a fresh cycle identity and fresh token-slot identities.

Discovery may not overwrite first-cycle reporting or source-accounting evidence.
Cycle-attributable evidence must remain identifiable by its real cycle id.

### 3. The factory loop must wake for both lifecycle work and admission opportunity

The current loop sleeps toward the next due lifecycle step. With a staggered
second admission it must instead consider the earliest of:

- next due existing lifecycle work;
- next lawful cycle-admission opportunity;
- cancellation/supervision failure;
- bounded proof duration/stop boundary.

A due mandatory close always outranks fresh admission.

The integration must not busy-poll and must not add an independent background
admission process.

### 4. Resolve cycle identity from durable work ownership

The current single-cycle path can safely carry one function-level `cycle_id`.
That is insufficient once later-cycle work exists.

For each Scheduler/lifecycle operation, the real cycle identity must be resolved
from durable campaign ownership, preferably through the existing
`printer_memory_factory_campaign_scheduler_work` row associated with the
canonical Scheduler job.

A second-cycle snapshot or close must never inherit cycle 1 merely because cycle
1 was the original function argument.

Identity drift must fail closed.

### 5. Continuation barriers must be cycle-local

The existing two-token 15m continuation law remains correct **inside each
cycle**.

Any helper that currently counts terminal 15m closes or activated tokens across
the whole factory run must be scoped to the owning cycle for the multi-cycle
proof.

Required behavior:

```text
cycle 1 A/B 15m barrier waits only for cycle 1 A/B
cycle 2 C/D 15m barrier waits only for cycle 2 C/D
```

Cycle 1 must not wait for C/D and cycle 2 must not change A/B's already-made
continuation decisions.

Likewise, the standard 1h -> 4h barrier must receive the actual owning cycle id
for the current continuation close.

### 6. Campaign window ownership must be cycle-local

Every 15m/1h/4h campaign window and campaign Scheduler-work projection must bind
to the actual cycle/token slot that owns the current factory step.

The proof must reject:

- a cycle-2 window attached to a cycle-1 slot;
- a cycle-2 Scheduler job projected under cycle 1;
- a duplicate token/pair active across the two cycles;
- reuse of a historical cycle/window identity.

No migration appears necessary because the existing campaign Scheduler-work and
window tables already carry `cycle_id`, `token_slot_id`, and `factory_run_id`.

### 7. Keep full-run accounting two-token and cycle-local

`campaign_full_run_accounting.py` is intentionally a two-token accounting
contract. Its `OperationalLifecycleOwnershipContext` requires:

```text
expected_token_capacity = 2
one exact cycle_id
```

Do **not** change that context to `expected_token_capacity = 4` merely because the
factory run contains two cycles.

The safer design is:

```text
shared campaign/run/factory identity

cycle 1 accounting context -> A/B -> exact two-token acceptance result
cycle 2 accounting context -> C/D -> exact two-token acceptance result

campaign-level aggregate -> requires both cycle-level accounting results to be
truthful and terminal, plus shared budget/lease/active-work reconciliation
```

This preserves the proven two-token accounting semantics and avoids rewriting
six-unit stage vocabulary into an unproved N-token model.

A cycle may close dirty/blocked honestly without fabricating a clean result. The
aggregate proof result reports both cycle outcomes; it never turns a dirty cycle
clean because its peer cycle succeeded.

### 8. Aggregate budgets from the canonical two-token contract

For the four-token proof, the active capacity envelope must derive from:

`scaled_standard_four_hour_capacity_contract(4)`

which itself derives from the canonical existing two-token standard-four-hour
contract.

The proof must not duplicate `117` or other per-token numeric arithmetic in a
new owner.

Provider **rate** ceilings remain unchanged. Scaling changes aggregate bounded
usage authority only; it does not increase DexScreener, GeckoTerminal, Jupiter,
Solana RPC, Helius, GoPlus, CoinGecko, fallback, retry, or endpoint-rotation
ceilings.

New admission is deferred before an existing memory close is weakened.

### 9. Multi-cycle terminal reconciliation

The current unified terminal path is safe for a single cycle but receives one
`cycle_id` for discovery parity, token-slot disposition, cycle transition, and
active-work proof. It separately terminalizes campaign-wide windows and the
shared run/campaign.

The four-token integration therefore needs a small terminal coordinator that:

1. reconciles each admitted cycle's discovery/work/slots exactly once;
2. terminalizes/cancels all remaining owned windows/work across the shared run;
3. transitions every admitted cycle to a lawful terminal state;
4. only then terminalizes the shared campaign run and campaign;
5. proves zero active/orphan Scheduler work for **all admitted cycles**;
6. preserves one immutable first shared terminal cause where a campaign-wide
   stop occurred;
7. creates no restart or successor.

It must compose the existing terminal owner rather than introduce a parallel
cleanup implementation.

### 10. Proof reports must distinguish cycle-local and shared truth

The four-token report must include at minimum:

- campaign id / campaign-run id / authoritative factory-run id;
- configured capacity `4 / 2`;
- actual admitted cycle count;
- exact cycle ids and admission times;
- >=300s stagger evidence;
- exact two slots per cycle;
- per-cycle discovery/selection outcome;
- per-cycle 15m/1h/4h lifecycle outcome;
- per-cycle clean/dirty/blocked memory outcome;
- per-cycle source/Scheduler usage;
- aggregate source/Scheduler usage and ceilings;
- provider failures / fallback use;
- Scheduler lag / due-close evidence;
- DB busy/lock and heartbeat/lease evidence;
- final active-work counts;
- locked-capability deltas;
- no successor/restart;
- four-token proof verdict.

The report must not call four tokens one four-slot cycle.

## Public runtime and authorization boundary

The current public runtime stays:

```text
TOKEN_CAPACITY = 2
cycle_count = 1
```

through this readiness/design/integration work.

The existing standard-four-hour authorization profile remains a one-attempt,
fail-closed authority. No authorization is created by this readiness audit.

A future four-token proof authorization must be a fresh, independently reviewed
bounded authority tied to the exact proof-integrated Git head and the exact
four-token configuration. It must not reuse any consumed prior standard-4h
authorization.

The actual proof must not be launched until:

1. this readiness audit closes PASS;
2. a separate proof-integration design closes PASS;
3. implementation + focused verification closes PASS;
4. proof preflight/readiness closes PASS;
5. fresh authorization is prepared and independently reviewed.

## Proof success requirements

The four-token bounded proof must establish, at minimum:

- exactly one campaign;
- exactly one campaign run;
- exactly one authoritative factory run;
- exactly two admitted cycles;
- exactly two slots per cycle;
- no second cycle before 300 seconds;
- never more than four active through-4h tokens;
- no single-token fresh admission;
- no duplicate token/pair across active cycles;
- Central Scheduler owns all lifecycle work;
- Source Governor owns all external work;
- mandatory close work is not starved by later admission;
- deterministic fairness across both cycles;
- cycle-local 15m and 1h/4h barriers;
- exact cycle/window/token/pair ownership;
- aggregate request/Scheduler ceilings stay within the four-token contract;
- provider rate ceilings remain unchanged;
- no hidden retry or endpoint rotation;
- no SQLite lock/heartbeat failure caused by multi-cycle integration;
- honest clean/dirty/blocked memory outcomes;
- zero active/orphan work at terminal;
- no restart/successor;
- all capability locks remain zero-delta.

Passing four does **not** authorize six. Six gets its own later readiness/proof
step after the four-token proof closeout PASS.

## Money-usefulness contribution

This proof integration is useful because it tests the smallest real increase in
concurrent learning diversity without sacrificing evidence quality. Two
staggered pairs allow Printer to observe four independent Solana memecoin
trajectories through the same 15m -> 1h -> 4h system, increasing the chance of
capturing different failure, survival, delayed-dump, recovery, manipulation,
and tradeability contexts while preserving the safety laws needed for later
paper decisions.

The objective remains **more trustworthy learning per day**, not maximum row
count or maximum API use.

## What this lane improves

- identifies the exact single-cycle runtime assumptions that must be generalized;
- proves no schema migration is inherently required for the two-cycle ownership
  shape;
- preserves pair-atomic discovery/selection instead of inventing a four-token
  selector;
- preserves one authoritative factory run;
- preserves the existing two-token full-run accounting contract cycle by cycle;
- defines cycle-local barriers and terminal reconciliation;
- keeps the four-token proof much smaller than the later 24h/30-token session.

## What this lane still does not unlock

This readiness PASS does not unlock:

- four-token runtime;
- six-token runtime;
- 24h continuous intake;
- a new authorization;
- any source fetch or discovery run;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet/private keys/real funds/live execution;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors;
- provider-ceiling increases;
- automatic retries or endpoint rotation changes.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Required mitigation | Proof / stop condition |
|---|---|---|---|
| Factory entry point assumes one cycle | Calling it twice would create competing factory ownership | Add one proof-gated admission hook inside the existing factory run | Any second factory run = stop/fail |
| Run-global 15m barrier | Four tokens could incorrectly wait/evaluate as one cohort | Scope barrier by durable cycle id | Cross-cycle continuation dependency = fail |
| Global function `cycle_id` reused for later work | Cycle-2 evidence could be attributed to cycle 1 | Resolve cycle from durable Scheduler/campaign ownership per work item | Any cycle/window mismatch = fail |
| Standard 4h barrier receives one cycle id | Later-cycle 4h planning could bind to wrong slot/window | Pass actual owning cycle at each continuation close | Wrong-cycle long work = fail |
| Full-run accounting is two-token by design | Widening it to four weakens proven semantics and requires broad rewrite | Keep one two-token accounting context/result per cycle and aggregate | `expected_token_capacity=4` shortcut = design failure |
| Unified terminal closure accepts one cycle id | One cycle could remain nonterminal/orphaned | Compose cycle-by-cycle reconciliation before shared run/campaign terminal | Any active/nonterminal admitted cycle after closeout = fail |
| Admission timer competes with close deadlines | Fresh intake could starve mandatory evidence | Earliest wake + close priority; admission defers | Missed/late close caused by admission = fail |
| Aggregate budget arithmetic drifts | Four-token operation could silently exceed source/Scheduler contract | Derive from canonical two-token standard-4h contract | Duplicated independent budget constants = fail |
| Discovery result aggregation unclear | Cycle 2 could overwrite cycle 1 accounting/reporting | Preserve per-cycle discovery evidence + aggregate report | Lost/ambiguous source ownership = fail |
| SQLite write contention | More lifecycle work can threaten lease continuity | Preserve short writes/no network under write lock; measure busy/heartbeat | New lock/heartbeat failure attributable to integration = blocker |
| Provider fallback burst | Concurrent failures may consume reserve | Keep provider ceilings unchanged and defer admission first | Ceiling/fallback reserve breach = safe stop |
| Six accidentally exercised | Skips required proof ladder | Hard proof config = 4/2; assert no >4 state | Any >4 active through-4h token state = fail |
| Long windows leak in | Violates active roadmap | Keep 12h/24h locks and zero-delta checks | Any 12h/24h runtime row/work = fail |

## Closeout decision

The four-token proof is **architecturally feasible without redesigning Printer**.
The required work is a bounded extension of the existing canonical factory,
Scheduler ownership, campaign cycle graph, and terminal/accounting owners.

There is no evidence in this audit that a new database schema, new Scheduler,
new Source Governor, new discovery engine, or four-slot cycle is required.

The next permitted lane is:

`FOUR_TOKEN_BOUNDED_CAPACITY_PROOF_INTEGRATION_DESIGN`

That lane is design-only. It must freeze the exact hook/API boundaries,
cycle-resolution method, cycle-local accounting aggregation, budget contract,
terminal composition, and focused proof fixtures before implementation begins.
