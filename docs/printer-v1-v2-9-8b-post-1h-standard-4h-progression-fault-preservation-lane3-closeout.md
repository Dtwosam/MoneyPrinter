# V2-9.8B Lane 3 — Post-1H Standard-4H Progression + Fault Preservation Closeout

**Document status:** `CLOSEOUT`

**Date:** 2026-08-23

**Starting implementation/repair HEAD reviewed:**
`01fe653b27f3d8d5101d675d4848fb5de85d0e38`

**Verdict:**
`V2_9_8B_LANE3_POST_1H_STANDARD_4H_PROGRESSION_FAULT_PRESERVATION_CLOSEOUT_PASS_READY_FOR_LANE4_READINESS_AUDIT`

## Scope and accepted commits

This closeout covers only the durable post-1h Standard-4H progression and
fault-preservation boundary. It performs no campaign, provider call,
authoritative operational-database mutation, Lane-4 work, or Cycle-3
activation.

| Commit | Accepted role |
| --- | --- |
| `eefc1df8ffee3b91f85571511f97c0d6c9b9811c` | Lane-3 readiness audit |
| `9ea8baaf75162b31ecb6d1dd23abbaf64949aa47` | Lane-3 design |
| `93903dc3d743594120409f7cb6fa563ddd10098d` | Two-contract design amendment |
| `899c69fd1322d06355bcf9f3a0c2e1c7d99a6a7b` | Narrow implementation and focused proof |
| `01fe653b27f3d8d5101d675d4848fb5de85d0e38` | Post-commit factory wiring repair |

## Final production path

The accepted reachable production path is:

```text
standard first-hour handoff transaction
-> one durable progression attempt + exactly two token rows
-> committed WINDOW_1H predecessor terminal truth
-> sole post-commit factory-loop progression evaluation
-> durable 0/1/2 eligible subset
-> existing atomic Standard-4H handoff transaction
-> WINDOW_4H rows + LONG_CONTINUATION_* steps + Central Scheduler jobs
   + stage-scoped campaign work
-> Central-Scheduler-claimed, Source-Governed Standard-4H execution
-> shared progression terminal/accounting/reporting derivation
```

`campaign_ownership.persist_standard_first_hour_handoff_set` creates the
progression aggregate inside the existing first-hour handoff transaction.
`standard_4h_progression.evaluate_standard_4h_progression` later consumes the
committed predecessors, and
`standard_4h_progression.commit_standard_4h_progression_handoff` extends the
existing `plan_standard_campaign_4h_handoff` authority. The only factory-loop
call to `run_standard_four_hour_campaign_barrier` is after the predecessor
step/job/work exception owner. The obsolete call inside that owner is absent.

## Migration 061 and durable authority

Migration 061 owns:

- `printer_memory_factory_standard_4h_progression_attempts`, unique for the
  exact campaign/campaign-run/cycle boundary; and
- `printer_memory_factory_standard_4h_progression_tokens`, exactly two rows
  created by the approved production producer for the two exact campaign
  slots.

The aggregate binds campaign, configuration, campaign run, factory run, cycle,
slot, token, mint, pair, lifecycle, exact tracking queue and cadence-owned
lane, predecessor window/memory, and optional successor WINDOW_4H identity.
Foreign keys, uniqueness, JSON validity, state/cause consistency, indexes, and
identity/primary/terminal immutability are enforced. The migration performs no
historical inference or backfill. Schema readiness verifies both tables,
columns, indexes, and foreign keys.

The real consumers are the progression evaluator, atomic handoff owner,
eligibility-manifest reader, factory terminal validator/report, full-run
accounting, and stopped-ownership terminalizer. Required historical campaigns
without an aggregate remain incomplete/ambiguous rather than complete.

## Authority, predecessor, and fault results

Progression reads the existing production owners for:

- exact campaign, configuration, campaign-run, factory-run, and cycle state;
- supervision lease and campaign/external cancellation;
- `OperationalDatabaseTargetBinding`, canonical database path, and runtime
  schema readiness;
- Scheduler health and stage-scoped campaign-work integrity;
- campaign and exact token lifecycle budgets plus actual request/job usage;
- exact slot `tracking_queue_id` and
  `resolve_campaign_slot_cadence_authority` lane truth; and
- exact WINDOW_1H window, run step, Scheduler job, campaign work, memory,
  promotion, safety, continuity, freshness, and provenance truth.

No parallel health ledger, budget owner, lane-only identity, or synthesized
provider-capacity eligibility authority was introduced.

Once a 1h predecessor close commits, later progression exceptions cannot reach
its success/failure owner. The 1h step, Scheduler job, campaign work, and
campaign window therefore remain unchanged. A progression primary belongs only
to its attempt or token. Atomic compare-and-set plus migration triggers make the
first primary immutable; later cleanup, reconciliation, and reporting facts are
secondary. A real progression cause is not replaced by
`SAFE_STOP_PREFLIGHT_FAILED`.

## Peer isolation and atomic handoff

