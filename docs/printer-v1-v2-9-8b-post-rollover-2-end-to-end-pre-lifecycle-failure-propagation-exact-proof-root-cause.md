# Printer V1 V2-9.8B Post-Rollover-2 End-to-End Pre-Lifecycle Failure Propagation Exact Proof Root Cause

Date: 2026-08-03

## Verdict

`V2_9_8B_POST_ROLLOVER_2_END_TO_END_PRE_LIFECYCLE_FAILURE_PROPAGATION_EXACT_PROOF_ROOT_CAUSE_CAPTURED`

The one authorized exact public composition failed. It was not rerun and no
post-composition repair was made. The repaired public boundary did not mask the
operational failure: it returned an exact pre-lifecycle failure terminal, invoked
the failure-evidence helper before temporary cleanup, and preserved a closed copy
of the disposable Migration-050 database.

## Baseline and composition identity

- Requested baseline: `2e11f1304c3ba7151ef21f27e0db4fec88890ec1`
  (`Record post-origin-driver exact composition proof`).
- Repair commit under proof:
  `1a95458b20a222c02f9f056bd996f387356f61a8`
  (`Repair end-to-end pre-lifecycle failure propagation`).
- Branch:
  `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`.
- Exact node:
  `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition`.
- Execution identity: `20260803T192641Z-69f5e15b7c75`.
- Public campaign identity: `20260803T192641Z-69f5e15b7c75-campaign`.
- Public campaign-run identity:
  `20260803T192641Z-69f5e15b7c75-campaign-run`.
- Exact invocation count: one.
- Result: `1 failed in 3.45s`.

## First failure and precedence

The immutable first operational failure is:

```json
{
  "classification": "SHARED_FAILURE",
  "exception_class": "SecondaryDiscoveryError",
  "sanitized_message": "MALFORMED_RESPONSE: missing pool object"
}
```

The authoritative returned terminal preserved:

| Field | Value |
| --- | --- |
| `status` | `OPERATIONAL_CAMPAIGN_PRE_LIFECYCLE_TERMINAL` |
| `run_status` | `NOT_STARTED` |
| `activation_terminal_status` | `FAILED` |
| `first_terminal_cause` | `SHARED_FAILURE` |
| `cancellation_reason` | `SHARED_FAILURE` |
| `lifecycle_started` | `false` |
| `accountable_stage_started` | `true` |
| `accounting_required` | `true` |
| `accounting_status` | `SIX_UNIT_ACCOUNTING_BLOCKED` |

The test's final assertion expected the success-path wrapper status
`OPERATIONAL_CAMPAIGN_TERMINAL`; it instead received the new truthful
pre-lifecycle terminal. This assertion failure is not the first operational
cause. The frozen secondary discovery response had already produced the
`SHARED_FAILURE` above.

Strict accounting also correctly failed closed because accountable work had
been claimed but rollback left no durable stage evidence to account. That is a
post-failure accounting/projection blocker and does not replace the earlier
`SHARED_FAILURE`. No secondary helper failure was recorded.

## Scheduler transition evidence

The pre-rollback evidence contains the real, transaction-local transitions:

| Order | Scheduler transition | Job state | Lock owner |
| ---: | --- | --- | --- |
| 1 | `SCHEDULER_ENQUEUE` | pending work inserted | none before claim |
| 2 | `SCHEDULER_CLAIM` | `RUNNING` | exact discovery-work owner below |
| 3 | no durable terminal transition | attempt rolled back | no residue |

- Scheduler job ID: `2`.
- Work type: `DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`.
- Discovery work ID:
  `work:DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE:discovery-batch:20260803T192641Z-69f5e15b7c75-campaign:20260803T192641Z-69f5e15b7c75-campaign-run:20260803T192641Z-69f5e15b7c75-cycle`.
- Expected and observed lock owner:
  `discovery-work:work:DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE:discovery-batch:20260803T192641Z-69f5e15b7c75-campaign:20260803T192641Z-69f5e15b7c75-campaign-run:20260803T192641Z-69f5e15b7c75-cycle`.
- Claim result: `ACQUIRED`.
- Rollback: started and completed.
- Durable active Scheduler residue after rollback: zero.
- Retry count: zero.

The evidence labels the job, discovery batch, and discovery work as visible in
the active transaction and records that rows created in this attempt were not
proven durable. No synthetic Scheduler identity or transition was created.

## Windows and campaign acceptance

No lifecycle started. Therefore:

- token-slot identities: none;
- `WINDOW_15M` identities: none;
- completed `WINDOW_15M` closes: zero;
- campaign acceptance: not reached;
- `CAMPAIGN_PASS`: not emitted.

The preserved database records the campaign and campaign run as
`TERMINAL_FAILED` with first cause `SHARED_FAILURE`. Token slots, campaign
windows, and memory windows are all zero.

## Preserved evidence and database verification

Artifact directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260803-post-rollover-2-exact-public-composition/20260803T192641Z-69f5e15b7c75`

| Artifact | SHA-256 |
| --- | --- |
| `shared-failure-evidence.json` | `bbe75a2aaaaffdca547088dcd3cf8a3fceaa3979471c321385c1178246906b55` |
| `shared-failure-disposable-migration-050.sqlite3` | `fe2ba601b62161c9b3b61d2654eb9662e37c5221d86b5efcd1362b2065ad97b2` |

Database verification:

- copy method: SQLite backup API after owner connections closed;
- journal mode: `delete`;
- Migration count: 50;
- migration head: `050_campaign_scheduler_ownership_scope.sql`;
- Migration-050 applied: yes;
- `PRAGMA integrity_check`: `ok`;
- `PRAGMA foreign_key_check`: empty;
- source and destination sidecars: none;
- evidence-only disposable database: yes;
- authoritative database: not used.

## Zero-network, authorization, retry, and cleanup boundary

- Discovery and lifecycle transports were frozen/fake.
- `urllib.request.urlopen` was patched and called zero times.
- This is an application-boundary zero-network assertion, not packet-level
  capture.
- No live provider, RPC, or WebSocket was used.
- No live authorization was created or reused.
- No wallet, key, signing, or funds were used.
- Automatic retries, reruns, resumes, restarts, and successors: all zero.
- The helper ran before the disposable temporary directory was cleaned.
- The external preserved database and structured JSON survived cleanup.
- `/private/tmp/mp-preclaim` was not used or modified.

## Residue and locked capabilities

The preserved database contains zero active Scheduler jobs and zero rows in all
of these locked downstream surfaces:

- memory retrieval queries: zero;
- memory retrieval matches: zero;
- paper decisions: zero;
- paper positions: zero;
- paper trade events: zero;
- paper trade audits: zero;
- episode outcomes / PnL-bearing outcome rows: zero.

Longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, wallets, live providers, and paid APIs remain locked.

## Money-usefulness contribution

This failed composition is useful because it proves that a discovery failure is
no longer converted into an unrelated accounting exception with its cause lost.
The exact source failure, transaction-local Scheduler claim, rollback outcome,
and disposable database now survive cleanup as reviewable evidence. That
reduces false campaign-success signals and prevents later money-bearing lanes
from acting on an unexplained pre-lifecycle outcome.

## What improves

- The public owner receives the original non-success activation terminal.
- No `(None,)` stage-evidence placeholder reaches accounting.
- The earliest operational failure remains primary.
- Returned failures reach evidence capture before cleanup.
- The closed disposable database, hash, migration state, integrity result, and
  FK result are retained.

## What remains locked

All capability locks listed above remain at zero. No exact-pass authorization,
fresh authoritative campaign authorization, retry, restart, successor, or
downstream lifecycle activation is granted by this report.

## Required proof for a future lane

A separately authorized lane may diagnose the frozen secondary discovery
fixture/response contract and the claimed-but-rolled-back stage-evidence
projection. It must begin from this preserved first-failure evidence, retain
strict six-unit accounting, and obtain a new explicit authorization before any
new exact public composition. This lane grants no rerun.

## Functionality Risks / Setbacks / Efficiency Blockers

- The exact public composition did not reach token-slot activation or two
  `WINDOW_15M` closes.
- The frozen secondary response produced `MALFORMED_RESPONSE: missing pool
  object`; whether the fixture or consumer contract is wrong is not resolved in
  this lane.
- Accountable discovery work was claimed inside the rolled-back transaction,
  but no durable stage-evidence object remained; strict accounting consequently
  blocked. Resolving that projection without synthetic evidence requires a new
  bounded audit/design authorization.
- Application-level network patching proves the exercised Python path made no
  `urllib` call; it is not packet capture.
- No closeout report is permitted because exact PASS was not achieved.

## Stop condition

This report is the sole post-composition change. No source, test, fixture, or
implementation repair was made after the one exact execution, and the exact
node was not rerun.
