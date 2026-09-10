# Printer V1 Terminal-Only Expired-Orphan Reconciliation Design

Status: approved design for implementation planning; implementation has not started.

Design baseline: branch `assistant/v2-9-8b-cycle1-cycle2-four-hour-admission-proof` at `4403d8e7215a25c055a229497fc05163a9411d98`.

## 1. Problem

The four-token Standard-4H operational path now proves the intended 4/2/2 lifecycle when the authorized child remains alive: two Cycle-1 tokens plus two fresh/disjoint Cycle-2 tokens can progress through `WINDOW_15M -> WINDOW_1H -> WINDOW_4H`, and clean evidence can form four exact clean 4h episode/fingerprint pairs.

Graceful provider, RPC, lifecycle, and lease-renewal failures already return through the child-owned terminal coordinator. The coordinator stops heartbeat ownership, reconciles campaign/factory state, cancels owned work, releases the campaign lease, and records terminal evidence.

Abrupt child or host termination is different. `SIGKILL`, process loss, host reboot, power loss, or equivalent termination can prevent all Python exception/finally handlers from running after the one-shot authorization has already been consumed. Durable state may then retain nonterminal campaign, run, cycle, supervision, factory, discovery, window, or Scheduler ownership.

The next four-token authorization correctly blocks because the zero-state gate requires those active domains to be zero. Lease expiry alone does not transition the durable graph to terminal state.

The current `recover-orphan` path is intentionally not a generic solution. It is an exact historical recovery bound to one prior execution and exact database/hash evidence. It must remain unchanged.

## 2. Goal

Add one explicit, operator-authorized, terminal-only recovery authority for an expired, proven-dead four-token Standard-4H operational campaign.

The authority must make the interrupted run terminal and remove only its exact active ownership so that future zero-state checks can reason from truthful durable state. It must never resume, restart, rerun, continue, replace, or create a successor for the interrupted campaign.

## 3. Non-goals and immutable safety rules

This design does not:

- resume any interrupted lifecycle;
- reuse the consumed authorization;
- create a new campaign, cycle, factory run, authorization, restart, retry, rerun, or successor;
- perform source, provider, RPC, WebSocket, holder, liquidity, discovery, or market-data calls;
- execute Scheduler work;
- promote a partial/dirty/incomplete window into clean memory;
- create new clean-memory episodes or fingerprints;
- alter already-valid clean memory;
- unlock retrieval, paper decisions, positions, PnL, wallets, signing, funds, or trading;
- unlock `WINDOW_12H` or `WINDOW_24H`;
- mutate the existing zero-state gate into an auto-repair path;
- generalize the historical `recover-orphan` implementation;
- guess a target from the latest campaign or latest supervision row.

The zero-state gate remains read-only and fail-closed. Recovery is a separate explicit operator action.

## 4. Scope of the first implementation

The first implementation is deliberately limited to the operational four-token Standard-4H mode:

`four-token-standard-four-hour-run`

A candidate whose immutable configuration does not prove that exact command mode and exact operational 4/2/2 authority is ineligible and must remain untouched.

A later decision may generalize the recovery owner to other operational modes, but this design does not authorize that work.

## 5. Architecture

### 5.1 New module

Add:

`src/printer_v1/operator_cli/expired_orphan_reconciliation.py`

It owns two operations:

1. a read-only exact orphan inspection;
2. an operator-approved terminalization using the existing terminal owners.

It must not become a lifecycle, Scheduler, Source Governor, memory-quality, or provider owner.

### 5.2 New auxiliary CLI modes

Extend the existing public operational command with two auxiliary modes:

- `inspect-expired-orphan`
- `terminalize-expired-orphan`

Both require explicit `--campaign-id` and `--run-id`. Neither may fall back to a latest row.

`terminalize-expired-orphan` additionally requires:

- `--operator-approved`
- `--inspection-sha256 <sha256>`

The historical `recover-orphan` mode remains byte-for-byte behaviorally separate.

