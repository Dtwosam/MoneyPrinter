# Printer V1 — Four-Concurrent Overlapped Two-Cycle Feasibility Audit

Status: **CLOSED PASS**

Audit/readiness verdict:

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_FEASIBILITY_AUDIT_PASS`

This lane is documentation-only. It does not implement a repair, change
production code or tests, drain the surviving `WAITING` row, rerun Printer,
prepare an authorization, or mutate the authoritative database.

Requested product target (operator):

```text
Cycle 1 admits 2 tokens, then Cycle 2 should ideally admit another 2 tokens
roughly 5–10 minutes later, and both cycles should independently run
WINDOW_15M -> WINDOW_1H -> WINDOW_4H concurrently so their 4H memory
completes roughly 5–10 minutes apart.
```

Four-concurrent-token feasibility classification:

`NARROW_CAPACITY_AND_ADMISSION_CHANGE_FEASIBLE`

Cycle-2 fast-admission classification (confirmed, not reopened):

`COMMITTED_CODE_DEFECT` /
`LATER_CYCLE_PRE_LIFECYCLE_ACQUISITION_DEADLINE_ENFORCEMENT_DEFECT`

Recommended-approach regression risk:

`MEDIUM`

## Identity

- branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- audited starting HEAD: `13acfea5aa256b84baadb9206879eaa959a51a54`
- authoritative DB SHA-256 (read-only, unchanged):
  `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` remains
  `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`
- governing prior Cycle-2 liveness audit:
  `docs/printer-v1-v2-9-8b-cycle2-pre-lifecycle-admission-liveness-and-wait-ownership-audit.md`
- surviving wait (do not drain):
  `prelifecycle-refresh-wait:20260902T123958Z-5a3e78f1a7b8-campaign:20260902T123958Z-5a3e78f1a7b8-campaign-run:20260902T123958Z-5a3e78f1a7b8-cycle-2:1`

## 1. Authority gate

### A. Does CURRENT_HANDOFF permit this feasibility audit now?

Yes, as operator-requested **audit / readiness / feasibility documentation
only**.

At audit start, `CURRENT_HANDOFF.md` and the live source-stack current-lane
pointer named:

```text
LATER-CYCLE PRE-LIFECYCLE DEADLINE ENFORCEMENT AND WAIT OWNERSHIP — DESIGN / SPECIFICATION ONLY
```

That lane forbids implementation, wait drainage, application, consumption, and
Printer execution. It does not forbid a related read-only feasibility audit of
the product target that Cycle-2 liveness exists to serve.

This audit does **not** skip sequencing into implementation. It does **not**
adopt four concurrent lifecycle tokens. The previous deadline-enforcement
design remains required work and is absorbed into the next combined design
lane named below.

If this had been an implementation, application, wait-drainage, or envelope-
changing source-stack rewrite, it would have been
`FOUR_CONCURRENT_TOKEN_OVERLAP_FEASIBILITY_AUDIT_GOVERNANCE_BLOCKED`.

### B. Can this be audited without changing the active capability envelope?

Yes. This document records a contradiction and a feasibility map. It does not
redefine concurrent capacity. The 2026-08-26 source-stack wording remains the
live envelope until a later explicit adoption:

- two cycles;
- exactly two concurrently active token slots;
- up to four distinct identities campaign-wide;
- “four-token” does not currently mean four concurrent tokens;
- no 3/4 concurrent-token capacity is currently authorized.

### C. What exact governance / source-stack adoption is required before implementation?

Before any implementation of four concurrent lifecycle tokens, a later design
lane must include an explicit source-stack / capability-envelope adoption that
states all of the following and no more:

1. one campaign / one campaign-run / one authoritative factory run;
2. two cycles, each exactly two slots with ordinals `(1, 2)`;
3. up to **four concurrent through-4h lifecycle tokens** while both cycles are
   live (`2 cycles × 2 slots`);
4. Cycle 2 may overlap Cycle 1 through `WINDOW_15M → WINDOW_1H → WINDOW_4H`;
5. concurrent campaign-wide token ceiling becomes `4`; active-cycle ceiling
   remains `2`; no third cycle; no fifth token;
6. freeze rule remains `4 freeze-ready → 2 selected + 2 report-only`;
7. Cycle-2 identities remain campaign-history disjoint;
8. Source Governor and Central Scheduler remain sole owners;
9. no retry / rerun / resume / restart / successor / endpoint rotation;
10. `WINDOW_5M_MICRO_EVENT` remains support-only;
11. `WINDOW_12H` / `WINDOW_24H`, retrieval, and all financial capability remain
    locked;
12. Cycle-2 fast admission is a liveness/target, not permission to weaken
    evidence.

That adoption is **not** this audit.

## 2. Technical question

The existing architecture already supports **most** of the requested shape.

This is:

**A. mostly already implemented but blocked by later-cycle admission liveness,
wait ownership, and source-stack wording — not by missing lifecycle machinery.**

It is not a substantial redesign. It is also not “flip one constant from 2 to
4.” The operational composition already binds
`scaled_standard_four_hour_capacity_contract(4)`.

| Layer | Current fact |
|---|---|
| Operational policy | `configured_through_4h_tokens = 4`, `configured_active_cycles = 2`, `tokens_per_cycle = 2`, spacing `300s` |
| Source-stack wording | concurrent capacity remains exactly `2` |
| Cycle-2 acquisition | already starts ~300s after Cycle 1 while Cycle 1 is live |
| Cycle-2 admission | lawful while Cycle 1 tokens are still active (`four_token_proof_controller` requires it) |
| Cycle-2 lifecycle runner | same canonical factory loop and same `15m → 1h → 4h` planner |
| Why recent campaigns fail the product target | Cycle 2 is starved / parked, then wait/cleanup fail; not because a second runner is missing |

## 3. Exact active-slot law

Map:

```text
scaled_standard_four_hour_capacity_contract(4)
  -> four_token_operational_composition.exact_operational_policy()
  -> FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY
  -> FourTokenProofController.exact() / build_four_token_proof_policy()
  -> evaluate_cycle_admission / load_multi_cycle_campaign_snapshot
  -> _run_four_token_admission_boundary
  -> admit_two_token_cycle_from_attempt
  -> materialize + _plan_opening_jobs(cycle_ordinal=2)
  -> same factory loop / Central Scheduler claim path
  -> cycle-local 1h/4h continuation
  -> shared terminal / cleanup
