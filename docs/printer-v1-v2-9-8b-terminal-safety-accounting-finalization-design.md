# Printer V1 V2-9.8B Terminal Safety and Accounting Finalization Design

Date: 2026-07-30

Lane: `V2-9.8B Terminal Safety, Accounting, Runner-Proof, and Supply-Truth Finalization`

Status: `FINAL_DESIGN_FOR_IMPLEMENTATION`

## 1. Exact Attempt Scope

`operator_cli/origin_lifecycle_campaign.py` owns an immutable
`PostHandoffCompensationScope` and a private attempt recorder. The scope stores
the exact campaign/run/cycle/factory-run identity, exact origin selection batch,
the two activated token/pair IDs, immutable-link first-15m job IDs, real-runner
Scheduler job IDs, run-step IDs, lifecycle-event IDs, token-snapshot IDs,
episode-snapshot IDs, and any exact owned lease IDs.

The origin batch insert records its exact batch primary key. The real factory
records durable IDs after the transaction that creates them commits. Rolled-back
IDs may remain recorded because exact deletion of an absent primary key is
idempotent.

## 2. Compensation Transaction

The compensation owner performs one exact-scope verification/mutation
transaction:

1. validate canonical identity and reject duplicate IDs;
2. verify every present scoped row belongs to the current attempt;
3. for tables without campaign columns, require both the recorded primary key
   and one of the two activated token/pair identities;
4. delete only exact recorded deletable IDs;
5. cancel only immutable-link first-15m job IDs and exact real-runner job IDs;
6. do not update/delete immutable selected-item links;
7. do not mutate candidate-acquisition leases in the ordinary path because that
   runner creates none;
8. commit only after all checks and mutations succeed.

Any mismatch raises `POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH` and rolls back
the whole compensation transaction.

Pinned token slots and tracking rows remain owned by
`unified_terminal_closure.reconcile_campaign_terminal`.

## 3. Fail-Closed Verification

SQLite failures are translated to a structured compensation error containing
operation, table, campaign/run/cycle, SQLite exception category, and rollback
status. The original campaign terminal cause remains separate.

The residual matrix covers the scoped selection batch/items, run steps,
lifecycle events, token snapshots, episode snapshots, exact Scheduler jobs,
pinned slots, linked tracking, exact owned leases, cycle/run/campaign state, and
active job locks.

`clean_zero_active_work` requires complete verification, no cleanup error, and
zero scoped active/runnable residue. Historical/unrelated rows are counted as
preserved evidence, never residue.

## 4. Six-Unit Accounting

`aggregate_campaign_six_unit_owner` rejects `None`, an empty sequence, empty
mappings, missing elements, malformed evidence, duplicate identities, negative
counters, and campaign/run/cycle mismatch with explicit
`SIX_UNIT_STAGE_EVIDENCE_*` errors.

The operational coordinator creates the campaign owner before accounted work,
passes that same owner as a one-way evidence sink to the canonical operational
owner, ingests evidence as source stages close without converting absence to
`[]`, and derives final totals only from that owner. A later-stage exception
marks the owner incomplete while retaining already-ingested evidence. An
attempted operational campaign with missing or incomplete evidence is
`SIX_UNIT_ACCOUNTING_BLOCKED`.

A pre-operation all-zero terminal is legal only through an explicit
`PRE_OPERATION_NO_WORK` evidence block whose exact identity and no-work reason
are durable and whose no-source/no-Scheduler/no-lifecycle conditions are
verified.

## 5. Initialized-Failure Reporting

`_terminalize_initialized_failure` receives the current accounting owner or
durable evidence.

- With evidence, canonical report build/write uses
  `require_six_unit_evidence=True` and independent reconstruction.
- Without evidence after operational work began, campaign cleanup and terminal
  state still run, but no canonical completion report is written. The failure
  summary records `SIX_UNIT_ACCOUNTING_BLOCKED`,
  `report_written=false`, `REPORT_BLOCK_REASON=SIX_UNIT_EVIDENCE_MISSING`, and
  no restart/successor. Reporting failure never replaces the first cause.

## 6. Real Runner Fault Seam

`run_one_command_15m_factory` accepts a private proof-only fault seam and exact
scope recorder. The seam is rejected unless `proof_mode=True` on a disposable
database. Default `None` preserves production behavior.

Faults are raised only after real runner transactions commit:

- first real run-step and Scheduler job;
- first real token snapshot;
- first real lifecycle/window materialization reached by the ordinary runner;
- real post-activation 15m state transition.

The driver catches `PostHandoffInjectedFault`, freezes the exact recorded scope,
and invokes the same canonical compensation owner. No source retry, restart,
successor, 1h transition, or fabricated driver object is used.

## 7. Eligible-Supply Truth

`run_persistent_eligible_token_supply` derives provider failures from a
deterministic set of attributable facts. Durable failure identity is
`(source_name, request_kind, source_failure_id)`; a transport identity is used
only when no failure-row ID exists. Status labels never add a second failure.

Valid empty discovery adds zero failures. Rate-limit/stale,
malformed/partial, transport-unavailable, budget, duration, tracking-state, and
true-supply categories remain distinct. Source failure lineage remains
Source-Governed.

## 8. Proof Boundary and Locks

All proof uses frozen transports and fresh disposable migration-049 databases.
The authoritative database is read-only and its SHA-256 must remain unchanged.
Normal success remains exactly two token/pair slots and exactly two ordinary
first-15m jobs. Ordinary operation remains `WINDOW_15M`; all longer-window,
retrieval, paper, financial, wallet, paid-source, scoring, ranking, confidence,
weighting, embedding, and vector capabilities remain locked.
