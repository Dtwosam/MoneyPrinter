# Printer V1 V2-9.8B.17 — External Stop and Heartbeat Lease Root-Cause Audit

## 1. Verdict

```text
V2_9_8B_17_EXTERNAL_STOP_AUDIT_BLOCKED_INSUFFICIENT_EVIDENCE
```

The execution is terminal and has no live lease, active Scheduler job, memory
window, clean-memory promotion, retrieval delta, or financial delta. The audit
proves that the canonical heartbeat thread signalled an unconfirmed lease
renewal and that the first lifecycle cancellation probe raised `_ExternalStop`.

The audit cannot truthfully prove the underlying renewal failure subtype. The
in-memory renewal result contained the fields needed to distinguish SQLite
contention, lease expiry, ownership/lock failure, or another exception, but that
result was not durably retained. The terminal report and summary preserve only
`OPERATIONAL_CAMPAIGN_FAILED:_ExternalStop`, and this operation has no captured
stdout or stderr artifact.

Two committed-code defects are nevertheless proven independently of that
missing subtype:

1. the cancellation check after factory-run creation is outside the lifecycle
   `try/finally`, so `_ExternalStop` escaped rather than closing the initialized
   factory run through its canonical owner; and
2. the outer failure coordinator passed `factory_run_id=None`, leaving the
   created factory row `RUNNING` with zero steps after the campaign itself was
   terminalized.

This is an audit-only verdict. It does not authorize a repair, production
retry, live source use, resume, successor, or capability unlock.

## 2. Scope and baseline

```text
Repository: /Users/Dtwo1/Developer/MoneyPrinter
Expected and observed HEAD: fd721d4f978f2864e82eb6f069ffc72412ea1917
Commit subject: Close V2-9.8B batch-scoped persistence repair
Execution: 20260727T161750Z-95e40c3efae3
Authoritative DB: data/printer_v1.sqlite3
Operation root: /Users/Dtwo1/PrinterOperations/v2-9-8/20260727T161750Z-95e40c3efae3
```

The worktree was clean before this document was created. The audit used only
tracked source/document reads, read-only SQLite queries, and operation-artifact
reads. It did not run production, sources, Python, tests, migrations, or an
authoritative write.

Relevant governing sources were the active V2 memory-growth build order, the
V2-9.8A gate, the V2-9.8B.16 closeout/design, the Python Builder Guide's
source-grounded blocker classification, and the canonical campaign,
supervision, lifecycle, discovery, and terminal-report owners.

## 3. Evidence inventory

### 3.1 Operation artifacts

The operation directory contains exactly the retained pre-campaign backup,
restore rehearsal, terminal report, and terminal summary. It contains no lease
lock and no stdout/stderr log:

```text
printer_v1.pre-campaign.backup.sqlite3
printer_v1.restore-rehearsal.sqlite3
reports/20260727T161750Z-95e40c3efae3-report.campaign-report.json
terminal-summary.json
```

The summary records:

```text
status: OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE
original_exception_type: _ExternalStop
first_terminal_cause: OPERATIONAL_CAMPAIGN_FAILED:_ExternalStop
cleanup_completed: true
lease_released: true
active_owned_work_after: 0
restart_created: false
successor_created: false
closure_errors: []
```

The report records 22 campaign source calls, zero campaign lifecycle Scheduler
calls, `lifecycle_started=false`, and `factory_run_id=null`.

### 3.2 Authoritative campaign and supervision state

The exact campaign, run, and cycle are `TERMINAL_FAILED` at
`2026-07-27T16:24:26.127090+00:00` with the same first cause:

```text
OPERATIONAL_CAMPAIGN_FAILED:_ExternalStop
```

The supervision row is `TERMINAL/FAILED`, has the exact expected owner, and
shows:

```text
heartbeat_at:       2026-07-27T16:17:50.301171+00:00
lease_expires_at:   2026-07-27T16:19:20.301171+00:00
cleanup_completed:  2026-07-27T16:24:26.127090+00:00
lease_released_at:  2026-07-27T16:24:26.127090+00:00
cancellation_requested_at: NULL
cancellation_reason:       NULL
```

The heartbeat timestamp equals campaign lease creation and never advanced.
The lease lock is now absent as expected after successful cleanup.

