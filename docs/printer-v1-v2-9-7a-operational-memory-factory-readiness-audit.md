# Printer V1 V2-9.7A Operational Memory Factory Readiness Audit

## Executive Verdict

`V2_9_7A_OPERATIONAL_READINESS_AUDIT_PASS`

The audit is complete and produces a reliable repair and design map. This PASS
does not mean that operational activation is ready.

The current repository cannot yet support the required bounded operational
command against the persistent corpus. Its strongest end-to-end path is still
explicitly proof-only: it rejects the persistent DB, requires a proof DB and
proof backup, permits continuous 15m -> 1h -> 4h only for one token, captures
5m support whenever that continuous path is enabled rather than conditionally,
and depends on proof-specific supervision.

The underlying evidence machinery is substantially ready. Attempt 7 proved one
exact-token, exact-pair, real-cadence lifecycle through governed discovery,
15m, 1h, 4h, audit, and clean E2Z promotion. The remaining work is an
operational product boundary, selective multi-token campaign policy, persistent
schema and recovery safety, lifecycle integration, and reporting/supervision
repair. No further four-hour proof is required before those lanes.

Operational activation remains blocked.

## Todo / Checklist

- [x] Verify exact clean baseline and inactive runtime/lock state.
- [x] Read the active Printer and relevant Solana Builder source stack.
- [x] Inspect current command, scheduler, persistence, lifecycle, reporting,
  supervision, and evidence boundaries statically.
- [x] Query the persistent and latest V2-9 proof DBs read-only where current
  repository evidence was necessary.
- [x] Classify readiness and map each blocker to the smallest later lane and
  minimum sufficient proof.
- [x] Preserve every retrieval, paper, financial, wallet, and live-execution
  lock.

## Preflight

- HEAD: exact `7f30283` (`Adopt operational memory growth program`).
- Tracked tree: clean before this document was created.
- Runtime: no Python process was active. No Printer runtime was started.
- One-proof lock: `operator-runs/v2-9-one-proof.lock.json` was absent.
- Unrelated untracked artifacts under the repository root, `data/`, and
  `operator-runs/` were inspected only when read-only evidence was needed and
  were otherwise untouched.
- DB access: SQLite URI `mode=ro` with `PRAGMA query_only=ON`; no DB was
  modified.

## Source Stack and Authority