```

### Guards

| Location | Current limit | If count becomes 3 or 4 | Safety vs policy |
|---|---|---|---|
| `multi_cycle_memory_growth.TOKENS_PER_CYCLE` | `2` per cycle | A third slot in one cycle fails closed | safety (pair-atomic contract) |
| `scaled_standard_four_hour_capacity_contract(4)` / `exact_operational_policy()` | `through_4h = 4`, `active_cycles = 2` | 3rd cycle / 5th token `DEFER` `active_cycle_capacity_full` or `through_4h_capacity_full` | policy/capacity |
| `evaluate_cycle_admission` | admits a second two-token cycle while 2 tokens are already active | 4 active is the configured ceiling; 5th deferred | policy |
| `four_token_proof_controller._first_cycle_state` | requires both Cycle-1 tokens still in active-through-4h states at Cycle-2 admission; `len(cycles) > 2` fails | overlap is required, not forbidden | policy + overlap contract |
| `_ACTIVE_THROUGH_4H_TOKEN_STATES` | `SELECTED` through `WINDOW_4H_CONTINUING` | `WINDOW_4H_CLOSED` releases capacity | safety (capacity accounting) |
| `create_cycle_with_two_slots` / slot ordinals | exactly `(1, 2)` | cannot represent 3 slots in one cycle | safety |
| `cycle_step_key` | `t{1,2}_…` for cycle 1; `t{1,2}_c0002_…` for cycle 2 | no `t3` namespace | safety (identity) |
| factory `expected_token_capacity` | `2` **per owned cycle** | 4 concurrent tokens remain 2+2 | safety (cycle-local) |
| `TWO_TOKEN_ACTIVE_SLOT_COUNT` | `2` per cycle | not a campaign-wide 2-token cap | safety (per-cycle) |
| `MAX_THROUGH_4H_TOKENS = 6` / `MAX_ACTIVE_TWO_TOKEN_CYCLES = 3` | compiled scaling max | operational 4/2/2 must not exercise 6 | policy (hard compiled cap) |
| `candidate_acquisition.approved_active_memory_capacity` | `2` | rejects manifests `!= 2` | **do not widen**; this is the deferred/legacy acquisition path, not the operational 4/2/2 owner |
| shared terminal / `campaign_active_work` | any `WAITING`/`CLAIMED` wait is active work | 4 live tokens add more jobs/waits to drain | safety (cleanup) |
| official `project_four_token_proof_zero_state` | omits wait table | four-token overlap does not fix this | committed gap |

Changing one profile constant from 2 → 4 is **not sufficient** and is **not
the remaining gap**. Operational `configured_through_4h_tokens` is already 4.

Additional required seams before the product target can be lawfully exercised:

1. source-stack / capability-envelope adoption (governance);
2. Cycle-2 pre-lifecycle deadline enforcement and factory re-entry (liveness);
3. parent-stop / official-zero-state wait ownership (cleanup);
4. optional later-cycle-only refresh-interval change if `<=10m` admission must
   remain possible after an insufficient first intake;
5. overlapping cadence/close contention proof (verification, not a scheduler
   rewrite).

## 4. Does Cycle 2 already have a complete independent lifecycle runner?

Yes. It is the **same** canonical factory runner, not a duplicate.

After `PAIR_READY` / `admit_two_token_cycle_from_attempt` /
`materialize_consumed_pre_admission_pair`:

```text
_plan_opening_jobs(..., cycle_ordinal=2, four_token_proof=True)
  -> cycle_step_key t1_c0002_snapshot_00 / t2_c0002_snapshot_00
  -> same pending-step factory loop
  -> resolve_owned_cycle_for_scheduler_job
  -> cycle-local ownership context (expected_token_capacity=2)
  -> same WINDOW_15M snapshots/close
  -> token-local continuation (evaluate_token_local_continuations, 2 slots)
  -> cycle-local WINDOW_1H then WINDOW_4H planning
     (operational_standard_4h loads by cycle_id;
      4h barrier is BOTH_OWNED_FIRST_HOUR_VERDICTS_TERMINAL for that cycle)
  -> shared terminal only after both cycles drain
