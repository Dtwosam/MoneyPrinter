# V2-9.8B Design Lane 2 — Multi-Token Evidence-Deadline Scheduling

**Document status:** `DESIGN` (post-capture timing amendment)
**Date:** 2026-08-22  
**Original design HEAD:** `012eacd785c950367a550259d83e09957906dffe`  
**Amendment starting HEAD:** `46fc13c0f36297f8d76c24f7bbba1313a6db796e`  
**Post-capture timing amendment starting HEAD:** `7d24bcbb7fdd781f4ac628662d89a65c1621bbd6`
**Governing forensic audit:** `docs/printer-v1-v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit.md`  
**Prerequisite Lane 1 closeout:** `docs/printer-v1-v2-9-8b-cadence-authority-lane1-closeout.md`  
**Verdict:** `V2_9_8B_POST_CAPTURE_CONTEXT_TIMING_DESIGN_AMENDMENT_PASS_READY_FOR_CORRECTIVE_IMPLEMENTATION`

### Amendment scope (docs-only)

Retains the core Lane-2 architecture:

- Central Scheduler as execution authority
- phase-split close work
- deterministic multi-token fairness
- Source Governor preservation
- bounded overload behavior

The first amendment corrected two design defects:

1. **Canonical AGENTS resource priority must lead selection.** Protection /
   phase classes must not globally outrank `TRACK_FAST` / `TRACK_NORMAL`
   snapshots, and future paper/retrieval must not encode a contrary runtime
   priority while locked.
2. **`deadline_at` must protect the Lane-1 clean-gap contract** from the
   previous **actual** captured snapshot, not from `scheduled_for` or
   `window_end_at + closing_clean_late_seconds` alone.

The post-capture timing amendment in Section 20 corrects one additional design
ambiguity exposed by the phase-split implementation: executing
`CLOSE_CONTEXT` after `CLOSE_EVIDENCE` does not extend a window's lawful
evidence boundary or backdate later context into the closed window.

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

### 2.3 Canonical AGENTS resource category order (authoritative)

`AGENTS.md` Resource Priority Order is the **global** categorical resource
authority under pressure. Existing `JOB_PRIORITY_ORDER` already mirrors it for
token-level work:

1. open paper-trade monitoring (`OPEN_PAPER_TRADE_MONITOR`) — **LOCKED now**
2. exit-risk token snapshots (`ACTIVE_EXIT_RISK_TOKEN`)
3. TRACK_FAST / micro-event token snapshots
4. TRACK_NORMAL token snapshots
5. memory-window close snapshots (`MEMORY_WINDOW_CLOSE`)
6. safety and liquidity refreshes
7. discovery refresh / admission
8. market regime context
9. Solana chain heat context
10. backup checks

Lane 2 does **not** invent numeric confidence scores and does **not** invent a
second global priority ladder that can place `MEMORY_WINDOW_CLOSE` evidence
above TRACK_FAST/TRACK_NORMAL. Phase/deadline eligibility and token/cycle
fairness operate **inside** the winning AGENTS resource category.

Paper monitoring and retrieval remain locked. Their future runtime category,
when an explicit lane unlocks them, must inherit the AGENTS order applicable at
that time — not a design-time low-priority placeholder.

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

Cadence quality is based on gaps between **actual captured snapshots**. Dispatch
protection must therefore be anchored to the previous truthful capture, not to
nominal schedule alone.

| Clock | Label | Canonical owner | Meaning | Honesty if missed / absent |
| --- | --- | --- | --- | --- |
| **A. Scheduled cadence target** | `scheduled_for` | Cadence planner + `printer_scheduler_jobs.scheduled_for` / run-step `scheduled_for` | Nominal due/fire time | Lateness measurable; not itself dirty |
| **B. Clean dispatch protection deadline** | `deadline_at` | Campaign scheduler-work `deadline_at` (semantic owner), derived below | Latest capture time that still preserves the current **clean-gap** contract vs the previous actual snapshot (and closing freshness when forced) | Report `MISSED_CLEAN_DISPATCH_DEADLINE`; clean coverage is no longer guaranteed. Actual cadence status still comes only from the authoritative evaluator (DIRTY vs BLOCKED). Missing required prior capture → fail closed / `UNKNOWN`; **do not synthesize** a deadline or fabricate CLEAN |
| **C. Block boundary** | `block_boundary_at` (derived; not `deadline_at`) | `last_actual_snapshot_captured_at + max_clean_snapshot_gap_seconds` (Lane-1 policy) | Gap above this blocks the window | Distinct from `deadline_at`. Evaluator-only; never used as a substitute clean-dispatch deadline |
| **Dirty boundary (evaluation)** | policy `dirty_above_gap_seconds` | `SnapshotCadencePolicy` + Lane-1 lane authority | Gap above this dirties coverage | DIRTY / do_not_train; never fabricate fill |
| **Source-operation timeout** | adapter timeout | Adapter / transport `timeout_seconds` | One provider call wall budget | Partial/failed/unknown evidence; no invent |
| **Scheduler execution deadline** | per-step wall budget | Optional bound after claim | Max time one claimed step may hold the worker before cooperative yield/fail-closed | Exceed → fail/skip step with typed cause; never silent hang |
| **Window-close plan time** | `window_end_at` | Window / campaign window close plan | When the window is planned to close/evaluate | Close bookkeeping may finish after evidence capture; evaluation uses real capture times |

### Binding rules

1. **`deadline_at` ≠ source timeout.** A slow provider call may miss a source
   timeout without being allowed to consume another token’s clean-dispatch
   deadline inside the same AGENTS category.
2. **`deadline_at` ≠ block boundary.** Block boundary (`max_clean_snapshot_gap_seconds`)
   remains evaluator-only and must stay distinct from clean-dispatch `deadline_at`.
3. **`scheduled_for` remains the due/fire time.** `deadline_at` is a distinct
   later bound derived from actual prior capture (today they are wrongly equal
   for 15m projections).
4. **Window-close bookkeeping may finish after `deadline_at`** if the closing
   snapshot was already captured on time. Audit latency must not rewrite
   capture time.
5. **Missing `deadline_at` never fabricates CLEAN.** The authoritative cadence
   evaluator still determines CLEAN / DIRTY / BLOCKED from actual captured
   times. Missing the clean dispatch deadline only means clean coverage is no
   longer guaranteed and must be reported.
6. **Do not widen Lane-1 cadence thresholds** to hide contention.
7. Provider failure remains honest missing/partial/dirty/blocked evidence.

### Deterministic `deadline_at` derivation (amended)

Require a truthful previous actual captured snapshot wherever one is required
for gap protection. If absent: fail closed / `UNKNOWN`; do **not** synthesize
`deadline_at` from `scheduled_for` alone.

