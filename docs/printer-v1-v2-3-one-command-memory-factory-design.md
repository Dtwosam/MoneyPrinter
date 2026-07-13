# V2-3 One-Command 15m Memory Factory Design

## Status And Verdict

`V2_3_ONE_COMMAND_DESIGN_PASS`

This document completes V2-3A through V2-3E as one audit/design lane. It does
not implement V2-4, activate runtime, fetch sources, mutate a database, or
generate memory.

Only `WINDOW_15M` is in scope. `WINDOW_5M_MICRO_EVENT` remains support-only.
`WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` remain blocked.

## 1. Source Stack And Evidence Reviewed

The design was checked against the active Printer stack: `AGENTS.md`, Clean
Master Spec, Post-RC Build Order, Memory Factory Guide, current-state memory-
growth audit, and active V2 memory-growth build order.

Subordinate Solana Builder references reviewed include the stack index, Source
Governor evidence rules, GeckoTerminal, DexScreener, PumpPortal, PumpSwap,
Solana RPC, and token-age evidence contracts. The V2-2E and qualified-random
closeouts and existing governed `WINDOW_15M` Memory Factory proofs were also
reviewed. External source modules define provider contracts; current Printer
code and tests define implemented behavior. Neither silently rewrites the
other.

## 2. V2-3A - Fragmented Command Audit

### 2.1 Current End-To-End Map

```text
printer-discover-candidates-once
  -> governed discovery requests
  -> normalize / STNP / dedup / lifecycle gates
  -> qualified seeded random active selection
  -> selection batch + tracking queue + pending scheduler jobs

operator prepares token list / chooses runner and timing
  -> printer-run-memory-factory-cycle or narrower E2J/E2T commands
  -> repeated governed snapshots
  -> WINDOW_15M close
  -> coverage/gap/context/memory quality gates
  -> clean or dirty/audit-only memory result
  -> closeout/report command
  -> safe stop
```

Discovery/selection and governed memory creation are separately proven. The
missing connection is an auditable run-level orchestration ledger that consumes
the selected batch, dispatches timed work through Central Scheduler, closes
each exact token/pair window, and emits one final report without an operator-
authored token list or command chain.

### 2.2 Step Audit Matrix