### 3.3 Initialized lifecycle residue

Factory run `42afd94c-2e5a-40c3-939d-e1941a4033e4` was created at
`2026-07-27T16:24:26.105647+00:00`. It remains:

```text
run_status: RUNNING
selection_batch_id: NULL
selected_token_count: 0
finished_at: NULL
stop_reason: NULL
run-step rows: 0
active/locked factory jobs: 0
```

The DB has no other `RUNNING` factory row. This row was not known to the outer
terminal coordinator because the exception escaped before the lifecycle result
could return its run ID.

## 4. Required findings

### 4.1 Exactly where `_ExternalStop` was raised

`run_one_command_15m_factory` inserted and committed the factory run, then
called `_check_cancellation(cancellation_probe)` at
`src/printer_v1/operator_cli/one_command_15m_factory.py:3596`.

`_check_cancellation` raises `_ExternalStop` at line 307 when its probe returns
a reason. This call is immediately before the lifecycle `try` beginning at line
3597. The `_ExternalStop` handler at lines 3957-3958 therefore could not catch
this instance.

The exact sequence is proven by the DB:

1. factory row created at `16:24:26.105647Z`;
2. zero factory steps and no selection batch attached to that row;
3. outer campaign cleanup at `16:24:26.127090Z`;
4. terminal summary records `original_exception_type=_ExternalStop` and
   `lifecycle_started=false`.

No later cancellation checkpoint fits all four facts.

### 4.2 Who set the stop event and why

The canonical setter was the daemon thread named `campaign-heartbeat` in
`operational_memory_factory_command.py:494-530`.

The thread has two event objects:

- `stop_event`, set only by the main coordinator when asking the thread to end;
- `failure_event`, set only by the heartbeat loop when renewal raises a
  `BaseException` or returns `renewal_confirmed=false`.

The cancellation probe at lines 826-852 checks the heartbeat's retained
failure mapping before it checks the supervision row. Because the supervision
row had no cancellation request and remained `ACTIVE` until terminal cleanup,
its only code-supported reason at the failing probe was the heartbeat failure
mapping, whose suggested cause is `LEASE_RENEWAL_UNCONFIRMED`.

Therefore:

```text
event setter: campaign-heartbeat thread
immediate reason: renew_campaign_lease did not confirm renewal
operator cancellation: not evidenced
```

The failure event itself is not polled directly; `poll_failure()` reads the
mapping whose creation and event setting occur together under the same lock.

### 4.3 Why `heartbeat_at` never advanced

`renew_campaign_lease` advances the DB row only after all of these succeed:

1. exact supervision/owner load;
2. unexpired and monotonic timestamps;
3. exact lease-lock read;
4. atomic lock-file replacement;
5. `BEGIN IMMEDIATE` and exact compare-and-set DB update;
6. DB commit.

It returns `renewal_confirmed=false` for handled campaign, filesystem, or SQLite
errors. The heartbeat loop then stores that result, sets the failure event, and
breaks. The unchanged DB timestamp proves that no DB renewal committed. It does
not identify which prerequisite failed.

### 4.4 Whether lease expiry caused the stop

Lease expiry is not itself an asynchronous stop owner in this command. The
cancellation probe does not compare `lease_expires_at` with current time; it
reacts to the heartbeat failure mapping, an operator-requested `STOPPING` row,
a missing row, or a terminal row.

At the eventual `_ExternalStop`, the original lease was expired. However, the
missing renewal detail prevents proving whether:

- the renewal attempt occurred on time and failed for another reason; or
- process/platform delay caused the first effective renewal attempt to occur
  after expiry, making expiry the renewal error.

Verdict: expiry did not independently raise the stop, but expiry as the
underlying renewal-failure subtype is unproven and cannot be excluded.

### 4.5 Renewal failure subtype

The canonical renewal result would have retained:

```text
renewal_error
renewal_error_type
sqlite_locked
suggested_terminal_cause
```

Those fields stayed only in `_CampaignHeartbeat._failure`. They were not copied
into the outer exception, terminal summary, terminal report, supervision row,
or a log artifact. The report instead collapsed the cause to the exception
class `_ExternalStop`.

Consequently:

| Candidate condition | Audit conclusion |
|---|---|
| SQLite contention | plausible; DB is DELETE-journal/normal-locking and renewal uses bounded `BEGIN IMMEDIATE`, but not proven |
| heartbeat thread failure | the thread deliberately signalled failure and exited; a silent thread death is excluded, but exact caught/returned failure is unavailable |
| ownership mismatch | no mismatch is retained; exact owner later completed cleanup, but the first renewal's lock state was not preserved |
| lease expired before renewal | possible but unproven |
| lock replacement/file condition | possible but unproven |
| operator/platform interruption | no operator cancellation is recorded; a platform scheduling/suspension event has no artifact and is unproven |

Naming any one of these as root cause would exceed the evidence.

### 4.6 Last successful stage and repaired persistence path

The repaired V2-9.8B.16 cross-batch persistence path was reached and succeeded.
The authoritative DB contains this campaign's batch-scoped rows:

- two provider observations;
- two merged candidates;
- two selected-item links;
- two selected token slots;
- eight terminal `SUCCEEDED` discovery-work rows and eight `SUCCEEDED`
  discovery Scheduler jobs;
- two tracking-queue handoffs;
- two holder maturation completions and six holder evidence attempts;
- one `PILOT_INPUT_READY` bundle;
- 22 governed campaign requests in the holder operation ledger.

Both tracking handoff jobs completed at approximately `16:24:26.079Z`; the
origin-activated two-token selection batch was assembled at
`16:24:26.085140Z`. The readiness bundle identifies both selected PumpSwap
pairs and exact holder evidence. The subsequent factory run was committed at
`16:24:26.105647Z`.

Thus the last successful product stage was atomic two-slot discovery/selection
and tracking handoff plus pilot-input readiness. The lifecycle factory was
initialized, but no 15m planning, snapshot, window, audit, or promotion stage
ran.

### 4.7 Whether all retained partial state is safe

The retained state is financially and memory-quality safe, but it is not fully
operationally reconciled.

Safe/fail-closed facts:

- SQLite integrity is `ok` and foreign-key violations are zero;
- campaign-scoped active Scheduler/discovery work is zero;
- no lock owner or campaign lease remains;
- no campaign window, token snapshot, memory window, episode, or fingerprint
  was created for the two selected tokens;
- backup-to-current deltas are zero for retrieval queries/matches, paper
  decisions/decision audits, positions, trade events/trade audits, and paper
  audit reports;
- no restart or successor was created.

Residual operational state:

- factory run `42afd94c-...` remains `RUNNING` with zero steps;
- tracking queue rows 18 and 19 remain `QUEUED`;
- campaign token slots remain `SELECTED` even though the campaign is terminal;
- the terminal report says `factory_run_id=null` and `factory_run=not_found`, so
  it understates retained factory state.

These residues cannot create a paper position, trade, PnL, or clean memory on
their own, and no Scheduler process is active. They can, however, confuse a
future quiescence/preflight or later tracking owner. Therefore the answer to
"whether all retained partial state is safe" is:

```text
SAFE AGAINST FINANCIAL OR CLEAN-MEMORY EFFECT: YES
FULLY TERMINALIZED AND OPERATIONALLY REUSABLE: NO
AUTHORITATIVE CLEANUP/REWRITE AUTHORIZED BY THIS AUDIT: NO
```

### 4.8 Failure classification

