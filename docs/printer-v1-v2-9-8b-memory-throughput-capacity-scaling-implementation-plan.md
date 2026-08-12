# Printer V1 V2-9.8B Memory Throughput Capacity Scaling Implementation Plan

> **For agentic workers:** implement this plan task-by-task with test-first changes and focused verification only.

**Goal:** Build the existing Memory Factory architecture once for a hard maximum of six concurrent through-4h tokens as three exact two-token cycles, while keeping current public runtime capacity at two until separate 4-token and then 6-token proofs pass.

**Architecture:** Preserve the existing two-token cycle, atomic pair admission, Central Scheduler, Source Governor, campaign ownership, and provider ceilings. Add a pure multi-cycle capacity/session policy and a campaign-wide fairness wrapper that composes the existing two-token selector. Add a bounded internal coordinator contract for 24h intake -> drain semantics without activating a new public runtime mode or 12h/24h.

**Tech stack:** Python 3, dataclasses/enums, existing Printer scheduler contracts, existing two-token fairness policy, unittest/pytest-compatible tests.

## Global constraints

- Solana-only, Solana-memecoin-only, paper-only V1 restrictions remain unchanged.
- No live wallet, keys, funds, signing, execution, paid API, scoring/ranking/confidence/weighted logic, embeddings/vectors.
- Source Governor and Central Scheduler remain mandatory owners.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- 12h/24h runtime, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked.
- Existing provider ceilings, automatic retries=0, and endpoint-rotation policy remain unchanged.
- Existing public operational token capacity remains 2 in this implementation lane.
- Compiled/design maximum: 6 through-4h tokens / 3 active two-token cycles.
- Proof sequence after implementation: configured 4 tokens / 2 cycles first; only after PASS may 6 / 3 be exercised.
- New-cycle spacing minimum: 300 seconds.
- Fresh admission is pair-atomic: exactly two new tokens or no new cycle.
- Intake duration is admission duration; after deadline the session enters bounded drain and admits nothing new.

---

### Task 1: Pure multi-cycle capacity and intake/drain policy

**Files:**
- Create: `src/printer_v1/operator_cli/multi_cycle_memory_growth.py`
- Test: `tests/test_v2_9_8b_memory_throughput_capacity_scaling.py`

**Produces:**
- `MAX_THROUGH_4H_TOKENS = 6`
- `MAX_ACTIVE_TWO_TOKEN_CYCLES = 3`
- `TOKENS_PER_CYCLE = 2`
- `MIN_CYCLE_ADMISSION_SPACING_SECONDS = 300`
- `MultiCycleCapacityPolicy`
- `MultiCycleAdmissionState`
- `AdmissionDecision`
- `evaluate_cycle_admission(...)`
- `scaled_standard_four_hour_capacity_contract(...)`

**Required behavior:**
- Accept configured ceilings 2/1, 4/2, or 6/3 only; reject odd, mismatched, zero, or >6 configurations.
- Derive aggregate 4h request/Scheduler ceilings from the canonical existing two-token standard-four-hour contract, never duplicate per-token numbers.
- Admit only when two token positions and one cycle position are available, intake remains open, >=300s has elapsed since the prior admission, and every explicit health/budget gate is true.
- Defer admission without affecting existing work when capacity, spacing, source, Scheduler, close reserve, DB, lease, discovery, or protected-work gate is unavailable.
- Enter `DRAIN` at/after the intake deadline and never admit another cycle.
- Report `COMPLETE` only after drain and zero accepted active through-4h cycles/tokens.
- Treat impossible state (negative counts, counts above configured ceiling, active tokens with zero cycles, active cycles requiring more than configured capacity) as fail-closed invalid state.

**TDD verification:** focused tests must cover 2/4/6 configuration, >6 rejection, 12:00/12:05/12:10 admissions, no admission before five minutes, automatic capacity reuse after a completed cycle, individual-token early failure without single-token refill, each health gate, intake deadline -> drain, and drain -> complete.

---

### Task 2: Campaign-wide fairness across several exact two-token cycles