| Step | Existing command/function | Inputs | Outputs | Tables read | Tables written | Governor/scheduler boundary | Manual action now | Replay/failure behavior | Proof and gap |
|---|---|---|---|---|---|---|---|---|---|
| Discovery | `printer-discover-candidates-once`; `build_discover_candidates_once_payload()` | approved source, request budget, candidate cap, optional seed, DB | normalized candidates and source-budget report | source registry, tokens, pairs, lifecycle/rotation state | source requests/responses/failures, selection batch/items, eligible token/pair/candidate rows | Every request uses Source Governor; no timed scheduler execution | choose command/source/DB | bounded requests; failures recorded; empty pool stops | unassisted governed proof passed; unified cross-provider invocation unproven |
| Qualified selection | `build_qualified_random_active_selection()` after `_select_discovery_candidates()` and cooldown | clean active pool, target, seed | reproducible selected sample and diagnostic composition | selection rotation, existing identity/lifecycle state | selection batch/items; rotation after assembled batch | no source call; handoff creates pending scheduler rows | none inside command | same universe+seed reproducible; empty pool rejects | V2-2 qualified-random proof passed; legacy duplicate diagnostic remains |
| Tracking handoff | `process_discovery_payload(... create_tracking_handoff=True)` | selected exact mint/pair/source trace | token, pair, discovery, queue and job IDs | tokens/pairs/queue | tokens, pairs, discovery candidates, tracking queue, scheduler jobs | creates jobs through shared persistence path; does not execute | operator currently chooses later runner/input | duplicate/persistence gates apply; audit-only excluded | active handoff proven; selection-to-Memory-Factory consumption missing |
| Scheduler | `printer-run-scheduler-single-tick`; `build_scheduler_single_tick_payload()` | one pending due job | claimed/succeeded/failed job report | scheduler jobs and target tables | scheduler status/locks/errors | Central Scheduler boundary exists | operator invokes ticks; current generic handler is not full 15m dispatcher | one job only; claim/fail/complete; reports running locks | single-tick safety proven historically; snapshot/window-close dispatch wiring incomplete |
| Snapshot | `printer-collect-token-snapshots-once`; E2J snapshot-only path; `record_token_snapshot()` | exact approved token/pair, bounded source call | governed snapshot or skip reason | token/pair/tracking target | source rows, token snapshots, scheduler status through runner | Source Governor mandatory; timed cadence must be Scheduler-owned in V2-4 | operator supplies target or token list; Lane U controls loop/timing | source failure records and no snapshot; cadence gaps later block clean | governed snapshots proven; discovery-selected batch is not direct input |
| Window close | E2J/E2O/Lane Q/Lane K chain; `build_memory_window_once_payload()` | exact token/pair, start/end snapshot IDs, `WINDOW_15M`, cycle identity | memory window/episode/outcome/fingerprint or blocker | snapshots, source traces, context/evidence | memory windows, episodes/outcomes/fingerprints, coverage/gap audit rows | no direct source bypass; close must be scheduled | runner/window timing selection and token list | evidence identity and duplicate guards prevent source-reference-only duplicates | repeatable 15m and Lane U/U2 proofs passed; autonomous selected-batch close missing |
| Clean/dirty classification | Lane Q/E2Y/E2Z and memory audit helpers | completed window and all critical evidence | CLEAN_MEMORY or dirty/audit-only/do-not-train | memory, snapshots, context, source/evidence rows | quality/coverage/audit rows; clean episode only when gates pass | no source or scheduler bypass | separate report/audit invocation in some paths | missing/stale/dirty evidence fails closed; zero clean is valid | clean and blocked outcomes both proven in isolated paths |
| Final report | Lane U payload, E2U closeout, operator reports | run outputs and table counts | bounded closeout JSON/text | all scoped run/source/scheduler/memory tables | proposed run report row/file only | read-only aggregation after stop | operator chooses multiple reports/artifacts | current reports are lane-specific and fragmented | complete single-run report and one stop reason missing |
| Safe stop | Lane U stop checks plus scheduler lock checks | deadline, budget, failures, interruption | stopped/blocked/completed status | scheduler/run state | job/run final status and released locks | Central Scheduler must own all timed jobs | operator interruption handling varies by runner | Lane U is bounded, but lacks selected-batch run ledger | zero running jobs must be a V2-4 hard postcondition |

### 2.3 Missing Or Duplicated Connections

- Discovery writes tracking and scheduler handoffs, but current Memory Factory
  runners still depend on an operator-provided token-list path.
- Lane U contains a bounded timing loop and directly invokes governed E2J/Lane
  K helpers. V2-4 must reuse those helpers but move every timed action behind
  Central Scheduler job dispatch; it must not create a second scheduler.
- Snapshot collection exists in both the one-shot command and E2J runner path.
  V2-4 needs one shared scheduler handler, not duplicated source transport.
- Several reports expose overlapping counts, but no durable run ID/config hash
  joins discovery, scheduler, snapshots, windows, and final stop state.
- Duplicate memory guards are strong, while snapshot idempotency across a
  partially resumed orchestration needs an explicit scheduled-slot key.
- The V2-2 legacy duplicate diagnostic defect is reporting-only and must not be
  mistaken for identity-gate failure.
- Unified cross-provider discovery remains unproven. V2-4 must use only the
  currently approved production source plan; source expansion is not part of
  orchestration implementation.

## 3. V2-3B - One-Command Orchestration Design

### 3.1 Command Contract

Proposed future V2-4 command:

```text
printer-run-one-command-15m-memory-factory
```

PowerShell starts exactly one foreground process. The process creates no daemon,
background worker, independent source loop, or financial action.

### 3.2 Options And Defaults