```

| Concern | Finding |
|---|---|
| Same runner or duplicated? | Same `run_one_command_15m_factory` loop |
| Token-local lifecycle state? | Yes; slot `token_state` and window rows are slot/window scoped |
| Cycle-local IDs? | Yes; `cycle_id`, `token_slot_id`, `window_id` |
| Scheduler job identity isolation? | Yes; `printer_memory_factory_campaign_scheduler_work` stage-scoped owner + namespaced step keys |
| Factory-step identity isolation? | Yes; `cycle_token_usage_key` is `c{NNNN}:t{slot}` so later `t1/t2` streams never merge |
| Snapshot ownership isolation? | Yes; job → exactly one cycle/window owner |
| Terminalization isolation? | Cycle-local unstarted materialization failure exists; token-local continuation is per 2-slot cycle; shared terminal is campaign-wide |
| Source-request-scope isolation? | Later-cycle scope repair remains in the live path (`campaign_source_request_scope`); do not regress |
| Memory-write isolation? | Windows/episodes bind lifecycle/window identity; no second memory pipeline |

Proof (code + tests, not a live 4H overlap):

- `four_token_proof_integration.cycle_step_key` / `resolve_owned_cycle_for_scheduler_job`
- `tests/test_v2_9_8b_four_token_gate_h_integrated_disposable.py`
- `tests/test_v2_9_8b_four_token_gate_f_cycle_accounting.py`
- `tests/test_v2_9_8b_four_token_proof_integration.py` (`active_through_4h_peak: 4`)
- historical live Cycle-2 15M while Cycle 1 was in 1H (section 11)

## 5. Scheduler collision analysis

There is one Central Scheduler and one factory claim loop. No second scheduler
is required or permitted.

The live selector is `_select_next_pending_step` in
`one_command_15m_factory.py`: due jobs first, AGENTS resource-category order,
then token/pre-close fairness. It already sees every pending step in the one
factory run.

`select_multi_cycle_scheduler_work` exists in
`scheduler/multi_cycle_fairness.py` but is **not wired** into the canonical
factory loop (tests + scaling plan only). Do not treat wiring it as a
prerequisite. Design may later decide it is unnecessary if token-fairness
across four distinct `token_id`s is sufficient.

Cadence used for collision modeling (TRACK_FAST, the worst-case envelope):

| Window | Interval | Dirty-above gap | Close duration | Min snapshots |
|---|---|---|---|---|
| `WINDOW_15M` | 60s | 90s | 900s | 16 |
| `WINDOW_1H` | 120s | 180s | 2700s | 24 |
| `WINDOW_4H` | 180s | 225s | 10800s | 61 |

Offsets from Cycle-1 admission `T0`. Cycle-2 admission at `T0+5m / +7m / +10m`:

| Time | Cycle 1 | Cycle 2 | Due density (FAST) |
|---|---|---|---|
| `T0` | 15M starts | not admitted | 2 snaps / 60s |
| `T0+5–10m` | 15M | 15M starts | **4 snaps / 60s** (worst overlap) |
| `T0+15m` | 15M close → 1H | still 15M | mixed 60s + 120s |
| `T0+20–25m` | 1H | 15M close → 1H | 4 tokens at 120s after both 1H |
| `T0+60m` | 1H close → 4H | still 1H | mixed 180s + 120s |
| `T0+65–70m` | 4H | 1H close → 4H | 4 tokens at 180s |
| `T0+4h` | 4H close | 4H remaining ~5–10m | drain |
| `T0+4h5–10m` | terminal | 4H close | drain |

Worst collision points:

1. **Overlapping FAST 15M** (`T0+5m` to `T0+15m`): four 60s snapshot streams on
   one serial claim loop. If each snapshot+source unit is 10–20s, the last of
   four simultaneously due jobs can be 30–60s late against a 90s dirty-above
   gap. **Unproven. Tightest snapshot risk.**
2. **Serial close contention**: already proven on Aug-21 Cycle-2 15M closes
   (sibling wait ~16.9s; closing gaps 127.7s / 134.8s). Four overlapping
   closes can worsen this. This is a known serial-consumer reality, not a
   missing second scheduler.
3. **Cycle-2 acquisition vs Cycle-1 due snapshots**: already proven on
   `59fdefe7`. Persisted-refresh quantum `115s` vs remaining time to the next
   Cycle-1 1H snapshot (~90s) produced
   `LIFECYCLE_DEADLINE_PROTECTS_CADENCE` forever. This is the liveness seam,
   not a Scheduler identity collision.
4. **1H and 4H overlap**: 120s / 180s cadences are more comfortable than 15M
   FAST. Still serial. Not live-proven at four tokens.

Duplicate job identities: namespaced step keys prevent `t1_snapshot_00`
colliding across cycles. Lock contention: one factory lock-owner
`v2_4:{run_id}` claims one due job at a time; SQLite remains single-writer.
Campaign safe-stop: shared, not cycle-cloned. Scheduler runtime ceiling for
four-token operational policy is `444` rows (`2 × 222`); arithmetic covers two
full through-4h cycles.

## 6. Source Governor / request-budget analysis

Do not increase budgets.

Canonical two-token standard-4h contract:

- shared discovery `2`
- lifecycle request outer `238`
- per-token `118`
- scheduler outer `222`

Operational four-token scaled contract
(`scaled_standard_four_hour_capacity_contract(4)` /
`FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY`):

- shared discovery `4`
- lifecycle request outer `476`
- per-token `118` (unchanged)
- scheduler outer `444`
- retries `0`
- endpoint rotation `false`
- long windows `false`

Arithmetic: `476 = 2 × 238` and `444 = 2 × 222`. Campaign request and
Scheduler row ceilings are already sized for two overlapping through-4h
cycles.

Provider-specific live ceilings inspected:

- DexScreener pair rate: `300 / min` — campaign-ceiling class:
  **existing ceilings already sufficient**
- GeckoTerminal: `10 / min` — four FAST 15M tokens at 60s, if each snapshot
  plus close/context/acquisition also touches GT, is the tight real constraint.
  Class: **existing ceilings probably sufficient but unproven** at four
  overlapping FAST 15M tokens plus Cycle-2 acquisition. `59fdefe7` already
  observed one Cycle-2 GT rate-limit (`source_failure 401`, request `4567`)
  during two-token Cycle-1 overlap.
- Database write envelope: serial factory writer; no schema widening. Class:
  **probably sufficient but unproven** at four-token 15M burst.
- No-retry / no-rotation laws: preserved by the scaled contract. Do not change.

Classification overall:

**existing four-token policy ceilings already sufficient as campaign
arithmetic; provider GT 10/min and serial 15M close/snapshot latency remain
unproven at four concurrent FAST tokens.**

Do not raise Source Governor or provider ceilings in the later design.

## 7. Cycle-1 non-regression risk

Preferred solution must leave Cycle 1 unchanged wherever possible.

| Approach | Risk | Notes |
|---|---|---|
| **A. Confirm existing 4-through-4h capacity + fix Cycle-2 starvation** | **MEDIUM** | Capacity already 4. Remaining production work is later-cycle liveness, wait ownership, and optional later-cycle refresh interval. Lowest-code path. |
| B. Change coordinator/admission, leave runner | LOW for runner, unnecessary | Coordinator already admits a second cycle while Cycle 1 is active. |
| C. Change Central Scheduler | HIGH | Rewrite not required. Live selector already serializes four tokens. Optional later fairness wiring is a design choice, not a prerequisite. |
| D. Duplicate/create a second lifecycle runner | HIGH | Contradicts one-machine law. Cycle 2 already uses the same runner. |
| E. Other: later-cycle-only refresh interval + wait-table zero-state | MEDIUM | Profile-specific, not global, if technically confined to the later-cycle owner constructor. |

**Recommend A + the later-cycle-only parts of E.** Do not recommend a
scheduler rewrite. Do not recommend a second runner. Do not change Cycle-1
opening discovery, 15M/1H/4H cadence, freeze depth, or selection algorithm.

Cycle-1 regression seams if the later design is sloppy:

- factory-loop re-entry / sleep bounds (`_later_cycle_acquisition_deadline_conflict`)
- shared terminal / parent-interrupt cleanup
- official zero-state projection
- any global `DISCOVERY_REFRESH` interval change (avoid; keep later-cycle-only)

## 8. Cycle-2 ≤10-minute admission target

Confirmed from the closed liveness audit, not re-investigated as a new
defect:

- absolute 2400s deadline propagated correctly;
- enforcement failed;
- cooperative refresh became `WAITING`;
- 115s persisted-refresh quantum repeatedly lost to Cycle-1 deadlines;
- Cycle 2 starved;
- freeze-ready never reached 4.

Smallest repair so Cycle 2 continues acquisition while Cycle 1 is active:

1. cooperative wait insert must not return `WAITING` without claim/deadline
   check when `due` is already past;
2. factory loop must re-enter the later-cycle owner, and the 2400s
   acquisition deadline must be a wake bound rather than only an in-owner
   check;
3. later-cycle quanta must not be permanently skipped solely because a 115s
   worst-case persisted-refresh quantum does not fit the next Cycle-1
   snapshot gap. Design must keep Cycle-1 snapshot deadlines protected
   without parking Cycle 2 for the rest of 1H/4H.

Preserve: 4 freeze-ready minimum; 2 selected + 2 report-only;
campaign-history disjointness; Source Governor; Central Scheduler; no
scoring/ranking; no retries/rotation; no lowered evidence quality.

`<=10 minutes after Cycle-2 acquisition start` is an **operational target**,
not permission to weaken evidence. Historical successful Cycle-2 attempt
durations were ~11–13 minutes when acquisition actually ran. The Aug-21 live
admission was ~16.5 minutes after Cycle-1 start and occurred **after** Cycle-1
15M close. `59fdefe7` started Cycle-2 acquisition at Cycle-1 `T0+300s` but
never admitted.

## 9. Existing 600-second refresh issue

Four bounded opportunities exist: campaign-start intake, then `+600 / +1200 /
+1800`. Strict `due < deadline` keeps `+2400` outside the horizon.

Default interval is `next_check_interval_seconds(JobKind.DISCOVERY_REFRESH) =
600`, passed into `PreLifecycleTemporalRefreshOwner` unless overridden.

If initial freeze-ready supply is already 4, refresh is unnecessary and
`<=10m` depends only on liveness during the first intake.

If initial supply is **not** 4, the first extra opportunity is at exactly
`T_cycle2+600s`. Refresh work then still has to run, revalidate, freeze, and
admit. That makes `<=10m` admission after an insufficient first intake
**unrealistic** under the current interval.

Earlier refresh can be achieved **without** a global refresh change:

- `PreLifecycleTemporalRefreshOwner.__init__` already accepts
  `refresh_interval_seconds`;
- later-cycle construction can pass a four-token operational-profile value;
- Cycle 1 does not use this 2400s wait as its opening path;
- do not change `resource_governor.next_check_interval_seconds` globally;
- do not increase total source-call budget; fewer/earlier opportunities, not
  more budgeted calls.

Prefer a later-cycle / four-token-operational-profile interval over a global
`DISCOVERY_REFRESH` change. Exact earlier value is a **design** choice. This
audit does not pick `180s` vs `300s`.

## 10. Cleanup / zero-state implications

Existing defects remain and are **not repaired here**:

- `PRE_LIFECYCLE_TERMINAL_CLEANUP_ORDERING_OR_OWNERSHIP_DEFECT`
- `OFFICIAL_ZERO_STATE_OMITS_ACTIVE_PRE_LIFECYCLE_REFRESH_WAITS`

Four concurrent lifecycle tokens do not invent a new cleanup architecture, but
they add more objects that the same broken wait-ownership path must drain.

| Case | Implication |
|---|---|
| Parent-stop with both cycles active | Must terminalize both cycles’ jobs, windows, leases, **and** any Cycle-2 `WAITING`/`CLAIMED` refresh waits. `59fdefe7` cancelled the attempt/job and left the wait `WAITING`. Overlap makes this more likely, not less. |
| Token-local failure in Cycle 1 while Cycle 2 continues | Token-local continuation is cycle-scoped (2 slots). Cycle 2 should continue. Shared terminal must not collapse Cycle 2 because one Cycle-1 token failed. |
| Token-local failure in Cycle 2 while Cycle 1 continues | Symmetric. Cycle-local unstarted materialization isolation already exists. |
| Campaign terminalization | Shared; both cycles must be terminal before one cleanup. Incomplete Cycle-2 wait rows already fail this. |
| Active-work reporting | `campaign_active_work` already counts `WAITING`/`CLAIMED` waits. Official zero-state does not. Divergence remains. |
| Leases | One campaign lease. Do not add a second lease owner. |
| Wait rows | One later-cycle wait was enough to block shared terminal. Four-token overlap does not remove that. |
| Scheduler jobs | Cycle-namespaced; outer reconcile cancelled job `3548` without `terminalize_refresh_wait`. |

The later combined design must cover wait-row terminalization and official
zero-state projection. Do not drain the current `WAITING` row in design or
implementation until a separately approved repair/closeout says so.

## 11. Historical evidence

Do not infer from stale slot rows. Evidence below is from closed campaign
documentation.

### Live overlap that did happen

Consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436`, campaign
`20260821T160842Z-2d39af1663dd`:

- Cycle 1 admitted `16:08:43Z`
- Cycle 1 `WINDOW_15M` closed `16:24:24Z` / `16:24:35Z` and `WINDOW_1H` opened
- Cycle 2 admitted `16:25:08Z` (`…-cycle-2`, tokens 78/77)
- Cycle 2 first snapshots `16:25:13Z` / `16:25:15Z`
- Cycle 1 `WINDOW_1H` continued through Cycle 2’s lifetime until `17:09:45Z` /
  `17:09:52Z`

That is lawful-at-the-time **Cycle-1 1H + Cycle-2 15M overlap** under the then
4/2/2 operational authorization. Source:
`docs/printer-v1-v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit.md`.

Cycle 2 15M was dirtied by a later-classified `token_status` NULL / TRACK_FAST
mis-bind. Cycle 2 never reached 1H or 4H. Cycle 1 4H never materialized
(`SAFE_STOP_PREFLIGHT_FAILED` ~17ms after the second 1H close). Serial close
contention was measured on Cycle 2.

### Live overlap that did not happen

No closed durable campaign evidence was found in which:

- Cycle 1 was in `WINDOW_1H` or `WINDOW_4H`, **and**
- Cycle 2 had active `WINDOW_1H` or `WINDOW_4H` work at the same time.

