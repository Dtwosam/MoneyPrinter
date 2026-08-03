# Printer V1 V2-9.8B Post-Rollover-2 Exact Public Composition Post-Origin-Driver Repair Bounded Offline Proof

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Exact Public Composition Post-Origin-Driver Repair Bounded Offline Proof`

Lane type: one exact offline public-composition execution, read-only evidence
inspection, failure classification, and documentation only.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_EXACT_PUBLIC_COMPOSITION_POST_ORIGIN_DRIVER_REPAIR_ROOT_CAUSE_CAPTURED`

The one permitted exact public composition failed outside the returned
`SHARED_FAILURE` path. Its ordinary first visible failure was preserved exactly:

```text
printer_v1.operator_cli.operational_memory_factory_command.OperationalMemoryFactoryError:
SIX_UNIT_ACCOUNTING_BLOCKED
```

The public coordinator received a non-lifecycle result with no sealed stage
evidence, then called `_finalize_operational_six_unit_accounting` with
`stage_evidences=(None,)`. The committed finalizer deterministically rejects the
non-mapping item before the original returned terminal can be mapped, reported,
or passed to the failure-only evidence helper.

Primary classification:

`COMMITTED_CODE_DEFECT`

The visible defect is in the committed public coordinator's pre-lifecycle
six-unit failure-propagation boundary. It is not relabelled as `SHARED_FAILURE`.
The underlying activation terminal/cause remains unavailable and is not guessed
or repaired in this lane.

## 2. Baseline

| Item | Exact result |
| --- | --- |
| Required HEAD | `4cec9a2dfe7fc3d6b535e384a464cfc4417c3df5` |
| Required commit | `Prove origin driver activation failure propagation` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked tree at preflight | Clean; no staged or unstaged tracked changes |
| Upstream | `origin/agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Ahead / behind at preflight | 7 ahead / 0 behind |
| Preserved untracked evidence | `.DS_Store`, authoritative Migration-050 operator evidence, and consumed final-authorization evidence |
| Relevant Printer process | None; only the process-filter commands matched themselves |

No fetch, pull, reset, checkout, rebase, push, or branch change occurred.

## 3. Proof execution identity

| Identity | Value |
| --- | --- |
| External proof scope | `20260803T183529Z-post-origin-driver-exact-public-composition-4cec9a2` |
| Public execution identity | `20260803T183717Z-8c6fc1b39c37` |
| Campaign identity | `20260803T183717Z-8c6fc1b39c37-campaign` |
| Campaign run identity | `20260803T183717Z-8c6fc1b39c37-campaign-run` |
| Composition count | Exactly 1 |
| Process result | Exit 1; 1 failed in 3.42 seconds |

The public identities are preserved in the full traceback's
`CampaignSixUnitOwner` representation.

## 4. Exact command

```bash
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition
```

Execution-only environment bindings:

- `TMPDIR` pointed at the execution-scoped external runtime directory;
- `PRINTER_V1_OFFLINE_FAILURE_EVIDENCE_ROOT` pointed at its external
  `shared-failure` directory;
- `PYTHONDONTWRITEBYTECODE=1`.

Stdout and stderr were redirected separately into the same external proof scope.
No pytest option, node, fixture, source, or test was changed.

## 5. Preflight

| Gate | Result |
| --- | --- |
| Exact clean baseline | PASS |
| Exact node collection | PASS — exactly 1 node collected |
| Evidence helper import | PASS — `printer_v1.operator_cli.offline_shared_failure_evidence` |
| Evidence helper compile | PASS |
| Canonical migration head | PASS — `050_campaign_scheduler_ownership_scope.sql` |
| External artifact directory | PASS — created and writable |
| Relevant process scan | PASS |
| Database boundary | PASS — test creates only a fresh `dtw23-migration-050.sqlite3` with `apply_migrations` |
| Pump origin/graduation transport | Frozen fake transport |
| Secondary transport | Fake empty transport |
| Snapshot/context transports | Fixture adapters |
| Migration transport | Forced unavailable (`None`) by the exact proof owner |
| RPC/provider configuration | Patched to `https://unused.invalid`; no live transport owner available |
| Ordinary urllib boundary | Patched for the public call |
| Operator/live authorization | Not required; preflight is proof-patched and no external marker is created or applied |

Preflight passed, so the one composition execution was permitted.

## 6. Exact result and first-failure ownership

The captured call chain is:

```text
exact public test node
-> public_command._run_operational_campaign
-> returned non-lifecycle result
-> public pre-lifecycle accounting finalization
-> _finalize_operational_six_unit_accounting
-> reject stage_evidences=(None,)
-> OperationalMemoryFactoryError: SIX_UNIT_ACCOUNTING_BLOCKED
```

The traceback preserves these exact finalizer inputs:

| Input | Captured value |
| --- | --- |
| `accounting_owner.stage_evidence_count` | 0 |
| `stage_evidences` | `(None,)` |
| Action-local source-operation count | 8 |
| Action-local transport identities | `None` |
| Owner stage diagnostics | Empty |
| Owner Scheduler identities | Empty |
| Owner lifecycle-reservation identities | Empty |
| Owner local-validation identities | Empty |

Committed source history shows:

- the rejecting finalizer branch at lines 1515–1525 is committed code, primarily
  from `b168c57d`;
- the public call when `result.lifecycle_started` is false is committed code at
  lines 2087–2095, introduced by `02f87289`;
- neither boundary belongs to this proof harness.

The defect is therefore the production public coordinator's inability to carry a
returned pre-lifecycle terminal through strict six-unit finalization when no
sealed stage mapping exists. Strict accounting is not weakened: accepting
`None` as evidence would be false evidence. The safe future response is a
narrow failure-propagation design, not an accounting bypass.

## 7. Origin-driver observer result

The origin-driver repair did not emit or seal an empty completed
`DISCOVERY_SELECTION_TERMINAL` stage:

- owner stage count was zero;
- stage diagnostics and all accountable identity collections were empty;
- the former `EMPTY_STARTED_STAGE_EVIDENCE` observer failure did not recur.

This is consistent with the established repaired ordering: a non-completed
activation returns before the successful discovery-stage observer. The public
coordinator then masked that returned terminal with the later
`SIX_UNIT_ACCOUNTING_BLOCKED` finalization error.

No successful observer result, two-slot callback, or lifecycle start was proved.

## 8. Scheduler transition table

No accountable Scheduler identity reached the public stage owner, and the
disposable database was removed by test cleanup before it could be preserved.
Transition truth cannot be reconstructed.

| Scope | Enqueue | Claim | Terminal | Evidence status |
| --- | --- | --- | --- | --- |
| Discovery Scheduler jobs | Unavailable | Unavailable | Unavailable | No durable DB or structured failure artifact |
| Handoff Scheduler jobs | Not proved | Not proved | Not proved | No successful selection handoff |
| Lifecycle snapshot/close jobs | Not reached / not proved | Not reached / not proved | Not reached / not proved | `lifecycle_started` was false at the public finalizer |

No transition is invented. Any enqueue/claim/work rows that may have existed
inside an activation transaction are not called durable.

Claim-at-work-start remains established only by the prior focused deterministic
proof; this execution did not produce the required public-composition transition
evidence.

## 9. Window identities, accounting, and campaign acceptance

| Requirement | Exact result |
| --- | --- |
| Completed `WINDOW_15M` closes | 0 proved; lifecycle did not start |
| First window identity | Unavailable |
| Second window identity | Unavailable |
| Strict six-unit accounting | Fail-closed at pre-lifecycle finalization on `(None,)` |
| Empty completed started stage | Not emitted |
| Action-local source count | 8, count-only; no identity reconciliation |
| Final campaign acceptance | Not reached |
| `CAMPAIGN_PASS` | Not reached / false as a proof claim |

A passing execution is not claimed, and this result does not explain the
historical `SHARED_FAILURE`.

## 10. Residue matrix

The exception escaped before the test's database inspection, terminal summary,
report-only replay, and residue assertions. Temporary cleanup removed the source
database. These results are therefore unavailable, not zero.

| Residue surface | Result |
| --- | --- |
| Scheduler active jobs | Unavailable |
| Scheduler locks | Unavailable |
| Discovery work | Unavailable |
| Lifecycle work | Not reached; durable count unavailable |
| Factory work | Not reached; durable count unavailable |
| Campaign ownership/runs | Unavailable |
| Leases/supervision | Unavailable |
| Proof supervision/state | Unavailable |

No production or authoritative database was opened, restored, or mutated.

## 11. Evidence artifacts and hashes