**Ordinary cadence / close-evidence step (clean dispatch protection):**

```text
deadline_at =
  last_actual_snapshot_captured_at
  + dirty_above_gap_seconds
```

using the Lane-1-resolved cadence policy for that exact token/window/lane.

**Forced closing snapshot** (also respects closing freshness):

```text
deadline_at = min(
  last_actual_snapshot_captured_at + dirty_above_gap_seconds,
  window_end_at + closing_clean_late_seconds
)
```

**Block boundary (distinct; not stored as `deadline_at`):**

```text
block_boundary_at =
  last_actual_snapshot_captured_at
  + max_clean_snapshot_gap_seconds
```

FAST example (why `window_end + closing_clean_late` alone is insufficient):
if the previous actual capture drifted late,  
`last_actual + dirty_above` can be **earlier** than  
`window_end + closing_clean_late`. The `min(...)` form keeps the clean-gap
contract; the later window-end-only bound must not win.

When a prior actual capture drifts, recompute `deadline_at` from that new
truthful capture before dispatching the next evidence step.

---

## 5. Deterministic fairness / dispatch model

### 5.1 Chosen architecture (amended)

**Central-Scheduler Deadline-Phased Fair Dispatch**

Narrowest change that preserves existing owners and AGENTS resource law:

1. Keep one Central Scheduler–led worker loop (no bypass engine).
2. **Phase-split** close work into separate claimable scheduler steps so
   evidence capture can interleave across tokens.
3. **Wire** the existing pure fairness selectors (or an equivalent factory-side
   adapter that reuses their categorical keys) into `_select_next_pending_step`
   for all active window lifecycle work, not only `WINDOW_4H`.
4. Selection is layered — **not** a second global priority ladder:

```text
canonical AGENTS / JobKind resource category
  -> phase / deadline eligibility inside that category
  -> token / cycle fairness
  -> deterministic tie-break
```

This is not ranking, scoring, confidence, or weighted decision logic.
`SAFE_STOP` / shared integrity / shared campaign-budget failure remains an
**overriding safety gate**, not ordinary workload priority.

### 5.2 Canonical resource categories (global; AGENTS-led)

Under resource pressure, due work is first partitioned by the AGENTS resource
category mirrored in `JOB_PRIORITY_ORDER`. Examples:

| AGENTS rank | Resource category | Active now? |
| --- | --- | --- |
| 1 | Open paper-trade monitoring | **LOCKED** (JobKind exists; runtime inactive for V2-9.8B) |
| 2 | Exit-risk token snapshots | available when produced |
| 3 | TRACK_FAST / micro-event token snapshots | active |
| 4 | TRACK_NORMAL token snapshots | active |
| 5 | Memory-window close snapshots (`MEMORY_WINDOW_CLOSE`) | active |
| 6 | Safety / liquidity refresh | active |
| 7 | Discovery / admission | active |
| 8–10 | Market regime / chain heat / backup | active as scheduled |

**Hard amendments:**

- `MEMORY_WINDOW_CLOSE` evidence **must not** globally outrank due TRACK_FAST
  or TRACK_NORMAL snapshots.
- When TRACK_FAST and memory-close evidence are both due, TRACK_FAST wins.
- When TRACK_NORMAL and memory-close evidence are both due, TRACK_NORMAL wins.
- Future paper monitor, when unlocked by an explicit lane, inherits AGENTS
  rank 1 at that time — it must **not** be permanently assigned a low-priority
  design class now.
- Retrieval priority remains **undecided / locked** until its approved lane.
  No runtime retrieval priority may be encoded that contradicts the authority
  stack.

### 5.3 Phase / deadline eligibility (inside one resource category only)

Phase eligibility is **intra-category**. It never promotes close work above
TRACK_FAST/NORMAL.

#### Inside `MEMORY_WINDOW_CLOSE` (AGENTS rank 5)

| Intra-close phase order | Phase step_kind | Eligibility role |
| --- | --- | --- |
| 1 | `*_CLOSE_EVIDENCE` | Clean-dispatch deadline–critical capture |
| 2 | `*_CLOSE_CONTEXT` | Supporting/preclose context after capture |
| 3 | `*_CLOSE_AUDIT` | E2O / E2Q / Lane Q/K / E2Z bookkeeping |

`CLOSE_EVIDENCE` must be selected before `CLOSE_CONTEXT` / `CLOSE_AUDIT`
**within the close-work category**. Sibling close-evidence steps compete by
earliest lawful `deadline_at`, then token/cycle fairness — never by permanent
cycle priority.

#### Inside TRACK_FAST / TRACK_NORMAL snapshot categories (AGENTS ranks 3–4)

| Intra-track eligibility | Meaning |
| --- | --- |
| Due ordinary cadence snapshot | Eligible when `scheduled_for <= now` |
| Deadline-urgent cadence snapshot | Same category; prefer earlier clean-dispatch `deadline_at` among due track snapshots only |

A deadline-urgent TRACK_* snapshot still outranks any `MEMORY_WINDOW_CLOSE`
phase because the AGENTS category is higher. Close evidence urgency cannot
leapfrog into the TRACK_* category.

#### Supporting labels (not a global ladder)

These labels are reporting / intra-category phase tags only:

- `CLOSE_EVIDENCE` / `CLOSE_CONTEXT` / `CLOSE_AUDIT`
- `CADENCE_ORDINARY` (within a TRACK_* category)
- `DISCOVERY_ADMISSION` (within discovery category)
- `BROAD_CONTEXT` / `BACKUP` (within their AGENTS categories)

They must **not** be interpreted as a global order that places close evidence
above TRACK_* work.

### 5.4 Dispatch keys (deterministic)

Selection key for due, Source-Governor–eligible work:

```text
(
  safe_stop_gate,                 # overriding safety gate first
  agents_resource_rank,           # canonical AGENTS / JobKind category
  intra_category_phase_order,     # e.g. CLOSE_EVIDENCE before CONTEXT/AUDIT
  deadline_at_or_sentinel,        # earliest clean-dispatch deadline inside category
  token_ordinary_service_count,   # fewer served first (fairness; not a score)
  scheduled_for,
  created_at,
  cycle_ordinal,                  # tie-break / readiness only
  slot_ordinal,
  scheduler_work_id / step id
)
```

Notes:

- `deadline_at_or_sentinel` uses the derived clean-dispatch deadline when
  present; missing required deadline → that step is not preferentially
  “protected clean”; report UNKNOWN / fail closed for synthesis attempts.
- Reuse / adapt `two_token_fairness` / `multi_cycle_fairness` **inside** the
  already-selected AGENTS category; do not let those modules invent a global
  `MAIN_WINDOW_CLOSE` rank above TRACK_* JobKinds.