Each predecessor is evaluated independently. `INELIGIBLE` and token-local
`TERMINAL_FAILED` are terminally non-eligible and contribute zero successors;
`TERMINAL_FAILED` remains reported as `FAILED`. These states do not destroy an
eligible peer. Genuine campaign/run/lease/database/global-integrity/global-
budget/cancellation faults terminalize the shared attempt instead.

From exact `ELIGIBILITY_COMPLETE`, the handoff re-reads the immutable two-row
truth and real shared prerequisites inside one transaction. It creates only
the eligible 0/1/2 WINDOW_4H graph, advances only eligible slots, records exact
successor identities, and moves the attempt to `HANDOFF_COMMITTED` only after
complete read-back. Two terminally non-eligible rows produce an explicit
zero-token committed no-op. Any exception rolls back to the complete prior
eligibility state; partial graphs are rejected. A committed graph may only be
verified idempotently, not recreated. No automatic retry, resume, restart,
rerun, or successor authority exists.

## Crash, SQLite, and accounting truth

- Missing required progression, stopped `WAITING_FOR_PREDECESSORS` or
  `EVALUATING`, missing/partial successor graphs, and stopped claimed work are
  `INTERRUPTED_AMBIGUOUS` / review-required, never success.
- `ELIGIBILITY_COMPLETE` without handoff is `ELIGIBLE_NOT_CREATED` and
  incomplete. A handoff transaction failure leaves that prior durable state.
- A committed handoff exposes exact `CREATED_PENDING`, `RUNNING`, `SUCCEEDED`,
  `FAILED`, `CANCELLED`, or `INTERRUPTED_AMBIGUOUS` successor truth.
- If SQLite prevents the canonical progression primary write, the last durable
  state remains authoritative, no child graph is created, and stopped
  ownership derives ambiguity/review. Progression writes no generic heartbeat
  lease-file evidence; the heartbeat channel remains heartbeat-owned only.

`derive_standard_4h_progression_status` is the shared read contract used by
the Standard-4H terminal validator and full-run accounting, and its result is
carried into the factory terminal report. It distinguishes waiting,
ineligible, eligible-not-created, created/pending, running, succeeded, failed,
cancelled, and interrupted/ambiguous. `HANDOFF_COMMITTED` alone is not success:
composition completes only when every created successor has exact terminal 4h
truth and every other token is `INELIGIBLE` or token-local `TERMINAL_FAILED`.

## Bounded proof and checks

- Lane-3 progression, migration 061, authority, fault, interruption,
  accounting, atomicity, and real factory-loop wiring module: **31 passed**.
- Six directly affected selective-1h and 1h-to-4h modules: **70 passed**;
  two legacy fixture failures reproduced identically at pre-Lane-3 HEAD
  `93903dc3d743594120409f7cb6fa563ddd10098d`.
- Accepted Lane-2 close-phase, one-source-unit/yield/reselection,
  category/fairness, and last-ACTUAL deadline lock set: **76 passed**.
- All seven Lane-3-touched production Python modules compiled from source.
- Production search found one factory-loop barrier invocation and no second
  production call boundary.
- Migration 061 disposable application, integrity, foreign-key, vocabulary,
  no-backfill, and schema-readiness checks are included in the passing Lane-3
  module.
- Documentation whitespace/diff and tracked-tree/index checks passed before
  the closeout commit.

No broad suite, campaign, live provider, or authoritative database mutation
was performed.

## Non-blocking baseline debt

The unchanged selective-1h fixtures still include an obsolete clean-promotion
expectation (`E2Z_BLOCKED` versus expected creation) and a stale first-hour
safety request-count expectation (`3` versus canonical `4`). Both exact nodes
fail the same way at pre-Lane-3 HEAD `93903dc`; neither is a Lane-3 regression.

Legacy full-run fixture assumptions and obsolete synthetic multi-cycle adapter
assumptions remain baseline/Lane-4 accounting debt. Existing Cycle-2 reporting
defects are not repaired here. Historical required Standard-4H runs without
Migration-061 rows remain truthfully legacy ambiguous/incomplete.

## Locks and next permitted lane

Lane-2 category-first selection, within-category deadline ordering,
token/cycle fairness, Central Scheduler claim ownership, Source Governor,
one-unit yield/reselection, evidence cutoffs, degraded-evidence success-to-
audit behavior, and technical-context fail-closed behavior remain unchanged.

Cycle 3, WINDOW_12H/WINDOW_24H, retrieval, BUY/SELL/HOLD, positions, trades,
paper audits, PnL, live wallet/private-key/signing/funds/execution, paid APIs,
scoring/ranking/confidence/weighted logic, and embeddings/vectors remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

Lane 3 is **CLOSED PASS** with no remaining proven Lane-3 blocker. The next
permitted action is only:

```text
LANE 4:
Multi-Cycle Terminal Accounting / Reporting
AUDIT / READINESS ONLY.
```

This closeout does not authorize Lane-4 design or implementation and does not
activate Cycle 3.
