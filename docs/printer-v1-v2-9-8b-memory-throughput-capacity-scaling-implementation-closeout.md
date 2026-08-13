# Printer V1 V2-9.8B Memory Throughput Capacity Scaling Implementation Closeout

## Verdict

`V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_SCALING_IMPLEMENTATION_PASS_READY_FOR_FOUR_TOKEN_BOUNDED_PROOF`

This closes the implementation lane defined by:

- `docs/printer-v1-v2-9-8b-memory-throughput-capacity-scaling-design.md`
- `docs/printer-v1-v2-9-8b-memory-throughput-capacity-scaling-design-clarification.md`
- `docs/printer-v1-v2-9-8b-memory-throughput-capacity-scaling-implementation-plan.md`

The implementation is built for a hard compiled maximum of **six concurrent through-4h tokens as three exact two-token active cycles**, while the current public operational runtime remains unchanged at **two tokens / one cycle** until separately bounded proof and activation lanes pass.

## Implemented capability

The lane added three bounded foundations without replacing Printer's architecture:

1. `multi_cycle_memory_growth.py`
   - exact 2/4/6 configured through-4h capacity contracts;
   - hard maximum 6 concurrent through-4h tokens / 3 active two-token cycles;
   - minimum 300-second cycle-admission spacing;
   - independent whole-session ceiling of 15 two-token admissions / 30 new tokens for a 24h intake;
   - ACTIVE_INTAKE -> DRAIN -> COMPLETE state model;
   - explicit Source Governor, provider-budget, Scheduler, close-reserve, DB, lease, discovery, and protected-work admission gates;
   - no single-token fresh admission.

2. `multi_cycle_fairness.py`
   - composes the existing two-token Scheduler selector rather than replacing it;
   - supports 1-3 active exact two-token cycles;
   - global close priority, evidence-gap/safe-stop priority, then deterministic ordinary fairness;
   - no score/rank/confidence/weighted scheduling system.

3. `multi_cycle_campaign_coordinator.py`
   - reuses the existing campaign/run/cycle/token-slot ownership graph;
   - keeps one campaign run bound to one authoritative factory-run identity;
   - permits finite historical cycles beyond the first three while limiting simultaneous active cycles to three;
   - requires exact pair-atomic two-token admission;
   - uses monotonic cycle ordinals and fresh cycle/token-slot identities;
   - recycles released through-4h pair capacity while intake is open;
   - enters drain when intake or the total-cycle ceiling closes;
   - creates no second campaign, factory run, Scheduler, Source Governor, or database schema owner.

No migration was required.

## Verified evidence

Operator verification was run on exact implementation head:

`384ee4090f241557d489432bec17f936db7abe5a`

Observed results:

- `tests/test_v2_9_8b_multi_cycle_session_coordinator.py`: **12 passed**
- `tests/test_v2_9_8b_memory_throughput_capacity_scaling.py`: **20 passed, 23 subtests passed**
- `tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py`: **6 passed**
- `tests/test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py`: **14 passed**
- static compilation: PASS
- `git diff --check`: PASS
- migration-change guard: PASS; no migration changed
- current public runtime token capacity remains `2`: PASS
- canonical two-token standard-4h contract remains `2 / 236 / 117 / 210`: PASS
- compiled scaling maximum `6 tokens / 3 active cycles`: PASS
- whole-session maximum `15 cycles / 30 new tokens`: PASS
- `WINDOW_12H` / `WINDOW_24H` runtime remains locked: PASS

The final local status also showed only the pre-existing untracked historical operator artifact directory:

`operator-runs/v2-9-8b-standard-four-hour-final-authorization/`

It is not part of this implementation and was not modified or deleted.

## Public-runtime boundary

Six is **implemented capacity**, not proven or authorized operational capacity.

Three is the **simultaneous active-cycle ceiling**, not the whole-session cycle count.

The current public operational command remains at two tokens / one cycle. This implementation lane deliberately does not widen `TOKEN_CAPACITY`, does not expose a six-token public mode, and does not run Printer.

The canonical factory currently initializes one factory-run ledger and one initial discovery/lifecycle cycle at its public entry point. The next bounded-proof integration must therefore add only the smallest proof-gated cycle-admission hook needed to let that same authoritative factory run accept a second cycle. It must not invoke the canonical factory three separate times and must not create competing lifecycle runners.

