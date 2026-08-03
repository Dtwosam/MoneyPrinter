# Printer V1 V2-9.8B Post-Rollover-2 Exact Public Composition Discovery Scheduler Claim-Coverage Blocker Audit

Date: 2026-08-03

Linear: `DTW-24`

Lane:
`V2-9.8B Post-Rollover-2 Exact Public Composition Discovery Scheduler Claim-Coverage Blocker Audit`

Lane type: read-only blocker audit and documentation only.

Parent proof lane: `DTW-23`

Accepted production repair HEAD:
`089eb38651874d9b3ec4a4ce04600d45ea401b05`

Consumed authorization:
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

The consumed authorization remains permanently non-reusable. This audit does not
authorize a repair, a proof run, provider contact, authoritative DB mutation,
wrapper use, operational execution, memory generation, retrieval, decisions,
positions, trades, audits, PnL, longer windows, or a fresh authorization.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_COVERAGE_BLOCKER_ROOT_CAUSE_CONFIRMED`

Exact root cause:

The operational discovery path books real Central Scheduler rows for each
discovery work unit, executes the work **synchronously in-process** while the
Scheduler job remains `PENDING`, then terminalizes the job through the committed
Scheduler owners `complete_job` / `fail_job` / `cancel_job` **without ever calling
`claim_due_job`**.

Full-run accounting's independent transition coverage contract requires every
observed non-`CANCELLED` job to show:

```text
SCHEDULER_ENQUEUE + SCHEDULER_CLAIM + SCHEDULER_TERMINAL
```

Discovery jobs therefore record honest `SCHEDULER_ENQUEUE` and successful
`SCHEDULER_TERMINAL` while missing `SCHEDULER_CLAIM`, failing
`scheduler_transition_coverage_complete` and the final campaign acceptance gate.

Classification:

| Candidate cause | Status |
| --- | --- |
| Scheduler execution omission of claim on discovery work | **Confirmed primary cause** |
| Transition-observer omission | **Rejected** — observer faithfully records only real Scheduler boundaries |
| Incorrect accounting classification | **Rejected as primary** — written contract requires claim for non-cancelled terminals; contract is consistent with lifecycle/working paths |
| Public-composition / test assumption | **Rejected** — exact public composition uses the real public coordinator → owner → origin driver → factory chain |
| Synthetic claim injection as a fix | **Explicitly rejected** unless a real `claim_due_job` transition is performed by the Scheduler owner |

Evidence gap for the root cause: **none**. Remaining open items are repair design
choices only, not uncertainty about where claim is missing.

## 2. Exact baseline and method

| Item | Exact value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Audit start HEAD | `8fb4256c70d4e81660c177238253322cb37ae947` |
| Accepted production repair HEAD | `089eb38651874d9b3ec4a4ce04600d45ea401b05` |
| Parent proof lane | `DTW-23` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` (permanently non-reusable) |
| Supporting patch (read-only) | `/tmp/dtw23-scheduler-claim-blocker-proof.patch` present |

Method (allowed only):

- static inspection of the active Printer source stack and Python builder/accounting
  owners;
- read-only review of Scheduler enqueue/claim/terminal owners;
- discovery request/work wiring and public operational coordinator;
- authoritative live operational owner path;
- exact public composition test and directly relevant Scheduler-transition tests;
- parent token-slot repair design/implementation/closeout reports;
- read-only supporting patch evidence.

Forbidden and not performed:

- source or test modification;
- synthetic claim injection;
- discovery, Scheduler, campaign, factory, or operational command execution;
- provider/RPC/WebSocket contact;
- authoritative DB mutation;
- new authorization;
- retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL;
- 1h or longer windows.

## 3. Observed blocker (DTW-23 parent)

The corrected disposable offline composition:

- used Migration 050;
- contacted no network source;
- passed 155 directly affected regressions and 6 subtests;
- completed two `WINDOW_15M` closes;
- left zero active/locked residue;
- failed final accounting acceptance because discovery Scheduler jobs `1–10`
  recorded `SCHEDULER_ENQUEUE` and successful `SCHEDULER_TERMINAL`, but no
  `SCHEDULER_CLAIM`.

