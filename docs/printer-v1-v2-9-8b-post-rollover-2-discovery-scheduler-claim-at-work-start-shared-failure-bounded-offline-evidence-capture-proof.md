# Printer V1 V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Bounded Offline Evidence-Capture Proof

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start SHARED_FAILURE Bounded Offline Evidence-Capture Proof`

Lane type: one exact public-composition execution, evidence inspection, classification, and documentation only.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_SHARED_FAILURE_BOUNDED_OFFLINE_EVIDENCE_CAPTURE_PROOF_BLOCKED`

The single authorized exact public composition failed without returning a
`SHARED_FAILURE` terminal. Its ordinary first visible failure was:

```text
printer_v1.sources.campaign_six_unit_accounting.CampaignSixUnitError:
SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE
```

The failure occurred while sealing the public composition's
`DISCOVERY_SELECTION_SCHEDULER` stage at the
`DISCOVERY_SELECTION_TERMINAL` callback. The callback received zero Scheduler
work identities and zero local-validation identities, so the committed
accounting owner correctly rejected an empty started-stage evidence block.

The exception escaped before `_run_operational_campaign` returned a terminal
mapping. The failure-only SHARED_FAILURE evidence helper therefore was not
invoked. No structured JSON artifact or preserved disposable database was
created. The discovery exception, transaction-local claim/work state, rollback
result, database hash, integrity result, and foreign-key result consequently
remain unavailable.

This is Outcome C: the composition failed without a public `SHARED_FAILURE`.
It is not forced or relabeled as `SHARED_FAILURE`.

Primary lane classification:

`PRE_EXISTING_UNRELATED_FAILURE`

Python Builder classification of the visible failure owner:

`COMMITTED_CODE_DEFECT`

The primary lane classification is `PRE_EXISTING_UNRELATED_FAILURE` because the
visible failure is owned by pre-existing public origin-driver/accounting-stage
wiring outside the evidence-capture implementation. The underlying discovery
failure remains `INSUFFICIENT_EVIDENCE` and is not repaired or guessed in this
lane.

## 2. Baseline and execution identity

| Item | Exact value |
| --- | --- |
| Required baseline HEAD | `f32336b44f3c890f6a6d51e1cc9b54db3997da59` |
| Baseline commit | `Add discovery SHARED_FAILURE evidence capture` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Initial tracked tree | Clean |
| Initial upstream state | 4 ahead / 0 behind |
| Proof artifact scope identity | `20260803T152139Z-f32336b` |
| Public execution identity | `20260803T152202Z-908dd3b115b9` |
| Campaign identity | `20260803T152202Z-908dd3b115b9-campaign` |
| Campaign run identity | `20260803T152202Z-908dd3b115b9-campaign-run` |
| Cycle identity | `20260803T152202Z-908dd3b115b9-cycle` |
| Test result | 1 failed in 3.59 seconds; process exit 1 |
| Automatic campaign retries | 0 |
| Composition reruns | 0 |
| Comparison executions | 0 |
| Automatic successor/restart | None created; execution aborted before terminal return |

The public execution identity and campaign/run/cycle identities are preserved in
the full traceback's exact stage ID. No authorization identity was created,
applied, or reused by this disposable offline test.

## 3. Repository and worktree preflight

Preflight completed before the one composition:

| Check | Result |
| --- | --- |
| Exact HEAD | PASS — `f32336b44f3c890f6a6d51e1cc9b54db3997da59` |
| Exact branch | PASS |
| Tracked tree | PASS — no staged or unstaged tracked changes |
| Ahead/behind | PASS — 4 ahead / 0 behind |
| Relevant process scan | PASS — no Printer/Memory Factory process active |
| Evidence helper import | PASS |
| Evidence helper compile | PASS |
| Migration head | PASS — `050_campaign_scheduler_ownership_scope.sql` |
| Exact node collection | PASS — exactly one test node collected |
| External transport boundary | PASS — frozen Pump, secondary, snapshot, and context adapters; resolved RPC URL patched to unused; ordinary urllib patched |

Registered worktrees at preflight:

| Worktree | State |
| --- | --- |
| `/Users/Dtwo1/Developer/MoneyPrinter` | branch at exact required HEAD |
| `/private/tmp/mp-preclaim` | detached `8fb4256c70d4e81660c177238253322cb37ae947` |

The comparison worktree was not read as proof evidence, modified, executed, or
removed.

Preserved pre-existing untracked repository artifacts:

- `.DS_Store`
- `operator-runs/v2-9-8b-authoritative-mig050/`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/`

## 4. Exact authorized command

The test invocation was exactly:

```text
.venv/bin/python -m pytest -q tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition
```

`PRINTER_V1_OFFLINE_FAILURE_EVIDENCE_ROOT` was bound to the external untracked
proof directory, `PYTHONDONTWRITEBYTECODE=1` prevented cache creation, and shell
redirection captured stdout and stderr separately. Those capture bindings did
not change the test node or invoke a wrapper, retry, comparison, provider, RPC,
WebSocket, wallet, or operational command.

## 5. Exact composition outcome

The public chain reached:

```text
public _run_operational_campaign
-> AuthoritativeLiveOperationalCampaignOwner.run_operational
-> OriginToLifecycleCampaignDriver.run
-> DISCOVERY_SELECTION_TERMINAL callback
-> public _observe_full_run_stage
-> seal_campaign_stage_evidence
```

The seal received:

```text
stage_kind = DISCOVERY_SELECTION_SCHEDULER
stage_sequence = 1
stage_terminal_status = COMPLETED
scheduler_work_identities = []
local_validation_identities = []
transport_operations = []
lifecycle_reservations = 0
```

The accounting owner then raised:

```text
CampaignSixUnitError:
SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE
```

This was an ordinary uncaught composition failure, not a returned
`SHARED_FAILURE` terminal. The test stopped at the public call site before its
post-terminal assertions, evidence print, two-window checks, report-only replay,
and success evidence construction.

## 6. Evidence artifact paths

Execution-scoped artifact directory:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/post-rollover-2-shared-failure-bounded-offline-proof/20260803T152139Z-f32336b
```

Preserved files:

| Artifact | Path | Size | SHA-256 |
| --- | --- | ---: | --- |
| Full stdout / traceback | `/Users/Dtwo1/PrinterOperations/v2-9-8/post-rollover-2-shared-failure-bounded-offline-proof/20260803T152139Z-f32336b/stdout.txt` | 13,006 bytes | `80253eca2fa40d4ce4b44ba91d6274769a34659d40627e665281e528fa30d1c5` |
| Full stderr | `/Users/Dtwo1/PrinterOperations/v2-9-8/post-rollover-2-shared-failure-bounded-offline-proof/20260803T152139Z-f32336b/stderr.txt` | 0 bytes | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The configured failure-helper root exists but is empty:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/post-rollover-2-shared-failure-bounded-offline-proof/20260803T152139Z-f32336b/shared-failure
```

No `shared-failure-evidence.json`, copied database, SQLite sidecar, success
evidence JSON, or report artifact was created.

## 7. Disposable database, Migration 050, integrity, and FK status

The test's `setUp` created a fresh temporary database named:

```text
<pytest TemporaryDirectory>/dtw23-migration-050.sqlite3
```

The exact temporary root was not printed or retained. The test reached the
public composition after `apply_migrations`, and preflight independently
confirmed the canonical migration head as
`050_campaign_scheduler_ownership_scope.sql`.

Post-failure evidence status:

| Evidence | Result |
| --- | --- |
| Exact disposable source DB path | Unavailable after temporary cleanup |
| Closed evidence copy path | Not created |
| Applicable SQLite sidecars | Not preserved / unavailable |
| Database SHA-256 | Unavailable |
| Migration-050 verification on preserved copy | Not runnable; no copy |
| `PRAGMA integrity_check` | Not runnable through approved helper; no copy |
| `PRAGMA foreign_key_check` | Not runnable through approved helper; no copy |

No surviving accessible `dtw23-migration-050.sqlite3` was found after pytest
cleanup. The preserved database cannot be restored because no copy exists; no
authoritative database was touched.

## 8. Exception, stage, and first-failure interpretation

| Field | Captured value |
| --- | --- |
| Exception class | `printer_v1.sources.campaign_six_unit_accounting.CampaignSixUnitError` |
| Sanitized message | `SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE` |
| Public stage | `DISCOVERY_SELECTION_SCHEDULER` |
| Callback boundary | `DISCOVERY_SELECTION_TERMINAL` |
| Stage sequence | 1 |
| Stage terminal label supplied by caller | `COMPLETED` |
| Scheduler identities supplied | 0 |
| Local validation identities supplied | 0 |
| Public terminal returned | No |
| SHARED_FAILURE artifact created | No |

The accounting seal is fail-closed and is not reclassified as the defect. It
correctly rejects a started stage whose reconstructed six-unit totals are all
zero. The visible defect boundary is earlier: the origin driver calls the
started-stage observer with an empty projection before it checks the failed or
zero-slot activation result and returns that result to the public coordinator.

Static history confirms this boundary predates the evidence-capture lane:

- the affected origin-driver observer block is attributed to commit `02f87289`;
- the empty-started-stage accounting rejection is attributed to commit
  `b168c57d`;
- the affected origin driver, accounting owner, and public coordinator have no
  diff from the evidence-capture implementation baseline
  `f765b6d1201e64bd2d1d6b6514128b6b7351626d` to current HEAD.

This establishes `PRE_EXISTING_UNRELATED_FAILURE` relative to the current
instrumentation lane. Under the Python Builder taxonomy, the visible path is a
`COMMITTED_CODE_DEFECT`, not an environment failure or proof-fixture-only
failure, because the exact production public coordinator supplies this observer
on the real composition path.

The underlying discovery exception is not established. No repair is justified
for that unknown cause.

## 9. Enqueue, claim, work-insertion, and transaction state

The visible post-activation read used a separate connection and produced no
projected discovery Scheduler identities, no handoff Scheduler identities, and
no activated slots for this campaign/cycle at the observer boundary.

That is durable post-activation visibility only. It does **not** establish what
was visible inside the discovery transaction before its terminal handling.

| Required evidence | Result |
| --- | --- |
| Discovery batch identity/row | Not preserved |
| Discovery work identity/row | Not preserved |
| Linked Scheduler job identity/row | Not preserved |
| Enqueue completed | Unknown |
| Claim returned / result / status | Unknown |
| Expected and observed lock owner | Unknown |
| `locked_at` / `started_at` | Unknown |
| Work insertion completed | Unknown |
| Allowlisted transaction-local rows | Not captured |
| `connection.in_transaction` | Not captured |
| Expected rollback effects | Not captured |
| Rollback started/completed | Not captured |
| Secondary rollback/artifact failure | No helper artifact; exact secondary discovery diagnostics unavailable |

No transaction-local row is called durable. The empty later projection cannot
be used to reconstruct whether enqueue, claim, or work insertion occurred before
rollback.

## 10. Window, Scheduler, campaign, and residue results

The composition stopped before lifecycle execution and final acceptance evidence
could be produced.

| Required proof | Result |
| --- | --- |
| Two completed `WINDOW_15M` closes | Not reached / not proved |
| Two window identities | Not available |
| Discovery Scheduler transition table | Not available; zero identities reached the stage seal |
| Lifecycle Scheduler transition coverage | Not reached |
| `scheduler_transition_coverage.complete` | Not reached |
| Final campaign acceptance | Not reached; no `CAMPAIGN_PASS` |
| Active/locked Scheduler residue | Not inspectable after temporary cleanup |
| Discovery/lifecycle/factory/lease/campaign/proof residue | Not inspectable after temporary cleanup |
| Protected capability counts | Not reached / not inspectable |
| Report-only replay | Not reached |

No retry, rerun, comparison, resume, fresh authorization, automatic restart, or
successor was performed. `AUTOMATIC_RETRIES` remained committed at zero.

## 11. Zero-network boundary

The one composition used only:

- frozen Pump origin/graduation transports;
- a fake secondary transport;
- fixture DexScreener, CoinGecko, GoPlus, and Jupiter adapters;
- an unused patched Solana RPC configuration;
- `migration_transport=None` inside the exact proof owner;
- patched `urllib.request.urlopen` for the entire public call.

Therefore no real provider, RPC, WebSocket, wallet, or external source transport
was available to this proof path. Because the exception escaped before the
test's `network_open.assert_not_called()` and before structured evidence
serialization, the patched urllib call count was not durably captured. This is
a frozen/blocked transport boundary, not packet-level or host-wide monitoring,
and it does not claim an unavailable attempted-call count.

No external authorization, wallet, paid API, signing, or financial path was
configured or invoked.

## 12. Source-grounded blocker classification

```text
BLOCKER CLASSIFICATION:
Primary lane classification: PRE_EXISTING_UNRELATED_FAILURE
Python Builder mapping: COMMITTED_CODE_DEFECT

EVIDENCE:
The full traceback shows the exact public owner chain and an empty identity-bearing
DISCOVERY_SELECTION_SCHEDULER stage. Static diff/blame establishes that both the
observer ordering and the strict accounting rejection predate this evidence-capture lane.

OFFICIAL-SOURCE COMPARISON:
No version-sensitive Python or SQLite behavior caused the visible failure. The
exception propagated normally and pytest preserved it in stdout.

PRINTER-CONTRACT COMPARISON:
The accounting owner correctly forbids empty started-stage evidence. The origin
driver must not advertise a completed started stage with zero accountable identities
before propagating a failed/zero-slot activation.