### 5.5 Cycle fairness

- Cycle 1 must not permanently outrank Cycle 2; Cycle 2 must not permanently
  outrank Cycle 3.
- `cycle_ordinal` is a **tie-breaker and dependency/readiness key only**.
- Semantic dependencies remain: a token’s continuation window cannot run before
  its predecessor close/admission readiness; that is readiness, not priority.
- Cross-cycle selection: each cycle proposes its local next item within the
  current AGENTS category; campaign picks by the dispatch key above, not by
  “older cycle wins.”

### 5.6 Anti-monopoly rules (no scores)

A single token, queue, cycle, window, source call, or close operation must not
monopolize the worker so that another token’s lawful **same-or-higher AGENTS
category** evidence misses its clean-dispatch deadline.

Concrete rules:

1. After completing any `CLOSE_CONTEXT` / `CLOSE_AUDIT` step, re-enter
   selection before starting another lower intra-close phase if any due
   higher-AGENTS work or sibling `CLOSE_EVIDENCE` is claimable.
2. A claimed context/audit step has a bounded scheduler execution deadline; on
   exceed, fail closed with `SCHEDULER_EXECUTION_DEADLINE_EXCEEDED` for that
   step only (token-local), then reselect.
3. One source call cannot extend into another token’s clean-dispatch deadline
   by chaining unbounded retries (existing no-auto-restart / cooldown law).
4. No automatic capacity increase.
5. Slow context/audit for token A must not delay token B’s due `CLOSE_EVIDENCE`
   inside the close category, and must not delay due TRACK_* snapshots at all.

---

## 6. Token / window isolation model

| Boundary | Isolation rule |
| --- | --- |
| Snapshot acquisition | Per exact token/pair/window step; sibling capture must be independently claimable |
| Supporting evidence | Per token; failure/slowness is token-local unless shared Source Governor budget is exhausted (campaign-visible) |
| Main-window audit/close bookkeeping | Per window after that window’s closing evidence exists; must not block sibling capture |
| Continuation admission | Depends on predecessor window terminal truth for **that** token only |
| Campaign cycle progression | Cycle admission quanta remain in the discovery AGENTS category; they yield to higher AGENTS ranks (including TRACK_* and, when competing only among close work, to `CLOSE_EVIDENCE`) |

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
claimed / completed through Central Scheduler, and all remaining in AGENTS
resource category rank 5:

| Phase step_kind | Intra-close phase order | Must finish by | May yield |
| --- | --- | --- | --- |
| `WINDOW_CLOSE_EVIDENCE` (and 1h/4h analogues) | 1 | clean-dispatch `deadline_at` | No (short; snapshot only) |
| `WINDOW_CLOSE_CONTEXT` | 2 | best-effort before audit; never rewrite capture time | Yes — to any higher AGENTS category and to sibling `CLOSE_EVIDENCE` |
| `WINDOW_CLOSE_AUDIT` | 3 | bounded execution deadline | Yes — to any higher AGENTS category, track snapshots, and sibling `CLOSE_EVIDENCE` / context as ordered |

Ordering constraints:

1. Evidence phase requires window collecting + due close schedule + lawful
   `deadline_at` derivation (or fail closed / UNKNOWN if prior capture missing).
2. Context phase must not run ahead of evidence for that window by default
   (**capture before context**; reorder vs today’s preclose-before-capture).
   This is an execution-order rule, not evidence-boundary authority. Section 20
   governs whether context resolved or collected later is admissible to the
   just-closed window.
3. Audit phase requires persisted closing snapshot identity for that window.
4. No phase may create an independent API loop or bypass Source Governor.
5. No close phase may outrank due TRACK_FAST / TRACK_NORMAL snapshots.

This is the primary structural fix for C1–C3.

Continuation windows (`CONTINUATION_CLOSE`, `LONG_CONTINUATION_CLOSE`) use the
same three-phase pattern with stage-specific names.

---

## 8. Source Governor interaction

Central Scheduler fairness **never** bypasses Source Governor.

| Situation | Required behavior |
| --- | --- |
| Deadline-sensitive work, source budget exhausted | Do not fetch; mark evidence missing/stale/blocked; report `SOURCE_BUDGET_EXHAUSTED_BEFORE_CLEAN_DISPATCH_DEADLINE` |
| Source operation slow | Bound by source-operation timeout; on timeout, partial/fail closed; do not extend retries into sibling clean-dispatch deadlines |
| Provider partial/unknown/failure | Persist honest status; dirty/blocked as policy requires; never fabricate |
| Multiple tokens want same constrained source | Deterministic grant order: higher AGENTS category first; inside category, earlier clean-dispatch `deadline_at` then token fairness; denied tokens remain honest missing |

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
| No silent starvation | If clean-dispatch work misses `deadline_at` while the worker was busy on lower AGENTS category or lower intra-close phase work, report `STARVED_BY_LOWER_AGENTS_CATEGORY_WORK`, `STARVED_BY_LOWER_CLOSE_PHASE`, or `STARVED_BY_SIBLING_CLOSE` |
| No automatic capacity increase | Operator/design lanes only |

Required reports when Printer cannot service all lawful clean-dispatch deadlines:

- `scheduler_saturation=true`
- `missed_clean_dispatch_deadlines=[...]` with exact token/window/cycle ids
- `blocked_reason` per affected window
- queue depth by AGENTS resource category and intra-close phase
- campaign acceptance remains honest (`BLOCKED_UNSAFE` / dirty/blocked memory as earned)

Reuse existing ceiling vocabulary where applicable:

`scheduler_work_ceiling_exhausted`, `source_request_ceiling_exhausted`,
`storage_growth_ceiling_exhausted`, `failure_ceiling_exhausted`.

---

## 10. Cycle-3+ and future-workload compatibility

Known future / adjacent scheduler consumers from the active build order:

- additional two-token cycles up to compiled max (`MAX_ACTIVE_TWO_TOKEN_CYCLES = 3`);
- longer approved windows (1h/4h already; 12h/24h locked);
- retrieval evaluation (locked; priority undecided until approved lane);
- paper decision / monitor / audit work (locked; paper monitor inherits AGENTS
  rank 1 only when explicitly unlocked).

Compatibility contract:

1. Every future consumer must declare its **AGENTS resource category** (or an
   explicit later AGENTS amendment) before it can be selected. Intra-category
   phase/deadline tags are secondary.
2. Close-phase evidence protection remains **inside** `MEMORY_WINDOW_CLOSE`.
   It does not become a permanent global superseding class over TRACK_*.
3. Locked paper/retrieval surfaces must remain inactive. Runtime must reject
   enqueue/selection while locked. Design must **not** permanently encode
   paper monitor as a low-priority class or invent a retrieval priority that
   contradicts the authority stack.
