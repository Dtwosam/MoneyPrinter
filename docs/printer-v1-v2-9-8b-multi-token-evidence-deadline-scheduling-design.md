# V2-9.8B Design Lane 2 — Multi-Token Evidence-Deadline Scheduling

**Document status:** `DESIGN`  
**Date:** 2026-08-22  
**Starting HEAD:** `012eacd785c950367a550259d83e09957906dffe`  
**Governing forensic audit:** `docs/printer-v1-v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit.md`  
**Prerequisite Lane 1 closeout:** `docs/printer-v1-v2-9-8b-cadence-authority-lane1-closeout.md`  
**Verdict:** `V2_9_8B_MULTI_TOKEN_EVIDENCE_DEADLINE_SCHEDULING_DESIGN_PASS_READY_FOR_IMPLEMENTATION`

---

## 0. Scope and hard locks

This lane is **design only**.

It may not:

- implement code, migrations, or runners;
- run Printer / Source Governor / Central Scheduler;
- create, reuse, or apply authorization;
- begin Design Lane 3 (post-1H → 4H progression);
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
  live execution, wallets/private keys, paid APIs, scoring/ranking/confidence/
  weighted logic, embeddings/vectors, or `WINDOW_12H` / `WINDOW_24H`;
- loosen Lane-1 cadence authority;
- raise cadence dirty/block thresholds merely to hide contention;
- attribute the proven defect to GoPlus/provider timeout without current proof
  (the consumed 4/2/2 run had zero source failures and complete GoPlus).

Preserve:

- Source Governor as source authority;
- Central Scheduler as execution authority;
- exact token/pair/run/cycle/window identity;
- dirty-memory honesty;
- safe shutdown and no automatic restart after terminal failure;
- `WINDOW_5M_MICRO_EVENT` support-only;
- bounded campaigns and existing campaign ceilings.

---

## 1. Proven problem statement

The consumed four-token 4/2/2 campaign proved a **scheduling / resource-contention
defect separate from Lane 1**.

Lane 1 closed the false `TRACK_FAST` cadence-authority bind. Under correct
`TRACK_NORMAL` policy, the measured Cycle-2 closing gaps (~127.7s / ~134.8s) alone
were not dirty. They remain a proven systemic contention hazard:

| Fact | Evidence |
| --- | --- |
| Sibling closes clustered near the same due time | Cycle2 close jobs 2484 / 2492 |
| Close execution was effectively serial | job 2492 waited ~16.9s behind sibling |
| Closing observation timestamp is close-path capture time | Surface F forensic table |
| Preclose context + close/audit work inflate final inter-snapshot gap | `_execute_close` order |
| Defect recurs with two due tokens and worsens with Cycle3+/future work | forensic Surface O |
| Provider timeout was not causal | source failures = 0; GoPlus COMPLETE |

Root statement:

> One token’s close/context/audit path can monopolize the single factory
> execution loop long enough that another token’s lawful closing evidence is
> captured late. The architecture lacks deadline-protecting multi-token
> dispatch for evidence work.

Do **not** “fix” this by raising the 120s / 180s cadence thresholds.

---

## 2. Current scheduler / close-path execution map

### 2.1 Owners inspected

