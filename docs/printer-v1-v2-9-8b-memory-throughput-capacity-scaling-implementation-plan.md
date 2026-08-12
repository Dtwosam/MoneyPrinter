# Printer V1 V2-9.8B Memory Throughput Capacity Scaling Implementation Plan

> **For agentic workers:** implement this plan task-by-task with test-first changes and focused verification only.

**Goal:** Build the existing Memory Factory architecture once for a hard maximum of six concurrent through-4h tokens as three exact two-token cycles, while allowing a bounded 24-hour intake session to recycle that capacity across up to fifteen two-token admissions (30 new tokens maximum). Current public runtime capacity remains two until separate 4-token and then 6-token proofs pass.

**Architecture:** Preserve the existing two-token cycle, atomic pair admission, Central Scheduler, Source Governor, campaign ownership, and provider ceilings. Distinguish **simultaneous capacity** from **whole-session capacity**: at most three cycles / six tokens may be active through 4h at once, while one 24h intake session may admit at most fifteen two-token cycles total. Add a pure admission/session policy and a campaign-wide fairness wrapper that composes the existing two-token selector. Operational integration must reuse the existing campaign/run/cycle ownership and one-command lifecycle owners; no independent campaign process per cycle is allowed.

**Tech stack:** Python 3, dataclasses/enums, existing Printer scheduler contracts, existing two-token fairness policy, existing campaign ownership/persistence owners, unittest/pytest-compatible tests.

## Global constraints

- Solana-only, Solana-memecoin-only, paper-only V1 restrictions remain unchanged.
- No live wallet, keys, funds, signing, execution, paid API, scoring/ranking/confidence/weighted logic, embeddings/vectors.
- Source Governor and Central Scheduler remain mandatory owners.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- 12h/24h runtime, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked.
- Existing provider ceilings, automatic retries=0, and endpoint-rotation policy remain unchanged.
- Existing public operational token capacity remains 2 in this implementation lane.
- Compiled/design simultaneous maximum: 6 through-4h tokens / 3 active two-token cycles.
- Whole-session maximum for a 24h intake: 15 two-token cycle admissions / 30 new tokens.
- `CampaignCeilings.cycle_count` in a future operationally integrated 24h session must represent the **total session cycle ceiling**, not the simultaneous active-cycle ceiling.
- Proof sequence after implementation: configured 4 tokens / 2 active cycles first; only after PASS may 6 / 3 be exercised.
- New-cycle spacing minimum: 300 seconds.
- Fresh admission is pair-atomic: exactly two new tokens or no new cycle.
- Intake duration is admission duration; after the deadline or total-cycle ceiling the session enters bounded drain and admits nothing new.

---

### Task 1: Pure multi-cycle capacity and intake/drain policy

**Files:**
- Create: `src/printer_v1/operator_cli/multi_cycle_memory_growth.py`
- Test: `tests/test_v2_9_8b_memory_throughput_capacity_scaling.py`

**Produces:**
- `MAX_THROUGH_4H_TOKENS = 6`
- `MAX_ACTIVE_TWO_TOKEN_CYCLES = 3`
- `MAX_TOTAL_CYCLE_ADMISSIONS_PER_24H_SESSION = 15`
- `MAX_NEW_TOKENS_PER_24H_SESSION = 30`
- `TOKENS_PER_CYCLE = 2`
- `MIN_CYCLE_ADMISSION_SPACING_SECONDS = 300`
- `MultiCycleCapacityPolicy`
- `MultiCycleAdmissionState`
- `AdmissionDecision`
- `evaluate_cycle_admission(...)`
- `evaluate_session_phase(...)`
- `scaled_standard_four_hour_capacity_contract(...)`
- `scaled_session_capacity_contract(...)`

**Required behavior:**
- Accept simultaneous configurations 2/1, 4/2, or 6/3 only; reject odd, mismatched, zero, or >6 active configurations.
- Keep total session admission ceiling independent from active concurrency; it must cover the active-cycle ceiling and may not exceed 15 cycles in this implementation.
- Derive active and total-session 4h request/Scheduler envelopes from the canonical existing two-token standard-four-hour contract, never duplicate per-token numbers.
- Admit only when two token positions and one active-cycle position are available, total session admissions remain, intake remains open, >=300s has elapsed since the prior admission, and every explicit health/budget gate is true.
- Defer admission without affecting existing work when capacity, spacing, source, Scheduler, close reserve, DB, lease, discovery, or protected-work gate is unavailable.
- Enter `DRAIN` at/after the intake deadline **or when the total session cycle ceiling is consumed**; never admit another cycle afterward.
- Report `COMPLETE` only after intake is closed and zero accepted active through-4h cycles/tokens remain.
- Treat impossible state (negative counts, counts above configured ceiling, active cycles exceeding admitted cycles, active tokens without cycles, or admission count beyond total ceiling) as fail-closed invalid state.

