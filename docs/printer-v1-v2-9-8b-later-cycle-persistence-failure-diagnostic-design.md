# Printer V1 V2-9.8B Later-Cycle Persistence Failure Diagnostic Design

Date: 2026-08-24

Work class: documentation-only bounded diagnostic design

Starting HEAD: `e53f7c99f7dc8c3a512b8c51453af714cbd1b3cc`

Consumed authorization:
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd`

Authoritative incident DB SHA-256:
`9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`

## Verdict

`V2_9_8B_LATER_CYCLE_PERSISTENCE_FAILURE_DIAGNOSTIC_DESIGN_PASS_READY_FOR_NEXT_LANE`

Schema verdict:

`NO_SCHEMA_CHANGE_REQUIRED`

Exact next permitted action:

`BOUNDED PERSISTENCE FAILURE DIAGNOSTIC NARROW TDD IMPLEMENTATION`

This design closes the established `DESIGN_GAP` only. It does not identify or
repair an underlying persistence defect and does not authorize a campaign.

## Authority, baseline, and preserved forensic truth

The required HEAD and `CURRENT_HANDOFF.md` gate match exactly. This design used
the active Printer source stack, the Python Builder Guide, the completed
later-cycle persistence forensic/readiness audit, the real exception producers,
the later-cycle catch, migrations 055/056/059/060, the Scheduler failure owner,
and the terminal consumers.

The audit classification remains
`DIAGNOSTIC_GAP_BLOCKS_ROOT_CAUSE_IDENTIFICATION` / Python Builder Guide
`DESIGN_GAP`. No coding is justified until this design is adopted into the next
narrow TDD lane.

Established facts remain unchanged:

- all 13 later-cycle source-evidence links and two neutral token/pair identities
  persisted;
- no Cycle-2 pre-admission item, Cycle-2 row, or Cycle-2 tracking row persisted;
- exact-two pair item plus `PAIR_READY` atomicity behaved correctly;
- GeckoTerminal rate limits were source-scarcity evidence, not a proven cause;
- the initiating subcause is irrecoverable; and
- the later terminal-accounting `TypeError` was independent and is repaired.

The incident DB, consumed authorization, application artifacts, and terminal
evidence remain immutable and are not backfilled. This mechanism is prospective
only.

## Design alternatives

1. **Use the exact Scheduler job's existing `last_error` diagnostic owner —
   selected.** `scheduler.py` already preserves bounded canonical JSON in this
   field while emitting the unchanged categorical cause to the Scheduler
   observer. The pre-admission attempt has a unique `scheduler_job_id`, so the
   owner and attempt are joined deterministically.
2. Add an attempt diagnostic column/table — rejected. The existing Scheduler
   field is durable, exact-owner-linked, and already approved for diagnostics;
   a migration would duplicate ownership without evidence of necessity.
3. Put JSON in `first_terminal_cause` — rejected. That field and its immutable
   trigger own the stable top-level categorical cause.
4. Use logs, stderr, or raw exception strings — rejected. They are not the
   canonical durable owner and cannot provide bounded, safe classification.

## Discarded-detail boundary

The loss occurs in
`authoritative_live_operational_campaign.py` at the outer
`except PreAdmissionAttemptError as exc` boundary. When the attempt is still
`RUNNING`, the catch writes `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` to the
attempt and Scheduler job and uses `exc` only transiently for failure-domain
classification. The producer, stable subcode, underlying exception type,
SQLite extended result, and chained exception are then discarded.

The design retains the top-level cause and adds a bounded subcause. It does not
change the separate generic `except Exception` mapping to
`LATER_CYCLE_SUPPLY_FAILED`.

## Production producer inventory

Only boundaries reachable while the attempt is durably `RUNNING` can complete
the generic failure terminalization. Attempt/Scheduler creation, initial claim,
and pre-RUNNING transition failures are excluded: when they fail, no RUNNING
attempt exists for this catch to terminalize. Post-`PAIR_READY`/`NO_PAIR` final
loads are also excluded because the attempt is no longer RUNNING.

| Canonical operation | Production function / underlying boundary | SQLite | Application validation | Transaction position | Retained now | Discarded now |
|---|---|---:|---:|---|---|---|
| `RUNNING_ATTEMPT_FAILURE_TERMINALIZATION` | `terminalize_pre_admission_attempt`; `_required`, load, allowed-state check, compare-and-set `_transition`; reachable while handling missing supply, a supply exception, or the no-pair result | update/read may use SQLite, but current SQLite errors escape the other top-level catch | yes | Phase-C outer transaction, before commit | generic terminal value if the fallback succeeds | exact validation/transition producer and chain |
| `SOURCE_EVIDENCE_LINK_ARGUMENT` | `link_pre_admission_source_evidence`; ambiguous response/failure, ordinal/request/logical-stage/time validation | no | yes | Phase-C outer transaction, before pair savepoint | stable `PreAdmissionAttemptError` text only in memory | producer identity and bounded reason |
| `SOURCE_EVIDENCE_LINK_INSERT` | same function; immutable link `INSERT` catches `sqlite3.IntegrityError` | yes | no | Phase-C outer transaction, before pair savepoint | `SOURCE_EVIDENCE_LINK_INVALID` only in memory | SQLite exception type/name and exact insert boundary |
| `FROZEN_EVIDENCE_PROJECTION` | `attach_frozen_tracking_lane` -> `project_classifier_candidate_from_pre_admission_evidence` / `_decode_evidence_candidate`; required field, JSON, captured-time projection | no | yes | after selection, before pair savepoint | `FROZEN_LANE_EVIDENCE_INVALID` or dynamic required/time code in memory | exact projection boundary and chain |
| `FROZEN_LANE_CLASSIFICATION` | `attach_frozen_tracking_lane` -> `classify_tracking_lane_from_candidate_evidence`; no permitted lane or action/lane mismatch | no | yes | after projection, before pair savepoint | `FROZEN_TRACKING_LANE_UNAVAILABLE` in memory | exact classifier boundary |
| `PAIR_SHAPE_VALIDATION` | `persist_pre_admission_pair` -> `_validate_pair`; exact-two/ordinal, attempt owner, distinct identity, channel labels | no | yes | before pair savepoint | categorical code in memory | exact pair-precheck producer |
| `FROZEN_LANE_FIELD_VALIDATION` | `persist_pre_admission_pair` -> `_require_frozen_tracking_lane_fields`; completeness, allowlist, equality, hash, time, owner | no | yes | before pair savepoint | `FROZEN_TRACKING_LANE_MISSING` or helper code in memory | exact frozen-field producer |
| `PAIR_ATTEMPT_RUNNING_PREREQUISITE` | `persist_pre_admission_pair` -> `load_pre_admission_attempt` and RUNNING check | read only | yes | before pair savepoint | `ATTEMPT_NOT_FOUND`, timestamp code, or `INVALID_ATTEMPT_TRANSITION` in memory | exact prerequisite boundary |
| `PAIR_ITEM_INSERT` | `persist_pre_admission_pair`; per-slot required/time serialization followed by item `INSERT` | yes | yes | inside `persist_pre_admission_pair` savepoint; phase is `PAIR_ITEM_1` or `PAIR_ITEM_2` | application code, or all `sqlite3.Error` collapsed to `PAIR_PERSISTENCE_FAILED` | slot boundary, SQLite class/name, original chain |
| `PAIR_READY_TRANSITION` | `persist_pre_admission_pair` -> `_transition`; RUNNING -> `PAIR_READY` compare-and-set and reload | yes | yes | inside the same pair savepoint after both inserts | typed transition code, or SQLite error collapsed to `PAIR_PERSISTENCE_FAILED` | transition-versus-insert boundary and SQLite detail |

Savepoint rollback/release errors currently escape as a general exception and
therefore do not themselves produce
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`. The implementation must capture the
initiating pair diagnostic before cleanup so a cleanup exception cannot replace
it; it must not broaden the top-level classification for unrelated exceptions.