| Owner | Path | Role |
| --- | --- | --- |
| Factory execution loop | `operator_cli/one_command_15m_factory.py` (`run_one_command_15m_factory`) | Single-threaded select → claim → execute |
| Step selection | `_select_next_pending_step` | FIFO `scheduled_for,id` for 15m/1h; special close-preferring fairness only for owned `WINDOW_4H` |
| Job claim | `scheduler/_scheduler_base.py` (`claim_due_job`, `list_due_jobs`, `select_next_jobs`) | Canonical job lock/status |
| Job kinds / priority | `scheduler/contracts.py`, `scheduler/resource_governor.py` | Categorical `JobKind` priority; age bump; not score-based |
| Pure fairness policy (unwired) | `scheduler/two_token_fairness.py`, `scheduler/multi_cycle_fairness.py` | Deadline/intent categorical selection; tested, **not production-wired** |
| Campaign ownership | `operator_cli/campaign_ownership.py` + mig 050 work table | `work_intent`, `deadline_at`, stage/scope identity |
| Close pipeline | `_execute_close` / `_execute_continuation_close` / `_execute_long_4h_step` | Preclose context → closing snapshot → E2O → E2Q → Lane Q/K/E2Z |
| Preclose context | `_collect_preclose_context` | Serial governed source calls (CoinGecko, GoPlus, Solana RPC, Jupiter, holders…) |
| Cadence authority (Lane 1) | `operator_cli/cadence_authority.py`, `snapshots/cadence_policy.py` | FAST/NORMAL dirty/block boundaries |
| Source Governor | `sources/governor.py`, `sources/governed_execution.py` | Allow/deny/rate-limit; fail closed |
| Active-work accounting | `operator_cli/campaign_active_work.py` | Read-only job/work inventory |
| Safe stop / ceilings | factory budget enforcement + fairness ceiling vocabulary | Bounded campaign stop |

### 2.2 Production dispatch shape (current)

```text
while campaign running:
  pending = _select_next_pending_step(...)   # mostly earliest scheduled_for
  sleep until due
  claim_due_job(pending.scheduler_job_id)
  if WINDOW_CLOSE / CONTINUATION_CLOSE / LONG_CONTINUATION_CLOSE:
      _collect_preclose_context(...)        # many source ops, wall-time heavy
      _execute_snapshot(...)                # closing observation timestamp HERE
      close / audit / E2Z pipeline          # more wall-time
  else:
      _execute_snapshot(...)
  complete / fail job
  # only then may sibling due work be claimed
```

Implications:

1. The factory loop is one cooperative serial worker under Central Scheduler
   claim semantics — not an independent engine loop, but also not
   deadline-aware across tokens.
2. Pure fairness modules already encode the right categorical model, but
   production selection does not call them.
3. `printer_memory_factory_campaign_scheduler_work.deadline_at` exists and is
   required, but current 15m projection sets `deadline_at = scheduled_for`.
4. `work_intent` is currently stage-descriptive (`WINDOW_15M_WINDOW_CLOSE`),
   not the fairness vocabulary (`MAIN_WINDOW_CLOSE` / `EVIDENCE_GAP` /
   `SAFE_STOP` / `ORDINARY`).

### 2.3 Global JobKind order (preserved, not a hidden score)

`JOB_PRIORITY_ORDER` already matches AGENTS resource priority for token-level
work: paper monitor → exit risk → FAST tracks → NORMAL tracks →
`MEMORY_WINDOW_CLOSE` → safety/liquidity → discovery → broad context → backup.

Lane 2 does **not** invent numeric confidence scores. It adds categorical
**protection classes** and deadline-aware selection inside that order.

---

## 3. Exact contention points

| ID | Contention point | Mechanism | Effect |
| --- | --- | --- | --- |
| C1 | Serial sibling close admission | One RUNNING close blocks next claim | Sibling closing snap waits |
| C2 | Preclose-before-capture ordering | Context collection precedes closing snapshot | Capture time drifts past due |
| C3 | Close audit/E2Z on same path as capture | Heavy bookkeeping shares worker with evidence | Other tokens’ cadence work starves |
| C4 | Cross-cycle overlap | Cycle1 WINDOW_1H concurrent with Cycle2 WINDOW_15M | Shared worker / source budget |
| C5 | FIFO selection for 15m/1h | Earliest `scheduled_for` only; no token fairness | One token can stay preferred by accident of schedule/id |
| C6 | Unwired fairness policy | `two_token_fairness` / `multi_cycle_fairness` unused in factory | Existing design intent not enforced |
| C7 | Future workloads | Retrieval / paper monitor / Cycle3+ | Same serial slot becomes undefined contention |

