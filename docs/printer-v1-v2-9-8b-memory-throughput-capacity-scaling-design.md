# Printer V1 V2-9.8B Memory Throughput Capacity Scaling Design

## Verdict

`V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_SCALING_DESIGN_PASS_READY_FOR_SEPARATE_LE4H_IMPLEMENTATION`

This design adopts the minimal-change scaling direction proven feasible by
`docs/printer-v1-v2-9-8b-memory-throughput-capacity-audit.md`.

The implementation target is built to support a hard maximum of **six concurrent
through-4h tokens**, while the operational proof ladder must exercise **four
concurrent tokens first and six only after four closes PASS**.

This design does not change the current authorized runtime capacity. It does not
run Printer, fetch sources, mutate the authoritative database, generate memory,
activate 12h/24h, activate retrieval, create paper decisions, unlock
BUY/SELL/HOLD, create positions/trades/audits/PnL, or change provider rate
ceilings.

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

Design baseline:

- audit branch: `agent/v2-9-8b-memory-throughput-capacity-audit`
- audit commit: `abef1aa12fce9d20690066b3820ce19b39b7a452`
- audit verdict:
  `V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_AUDIT_PASS_MINIMAL_CHANGE_MULTI_CYCLE_SCALING_RECOMMENDED`

## Design objective

Maximize the number of Solana memecoins Printer can learn from per day without
replacing the architecture already built.

The scaled factory must:

- reuse the existing campaign/run/cycle/token-slot ownership graph;
- retain exactly two token slots per admission cycle;
- retain atomic two-token initial handoff per cycle;
- use one Central Scheduler;
- use one Source Governor and one global source-accounting path;
- use one bounded supervised operational campaign;
- preserve exact token/mint/pair/lifecycle/window identity;
- preserve clean/dirty/evidence rules;
- preserve token-local failure isolation;
- preserve SQLite short-write/no-network-I/O-under-write-lock protections;
- preserve all current free/public provider ceilings;
- preserve no automatic retry and no endpoint-rotation drift;
- leave capacity available for future retrieval and paper components;
- stop/defer new admissions rather than weaken evidence quality.

## Core architecture decision

### Keep the two-token cycle

One cycle remains exactly:

```text
Cycle N
  - slot 1 -> one token
  - slot 2 -> one token
```

Do not widen the existing `(1,2)` slot-ordinal schema contract merely to obtain
more concurrency.

Do not replace the atomic two-slot discovery/selection/handoff contract.

Do not create a new N-token discovery engine.

### Scale by overlapping finite cycles

One bounded campaign/run may own several finite two-token cycles whose token
lifecycles overlap in wall-clock time.

Initial implementation capability:

```text
maximum concurrently active through-4h cycles = 3
maximum concurrently active through-4h tokens = 6
```

Example:

```text
12:00  Cycle 1 -> A + B
12:05  Cycle 2 -> C + D
12:10  Cycle 3 -> E + F

A-F may all remain active concurrently through their standard
15m -> 1h -> 4h observation lifecycle.
```

Starting a later cycle must not cancel, restart, replace, reset, or otherwise
interrupt an earlier healthy cycle.

## Build for six; prove four before six

The production implementation is intentionally written once for the six-token
capability.

It must expose a bounded configuration/authorization ceiling that allows the
same implementation to run below its compiled/design maximum.

Required proof sequence:

```text
implementation capability maximum = 6

Proof 1:
  configured concurrent-through-4h maximum = 4
  active cycles maximum = 2

Only if Proof 1 PASS:

Proof 2:
  configured concurrent-through-4h maximum = 6
  active cycles maximum = 3

Only if Proof 2 PASS:
  six becomes the first proven scaled operational ceiling
```

Do not build a four-token-only architecture and then redesign it for six.

Do not exercise six before the four-token proof closes PASS.

A four-token failure must be classified first. A genuine design/implementation
fault must be repaired and re-proven before six is attempted. A provider or
external-network failure must not automatically trigger code changes.

## Admission cadence

The initial design uses a **minimum five-minute spacing** between new two-token
cycle admissions.

Five minutes is not a promise to admit a new cycle every five minutes.

At each admission opportunity, Printer must first confirm that all applicable
bounded gates remain healthy, including:

- configured concurrent-through-4h token ceiling;
- configured active-cycle ceiling;
- global source-request budget;
- provider-specific rolling ceilings;
- Scheduler-work budget and due-work health;
- mandatory close-time reserve;
- shared campaign supervision/lease health;
- authoritative DB health;
- no shared terminal condition;
- no cancellation/drain state;
- discovery/selection capacity;
- future protected-work admission guard when later capabilities unlock.