## Minimum diagnostic envelope

The canonical JSON object is named
`PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1`. It contains exactly:

| Field | Contract |
|---|---|
| `diagnostic_schema` | exact literal `PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1` |
| `failure_code` | exact literal `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`; also binds the existing Scheduler diagnostic staging/consumption |
| `producer_code` | one stable producer from the inventory, or `PRE_ADMISSION_PERSISTENCE_UNKNOWN` |
| `failure_category` | one enum value from the taxonomy below |
| `operation_phase` | stable bounded phase: `TERMINALIZATION`, `SOURCE_LINK`, `FROZEN_CARRIER`, `PAIR_PRECHECK`, `PAIR_ITEM_1`, `PAIR_ITEM_2`, `PAIR_READY`, or `UNKNOWN_PHASE` |
| `exception_type` | sanitized class name, ASCII `[A-Za-z0-9_]`, maximum 96 characters |
| `reason_code` | existing strict uppercase application code, SQLite `sqlite_errorname`, or an honest bounded fallback code; maximum 128 characters |

Attempt/campaign/cycle identity and time are deliberately not duplicated. The
Scheduler row is uniquely linked from the attempt through `scheduler_job_id`;
the attempt owns campaign/run/proposed-cycle identities and `terminal_at`; the
job owns `finished_at`. The canonical JSON remains under the Scheduler owner's
existing 1,536-character total bound.