Recent Standard-4H campaigns `ab6c68fe`, `12a7ea61`, and `59fdefe7` attempted
Cycle-2 acquisition while Cycle 1 was live and **did not admit** Cycle 2.

### Tests

Disposable/accounting tests assert `active_through_4h_peak = 4` and cycle-
namespaced jobs. They are not a live overlapping-4H proof.

**No clean live proof exists of overlapping 1H or overlapping 4H.** Overlapping
15M (Cycle 2) against Cycle-1 1H exists once historically and was not a clean
Cycle-2 15M close.

## 12. Required implementation-size estimate

Evidence-based, not line-count:

| Item | Estimate |
|---|---|
| Production files likely requiring changes | **5–8**: `pre_lifecycle_persistent_refresh_owner.py`, `one_command_15m_factory.py`, `authoritative_live_operational_campaign.py`, wait-row reconcile/unified terminal owner, `four_token_proof_zero_state_gate.py`, optionally `four_token_operational_composition.py` for a later-cycle refresh interval |
| Functions likely requiring changes | **~10–15**: `_request` / cooperative insert; `_later_cycle_acquisition_deadline_conflict` and factory re-entry; later-cycle quantum/wake; parent-interrupt wait terminalize; official zero-state query; optional later-cycle `refresh_interval_seconds` pass-through |
| Policy/profile constants | Operational through-4h is already `4`. Maybe one later-cycle-only refresh-interval constant. Do not change freeze depth, spacing floor `300s`, retries, or provider rates. |
| Schema/migration required? | **NO** |
| Scheduler rewrite required? | **NO** |
| Lifecycle runner rewrite required? | **NO** |
| Source Governor change required? | **NO** (do not raise ceilings) |
| Candidate-selection change required? | **NO** |
| Approximate focused new/updated tests | **18–25** covering the verification plan below |