**TDD verification:** focused tests cover 2/4/6 simultaneous configuration, 15-cycle/30-token whole-session ceiling, >6 active rejection, >15 total rejection, 12:00/12:05/12:10 admissions, no admission before five minutes, automatic pair-capacity reuse after a completed cycle, individual-token early failure without single-token refill, each health gate, intake deadline -> drain, total-cycle ceiling -> drain, and drain -> complete.

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
- Accept 1-3 **active** cycles only; every active cycle contains exactly two owned slots even when one token later becomes terminal/ineligible.
- Preserve the existing two-token selector inside each cycle rather than replacing it.
- Use one shared campaign ceiling and shared-stop set.
- Global priority: mandatory main-window close first (earliest deadline), then evidence-gap/safe-stop, then ordinary work.
- Ordinary work remains fair by the selected token's existing `ordinary_service_count`, then oldest creation time, then stable cycle ordinal/work id.
- A later cycle cannot starve an older cycle, and an older cycle cannot monopolize ordinary work.
- Token-local failure remains isolated through the existing selector.
- Shared DB/lease/integrity/campaign-budget failure blocks campaign-wide selection.
- No score/rank/confidence/weighted scheduling logic.

**TDD verification:** focused tests cover earliest close across cycles, safe-stop over ordinary across cycles, ordinary fairness across all six tokens, deterministic tie breaking, terminal/failed token exclusion, shared ceiling exhaustion, exactly-three-active-cycle acceptance, and fourth-active-cycle rejection.

---

### Task 3: Bounded session coordinator and ownership integration

**Files:**
- Extend: `src/printer_v1/operator_cli/multi_cycle_memory_growth.py`
- Use existing ownership/persistence helpers rather than introducing a parallel schema owner.
- Add only the smallest operational adapter needed after the pure policy tests are green.
- Extend focused tests with disposable/fixture-only state where necessary.

**Required behavior:**
- One session/campaign/run owns every admitted cycle; no child campaign per admission.
- `cycle_count` is a finite whole-session ceiling and may be 15 even though only 3 cycles may be active concurrently.
- New cycle identities/ordinals are monotonic and exact; completed cycles remain historical audit evidence and do not count as active concurrency.
- A new cycle cannot cancel/reset existing cycles.
- Released pair capacity can be reused while intake and total-cycle capacity remain open.
- After intake deadline or total-cycle exhaustion, no new cycle is permitted even if active capacity is free.
- No automatic successor session/restart.
- No 12h/24h state or runtime is introduced.
- Current public two-token command remains unchanged until the separate proof/activation lane.

**TDD verification:** model one 24h intake with three staggered active cycles, capacity saturation, repeated cycle completion/reuse beyond the first three cycle ordinals, a total of at most 15 admissions, intake cutoff, and bounded drain. Confirm no single-token admission, no fourth active cycle, no >6 active token state, and no six-token public activation.

---

### Task 4: Focused operational compatibility verification

Minimum sufficient verification before an implementation closeout:

- new focused scaling test module;
- existing two-token fairness tests unchanged;
- focused standard-four-hour policy/capacity tests or direct focused assertions that the canonical two-token contract remains `2 / 236 / 117 / 210`;
- focused campaign ownership/persistence tests if an ownership adapter is changed or added;
- `git diff --check`;
- static confirmation that current public operational constants still report token capacity=2 / current one-cycle mode;
- static confirmation that no migration, provider ceiling, retry, endpoint rotation, 12h/24h, retrieval, decision, paper-position, trade, audit, PnL, wallet, signing, or execution capability changed.

Do not run a broad suite unless focused failures indicate a broader architectural regression.

---

### Task 5: Implementation closeout

**File:**
- Add: `docs/printer-v1-v2-9-8b-memory-throughput-capacity-scaling-implementation-closeout.md`

**Closeout verdict on PASS:**
`V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_SCALING_IMPLEMENTATION_PASS_READY_FOR_FOUR_TOKEN_BOUNDED_PROOF`

The closeout must state all of the following exactly in substance:

- six is implemented capability, not proven/authorized runtime capacity;
- three is the simultaneous active-cycle maximum, not the whole-session cycle count;
- the bounded 24h session ceiling is at most 15 pair admissions / 30 new tokens;
- current public runtime remains two;
- no 12h/24h runtime was activated;
- the next permitted runtime step is the separately bounded 4-token / 2-active-cycle proof only;
- 6 / 3 cannot be exercised until 4 / 2 closes PASS.