Read as the active Printer stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-9-final-closeout.md`
- `docs/printer-v1-post-v2-9-operational-memory-growth-adoption-closeout.md`

Read as subordinate Solana Builder evidence rules:

- `docs/solana-builder-source-of-truth/README.md`
- `docs/solana-builder-source-of-truth/source-governor-evidence-rules.md`

The Builder stack remains subordinate to Printer product law. Its evidence
rules confirm that source claims must remain source-specific, governed,
provenance-preserving, and unable to unlock memory, retrieval, or financial
capabilities by themselves.

## End-to-End Readiness Map

| Required stage or control | Status | Current evidence | Operational conclusion |
|---|---|---|---|
| Discovery | READY | `build_discover_candidates_once_payload()` uses bounded governed source plans; Attempt 7 sampled two GeckoTerminal channels with 40 candidates seen and zero source failures | Current discovery is productive; no old zero-yield count is carried forward |
| Selection | PARTIAL | Qualified random active selection, exact provenance, cooldown gates, batch persistence, and rotation-state writes exist | Works on a migrated proof DB; persistent DB lacks selection tables and repeated campaign behavior is unproved |
| Tracking handoff | PARTIAL | Discovery creates tracking queue and scheduler handoffs; the factory reads selected batch targets | Factory cancels discovery scheduler handoffs but does not complete queue lifecycle; persistent DB still contains old `QUEUED` rows |
| Governed collection | READY | Snapshot and context collection use Source Governor adapters and scheduler rows; budgets fail closed | Ready as reusable machinery, not as an operational command |
| Conditional 5m support | PARTIAL | Exact-linked support window is created from the same run/token/pair/15m stream and remains audit/support-only | Capture is mandatory whenever continuous 1h is enabled; no event-based conditional gate exists |
| Main 15m closeout | READY | Current cadence policy is enabled; exact close, audit, Lane Q/Lane K/E2Z path is proven | Reusable after operational persistence boundary exists |
| Selective 1h continuation | PARTIAL | Exact current-run 15m predecessor and 24/24 real-cadence continuation are proven | `continuous_first_hour` is a run-wide flag and requires exactly one selected token; per-token selective eligibility is absent |
| Conditional 4h continuation | PARTIAL | Exact 1h predecessor and 61/61 real-cadence 4h path are proven | Explicit proof mode, disabled cadence policy override, and exactly one token are still required |
| Clean/dirty/blocked audit | PARTIAL | E2Q, Lane Q, Lane K, and E2Z preserve evidence quality and idempotent clean promotion | Run-level report reads the pre-promotion window and under-counts authoritative clean episodes |
| Cooldown | BLOCKED | Standalone X3 cooldown functions exist | Not invoked by the one-command factory or a campaign loop |
| Archive | BLOCKED | Standalone archive/reopen functions exist | No automatic terminal policy or campaign integration |
| Candidate rotation | PARTIAL | `printer_selection_rotation_state` and cross-batch cooldown code exist; Attempt 7 wrote one row | Persistent DB lacks migration 026; multi-cycle rotation and revival behavior are unproved |
| Persistent corpus reporting | PARTIAL | Rich final proof report contains source, cadence, budget, memory, and lock deltas | No operational corpus-growth/diversity/concentration/rotation report and clean promotion is under-counted |
| Safe stop | PARTIAL | Factory catches interruption, cancels pending work, reports terminal state, and uses zero automatic retries | Durable host supervision and recovery are proof-specific; no operational supervisor exists |
| Terminal failure without restart | PARTIAL | `automatic_retries=0`; proof supervisor creates no successor and Attempt 7 ended naturally | Required behavior exists in proof machinery but is not packaged for persistent campaigns |
| Persistent DB isolation | BLOCKED | Proof preparation correctly copies and migrates an isolated DB and leaves the persistent DB unchanged | Operational use must intentionally target the persistent DB, which the current command forbids |
| Backup and restore | PARTIAL | Proof copy/backup hashing is strong; older operator material has a manual restore checklist | No verified operational backup, restore, and post-restore campaign recovery boundary |
| Replay/idempotency | PARTIAL | E2Z promotion and 4h plan/close have idempotency checks; stored proof report replay performs zero source calls | No resume-safe operational campaign replay, and no separately proven live report-only replay |
| Campaign bounds | BLOCKED | One run has duration, request, scheduler, and token ceilings | No bounded multi-cycle campaign, two-active-token lifecycle, archive/rotation cycle, or corpus review boundary |
| Scheduler fairness | PARTIAL | Central Scheduler has priority and due-time ordering | The factory loop selects run steps directly by `scheduled_for,id`; no per-token fairness contract or proof exists |
| Embedded Git provenance | NOT_IMPLEMENTED | Attempt 7 provenance was reconstructed after the run | Run and report schemas do not capture launch commit and tracked-tree state |
| Safety-label timeframe clarity | PARTIAL | Exact 4h shared safety gate is provenance-clean and fail-closed | Labels remain `SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY` and `BLOCK_CLEAN_MEMORY` even when the approved 4h gate accepts them |
| Wallet-level flow authenticity | PARTIAL | Missing wallets are reported as partial/caution; provenance or authenticity faults still block | Wallet authenticity is not available and must not be claimed |
| Wallet-authenticity proof for activation | NOT_REQUIRED | Product law permits honest partial flow context | Activation may proceed later only if reports preserve the limitation; no wallet or paid source may be added |
| Retrieval and financial capabilities | NOT_REQUIRED | They are outside this factory program | Must remain locked with zero campaign deltas |

## Current Discovery and Selection Readiness

The latest relevant repository evidence is Attempt 7, not the older discovery
counts in the V2-0 audit:

- two governed discovery requests were planned and attempted;
- both new-pool and trending-pool channels returned complete responses;
- source failure rate was `0.0`;
- 40 candidates were seen and normalized;
- 24 candidates passed the active eligibility/cooldown pool;
- one token was selected because the V2-9 lifecycle proof requested one;
- 23 otherwise eligible candidates were recorded as
  `QUALIFIED_RANDOM_NOT_SELECTED`;
- 14 WATCH_ONLY candidates remained audit-only;
- selection rotation state was recorded.

This proves current discovery productivity for a bounded run. It does not prove
multi-cycle diversity, dead/revival yield, or two-token campaign rotation.

The handoff is implemented across:

- `src/printer_v1/operator_cli/commands.py`:
  `build_discover_candidates_once_payload()` and
  `_select_discovery_candidates()`;
- `src/printer_v1/discovery/selection_batch.py`:
  `build_qualified_random_active_selection()`,
  `apply_selection_cooldown_gates()`, `persist_selection_batch()`, and
  `record_selection_rotation_state()`;
- `src/printer_v1/discovery/discovery.py`:
  `process_discovery_payload()` and `route_candidate_to_lifecycle()`;
- `src/printer_v1/operator_cli/one_command_15m_factory.py`:
  `_selected_targets()` and `_cancel_discovery_handoffs()`.

The current selection policy is categorical and seeded, not a score or ranking.
The old Group A quota view remains diagnostic rather than a hard gate. Attempt
7 reported its quota violations openly while the qualified-random gate passed.

## Manual-Step Inventory

| Manual step today | Why it exists | Required operational disposition |
|---|---|---|
| Prepare a fresh proof copy from `data/printer_v1.sqlite3` | Current runtime schema and isolation are proof-oriented | Replace with a verified persistent preflight and backup transaction; never copy production output into a proof DB |
| Apply migrations to the proof copy | Persistent DB is only at migration 024 | Back up and migrate the authoritative corpus through an approved operational schema lane |
| Create and verify a byte-identical proof backup | V2-9 rollback baseline | Keep backup verification, but define operational restore and interruption semantics |
| Start `scripts/Start-V2-9-Proof.ps1` | Proof-only supervision and flags | Do not reuse as the operational launcher; implement bounded operational supervision |
| Choose proof flags for 1h/4h | Continuation is run-wide and proof-gated | Replace with committed per-token selective continuation policy |
| Run X3 cooldown/archive commands separately | Factory does not invoke terminal lifecycle | Integrate deterministic cooldown/archive and revival-safe rotation |
| Reconstruct Git commit/clean state after a run | Artifacts omit launch provenance | Persist commit and tracked-tree state in the run ledger/report |
| Inspect nested Lane K/E2Z output for true clean yield | Top-level report under-counts clean promotion | Make authoritative episode promotion the top-level yield source |
| Invoke report-only mode separately | Stored report replay is not part of live supervision | Provide zero-source operational status/report replay and prove it |

Candidate choice itself was autonomous in Attempt 7 and is not a remaining
manual step.

## Authoritative Corpus DB Recommendation

The sole authoritative operational corpus should remain:

`data/printer_v1.sqlite3`

No file under `data/proof_runs/`, `operator-runs/`, or any V2-9 attempt path may
become the corpus. Proof DBs are immutable historical evidence after closeout.

Current read-only persistent DB facts:

- integrity check: `ok`;
- foreign-key errors: `0`;
- applied migrations: `24`;
- latest migration: `024_discovery_source_channel.sql`;
- missing current canonical migrations: 025 through 030;
- `printer_selection_batches`, `printer_selection_batch_items`,
  `printer_selection_rotation_state`, `printer_memory_factory_runs`,
  `printer_memory_factory_run_steps`, and `printer_proof_run_supervision` are
  absent.

The DB is healthy but not operational-runtime-schema ready. Existing migration
028 also constrains `printer_memory_factory_runs.db_mode` to `PROOF_ONLY`, and
the current validator requires that constraint. A later operational migration
must preserve historical proof rows while introducing an explicit bounded
operational mode; it must not weaken proof isolation or repurpose the proof
supervision table.

Minimum persistent DB safety contract:

1. verify exact canonical path and reject proof paths;
2. create and hash a restorable backup before migration or campaign mutation;
3. apply only committed canonical migrations;
4. run integrity, foreign-key, required-table, and lock checks;
5. record pre-run counts and Git provenance;
6. preserve the backup until terminal report and corpus review pass;
7. provide a tested restore procedure that does not merge proof data;
8. never automatically restart after terminal failure.

## Timeframe Continuation Readiness

### 15m to 1h

`_resolve_current_run_15m_source()` and
`build_1h_continuation_plan()` enforce exact run, token, pair, lane, closing
snapshot, and one-time predecessor consumption. `_execute_continuation_close()`
uses the exact current-run 15m row and the proven generalized audit/promotion
path. Attempt 7 produced 24/24 continuation snapshots with exact continuity.

The operational gap is selection policy, not evidence continuity. In
`run_one_command_15m_factory()`, enabling `continuous_first_hour` requires
exactly one selected token, and every successful 15m close in that mode plans
1h. There is no per-token continuation verdict based on learning value,
evidence quality, source budget, activity, or concentration.

### 1h to 4h

`one_token_4h_runtime.plan_current_run_4h()` enforces an exact unconsumed 1h
predecessor and exact identity. Attempt 7 proved 61/61 snapshots and clean
promotion. It nevertheless requires `explicit_proof_mode=True`, exactly one
selected token, and evaluation of a cadence policy whose real-collection flag
remains false. The installed console entry point in
`commands.py::main_run_one_command_15m_memory_factory()` exposes the
first-hour flag but no 4h continuation flags; V2-9 reached 4h through the
proof-supervision path.

The V2-9 proof contract is complete. V2-9.7C must define which token may
continue; V2-9.7D must implement that policy for a two-token campaign without
turning continuation on for every token.

## 5m Support Readiness

`_capture_same_stream_5m_support()` correctly:

- derives evidence from the same run's 15m snapshot stream;
- exact-links run, token, pair, lane, parent 15m window, and snapshot IDs;
- persists a `SUPPORT_5M` run step;
- keeps the 5m window audit/support-only;
- does not independently create retrieval or financial actions.

It is not conditional. The factory calls it for every successful 15m close
whenever continuous 1h mode is active, and treats failure to create the support
window as a token failure. Operational design must add a categorical
micro-event need gate for pumps, dumps, wicks, traps, or exit realism. No 5m
result may trigger 1h/4h continuation or enter main clean-memory thresholds.

## Recovery and Replay Readiness

Proof recovery is strong but not reusable unchanged:

- `proof_supervision._zero_source_cleanup()` cancels abandoned run steps/jobs,
  checks zero evidence mutation, records immutable terminal cause, and releases
  the proof lock;
- recovery is idempotent and creates no successor;
- the factory catches operator interruption, cancels pending steps, records the
  first stop reason, and reports running jobs after cleanup;
- `automatic_retries` and endpoint rotation remain zero;
- `load_report_only()` returns the stored report with zero source/evidence
  deltas;
- E2Z clean promotion is idempotent by memory-window identity.

Operational recovery is not implemented. Migration 030, the supervision
module, and the PowerShell launcher are all explicitly V2-9/proof-only. There
is no persistent-corpus campaign lease, no operational stale-host recovery, no
resume policy, and no verified restore path. The transient Windows atomic
lock-file replacement failure from Attempt 7 remains a reliability warning.

Repeated campaigns also need a durable idempotency identity covering campaign,
cycle, token, pair, evidence window, and predecessor. Current run UUIDs and
window-level checks prevent several duplicate cases, but do not define whether
an interrupted operational cycle resumes, terminally closes, or rotates away.

## Campaign Bounds and Scheduler Fairness

Existing proof bounds are useful:

- finite total duration;
- bounded discovery requests;
- cadence-derived request and scheduler ceilings;
- per-token and run-wide budget checks before execution;
- zero automatic retries and endpoint rotation;
- token-local failure isolation;
- run-wide safe stop for integrity/budget failure.

An operational campaign layer is absent. There is no cycle count, campaign
duration plus cycle duration contract, two-active-token selective lifecycle,
cooldown/archive cycle, corpus review checkpoint, or automatic candidate
replacement.

Central Scheduler's generic `select_next_jobs()` applies effective priority and
due-time ordering. The one-command factory instead reads its own pending ledger
with `ORDER BY scheduled_for,id` and claims that exact job. This is scheduler-led
in persistence and locking, but it does not prove fairness between two tokens.
V2-9.7C must define fairness; V2-9.7D must use or extend the Central Scheduler
selection contract; V2-9.7E must prove that neither token starves, especially
around close boundaries and selective continuation.

## Cooldown, Archive, and Rotation Readiness

Standalone lifecycle behavior exists in
`lane_x3_post_cycle_lifecycle.py`:
`enter_cooldown_after_window()`, `archive_after_memory_window()`,
`reopen_token()`, and `evaluate_post_cycle_lifecycle()`.

Selection-time rotation exists in `selection_batch.py` through token/pair
cooldown checks and `printer_selection_rotation_state`. These are not connected
to the proof factory terminal path. `_cancel_discovery_handoffs()` cancels the
handoff scheduler job but does not resolve the tracking queue item. The current
persistent DB has 15 tracking queue rows and all are still `QUEUED`, including
rows from June and July.

Operational activation requires one deterministic terminal transition per
selected token: cooldown, archive, or blocked/manual-review. Revival may reopen
only with new governed evidence. Rotation must choose a replacement without
silently recycling a token/pair inside its cooldown.

## Reporting and Supervision Readiness

The proof report already covers run identity, selected targets, steps, cadence,
sources, budgets, deltas, terminal cause, locks, and per-token outcomes. Four
repairs remain before operational use:

1. `_per_token_outcomes()`, `run_local_yield`, and `memory_results` read the
   source `printer_memory_windows` label. E2Z intentionally leaves that row
   partial and creates the authoritative clean `printer_episodes` row, so clean
   promotion is under-counted.
2. Safety evidence accepted by the exact 4h gate still exposes 15m-only and
   `BLOCK_CLEAN_MEMORY` names from `safety/goplus_normalizer.py`,
   `safety/composite.py`, and `context_evidence/window_15m.py`.
3. Run records do not embed Git HEAD and tracked-tree state.
4. Operational status/report replay and durable supervision do not exist; the
   corresponding implementation is proof-only.

Future corpus reporting must add campaign/cycle counts, clean promotions by
authoritative episode kind, dirty/blocked reasons, source efficiency,
timeframe yield, token/pair and outcome diversity, concentration, continuation
yield, cooldown/archive/rotation transitions, interrupted cycles, and safe
shutdown state. Raw row count is not a success criterion.

Flow authenticity must continue to report `TRADING_FLOW_CONTEXT_PARTIAL` /
`FLOW_CONTEXT_CAUTION` when wallets are unknown. It may support a clean memory
under the adopted evidence contract, but cannot support a wallet-authenticity
or wash-detection claim.

## Blocker and Dependency Table

| Blocker | Exact file/function/schema | Blocks | Smallest later lane | Minimum sufficient proof |
|---|---|---|---|---|
| Command rejects operational/persistent mode | `one_command_15m_factory.py::run_one_command_15m_factory()`, `commands.py::main_run_one_command_15m_memory_factory()` | Implementation, pilot, activation | V2-9.7D after V2-9.7C design | Static fail-closed tests plus bounded temp-DB integration using explicit operational mode |
| Run ledger is proof-only | `migrations/028_memory_factory_run_ledger.sql` checks `db_mode='PROOF_ONLY'`; `proof_db_schema_readiness.validate_runtime_schema_connection()` requires it | Implementation, activation | V2-9.7D operational migration | Fresh DB and upgraded-copy migration tests preserving historical proof rows and constraints |
| Persistent corpus is six migrations behind | `printer_schema_migrations`; missing 025-030 and their tables in `data/printer_v1.sqlite3` | Pilot, activation | V2-9.7D persistent preflight/migration boundary | Backup hash, migration dry run on a copy, integrity/FK/schema/count preservation checks, then separately approved persistent migration |
| No per-token selective 1h continuation | `run_one_command_15m_factory()` and `_plan_continuation_jobs()` | Campaign design, implementation, pilot, activation | V2-9.7C design then V2-9.7D | Two-token fixture where only the eligible token continues and the other closes cleanly at 15m |
| 4h is one-token proof-only and absent from the installed console entry point | `one_token_4h_runtime.plan_current_run_4h()`, `snapshots/cadence_policy.py`, `commands.py::main_run_one_command_15m_memory_factory()` | Campaign design, implementation, pilot, activation | V2-9.7C/D | Two-token campaign fixture with at most one conditionally continued 4h token, exact continuity, bounded budgets, and an explicit operational CLI boundary |
| 5m support is unconditional in continuous mode | `one_command_15m_factory._capture_same_stream_5m_support()` and its call after every 15m close | Implementation, pilot, activation | V2-9.7C/D | Positive micro-event and negative no-event fixtures proving exact linkage, no main-threshold count, and no continuation trigger |
| Cooldown/archive not integrated | `lane_x3_post_cycle_lifecycle.py`; no call from `one_command_15m_factory.py` | Pilot, activation | V2-9.7B lifecycle handoff repair | Terminal clean, dirty, blocked, and failed fixtures each produce exactly one allowed lifecycle transition |
| Tracking handoff queue can remain stale | `_cancel_discovery_handoffs()` plus `lifecycle/tracking_queue.py`; persistent DB has 15 old `QUEUED` rows | Pilot, activation | V2-9.7B queue-state repair | Repeated-cycle fixture proves no stale active queue/job after close, stop, failure, cooldown, or archive |
| Cross-token scheduler fairness unproved | factory pending-step query ordered by `scheduled_for,id`; `scheduler.select_next_jobs()` | Campaign design, pilot, activation | V2-9.7C/D/E | Two-token deterministic scheduling test and bounded pilot showing no starvation and close-boundary priority |
| Clean promotion under-count | `_per_token_outcomes()`, `_final_report()`, `e2z_clean_memory_creation.create_clean_memory_from_window()` | Pilot, activation | V2-9.7B reporting repair | Clean, dirty, blocked, and already-exists fixtures reconcile window candidates to authoritative episode promotions |
| Safety labels confuse timeframe | `safety/goplus_normalizer.py`, `safety/composite.py`, `context_evidence/window_15m.py` | Pilot interpretation, activation | V2-9.7B label clarification | 15m/1h/4h shared-context fixtures prove labels match gate outcome without broadening safety acceptance |
| Operational supervisor/recovery absent | `proof_supervision.py`, migration 030, `scripts/Start-V2-9-Proof.ps1` | Implementation, pilot, activation | V2-9.7D | Host disappearance, operator cancel, source failure, budget stop, natural completion, and no-restart tests |
| Heartbeat replacement contention | `proof_supervision.heartbeat_active_lease()`, `V2-9-LauncherLogging.ps1`, `Start-V2-9-Proof.ps1` | Long pilot reliability, activation | V2-9.7B supervision primitive repair | Repeated Windows contention fixture keeps lease continuity or terminates safely with immutable cause |
| Operational backup/restore absent | proof-only `prepare_proof_db()` plus older manual restore checklists | Pilot, activation | V2-9.7D | Byte-verified backup, interrupted-copy defense, restore rehearsal on a disposable copy, count/integrity reconciliation |
| Operational report-only replay absent | `one_command_15m_factory.load_report_only()` is tied to proof run ledger | Pilot auditability, activation | V2-9.7D/E | Separate zero-source report/status invocation after a bounded pilot with zero evidence and financial deltas |
| Embedded Git provenance absent | run ledger migration 028 and `_final_report()` | Pilot auditability, activation | V2-9.7B provenance repair | Dirty-tree rejection/recording tests and committed-clean pilot artifact containing exact HEAD |
| Multi-cycle campaign/rotation layer absent | no operational campaign module/schema; standalone selection/lifecycle pieces only | Implementation, pilot, activation | V2-9.7C/D | Bounded multi-cycle two-token fixture plus pilot proving caps, rotation, review stop, and no automatic restart |

Wallet-level flow authenticity is deliberately not a repair blocker. The
smallest correct treatment is to preserve partial/caution labels and never
claim wallet authenticity. A future source-authenticity enhancement would need
its own approved lane and is not required for V2-9.7 activation.

## Recommended V2-9.7B Repair Sequence

V2-9.7B should repair only defects already proven in existing reusable
components. It should not implement the operational campaign command.

1. Reconcile top-level yield with authoritative E2Z episode promotion,
   including idempotent `ALREADY_EXISTS`, dirty, and blocked outcomes.
2. Clarify timeframe-aware safety reporting without widening the accepted
   evidence contract.
3. Repair tracking-queue terminal state and connect existing cooldown/archive
   primitives to a reusable post-cycle lifecycle function.
4. Harden the heartbeat/lease atomic-update primitive against the observed
   Windows contention while preserving fail-closed terminal behavior.
5. Add reusable Git provenance capture for run configuration and reports.
6. Close V2-9.7B with focused tests and a static lock scan.

The following belong after B and must not be smuggled into it:

- V2-9.7C: selective continuation, conditional 5m, fairness, campaign bounds,
  rotation/replacement, recovery semantics, and corpus-report design.
- V2-9.7D: operational schema, persistent preflight/backup/restore,
  operational supervision, bounded multi-cycle command, and zero-source status
  replay implementation.
- V2-9.7E: two-token pilot proof against an approved isolated pilot target or
  explicitly approved persistent boundary, as defined by C/D.
- V2-9.7F: activation closeout and V2-9.8A readiness decision.

## Money-Usefulness Contribution

This lane prevents proof success from being mistaken for a safe memory-growth
product. It identifies the smallest work needed to turn one trustworthy 4h
lesson into a repeatable, diverse, persistent corpus process while protecting
against stale queue work, winner concentration, false clean-yield reports,
duplicate campaigns, and unsafe restart behavior.

The current discovery evidence is encouraging: one bounded two-request sample
produced 24 eligible candidates spanning fast activity, volume rise/decay,
consolidation, and liquidity states. The next value gain comes from selective
continuation and rotation, not from indiscriminately tracking every candidate
through every timeframe.

## What This Lane Improves

- Replaces stale discovery assumptions with current read-only evidence.
- Separates proven 15m/1h/4h evidence machinery from proof-only orchestration.
- Establishes the authoritative persistent DB and names its exact schema gap.
- Makes manual steps, lifecycle gaps, fairness risk, and recovery gaps explicit.
- Converts the V2-9 observations into scoped repair requirements.
- Prevents V2-9.7B from becoming a broad redesign or premature activation.

## What Remains Locked

- Operational memory growth and any persistent campaign write.
- The operational PowerShell command and V2-9.8 activation gate.
- V2-10 and all 12h/24h work.
- Memory retrieval activation or retrieval use in decisions.
- Paper decisions and BUY, SELL, or HOLD.
- Paper positions, trade events, paper trade audits, and PnL.
- Live trading, execution, transactions, signing, wallets, private keys, and
  real funds.
- Paid APIs.
- Scoring, ranking, confidence percentages, weighted logic, embeddings, and
  vectors.
- Source or scheduler bypass.
- 5m as a main outcome, clean-memory threshold, or continuation trigger.
- Any claim of wallet-level flow authenticity.

## Proof Required Before V2-9.7 Completion

V2-9.7A is complete with this static/read-only audit. Before V2-9.7F can pass:

1. V2-9.7B focused repair tests must pass for authoritative promotion
   reporting, safety-label clarity, queue/lifecycle terminal state, heartbeat
   reliability, and embedded Git provenance.
2. V2-9.7C must approve a categorical two-token campaign design with
   conditional 5m, per-token selective 1h/4h, fairness, budgets, rotation,
   recovery, reporting, and no-restart rules.
3. V2-9.7D must implement an explicit operational mode and schema without
   weakening historical proof isolation.
4. Migration and restore must be rehearsed on disposable copies with integrity,
   foreign-key, count, and hash reconciliation.
5. Focused integration tests must prove clean/dirty/blocked outcomes,
   idempotency, interruption recovery, terminal failure, and zero retrieval /
   financial deltas.
6. V2-9.7E must pass a bounded two-active-token pilot, then prove selective
   continuation rather than all-timeframe tracking.
7. A separate zero-source report-only replay must reconcile the pilot after
   natural cleanup.

No repeated 4h proof is required merely to re-prove V2-9 Attempt 7.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control |
|---|---|---|
| Reusing proof launcher for production | Writes to wrong DB boundary or preserves proof-only assumptions | Build a distinct operational supervisor and command |
| Migrating the persistent DB without verified restore | Corpus loss or irreversible partial schema | Backup/hash/copy rehearsal before separately approved migration |
| Treating one-token continuation as selective policy | Every chosen token may consume expensive long-window capacity | Per-token categorical continuation verdict and source-budget gate |
| Unconditional 5m capture | Support evidence becomes a hidden mandatory main-stage dependency | Conditional micro-event gate and negative no-capture proof |
| Scheduler tie ordering favors one token | Starvation or missed close evidence for the other token | Fairness contract and two-token deterministic proof |
| Stale queue rows survive cycles | Duplicate work, false active-token counts, poor rotation | Terminal queue/lifecycle reconciliation |
| Top-level clean under-count persists | Operator may discard good memories or misread campaign quality | Episode-authoritative yield reconciliation |
| Safety labels remain timeframe-confusing | Operators may mistake accepted context for a safety bypass | Timeframe-neutral or explicit context labels with unchanged gate |
| Heartbeat contention recurs | Ambiguous long-run supervision | Durable atomic renewal and terminal-failure tests |
| Git provenance remains external | Campaign cannot be tied to exact committed behavior | Embed HEAD and tracked-tree state at launch |
| Report-only replay remains proof-bound | Post-run audit may require touching live execution path | Zero-source operational status/report command |
| Partial flow is overstated | False wash/authenticity claims contaminate memory interpretation | Preserve partial/caution and unknown-wallet reporting |
| Raw row count drives continuation | Corpus grows concentrated, dirty, or winner-heavy | Formal corpus-quality reviews and diversity/concentration reporting |

## Files Changed

- `docs/printer-v1-v2-9-7a-operational-memory-factory-readiness-audit.md`

## What Was Built

One audit-only V2-9.7A readiness closeout with a current end-to-end component
classification, persistent DB recommendation, manual-step inventory, exact
blocker/dependency map, and recommended V2-9.7B repair sequence.

## What Was Not Touched

- Code, tests, migrations, schemas, databases, and runtime.
- Active build-order or source-law documents.
- V2-9.8, V2-10, retrieval, paper decisions, or financial functions.
- Unrelated untracked artifacts.

## Tests / Checks Run

- Static source and document inspection.
- Read-only persistent DB integrity, migration, schema, discovery, and tracking
  inspection.
- Read-only Attempt 7 proof DB discovery/selection/run inspection.
- Accidental-unlock scan.
- Approved-file scope check.
- `git diff --check`.

## Pass / Fail Status

`V2_9_7A_OPERATIONAL_READINESS_AUDIT_PASS`

The audit is complete. Operational activation is not ready.

## Risks or Concerns

The largest risk is treating the proven V2-9 proof engine as an operational
factory without first separating proof and persistent schemas, adding selective
multi-token campaign behavior, integrating lifecycle/rotation, and repairing
supervision/reporting. The persistent DB is healthy but six canonical
migrations behind the current proof schema and must not be modified in this
lane.

## Next Recommended Phase

`V2-9.7B - Repair only proven discovery/operational blockers`, limited to the
repair sequence in this audit. Do not provide or run the operational command.