## 13. Preferred minimal architecture

The requested architecture is exactly:

- one existing campaign;
- two cycles;
- two tokens each;
- up to four active lifecycle tokens;
- Cycle 2 begins ~5–10m after Cycle 1 when supply permits;
- same existing lifecycle runner;
- same Central Scheduler;
- same Source Governor;
- same `4 → 2 + 2` freeze rule;
- no new thread/process/scheduler;
- no global provider-policy change.

That architecture is **already the operational 4/2/2 code shape**
(`FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY` + canonical factory hook).

It is **technically safe to design** under these conditions:

- source-stack adoption first;
- Cycle-2 liveness repaired so acquisition is not parked;
- wait-row cleanup / official zero-state repaired;
- freeze/disjointness/evidence quality unchanged;
- overlapping FAST 15M and serial close contention are proven with frozen
  transport before any live campaign.

It is **not currently authorized**. It is **not live-proven through 4H
overlap**. GeckoTerminal `10/min` and 15M FAST dirty-above `90s` are the
honest residual hazards.

## 14. Required verification plan

Minimum sufficient bounded proof before implementation closeout. Prefer
deterministic frozen/fake transport. Do not run live providers.

- Cycle-1 baseline non-regression (2-token 15M→1H→4H path unchanged)
- Cycle-2 acquisition liveness (deadline fires or refresh claims; no silent
  park past 2400s)
