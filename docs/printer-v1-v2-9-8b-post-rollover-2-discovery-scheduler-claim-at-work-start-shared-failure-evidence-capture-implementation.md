# Printer V1 V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Evidence-Capture Implementation

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Evidence-Capture Design and Instrumentation Implementation`

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_SHARED_FAILURE_EVIDENCE_CAPTURE_IMPLEMENTATION_PASS`

The implementation preserves the original generic discovery exception and
allowlisted in-transaction Scheduler/discovery state before the existing
`SHARED_FAILURE` translation and rollback. The exact offline proof harness can
now preserve the closed disposable Migration-050 database plus one structured
failure artifact outside temporary-directory cleanup.

No composition was run.

## 2. Baseline

| Item | Value |
| --- | --- |
| Starting HEAD | `f765b6d1201e64bd2d1d6b6514128b6b7351626d` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Starting tracked tree | Clean |
| Upstream state at start | 3 ahead / 0 behind |
| Preserved comparison worktree | `/private/tmp/mp-preclaim`, detached `8fb4256c70d4e81660c177238253322cb37ae947` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` — permanently non-reusable |

Pre-existing untracked `.DS_Store`, operator-run artifacts, and authorization
artifacts were preserved and excluded from the commit.

## 3. Accepted evidence gap

The blocked report adopts these facts:

- the authorized exact public composition returned discovery `SHARED_FAILURE`;
- its discovery transaction rolled back;
- the original exception/traceback was not preserved;
- temporary cleanup deleted the disposable Migration-050 database;
- claim/work state immediately before rollback cannot be determined;
- the completed pre-repair comparison at `8fb4256` was unauthorized and is not
  proof evidence;
- no tracked source/test mutation and no durable database survived;
- zero-network is only absence of discovered evidence, not packet-level proof;
- classification is `INSUFFICIENT_EVIDENCE`;
- no underlying production repair is justified.

## 4. Design decision and stop gate

The design passed the narrow stop gate. The implementation is limited to:

1. executor-local context at the existing generic discovery exception boundary;
2. read-only pre-rollback snapshot and rollback-result recording;
3. existing `CampaignExecutionResult.fault_details` propagation;
4. proof-only closed disposable DB and JSON artifact preservation;
5. exact proof-harness failure hook and directly affected tests.

It requires no Scheduler/accounting semantic change, schema/migration, Source
Governor/provider change, retry, transaction-boundary redesign, broad logging
architecture, or authoritative DB mutation.

## 5. Files changed

| File | Purpose |
| --- | --- |
| `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-focused-offline-proof-blocked.md` | Final blocked proof adoption |
| `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-shared-failure-evidence-capture-design.md` | Approved evidence-capture design and stop gate |
| `src/printer_v1/discovery/combined_executor.py` | First-exception, stage/identity, pre-rollback state and rollback diagnostics |
| `src/printer_v1/operator_cli/offline_shared_failure_evidence.py` | Proof-only disposable DB copy and structured artifact owner |
| `tests/test_v2_9_8b_shared_failure_evidence_capture.py` | Direct deterministic evidence-capture tests |
| `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py` | Failure-only preservation hook for the later bounded proof |
| `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-shared-failure-evidence-capture-implementation.md` | This report |

## 6. Diagnostic owner

`CombinedPumpfunCampaignExecutor` owns one reset context per executor execution.
It records exact progress around the existing work-start owner:

```text
DISCOVERY_WORK_BEFORE_ENQUEUE
-> DISCOVERY_WORK_AFTER_ENQUEUE_BEFORE_CLAIM
-> DISCOVERY_WORK_AFTER_CLAIM_BEFORE_INSERT
-> DISCOVERY_WORK_RUNNING / DISCOVERY_WORK_GOVERNED_EXECUTION
-> existing terminal/persistence stages
```

The context is instance-local, not a mutable module-global campaign owner. It
does not create or emit Scheduler transitions. The observed-transition list is
updated only after an actual Scheduler owner call returns and is never submitted
to accounting.

## 7. Exception-preservation contract

For an unexpected `Exception` at the generic boundary, `fault_details` now
contains:

- schema `DISCOVERY_SHARED_FAILURE_DIAGNOSTIC_V1`;
- immutable `first_failure` classification, exception class, and sanitized
  message;
- exact stage and known batch/work/job identities;
- enqueue-created, claim-returned/result/status, expected/observed lock owner,
  work-insert, and owner-transition state;
- pre-rollback snapshot;
- rollback started/completed;
- ordered secondary failures.

The returned terminal remains `FAILED` / `SHARED_FAILURE`; failure ceilings,
cancellation, successor/restart false, and all other fail-closed behavior remain
unchanged.

A pre-rollback snapshot failure or rollback failure is secondary. It cannot
replace the original exception. A proof artifact-write failure raises
`OfflineSharedFailureEvidenceError`, which carries the original first failure
and the secondary write diagnostic separately.

## 8. Pre-rollback state contract

Allowlisted read-only SQL captures, when allocated:

- Scheduler job identity/kind/target/status, lock owner/timestamps, start/finish,
  retry count, and row timestamps;
- discovery work identity/link/type/state/deadline/terminal fields;
- discovery batch identity/state/terminal fields;
- actual executor-observed Scheduler owner transitions;
- accountable batch/work/job projection;
- `connection.in_transaction`.

The snapshot says `ACTIVE_TRANSACTION_MAY_INCLUDE_UNCOMMITTED_STATE`, separately
marks pre-existing Scheduler rows, and lists attempt changes expected to
disappear after successful rollback. It never calls transaction-local state
durable truth.

## 9. Disposable database preservation contract

`offline_shared_failure_evidence.py` is proof-only and is not imported by normal
discovery. The exact proof harness invokes it only when the returned first cause
is `SHARED_FAILURE`, after the public coordinator returns and connection owners
have closed.

It:

- rejects the canonical authoritative database path;
- requires explicit `connections_closed=True`;
- creates a unique `<artifact-root>/<execution-id>` directory;
- inventories `-wal`, `-shm`, and `-journal` companions;
- checkpoints WAL when required;
- uses SQLite's backup API into
  `shared-failure-disposable-migration-050.sqlite3`;
- closes connections before SHA-256 and inspection;
- requires no destination sidecars;
- runs read-only integrity and FK checks;
- records Migration-050 head application;
- writes canonical `shared-failure-evidence.json`;
- marks the copy as evidence-only, never production.

The helper refuses success results before creating an artifact directory.

## 10. Structured failure artifact

The JSON contains:

- execution ID, exact baseline Git HEAD and tracked-tree flags;
- exact pytest node ID;
- first `SHARED_FAILURE` classification and sanitized exception;
- discovery stage and batch/work/job/claim/Scheduler state;
- pre-rollback truth layers and rollback result;
- preserved DB absolute path and SHA-256;
- journal/checkpoint/sidecar, integrity, FK, and migration results;
- frozen-transport/patched-urllib zero-network assertion boundary, explicitly
  not packet-level proof;
- retry, rerun, resume, restart, and successor counts.

The existing public terminal/report owner still receives `fault_details`; the
new helper does not add an unrelated logger or write diagnostics to the
authoritative database.

## 11. Redaction rules

Before diagnostic persistence:

- HTTP(S) URLs are replaced;
- bearer values and API-key/authorization/credential/password/secret/token
  assignments are replaced;
- sensitive configured environment values are replaced without recording the
  environment name or value;
- whitespace is normalized and messages are bounded;
- raw provider payloads, raw environment mappings, credentials, sensitive RPC
  URLs, and raw tracebacks are excluded;
- `last_error` is excluded from row snapshots.

Tests prove configured RPC/API values and URLs are absent from the artifact.

## 12. Focused tests

### 12.1 New evidence-capture tests

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_shared_failure_evidence_capture.py \
  tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py
Result: 18 passed
```