**Files:**
- Create: `src/printer_v1/scheduler/multi_cycle_fairness.py`
- Extend test: `tests/test_v2_9_8b_memory_throughput_capacity_scaling.py`

**Consumes:** existing `TwoTokenSlot`, `SchedulerWorkItem`, `CampaignSchedulerCeilings`, `SchedulerWorkIntent`, `SchedulerSelectionStatus`, and `select_two_token_scheduler_work` from `two_token_fairness.py`.

**Produces:**
- `TwoTokenCycleWork`
- `MultiCycleSchedulerSelection`
- `select_multi_cycle_scheduler_work(...)`

**Required behavior:**
- Accept 1-3 cycles only; every cycle must contain exactly two slots.
- Preserve the existing two-token selector inside each cycle rather than replacing it.
- Use one shared campaign ceiling and shared-stop set.
- Global priority: mandatory main-window close first (earliest deadline), then evidence-gap/safe-stop, then ordinary work.
- Ordinary work remains fair by the selected token's existing `ordinary_service_count`, then oldest creation time, then stable cycle ordinal/work id.
- A later cycle cannot starve an older cycle, and an older cycle cannot monopolize ordinary work.
- Token-local failure remains isolated through the existing selector.
- Shared DB/lease/integrity/campaign-budget failure blocks the campaign-wide selection.
- No score/rank/confidence/weighted scheduling logic.

**TDD verification:** focused tests cover earliest close across cycles, safe-stop over ordinary across cycles, ordinary fairness across all six tokens, deterministic tie breaking, terminal/failed token exclusion, shared ceiling exhaustion, exactly-three-cycle acceptance, and fourth-cycle rejection.

---

### Task 3: Bounded internal session coordinator contract

**Files:**
- Extend: `src/printer_v1/operator_cli/multi_cycle_memory_growth.py`
- Extend test: `tests/test_v2_9_8b_memory_throughput_capacity_scaling.py`

**Produces:**
- `MultiCycleSessionPhase` with `ACTIVE_INTAKE`, `DRAIN`, `COMPLETE`, `BLOCKED`.
- `MultiCycleSessionSnapshot` containing intake anchor/deadline, configured ceilings, active cycle/token counts, admissions completed, and last admission time.
- Pure transition/evaluation helpers that tell the future operational owner whether it may admit a new exact two-token cycle, must continue servicing existing work, must drain, or is complete.

**Required behavior:**
- One session/campaign owns all cycles; no independent child campaign per admission.
- A new cycle cannot cancel/reset existing cycles.
- Released through-4h capacity can be reused while intake remains open.
- After intake deadline, no new cycle is permitted even if capacity is free.
- No automatic successor session/restart.
- No 12h/24h state or runtime is introduced in this implementation.
- No source I/O, DB writes, Scheduler execution, or financial side effects occur in the pure coordinator.

**TDD verification:** model a 24h intake timeline with three staggered cycles, capacity saturation, cycle completion/reuse, intake cutoff, and bounded drain. Confirm no single-token admission and no >6 active state is accepted.

---

### Task 4: Focused compatibility verification and implementation closeout

**Files:**
- Add: `docs/printer-v1-v2-9-8b-memory-throughput-capacity-scaling-implementation-closeout.md`

**Minimum sufficient verification:**
- Run the new focused test module.
- Run the existing two-token fairness tests unchanged.
- Run focused standard-four-hour capacity/policy tests that exercise `standard_four_hour_capacity_contract`.
- Run `git diff --check`.
- Confirm current public operational constants still report token capacity=2 / one current operational cycle unless a later proof/activation lane changes them.
- Confirm no migration, provider ceiling, retry, endpoint rotation, 12h/24h, retrieval, decision, paper-position, trade, audit, PnL, wallet, signing, or execution code changed.

**Closeout verdict on PASS:**
`V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_SCALING_IMPLEMENTATION_PASS_READY_FOR_FOUR_TOKEN_BOUNDED_PROOF`

The closeout must explicitly state that six is implemented capability, not proven/authorized runtime capacity, and the next permitted runtime step is the separately bounded 4-token / 2-cycle proof only.