External execution directory:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T183529Z-post-origin-driver-exact-public-composition-4cec9a2
```

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| Full stdout and traceback | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T183529Z-post-origin-driver-exact-public-composition-4cec9a2/stdout.txt` | `08985c2d2c357821b436026297e61c1d7d825d40e544102a085f32594c144351` |
| Full stderr | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T183529Z-post-origin-driver-exact-public-composition-4cec9a2/stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Stdout size is 8,141 bytes. Stderr is empty.

Structured `SHARED_FAILURE` artifact: **not created**. The exception occurred
outside a returned `SHARED_FAILURE` terminal, so the committed failure-only
helper was not invoked.

## 12. Disposable database and verification

| Evidence | Result |
| --- | --- |
| Source database name | `dtw23-migration-050.sqlite3` under the execution `TMPDIR` |
| Exact temporary source path | Not printed; removed by `TemporaryDirectory` cleanup |
| Evidence-copy path | Not created; no public terminal summary was written for the copy sidecar to observe |
| SQLite sidecars | None preserved; source unavailable after cleanup |
| Database SHA-256 | Unavailable |
| Migration-050 verification on preserved DB | Unavailable |
| `PRAGMA integrity_check` | Unavailable |
| `PRAGMA foreign_key_check` | Unavailable |

Preflight confirmed the canonical migration head only. It is not substituted for
post-execution verification of the deleted database. No database is restored
into production.

## 13. Retry, restart, resume, comparison, and successor

| Boundary | Count/result |
| --- | --- |
| Composition executions | 1 |
| Retries | 0 |
| Reruns | 0 |
| Comparison executions | 0 |
| Restarts | 0 created by this proof |
| Resumes | 0 |
| Automatic successors | 0 created by this proof |

The failed evidence-copy sidecar launch before the composition was a shell
quoting error only. It did not start pytest or any Printer owner and therefore
does not add a composition execution. The corrected sidecar observed no public
terminal summary, copied no database, and was stopped after the sole process
result.

## 14. Zero-network boundary

The exact node made all source transports frozen, fake, patched, or unavailable:

- frozen Pump fixture transport;
- fake empty secondary transport;
- fixture snapshot and context adapters;
- migration transport removed by the proof owner;
- RPC resolution patched to an unused invalid URL;
- `urllib.request.urlopen` patched around the public call.

No provider, RPC, WebSocket, wallet, paid API, or external source transport was
available to the composition. Because the exception escaped before
`network_open.assert_not_called()`, a final mock call-count assertion was not
durably produced. This is a structural frozen/blocked transport boundary, not
packet-level or host-wide proof.

No external authorization, wallet, signing, execution, or real-fund path was
configured.

## 15. Locked-capability result

The execution did not reach the test's locked-capability table queries. Exact
post-execution counts are unavailable because the disposable DB was deleted.

No retrieval, memory generation, decision, BUY/SELL/HOLD, position, trade,
paper-audit, PnL, wallet, signing, execution, scoring, ranking, confidence,
weighted logic, embedding, vector, or longer-window owner was configured or
invoked by the exact node. This structural boundary is not reported as a durable
zero-count database proof.

All capabilities remain locked.

## 16. Failure classification

```text
FIRST VISIBLE FAILURE:
OperationalMemoryFactoryError: SIX_UNIT_ACCOUNTING_BLOCKED

CLASSIFICATION:
COMMITTED_CODE_DEFECT

ROOT OWNER:
public _run_operational_campaign pre-lifecycle six-unit finalization

EVIDENCE:
full traceback plus committed source history; result.lifecycle_started was false,
owner stage count was zero, and stage_evidences was (None,)

NOT CLASSIFIED:
the underlying activation terminal/cause, which the public finalization error masked

REPAIR IN THIS LANE:
none
```

This is not `TEST_OR_PROOF_HARNESS_DEFECT`: the exact test calls the real public
coordinator and the rejecting owner chain is committed production code. It is
not `ENVIRONMENT_OR_RESOURCE_FAILURE`: no resource, permission, SQLite, or
external dependency error appears in the traceback. It is not relabelled
`SHARED_FAILURE`.

## 17. Money-usefulness contribution

This proof prevents a masked pre-lifecycle terminal from being promoted to a
campaign PASS. It demonstrates that the repaired origin driver no longer emits
an empty completed accountable stage, while also proving that the next public
owner cannot yet report that returned failure without colliding with strict
six-unit evidence law. Preserving that distinction protects future
clean-memory/campaign claims from synthetic evidence and keeps financial
capabilities locked.