This audit does not re-run that composition. Static ownership tracing fully
explains the missing-claim pattern on the real production discovery path used by
the public composition.

## 4. Producer / consumer / observer transition table

### 4.1 Central Scheduler transition owners

| Boundary | Owner function | File | Emits observer event | DB effect |
| --- | --- | --- | --- | --- |
| Enqueue | `enqueue_job` | `src/printer_v1/scheduler/scheduler.py` | `SCHEDULER_ENQUEUE` via `_observe` | Insert `printer_scheduler_jobs` as `PENDING` |
| Claim | `claim_due_job` | same | `SCHEDULER_CLAIM` via `_observe` | `PENDING`/`COOLDOWN` → `RUNNING`; set `lock_owner` / `locked_at` / `started_at` |
| Terminal success | `complete_job` | same | `SCHEDULER_TERMINAL` (`SUCCEEDED`) | Clear lock; set `finished_at` |
| Terminal fail | `fail_job` | same | `SCHEDULER_TERMINAL` (`FAILED` or `COOLDOWN`) | Retry/cooldown or fail |
| Terminal cancel | `cancel_job` | same | `SCHEDULER_TERMINAL` (`CANCELLED`) | Clear lock; cancel |

Observer plumbing:

- `set_scheduler_operation_observer` / `reset_scheduler_operation_observer` ContextVar
  in `scheduler.py`;
- public coordinator installs the observer in
  `operational_memory_factory_command.py` around the operational owner run and
  copies observed events into the action-local ledger for accountable job IDs.

### 4.2 Discovery job call chain (affected path)

```text
public_command._run_operational_campaign
  -> AuthoritativeLiveOperationalCampaignOwner / operational owner
  -> origin_lifecycle_campaign driver
  -> CombinedDiscoveryExecutor (combined_executor.py)
       _create_work:
         enqueue_job(... job_kind=DISCOVERY_REFRESH ...)   # SCHEDULER_ENQUEUE
         insert_discovery_work(... work_state="RUNNING")  # discovery work only
         # claim_due_job is never called
       <synchronous lane/merge/gates/selection/handoff work>
       _terminalize_work / reconcile_discovery_work_jobs:
         terminalize_scheduler_job_for_work
           -> complete_job / fail_job / cancel_job           # SCHEDULER_TERMINAL
  -> full_run_stage_observer projects DISCOVERY_SELECTION_SCHEDULER identities
  -> action-local ledger observes runtime Scheduler transitions for those job IDs
  -> evaluate_campaign_acceptance_gate requires
       scheduler_transition_coverage_complete
```

Key discovery owner facts:

| Step | Owner | Claim? |
| --- | --- | --- |
| Create discovery work + Scheduler row | `CombinedDiscoveryExecutor._create_work` | No |
| Set discovery work running | `insert_discovery_work(..., work_state="RUNNING")` | No — only the discovery work row, not the Scheduler job |
| Execute provider/merge/gates/selection/handoff | Combined executor in-process | No Scheduler claim loop |
| Terminalize discovery work | `_terminalize_work` | No claim |
| Terminalize linked Scheduler job | `terminalize_scheduler_job_for_work` in `discovery/scheduler_parity.py` | No claim; calls `complete_job` / `fail_job` / `cancel_job` only |
| Batch failure cleanup | `reconcile_discovery_work_jobs` | Same parity owner; no claim |

`scheduler_parity.py` documents the V2-9.7E.47 A2 repair: discovery work must not
leave linked Scheduler jobs `PENDING` after work terminalization. That repair
added **terminal** ownership only. It did not add **claim** ownership.

### 4.3 Accounting consumer contract

`CampaignActionLocalLedger.scheduler_transition_coverage()` in
`campaign_six_unit_accounting.py`:

```text
required = {SCHEDULER_ENQUEUE, SCHEDULER_TERMINAL}
if terminal_state != "CANCELLED":
    required.add(SCHEDULER_CLAIM)
```

Acceptance gate
`evaluate_campaign_acceptance_gate` → check
`scheduler_transition_coverage_complete` requires
`scheduler_transition_coverage.complete == True`.