## Required proof order

The next permitted runtime progression is:

1. **four-token bounded proof**
   - configured through-4h maximum: 4
   - configured active-cycle maximum: 2
   - two exact two-token cycles
   - second cycle admission no earlier than 300 seconds after the first

2. Only if the four-token proof closes PASS: **six-token bounded proof**
   - configured through-4h maximum: 6
   - configured active-cycle maximum: 3
   - three exact two-token cycles

Six / three must not be exercised before four / two passes.

A proof failure must be classified before any repair. External/provider/network failures do not justify production changes by themselves.

## Money-usefulness contribution

This implementation creates the bounded foundation for materially increasing daily learning diversity without weakening memory quality. Once proved and activated, Printer can recycle a finite six-token through-4h envelope across multiple two-token admissions rather than keeping daily learning constrained to one pair. The design target remains approximately 20-25 comfortable new tracked tokens per 24h intake and up to 30 as an upper target to prove, not a guaranteed quota.

More clean, dirty, failed, delayed-dump, recovery, survival, and lifecycle examples can improve the usefulness of the later memory corpus while preserving source and Scheduler headroom for higher-priority Printer work.

## What this lane improves

- bounded simultaneous-capacity representation for 2/4/6 tokens;
- correct separation of simultaneous active cycles from total 24h cycle admissions;
- campaign-wide deterministic fairness across up to three two-token cycles;
- one-run multi-cycle persistence and admission ownership;
- automatic pair-capacity recycling semantics;
- intake/drain semantics for eventual one-command continuous operation;
- explicit admission throttling before memory-quality degradation.

## What this lane still does not unlock

This closeout does **not** unlock:

- four-token or six-token live/runtime operation;
- a 24h live memory-growth run;
- `WINDOW_12H` or `WINDOW_24H` runtime;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet/private keys/real funds/live execution;
- paid API dependency;
- provider-ceiling increases;
- automatic retries or endpoint rotation changes.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test required before completion of scaling

The implementation closeout is complete, but operational scaling is not. The next proof must establish at four-token / two-active-cycle load:

- one authoritative factory-run identity throughout;
- exact cycle/token/pair/window ownership;
- no competing Scheduler or Source Governor path;
- no fourth/six-token accidental activation;
- >=300-second staggered admission;
- close-boundary priority and no token/cycle starvation;
- provider/source ceilings and fallback reserve remain inside policy;
- Scheduler work ceilings remain inside policy;
- SQLite busy/lock behavior and heartbeat continuity remain healthy;
- token-local failure isolation remains correct;
- no missed mandatory closes caused by the added cycle;
- clean/dirty outcomes remain honest;
- terminal reconciliation leaves zero active/orphan work;
- no successor/restart is created;
- locked capability tables remain unchanged.

Only after that closes PASS may a six-token proof be prepared.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Canonical factory public entry point is still single-cycle.**
   - This is intentional at implementation closeout.
   - The four-token proof lane must introduce a proof-gated admission hook into the same factory run rather than start a second factory runner.

2. **Cross-cycle lifecycle ownership must resolve by actual cycle identity.**
   - Later-cycle Scheduler/window work cannot inherit the first cycle's identity.
   - The proof integration must resolve the cycle from durable campaign Scheduler ownership for each admitted token/work item.

3. **Whole-session 30-token capacity is a ceiling, not demonstrated throughput.**
   - Actual sustainable daily throughput depends on proof-measured source usage, Scheduler lag, DB pressure, failure reserve, and eventual long-window load.

4. **12h/24h continuation remains separately gated.**
   - Long-window cadence/capacity must be settled in the approved V2-10/V2-11 sequence before runtime activation.

5. **Future retrieval/paper workloads are not yet active.**
   - Memory admission must remain the first workload throttled when those higher-priority components later consume real capacity.

## Next permitted lane

`FOUR_TOKEN_BOUNDED_CAPACITY_PROOF_INTEGRATION_AND_READINESS`

The next work is implementation/readiness for a **four-token / two-active-cycle bounded proof only**. It may add the minimum proof-gated canonical-factory cycle-admission integration required to exercise two staggered cycles under the same authoritative factory run.

It must not create an authorization or run the four-token proof until its own readiness review and closeout pass.