## 18. What the proof improves

- Executes the exact public coordinator-to-owner-to-driver composition once at
  the repaired HEAD.
- Confirms the former empty completed discovery-stage observer error did not
  recur.
- Preserves the next exact production failure with full traceback and hashes.
- Locates the committed masking boundary at pre-lifecycle six-unit finalization.
- Keeps strict evidence rejection intact rather than treating `None` as work.
- Prevents unavailable Scheduler, residue, database, or capability facts from
  being invented.

## 19. What remains locked

- exact public-composition PASS and closeout;
- any retry, rerun, comparison, resume, restart, or successor;
- fresh authorization or reuse of the consumed authorization;
- live/operational discovery, Scheduler, Source Governor, Memory Factory, or
  campaign execution;
- provider/RPC/WebSocket contact and authoritative database mutation;
- memory generation and all longer-window production work;
- retrieval and paper decisions;
- BUY, SELL, HOLD, positions, trades, paper audits, and PnL;
- wallets, private keys, signing, live execution, and real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors;
- accounting weakening or synthetic stage/transition evidence.

## 20. Authorization and preserved comparison

`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` remains consumed and permanently
non-reusable. This proof created, applied, refreshed, or reused no live
authorization.

`/private/tmp/mp-preclaim` remains registered, clean, detached, and untouched at:

`8fb4256c70d4e81660c177238253322cb37ae947`

It was not executed or used as proof evidence.

## 21. Functionality Risks / Setbacks / Efficiency Blockers

| Area | Finding |
| --- | --- |
| Functionality | A returned pre-lifecycle terminal with no sealed stage mapping is masked by `SIX_UNIT_ACCOUNTING_BLOCKED` |
| First-cause risk | The original activation terminal/cause does not reach the public terminal or failure helper |
| Accounting risk | Treating `None` or count-only source operations as sealed evidence would be dishonest; strict accounting must remain unchanged |
| Scheduler evidence | No public accountable identities or durable transitions survived this failure |
| Persistence setback | No terminal summary was written; temporary cleanup deleted the disposable database before evidence copy |
| Residue blocker | Active/locked and ownership residue cannot be verified without the deleted database |
| Network evidence limit | Transport owners were frozen/patched, but the post-call mock assertion was not reached |
| Efficiency | Another composition is forbidden; repair design must proceed from this exact traceback and static owner boundary |
| Historical boundary | This result does not retroactively explain the earlier historical `SHARED_FAILURE` |

## 22. Files changed

Only this proof report:

```text
docs/printer-v1-v2-9-8b-post-rollover-2-exact-public-composition-post-origin-driver-repair-bounded-offline-proof.md
```

No source, test, fixture, accounting, Scheduler, Source Governor, schema,
migration, authorization, runtime evidence, database, sidecar, stdout, stderr,
cache, or JSON artifact is committed.

## 23. Tests and operations not run

- no second composition;
- no retry, rerun, comparison, restart, resume, recovery, or successor;
- no broad/full pytest;
- no other test node after the composition;
- no live or operational discovery/campaign command;
- no provider, RPC, WebSocket, authoritative database, wallet, or financial
  operation;
- no database integrity/FK command because no preserved database exists.

The preflight collection-only command collected exactly one node and did not
execute it.

## 24. Next permitted lane

```text
V2-9.8B Post-Rollover-2 Public Coordinator Pre-Lifecycle Six-Unit Failure
Propagation Repair Design
```

Design/specification only. It may define how the public coordinator preserves and
returns a non-lifecycle activation terminal when no accountable stage was
started, without accepting `None` as evidence, manufacturing Scheduler/stage
identities, weakening six-unit accounting, or losing existing transport
evidence. It may not implement a repair, rerun the composition, contact sources,
mutate a database, issue/reuse authorization, or unlock later capabilities.

## 25. Final statement

The exact public composition ran once at `4cec9a2d` and failed outside
`SHARED_FAILURE` with the preserved committed-code defect
`OperationalMemoryFactoryError: SIX_UNIT_ACCOUNTING_BLOCKED`. The repaired
origin driver did not emit an empty completed discovery stage, but the public
pre-lifecycle finalizer masked the returned terminal when it received
`stage_evidences=(None,)`. No repair or rerun occurred.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_EXACT_PUBLIC_COMPOSITION_POST_ORIGIN_DRIVER_REPAIR_ROOT_CAUSE_CAPTURED`