Therefore:

| Terminal path | Claim required by accounting? |
| --- | --- |
| `SUCCEEDED` via `complete_job` | **Yes** |
| `FAILED` via `fail_job` | **Yes** |
| `CANCELLED` via `cancel_job` | **No** (explicit exemption) |

Discovery successes and failures that terminalize without claim fail the gate.
Cleanup/cancel-only residue can still pass the claim requirement for those
cancelled job IDs.

### 4.4 Transition table by job family

| Job family | Producer | Claim owner | Terminal owner | Observed transitions on public path | Coverage result |
| --- | --- | --- | --- | --- | --- |
| Discovery `DISCOVERY_REFRESH` work units | `combined_executor._create_work` → `enqueue_job` | **None in production discovery path** | `scheduler_parity.terminalize_scheduler_job_for_work` → `complete_job`/`fail_job`/`cancel_job` | ENQUEUE + TERMINAL (no CLAIM for non-cancelled) | **Incomplete** — matches observed jobs `1–10` |
| First-15m handoff `TRACK_NORMAL_FIRST_15M` | `combined_executor` handoff `enqueue_job` | Factory `claim_due_job` when steps run | Factory `complete_job` / cleanup `cancel_job` | ENQUEUE + CLAIM + TERMINAL when factory executes | Complete when executed as claimed factory work |
| Lifecycle `SNAPSHOT` / `WINDOW_CLOSE` | `one_command_15m_factory` plan/enqueue | `claim_due_job` in factory step loop | `complete_job` in factory step loop | ENQUEUE + CLAIM + TERMINAL via lifecycle observer | Complete — working path |
| Unified cleanup cancellation | residue scan | N/A | `cancel_job` | TERMINAL `CANCELLED` (claim not required) | Complete under cancel exemption |

## 5. Are discovery jobs genuine async work or synchronous reservation rows?

They are **hybrid bookkeeping rows for synchronous reservation/accounting work**,
not jobs executed by a Central Scheduler claim loop.

Evidence:

1. `_create_work` immediately inserts `printer_discovery_work` with
   `work_state="RUNNING"` after enqueue, while the Scheduler job stays
   `PENDING`.
2. All discovery lane work (direct/secondary providers, identity merge, origin,
   PumpSwap, gates, selection, handoff) runs inside the same executor call stack.
3. No discovery module imports or calls `claim_due_job`.
4. Ceiling `INTAKE_SCHEDULER_WORK = 11` and `WORK_TYPES_ORDER` (11 named discovery
   work types) treat Scheduler rows as intake accounting units.
5. After V2-9.7E.47, terminal parity forces those rows to a terminal Scheduler
   status so residue cleanup does not see stranded `PENDING` jobs.

They are still **real** `printer_scheduler_jobs` rows with real enqueue and
terminal transitions, projected into `DISCOVERY_SELECTION_SCHEDULER` ownership and
six-unit `SCHEDULER_WORK_ITEM` identities. Accounting therefore treats them as
full Scheduler work items and requires full transition coverage for non-cancelled
terminals.

## 6. Is claim contractually mandatory for this job type and terminal path?

Yes, under the **current full-run accounting contract**, for every non-cancelled
terminal.

Not under the **current discovery execution model**, which never claims.

That is the contract collision:

- Scheduler primitive contract: claim is the only owner that moves a job to
  `RUNNING` with lock ownership.
- Discovery execution model: work runs while the job remains unclaimed
  `PENDING`, then jumps to terminal via parity.
- Accounting C7 / `scheduler_transition_coverage`: non-cancelled jobs must show
  enqueue/claim/terminal.

This audit does **not** assume the accounting contract is wrong. The accounting
gate correctly detects that discovery non-cancelled jobs never entered the claim
boundary that lifecycle jobs use.

## 7. Earliest divergence from a working claimed-job path

Working lifecycle path (`one_command_15m_factory.py`):

```text
enqueue_job
  -> claim_due_job(lock_owner=...)
  -> execute step
  -> complete_job
```

Observed discovery path:

```text
enqueue_job
  -> (no claim_due_job)
  -> execute discovery work synchronously
  -> complete_job / fail_job / cancel_job
```

Earliest divergence point:

**Immediately after enqueue / at discovery-work start**, when discovery marks its
own work row `RUNNING` without claiming the linked Scheduler job.

Secondary divergence at terminalization:

`terminalize_scheduler_job_for_work` terminalizes from `PENDING` without a claim
transition. `complete_job` does not require prior `RUNNING` status; it updates
status to `SUCCEEDED` directly. That allows the missing-claim path to leave zero
active residue while still failing transition coverage.

## 8. Cause determination

### 8.1 Confirmed

**Scheduler claim omission on the discovery execution/terminal path.**

Root owner boundary:

- missing claim: never present in `combined_executor` / `scheduler_parity`;
- present terminal: `scheduler_parity` → `complete_job`/`fail_job`/`cancel_job`;
- present observation: public coordinator ContextVar observer records real
  boundaries only.

### 8.2 Explicitly rejected

| Hypothesis | Why rejected |
| --- | --- |
| Transition-observer omission | Observer is installed and records ENQUEUE/TERMINAL; CLAIM cannot be observed because `claim_due_job` never runs |
| Accounting false positive | Contract matches C7 and working lifecycle path; cancel exemption is intentional and limited |
| Composition-test-only artifact | Public composition uses real coordinator/owner/driver/factory; production path shares the same discovery claim omission |
| Synthetic claim injection as truth | Would forge a transition the Scheduler owner never performed; forbidden by this lane and by evidence law |
| Token-slot repair regression | Accepted repair HEAD only projected durable `token_slot_id`; claim omission is older discovery/parity design relative to full-run transition coverage |

### 8.3 Historical context (not a new invention)

V2-9.7E.47 A2 repaired stranded `PENDING` discovery jobs by adding terminal
parity. Full-run accounting later required claim coverage for non-cancelled jobs.
The public composition now exercises both together and fails closed at final
acceptance after otherwise successful two-token `WINDOW_15M` closeout.

## 9. Production reachability

**Yes. The same condition can occur on the real operational command.**

Reason:

1. Public operational coordinator
   (`operational_memory_factory_command.py`) is the exact composition surface.
2. It installs the Scheduler operation observer, projects discovery Scheduler
   identities at `DISCOVERY_SELECTION_TERMINAL`, and feeds non-factory accountable
   job transitions into the action-local ledger.
3. Final acceptance calls `evaluate_campaign_acceptance_gate`, which requires
   `scheduler_transition_coverage_complete`.
4. The authoritative/live operational owner path uses the same origin driver and
   combined discovery executor.

Therefore a live ordinary `WINDOW_15M` attempt on the restored operational path
can complete discovery, open lifecycle, close two windows, cleanup residue to
zero, and still fail final full-run acceptance on discovery claim coverage.

No new authorization or live attempt is authorized by this finding.

## 10. Blast radius

| Area | Impact |
| --- | --- |
| Discovery `DISCOVERY_REFRESH` work units | **Direct** — all non-cancelled discovery jobs lack claim on the operational path |
| Selection work (`DISCOVERY_UNIFORM_SELECTION`) | **Direct** — same `_create_work` / parity path |
| Handoff discovery work rows (`DISCOVERY_TRACKING_HANDOFF_SLOT_*`) | **Direct** for their discovery work Scheduler rows if terminalized via parity without claim |
| First-15m handoff `TRACK_NORMAL_FIRST_15M` jobs | **Indirect / mixed** — enqueued by discovery, claimed when factory executes them; not the same defect as discovery work rows |
| Holder evidence | **Not the claim defect** — holder facts are eligibility inputs; no separate missing-claim owner found as the DTW-23 jobs `1–10` pattern |
| Snapshot / window-close lifecycle jobs | **Not affected** — factory claim/complete path is the working reference |
| Cleanup cancellation | **Not affected** — cancel terminal exempt from claim requirement |
| Zero-active residue checks | **Not affected** — jobs are terminally closed; residue can be zero while coverage is incomplete |
| Full-run campaign acceptance | **Direct blocker** after otherwise successful lifecycle |
| Retrieval / decisions / positions / PnL | **Still locked**; this defect does not unlock them |