C2 + C1 are the proven Cycle-2 gap producers. C3–C7 are the structural reasons
Lane 2 must be generic enough for Cycle 3+ and later unlocked scheduler users.

---

## 4. Canonical deadline model

Never conflate these clocks. Each has one owner and one honesty rule.

| Clock | Canonical owner | Meaning | Honesty if missed |
| --- | --- | --- | --- |
| **Scheduled cadence target** | Cadence planner + `printer_scheduler_jobs.scheduled_for` / run-step `scheduled_for` | Nominal time the step should become due | Lateness measurable; not itself dirty |
| **Admissible lateness / dirty boundary** | `SnapshotCadencePolicy.dirty_above_gap_seconds` (+ Lane-1 lane authority) | Gap above this dirties coverage | DIRTY / do_not_train; never fabricate fill |
| **Hard evidence deadline** | Campaign scheduler-work `deadline_at` (semantic owner) derived from window end + `closing_clean_late_seconds` / policy close lateness | Latest lawful time for the **closing evidence capture** (or gap-fill evidence) to complete | Miss → dirty/blocked per cadence policy; report `MISSED_EVIDENCE_DEADLINE` |
| **Source-operation timeout** | Adapter / transport `timeout_seconds` | One provider call wall budget | Partial/failed/unknown evidence; no invent |
| **Scheduler execution deadline** | Optional per-step wall budget after claim (new explicit bound) | Max time one claimed step may hold the worker before cooperative yield/fail-closed | Exceed → fail/skip step with typed cause; never silent hang |
| **Window-close deadline** | Window `window_end_at` / campaign window close plan | When the window must close/evaluate | Close may complete after capture; evaluation uses real capture times |

### Binding rules

1. **Hard evidence deadline ≠ source timeout.** A slow GoPlus call may miss a
   source timeout without being allowed to consume another token’s evidence
   deadline.
2. **Hard evidence deadline ≠ dirty boundary.** Dirty boundary evaluates gaps
   after the fact; hard evidence deadline is the dispatch protection target.
3. **`scheduled_for` remains the due/fire time.** `deadline_at` must become a
   **distinct** later bound for evidence-critical work (today they are wrongly
   equal for 15m projections).
4. **Window-close bookkeeping may finish after the evidence deadline** if the
   closing snapshot was already captured on time. Audit latency must not rewrite
   capture time.
5. Provider failure remains honest missing/partial/dirty/blocked evidence.

### Default hard-evidence deadline derivation (deterministic)

For forced closing evidence:

```text
deadline_at = window_end_at + closing_clean_late_seconds
```

using the Lane-1-resolved cadence policy for that exact token/window/lane.
For ordinary cadence snapshots, `deadline_at` may equal
`scheduled_for + dirty_above_gap_seconds` only as a dispatch urgency bound; the
cadence evaluator remains authoritative for memory quality.

---

## 5. Deterministic fairness / dispatch model

### 5.1 Chosen architecture

**Central-Scheduler Deadline-Phased Fair Dispatch**

Narrowest change that preserves existing owners:

1. Keep one Central Scheduler–led worker loop (no bypass engine).
2. **Phase-split** close work into separate claimable scheduler steps so
   evidence capture can interleave across tokens.
3. **Wire** the existing pure fairness selectors (or an equivalent factory-side
   adapter that reuses their categorical keys) into `_select_next_pending_step`
   for all active window lifecycle work, not only `WINDOW_4H`.
4. Introduce an explicit categorical **protection class** so future locked
   workloads join without fighting an undefined global slot.

This is not ranking, scoring, confidence, or weighted decision logic. Selection
keys are categorical then deterministic tie-breakers.

### 5.2 Protection classes (categorical, fixed order)

