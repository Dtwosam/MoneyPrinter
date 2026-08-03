# Printer V1 V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Evidence-Capture Design

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Evidence-Capture Design and Instrumentation Implementation`

Baseline:
`f765b6d1201e64bd2d1d6b6514128b6b7351626d`

Accepted evidence classification:
`INSUFFICIENT_EVIDENCE`

Consumed authorization:
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` — permanently non-reusable.

## 1. Design verdict

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_SHARED_FAILURE_EVIDENCE_CAPTURE_DESIGN_PASS`

The smallest sufficient boundary is:

1. preserve sanitized exception and execution context inside
   `CombinedPumpfunCampaignExecutor.execute` immediately before the existing
   generic exception is translated to `SHARED_FAILURE`;
2. take a read-only, allowlisted snapshot through the same borrowed discovery
   connection before rollback;
3. perform the existing rollback while recording started/completed and any
   secondary rollback failure;
4. return the diagnostic structure through the existing
   `CampaignExecutionResult.fault_details` contract;
5. let a proof-only offline helper copy the closed disposable database and write
   one execution-scoped failure artifact before the harness temporary directory
   is cleaned.

No Scheduler, accounting, schema, migration, provider, retry, or transaction
boundary change is required.

## 2. Authority and accepted gap

This design follows the active Printer stack and the claim-at-work-start audit,
design, implementation, and blocked proof report. It accepts without reopening:

- the implementation baseline and focused-test PASS;
- authorized `SHARED_FAILURE` and transaction rollback;
- missing original exception/traceback;
- deleted disposable Migration-050 database;
- unknown claim/work state before rollback;
- completed but unauthorized comparison at `8fb4256`;
- no tracked mutation and no durable database;
- `INSUFFICIENT_EVIDENCE` and no justified underlying production repair.

## 3. Canonical diagnostic owners

| Evidence | Owner | Persistence boundary |
| --- | --- | --- |
| First exception and in-flight stage/identity | `CombinedPumpfunCampaignExecutor.execute` plus executor-local context | In-memory `fault_details`; never authoritative DB |
| Pre-rollback Scheduler/discovery snapshot | Same executor and borrowed active connection | In-memory allowlisted snapshot; read-only SQL only |
| Rollback outcome | Same executor | `fault_details.rollback` |
| Public terminal/report propagation | Existing `CampaignExecutionResult.fault_details` → origin driver → public terminal report | Existing report owner; no new global logger |
| Failed disposable DB copy and structured artifact | Offline proof helper invoked only by the exact proof harness on failure | Execution-scoped external artifact directory |

The executor instance is one execution-scoped owner. Its context is reset at
`execute` start and cannot collide with another executor/run. No module-global
campaign truth or unrelated logger is added.

## 4. Exception-preservation contract

Before translation to `SHARED_FAILURE`, capture:

- original exception class;
- sanitized exception message;
- exact diagnostic discovery stage;
- current work type;
- discovery batch ID;
- discovery work ID, if allocated;
- linked Scheduler job ID, if allocated;
- enqueue completed;
- claim returned;
- exact claim result and observed Scheduler status;
- expected and observed lock owner;
- discovery work insertion completed;
- rollback started and rollback completed.

The first operational exception is immutable. Rollback, snapshot, close, or
artifact-write faults are secondary diagnostics and never replace its class,
message, classification, or `SHARED_FAILURE` terminal cause.

Sanitization is allowlisted and bounded:

- remove control characters and cap length;
- redact HTTP(S) URLs, bearer values, credential/API-key/token/secret/password
  assignments, and sensitive configured environment values;
- never include raw provider payloads, environment mappings, credentials,
  authenticated URLs, or raw traceback text in the structured artifact.

## 5. Exact stage and claim state model

The executor records only actual owner progress. It does not emit Scheduler
events or fabricate transitions.

| Stage | enqueue | claim returned/result | work insert |
| --- | ---: | --- | ---: |
| `DISCOVERY_WORK_BEFORE_ENQUEUE` | false | false / null | false |
| `DISCOVERY_WORK_AFTER_ENQUEUE_BEFORE_CLAIM` | true | false / null | false |
| `DISCOVERY_WORK_AFTER_CLAIM_BEFORE_INSERT` | true | true / `ACQUIRED` | false |
| `DISCOVERY_WORK_GOVERNED_EXECUTION` | true | true / `ACQUIRED` | true |

Other internal persistence stages continue to use the executor's existing exact
stage/object markers. The diagnostic context retains current work identity
through later work so a generic failure remains attributable.

`observed_scheduler_transitions` is a diagnostic record of successfully returned
owner calls (`SCHEDULER_ENQUEUE`, `SCHEDULER_CLAIM`, and a terminal only when the
terminal owner actually returned). It is not sent to the Scheduler observer or
accounting ledger and cannot satisfy transition coverage.

## 6. Pre-rollback read-only snapshot

Immediately inside the generic handler and before rollback, use only allowlisted
`SELECT` statements on the active discovery connection.

Capture where technically available:

- linked `printer_scheduler_jobs` row: id, name/kind, target, status,
  `lock_owner`, `locked_at`, `started_at`, `finished_at`, retry count, and
  created/updated timestamps (exclude `last_error`);
- linked `printer_discovery_work` row: work/batch/campaign/run/cycle identities,
  Scheduler job ID, type/state, deadline, terminal timestamps/cause;
- discovery batch: batch/campaign/config/run/cycle identities, batch state and
  timestamps;
- actual Scheduler owner transitions recorded by the executor context;
- `connection.in_transaction` and owner-known transaction state;
- accountable identity projection for batch/work/job.

Snapshot-query failure is secondary and sanitized. It does not prevent rollback
and does not replace the first operational failure.

### 6.1 Truth layers

The artifact must label three distinct truth layers:

1. **Active-transaction visibility** — rows read through the failing connection
   may include uncommitted changes visible only to that connection.
2. **Durably committed outside the transaction** — only pre-existing/rebound
   rows proven committed before the attempt may be described this way; newly
   inserted discovery rows are not.
3. **Expected after rollback** — attempt-local batch/work/jobs and uncommitted
   Scheduler transitions are expected to disappear after successful rollback.

No uncommitted row or transition may be represented as durable production truth.

## 7. Rollback contract

Set `rollback.started=true` immediately before calling the existing connection
rollback. Set `rollback.completed=true` only after it returns. If rollback
raises:

- retain the original operational exception as `first_failure`;
- record the rollback exception class and sanitized message under
  `secondary_failures`;
- report `rollback.completed=false`;
- allow ordinary connection close to release resources;
- keep terminal result fail-closed as `SHARED_FAILURE`.

## 8. Disposable Migration-050 database preservation

The later bounded proof harness supplies an external artifact root. On proof
failure only, the helper creates exactly:

```text
<artifact-root>/<execution-id>/
  shared-failure-disposable-migration-050.sqlite3
  shared-failure-evidence.json