| Option | Default | Rule |
|---|---|---|
| `--operator-approved` | false | Required or stop before writes |
| `--db-mode` | `proof` | First V2-4 proof accepts `proof` only |
| `--db-path` | none | Required isolated proof DB path |
| `--persistent-db-reference` | `data/printer_v1.sqlite3` | Hash/count reference only in first proof; never opened writable |
| `--backup-path` | none | Required pre-run proof DB backup/checkpoint |
| `--run-id` | generated UUID | Stable replay identity |
| `--resume-run-id` | none | Resume only an interrupted matching run |
| `--selection-seed` | generated once | Persist before shuffle; explicit value allowed |
| `--source-name` | `geckoterminal` | Existing approved production source plan only |
| `--max-source-requests` | `2` | Hard maximum for discovery; no hidden requests |
| `--max-selected-tokens` | `2` | First proof default; allowed range 1-10 |
| `--source-timeout-seconds` | `5` | Per discovery/snapshot request; Solana RPC-specific limits remain separate |
| `--max-retries` | `0` | No automatic retries in first proof |
| `--window-kind` | `WINDOW_15M` | Only accepted value |
| `--window-duration-seconds` | `900` | Fixed; not operator-shortenable for clean proof |
| `--fast-snapshot-interval-seconds` | `90` | Existing TRACK_FAST cadence policy |
| `--normal-snapshot-interval-seconds` | `180` | Existing TRACK_NORMAL cadence policy |
| `--max-total-duration-seconds` | `1200` | 15m window plus bounded setup/closeout allowance |
| `--report-path` | generated under ignored operator-run area | Final JSON plus human-readable summary; never source of DB truth |
| `--format` | `json` | `json` or `text` presentation only |

No option enables another timeframe, retrieval, paper decisions, financial
actions, paid sources, or score-like selection.

### 3.3 Required Operation Sequence

1. Validate operator approval, `proof` mode, paths, bounds, `WINDOW_15M`, and
   persistent-DB read-only reference.
2. Hash and count the persistent DB; create/verify the isolated proof DB backup.
3. Create a run ledger row with immutable config hash and `PREFLIGHT` status.
4. Reject active scheduler locks or a conflicting RUNNING orchestration.
5. Invoke the existing governed discovery/qualified-random production payload.
6. Persist the seed and exact selected mint/pair/source/selection identities in
   the run ledger. Audit-only candidates remain outside the active token set.
7. If no qualified token is selected, mark `SAFE_STOP_EMPTY_POOL`, create no
   timed jobs, emit the report, and exit successfully as a safe stop.
8. Convert selected tracking handoffs into run-owned scheduler jobs. Do not
   create a parallel token list.
9. Central Scheduler dispatches each due snapshot job to the shared governed
   E2J/DexScreener snapshot helper. TRACK_FAST and TRACK_NORMAL use their
   existing cadence policies per token.
10. Central Scheduler dispatches one window-close job per exact token/pair after
    900 real seconds, threading the first and last eligible snapshot IDs.
11. Reuse the existing coverage/gap/context/memory pipeline. Each token/pair
    independently becomes clean, dirty/audit-only, or blocked. Never force
    clean memory to satisfy yield.
12. Mark every run-owned scheduler job terminal. Any remaining RUNNING lock is
    a failed postcondition and forces `SAFE_STOP_LOCK_CLEANUP_FAILED`.
13. Build one report from run-ledger and DB rows, verify downstream zero-delta
    locks, re-hash the persistent DB, store final stop reason, and exit.

## 4. V2-3C - DB Safety And Replay Design

### 4.1 First-Proof Isolation

- The first V2-4 proof must create a fresh isolated DB under ignored `data/`.
- Apply existing migrations only to that proof DB.
- Create a byte-for-byte backup/checkpoint before the first orchestration write.
- Open the persistent DB only read-only for hash and count comparison.
- Refuse `--db-mode persistent` in V2-4's first implementation/proof.
- Never commit proof DBs, backups, operator-run files, or raw source artifacts.

### 4.2 Minimal Run Ledger Required In V2-4

V2-4 may add one narrowly scoped migration containing:

`printer_memory_factory_runs`

- unique `run_id`;
- immutable config hash and config JSON;
- DB mode and proof DB identity;
- selection policy version and seed;
- status, started/finished timestamps, stop reason;
- selected identity JSON and final report JSON.

`printer_memory_factory_run_steps`