These are recovery/inspection modes, not wrapper-bound run modes. They never accept run authorization bindings and never create a child process.

## 6. Read-only orphan inspection contract

### 6.1 Exact identity resolution

Given exact `campaign_id` and `run_id`, inspection must prove all of the following from the authoritative database:

- exactly one matching campaign row;
- exactly one matching campaign-run row;
- exactly one configuration row owned by that campaign;
- exactly one supervision row owned by that campaign/run;
- configuration, supervision, campaign, and run identities agree;
- the configuration's `execution_id`, `campaign_id`, `configuration_id`, `run_id`, `cycle_id`, `command_mode`, and policy facts are internally consistent;
- the configured origin cycle is the durable cycle ordinal 1 identity.

No global newest/latest fallback is permitted.

### 6.2 Original authorization proof

Inspection must reuse the immutable configuration evidence already written by `_create_campaign_command` and the operational database-target authority.

It must prove:

- `command_mode == "four-token-standard-four-hour-run"`;
- the exact four-token operational policy/capacity is present;
- the durable internal authorization marker is present and its stored SHA matches its canonical payload;
- the durable operational database-target expectation binds the same execution/campaign/run/configuration/origin-cycle identities;
- the original external authorization is recorded as consumed exactly once;
- `invocation_count == allowed_invocation_count == 1`;
- `automatic_retry_allowed == False`;
- `manual_rerun_allowed == False`;
- `resume_allowed == False`;
- `restart_allowed == False`;
- `successor_allowed == False`.

Recovery does not change any of those facts.

### 6.3 Database health proof

Before declaring a recovery candidate eligible, inspection must prove the authoritative database is safe to reason about:

- exact canonical database path;
- readable database;
- migration ledger compatible with the executing recovery code;
- integrity check passes;
- foreign-key check passes;
- no authoritative SQLite WAL/SHM/journal sidecar ambiguity.

The original pre-run database SHA stored in authorization evidence is historical authorization identity. It must not be confused with the current post-run database SHA.

Inspection also records the current database file identity and current SHA-256 as recovery compare-and-swap evidence.

### 6.4 Process-death proof

Inspection must reuse the existing bounded host-process inventory owner and exact Printer operational runtime command classifier.

Eligibility requires a successful host inspection and zero live Printer operational runtime processes.

The recovery command never sends signals, kills processes, polls indefinitely, or assumes that lease expiry proves process death.

If any Printer operational runtime process is visible, recovery is blocked.

### 6.5 Lease proof

For an initial orphan candidate, the exact supervision row must be `ACTIVE` or `STOPPING` and its lease must be expired at inspection time.

The configured lease file must:

- exist;
- be a regular readable file;
- decode to the exact expected campaign/configuration/run/supervision/owner scope;
- carry the same authoritative ownership identity as the supervision row.

A missing, malformed, symlinked, or ownership-mismatched lease is not auto-repaired by this first implementation. It is a forensic blocker.

A terminal-supervision replay is eligible only for one narrow cleanup-completion case: all campaign/factory/work ownership is already terminal and zero-active, the first cause is the recovery cause, but the exact lease release/lock removal did not finish. That replay may invoke only the existing idempotent lease-release cleanup path.

### 6.6 Four-token admitted-shape proof

The recovery owner accepts only shapes that the existing atomic admission contracts can lawfully produce:

- **PRE_ADMISSION**: origin cycle only, zero token slots;
- **CYCLE_1_ADMITTED**: cycle ordinal 1 with exact slot ordinals `[1, 2]`;
- **TWO_CYCLES_ADMITTED**: cycle ordinals `[1, 2]`, each with exact slot ordinals `[1, 2]`.

Any partial, duplicate, unexpected, or ambiguous cycle/slot shape blocks recovery without mutation.

When a factory run has been durably linked through `printer_memory_factory_campaign_runs.authoritative_run_id`, that exact identity is carried into terminal reconciliation. No unlinked factory identity is invented.

### 6.7 Ownership proof

Inspection records all attributable active work and Scheduler identities for the target campaign/run.