No free-form raw detail is part of V1 of this envelope. Stable application codes
and SQLite `sqlite_errorname` provide the minimum safe reason. This excludes
secrets, credentials, URLs/query material, paths, provider bodies, payloads,
SQL values, and unbounded messages by construction. If a later design proposes
raw detail, it requires a separately reviewed sanitizer and hard bound; arbitrary
`str(exc)` must never enter this envelope.

## Producer and category taxonomy

`producer_code` says **where**. `failure_category` plus `reason_code` says
**what kind of failure occurred**. They are categorical evidence, never scores,
ranks, confidence, or policy weights.

Allowed categories are limited to producers proven above:

- `APPLICATION_VALIDATION`: strict existing pre-admission validation or
  compare-and-set code that is not a missing prerequisite;
- `PREREQUISITE_MISSING`: a required attempt/state/frozen prerequisite is
  absent or no longer valid;
- `CONSTRAINT_OR_INTEGRITY`: `sqlite3.IntegrityError` or SQLite primary result
  `SQLITE_CONSTRAINT`, retaining its safe extended `sqlite_errorname`;
- `SQLITE_BUSY_OR_LOCK`: SQLite primary result `SQLITE_BUSY` or
  `SQLITE_LOCKED`;
- `SQLITE_IO_OR_OPERATIONAL`: another `sqlite3.Error` at an inventoried write
  boundary, retaining its safe SQLite error name when available; and
- `UNKNOWN_PERSISTENCE_FAILURE`: an untyped/unmapped
  `PreAdmissionAttemptError` or an otherwise unmapped exception caught by an
  inventoried persistence-boundary wrapper.

`SOURCE_EVIDENCE_LINK` and `ATOMIC_MATERIALIZATION` are producer/phase facts,
not failure categories, so they are not duplicated as categories.

For an application error, `reason_code` is retained only when it matches
`[A-Z][A-Z0-9_]{0,127}`; otherwise it becomes
`UNCLASSIFIED_PRE_ADMISSION_ERROR`. For SQLite, use `sqlite_errorname` when it
meets the same bound, else `SQLITE_ERROR_NAME_UNAVAILABLE`. Unknown uses
`UNKNOWN_PERSISTENCE_REASON`. No mapping may infer a root cause from message
text.

## First-cause ownership

`PreAdmissionAttemptError` remains the existing exception owner but gains one
optional immutable diagnostic value. The exact originating boundary constructs
it before rollback or re-raise. Wrapping an error that already owns a diagnostic
must preserve that object unchanged. The outer catch constructs the UNKNOWN
fallback only when no typed diagnostic exists.

The job-keyed in-process staging map must become first-write-wins for this
failure: a second different diagnostic for the same job is rejected or ignored,
never substituted. `printer_pre_admission_discovery_attempts.first_terminal_cause`
remains protected by its existing immutable trigger. Once `fail_job` consumes
the staged envelope and leaves the job `FAILED`, no terminalization, report,
cleanup, reconstruction, or replay path may stage or write another primary
diagnostic.

There is no approved secondary persistence envelope here. A later terminal,
report, cleanup, or reconstruction error remains separate evidence and cannot
be appended to or overwrite this diagnostic.

## Durable producer and transaction semantics

The exact production path is:

```text
inventoried underlying condition
-> boundary constructs immutable bounded diagnostic
-> PreAdmissionAttemptError carries it outward
-> pair savepoint rolls back/release when applicable
-> authoritative later-cycle outer catch verifies the exact RUNNING attempt/job
-> stage diagnostic for that exact scheduler_job_id
-> terminalize attempt FAILED with unchanged generic cause
-> fail_job(error=unchanged generic cause, max_retries=0)
-> Scheduler consumes the matching staged envelope into last_error
-> one outer commit makes attempt/job terminal truth and diagnostic durable
-> existing terminal consumer stops the campaign
```