- foreign-key `run_id`;
- unique `(run_id, step_key)`;
- categorical step kind/status;
- exact token/pair where applicable;
- scheduled slot/window boundary;
- source request/response/failure, scheduler job, snapshot, memory-window, and
  audit row references where applicable;
- started/finished timestamps and error/skip reason.

These tables coordinate proven components. They do not become a second source,
scheduler, memory store, or decision engine.

### 4.3 Transaction Boundaries

- Do not hold one SQLite transaction across network calls or the 15m wait.
- Transaction A reserves one run/step and commits `RUNNING` before work.
- Source Governor owns its existing request/response/failure transaction path.
- Transaction B records the returned references and terminal step status.
- Snapshot insertion remains inside the existing snapshot recorder transaction.
- Window-close/memory operations retain their existing atomic duplicate guards.
- Finalization transaction marks the run terminal only after job-lock and DB-
  delta checks complete.

### 4.4 Idempotency Keys

- Run: unique `run_id` plus immutable config hash.
- Discovery: `(run_id, discovery)` step and run-derived request keys.
- Selection: persisted batch ID, policy version, seed, and canonical eligible-
  universe identity hash.
- Snapshot: `(run_id, token_id, pair_id, scheduled_slot_at)` step key. A
  completed step reuses its snapshot/source references and never fetches again.
- Window close: `(run_id, token_id, pair_id, WINDOW_15M, window_start_slot)`.
- Memory: existing evidence identity hash, snapshot start/end identity, and
  duplicate guard remain authoritative.
- Report: `(run_id, final_report)`; rerendering may update an ignored file but
  must not duplicate DB evidence.

### 4.5 Partial Recovery And Replay

- A process interruption marks the run `INTERRUPTED` on the next foreground
  invocation after stale-lock inspection; it is never silently treated as pass.
- `--resume-run-id` requires the same DB, config hash, seed, and policy version.
- SUCCEEDED/SKIPPED steps are read, not rerun.
- A source step with a persisted response is not fetched again.
- A source step with a persisted failure remains failed in the zero-retry first
  proof; operator starts a new run for another attempt.
- A RUNNING step without a durable output is reconciled from referenced tables;
  if ambiguous, stop with `SAFE_STOP_AMBIGUOUS_PARTIAL_STEP`.
- A completed window never gets promoted or overwritten. New evidence creates a
  new distinct window/revision through existing rules.
- Replaying a terminal run is report-only and creates zero DB deltas.

### 4.6 Token/Pair Isolation And Rollback

- Every step stores non-null token ID, pair ID, mint, and pair address where
  applicable and revalidates exact equality before writing.
- One token/pair failure does not borrow another token's snapshots or context.
- No cross-token snapshot range, source response, fingerprint, or memory row is
  allowed.
- SQLite rollback applies only to the current short transaction. Completed
  governed source or snapshot evidence is not deleted to simulate all-or-nothing.
- Safe stop leaves honest partial evidence, terminal failed/skipped jobs, no
  active locks, and no clean memory unless every clean gate passed.
- Restore from backup is an operator decision outside automatic orchestration;
  the command never replaces the DB automatically.

## 5. V2-3D - Budgets, Stops, And Reporting

### 5.1 Categorical Hard Limits For First V2-4 Proof

| Budget | Limit |
|---|---|
| Selected active tokens | default 2; min 1; hard max 10 |
| Discovery source requests | default/hard max 2 |
| Snapshot requests | per-token cadence for one 900s window; max 10 TRACK_FAST or 5 TRACK_NORMAL attempts, plus no hidden attempt |
| Source timeout | 5s per market request; existing stricter adapter caps remain |
| Automatic retries | 0 |
| Scheduler jobs | max selected tokens multiplied by snapshot-attempt budget plus one close and one finalization job per token; hard report of planned/created/executed |
| Main windows | exactly one `WINDOW_15M` close attempt per selected exact token/pair |
| Total duration | 1200s hard elapsed limit |
| Concurrent job execution | one foreground scheduler dispatch at a time in first proof |
| Failed/dirty evidence | unlimited as honest outcomes within other budgets; never replaced by fabricated clean evidence |
| Operator interruption | immediate stop request; finish current short transaction, mark remaining jobs cancelled/skipped, release locks, report interruption |