Jobs `1–10` in the observed parent proof align with the first batch of discovery
Scheduler rows created by intake work (`_create_work` / lane work types), not
with the 18 lifecycle snapshot/close jobs.

## 11. Historical PASS claims

| Historical surface | Affected by this defect? |
| --- | --- |
| Fixture full-run accounting tests that inject synthetic ENQUEUE/CLAIM/TERMINAL for pre-lifecycle jobs | Not production proof; their PASS remains fixture-local and does **not** prove live discovery claim behavior |
| Wiring integration tests that call `claim_due_job` themselves for fixture jobs | Same — fixture-owned claim, not combined-executor claim |
| V2-9.7E.47 discovery/Scheduler parity PASS | Still valid for its repaired goal (no stranded PENDING jobs); it never claimed to emit CLAIM transitions |
| Token-slot projection repair source conformance PASS | Unaffected; different boundary |
| Token-slot independent closeout blocked on proof-evidence gap | Unaffected root; DTW-23/24 are the evidence-completion / claim-coverage successors |
| Any prior live operational PASS under current full-run acceptance with real discovery identities | Static production code shows discovery never claims; any such PASS would require separate durable transition evidence and is not revalidated here |

This audit does **not** rewrite historical lane verdicts. It states that historical
fixture PASSes with synthetic claims are not substitutes for a production claim
owner on discovery jobs.

## 12. Smallest safe repair boundary (justified; not authorized)

Justified boundary only if a later implementation lane is approved:

1. **Primary preferred boundary** — discovery work start claim:
   - In the real discovery Scheduler owner path (`_create_work` or an immediately
     following owned helper), call `claim_due_job` on the newly enqueued job with a
     deterministic `lock_owner` identifying the discovery work/batch owner before
     governed work proceeds.
   - Keep existing parity terminalization through `complete_job` / `fail_job` /
     `cancel_job`.
   - Resulting real transitions: ENQUEUE → CLAIM → TERMINAL.
   - This is a real Scheduler owner claim, not a synthetic ledger injection.

2. **Not acceptable without separate design approval**:
   - Injecting `SCHEDULER_CLAIM` events into the action-local ledger without
     `claim_due_job`;
   - Weakening `scheduler_transition_coverage` to drop claim for discovery
     successes solely to green the composition;
   - Writing Scheduler status with raw SQL outside the Central Scheduler owner;
   - Broad Scheduler refactor, Source Governor changes, or accounting-law rewrite
     beyond the discovery claim boundary;
   - Re-opening retrieval, decisions, positions, or longer windows.

3. **Cancel path** remains claim-exempt under current accounting; do not invent
   claims for pure cancel residue.

This audit authorizes **none** of the above. It only bounds the future repair.

## 13. Minimum focused implementation proof required later

After an approved implementation lane (not this audit):

1. Disposable Migration-050 database only.
2. Offline exact public composition proof (public coordinator → authoritative
   owner → origin driver → one-command factory) with frozen transports and no
   network.
3. Assert for every accountable discovery Scheduler job identity:
   - durable job row terminal;
   - observed transitions include ENQUEUE, CLAIM, TERMINAL in order for
     non-cancelled terminals;
   - `claim_due_job` produced `RUNNING` with lock fields before terminal;
   - no synthetic claim-only ledger rows without matching Scheduler status history.
4. Assert lifecycle snapshot/close jobs still show full claim coverage.
5. Assert two `WINDOW_15M` closes, zero active/locked residue, integrity/FK clean.
6. Assert `scheduler_transition_coverage.complete is True` and campaign acceptance
   `CAMPAIGN_PASS` (or honest fail if other independent gates fail).
7. Negative proof: with claim deliberately omitted on one discovery job, coverage
   fails closed.
8. Focused regressions only: exact public composition, discovery/Scheduler parity,
   full-run wiring/accounting transition tests. No broad suite expansion required
   for the repair lane itself.

## 14. Money-usefulness contribution

