# Printer V1 V2-9.8B Later-Cycle Persistence Failure Diagnostic Closeout

Date: 2026-08-24

Starting HEAD:

`9ea7df5c33f54b0d25e16ab98af79737996402c3`

Accepted design:

`5f560464b73a8809e148e31e6dfa0a02307a9c5e`

Initial implementation:

`3c01a2901905327cee67448fea41e3d25d0eadb0`

Accepted first-cause repair:

`9ea7df5c33f54b0d25e16ab98af79737996402c3`

## Closeout verdict

`V2_9_8B_LATER_CYCLE_PERSISTENCE_FAILURE_DIAGNOSTIC_CLOSEOUT_PASS`

The prospective diagnostic gap classified as
`DIAGNOSTIC_GAP_BLOCKS_ROOT_CAUSE_IDENTIFICATION` is resolved. A future
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` can preserve a bounded, safe, stable
subcause when the existing terminal SQLite transaction succeeds. This closeout
does not identify or repair the consumed incident's irrecoverable persistence
subcause.

## Final production surface

The implementation range from the accepted design through the accepted repair
changed production only in:

- `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`;
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
- `src/printer_v1/scheduler/scheduler.py`.

The first-cause repair changed only the first two files. No schema, migration,
provider, Source Governor, Scheduler selection/priority/retry/cooldown policy,
authorization, terminal-accounting, or capability surface changed.

## Diagnostic contract

The exact schema is `PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1`. The canonical
object has exactly these fields:

- `diagnostic_schema`;
- `failure_code`;
- `producer_code`;
- `failure_category`;
- `operation_phase`;
- `exception_type`;
- `reason_code`.

`failure_code` remains exactly
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`. Validation requires the exact key set,
approved enums, ASCII exception type of at most 96 characters, uppercase bounded
reason code, deterministic sorted compact JSON, and the existing 1,536-character
Scheduler `last_error` limit. There is no free-form exception message, provider
body, URL/query material, secret, SQL value, identifier duplication, timestamp,
or arbitrary metadata.

Canonical example:

```json
{"diagnostic_schema":"PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1","exception_type":"IntegrityError","failure_category":"CONSTRAINT_OR_INTEGRITY","failure_code":"LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED","operation_phase":"SOURCE_LINK","producer_code":"SOURCE_EVIDENCE_LINK_INSERT","reason_code":"SQLITE_CONSTRAINT_FOREIGNKEY"}
```

## Bounded production proof

Focused disposable-DB tests prove underlying conditions are classified at the
real production boundaries rather than by injecting final diagnostic rows:

| Proof | Underlying condition | Result |
|---|---|---|
| Source evidence | Real immutable source-link insert violates SQLite integrity | `SOURCE_EVIDENCE_LINK_INSERT` / `CONSTRAINT_OR_INTEGRITY` / `SOURCE_LINK`; safe SQLite reason; generic terminal cause unchanged |
| Pair item | Slot 2 reaches its real item insert and a disposable SQLite trigger aborts it | `PAIR_ITEM_INSERT` / `CONSTRAINT_OR_INTEGRITY` / `PAIR_ITEM_2`, distinct from source-link failure |
| Unknown | The real delegated source-link insert operation raises an unmapped exception | known producer and phase retained; `UNKNOWN_PERSISTENCE_FAILURE`, safe exception class, `UNKNOWN_PERSISTENCE_REASON`, no raw message |

The production path is complete:

```text
underlying persistence condition
-> exact boundary constructs immutable diagnostic
-> PreAdmissionAttemptError carries it
-> pair savepoint rollback/release when applicable
-> exact RUNNING attempt/job outer catch
-> job-keyed diagnostic staging
-> attempt FAILED with unchanged generic cause
-> fail_job(max_retries=0)
-> existing Scheduler last_error owner
-> one existing terminal commit
-> strict read-only forensic decoder
```

## Rollback and first-cause proof

The pair savepoint still covers both item inserts and the `PAIR_READY`
transition. When slot 2 fails, slot 1 is rolled back, zero pair items survive,
no attempt reaches `PAIR_READY`, and no Cycle-2 root or tracking authority is
created. The diagnostic becomes durable only in the existing later terminal
transaction; no nested recovery commit or persistence retry exists.

Both repaired first-cause cases pass:

1. A real source-link integrity failure followed by a real disposable trigger
   failure on the attempt `FAILED` transition raises the original
   `PreAdmissionAttemptError`. Its source-link diagnostic is unchanged, the
   terminalization error is chained, staging is discarded, the attempt/job stay
   nonterminal, `last_error` stays absent, and the decoder returns
   `DIAGNOSTIC_UNAVAILABLE`.