ROOT CAUSE:
Visible failure: pre-existing origin-driver activation/observer ordering lets an
empty DISCOVERY_SELECTION_TERMINAL stage reach the strict public accounting seal.
Underlying discovery failure: NOT ESTABLISHED.

CODE CHANGE JUSTIFIED:
NO in this proof/documentation lane.

MINIMUM SAFE RESPONSE:
Preserve the ordinary failure, report BLOCKED, and audit the confirmed origin-driver
failed-activation propagation owner before any design or repair.

FOCUSED PROOF:
No rerun. A future separately approved lane must first close the observer/terminal
propagation design and retain the discovery terminal/fault details.

UNTOUCHED SCOPE:
Production source, tests, fixtures, Scheduler/accounting law, Source Governor,
migrations, databases, authorization, financial surfaces, and comparison worktree.

AUTHORIZATION STATUS:
V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z remains consumed and permanently non-reusable.

NEXT ROADMAP-COMPLIANT STEP:
Narrow read-only audit of the confirmed pre-existing origin-driver owner.
```

## 13. Money-usefulness contribution

This blocked result prevents an empty accounting stage, an uncaptured discovery
failure, or a deleted temporary database from being promoted to product proof.
It preserves the distinction between transaction-local work, durable evidence,
and missing evidence, which protects later clean-memory and campaign-acceptance
claims from reconstructed or synthetic Scheduler truth.

## 14. What the proof improves

- Preserves the exact ordinary first visible exception and full traceback.
- Confirms that the public composition can still bypass the failure-only helper
  when a later stage observer raises before terminal propagation.
- Identifies the exact pre-existing origin-driver/accounting boundary that
  masked the discovery terminal at the public surface.
- Confirms that the strict accounting owner rejected empty started-stage
  evidence rather than manufacturing work identities.
- Prevents the current run from being misreported as `SHARED_FAILURE`, a
  Scheduler claim proof, or campaign PASS.

## 15. What remains locked

- the underlying discovery failure classification;
- the SHARED_FAILURE evidence-capture proof and product proof PASS;
- repair of the confirmed visible origin-driver boundary in this lane;
- exact public-composition retry/rerun or comparison execution;
- fresh authorization or reuse of the consumed authorization;
- live/operational discovery, Scheduler, or Memory Factory execution;
- authoritative database mutation;
- memory generation and longer windows;
- retrieval and decisions;
- BUY/SELL/HOLD, positions, trades, audits, and PnL;
- wallets, private keys, signing, execution, and real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, and vectors.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Area | Finding |
| --- | --- |
| Functionality risk | Failed/zero-slot activation can reach a completed started-stage observer before the driver returns the activation failure |
| Evidence setback | The later observer exception prevented the returned discovery terminal and `fault_details` from reaching the helper |
| Persistence setback | Temporary cleanup removed the disposable database before approved helper preservation |
| Transaction truth risk | Enqueue/claim/work rows may have existed only inside the discovery transaction; none were captured |
| Classification boundary | The visible pre-existing failure is confirmed, but the underlying discovery cause remains unknown |
| Network evidence limit | Real transports were frozen/patched, but the post-call mock assertion and call-count artifact were not reached |
| Residue blocker | No surviving database exists for read-only residue, integrity, or FK checks |
| Efficiency blocker | Another composition cannot safely add evidence until the public failed-activation propagation boundary is audited/designed |
| Repair risk | Changing strict accounting to accept an empty started stage would suppress honest evidence failure and is prohibited |

## 17. Smallest safe next lane

```text
V2-9.8B Post-Rollover-2 Origin Driver Empty Discovery Stage Evidence and
Activation-Failure Propagation Audit
```

This is the required narrow audit of the confirmed owner for a
`PRE_EXISTING_UNRELATED_FAILURE`. It is read-only and must determine how a
failed/zero-slot activation should propagate its existing terminal and
`fault_details` without emitting an empty completed stage and without weakening
accounting.

It may not repair code, rerun the composition, contact providers, mutate any
database, use the comparison worktree, issue/reuse authorization, add retries,
inject Scheduler transitions, or unlock financial capabilities. Only after an
approved audit and design may a narrow implementation/proof lane be considered.

## 18. Final statement

The one authorized public composition ran exactly once at the required baseline
and failed outside the returned SHARED_FAILURE path on strict empty-stage
accounting. Stdout and stderr are preserved, but the failure helper did not run,
the disposable database was cleaned, and claim/transaction/rollback/integrity/FK
evidence is unavailable. The visible pre-existing origin-driver boundary is
classified, while the underlying discovery failure remains unexplained.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_SHARED_FAILURE_BOUNDED_OFFLINE_EVIDENCE_CAPTURE_PROOF_BLOCKED`