The pair savepoint continues to cover both item inserts and the `PAIR_READY`
transition. Diagnostic construction occurs before rollback. A successful
rollback removes every partial item and `PAIR_READY` change but leaves the
outer Phase-C transaction usable; the existing attempt/job terminal boundary
then commits the diagnostic. There is no nested commit inside materialization,
no partial Cycle-2 authority, and no weakening of pair atomicity.

If the database cannot perform the existing terminal write at all, code must
not claim durable diagnostic success. The initiating in-memory diagnostic stays
primary for propagation, and the existing fail-closed terminal behavior applies.
This mechanism does not add a loop or retry the failed materialization.

## Durable evidence consumer

The canonical consumer is read-only forensic/readiness inspection of the exact
attempt joined to its unique Scheduler job. The narrow implementation should
provide a pure bounded decoder beside the pre-admission model; it reads and
validates the canonical JSON only when:

- attempt cause is exactly `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`;
- attempt state and job status are both `FAILED`;
- `max_retries=0` behavior left no active job; and
- the joined job `last_error` is a valid V1 envelope whose `failure_code`
  matches the attempt cause.

Malformed, missing, mismatched, or legacy plain-string `last_error` returns
`DIAGNOSTIC_UNAVAILABLE`; it never changes terminal truth. The completed audit's
same attempt/job forensic join is therefore the operational consumer class.
Campaign terminalization, `finalize_four_token_shared_terminal`, and the repaired
terminal-accounting bridge remain unchanged and continue to consume only the
top-level generic cause.

The decoder is evidence-only. It is not imported by source, selection,
admission, cadence, Scheduler priority, memory, retrieval, decision, position,
trade, audit-PnL, retry, resume, restart, or successor owners.

## Unknown behavior

An unrecognized exception at an inventoried boundary keeps the stable boundary
when known, uses `UNKNOWN_PERSISTENCE_FAILURE`, records only the safe exception
class and `UNKNOWN_PERSISTENCE_REASON`, and fails closed under the unchanged
top-level cause. If even the boundary is not known, producer/phase become
`PRE_ADMISSION_PERSISTENCE_UNKNOWN` / `UNKNOWN_PHASE`.

UNKNOWN is evidence of missing classification only. It is never success,
retryability, rerun authority, resume authority, restart authority, successor
authority, or permission to create an authorization.

## Narrow expected implementation surface

No implementation occurs in this lane. The next lane should normally touch
only:

- `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`: immutable
  diagnostic type/constructor, strict category mapping, producer annotations,
  first-cause preservation, and read-only decoder;
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`:
  stage the carried/UNKNOWN diagnostic at the existing generic catch before the
  unchanged attempt/job terminal writes;
- `src/printer_v1/scheduler/scheduler.py`: extend the existing bounded
  diagnostic allowlist for the exact V1 fields and make staging first-write-wins
  without changing observer cause or `fail_job` scheduling behavior; and
- the focused pre-admission persistence and later-cycle terminal integration
  tests named below.

No new subsystem, table, migration, scheduler job, source/provider call,
runtime loop, global exception framework, terminal-accounting change, or public
financial interface is needed.

## Focused narrow TDD matrix

Tests inject an underlying condition at the real producer and invoke the real
later-cycle catch. They must not inject a final diagnostic record or expected
classification.

| Proof | Underlying condition injected at real boundary | Required durable result |
|---|---|---|
| A — known source-link producer | violate the real source response/failure/request trigger or immutable link constraint through `link_pre_admission_source_evidence` | producer `SOURCE_EVIDENCE_LINK_INSERT`, category `CONSTRAINT_OR_INTEGRITY`, safe SQLite reason, attempt generic cause unchanged, job `FAILED`, `max_retries=0` with no retry/cooldown |
| B — distinct pair producer | use otherwise-valid two items with a real item FK/constraint failure inside `persist_pre_admission_pair` | producer `PAIR_ITEM_INSERT`, phase identifies slot, category `CONSTRAINT_OR_INTEGRITY`; proves it does not collapse with A |
| C — unknown | make an inventoried boundary wrapper receive an unmapped exception through a delegating fault at its actual operation call, not by constructing a diagnostic/terminal row | known producer when available, `UNKNOWN_PERSISTENCE_FAILURE`, bounded safe exception type, no raw message, generic top-level failure |
| D — rollback durability | make slot 1 insert succeed and slot 2 fail through a real FK/constraint | zero attempt-item rows, no `PAIR_READY`, zero Cycle-2/slot/tracking rows; the Scheduler diagnostic and failed attempt survive |
| E — first-cause immutability | after A or B durably terminalizes, inject a later reporting/cleanup failure at its real consumer boundary | original `last_error` envelope, attempt cause, and job terminal row remain byte-for-byte unchanged; later issue is separate |
| F — success opposite | persist a valid exact pair through the same production functions | `PAIR_READY`, exactly two items, no failure diagnostic, no generic persistence cause |
| G — legacy/malformed read safety | read a legacy plain-string, missing, oversized, unknown-field, or mismatched envelope through the read-only decoder | `DIAGNOSTIC_UNAVAILABLE`; no write and no terminal/policy change |
| H — no retry semantics | complete A/B/C then inspect Scheduler/job/campaign state and exercise the evidence decoder | `FAILED`, `max_retries=0` outcome, no cooldown/pending job, no new job/attempt/authorization, and no consumer capable of restart/resume/successor action |

Nearest suites are
`tests/test_v2_9_8b_pre_admission_discovery_attempt_persistence.py` and
`tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py`.
Run their changed nodes, the nearest existing Scheduler diagnostic compatibility
tests, compile changed production modules, then static diff/unlock checks. No
live command, provider, broad suite, or consumed incident rerun belongs to that
lane.

## Schema and no-retry verdicts

`NO_SCHEMA_CHANGE_REQUIRED`.

`printer_scheduler_jobs.last_error` is already an approved bounded diagnostic
owner for the exact `PRE_ADMISSION_DISCOVERY_SELECTION` job, and the attempt's
unique `scheduler_job_id` supplies durable identity. The attempt cause and
Scheduler observer retain the unchanged top-level category. Every existing
attempt field remains semantically correct; adding a column/table would be
duplicative.

The envelope deliberately has no `retryable`, priority, action, decision,
eligibility, or successor field. The only failure call remains
`fail_job(..., max_retries=0)`. No consumer may translate category, producer,
reason, presence, absence, or UNKNOWN into execution authority.

## Permanent locks and closeout

Permanent-lock result: **PASS, unchanged**. Solana-only, Solana-memecoin-only,
paper-only, no wallet/private keys/signing/funds/live execution, no paid API,
no scoring/ranking/confidence/weighted logic, no embeddings/vectors, no Source
Governor or Central Scheduler bypass, dirty memory excluded, 5m support-only,
and Cycle 3 / 12h / 24h / retrieval / BUY / SELL / HOLD / positions / trade
events / paper audits / PnL / V2-10 remain locked.

Functionality Risks / Setbacks / Efficiency Blockers:

- the consumed incident's exact subcause remains permanently irrecoverable;
- catastrophic inability to write SQLite cannot be made durably diagnosable by
  writing more SQLite and must remain honestly fail closed;
- Scheduler `last_error` has no schema-level JSON check, so strict producer and
  decoder validation plus focused malformed-envelope tests are mandatory; and
- producer annotations must cover the real boundaries above without turning
  arbitrary exception messages into a taxonomy.

Required task closeout:

- **Files changed:** this design and minimal `CURRENT_HANDOFF.md` update only.
- **What was built:** a prospective minimum producer/envelope/consumer,
  taxonomy, first-cause, transaction, schema, and TDD design.
- **What was not touched:** production, tests, migrations/schema, DB/operator
  evidence, terminal-accounting repair, providers, Scheduler runtime, campaign,
  authorization, and locked capabilities.
- **Tests/checks:** documentation/static/diff checks only.
- **Pass/fail:**
  `V2_9_8B_LATER_CYCLE_PERSISTENCE_FAILURE_DIAGNOSTIC_DESIGN_PASS_READY_FOR_NEXT_LANE`.
- **Next recommended phase:**
  `BOUNDED PERSISTENCE FAILURE DIAGNOSTIC NARROW TDD IMPLEMENTATION`.