Coverage includes:

- all four claim/work stages;
- original class/message/stage/batch/work/job preservation;
- unchanged `SHARED_FAILURE` terminal;
- successful rollback;
- rollback failure as secondary;
- no synthetic Scheduler terminal and no alternate claim;
- successful discovery result has no failure details;
- failure-only DB preservation after connections close;
- source-temp cleanup survival, SHA-256, integrity, FK, migration and sidecars;
- secret/RPC/API/URL redaction;
- artifact-write failure precedence.

### 12.2 Nearest claim/parity/Scheduler regressions

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py \
  tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py \
  tests/test_phase3_scheduler_resource_governor.py
Result: 73 passed, 30 subtests passed
```

### 12.3 Full-run wiring/accounting semantics

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py
Result: 30 passed, 6 subtests passed
```

Combined focused total:

`121 passed, 36 subtests passed`

Python compilation for all changed Python files passed. `git diff --check`
passed.

## 13. Tests and compositions not run

Not run:

- exact public composition;
- unauthorized pre-repair comparison;
- live/operational discovery or Memory Factory command;
- wrappers;
- provider/RPC/WebSocket calls;
- authoritative database commands or mutation;
- broad/full pytest.

## 14. Production semantics preserved

- claim-at-work-start remains enqueue → exact claim → work insert → governed
  work → parity terminal;