| Order | Protection class | Examples | Notes |
| --- | --- | --- | --- |
| 0 | `SAFE_STOP_CRITICAL` | shared lease/integrity/budget safe-stop | Always first |
| 1 | `EVIDENCE_DEADLINE_CRITICAL` | closing evidence capture; due gap-fill before dirty/hard deadline | Protected evidence contract |
| 2 | `CADENCE_ORDINARY` | on-cadence snapshots not yet deadline-critical | Round-robin by token service count |
| 3 | `CLOSE_SUPPORT_CONTEXT` | preclose/supporting evidence after capture | Yields to class 0–1 |
| 4 | `WINDOW_BOOKKEEPING` | E2O/E2Q/Lane Q/K/E2Z / ledger attach | Yields to class 0–2 |
| 5 | `DISCOVERY_ADMISSION` | later-cycle admission quanta | Must not starve class 1 |
| 6 | `BROAD_CONTEXT` | market regime / chain heat | Existing delay-under-pressure rule |
| 7 | `FUTURE_RETRIEVAL_EVAL` | locked | Schema-ready only; inactive |
| 8 | `FUTURE_PAPER_MONITOR` | locked (`OPEN_PAPER_TRADE_MONITOR` already exists as JobKind) | Inactive until explicit lane |

Cadence-critical evidence acquisition retains an **explicit protected contract**
(class 1). It must never depend on accidental FIFO task order.

### 5.3 Within-class deterministic keys

Reuse / adapt `two_token_fairness` / `multi_cycle_fairness` keys:

For `EVIDENCE_DEADLINE_CRITICAL`:

```text
(protection_class,
 earliest deadline_at,
 scheduled_for,
 created_at,
 cycle_ordinal,      # tie-break only; never permanent priority
 slot_ordinal,
 scheduler_work_id / step id)
```

For ordinary classes:

```text
(protection_class,
 token_ordinary_service_count,   # fewer served first
 scheduled_for / created_at,
 cycle_ordinal,
 slot_ordinal,
 id)
```

### 5.4 Cycle fairness

- Cycle 1 must not permanently outrank Cycle 2; Cycle 2 must not permanently
  outrank Cycle 3.
- `cycle_ordinal` is a **tie-breaker and dependency/readiness key only**.
- Semantic dependencies remain: a token’s continuation window cannot run before
  its predecessor close/admission readiness; that is readiness, not priority.
- Cross-cycle selection uses `select_multi_cycle_scheduler_work` composition:
  each cycle proposes its local next item; campaign picks by categorical key
  above, not by “older cycle wins.”

### 5.5 Anti-monopoly rules (no scores)

A single token, queue, cycle, window, source call, or close operation must not
hold the worker across another token’s due evidence deadline when class-1 work
is claimable.

Concrete rules:

1. After completing any non-class-1 step, re-enter selection before starting
   another non-class-1 step for the same token if any class-1 work is due.
2. A claimed class-3/4 step has a bounded scheduler execution deadline; on
   exceed, fail closed with `SCHEDULER_EXECUTION_DEADLINE_EXCEEDED` for that
   step only (token-local), then reselect.
3. One source call cannot extend into another token’s evidence deadline by
   chaining unbounded retries (existing no-auto-restart / cooldown law).
4. No automatic capacity increase.

---

## 6. Token / window isolation model

| Boundary | Isolation rule |
| --- | --- |
| Snapshot acquisition | Per exact token/pair/window step; sibling capture must be independently claimable |
| Supporting evidence | Per token; failure/slowness is token-local unless shared Source Governor budget is exhausted (campaign-visible) |
| Main-window audit/close bookkeeping | Per window after that window’s closing evidence exists; must not block sibling capture |
| Continuation admission | Depends on predecessor window terminal truth for **that** token only |
| Campaign cycle progression | Cycle admission quanta are class 5; they yield to class 0–1 across all cycles |

Preserve exact identities on every step and ownership row:

`campaign_id / run_id / cycle_id / token_slot_id / window_id / factory_run_id / scheduler_job_id / scheduler_work_id`.

Token-local failure excludes that token’s ordinary work; it must not cancel
unrelated tokens except via shared stop reasons already defined
(`SHARED_DB_FAILURE`, `SHARED_LEASE_FAILURE`, `SHARED_INTEGRITY_FAILURE`,
`CAMPAIGN_BUDGET_FAILURE`).

---

## 7. Close-path contention repair (phase split)

### 7.1 Current close atomic blob

Today one `WINDOW_CLOSE` (and analogues) performs:

1. `_collect_preclose_context` (source-heavy)
2. closing `_execute_snapshot` (evidence timestamp)
3. ledger attach / context persist
4. E2O close
5. E2Q audit
6. Lane Q / Lane K / E2Z

Steps 1 and 4–6 are occupying the same claim as step 2.

### 7.2 Lawful separation under Central Scheduler

Replace the single close blob with **three claimable phases** (same JobKind
family `MEMORY_WINDOW_CLOSE` or explicit sub step_kinds), all still enqueued /
claimed / completed through Central Scheduler:

| Phase step_kind | Protection class | Must finish by | May yield |
| --- | --- | --- | --- |
| `WINDOW_CLOSE_EVIDENCE` (and 1h/4h analogues) | `EVIDENCE_DEADLINE_CRITICAL` | hard evidence deadline | No (short; snapshot only) |
| `WINDOW_CLOSE_CONTEXT` | `CLOSE_SUPPORT_CONTEXT` | best-effort before audit; never rewrite capture time | Yes, to class 0–1 |
| `WINDOW_CLOSE_AUDIT` | `WINDOW_BOOKKEEPING` | bounded execution deadline | Yes, to class 0–2 |

Ordering constraints:

1. Evidence phase requires window collecting + due close schedule.
2. Context phase may start before evidence only if it cannot push evidence past
   deadline; **default implementation rule:** schedule context **after**
   evidence for that window (reorder vs today’s preclose-before-capture).
3. Audit phase requires persisted closing snapshot identity for that window.
4. No phase may create an independent API loop or bypass Source Governor.

This is the primary structural fix for C1–C3.

Continuation windows (`CONTINUATION_CLOSE`, `LONG_CONTINUATION_CLOSE`) use the
same three-phase pattern with stage-specific names.

---

## 8. Source Governor interaction

Central Scheduler fairness **never** bypasses Source Governor.

| Situation | Required behavior |
| --- | --- |
| Deadline-sensitive work, source budget exhausted | Do not fetch; mark evidence missing/stale/blocked; report `SOURCE_BUDGET_EXHAUSTED_BEFORE_EVIDENCE_DEADLINE` |
| Source operation slow | Bound by source-operation timeout; on timeout, partial/fail closed; do not extend retries into sibling deadlines |
| Provider partial/unknown/failure | Persist honest status; dirty/blocked as policy requires; never fabricate |
| Multiple tokens want same constrained source | Deterministic grant order: class 1 due earliest deadline first; then class 2 round-robin; denied tokens remain honest missing |

Source Governor remains the allow/deny authority (`can_request_source` /
`execute_source_request_with_governor`). Scheduler only decides **which owned
step** may attempt a governed request next.

---

## 9. Capacity / backpressure

When admitted work exceeds available scheduler capacity:

| Property | Rule |
| --- | --- |
| Deterministic | Same input state → same next selection / block reason |
| Observable | Emit saturation signals (below) |
| Bounded | Existing campaign ceilings + finite pending queues; no unbounded growth |
| Fail closed | Exhausted ceiling → blocked/safe-stop with typed reason; no silent drop that looks like success |
| No silent starvation | If class-1 work misses deadline while worker was busy on lower class, report `STARVED_BY_LOWER_CLASS_WORK` or `STARVED_BY_SIBLING_CLOSE` |
| No automatic capacity increase | Operator/design lanes only |