If an admission gate is not satisfied, Printer skips or defers that admission.
Existing healthy tokens continue normally.

No new cycle may be admitted by weakening close freshness, source evidence,
identity validation, source provenance, Scheduler ownership, or memory-quality
rules.

## Automatic capacity recycling

The one-command factory must recycle through-4h capacity automatically.

Example:

```text
12:00  A+B start
12:05  C+D start
12:10  E+F start

~16:00 A+B finish their 4h boundary
        -> their through-4h capacity is released
        -> if intake remains open and all admission gates pass,
           a new two-token cycle may start

~16:05 C+D release their through-4h capacity
~16:10 E+F release their through-4h capacity
```

A later cycle receives fresh identities. It must never reuse a prior token
window as if it were the new cycle's evidence.

Existing cooldown/archive/replacement hygiene remains authoritative.

## One-command continuous operation

The eventual public operator surface must require **one terminal command** for
one bounded memory-growth session.

The exact public command name and syntax are implementation details and are not
invented by this design. Whatever command is adopted must have one canonical
wrapper and one child ownership path.

The requested duration is an **intake duration**, not an unconditional process
kill time.

For a requested 24-hour memory-growth session:

### Stage 1 - active intake

For 24 hours from the accepted start anchor:

- Printer may discover/select and admit new two-token cycles;
- new-cycle admissions remain bounded by concurrency, source, Scheduler, DB,
  close-reserve, and health gates;
- admitted token lifecycles run continuously and independently under the same
  campaign/supervisor/Scheduler/Source Governor.

### Stage 2 - bounded drain

At the intake deadline:

- no new token or new two-token cycle may be admitted;
- already accepted lifecycles are not killed merely because intake ended;
- existing work may continue only to its already-authorized legitimate terminal
  boundary;
- the drain remains bounded, supervised, cancellable, and globally budgeted;
- no restart, successor campaign, or new intake period is created automatically.

### Stage 3 - final closeout

After all accepted lifecycle work reaches a terminal state or a valid safe-stop:

- reconcile campaign/run/cycle/token/window/Scheduler ownership;
- confirm no active work or leaked lease;
- produce the required campaign/corpus/source-efficiency report;
- preserve all capability-lock deltas;
- exit cleanly.

This means a `24h` request means **24 hours of new-token intake plus safe bounded
drain**, not "kill everything exactly 24 hours after process start."

## Through-4h capacity semantics

The first scaled operational target is:

```text
maximum through-4h active tokens = 6
maximum through-4h active cycles = 3
```

This ceiling covers tokens in the standard bounded observation path through:

- `WINDOW_5M_MICRO_EVENT` support evidence;
- `WINDOW_15M`;
- `WINDOW_1H`;
- `WINDOW_4H`.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create a
main outcome, continuation, retrieval result, paper decision, BUY/SELL/HOLD,
position, trade event, audit, or PnL.

The current post-DTW100 through-4h rule remains unchanged: every otherwise-valid
activated token follows the standard 15m -> 1h -> 4h observation path unless a
hard evidence/identity/freshness/provenance/safety/continuity/resource/cancel
condition blocks it.

## New admission remains pair-atomic in the first version

The first scaled version does not add opportunistic single-token fresh intake
inside a half-vacant cohort.

Fresh intake remains:

```text
new cycle = exactly two newly admitted tokens or no new cycle
```

This preserves the proven atomic two-slot handoff and minimizes changes to
fairness and ownership.

If one through-4h token fails early while its cohort peer remains active, the
first version does not immediately fill that one vacancy with an unrelated fresh
token. Single-vacancy throughput optimization may be audited later if measured
waste justifies the additional complexity.

## Scheduler fairness across overlapping cycles

The existing two-token fairness semantics remain the model; they must be
generalized across several active two-token cycles rather than replaced.

Required global ordering principles:

1. existing higher-priority Printer work remains higher priority;
2. mandatory main-window closes and close-freshness work must not be starved;
3. evidence-gap and safe-stop work must not be starved;
4. ordinary memory work must remain deterministic and fair across active tokens;
5. no cycle may monopolize ordinary service merely because it was admitted first;
6. later cycle admission must not reorder or invalidate already-due close work;
7. all service remains Central-Scheduler-owned.

The implementation must not introduce scoring, ranking, confidence,
percentages, or weighted scheduling logic.

## Source Governor and provider capacity

All overlapping cycles consume one shared governed source budget.

No provider rate ceiling is raised by this scaling work.

The current internal provider ceilings remain authoritative unless separately
changed by a future approved source-policy lane.