Eligibility requires:

- no Scheduler job shared with another campaign/run;
- no ownership row whose campaign/run identity conflicts with the target;
- no second active/STOPPING campaign supervision that would make single-runtime ownership ambiguous.

The recovery owner never broad-cancels by status alone.

### 6.8 First-terminal-cause rule

The first implementation handles the pure abrupt-orphan case and its own idempotent continuation.

Before first recovery mutation, every existing campaign/run/cycle/supervision first-terminal-cause field must be either null or absent. The recovery cause is then:

`OPERATIONAL_CAMPAIGN_ORPHANED_AFTER_LEASE_EXPIRY`

If a previous recovery attempt partially committed that exact cause while supervision remains recoverable, a fresh inspection may continue the same recovery.

Any different pre-existing first terminal cause is outside this first slice and blocks mutation. That case belongs to graceful/incomplete-closeout forensics, not catastrophic-orphan inference.

## 7. Canonical inspection evidence and SHA binding

The read-only inspector returns a canonical mapping with a versioned schema. At minimum it contains:

- requested campaign/run identity;
- resolved execution/configuration/supervision/owner/origin-cycle identities;
- command mode and exact policy/capacity evidence;
- immutable authorization and non-reuse facts;
- current database path/SHA/integrity/migration evidence;
- host-process evidence;
- supervision/lease/lease-file evidence;
- admitted cycle/slot shape;
- linked factory-run identity, if any;
- exact active work/Scheduler identities;
- existing campaign-window and physical memory-window identities;
- existing clean episode/fingerprint identities linked to this campaign;
- the expected recovery first cause;
- eligibility status and blocker codes.

`inspection_sha256` is the SHA-256 of the canonical inspection payload excluding the `inspection_sha256` field itself.

The mutating command must rerun the complete inspection immediately before recovery and require exact SHA equality with `--inspection-sha256`. Any state drift blocks before database mutation.

This is not a new campaign authorization. It is a stale-state guard over an explicitly approved terminal-only recovery action.

## 8. Backup boundary

An eligible terminalization must create a verified pre-recovery backup and restore rehearsal using the existing `operational_backup_restore_preflight` owner before authoritative database mutation.

The backup is bound to the current recovery-time database SHA, not the historical pre-run authorization SHA.

After backup creation, the recovery owner reruns the read-only inspection. If its canonical SHA differs from the operator-approved inspection SHA, recovery stops before database mutation.

The backup is forensic protection only. This design does not authorize automatically restoring the authoritative database from it.

## 9. Terminalization flow

After all read-only proofs and the backup/reinspection check pass:

1. Resolve the exact controlling identities from the approved inspection. Never reselect by latest row.
2. Use `OPERATIONAL_CAMPAIGN_ORPHANED_AFTER_LEASE_EXPIRY` as the first cause unless this is an allowed continuation of the same exact recovery cause.
3. Resolve the exact linked factory-run identity from durable campaign-run ownership, if present.
4. Reconcile through existing terminal owners:
   - `PRE_ADMISSION` uses `reconcile_campaign_terminal` for the exact origin cycle;
   - `CYCLE_1_ADMITTED` and `TWO_CYCLES_ADMITTED` use `reconcile_admitted_campaign_terminal`, whose existing admitted-shape contract covers one or two exact two-slot cycles.
5. Use `run_status="FAILED"` and never claim successful campaign completion for an interrupted run.
6. Invoke `cleanup_campaign_supervision` with the exact supervision/campaign/configuration/run/owner identities, `terminal_status="FAILED"`, and the same first cause.
7. Never invoke source, discovery, market, holder, lifecycle-progression, snapshot-collection, memory-quality, or Scheduler execution code.
8. Run read-only postconditions.

The order is reconciliation before supervision cleanup. This matches the existing four-token shared terminal path and makes a partial recovery replay safe: if reconciliation commits but the process dies before cleanup, supervision is still recoverable and the same cause can be replayed idempotently.

## 10. Memory integrity during recovery

