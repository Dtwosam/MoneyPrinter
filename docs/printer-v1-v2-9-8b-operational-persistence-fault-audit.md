# Printer V1 V2-9.8B.15 Operational Persistence Fault Root-Cause Audit

## 1. Verdict

```text
V2_9_8B_15_PERSISTENCE_FAULT_AUDIT_PASS_ROOT_CAUSE_PROVEN
```

The failed execution reached and durably committed `PILOT_INPUT_READY`, then
entered the combined discovery/activation transaction. The transaction failed
while attempting to insert the first graduation-native provider observation
for a token already observed by an earlier campaign.

The exact rejected observation was:

```text
obs:graduation_native:7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump:47jtrzBcYZ84TAZSesjCEYySw6tUZCGEDC7xx8Zvxm4J3avd7mhEQnedDxG9RUjk6kjcgoGdJkywNVrScnFN9k5A
```

`insert_provider_observation` found that globally unique `observation_id`
already owned by execution `20260727T001520Z-d513e21260b5`. Its canonical hash
could not match because the canonical envelope includes the new discovery-batch
and discovery-work identities. It therefore raised exactly:

```text
DiscoveryPersistenceError: conflicting provider observation repeat rejected
```

`CombinedPumpfunCampaignExecutor.execute` caught that exception, rolled back the
whole combined-discovery transaction, replaced the detail with
`PERSISTENCE_FAULT`, explicitly discarded the exception object, and returned a
normal terminal result. This is a committed-code duplicate/idempotency defect,
not a provider, market-supply, SQLite-runtime, or operator fault.

## 2. Scope and authority

This lane was audit-only. It performed static code inspection and read-only
SQLite comparison only. It did not run production, call a live source, modify
the authoritative database, retry the campaign, run a test, or unlock a
capability.

Active boundary preserved:

- V2-9.8B remains bounded persistent 15m memory-growth operations only.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` production work remain locked.
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
  live execution, wallets, private keys, paid APIs, scoring, ranking,
  confidence percentages, weighted logic, embeddings, and vectors remain locked.

The Python Builder Guide blocker classification is:

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
CODE CHANGE JUSTIFIED: YES, but not in this audit-only lane
AUTHORIZATION STATUS: no production retry or new campaign authorized
```

No Python, SQLite, or platform-version behavior is implicated. The mismatch is
entirely between committed Printer identity construction and committed Printer
persistence semantics.

## 3. Starting gate

| Gate | Evidence | Result |
|---|---|---|
| Exact HEAD | `15e61375c22be996730598e8e6974056176329a9` | PASS |
| Tracked worktree | no changes | PASS |
| Untracked worktree | no files | PASS |
| Printer process | no matching Printer/MoneyPrinter operational process | PASS |
| Scheduler work | zero `PENDING`/`RUNNING` campaign work and Scheduler jobs | PASS |
| Active lease | zero `ACTIVE`/`STOPPING` supervision rows; no unreleased lease | PASS |
| SQLite integrity | `PRAGMA integrity_check` returned `ok` | PASS |
| Foreign keys | `PRAGMA foreign_key_check` returned zero rows | PASS |

## 4. Audited execution and retained evidence

| Item | Value |
|---|---|
| Execution | `20260727T124910Z-f6dc911b3efc` |
| Campaign | `20260727T124910Z-f6dc911b3efc-campaign` |
| Run | `20260727T124910Z-f6dc911b3efc-campaign-run` |
| Cycle | `20260727T124910Z-f6dc911b3efc-cycle` |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Pre-campaign backup | `printer_v1.pre-campaign.backup.sqlite3` |
| Backup SHA-256 | `97b168223a7234886739798511ae380487b810380b89f1e815b71ddc17a1296c` |
| Restore-rehearsal SHA-256 | same as backup |
| Final DB SHA-256 at audit | `0d662350feb4fb5f1e1cd4cb9d33fa045b1e70ad474feb824221edb54c222d86` |
| Governed source calls | 15 |
| Scheduler calls | 0 |
| Lifecycle started | false |
| Stored terminal cause | `PERSISTENCE_FAULT` |
| Stored run status | `NOT_STARTED` |
| Restart/successor | false / false |

The terminal report reconciles zero active campaign work, zero active Scheduler
jobs, zero pending/running factory steps, no factory run, and a released lease.

## 5. Database before/after comparison

All comparisons used the retained backup attached read-only to a read-only
connection to the authoritative database.