This blocker sits on the last honest acceptance gate after two real disposable
`WINDOW_15M` closes. Until discovery Scheduler claim coverage is real, Printer
cannot claim a full-run operational PASS for the restored factory path. Without
that PASS, clean-memory growth remains unproven at the ordinary campaign
acceptance surface, and later retrieval/decision value stays correctly locked.

The audit preserves capital discipline by refusing synthetic claim greening and by
keeping financial capabilities locked.

## 15. What this audit improves

- Names the exact missing owner call (`claim_due_job`) and the exact discovery
  owner chain that omits it.
- Separates residue-zero terminalization success from transition-coverage failure.
- Protects the accounting claim requirement from being misread as a test-only
  quirk.
- Bounds the smallest real repair to discovery claim at work start via the
  Scheduler owner.
- Rejects forged claim observations as non-evidence.

## 16. What remains locked

- source/test modification in this lane (audit report only);
- synthetic claim injection;
- discovery/Scheduler/campaign/factory/operational execution by this audit;
- provider/RPC/WebSocket contact;
- authoritative DB mutation;
- reuse of `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`;
- fresh authorization;
- retrieval activation;
- paper decisions;
- BUY / SELL / HOLD;
- paper positions, trade events, paper audits, PnL;
- live execution, wallets, private keys;
- paid APIs;
- scoring / ranking / confidence / weighted logic;
- embeddings / vectors;
- 1h / 4h / 12h / 24h production windows as main outcomes;
- N2/N7 candidate-acquisition operational prerequisite restoration.

## 17. Required proof

This audit lane requires only documentation review and the report commit.
Implementation and the focused claim-coverage proof above are future lanes.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Detail |
| --- | --- |
| Functionality | Ordinary full-run acceptance remains blocked after successful two-token lifecycle if discovery jobs stay unclaimed |
| Setback | V2-9.7E.47 terminal parity fixed residue but left claim gap relative to later full-run transition coverage |
| Efficiency | Re-running broad suites will not reveal a new root cause; the defect is static and path-local |
| Repair risk | Claiming too late (only at terminal) would be weaker evidence than claim-at-work-start; still better than synthetic observation |
| Over-repair risk | Weakening accounting claim law would hide other real unclaimed execution bugs |
| Proof risk | Fixture tests that inject claims can green without production claim ownership; future proof must use the real public composition path |
| Operational risk | Live attempts under a fresh authorization would hit the same acceptance blocker; do not burn authorization before repair + offline proof |
| Residual awareness | Secondary lanes that skip unplanned providers create fewer discovery jobs; job count may vary, but any non-cancelled discovery job without claim fails coverage |

## 19. Smallest safe next lane

```text
V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Repair Design
```

Design/specification only. It may define:

- exact claim owner and lock_owner identity at discovery work start;
- ordering relative to enqueue, governed requests, and parity terminalization;
- failure semantics if claim is not acquired;
- interaction with cancel/fail/reconcile paths;
- focused offline proof plan and negative cases;
- non-goals: synthetic claims, accounting weakening, financial unlocks.

It may not implement the repair, run the composition, contact providers, mutate
authoritative state, issue authorization, or unlock later capabilities.

## 20. Files inspected (read-only)

Primary:

- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/scheduler/scheduler.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/scheduler_parity.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py`
- `tests/test_v2_9_8b_full_run_wiring_integration.py`
- `tests/test_v2_9_8b_full_run_accounting_semantics_correction.py`
- `/tmp/dtw23-scheduler-claim-blocker-proof.patch`
- parent token-slot repair design/implementation/closeout docs under `docs/`

## 21. Final statement

Discovery Scheduler jobs are real rows used as synchronous intake accounting
units. They are enqueued and terminalized by committed Scheduler owners, but they
are never claimed on the operational discovery path. Full-run accounting
correctly fails closed when those non-cancelled jobs lack `SCHEDULER_CLAIM`.
The smallest safe future repair is a real `claim_due_job` at discovery work start,
followed by focused offline exact-public-composition proof. Synthetic claim
injection is rejected.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_COVERAGE_BLOCKER_ROOT_CAUSE_CONFIRMED`