2. A real slot-2 item failure followed by savepoint cleanup failure and full
   rollback failure still raises the original typed pair diagnostic. The
   rollback errors are secondary context, the diagnostic object is unchanged,
   no partial Cycle-2 authority is claimed, and no retry occurs.

A separately injected later terminal-reporting failure leaves the already
durable attempt `first_terminal_cause` and Scheduler diagnostic bytes unchanged.

## Success, Scheduler, and decoder proof

A valid exact pair through the same production functions creates exactly two
items, reaches `PAIR_READY`, completes the Scheduler job normally, and emits no
persistence diagnostic or generic persistence failure.

Scheduler staging remains non-authoritative and is keyed by exact `job_id`.
Focused proofs cover first-write-wins, job isolation, mismatched failure-code
non-consumption, one-time consumption, stale staging removal on success or
cancel, compatibility of generic plain `last_error`, and the unchanged public
categorical Scheduler observer cause. Static inspection confirms that outside
the bounded constructor, Scheduler staging validator, and strict forensic
decoder, other `last_error` readers use the value only as opaque display or
terminal-reconstruction evidence and do not parse the V1 fields. No diagnostic
field drives scheduling, priority, cooldown, admission, source budgets, memory,
retrieval, decisions, positions, trades, audits, PnL, retry, resume, restart, or
successor behavior.

The decoder joins the exact attempt to its Scheduler job and returns a typed
diagnostic only for exact failed attempt/cause, failed unlocked job, correct job
kind, valid bounded V1 JSON, and matching failure code. Missing, legacy,
malformed, oversized, extra/missing-field, wrong-schema/cause/code/enum/type,
active-lock, and nonterminal evidence return `DIAGNOSTIC_UNAVAILABLE`. Tests
also prove the decoder performs no write.

## Catastrophic SQLite honesty

If terminal SQLite persistence itself cannot succeed, no durable diagnostic is
claimed, no second transaction or retry is attempted, the in-memory initiating
diagnostic remains the primary exception, and the durable decoder truthfully
returns `DIAGNOSTIC_UNAVAILABLE`. This accepted design limitation is not a
regression.

## Focused verification and baseline debt

The focused diagnostic, first-cause, pre-admission persistence/Scheduler,
frozen-pair materialization, Cycle-2 diagnostic compatibility, and directly
affected shared-terminal node completed with `41 passed`.

Two broader nearby starting-HEAD fixture debts were characterized and left
unchanged:

- `test_callback_executes_one_durable_zero_or_two_attempt` uses stale candidate
  evidence and observes `FAILED` instead of its expected `PAIR_READY`
  (`1 failed, 4 passed` in that module);
- `test_real_factory_opening_failure_records_pre_lifecycle_zero_attempt_shape`
  reaches the pre-existing unbound `owned_proof_cycle_id` / incomplete-cycle
  terminal-accounting path (`1 failed, 1 passed` in that module; its directly
  affected Cycle-2 diagnostic sibling passes).

Neither failure is introduced by the documentation-only closeout, neither
invalidates the focused diagnostic production path, and neither is repaired in
this lane.

## Incident and permanent locks

The authoritative incident DB remained byte-identical at SHA-256
`9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`.
Read-only immutable inspection reports integrity `ok`, foreign-key violations
`0`, and unsafe SQLite sidecars `0`. The incident was not backfilled.

Consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd` remains permanently
dead and non-reusable. No authorization, campaign, provider call, Source
Governor runtime, Central Scheduler runtime, authoritative DB write, retry,
resume, restart, or successor occurred.

Solana-only, Solana-memecoin-only, paper-only, no wallet/private keys/signing/
funds/live execution, no paid API, no scoring/ranking/confidence/weighted logic,
no embeddings/vectors, no governor/scheduler bypass, dirty-memory exclusion,
and support-only 5m remain locked. Cycle 3, 12h/24h, retrieval, decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, and V2-10 remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- The consumed incident's exact persistence subcause remains irrecoverable.
- Catastrophic SQLite terminal-write failure can preserve only the in-memory
  first cause; durable evidence must remain unavailable.
- The two unrelated starting-HEAD fixture debts remain for a separately
  authorized lane and must not be conflated with this diagnostic closeout.

## Exact next permitted action

`READ-ONLY POST-DIAGNOSTIC-REPAIR EXACT-HEAD / WORKTREE / DB REREADINESS GATE`

That gate must complete before any new 4/2/2 authorization preparation. This
closeout does not create an authorization or authorize a campaign.