4. Multi-cycle fairness composition already caps active cycles; Lane 2 must not
   invent a fourth-cycle path here.
5. When paper monitor is later unlocked, it joins at the then-current AGENTS
   paper-monitoring rank. When retrieval is later unlocked, its rank is set
   only by that lane’s approved authority — undecided here.

---

## 11. Required schema / API / code changes (design only; do not implement)

### 11.1 Prefer existing owners

Minimum change set:

1. **Factory selection** — replace 15m/1h FIFO path in
   `_select_next_pending_step` with layered selection:
   AGENTS/`JobKind` category → intra-category phase/deadline → token/cycle
   fairness (adapter over fairness-module keys **within** category).
2. **Close phase split** — plan/enqueue three phase steps instead of one close
   blob; adjust `_execute_close` family to phase runners.
3. **Deadline semantics** — derive and persist distinct clean-dispatch
   `deadline_at` from last actual capture (+ closing freshness min for forced
   close). Stop equating `deadline_at` to `scheduled_for`. Never synthesize
   when prior capture is missing.
4. **Phase mapping** — derive intra-close phase from `step_kind`; do not
   require rewriting immutable historical `work_intent` strings.
5. **Observability** — emit structured per-step timing and deadline-basis
   fields into existing supervision/observer / final report surfaces.

### 11.2 Schema / migration impact

| Change | Required? | Notes |
| --- | --- | --- |
| New table | **No** (preferred) | Use existing jobs, run_steps, campaign_scheduler_work |
| New step_kind values | **Yes** (code/contract) | `WINDOW_CLOSE_EVIDENCE` / `_CONTEXT` / `_AUDIT` (+ 1h/4h analogues) |
| Distinct clean-dispatch `deadline_at` semantics | **Yes** (behavioral) | Column already exists (mig 032/050); derivation amended |
| Optional report fields for `last_actual_snapshot_captured_at`, `block_boundary_at` | **Yes** (observability) | Prefer report/observer; durable columns optional |
| Global `protection_class` superseding AGENTS order | **Forbidden** | Do not add a column/API that outranks TRACK_* |
| `printer_scheduler_jobs` new deadline column | **No** | Keep deadline on campaign ownership work row; job keeps `scheduled_for` |
| Fairness module API | **Minor** | Map factory rows → work items **after** AGENTS category filter |

No BUY/retrieval/12h/24h schema unlocks. No scoring columns.

### 11.3 Intent / phase mapping (no hidden priority score)

Because current `work_intent` values are stage-descriptive and historically
immutable, selection must **derive** AGENTS category from `JobKind` / step
family and intra-category phase from `step_kind`:

| step_kind / phase | AGENTS resource category | Intra-category phase |
| --- | --- | --- |
| TRACK_FAST_* snapshot | TRACK_FAST (rank 3) | cadence ordinary / deadline-urgent among track peers |
| TRACK_NORMAL_* snapshot | TRACK_NORMAL (rank 4) | cadence ordinary / deadline-urgent among track peers |
| `*_CLOSE_EVIDENCE` | MEMORY_WINDOW_CLOSE (rank 5) | close phase 1 |
| `*_CLOSE_CONTEXT` | MEMORY_WINDOW_CLOSE (rank 5) | close phase 2 |
| `*_CLOSE_AUDIT` | MEMORY_WINDOW_CLOSE (rank 5) | close phase 3 |
| discovery / admission steps | discovery (rank 7) | admission/refresh as owned |
| safe-stop / shared integrity | safety gate (overrides ordinary selection) | n/a |

New rows may optionally persist derived phase labels for observability; old
rows remain valid via derivation. Do not persist a future paper/retrieval
runtime priority while those capabilities remain locked.

---

## 12. Migration plan (if optional columns are approved)

Only if implementation chooses durable observability columns:

1. Forward-only migration after Lane-2 implementation approval.
2. Additive columns with NULL allowed for historical rows.
3. No rewrite of historical `work_intent` / `deadline_at` values except through
   lawful new projections for new steps.
4. Triggers preserve immutability of identity fields already protected by mig
   047/050.
5. Disposable rehearsal before any authoritative apply.
6. Rollback = do not apply; code remains backward compatible by deriving phase
   from step_kind and recomputing clean-dispatch deadlines from actual captures.

If report/observer-only observability suffices, **skip migration**.

---

## 13. Implementation sequence (future; not this lane)

1. **Contract freeze** — AGENTS-led layered dispatch, phase step_kinds,
   clean-dispatch deadline derivation helper, mapping table (this amended
   design).
2. **Selection wiring** — factory `_select_next_pending_step` adapter:
   AGENTS category first, then phase/deadline, then fairness; keep 4h
   special-case behavior as a subset, not a fork that reorders AGENTS ranks.
3. **Close phase split** — plan evidence/context/audit steps; implement phase
   executors; ensure capture precedes context by default.
4. **Deadline projection** — last-actual-capture-based `deadline_at` (+ forced
   close `min(...)`); miss / UNKNOWN reporting; never synthesize.
5. **Source Governor yield rules** — deadline-sensitive deny/report paths
   that still respect AGENTS category order.
6. **Observability** — observer + final-report fields including deadline basis.
7. **Bounded disposable proof** — matrix below (including amendment proofs).
8. **Independent closeout** — then Lane 3 design remains next per forensic
   sequence (not started here).

Suggested implementation slices:

| Slice | Content | Risk |
| --- | --- | --- |
| S1 | AGENTS-led selection wiring + intra-category fairness (no phase split yet) | Medium |
| S2 | Close evidence/context/audit phase split + reorder | High |
| S3 | Last-actual-capture `deadline_at` projection + miss/UNKNOWN reporting | Medium |
| S4 | Observability + saturation signals (category + phase + deadline basis) | Low |
| S5 | Optional migration if S4 needs durable columns | Low |

---

## 14. Bounded proof matrix

Disposable / fixture only. No live authorization. No authoritative campaign.