### 5.1 Attributable committed additions

| Table or group | Backup | After | Delta | Meaning |
|---|---:|---:|---:|---|
| campaigns/configurations/runs/cycles/supervision/reports | 6 each | 7 each | +1 each | complete terminal campaign graph |
| `printer_source_requests` | 1165 | 1180 | +15 | governed campaign source ledger |
| `printer_source_responses` | 1112 | 1124 | +12 | successful source responses |
| `printer_source_failures` | 53 | 56 | +3 | two PumpPortal timeouts and one Solana RPC 429 |
| graduated registry | 10 | 12 | +2 | two newly confirmed graduated candidates |
| market-floor state | 10 | 12 | +2 | one proven and one below-floor market result |
| holder campaign ledgers | 4 | 5 | +1 | 15 governed / 16 transport operations |
| holder evidence attempts | 4 | 8 | +4 | two GoPlus, one RPC failure, one Helius backup attempt |
| readiness bundles | 1 | 2 | +1 | immutable execution-scoped `PILOT_INPUT_READY` |

The readiness bundle selected, in order:

1. `7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump`
2. `aQVkmuasVQoZoHurni4S3SvZS6MHc8LdyLhUV8spump`

Its durable ledger records 15 governed requests, 16 underlying transport
operations, and 9 zero-transport operations. The bundle owner commits the row
inside `build_pilot_input_ready_bundle`, making this the last successful
pre-activation persistence boundary.

### 5.2 Expected downstream rows that are absent

| Table/group | Backup | After | Delta |
|---|---:|---:|---:|
| discovery batches | 1 | 1 | 0 |
| provider observations | 2 | 2 | 0 |
| merged candidates | 2 | 2 | 0 |
| origin verifications | 2 | 2 | 0 |
| PumpSwap confirmations | 2 | 2 | 0 |
| validation runs/items | 0 / 0 | 0 / 0 | 0 / 0 |
| selection batches/items | 2 / 4 | 2 / 4 | 0 / 0 |
| campaign token slots | 2 | 2 | 0 |
| tracking queue | 17 | 17 | 0 |
| campaign windows/work | 0 / 0 | 0 / 0 | 0 / 0 |
| Scheduler jobs | 999 | 999 | 0 |
| episodes/windows/fingerprints | 53 / 156 / 23 | unchanged | 0 |

The existing discovery, selection, slot, and Scheduler rows belong to earlier
campaigns; none is attributable to this execution.

### 5.3 Locked-capability comparison

| Table | Backup | After | Delta |
|---|---:|---:|---:|
| retrieval queries | 10 | 10 | 0 |
| retrieval matches | 0 | 0 | 0 |
| paper decisions | 2 | 2 | 0 |
| paper positions | 0 | 0 | 0 |
| paper trade events | 0 | 0 | 0 |
| paper trade audits | 0 | 0 | 0 |
| paper audit reports | 1 | 1 | 0 |

The nonzero retrieval/decision/audit rows are preserved historical baseline
evidence, not execution-attributable activation.

## 6. Exact failure boundary

The successful call path was:

```text
operational command
-> governed graduated-supply discovery
-> graduated-registry updates
-> exact-pool market-floor persistence
-> holder validation and holder-ledger persistence
-> build_pilot_input_ready_bundle (commit succeeds)
-> OriginToLifecycleCampaignDriver.run
-> CombinedPumpfunCampaignExecutor.execute
-> combined discovery transaction begins
-> discovery batch/work/source rows are staged
-> first graduation-native provider observation is attempted
-> conflicting provider observation repeat rejected
-> whole combined discovery transaction rolled back
-> PERSISTENCE_FAULT returned
-> no activation, selection handoff, tracking, Scheduler, or lifecycle start
-> terminal reconciliation/report/lease release commit
```

### Last successfully persisted operation

The last campaign-progress commit before the failing transaction was the
immutable `PILOT_INPUT_READY` row:

```text
20260727T124910Z-f6dc911b3efc-campaign-run:
20260727T124910Z-f6dc911b3efc-cycle:pilot-input
```

Terminal reconciliation, report creation, and lease release were later
successfully committed as cleanup, not campaign progress.

### First missing persistence

The first expected durable row after readiness is the execution-owned
`printer_discovery_batches` row. It and the initially staged discovery
work/source rows were rolled back with the transaction. The write that actually
triggered rollback was the first insert into
`printer_discovery_provider_observations`.

## 7. Root-cause proof