Python Builder Guide output:

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
EVIDENCE: pre-try _ExternalStop escape; lost heartbeat failure detail; one orphan RUNNING factory row
OFFICIAL-SOURCE COMPARISON: no provider/official-contract change is implicated
PRINTER-CONTRACT COMPARISON: terminal first cause is not diagnostic; initialized work was not fully reconciled
ROOT CAUSE: heartbeat renewal was unconfirmed, but the exact renewal subtype was not durably preserved
CODE CHANGE JUSTIFIED: YES, through a separate approved design/repair lane only
MINIMUM SAFE RESPONSE: stop; preserve artifacts; design the canonical observability and terminalization repair; do not retry production
```

This is not an expected bounded source stop: the two-token pool, selection, and
readiness gates passed. It is not proven to be an operator or platform
interruption. The committed code demonstrably lost the decisive renewal detail
and failed to terminalize an initialized factory row. Because the requested
underlying heartbeat root cause cannot be selected from the available evidence,
the overall audit verdict remains the required insufficient-evidence verdict.

### 4.9 Minimum justified next lane

The minimum justified next lane is design-only:

```text
V2-9.8B.18 — Heartbeat Failure Evidence and Pre-Lifecycle Terminalization Repair Design
```

That design should be restricted to the existing canonical owners and specify:

1. durable, redacted preservation of the first heartbeat renewal result,
   including failure type, `sqlite_locked`, attempt/observation time, prior
   heartbeat, and prior expiry;
2. one exact terminal cause that cannot collapse to `_ExternalStop`;
3. cancellation handling after factory creation inside the lifecycle terminal
   boundary;
4. exact propagation of an initialized factory run ID to reconciliation;
5. terminalization of zero-step initialized runs without deleting or rewriting
   historical evidence;
6. honest reconciliation of tracking/slot residue;
7. focused disposable proof only, followed by closeout before any separately
   operator-authorized production run.

No production retry is justified from this audit.

## 5. Money-usefulness contribution

The audit protects future money-useful memory by preventing an ambiguous lease
failure from being mistaken for a valid market outcome and by identifying a
`RUNNING` residue that could corrupt later operational accounting. It also
proves that the repaired cross-batch path can retain two independently owned,
holder-evidenced PumpSwap candidates through atomic handoff.

No 15m outcome memory was created, so this execution contributes no clean price
lesson, trade lesson, profit evidence, or decision evidence. Its contribution
is operational honesty: preserve valid intake evidence, reject false completion,
and require exact terminal provenance before spending another bounded source
budget.

## 6. What remains locked

- another production run or live source use;
- automatic retry, resume, restart, or successor creation;
- authoritative cleanup, rewrite, or manual terminalization of retained rows;
- clean-memory promotion from this execution;
- 1h, 4h, 12h, or 24h production expansion;
- V2-10 and V2-11;
- retrieval activation;
- paper decisions and BUY/SELL/HOLD;
- positions, trade events, paper audits, and PnL;
- live execution, wallets, private keys, signing, and real funds;
- paid APIs;
- scoring, ranking, confidence percentages, and weighted logic;
- embeddings and vectors.

## 7. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Evidence/current effect | Required control |
|---|---|---|
| renewal subtype lost | prevents distinguishing SQLite, expiry, lock, or platform cause | durably persist a redacted first renewal failure before cooperative stop |
| `_ExternalStop` outside lifecycle `try` | initialized factory run bypassed inner terminal owner | move/check the boundary through the canonical terminal path |
| factory run remains `RUNNING` | quiescence and future ownership can be misread | design exact owned terminal reconciliation; no audit-time DB write |
| queued tracking and selected slots remain | valid intake is retained but operational disposition is ambiguous | include queue/slot reconciliation semantics in design |
| report says factory run not found | terminal artifact understates authoritative residue | propagate exact initialized run identity into reporting/reconciliation |
| DELETE-journal write contention is plausible | heartbeat and operational writers share SQLite | prove rather than assume with durable failure fields and disposable contention coverage |
| no stdout/stderr capture | console-only failure text is unavailable after the fact | do not fabricate logs; design truthful durable structured evidence |
| two selected tokens produced no 15m outcome | source budget created intake value but no memory growth | do not count as corpus growth or authorize a retry from row count |
| historical retrieval/decision rows exist | could be mistaken for campaign deltas | preserve exact backup comparison; deltas for this execution are zero |

## 8. Checks and closeout status

Checks were static/read-only only:

- exact HEAD and initial clean-worktree verification;
- active source-stack and canonical-owner inspection;
- read-only authoritative and backup SQLite queries;
- operation artifact inventory and content inspection;
- SQLite integrity and foreign-key checks;
- exact campaign/run/cycle/supervision/discovery/selection/tracking/factory state
  reconciliation;
- backup/current locked-capability count comparison;
- lease-lock absence check.

No tests, Python execution, source calls, production process, migration,
authoritative write, repair, tag, or push was performed.

```text
AUDIT COMPLETENESS: PASS
ROOT-CAUSE SUBTYPE PROOF: BLOCKED_INSUFFICIENT_EVIDENCE
PRODUCTION RETRY AUTHORIZED: NO
```