Required reports when Printer cannot service all lawful deadlines:

- `scheduler_saturation=true`
- `missed_evidence_deadlines=[...]` with exact token/window/cycle ids
- `blocked_reason` per affected window
- queue depth by protection class
- campaign acceptance remains honest (`BLOCKED_UNSAFE` / dirty/blocked memory as earned)

Reuse existing ceiling vocabulary where applicable:

`scheduler_work_ceiling_exhausted`, `source_request_ceiling_exhausted`,
`storage_growth_ceiling_exhausted`, `failure_ceiling_exhausted`.

---

## 10. Cycle-3+ and future-workload compatibility

Known future / adjacent scheduler consumers from the active build order:

- additional two-token cycles up to compiled max (`MAX_ACTIVE_TWO_TOKEN_CYCLES = 3`);
- longer approved windows (1h/4h already; 12h/24h locked);
- retrieval evaluation (locked);
- paper decision / monitor / audit work (locked).

Compatibility contract:

1. Every future consumer must declare a **protection class** before it can be
   selected.
2. Class 1 (`EVIDENCE_DEADLINE_CRITICAL`) remains reserved for cadence/close
   evidence capture until an explicit later lane redefines it.
3. Locked classes 7–8 may exist in the enum/docs/tests as inactive; runtime
   must reject enqueue/selection while locked.
4. Multi-cycle fairness composition already caps active cycles; Lane 2 must not
   invent a fourth-cycle path here.
5. Retrieval/paper work, when eventually unlocked, joins as class 7/8 (or a
   later approved class) and must yield to class 1 evidence deadlines.

---

## 11. Required schema / API / code changes (design only; do not implement)

### 11.1 Prefer existing owners

Minimum change set:

1. **Factory selection** — replace 15m/1h FIFO path in
   `_select_next_pending_step` with deadline-phased categorical selection
   (adapter over `two_token_fairness` / `multi_cycle_fairness` keys).
2. **Close phase split** — plan/enqueue three phase steps instead of one close
   blob; adjust `_execute_close` family to phase runners.
3. **Deadline semantics** — when projecting campaign scheduler work, set
   distinct `deadline_at` for evidence-critical phases (stop equating it to
   `scheduled_for`).
4. **Protection-class mapping** — derive class from `step_kind` (+ optional
   stored class); do not require rewriting immutable historical `work_intent`
   strings.
5. **Observability** — emit structured per-step timing fields into existing
   supervision/observer / final report surfaces.

### 11.2 Schema / migration impact

| Change | Required? | Notes |
| --- | --- | --- |
| New table | **No** (preferred) | Use existing jobs, run_steps, campaign_scheduler_work |
| New step_kind values | **Yes** (code/contract) | `WINDOW_CLOSE_EVIDENCE` / `_CONTEXT` / `_AUDIT` (+ 1h/4h analogues) |
| Distinct `deadline_at` semantics | **Yes** (behavioral) | Column already exists (mig 032/050) |
| `protection_class` column | **Optional thin migration** | Only if derivation from step_kind is judged insufficient for reporting/replay; otherwise derive |
| Observability columns on work/steps (`dispatched_at`, `scheduler_wait_ms`, `source_wait_ms`, `evidence_captured_at`, `missed_deadline_reason`) | **Optional thin migration** or report-JSON-only | Prefer report/observer first; migrate only if durable query is required for closeout proof |
| `printer_scheduler_jobs` new deadline column | **No** | Keep deadline on campaign ownership work row; job keeps `scheduled_for` |
| Fairness module API | **Minor** | Map factory rows → `SchedulerWorkItem`; possibly extend intent mapping helper |

No BUY/retrieval/12h/24h schema unlocks. No scoring columns.

### 11.3 Intent mapping (no hidden priority score)

Because current `work_intent` values are stage-descriptive and historically
immutable, selection must **derive** fairness intent/protection class:

| step_kind / phase | Derived fairness intent | Protection class |
| --- | --- | --- |
| `*_CLOSE_EVIDENCE` | `MAIN_WINDOW_CLOSE` | `EVIDENCE_DEADLINE_CRITICAL` |
| due cadence snapshot near/past dirty bound | `EVIDENCE_GAP` | `EVIDENCE_DEADLINE_CRITICAL` |
| safe-stop / shared integrity | `SAFE_STOP` | `SAFE_STOP_CRITICAL` |
| ordinary snapshot | `ORDINARY` | `CADENCE_ORDINARY` |
| `*_CLOSE_CONTEXT` | `ORDINARY` (or dedicated support intent if added) | `CLOSE_SUPPORT_CONTEXT` |
| `*_CLOSE_AUDIT` | `ORDINARY` | `WINDOW_BOOKKEEPING` |

New rows may optionally persist the derived class for observability; old rows
remain valid via derivation.

---

## 12. Migration plan (if optional columns are approved)

Only if implementation chooses durable observability/protection_class columns:

1. Forward-only migration after Lane-2 implementation approval.
2. Additive columns with NULL allowed for historical rows.
3. No rewrite of historical `work_intent` / `deadline_at` values.
4. Triggers preserve immutability of identity fields already protected by mig
   047/050.
5. Disposable rehearsal before any authoritative apply.
6. Rollback = do not apply; code remains backward compatible by deriving class
   from step_kind when column NULL.

If report/observer-only observability suffices, **skip migration**.

---

## 13. Implementation sequence (future; not this lane)

1. **Contract freeze** — protection classes, phase step_kinds, deadline
   derivation helper, intent/class mapping table (this design).
2. **Selection wiring** — factory `_select_next_pending_step` adapter to
   fairness keys for all window stages; keep 4h special-case behavior as a
   subset, not a fork.
3. **Close phase split** — plan evidence/context/audit steps; implement phase
   executors; ensure capture precedes context by default.
4. **Deadline projection** — distinct `deadline_at` for evidence phases.
5. **Source Governor yield rules** — deadline-sensitive deny/report paths.
6. **Observability** — observer + final-report fields.
7. **Bounded disposable proof** — matrix below.
8. **Independent closeout** — then Lane 3 design remains next per forensic
   sequence (not started here).

Suggested implementation slices:

| Slice | Content | Risk |
| --- | --- | --- |
| S1 | Mapping helpers + selection wiring (no phase split yet) | Medium |
| S2 | Close evidence/context/audit phase split + reorder | High |
| S3 | Distinct deadline_at projection + miss reporting | Medium |
| S4 | Observability + saturation signals | Low |
| S5 | Optional migration if S4 needs durable columns | Low |

---

## 14. Bounded proof matrix

Disposable / fixture only. No live authorization. No authoritative campaign.

| Proof ID | Scenario | Expect |
| --- | --- | --- |
| P1 | Two sibling tokens with simultaneous due closes | Both evidence phases claim/complete before either audit phase starts (or before sibling evidence deadline miss) |
| P2 | Token A context/audit slow; Token B evidence due | B evidence selected next; A does not monopolize |
| P3 | Correct TRACK_NORMAL cadence after Lane 1 | Closing gaps do not exceed dirty band solely due to sibling serialization |
| P4 | Source budget exhausted during class-1 work | Honest miss/block; no fabricated evidence; typed reason |
| P5 | Provider timeout on context phase after timely capture | Capture remains on-time; context partial/failed; audit sees honest context |
| P6 | Cycle1 WINDOW_1H + Cycle2 WINDOW_15M overlap | No permanent Cycle1 priority; class-1 15m evidence still protected |
| P7 | Ordinary service round-robin with two tokens | Service counts converge; no silent starvation |
| P8 | Ceiling exhaustion | Blocked with ceiling reason; no auto capacity bump |
| P9 | Locked future class enqueue attempt | Rejected/fail closed |
| P10 | Safe shutdown mid-phase | No orphan RUNNING; active work drains; no auto-restart |
| P11 | Regression: single-token close still succeeds | Phase split preserves memory close/audit outcomes |
| P12 | 4h long-continuation path | Existing 4h close-preference remains compatible with generic selector |