| Proof ID | Scenario | Expect |
| --- | --- | --- |
| P1 | Two sibling tokens with simultaneous due closes | Both evidence phases claim/complete before either audit phase starts (or before sibling clean-dispatch deadline miss) |
| P2 | Token A context/audit slow; Token B evidence due | B `CLOSE_EVIDENCE` selected next inside close category; A does not monopolize |
| P3 | Correct TRACK_NORMAL cadence after Lane 1 | Closing gaps do not exceed dirty band solely due to sibling serialization |
| P4 | Source budget exhausted during clean-dispatch work | Honest miss/block; no fabricated evidence; typed reason |
| P5 | Provider timeout on context phase after timely capture | Capture remains on-time; context partial/failed; audit sees honest context |
| P6 | Cycle1 WINDOW_1H + Cycle2 WINDOW_15M overlap | No permanent Cycle1 priority; sibling/category rules still hold |
| P7 | Ordinary service round-robin with two tokens | Service counts converge; no silent starvation |
| P8 | Ceiling exhaustion | Blocked with ceiling reason; no auto capacity bump |
| P9 | Locked paper/retrieval enqueue attempt | Rejected/fail closed; no contrary runtime priority encoded |
| P10 | Safe shutdown mid-phase | No orphan RUNNING; active work drains; no auto-restart |
| P11 | Regression: single-token close still succeeds | Phase split preserves memory close/audit outcomes |
| P12 | 4h long-continuation path | Existing 4h close-preference remains compatible without outranking TRACK_* |
| **A1** | TRACK_FAST due snapshot + memory-close evidence simultaneously | **Canonical TRACK_FAST priority preserved** (close evidence waits) |
| **A2** | TRACK_NORMAL due snapshot + memory-close evidence simultaneously | **Canonical TRACK_NORMAL priority preserved** |
| **A3** | Two sibling close-evidence steps | Earliest clean-dispatch `deadline_at` wins; no permanent cycle priority |
| **A4** | Slow context/audit on token A | Cannot delay sibling token B close evidence |
| **A5** | Prior actual capture drift | `deadline_at` recomputes from new last actual capture |
| **A6** | FAST case where `window_end + closing_clean_late` is too late for clean gap | Earlier `last_actual + dirty_above` wins via `min(...)` |
| **A7** | Future paper/retrieval classes | Remain inactive; do not encode runtime priority contrary to authority stack |

---

## 15. Failure / rollback conditions

Implementation/closeout must fail closed if:

- any independent loop bypasses Central Scheduler or Source Governor;
- phase/protection labels use numeric scores/weights/confidence or create a
  global ladder that outranks AGENTS TRACK_FAST / TRACK_NORMAL;
- cadence dirty/block thresholds are raised to hide contention;
- `deadline_at` is synthesized without a required truthful prior actual capture;
- `deadline_at` ignores `last_actual + dirty_above` for close evidence;
- phase split allows audit to rewrite closing capture timestamps;
- multi-cycle selection permanently prefers Cycle 1 or Cycle 2;
- retrieval/paper/financial surfaces activate, or locked paper/retrieval is
  given a contrary runtime priority;
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
- Encoding a permanent low priority for future paper monitor, or any retrieval
  priority, while those lanes remain locked
- Live wallet / private keys / real funds / live execution
- `WINDOW_5M_MICRO_EVENT` as main outcome memory
- `WINDOW_12H` / `WINDOW_24H` unlock
- Automatic restart after terminal failure

---

## 17. Observability minimum

Per token/window (and per phase step), report:

| Field | Meaning |
| --- | --- |
| `scheduled_for` | nominal due/fire time |
| `last_actual_snapshot_captured_at` | prior truthful capture used for deadline derivation |
| `deadline_at` | clean dispatch protection deadline |
| `block_boundary_at` | derived block boundary (distinct; evaluator alignment) |
| `agents_resource_category` / `agents_resource_rank` | canonical AGENTS category |
| `intra_category_phase` | e.g. `CLOSE_EVIDENCE` / `CLOSE_CONTEXT` / `CLOSE_AUDIT` |
| `dispatched_at` / `started_at` / `finished_at` | claim/exec timing |
| `scheduler_wait_ms` | due → start |
| `source_wait_ms` | time in governed source calls |
| `evidence_captured_at` | closing/gap snapshot time |
| `lateness_ms` | capture/finish vs clean-dispatch `deadline_at` |
| `blocked_reason` | categorical deny/fail / UNKNOWN |
| `missed_deadline_reason` | e.g. `STARVED_BY_SIBLING_CLOSE`, `STARVED_BY_LOWER_CLOSE_PHASE`, `SOURCE_BUDGET_EXHAUSTED_BEFORE_CLEAN_DISPATCH_DEADLINE`, `SCHEDULER_EXECUTION_DEADLINE_EXCEEDED`, `MISSING_PRIOR_ACTUAL_CAPTURE` |
| `queue_depth_by_agents_category` | bounded saturation signal |
| `queue_depth_by_close_phase` | close-category saturation |
| `ordinary_service_count` | fairness counter |

No scores. No confidence percentages.

---

## 18. Authority notes

- `CURRENT_HANDOFF.md` was stale relative to the consumed 4/2/2 forensic path
  and was minimally updated during the first Design Lane 2 amendment. The
  post-capture timing amendment relies on the active source stack and does not
  modify the handoff.
- Lane 1 remains closed PASS and is a prerequisite, not reopened.
- This amended design does not authorize implementation, proof execution, or
  Lane 3.
- AGENTS.md resource priority remains higher authority than any Lane-2
  intra-category phase tag.

---

## 19. Verdict

The first amended design preserved the sound Lane-2 architecture while
correcting:

1. global selection to remain AGENTS resource-category–led; and
2. clean-dispatch `deadline_at` to anchor on last actual capture (+ forced-close
   freshness min), keeping block boundary distinct and never synthesizing
   deadlines or CLEAN status.

Its implementation-ready verdict is superseded for the unaccepted phase-split
slice by the post-capture evidence-boundary amendment below. The accepted S1
category/fairness and last-actual-capture deadline slices remain unchanged.

---

## 20. Post-capture context timing / evidence-boundary amendment

### 20.1 Discovered conflict and authority

The phase split lawfully changes worker execution order to:

```text
CLOSE_EVIDENCE
-> Central Scheduler reselection
-> CLOSE_CONTEXT
-> Central Scheduler reselection
-> CLOSE_AUDIT
```

That architecture is retained. The unaccepted implementation nevertheless
attempted to make later context usable by passing `tracking_lane` into the 15m
shared context resolver and by moving broad market/chain lookups from
`window_end_at` to `closing_evidence_cutoff_at`. Those changes conflate worker
execution time with evidence admissibility.

Existing authority already resolves the conflict:

1. `window_end_at` is the immutable logical boundary of the memory window.
2. The V2-9.4.8 15m close-ordering closeout deliberately passes `run_id` but
   not `tracking_lane`; therefore its effective
   `closing_evidence_allowance_seconds` is zero and its
   `closing_evidence_cutoff_at` is exactly `window_end_at`.
3. The V2-9.8B first-hour checkpoint-4 contract authorizes the existing
   60-second forced-closing-snapshot freshness allowance for `WINDOW_1H`. It
   does not authorize a blanket extension for newly fetched context.
4. The V2-9.4.6 exact-closing-boundary contract authorizes the existing
   60-second allowance for the exact `WINDOW_4H` closing snapshot and its exact
   snapshot-bound closing safety and exit-quote evidence. It expressly does
   not move the logical deadline.