```

Requirements:

1. The public composition and all borrowed/owned DB connections close first.
2. Reject the canonical authoritative database path and require a disposable
   source path.
3. Inspect `-wal`, `-shm`, and `-journal` companions.
4. Open the closed source, run a bounded WAL checkpoint when applicable, and use
   SQLite backup into the evidence copy so committed WAL content is included.
5. Close source and destination connections before hashing or inspection.
6. Require no destination sidecars after close; record source/destination
   sidecar handling.
7. Record SHA-256 of the exact copied bytes.
8. Reopen the copy read-only and run `PRAGMA integrity_check` plus
   `PRAGMA foreign_key_check`.
9. Perform all follow-up inspection on the copy, never the source or
   authoritative database.

The copy is immutable evidence only. It is never a restore target, production
database, campaign input, authorization object, or future write target.

## 9. Structured failure artifact

One canonical JSON artifact contains:

- schema version and execution identity;
- baseline full Git HEAD and tracked-tree state;
- exact test node ID;
- first failure classification (`SHARED_FAILURE`);
- sanitized exception class/message and any secondary diagnostics;
- discovery stage, work type, batch/work/job identities;
- enqueue, claim, Scheduler, and discovery-work state;
- active-transaction snapshot and truth-layer labels;
- rollback result;
- preserved DB path, SHA-256, integrity, FK and sidecar results;
- zero-network assertion boundary (frozen transports plus patched standard
  urllib call count, explicitly not packet-level proof);
- retry/resume/restart/successor counts.

JSON uses sorted keys, bounded allowlisted values, UTF-8, no NaN, and a final
newline. The execution directory is create-once to prevent collisions. If JSON
write fails, the helper surfaces a typed secondary diagnostic that still carries
the first operational failure; it never reports a replacement first cause.

## 10. Test seam

Use a narrow optional executor-local diagnostic fault callback. It is absent in
ordinary construction and therefore changes no default behavior. Focused tests
may raise a deterministic exception at the four stage tokens in section 5.

Rollback is likewise an optional injected callable for deterministic secondary
rollback-failure testing. Default behavior remains `connection.rollback`.

No provider, Scheduler, transaction, or accounting production behavior is
changed to make the capture testable.

## 11. Capability locks

Diagnostic capture:

- creates no Scheduler work;
- performs no Source Governor or provider request;
- changes no accounting rule;
- injects no fake Scheduler transition;
- does not mutate Scheduler rows to preserve evidence;
- writes nothing into the authoritative database;
- does not alter normal successful discovery behavior;
- does not suppress or replace the first operational exception;
- adds no retry, resume, restart, or successor;
- does not unlock runtime, memory, retrieval, decisions, BUY/SELL/HOLD,
  positions, trades, audits, PnL, wallets, execution, longer windows, paid APIs,
  scoring, ranking, confidence, weighted logic, embeddings, or vectors.

## 12. Focused verification plan

Use frozen transports and disposable databases only. Verify:

1. exception class/message/stage/batch/work/job preservation;
2. unchanged `SHARED_FAILURE` fail-closed result and first-failure precedence;
3. rollback success and secondary rollback failure;
4. claim-state accuracy at all four stages;
5. no synthetic transition and no alternate claim;
6. success emits no failure diagnostics/artifact;
7. failure-only closed-DB preservation, hash, integrity/FK, sidecars, and
   survival after source temporary cleanup;
8. secret/RPC/API redaction;
9. existing claim-at-work-start, discovery parity, and accounting regressions;
10. Python compilation, `git diff --check`, and exact changed-file scope.

The exact public composition, pre-repair comparison, live operation, providers,
RPC/WebSocket, authoritative DB, wrappers, and broad/full pytest remain forbidden.

## 13. Design stop-gate decision

Required changes are limited to:

- diagnostic context at the existing generic discovery exception boundary;
- a proof-only failure artifact/database preservation helper;
- exact proof-harness failure hook;
- directly affected deterministic tests;
- this design, blocked report, and implementation report.

The design requires no Scheduler semantic or accounting change, schema/migration,
Source Governor/provider change, retry, transaction-boundary redesign, broad
logging architecture, or authoritative DB mutation.

Therefore narrow implementation is allowed.

## 14. Money-usefulness contribution

The next single offline composition can classify its first failure instead of
losing it behind `SHARED_FAILURE`. This prevents speculative production repair,
false Scheduler-claim claims, and polluted readiness conclusions while preserving
all financial locks.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Disposition |
| --- | --- |
| Snapshot contains uncommitted state | Label active-transaction visibility and rollback expectation explicitly |
| Exception text contains secrets/URLs | Allowlist fields and redact before any durable write |
| Snapshot query fails | Preserve as secondary; still attempt rollback |
| Rollback fails | Preserve as secondary; first operational exception remains first |
| DB copied while open/WAL active | Require owner close, checkpoint/SQLite backup, sidecar inventory |
| Artifact collision | Create-once execution directory and fixed filenames |
| Artifact writer fails | Surface typed secondary diagnostic; never report false PASS |
| Diagnostics alter accounting | Never emit/inject Scheduler events or write authoritative rows |
| Exact proof remains unrun | Separate bounded evidence-capture proof lane remains mandatory |

## 16. Final design statement

The approved implementation preserves the first generic discovery exception and
allowlisted active-transaction state before rollback, carries it through the
existing `fault_details` report contract, and preserves a closed disposable DB
plus one structured artifact only in the offline proof harness. It makes no
semantic production repair and changes no Scheduler, accounting, schema,
provider, retry, or financial behavior.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_SHARED_FAILURE_EVIDENCE_CAPTURE_DESIGN_PASS`