In particular:

- DexScreener scaling must remain inside Printer's existing ceiling;
- GeckoTerminal fallback reserve must be protected;
- Jupiter keyless headroom must not be consumed by aggressive admission;
- Solana RPC and Helius must remain inside Printer's governed ceilings and free
  dependency rules;
- GoPlus/CoinGecko and any other approved context source must remain centrally
  governed;
- free-plan daily/monthly limits where applicable must remain reportable and
  bounded;
- no paid API dependency is permitted.

When source/fallback/close pressure increases, **new admission is the workload to
throttle first**. Existing clean-memory evidence requirements are not weakened.

## DB and supervision requirements

Multi-cycle scaling must preserve the existing SQLite concurrency repair:

- no network I/O while holding a shared write transaction;
- bounded short write transactions;
- heartbeat/lease renewal remains independently able to write;
- genuine SQLite contention continues to fail closed;
- exact campaign/run/cycle/token/window ownership remains auditable;
- no parallel authoritative database is created;
- no independent campaign process is started every five minutes.

The bounded proofs must explicitly measure DB lock/busy events, heartbeat
continuity, write/row growth, and terminal cleanup.

## Daily throughput target

The first scaled design is intended to support approximately:

```text
comfortable planning target: 20-25 new tracked tokens / 24h intake
initial upper target to prove: up to 30 new tracked tokens / 24h intake
```

These are throughput goals, not guarantees and not clean-memory quotas.

Success remains based on honest clean/dirty/blocked outcomes, memory quality,
source efficiency, diversity, safe lifecycle completion, and lock preservation;
not raw row count.

## Future 4h -> 12h continuation contract

This section records the agreed **future design requirement** for V2-10/V2-11
and later selective operational continuation. It does not activate or implement
12h runtime in this lane.

A token is evaluated independently after its real 4h close.

Required candidate gate:

```text
4H close = CLEAN_MEMORY
AND liquidity_usd >= 3,000
AND current rolling 1H volume_usd >= 500
AND current rolling 1H transactions >= 5
AND current rolling 24H volume_usd >= 5,000
AND exact pair remains valid
AND all gate evidence is fresh and clean
AND approved long-window capacity is available
```

`1H transactions` means exact-pair 1h buys + exact-pair 1h sells under the
approved source contract.

Thresholds are inclusive.

Missing, stale, failed, mismatched, or unsupported evidence never becomes zero
and never silently passes.

A failed gate stops long-window continuation without deleting or invalidating
the already-earned 15m/1h/4h memory.

## Future 12h -> 24h continuation contract

A token that reaches a real 12h close is evaluated independently again.

Required candidate gate:

```text
12H close = CLEAN_MEMORY
AND liquidity_usd >= 3,000
AND current rolling 1H volume_usd >= 500
AND current rolling 1H transactions >= 5
AND current rolling 24H volume_usd >= 5,000
AND exact pair remains valid
AND all gate evidence is fresh and clean
AND approved long-window capacity is available
```

Passing 4h -> 12h does not automatically authorize 12h -> 24h.

## Lone-token long continuation is required

Long-window continuation must be token-local.

For any two-token cohort at the 4h boundary:

```text
A passes / B passes -> A and B may continue independently
A passes / B fails  -> A may continue alone; B stops
A fails  / B passes -> B may continue alone; A stops
A fails  / B fails  -> neither continues
```

A qualifying token must never require an artificial partner merely because its
original intake cycle contained two tokens.

The existing token-local continuation philosophy is preserved. Later
long-window implementation must generalize the currently two-input operational
surface without changing this independent per-token verdict property.

## Long-window survivors do not occupy the six through-4h intake positions

Once a token completes its 4h boundary, its through-4h capacity position is
released even if that token later qualifies for a selective 12h continuation.

Therefore this must be possible in the later approved long-window system:

```text
A -> 12h long-window continuation
B -> stops at 4h

while

G + H -> enter a new fresh two-token through-4h cycle
```

A still consumes real Scheduler/source/DB resources. It is not free.

Long-window survivors therefore require a **separate bounded long-window
capacity ceiling** inside the same campaign/Scheduler/Source Governor/global
budgets.

The numerical 12h/24h concurrency ceiling is intentionally **not fixed here**.
V2-10 must define the long-window cadence, source cost, close reserve, and safe
capacity before V2-11 proof and later operational activation.

## Capacity scarcity in future long windows

Market/evidence eligibility is necessary but not sufficient when long-window
capacity is full.

If more tokens qualify than the approved long-window capacity can accept:

- do not exceed the capacity ceiling;
- do not rank or score tokens;
- use a deterministic categorical allocation rule approved in the V2-10 design,
  with earliest eligible close first as the default candidate;
- record an honest capacity-blocked reason for an otherwise eligible token;
- do not delay the start so long that lifecycle continuity becomes false.

Suggested reason:

`LONG_WINDOW_CONTINUATION_BLOCKED_CAPACITY`

## Future retrieval and paper-work fairness

This scaling design does not activate retrieval or paper capability.

When those lanes eventually unlock, memory growth must remain subordinate to
higher-priority safety-critical Printer work.

The existing Scheduler already represents open-paper monitoring and active exit
risk above ordinary memory work. That ordering must remain intact.

Before retrieval or paper activation, their real cadence/provider/DB demand must
be added to the capacity model.

The system may lower or pause **new memory admissions** when protected future
work needs capacity. It must not weaken already-required clean-memory evidence
to preserve admission throughput.

No arbitrary permanent 70/30 or similar resource split is adopted by this
design. Future reserve must be evidence-derived from the actual approved
workloads.

## Implementation boundary

### Allowed in the next separate <=4h implementation lane

After this design is reviewed/accepted, the next implementation lane may make
the minimum changes required to support:

- one bounded campaign/run with up to three overlapping two-token cycles;
- implementation hard maximum of six concurrent through-4h tokens;
- runtime-configured proof ceilings below that maximum;
- minimum five-minute admission spacing;
- admission defer/skip gates;
- automatic two-token capacity recycling after terminal through-4h work;
- generalized deterministic fairness across several cycles;
- one-command finite intake duration;
- automatic transition from intake to bounded drain;
- final safe closeout/reporting;
- global source/Scheduler/storage/failure ceilings derived for the configured
  concurrency;
- focused reporting for active cycles, admitted tokens, deferred admissions,
  source pressure, close pressure, DB health, and drain outcome.

### Not allowed in that <=4h implementation lane

- real 12h/24h collection;
- operational 4h -> 12h or 12h -> 24h successor creation;
- V2-11 proof runtime;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL;
- live wallet/private key/signing/real funds;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors;
- provider-ceiling increases;
- automatic retries;
- independent competing campaign processes;
- unbounded daemon operation.

The 12h/24h sections in this document are design input to the existing V2-10 ->
V2-11 -> V2-11.7 sequence, not an early implementation authorization.

## Minimum implementation verification

The implementation lane should use risk-based verification rather than a broad
suite by default.

Minimum sufficient static/disposable checks should cover:

- unchanged two-token behavior at configured maximum 2;
- exactly two slots per cycle;
- no partial-cycle activation on second-slot handoff failure;
- two overlapping cycles can coexist without identity collision;
- three overlapping cycles can be represented under the implementation hard cap;
- a fourth active through-4h cycle is blocked at the six-token cap;
- admission spacing cannot be shorter than the configured minimum;
- due close work outranks new admission;
- ordinary service remains deterministic/fair across cycles;
- token-local failure does not cancel healthy peers/cycles;
- ending intake creates no new cycles while preserving accepted work for drain;
- drain creates no successor campaign/restart;
- Source Governor and Central Scheduler remain the only owners;
- DB write-lock release around source I/O remains intact;
- all retrieval/financial capability deltas remain zero.

No live provider proof is part of implementation itself unless separately
authorized by the proof lane.

## Bounded proof plan

### Proof A - four concurrent through-4h tokens

Configuration:

```text
implementation hard max tokens = 6
proof configured max tokens = 4
proof configured active cycles = 2
```

Prove at minimum:

- staggered second-cycle admission;
- all four identities remain exact and independent;
- no Scheduler starvation;
- mandatory closes remain within freshness contract;
- source/provider ceilings and fallbacks remain within policy;
- no unexpected rate-limit pattern caused by concurrency;
- no SQLite/heartbeat contention regression;
- clean/dirty/blocked labels remain honest;
- terminal cleanup and reporting reconcile;
- no downstream capability delta.

Only a PASS closeout may authorize Proof B.

### Proof B - six concurrent through-4h tokens

Configuration:

```text
implementation hard max tokens = 6
proof configured max tokens = 6
proof configured active cycles = 3
```

Repeat the same core proof while also establishing:

- third-cycle staggered admission;
- six-token fairness;
- close/fallback burst behavior;
- global campaign/source/Scheduler/storage ceilings are sufficient but bounded;
- admission defers correctly when close/fallback pressure consumes reserve;
- six can become the proven operational capacity without weakening evidence.

Only a PASS closeout may make six the first scaled operational ceiling.