The scheduler-job maximum is calculated before writes from selected lanes and
must be stored in the run config. Any unplanned job is a hard stop.

### 5.2 Stop Reasons

At least these exact categorical stop reasons must exist:

- `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`;
- `SAFE_STOP_EMPTY_QUALIFIED_POOL`;
- `SAFE_STOP_PREFLIGHT_FAILED`;
- `SAFE_STOP_SOURCE_BUDGET_EXHAUSTED`;
- `SAFE_STOP_SOURCE_FAILURE`;
- `SAFE_STOP_SNAPSHOT_COVERAGE_INSUFFICIENT`;
- `SAFE_STOP_WINDOW_CLOSE_BLOCKED`;
- `SAFE_STOP_TOTAL_DURATION_EXCEEDED`;
- `SAFE_STOP_OPERATOR_INTERRUPTED`;
- `SAFE_STOP_AMBIGUOUS_PARTIAL_STEP`;
- `SAFE_STOP_UNEXPECTED_DB_DELTA`;
- `SAFE_STOP_RUNNING_JOB_REMAINS`;
- `SAFE_STOP_PERSISTENT_DB_CHANGED`.

Dirty or zero clean memory is not itself a command failure. The report must
distinguish a safely completed dirty result from infrastructure failure.

### 5.3 Required Final Report

One report must include:

- run ID, config hash, DB mode/path, backup path, start/end/duration, version;
- qualified-random policy version, seed, eligible-pool size, every selected
  exact mint/pair/lane/source identity, and old category diagnostics;
- every source request, response, failure, request kind, channel, quality, and
  target identity;
- every scheduler job, planned slot, claim/status/error, and zero-running-lock
  postcondition;
- every snapshot attempt, created/skipped result, source references, cadence,
  price/liquidity/activity evidence, and evidence gap;
- each exact window's start/end snapshots, elapsed time, coverage/gap/context,
  duplicate status, memory quality, do-not-train state, and blockers;
- clean, dirty/audit-only, blocked, and zero-clean counts without forced yield;
- trajectory coverage available from existing repeated exact-pair evidence;
- replay mode, prior completed-step reuse, duplicate-prevention result, and all
  idempotency decisions;
- pre/post counts and deltas for source, discovery, selection, tracking,
  scheduler, snapshot, context, memory, audit, retrieval, and financial tables;
- persistent DB hash/count before and after first proof;
- explicit preserved locks and exact final stop reason;
- the legacy diagnostic duplicate issue and unified-provider limitation when
  still present.

## 6. V2-3E - Design Closeout

### 6.1 Implementation Acceptance Criteria

V2-4 implementation is acceptable only when focused deterministic tests prove:

1. one command invokes existing governed discovery and qualified seeded random
   selection without an operator token list;
2. every source request passes Source Governor;
3. every timed snapshot/window action is represented and dispatched by Central
   Scheduler, with no Lane-U-style independent timing loop;
4. only `WINDOW_15M` is accepted and 5m remains support-only;
5. exact mint/pair identity survives every step;
6. audit-only and unselected candidates create no active timed work;
7. same config/universe/seed is reproducible;
8. completed-step resume creates no duplicate source call, snapshot, window,
   episode, fingerprint, or audit row;
9. interruption and every budget breach stop with zero RUNNING jobs/locks;
10. dirty, stale, failed, missing, conflicting, or incomplete evidence cannot
    become clean memory;
11. zero clean memories is a valid honest result;
12. first proof cannot write the persistent DB;
13. retrieval and every paper/financial table remain zero-delta;
14. final report contains every required field and one exact stop reason.

Implementation must reuse proven helpers. It may add only the minimal run/step
ledger migration, orchestration module, CLI entry point, scheduler handlers,
and focused tests/reporting needed by this design.

### 6.2 Bounded V2-4 Proof Plan

After deterministic tests pass and code is frozen:

1. create a fresh migrated isolated proof DB and backup;
2. hash/count the persistent DB read-only;
3. run exactly one operator-approved command with GeckoTerminal's existing
   approved plan, max two discovery requests, max two selected tokens, zero
   retries, lane-aware cadence, one real 900s window, and 1200s total cap;