- four-active-token maximum
- no fifth token / no third cycle admission
- overlapping 15M lifecycle
- overlapping 1H lifecycle
- overlapping 4H lifecycle
- exact Scheduler collision behavior (including serial close)
- Source Governor ceilings not exceeded; GT 10/min not implicitly raised
- token-local failure isolation (Cycle 1 fail / Cycle 2 continue and reverse)
- parent safe-stop with both cycles live
- cleanup zero-state **including** refresh waits
- duplicate transport guard
- source-request-scope repair preserved
- DB integrity / FK
- no 12h/24h/retrieval/financial capability

## 15. Classifications

### Four-concurrent-token feasibility

`NARROW_CAPACITY_AND_ADMISSION_CHANGE_FEASIBLE`

Not `MAJOR_ARCHITECTURE_CHANGE_REQUIRED`. Not `GOVERNANCE_BLOCKED` for this
audit. Implementation remains governance-blocked until the design lane
includes source-stack adoption.

### Cycle-2 fast admission

Confirmed:

`COMMITTED_CODE_DEFECT` /
`LATER_CYCLE_PRE_LIFECYCLE_ACQUISITION_DEADLINE_ENFORCEMENT_DEFECT`

Minimal liveness seam:

`pre_lifecycle_persistent_refresh_owner._request` cooperative insert-without-
claim when due is past, plus
`one_command_15m_factory._later_cycle_acquisition_deadline_conflict` /
factory-loop re-entry so the 2400s deadline and due refresh are actually
consumed while Cycle 1 lifecycle is running.