## Proof stop conditions

Stop/fail closed on any of the following:

- Source Governor or Central Scheduler bypass;
- source/provider ceiling breach;
- unaccounted transport operation;
- hidden automatic retry or endpoint rotation;
- missed mandatory close because new admission was serviced instead;
- cross-token/cross-cycle identity contamination;
- one cycle starving another beyond approved timing;
- DB lock/heartbeat regression attributable to the scaling change;
- orphaned active work after terminalization;
- intake deadline still admitting new tokens;
- bounded drain spawning a successor/restart;
- dirty/incomplete evidence promoted as clean;
- any retrieval/financial capability delta;
- implementation exercising 12h/24h runtime early.

## Money-usefulness contribution

This design increases the diversity and daily volume of real Solana memecoin
lifecycle lessons without lowering evidence quality or turning memory growth into
a source-budget race.

More independent 15m/1h/4h outcomes per day means Printer can accumulate useful
pump, dump, round-trip, trap, survival, liquidity, flow, and exit-realism lessons
more quickly. Selective later 12h/24h continuation adds delayed-death/revival and
full-cycle outcomes without forcing every token to consume long-window resources.

## What this design improves

- Reuses Printer's proven two-token unit rather than replacing it.
- Defines one implementation capable of six concurrent through-4h tokens.
- Separates implementation capability from staged operational proof.
- Enables staggered overlapping cohorts under one campaign.
- Defines automatic capacity recycling.
- Defines one-command finite intake plus safe bounded drain.
- Preserves provider/Scheduler/DB safety and future Printer fairness.
- Defines lone-token long-window continuation semantics for later V2-10/V2-11
  adoption.

## What this design still does not unlock

- runtime capacity above the currently authorized value;
- any 4-token or 6-token live proof;
- actual 12h/24h runtime;
- long-window capacity number;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live execution;
- wallet/private-key/signing logic;
- paid APIs;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- unbounded operation.

## Proof/test needed before completion of the scaling program

The full scaling program is not complete until:

1. this design is accepted;
2. the <=4h multi-cycle implementation passes focused static/disposable tests;
3. the four-token bounded proof closes PASS;
4. the six-token bounded proof closes PASS;
5. the operational-capacity closeout records the exact proven ceiling and
   preserves all locks.

Long-window operational scaling remains a later program requiring V2-10,
V2-11, and the explicit selective operational continuation lane.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Mitigation / proof |
| --- | --- | --- |
| Six-token implementation is exercised before four-token proof | Skips staged risk reduction | hard proof configuration cap; Proof A PASS required before Proof B |
| Multi-cycle fairness regression | One cohort could miss evidence/close work | global deterministic fairness + close-priority tests and bounded proofs |
| Fallback burst saturation | Primary failures can concentrate Gecko/RPC work | stagger cycles, protect close/fallback reserve, defer new admission |
| SQLite write contention returns | More cycles mean more persistence activity | preserve short-write/no-I/O lock contract; measure heartbeat/lock behavior |
| Intake greed damages active memory | More rows but worse clean-memory yield | admission throttles first; never weaken evidence/close rules |
| Long survivor blocks fresh learning | A 24h token could consume scarce intake slot | release <=4h slot at 4h; later use separate bounded long-window ceiling |
| Only one token qualifies for long continuation | Pair-locked continuation would waste useful evidence | long-window continuation is token-local and may run one token alone |
| 24h wall clock cuts accepted lifecycles | Produces incomplete/dirty memory artificially | 24h intake followed by bounded drain |
| Daily target becomes a quota | Could incentivize weak/dirty memory | 20-30/day is planning throughput, never success criterion |
| Future paper/retrieval contention | Memory could starve more important Printer work | protected Scheduler priority + throttle new admissions after later capacity review |
| Old 12h/24h cadence is too expensive | Long windows may consume excessive budget | V2-10 must define cadence/budgets before implementation/proof |
| Provider contracts change | Current arithmetic may become stale | recheck official limits immediately before proof/activation |

## Closeout

Design verdict:

`V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_SCALING_DESIGN_PASS_READY_FOR_SEPARATE_LE4H_IMPLEMENTATION`

The next permitted work from this design is a separately scoped **<=4h
multi-cycle capacity-scaling implementation** built for a hard maximum of six
concurrent through-4h tokens.

That implementation must not run a live capacity proof automatically. After
implementation closeout, the required proof sequence is **4 concurrent tokens
first, then 6 only after 4 PASS**.

The long-window continuation requirements recorded here remain design input only
until the active V2-10/V2-11/V2-11.7 sequence authorizes their implementation and
bounded proof.