The recovery action is terminal-only.

Before mutation, it snapshots the target campaign's linked physical memory-window IDs, clean episode IDs, and fingerprint IDs.

After mutation it must prove:

- no new `printer_episodes` row was created;
- no new `printer_memory_fingerprints` row was created;
- every pre-existing clean episode/fingerprint identity is unchanged;
- no incomplete or partial window was promoted to `CLEAN_MEMORY`;
- no quality label was upgraded by recovery;
- already terminal/clean campaign windows remain terminal rather than being downgraded;
- active/incomplete campaign-owned windows may only be terminalized/cancelled by the existing terminal owner;
- no `WINDOW_12H` or `WINDOW_24H` capability is created or unlocked.

A previously valid clean 15m/1h/4h memory remains valid historical evidence. An interrupted not-yet-promoted window remains non-clean; recovery does not attempt to finish it.

## 11. Postconditions

A successful initial recovery must prove all of the following for the exact target:

- campaign is terminal;
- campaign run is terminal;
- every admitted campaign cycle is terminal;
- linked factory run is not `PENDING` or `RUNNING`;
- linked factory run steps are not `PENDING` or `RUNNING`;
- supervision is `TERMINAL` with `terminal_status="FAILED"`;
- supervision cleanup timestamp exists;
- lease release timestamp exists;
- lease file is absent;
- exact campaign-owned active work count is zero;
- exact campaign-owned active Scheduler/locked job count is zero;
- active discovery/pre-admission/refresh ownership for the target is zero;
- no source-request or Scheduler-job row was created by recovery;
- no clean-memory episode/fingerprint row was created by recovery;
- no restart/resume/rerun/successor/campaign/cycle was created;
- retrieval/decision/position/PnL/trading tables have zero recovery-caused deltas;
- 12h/24h capability tables have zero recovery-caused deltas.

A recovery command must not report success if these postconditions are not proven.

## 12. Recovery artifact

After terminal postconditions are proven, write one immutable recovery artifact under the original execution artifact root, for example:

`<execution-root>/orphan-recovery/terminal-only-recovery.json`

It contains:

- design/schema version;
- approved inspection SHA;
- recovery-time code provenance;
- pre-recovery database/backup identities;
- exact target identities;
- admitted shape;
- first terminal cause;
- reconciliation result;
- cleanup result;
- postcondition evidence;
- zero-new-source/Scheduler/memory/restart facts.

The authoritative database remains the source of terminal truth. A filesystem artifact write failure after proven database terminalization is a secondary reporting fault, not permission to rerun the campaign.

## 13. Idempotence and partial recovery

Recovery itself may be attempted again only as terminalization recovery, never as campaign execution.

A fresh inspection SHA is required for every mutation attempt.

Allowed replay cases:

- reconciliation partially committed the same recovery cause but supervision remains `ACTIVE`/`STOPPING` and expired;
- reconciliation completed and cleanup has not yet run;
- cleanup committed terminal supervision and all active work is already zero, but exact lease release/lock removal remains incomplete.

A fully recovered campaign returns an already-terminal/read-only result and performs no new mutation.

A terminal supervision row with unrelated active residue, a conflicting first cause, ambiguous ownership, or any shape outside the explicit replay cases is a forensic blocker rather than an auto-repair target.

## 14. Error handling

All precondition failures are categorical and fail before authoritative mutation. Examples include:

- `ORPHAN_IDENTITY_NOT_FOUND`
- `ORPHAN_IDENTITY_AMBIGUOUS`
- `ORPHAN_MODE_NOT_FOUR_TOKEN_STANDARD_4H`
- `ORPHAN_AUTHORIZATION_EVIDENCE_INVALID`
- `ORPHAN_AUTHORIZATION_REUSE_FLAGS_INVALID`
- `ORPHAN_DATABASE_HEALTH_BLOCKED`
- `ORPHAN_DATABASE_SIDECAR_AMBIGUOUS`
- `ORPHAN_PRINTER_PROCESS_PRESENT`
- `ORPHAN_LEASE_NOT_EXPIRED`
- `ORPHAN_LEASE_FILE_MISSING`
- `ORPHAN_LEASE_OWNERSHIP_MISMATCH`
- `ORPHAN_ADMITTED_SHAPE_INVALID`
- `ORPHAN_ACTIVE_OWNERSHIP_AMBIGUOUS`
- `ORPHAN_FIRST_CAUSE_CONFLICT`
- `ORPHAN_INSPECTION_SHA_MISMATCH`
- `ORPHAN_BACKUP_PREFLIGHT_BLOCKED`
- `ORPHAN_TERMINAL_POSTCONDITION_FAILED`

Error text must not expose credentials, provider secrets, or raw unsafe transport material.

## 15. Expected implementation surface

Primary files:

- new `src/printer_v1/operator_cli/expired_orphan_reconciliation.py`;
- focused changes to `src/printer_v1/operator_cli/operational_memory_factory_command.py` for the two auxiliary modes and exact arguments;
- new focused tests under `tests/`.

Existing owners to reuse rather than duplicate:

- `operational_campaign_recovery.host_process_inventory`;
- Printer runtime command classification from `four_token_proof_zero_state_gate`;
- immutable campaign configuration and operational database-target expectation;
- `operational_backup_restore_preflight`;
- `campaign_active_work_report` / exact campaign Scheduler ownership helpers;
- `reconcile_campaign_terminal`;
- `reconcile_admitted_campaign_terminal`;
- `cleanup_campaign_supervision`.

No schema migration is expected. If implementation proves a migration is required, stop and revise this design before adding it.

The zero-state gate, historical `recover-orphan`, source owners, Scheduler runtime, memory-quality gates, and four-token lifecycle code should not change unless a focused failing regression proves a required compatibility repair.

## 16. TDD verification matrix

Implementation begins with failing disposable-state tests. The minimum matrix is:

1. eligible expired orphan is detected read-only;
2. visible live Printer process blocks;
3. non-expired lease blocks;
4. missing/malformed/mismatched lease blocks;
5. wrong command mode/policy blocks;
6. malformed or reusable authorization facts block;
7. second active supervision/ambiguous ownership blocks;
8. invalid cycle/slot shape blocks;
9. changed state causes inspection-SHA mismatch before mutation;
10. backup/restore-preflight failure causes zero authoritative mutation;
11. pre-admission orphan terminalizes without creating lifecycle work;
12. one-cycle/two-slot orphan terminalizes through existing shared owner;
13. two-cycle/four-slot orphan terminalizes both cycles and all exact slots;
14. linked factory run/steps become non-active;
15. exact active Scheduler/discovery/pre-admission/refresh ownership becomes zero;
16. already-clean 4h episodes/fingerprints are preserved byte-for-byte in identity/payload terms;
17. incomplete windows create zero new clean episodes/fingerprints;
18. no new source-request or Scheduler-job rows are created;
19. retrieval/decision/position/PnL/trading and 12h/24h deltas remain zero;
20. recovery replay after reconcile-before-cleanup partial state succeeds with the same cause;
21. lease-release-only cleanup replay succeeds;
22. fully recovered state is a zero-mutation no-op;
23. conflicting first cause/terminal residue blocks;
24. existing historical `recover-orphan` behavior remains unchanged;
25. existing four-token zero-state tests remain read-only and unchanged in semantics;
26. existing four-token two-cycle clean-memory integration proof remains green.

No test may contact live providers/RPC/WebSockets or mutate the authoritative production database.

## 17. Completion bar

This repair is complete only when disposable tests prove:

**a consumed four-token Standard-4H campaign whose child is absent and whose exact supervision lease is expired can be explicitly terminalized, without resuming the run, without creating source/Scheduler/lifecycle/memory work, while preserving already-valid clean memory and leaving zero exact owned active residue so a later separately authorized run can be evaluated by the unchanged zero-state gate.**

This design does not itself authorize any real recovery execution against the authoritative database.