### 7.1 Existing identity

The pre-campaign database already contained the exact first-candidate
observation identity from execution `20260727T001520Z-d513e21260b5`:

```text
mint:       7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump
signature:  47jtrzBcYZ84TAZSesjCEYySw6tUZCGEDC7xx8Zvxm4J3avd7mhEQnedDxG9RUjk6kjcgoGdJkywNVrScnFN9k5A
row hash:   b325ec27e98e01e30ff72d7f7b21065972367b1515f406850428587fca024d03
```

The graduated registry retained the same mint/signature pair. The failed
execution's readiness bundle proves that this mint was `chosen[0]` and therefore
the first item copied into `fixtures.direct_observations` for combined discovery.

### 7.2 Conflicting committed contracts

`CombinedPumpfunCampaignExecutor._run_direct_lane` constructs a global ID from
only the mint and migration signature:

```text
obs:graduation_native:<mint>:<migration_signature>
```

`observation_canonical_payload`, however, includes
`discovery_batch_id`, `discovery_work_id`, source-row identities, and timestamps.
Those fields differ in a later campaign, so a later campaign cannot reproduce
the earlier canonical hash even when it lawfully observes the same immutable
graduation fact.

`insert_provider_observation` first looks up by the global `observation_id`. On
finding the old row, it accepts only an identical canonical hash. Because the
new campaign owns a different batch and work identity, the comparison must fail
and the function raises `conflicting provider observation repeat rejected`.

This proof does not depend on guessing a provider payload or replaying a write.
The retained row, readiness order, registry signature, ID constructor, canonical
payload fields, and persistence branch uniquely determine the exception.

### 7.3 Fault classifier and lost detail

The fault was classified by this transaction boundary:

```text
CombinedPumpfunCampaignExecutor.execute
except DiscoveryPersistenceError as exc:
    connection.rollback()
    terminal = "FAILED"
    cause = "PERSISTENCE_FAULT"
    cancellation = "SHARED_FAILURE"
    ...
    del exc
```

Therefore the underlying exception was caught, reduced to a generic category,
and explicitly discarded. It was not logged to the terminal result, campaign
report, summary, stdout, or stderr.

## 8. Required findings

1. **Exact stage:** post-readiness combined discovery, during persistence of the
   first graduation-native provider observation, before merge, validation,
   selection, activation, tracking handoff, or lifecycle.
2. **Classifier:** `CombinedPumpfunCampaignExecutor.execute` and its
   `except DiscoveryPersistenceError` transaction handler.
3. **Attempted write:** `INSERT` into
   `printer_discovery_provider_observations` through
   `insert_provider_observation`.
4. **Exception handling:** swallowed at the owner boundary, reduced to
   `PERSISTENCE_FAULT`, then explicitly discarded with `del exc`.
5. **Exact reconstruction:** yes —
   `DiscoveryPersistenceError: conflicting provider observation repeat rejected`.
6. **Partial rows:** yes at the campaign level (source, registry, floor, holder,
   readiness, and terminal graph); no partial combined-discovery row set survived.
7. **Safety:** terminally consistent and capability-safe. Integrity/FKs pass,
   lease and active work are clear, no Scheduler/lifecycle work survived, and
   locked tables did not change. The readiness row is immutable, execution-scoped,
   expired before terminal close, and must remain audit evidence only.
8. **Defect class:** primary `duplicate/idempotency`; secondary
   `observability-only`. It is not schema/constraint, connection/transaction,
   serialization/value-shape, or state-transition as the initiating cause.
9. **Empty logs:** the operational command only creates the two artifact files
   with `touch`. `Start-PrinterV1-MemoryFactory.ps1` invokes Python in the
   foreground and does not redirect process output into those paths. In this
   case the persistence owner also returned a normal terminal result, so the
   CLI exception handler did not emit stderr. The final JSON went to the parent
   console stdout, not the touched artifact file.
10. **Minimum safe repair:** batch-scope the IDs of every batch-owned immutable
    discovery object whose canonical content includes batch identity, and retain
    structured safe exception diagnostics at the transaction/terminal boundary.

## 9. Partial-state safety

The retained partial state is safe to preserve and must not be manually deleted:

- all attributable source calls are governed and durably ledgered;
- the two registry additions and two market-floor rows are backed by retained
  governed source provenance;
- holder failures and backup use are explicit;
- the readiness row is scoped to the terminal run and is not a tracking handoff;
- the failed combined-discovery transaction left none of its batch, work,
  observation, merge, selection, slot, queue, or Scheduler rows;