5. No reviewed authority allows later broad market-regime or Solana-chain
   observations to characterize an already-closed main window.

The cadence policy model currently carries a 60-second
`closing_clean_late_seconds` default, including on policy objects for several
families. The existence of that field is not family-independent evidence
authority. A caller may consume it only where the relevant window and evidence
class has an approved contract. In particular, the phase split alone cannot
activate that field for 15m context.

### 20.2 Binding three-clock and anti-look-ahead contract

These times are separate facts:

```text
Scheduler execution time
!= evidence observation/evaluation time
!= logical window boundary
```

- `window_end_at` says when the logical window ends.
- `captured_at`, `observed_at`, `evaluated_at`, or the existing equivalent says
  when evidence was actually known.
- Scheduler claim/start/finish timestamps say when a phase ran.

Delayed execution of `CLOSE_CONTEXT` is allowed for fairness and resource
control. It does not extend `window_end_at`, create an evidence allowance, or
change an observation timestamp.

Binding anti-look-ahead rule:

> Evidence first observed after a window's lawful evidence boundary cannot be
> treated as if known inside that window merely because a later Scheduler
> phase collected it, even when the later value would make the window appear
> safer, cleaner, or more profitable.

Exact binding to the closing snapshot proves identity; it does not backdate the
bound evidence. All evidence retains its real observation/evaluation time.

### 20.3 Final per-window-family boundary

The narrow contract is evidence-class-specific; there is no common late
allowance for every close input.

| Window family | Closing snapshot boundary | Other exact close evidence | Broad market / chain boundary | Result |
| --- | --- | --- | --- | --- |
| `WINDOW_5M_MICRO_EVENT` | Existing support-only cadence law | Existing support-only law only | `window_end_at` | Never a main outcome window and never independently CLEAN or continuation-authorizing |
| `WINDOW_15M` | Effective allowance `0`; cutoff exactly `window_end_at` | Cutoff exactly `window_end_at` | Cutoff exactly `window_end_at` | Do not pass `tracking_lane` merely to obtain the policy default |
| `WINDOW_1H` | Existing forced-closing freshness allowance: at deadline through 60 seconds late may be freshness-clean; over 60 seconds but below nominal interval is dirty; nominal-or-later is blocked, subject to the existing evaluator | No reviewed contract extends newly observed safety, holder, quote, market, or chain context past `window_end_at`; those classes remain bounded by their existing time law | Cutoff exactly `window_end_at` | The 60 seconds belongs to forced snapshot freshness, not all context |
| `WINDOW_4H` | Existing 60-second closing allowance | Existing 60-second allowance only for exact closing safety and exact closing exit quote bound to the closing snapshot; entry evidence keeps its original boundary | Cutoff exactly `window_end_at` | Preserve V2-9.4.6 exactly; do not generalize its exception |
| `WINDOW_12H` / `WINDOW_24H` | Locked | Locked | Locked | This amendment creates no authority or activation |

For `WINDOW_15M`, the binding decision is therefore:

```text
closing_evidence_allowance_seconds = 0
closing_evidence_cutoff_at = window_end_at
```

This amendment does not alter how the accepted deadline projection uses
`closing_clean_late_seconds` while protecting dispatch. Dispatch protection
and evidence admissibility are different contracts.

### 20.4 Per-context-class treatment

Every row used by the closed-window audit must satisfy both exact identity and
its class-specific time boundary.

| Context class | Required identity binding | Time truth | Admissibility cutoff | Post-window use | May satisfy main-window CLEAN evidence? |
| --- | --- | --- | --- | --- | --- |
| Closing snapshot | Exact campaign/run/cycle/slot/token/pair/window/queue and persisted snapshot id | Actual `captured_at` | Per-family closing-snapshot rule in Section 20.3 | Durable capture fact; later phases may reference but never rewrite it | Only when the existing cadence and family boundary gates pass |
| Market regime | Exact governed observation/source provenance associated with the owning close | Actual `captured_at` / `observed_at` | `<= window_end_at` for every active main-window family | Diagnostic post-close support or later-lifecycle context only | No, if first observed after `window_end_at` |
| Solana chain heat | Exact governed observation/source provenance associated with the owning close | Actual `captured_at` / `observed_at` | `<= window_end_at` for every active main-window family | Diagnostic post-close support or later-lifecycle context only | No, if first observed after `window_end_at` |
| Safety / rug evidence | Exact token, mint, pair where applicable, and exact target closing snapshot; no nearby-snapshot substitution | Every underlying source observation time plus the actual composite `evaluated_at`; neither may be backdated | Underlying observations must be within the class cutoff: 15m and 1h `<= window_end_at`; 4h `<= window_end_at + 60s` only under the V2-9.4.6 closing-safety contract | Later risk/support truth; must not be backdated | Only when exact identity, class cutoff, source status, and existing safety gates all pass |
| Holder context | Exact token/mint and exact safety/composite or target-snapshot contribution | Actual underlying observation time and actual derivation/evaluation time | Underlying observations inherit the authorized safety-composite cutoff; holder context has no independent late allowance | Later support or later-lifecycle truth | Only as part of a timely, exact, otherwise-valid existing composite |
| Closing exit quote / liquidity realism | Exact token/pair, base/quote identity, direction, target closing snapshot, and governed quote provenance | Actual quote observation time | 15m and 1h: `<= window_end_at`; 4h: `<= window_end_at + 60s` only for the approved exact closing exit quote | Later support; may describe subsequent exit conditions but not the earlier window | Only within the applicable family/class cutoff and existing quote gates |
| Entry quote / opening realism | Exact opening snapshot/checkpoint and exact token/pair/direction | Actual quote observation time | The original entry/opening evidence boundary | Later closing allowance never extends it retroactively | Only under its original timely-entry contract |
| Trading-flow / chart evidence | Exact admitted ledger snapshot ids for the owning token/pair/run/window; no foreign or nearby snapshot | Each snapshot's actual `captured_at`; derived evaluation retains actual evaluation time | Derived only from the exact snapshot set admitted by the existing family boundary | A new later refresh is support only; it cannot be inserted into the closed set | Yes only when the derivation uses the exact admissible set and all existing quality gates pass |

The 4h exception is deliberately narrow. A closing snapshot captured within its
approved allowance may contribute to ledger-derived flow/chart facts because
the snapshot itself is lawful closing evidence. That does not admit an
independent market, chain, entry, or other refresh merely because it arrived
during the same 60 seconds.

A deterministic resolver or composite evaluation may execute after the cutoff
without creating look-ahead only when every underlying observation was already
persisted, exact, and timely and the evaluation adds no post-cutoff fact. Its
real later `evaluated_at` is still retained. When `evaluated_at` is itself the
time of a fresh source evaluation or observation, it is evidence time and must
satisfy the class cutoff. Execution time is never silently copied onto timely
inputs, and timely input timestamps are never copied onto a later refresh.