### Regression risk

Recommended approach **A + later-cycle-only E**: `MEDIUM`

Evidence: Cycle-1 runner/cadence/selection untouched if the repair is confined
to later-cycle wait/re-entry/refresh-interval and shared cleanup. Factory-loop
sleep/wake and shared terminal are the residual Cycle-1 contact surfaces.

## 16. Exact next permitted lane

```text
FOUR-CONCURRENT OVERLAPPED TWO-CYCLE CAPACITY + CYCLE-2 FAST ADMISSION — DESIGN / SPECIFICATION
```

That design must include explicit source-stack / capability-envelope adoption
before implementation. It absorbs, and does not skip, the previous
later-cycle deadline-enforcement and wait-ownership design.

Do not implement. Do not drain the surviving wait. Do not prepare another
authorization. Do not rerun `59fdefe7`.

## Verdicts in one place

| Question | Finding |
|---|---|
| Authority / handoff | Operator-requested read-only audit permitted; implementation still blocked |
| Envelope | Four concurrent lifecycle tokens violate the live 2026-08-26 wording; operational constants already say 4 |
| Cycle-2 runner | Already the same canonical lifecycle runner |
| Technical overlap | Yes, after Cycle-2 admission; currently starved before admission |
| Scheduler | One serial factory loop can service four tokens; 15M FAST overlap unproven; no rewrite |
| Budget | Campaign 476/444 already 2× two-token; GT 10/min unproven |
| Historical 1H/4H overlap | No clean proof; one historical Cycle-2 15M during Cycle-1 1H |
| Schema | No |
| Scheduler rewrite | No |
| Source Governor change | No |
| Cycle-1 regression | MEDIUM for the recommended later-cycle-only repair |
| `<=10m` Cycle-2 admission | Not under +600s when first intake is short; liveness first; optional later-cycle interval in design |

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_FEASIBILITY_AUDIT_PASS`