- terminal cleanup released the lease and reconciled active work to zero;
- no retrieval or financial table changed.

The terminal graph's `TERMINAL_COMPLETED`/`COMPLETED` status paired with
`PERSISTENCE_FAULT` is constraint-valid under the unified terminal-closure
policy, but it is operationally easy to misread. Reports must continue to use
the first terminal cause and `lifecycle_started=false`, not the word
`COMPLETED`, when deciding whether useful campaign work occurred.

## 10. Minimum justified next lane

The minimum roadmap-compliant next lane is a narrow, non-production repair lane,
proposed as:

```text
V2-9.8B.16 — Batch-Scoped Discovery Persistence Idempotency and Fault Observability Repair
```

Required scope:

1. Correct the canonical combined-discovery owner so repeated lawful observation
   of the same mint/signature in a later batch receives a deterministic
   batch-scoped immutable identity.
2. Audit and correct the immediately cascading global IDs before implementation:
   `merged_candidate_id`, origin-verification ID, and PumpSwap-confirmation ID
   currently inherit the same cross-batch collision risk.
3. Preserve within-batch idempotency and conflict rejection; do not weaken
   provenance, immutable-row, FK, Source Governor, or Scheduler controls.
4. Preserve a safe structured exception type/message in the execution result and
   terminal artifacts. Either wire artifact stdout/stderr intentionally or stop
   presenting touch-only files as captured process logs.
5. Prove on disposable SQLite databases that two sequential campaigns may
   observe the same immutable graduated fact without collision, while a true
   same-batch conflicting repeat still fails closed and leaves no partial handoff.
6. Verify zero retrieval/financial deltas and no production operation.

No production retry is justified until that repair follows the required
design/implementation/bounded-proof/closeout pattern and separately reaches an
operator-reviewed production-readiness gate.

## 11. Money-usefulness contribution

This audit prevents Printer from treating repeated observation of a useful
graduated token as a generic persistence failure. Correct batch ownership is
necessary for a persistent memory machine: lawful recurrence must remain
auditable across campaigns, while true conflicting evidence must still fail
closed. Preserving exact fault detail also prevents wasted source budget and
misdiagnosed market outcomes without creating fake memory, forced trades, or
financial claims.

## 12. What remains locked

This audit does not authorize:

- another production campaign or retry;
- deletion, rewriting, or manual reuse of the readiness row;
- tracking handoff, Scheduler runtime expansion, or lifecycle activation;
- clean-memory promotion from this failed execution;
- 1h/4h/12h/24h production operation;
- retrieval or paper decisions;
- BUY, SELL, HOLD, positions, trades, audits, or PnL;
- live execution, wallets, private keys, signing, or real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, or vectors.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Effect | Required control |
|---|---|---|
| Cross-batch global IDs | any previously observed candidate can terminate a later campaign | batch-scope all batch-owned immutable identities |
| Cascading collision after first fix | fixing only observation ID would expose merged/origin/PumpSwap global-ID collisions | repair and prove the whole direct persistence chain |
| Discarded exception detail | terminal report cannot distinguish duplicate conflict from other persistence faults | retain safe structured diagnostics |
| Touch-only stdout/stderr | artifact inventory suggests logs exist when no capture is wired | wire capture or label files honestly |
| Durable readiness after failed activation | stale readiness can be misunderstood as lifecycle success | keep execution-scoped, terminal-linked, audit-only semantics |
| `COMPLETED` plus fault cause | operator may read cleanup completion as campaign success | first terminal cause and lifecycle-start state remain authoritative |
| Source budget consumed before collision | repeated campaigns can spend governed calls before deterministic failure | preflight regression proof on persistent-history fixtures before live authorization |
| No production replay authorized | repair cannot be proven by rerunning this campaign now | disposable DB proof first; later operator gate required |

## 14. Checks performed

- exact HEAD and clean worktree checks;
- read-only process, lease, active-work, and Scheduler checks;
- read-only SQLite integrity and FK checks;
- read-only attached-database before/after queries;
- execution-scoped campaign/source/registry/floor/holder/readiness/terminal tracing;
- locked-capability delta checks;
- static inspection of the operational command, graduated-supply owner,
  readiness owner, origin-to-lifecycle driver, combined discovery executor,
  discovery persistence owner, terminal classifier, and PowerShell launcher;
- no tests, production commands, source calls, or database writes.