### 20.5 Meaning of `CLOSE_CONTEXT`

After exact `CLOSE_EVIDENCE`, `CLOSE_CONTEXT` may perform three distinct acts:

**A. Resolve already-existing governed context.** It may resolve rows already
persisted through lawful owners. A row remains admissible when its own evidence
timestamp, exact identity, source status, and class-specific cutoff pass. The
later time at which the resolver reads it does not make timely evidence late.

**B. Perform a new governed post-capture refresh.** It may request only sources
already authorized by the existing close path, only through Source Governor,
and without a private loop or new retry policy. The refresh's actual evidence
time controls admissibility.

**C. Persist/report the later refresh truthfully.** A later result may be kept
as diagnostic support or later-lifecycle truth. Persistence does not make it
main-window evidence and must not rewrite `evidence_captured_at`, snapshot
`captured_at`, `window_end_at`, or any source observation timestamp.

The existing schema is sufficient for the later corrective slice: use exact
foreign keys/provenance, existing actual evidence/evaluation timestamps,
`closing_evidence_cutoff_at`, `closing_evidence_allowance_seconds`, existing
eligibility/blocker fields, and existing supporting-context/report JSON. The
implementation may describe the concepts "timely/in-window", "post-close
support/late for main window", and "unknown" without adding a new table,
column, migration, or mandatory enum vocabulary. No schema change is authorized
or required by this amendment; if later implementation evidence disproves that
sufficiency, the corrective slice must stop BLOCKED rather than invent one.

The invariant is:

```text
later observation
!= historical evidence that it existed at window_end_at
```

### 20.6 Audit, promotion, and memory-quality behavior

`CLOSE_AUDIT` consumes the exact persisted closing snapshot plus context with
its identity and timing relationship intact.

| Audit input state | Required result |
| --- | --- |
| Valid closing capture and all required timely context present | Apply the unchanged cadence, evidence, quality, and promotion gates |
| Valid capture plus a successful refresh that is too late for its main-window class | Retain the refresh as post-close support; do not count it toward CLEAN |
| Valid capture plus context timeout/provider failure/budget denial | Keep the capture durable; record truthful failed/partial/unknown context; apply existing fail-closed quality gates |
| Valid capture plus partial context | Preserve partial truth; do not manufacture completeness |
| Valid capture but required timely main-window context absent | Treat that requirement as missing/late under its existing owner; it cannot be rescued by later context |
| Missing or mismatched exact closing snapshot | Audit is ineligible; do not manufacture a close or later phase success |

Consequences for existing memory-quality outcomes:

- `CLEAN_MEMORY` remains possible only when every required evidence class is
  exact, timely under its own boundary, source-valid, cadence-valid, and passes
  every unchanged quality gate.
- `PARTIAL_MEMORY` may be used only where the existing quality owner already
  permits a partial outcome. A late refresh may explain the partial state but
  cannot promote it to CLEAN.
- Existing `DIRTY_MEMORY` and cadence `DIRTY` / `BLOCKED` results remain honest
  and are never hidden by later support.
- Any outcome lacking required lawful evidence remains non-training under the
  existing `DO_NOT_TRAIN` / `can_support_clean_memory=false` rules.
- Existing continuation prerequisites remain unchanged. Post-close support
  cannot satisfy a missing timely prerequisite or independently authorize
  continuation. A valid closing capture also is not erased merely because a
  later context request failed.

This amendment does not invent a new mapping from each missing field to
PARTIAL, DIRTY, or BLOCKED. The current cadence and evidence-quality owners
remain final authority; the amendment only prevents late evidence from being
misclassified as timely input to those owners.

### 20.7 Required scenarios

#### Scenario A — 15m exact close, later context

```text
window_end_at                  = 12:15:00
closing snapshot captured_at  = 12:15:00
context refresh completes     = 12:15:08
```

The exact closing snapshot may count, subject to all unchanged gates. Completion
at `12:15:08` alone is not the admissibility test. A new refresh whose evidence
was first observed/evaluated at `12:15:08` cannot count toward 15m main-window
market, chain, safety, holder, quote, flow, or chart requirements because 15m
has zero closing-evidence allowance. It may be persisted as truthful post-close
support. If `CLOSE_CONTEXT` instead completes at `12:15:08` by resolving exact
governed observations already persisted at or before `12:15:00`, those timely
inputs may count; any later deterministic evaluation retains its real
evaluation time and may add no later fact. Audit must retain snapshot time
`12:15:00` and cannot use a later refresh to rescue missing timely evidence.

#### Scenario B — slightly late closing snapshot

- **5m:** remains support-only; no main-memory promotion follows.
- **15m:** no late evidence allowance is activated. A capture after
  `window_end_at` is retained at its real time and classified by the unchanged
  cadence/evidence owners; it cannot widen the context cutoff or synthesize
  CLEAN.
- **1h:** the forced closing snapshot may use the existing 60-second freshness
  allowance and its existing clean/dirty/blocked bands. That allowance does not
  admit post-window context.
- **4h:** the exact closing snapshot may use the existing 60-second allowance;
  exact closing safety and exact closing exit quote may use only the same
  V2-9.4.6 boundary. Broad context and entry evidence do not.
- **12h/24h:** locked; no scenario creates runtime authority.

#### Scenario C — pre-existing timely context

The closing snapshot is captured, and `CLOSE_CONTEXT` later resolves an exact
governed row with an evidence timestamp within its lawful cutoff. It remains
admissible because evidence observation time, not resolver execution time,
controls. Exact token/pair/snapshot/window/source provenance and every existing
quality gate still must pass.

#### Scenario D — post-close market shift

If market regime changes after `window_end_at` before `CLOSE_CONTEXT`, the new
regime may be reported as post-close support. The window-end resolver must use
the latest exact governed observation at or before `window_end_at`; the later
row cannot overwrite or replace the closed-window market state.

#### Scenario E — context timeout

A valid closing snapshot remains durable with its real capture timestamp.
Source timeout, partial response, or budget denial in `CLOSE_CONTEXT` is recorded
honestly. Audit sees the failure/partial/unknown state and applies unchanged
fail-closed quality gates. It neither deletes the capture nor fabricates
context, CLEAN status, continuation, or phase success.

#### Scenario F — post-close safety deterioration

Worse safety first observed after the class's lawful cutoff is not evidence
that the worse condition existed inside the closed window. It is truthful
post-close risk/support or later-lifecycle evidence. It cannot rewrite the
window's history. Any separate existing safety authority may act on current
risk for later lifecycle work, but this amendment adds no such capability or
continuation rule.