- exact Scheduler job ownership and lock identity are unchanged;
- no Scheduler row is created or mutated for diagnostics;
- no fake transition is emitted or injected;
- accounting and campaign acceptance law are unchanged;
- Source Governor and provider contracts are unchanged;
- normal successful discovery returns no failure diagnostics;
- no retry/restart/successor is added;
- the unknown underlying `SHARED_FAILURE` is not repaired.

## 15. Money-usefulness contribution

The later single bounded composition can retain enough evidence to classify its
first failure instead of guessing from `SHARED_FAILURE`. This protects campaign
accounting and future clean-memory claims from speculative repairs while adding
no financial capability.

## 16. What improves

- First operational exception survives generic translation in sanitized form.
- Claim/work state is distinguishable at each work-start stage.
- Transaction-local state is visible without being mislabeled durable.
- Rollback and diagnostic failures retain correct precedence.
- A failed disposable database survives harness cleanup with hash/integrity/FK
  evidence.
- The next proof can classify whether enqueue/claim/work insert occurred before
  rollback.

## 17. What remains locked

- exact public-composition proof PASS and closeout;
- production readiness, fresh authorization, and live/operational attempts;
- reuse/replacement of the consumed authorization;
- retries, resumes, restarts, and successors;
- memory generation beyond existing locks and longer windows;
- retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL;
- wallets, private keys, signing, execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Detail |
| --- | --- |
| Functionality risk | Snapshot rows are transaction-local; consumers must honor the explicit visibility labels |
| Functionality risk | A failure before identity allocation correctly leaves work/job fields null |
| Setback | The underlying authorized `SHARED_FAILURE` remains unknown until a separate bounded proof |
| Setback | The unauthorized comparison remains excluded and supplies no regression evidence |
| Test finding | Initial diagnostic test exposed an incorrect batch `updated_at` assumption; the allowlist was corrected to the actual schema before PASS |
| Efficiency | Artifact copy occurs only on proof failure and only after owners close; success pays no copy/write cost |
| Evidence risk | Frozen transport plus urllib patch is not packet-level network proof and is labeled accordingly |
| Operational risk | Evidence copies must not be used as production or restore databases |

## 19. Proof still required

The implementation does not prove the exact public composition. A later single
bounded offline run must use the new failure boundary and preserve its artifact
whether it passes or fails. Any failure must be classified from the preserved
first exception, pre-rollback snapshot, rollback outcome, and read-only DB copy.

## 20. Exact next lane

`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Bounded Offline Evidence-Capture Proof`

That lane alone may run the exact public composition once with frozen transports
and a disposable Migration-050 database. It may not use the comparison worktree,
providers, authoritative DB, consumed authorization, retry, or financial paths.

## 21. Final statement

The implementation follows the approved narrow design: preserve the first
generic discovery exception and pre-rollback state, record rollback honestly,
propagate through the existing fault-details/report owner, and preserve a closed
disposable database only in the offline proof harness. Production discovery,
Scheduler, accounting, Source Governor, schema, authorization, and financial
semantics remain unchanged.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_SHARED_FAILURE_EVIDENCE_CAPTURE_IMPLEMENTATION_PASS`