---

## 15. Failure / rollback conditions

Implementation/closeout must fail closed if:

- any independent loop bypasses Central Scheduler or Source Governor;
- protection class uses numeric scores/weights/confidence;
- cadence dirty/block thresholds are raised to hide contention;
- phase split allows audit to rewrite closing capture timestamps;
- multi-cycle selection permanently prefers Cycle 1 or Cycle 2;
- retrieval/paper/financial surfaces activate;
- authorization is created/reused;
- proofs require live provider dependence beyond disposable fixtures without
  explicit later approval.

Rollback:

- keep Lane-1 cadence authority intact;
- feature-flag or do not merge phase-split if disposable proofs fail;
- additive schema remains unused if rolled back;
- never reuse consumed `…512f2436` authorization.

---

## 16. Explicit non-goals / locks

- Design Lane 3 post-1H → 4H progression / fault preservation
- Design Lane 4 multi-cycle terminal accounting/reporting
- Candidate-acquisition redesign
- Raising FAST/NORMAL cadence thresholds
- Concurrent multi-process workers / thread pools as the primary fix
- Paid APIs / unlimited provider capacity
- Scoring, ranking, confidence percentages, weighted decision logic
- Retrieval, paper trading, BUY/SELL/HOLD, positions, trades, audits, PnL
- Live wallet / private keys / real funds / live execution
- `WINDOW_5M_MICRO_EVENT` as main outcome memory
- `WINDOW_12H` / `WINDOW_24H` unlock
- Automatic restart after terminal failure

---

## 17. Observability minimum

Per token/window (and per phase step), report:

| Field | Meaning |
| --- | --- |
| `scheduled_for` | cadence target |
| `deadline_at` | hard evidence deadline (when applicable) |
| `protection_class` | categorical class |
| `dispatched_at` / `started_at` / `finished_at` | claim/exec timing |
| `scheduler_wait_ms` | due → start |
| `source_wait_ms` | time in governed source calls |
| `evidence_captured_at` | closing/gap snapshot time |
| `lateness_ms` | capture/finish vs deadline |
| `blocked_reason` | categorical deny/fail |
| `missed_deadline_reason` | e.g. `STARVED_BY_SIBLING_CLOSE`, `SOURCE_BUDGET_EXHAUSTED_BEFORE_EVIDENCE_DEADLINE`, `SCHEDULER_EXECUTION_DEADLINE_EXCEEDED` |
| `queue_depth_by_class` | bounded saturation signal |
| `ordinary_service_count` | fairness counter |

No scores. No confidence percentages.

---

## 18. Authority notes

- `CURRENT_HANDOFF.md` was stale (still described fresh 4/2/2 authorization
  construction). Source stack + Lane-1 closeout + forensic audit win; handoff
  receives only the minimal docs-only update for this design lane.
- Lane 1 remains closed PASS and is a prerequisite, not reopened.
- This design does not authorize implementation, proof execution, or Lane 3.

---

## 19. Verdict

The current architecture provides enough truthful authority to design the
repair: forensic proof of serial close contention, inspected production
owners, existing unused fairness modules, existing campaign `deadline_at`
fields, and Lane-1 cadence authority.

`V2_9_8B_MULTI_TOKEN_EVIDENCE_DEADLINE_SCHEDULING_DESIGN_PASS_READY_FOR_IMPLEMENTATION`

Exact next permitted work after this design commit: **implementation of this
design’s approved slices** under a separate implementation lane, or operator
review of this design. **Do not start Design Lane 3 in this task.**