#### Scenario G — post-close context looks better

Better context first observed after the lawful cutoff cannot rescue a window
that lacked required timely evidence. It remains post-close support and cannot
change `can_support_clean_memory` from false to true for the closed window.

#### Scenario H — existing longer-window lawful allowance

For an exact 4h close at `window_end_at + 8s`, the exact closing snapshot,
closing safety composite, and closing exit quote may remain admissible under
the existing 60-second V2-9.4.6 contract when all other gates pass. A market or
chain observation at `+8s`, an entry quote refreshed at `+8s`, or unrelated
snapshot context does not inherit that allowance. For 1h, the same `+8s`
allowance applies to forced closing-snapshot freshness only; it does not become
a blanket context cutoff.

### 20.8 Exact corrective implementation map

After this amendment is independently accepted, the narrow corrective code
slice should:

1. Stop passing `tracking_lane` from the 15m close path into
   `build_window_15m_context_evidence`; continue passing the exact `run_id` so
   the V2-9.4.8 ledger ordering/provenance repair remains intact.
2. Restore the 15m resolver result to
   `closing_evidence_allowance_seconds == 0` and
   `closing_evidence_cutoff_at == window_end_at`.
3. Restore broad market-regime and Solana-chain lookups to
   `target_time=window_end_at`, rather than the closing-evidence cutoff, for
   every shared active main-window use.
4. Preserve the 1h 60-second forced-closing-snapshot freshness policy without
   extending newly observed context past `window_end_at`.
5. Preserve the already-lawful 4h 60-second cutoff only for the exact closing
   snapshot, exact closing safety, and exact closing exit quote; keep entry,
   broad context, and other classes at their original boundaries.
6. Use real source observation/evaluation timestamps when deciding whether a
   context row is timely. Treat an exact identity match as corroboration, not
   a substitute for time truth.
7. Carry later refreshes, timeouts, and partial results through existing
   supporting metadata and eligibility/blocker fields as post-close support or
   truthful unknown/failed context. Do not add schema; if the corrective
   implementation disproves the documented sufficiency, stop BLOCKED.
8. Keep the three Scheduler-owned phase kinds, dependencies, claims, and
   reselection points intact. Do not revert the phase split or recursively run
   context/audit after evidence.
9. Keep the accepted last-actual-capture deadline projection, separate block
   boundary, category-first ordering, and Source Governor path byte-for-byte in
   contract.

The current phase-split implementation remains unaccepted until a separate
corrective code commit proves this map. This document makes no production
change.

### 20.9 Bounded proof matrix for the later correction

Disposable fixtures only; no live campaign or provider dependency.

| Proof ID | Scenario | Binding expectation |
| --- | --- | --- |
| T1 | 15m resolver called with exact run provenance | No `tracking_lane` allowance; cutoff equals `window_end_at` |
| T2 | 15m exact close, new context observed at `+8s` | Capture remains durable; later context cannot satisfy main-window CLEAN requirements |
| T3 | `CLOSE_CONTEXT` runs late but resolves exact context observed `<= window_end_at` | Timely row remains admissible; resolution time does not disqualify it |
| T4 | Market/chain state changes after close | Closed-window resolver selects only observations `<= window_end_at`; later state cannot overwrite it |
| T5 | Context timeout/partial/budget denial after valid capture | Capture id/time unchanged; context truthful; audit fail-closed under existing gates |
| T6 | Late safety becomes worse or better | Retained as support; neither rewrites earlier truth nor rescues missing timely evidence |
| T7 | 1h closing snapshot at deadline, `+60s`, and beyond `+60s` | Existing forced-snapshot freshness classifications remain exact; context receives no blanket allowance |
| T8 | 4h exact closing snapshot/safety/exit quote inside and outside `+60s` | Existing V2-9.4.6 acceptance and late blockers remain exact |
| T9 | 4h market/chain observation inside the snapshot's `+60s` allowance but after window end | Rejected as main-window broad context; may remain support |
| T10 | Entry quote refreshed during close allowance | Original entry boundary remains binding; no retroactive extension |
| T11 | Exact snapshot-bound context persisted after capture | Real evidence/evaluation timestamp retained; no backdating to snapshot time |
| T12 | Accepted deadline, category, fairness, and Lane-1 provenance regressions | Remain green; context timing does not alter deadline or cadence authority |
| T13 | Two sibling closes and slow context | Scheduler reselection/interleaving remains intact; correction does not recreate atomic close |
| T14 | Persistence/source/capability review | No new schema, source, retry loop, independent worker, or locked capability |

### 20.10 Interaction with deadline scheduling and remaining locks

`CLOSE_EVIDENCE` remains the cadence-sensitive phase. The accepted projection
remains unchanged:

```text
ordinary deadline_at =
    last_actual_snapshot_captured_at + dirty_above_gap_seconds

forced-close deadline_at = min(
    last_actual_snapshot_captured_at + dirty_above_gap_seconds,
    window_end_at + closing_clean_late_seconds
)

block_boundary_at =
    last_actual_snapshot_captured_at + max_clean_snapshot_gap_seconds
```

Missing truthful prior ACTUAL capture still produces UNKNOWN and no synthesized
deadline or CLEAN status. Context/audit timing cannot replace the prior capture,
modify `deadline_at`, alter cadence dirty/block thresholds, or become cadence
timing. Category-first selection remains:

```text
TRACK_FAST
> TRACK_NORMAL
> MEMORY_WINDOW_CLOSE
```

Within `MEMORY_WINDOW_CLOSE`, due evidence remains protected over context and
audit. That intra-category protection never lets close work leapfrog due
TRACK_FAST or TRACK_NORMAL work globally.

Still locked: observability/saturation implementation, Lane 3, Lane 4, Cycle 3,
new progression, 12h/24h, independent 5m memory, retrieval, BUY/SELL/HOLD,
positions, trades, paper-trade audits/PnL, wallet/private-key/signing/live
execution, paid APIs, scoring/ranking/confidence/weighted logic,
embeddings/vectors, new providers, new retries, schema/migrations, live
campaigns, and any Source Governor or Central Scheduler bypass.

### 20.11 Amended verdict

The post-capture timing contract is resolved without widening 15m, weakening
longer-window evidence law, changing accepted deadline projection, or reverting
the Scheduler-owned phase split:

`V2_9_8B_POST_CAPTURE_CONTEXT_TIMING_DESIGN_AMENDMENT_PASS_READY_FOR_CORRECTIVE_IMPLEMENTATION`

Exact next permitted work after independent acceptance of this documentation
commit is one narrow corrective implementation commit following Section 20.8,
or operator review. The current phase-split implementation is **not accepted**
by this verdict. Do not start observability/saturation or Lane 3.