4. allow any natural selection composition and clean/dirty result;
5. do not rerun because selection or memory yield is poor;
6. verify all jobs terminal, report complete, persistent DB unchanged, and all
   retrieval/financial deltas zero;
7. run one report-only replay of the terminal run only if the approved proof
   explicitly includes idempotency verification; that replay must make no
   source call or DB evidence write.

The first proof must not use PumpPortal/PumpSwap expansion, another timeframe,
fixtures in the live portion, manual candidate insertion, or threshold changes.

### 6.3 Money-Usefulness Contribution

V2-3 converts independently proven pieces into a reviewable plan for collecting
honest 15m trajectories from autonomously selected active tokens. A single
bounded command reduces operator stitching errors, preserves exact evidence
lineage, and makes failed/dirty runs as visible as clean runs. This improves the
future memory corpus without claiming profit, predicting outcomes, or enabling
decisions.

### 6.4 What V2-3 Improves

- One explicit orchestration contract instead of fragmented operator steps.
- Central ownership of time and job state.
- Durable replay/idempotency semantics.
- Proof/persistent DB separation.
- Exact budgets and safe-stop categories.
- One complete source-to-memory report.
- Clear V2-4 coding and proof acceptance criteria.

### 6.5 What V2-3 Does Not Unlock

V2-3 does not implement or activate V2-4, source fetching, scheduler/runtime,
snapshots, memory generation, clean-memory promotion, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, paid
APIs, scoring, ranking, confidence, weights, embeddings, or vectors.

## 7. Functionality Risks / Setbacks / Efficiency Blockers

| Risk/blocker | Why it matters | Required V2-4 mitigation | Stop condition |
|---|---|---|---|
| Discovery-selected rows are not current Memory Factory input | Operator token-list stitching can mix identity | consume assembled selection batch/run identities directly | token list or manual mint required |
| Lane U owns timing internally | Could bypass true scheduler ownership | Central Scheduler job handlers own every due action | independent sleep/source loop appears |
| Generic scheduler handler coverage is incomplete | Jobs may exist but not execute intended work | explicit snapshot/window/finalize handlers using proven helpers | unknown job kind or direct helper call |
| No durable run ledger | Cannot reconcile partial runs | minimal run and step tables with config hash | ambiguous resume state |
| Snapshot duplicate prevention lacks scheduled-slot identity | Replay could refetch or duplicate | unique run/token/pair/slot step key | duplicate snapshot/source call on resume |
| Long SQLite transaction | Locks DB during network/wait | short reserve/result transactions | transaction spans source call or wait |
| Legacy duplicate diagnostic false positives | Misleading final report | fix reduced identity input or clearly classify diagnostic | report claims real dedup failure |
| Unified cross-provider path unproven | Coverage may remain source-concentrated | report limitation; no provider expansion in V2-4 | hidden provider fan-out |
| Natural sample produces zero clean memory | Temptation to force yield | zero clean explicitly valid | threshold/evidence weakened |
| Dirty evidence crosses token/pair | Corrupts memory | exact identity on every step/reference | cross-token evidence detected |
| Interruption leaves RUNNING locks | Blocks future runs | reconciliation and terminal cleanup | any lock remains after exit |
| Report assembled from files rather than DB references | Can drift from truth | ledger/table references authoritative | unverifiable report field |
| Persistent DB accidentally targeted | First proof blast radius | proof-only mode and hash/count guard | persistent hash/count changes |
| Financial/retrieval drift | Violates V1 | zero-delta postcondition | any forbidden row delta |

## 8. Final Closeout

The existing components are sufficiently proven and the orchestration contract
is sufficiently explicit for V2-4 implementation without inventing architecture
during coding. V2-4 must connect existing helpers through Central Scheduler and
the minimal run ledger exactly as designed; it must not redesign discovery,
selection, sources, snapshots, memory quality, or financial boundaries.

Verdict: `V2_3_ONE_COMMAND_DESIGN_PASS`.

Next lane, only after explicit operator approval:

`V2-4 - Implement one-command WINDOW_15M Memory Factory orchestration`.
