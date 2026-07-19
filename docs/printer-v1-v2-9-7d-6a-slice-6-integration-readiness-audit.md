# V2-9.7D.6A Slice 6 Integration Readiness Audit

## Verdict

`V2_9_7D_6A_SLICE_6_INTEGRATION_READINESS_PASS`

PASS means the static integration audit is complete and the minimum safe
follow-on order is defined. It does not mean Slice 6 is implementation-ready.
The blockers in this document prohibit an operational command or campaign.

## Scope and Method

This audit inspected the committed V2-9.7D persistence and 3A-5C object lanes,
the authoritative V2-9.7B.1-B.5 implementations and focused tests, and the
existing lifecycle, supervision, backup, report, and replay boundaries.

Inspection was static except for a read-only SQLite query against the configured
persistent target. No migration, database write, source call, scheduler/runtime
execution, lifecycle event, backup, restore, replay, memory generation, command,
retrieval, or financial action ran.

## Read-Only Persistent-Target Finding

`data/printer_v1.sqlite3` passed `PRAGMA integrity_check` and had zero
`foreign_key_check` rows. Its migration ledger ended at
`024_discovery_source_channel.sql`. It had none of migrations 025-031 and none
of the `printer_memory_factory_*` campaign/run tables.

Therefore the persistent target is not eligible for Slice 6 integration or an
operational campaign. Migration must not be applied there until a separate
lane has implemented and rehearsed the required backup/restore process on
disposable copies.

## Existing Reusable Owners

| Concern | Authoritative reusable owner | Exact files | Reuse boundary |
|---|---|---|---|
| Campaign/config/report envelope | V2-9.7D.2A | `migrations/031_operational_campaign_persistence.sql`; `src/printer_v1/operator_cli/campaign_persistence.py`; `tests/test_v2_9_7d_2a_campaign_persistence.py` | Reuse immutable configuration, Git-provenance validation, canonical JSON/hash, terminal-report identity, and exact replay predecessor constraints |
| Campaign identity/state | V2-9.7D.3A | `src/printer_v1/operator_cli/campaign_identity_state.py`; `tests/test_v2_9_7d_3a_identity_state_validation.py` | Reuse pure identity, transition, terminal-cause, idempotency, and report-predecessor validation |
| Two-token scheduling | V2-9.7D.3B | `src/printer_v1/scheduler/two_token_fairness.py`; `tests/test_v2_9_7d_3b_two_token_scheduler_fairness.py` | Reuse selection policy only; it does not own queueing, claiming, persistence, cancellation, or execution |
| Selective continuation | V2-9.7D.4A | `src/printer_v1/scheduler/token_local_continuation.py`; `tests/test_v2_9_7d_4a_token_local_selective_continuation.py` | Reuse pure token-local verdicts after authoritative B.1/B.2 facts are assembled |
| Support-only 5m | V2-9.7D.4B | `src/printer_v1/scheduler/support_only_5m_capture.py`; `tests/test_v2_9_7d_4b_conditional_support_only_5m_capture.py` | Reuse exact trigger/identity/provenance validation; never grant main-window authority |
| Trajectory/checkpoints | V2-9.7D.5A | `src/printer_v1/scheduler/trajectory_checkpoint.py`; `tests/test_v2_9_7d_5a_trajectory_checkpoint_objects.py` | Reuse immutable observations, gaps, phases, checkpoints, cutoff, and later-evidence separation |
| Manipulation context | V2-9.7D.5B | `src/printer_v1/scheduler/manipulation_context.py`; `tests/test_v2_9_7d_5b_manipulation_context_objects.py` | Reuse independent evidence quality, integrity, tradeability, eligibility, lifecycle, behavior, and unknown dimensions |
| Opportunity segments | V2-9.7D.5C | `src/printer_v1/scheduler/opportunity_segment.py`; `tests/test_v2_9_7d_5c_opportunity_segment_evidence_gaps.py` | Reuse immutable segment/outcome separation and explicit event-time gaps; do not calculate profit or execution |
| B.1 promotion reporting | V2-9.7B.1 | `src/printer_v1/operator_cli/one_command_15m_factory.py`; `tests/test_v2_9_7b_1_authoritative_promotion_reporting.py` | `_authoritative_promotions_for_run`, `_per_token_outcomes`, and `_memory_yield_report` own run-local authoritative promotion interpretation |
| B.2 effective safety | V2-9.7B.2 | `src/printer_v1/safety/composite.py`; `src/printer_v1/context_evidence/window_15m.py`; `tests/test_v2_9_7b_2_timeframe_aware_safety_reporting.py` | `effective_safety_context_report` owns neutral effective labels while preserving raw labels; the pre-existing composite gate remains acceptance authority |
| B.3 terminal lifecycle | V2-9.7B.3 | `src/printer_v1/operator_cli/tracking_lifecycle_reconciliation.py`; `src/printer_v1/operator_cli/lane_x3_post_cycle_lifecycle.py`; `tests/test_v2_9_7b_3_tracking_lifecycle_reconciliation.py` | Reuse one run/token/pair event, queue/job cleanup, support-only non-authority, cooldown/archive mapping, and idempotency |
| B.4 supervision primitive | V2-9.7B.4 | `src/printer_v1/operator_cli/proof_supervision.py`; `migrations/030_v2_9_proof_run_supervision.sql`; `tests/test_v2_9_7b_4_heartbeat_lease_reliability.py` | Reuse atomic lock replacement, exact ownership, monotonic renewal, bounded confirmed Windows retry, first-fault fallback, cooperative stop, cleanup, and no restart semantics; do not reuse the proof launcher as the campaign supervisor |
| B.5 Git provenance | V2-9.7B.5 | `src/printer_v1/operator_cli/git_provenance.py`; `tests/test_v2_9_7b_5_embedded_git_provenance.py` | Reuse `capture_git_provenance` only at launch and `validate_launch_provenance` thereafter; replay must use stored provenance |
| Existing run/final report | V2-4 through V2-9.7B | `migrations/028_memory_factory_run_ledger.sql`; `src/printer_v1/operator_cli/one_command_15m_factory.py` | Reuse reporting logic selectively, not the proof-only runner or schema constraints |
| Proof copy/schema validation | V2-9.1 | `src/printer_v1/operator_cli/proof_db_schema_readiness.py`; `tests/test_v2_9_1_proof_db_schema_readiness.py` | Reuse hashing, read-only counts, integrity/FK checks, and path isolation concepts; it is not an operational backup/restore implementation |

## Required Wiring to B.1-B.5

### B.1 Authoritative Promotion Reporting

The campaign run/cycle/window graph must exact-link each completed main window
to the existing integer `printer_memory_windows.id`, its close-step evidence,
and any eligible `printer_episodes` row. B.1 remains the sole promotion
interpreter. The 4A continuation adapter must consume B.1's exact
`CLEAN_PROMOTED`, `ALREADY_EXISTS_IDEMPOTENT`, `DIRTY_OR_BLOCKED`, or
`NO_PROMOTION` result; it must not infer promotion from a candidate memory
quality label, a 5m support row, or a 5A-5C object.

Campaign/cycle IDs and exact token-slot/lifecycle identities must be added to
the run-local scope. The current B.1 query scopes only through migration-028
run steps, so it cannot yet prove campaign, cycle, or token-slot ownership.

### B.2 Effective Safety Context

The integration adapter must load the exact persisted composite used at the
window checkpoint, preserve its source traces and raw labels, pass the already
decided gate result plus explicit window kind to
`effective_safety_context_report`, and store/report the returned neutral result.
`SAFETY_CONTEXT_UNKNOWN` is never acceptance. Manipulation context may refer to
the same raw safety evidence but cannot override the B.2 gate or tradeability.

The report must retain both the B.2 effective result and raw safety fields.
Persisting only the neutral label would lose the evidence needed for replay.

### B.3 Lifecycle Cooldown, Archive, and Rotation

One adapter must map a terminal campaign token record to B.3's existing
run/token/pair reconciliation key. B.3 must remain the only writer of tracking
queue disposition, lifecycle event, and associated scheduler cleanup. The
campaign token state may advance only after B.3 returns exactly one disposition
and zero active associated jobs.

Replacement selection may fill the same vacant slot only after reconciliation.
It must check the persisted pair-specific cooldown boundary and cannot create a
successor, silently recycle the same pair, or treat archive as permanent
rejection. A support-only 5m result never selects the disposition.

### B.4 Lease, First Fault, Cancellation, and No Restart

An operational campaign lease needs a new campaign-scoped persistence owner.
It may call the proven B.4 atomic lock/heartbeat primitive, but migration 030
and `proof_supervision.py` are proof-specific: `proof_scope='V2_9'`, proof-only
launcher types, proof/backup paths, and a foreign key to the proof-only run
ledger. They cannot be renamed or silently treated as operational ownership.

The supervisor must exact-link campaign/configuration/run identity; preserve
one immutable first fault in both campaign and supervision state; stop child
work after unconfirmed renewal; use one idempotent cleanup path for natural
completion, cancellation, and failure; terminalize all owned work; release the
lease; and create no successor, resume, or restart.

### B.5 Immutable Git Provenance

Capture once before campaign creation, validate it, and persist the exact payload
in migration 031's `launch_provenance_json`. Every run, final report, artifact,
and replay response must copy or validate that stored payload. No later slice
may call Git to refresh it. The report hash must cover the embedded provenance,
and replay must compare it with configuration provenance.

## Missing Schema, Persistence, and Report Fields

Migration 031 currently has only campaign, one configuration, and report
envelopes. The following durable links are absent:

- campaign-to-run and run-to-cycle identities, ordinals, start/end times, and
  first terminal cause;
- two token-slot records and exact token, mint, pair, lifecycle, queue, and
  replacement-predecessor identities;
- main/support window identity, kind, root 15m lifecycle, predecessor,
  checkpoint cutoff, and existing integer memory-window ID;
- scheduler-work identity, intent, deadline, status, Central Scheduler job ID,
  and source request/response/failure provenance;
- 4A continuation verdict/reasons and declared learning need;
- 4B trigger family, containing-main-window link, and permanent support-only
  authority flags;
- 5A trajectory, visible gaps, phases, reversals, checkpoints, and immutable
  evidence cutoffs;
- 5B manipulation lifecycle/behavior claims, four independent dimensions, raw
  evidence, and participant unknowns;
- 5C full-window/segment outcomes, path context, event-time references/gaps,
  re-entry link, and chart-versus-executable classification;
- B.1 authoritative episode/promotion identity and exact close-step event;
- B.2 effective and raw safety fields with exact composite/source links;
- B.3 lifecycle event, queue disposition, cooldown expiry, archive policy,
  replacement result, and cleanup reconciliation;
- operational lease owner, heartbeat/expiry, terminal status, first fault,
  cancellation, cleanup, and release evidence;
- backup, restore rehearsal, migration rehearsal, source/backup hashes, sizes,
  counts, integrity/FK results, and artifact identities;
- report-to-run/cycle links, terminal cause, shutdown/lease state, ceiling usage,
  source/scheduler efficiency, trajectory/manipulation/segment coverage, and
  locked-capability deltas.

`campaign_persistence.py` can create a campaign and persist immutable report
payloads, but it cannot persist a state transition or terminalization. The 3A
validator is pure, so a transactional compare-and-update writer is still
required.

## Duplicate Ownership and Conflicting Semantics

1. Migration 028 is fixed to `WINDOW_15M` and `db_mode='PROOF_ONLY'`; it cannot
   own operational multi-window campaign runs.
2. Migration 031 defines operational campaign envelopes but has no foreign key
   or identity link to migration-028 runs. B.1 and B.3 therefore operate on a
   disconnected run authority.
3. Migration 030 and `proof_supervision.py` own proof supervision, not an
   operational campaign lease. Reusing their rows would misstate scope and DB
   ownership.
4. Existing run statuses (`COMPLETED`, `SAFE_STOPPED`, and proof terminal
   labels) differ from 3A campaign terminal states. A fixed mapping is required;
   neither vocabulary may overwrite the other.
5. B.3 uses queue dispositions, lifecycle events, and existing tracking lanes;
   3A defines campaign token states such as `MANUAL_REVIEW`. The adapter must
   record both facts and prohibit two independent writers.
6. Existing DB identities are integer token/pair/window/job IDs, while 3A-5C
   object identities are strings. Exact mapping fields are required; string
   coercion or symbol/address guessing is unsafe.
7. B.1 derives created-versus-idempotent status from embedded close-step JSON
   because no promotion event table exists. Slice 6 must preserve the exact
   close-step payload or add a narrow immutable promotion linkage.
8. `persist_report_replay` writes a replay row, while the V2-9.7C contract says
   report-only replay writes nothing. The write-nothing rule is higher for Slice
   6; the persistence function must not be called by read-only replay until a
   later policy explicitly resolves this conflict.

## Backup, Restore, and Persistent-Target Prerequisites

The existing proof helper copies the persistent DB to a proof target, applies
migrations there, and creates a byte-identical proof backup. It does not create
an operational pre-migration backup, defend publication against interrupted
copy, rehearse restore, or reconcile a restored operational corpus.

Before any persistent migration or campaign start, a dedicated implementation
must:

1. verify the explicit canonical target identity and exclusive writer state;
2. close/checkpoint WAL writers and record source size, SHA-256, migration
   ledger, critical table counts, integrity, and foreign-key results;
3. copy to a same-volume temporary path and verify bytes/hash before atomic
   publication under a fresh backup identity;
4. leave the source untouched and never overwrite/delete the last verified
   backup;
5. restore the backup only to a disposable target and apply the proposed
   migrations there;
6. compare source/backup/restore hashes where byte identity is expected and
   schema, migration ledger, integrity, FKs, and critical counts after migration;
7. prove interruption leaves no published partial backup; and
8. persist or emit immutable prerequisite artifacts before launch eligibility.

The current persistent target's migration gap makes this a hard blocker, not a
preflight warning.

## Zero-Source Read-Only Replay Contract

### Required Inputs

- exact `campaign_id`, `configuration_id`, terminal `report_id`, and report
  hash;
- stored immutable configuration and B.5 launch provenance;
- exact linked run/cycle/token/window/work identities;
- committed B.1 promotion rows, B.2 safety composite/raw evidence, B.3 terminal
  lifecycle evidence, lease/shutdown evidence, and stored 4A-5C representations;
- locked-capability baseline/final counts already recorded by the terminal
  report.

### Required Outputs

- `REPLAY_VERIFIED` only when report bytes/hash and recomputed deterministic
  diagnostics agree, otherwise `REPLAY_BLOCKED` with exact reasons;
- the original report/replay identities, stored Git provenance, source/scheduler
  counts, promotion/safety/lifecycle outcomes, gaps/unknowns, terminal cause,
  and capability-lock deltas;
- explicit `source_calls=0`, `scheduler_work=0`, `memory_writes=0`, and
  `database_writes=0` evidence.

### Read-Only Guarantees and Current Gaps

The connection must use SQLite URI `mode=ro`, `PRAGMA query_only=ON`, and before/
after database file hash plus `total_changes=0`. Source Governor and Central
Scheduler entry points must be unavailable by construction, not merely unused
by a fixture.

Current `load_report_only` opens a normal connection, reads migration-028
`final_report_json`, mutates the returned in-memory report by adding a replay
field, does not validate migration-031 report hash/campaign/configuration
identity, and does not recompute authoritative diagnostics. It is a useful
legacy read helper, not the required Slice 6 replay owner.

## Minimum Safe Slice 6 Implementation Order

1. Freeze an ownership/identity mapping: migration-031 campaign is root;
   operational run/cycle/token/window/work records link to existing DB rows;
   B.1-B.5 remain semantic owners.
2. Implement and prove operational backup, restore rehearsal, and disposable
   migration preflight before touching the persistent target.
3. Add the smallest migration and persistence API for the missing campaign
   graph, transactional state transitions, first cause, and immutable object/
   report links. Rehearse only on disposable copies.
4. Add read-only B.1/B.2 adapters that assemble authoritative promotion and
   effective/raw safety facts for 4A continuation and reports.
5. Add the B.3 terminal adapter and rotation eligibility checks; prove cleanup
   before replacement.
6. Add a campaign-scoped operational lease/supervisor using B.4 primitives,
   with cancellation, first-fault, cleanup, release, no resume, and no restart.
7. Build one pure final-report assembler over stored authoritative facts and B.5
   provenance, then persist the terminal report once.
8. Build zero-source replay with enforced read-only DB access and no replay-row
   write.
9. Run an isolated two-token multi-cycle integration fixture proving all above
   and zero locked-capability deltas. Do not add a command surface in these
   sub-lanes.

## Recommended Narrow Follow-On Sub-Lanes and Proof

| Sub-lane | Narrow deliverable | Focused proof required |
|---|---|---|
| 6B.1 Ownership and schema reconciliation | campaign-rooted run/cycle/token/window/work/object schema plus transition writer | disposable migration upgrade/rollback; exact FKs and identities; idempotent transitions; immutable first cause; no existing-row change; zero locked rows |
| 6B.2 Operational backup/restore preflight | hash/size/count/integrity/FK backup publication and disposable restore rehearsal | interrupted copy, hash mismatch, existing target, WAL/writer conflict, restore mismatch, last-backup preservation, source byte/hash unchanged |
| 6B.3 B.1/B.2 integration adapters | read-only authoritative promotion and effective/raw safety assembly | clean/idempotent/dirty/no-promotion; 15m/1h/4h safety; stale/missing/mismatched evidence; exact campaign/run/cycle/window isolation; no writes |
| 6B.4 B.3 lifecycle and rotation adapter | one terminal disposition, cleanup, cooldown/archive, vacant-slot replacement eligibility | natural/dirty/blocked/cancelled token outcomes; support-only non-authority; idempotent event; zero active work; cooldown blocks reselection; replacement only after reconciliation |
| 6B.5 Operational lease and safe-stop | campaign-scoped lease and first-fault terminal cleanup | exact owner, monotonic renewal, bounded Windows retry, unconfirmed-renewal child stop, cancellation idempotency, logger fault, immutable first cause, lease release, no successor/restart |
| 6B.6 Final campaign report | pure deterministic report assembler and one immutable terminal persist | all required diagnostics, provenance equality, independent outcome layers, unknown/gap visibility, exact totals, hash determinism, zero forbidden deltas |
| 6B.7 Zero-source replay | enforced read-only deterministic report verification | `mode=ro`, query-only, DB hash/row counts unchanged, no source/scheduler entry, provenance not recaptured, equivalent and blocked fixtures, malformed/cross-campaign report rejection |
| 6B.8 Isolated Slice 6 integration proof | two-token multi-cycle fixture only | fairness, selective continuation, positive/negative 5m, 5A-5C persistence, B.1-B.5, backup prerequisite artifacts, terminal cleanup, replay, no restart, zero retrieval/financial rows |

## Blockers Before Integration

- The persistent target lacks migrations 025-031 and all campaign/run tables.
- No operational backup/restore implementation or restore rehearsal exists.
- Migration 028 and migration 030 are proof-only and incompatible with an
  operational multi-window campaign.
- Migration 031 has no campaign-to-run/cycle/token/window/work/object graph.
- No persistence API owns campaign transitions or transactional first-cause
  terminalization.
- B.1/B.3 cannot currently prove campaign/cycle/token-slot ownership.
- 4A-5C outputs are immutable in memory but have no durable exact-linked owner.
- Operational lease ownership and campaign-scoped recovery do not exist.
- Final campaign report fields and a single authoritative report assembler are
  absent.
- Read-only replay is not enforced and conflicts with persisted replay writes.
- Current Jupiter categorical storage cannot satisfy 5C quantitative execution
  proof; affected fields must remain explicit gaps.

Every blocker must fail preflight. None may be converted into a warning or an
`UNKNOWN` that still permits campaign start.

## Money-Usefulness Contribution

This audit prevents the completed object slices from being attached to the
wrong proof-era authorities. It protects corpus yield, safety interpretation,
lifecycle diversity, code identity, and shutdown evidence from becoming
disconnected or hindsight-reconstructed. The resulting implementation order
prioritizes recoverability and authoritative facts before campaign operation.

## What Integration Will Improve

When the listed blockers are repaired, Printer will be able to attribute each
bounded campaign lesson to an exact persistent target, code revision, source
trace, window trajectory, manipulation context, opportunity segment, promotion
outcome, safety result, lifecycle disposition, and terminal cause. Reports and
replay can then distinguish real clean yield from partial candidates and chart
opportunity from unproved execution without activating decisions or finance.

## What Remains Locked

Slice 6 implementation, operational command syntax, operational campaign start,
persistent migration, backup creation, restore, source fetching, scheduler
runtime, memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
WAIT/AVOID/NO_ACTION activation, positions, trades, audits, PnL, wallets, keys,
signing, real funds, live execution, paid APIs, scoring, ranking, confidence,
weighting, embeddings, and vectors remain locked.

No command surface or operational campaign should start yet. The abstract
command remains locked until lower Slice 6 integration and isolated proof pass;
operational use remains separately gated after V2-9.7D.

## Implementation and Proof Required

Complete sub-lanes 6B.1-6B.8 in order, with each lane independently passing its
focused proof and no-unlock checks. Only after backup/restore, migration,
authority wiring, terminal supervision, final reporting, and zero-source replay
all pass on isolated disposable targets may a later lane audit command-surface
readiness. This audit authorizes none of that implementation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Two persistence generations currently describe runs and campaigns without an
  exact relationship; premature wiring would create split authority.
- Proof-only schema constraints cannot be relaxed in place without migration
  and compatibility proof.
- B.1's embedded close-step JSON dependency is precise but fragile and may need
  a narrow immutable promotion link for durable replay.
- Existing lifecycle rows predate campaign/cycle identities, so adapters must
  preserve backward compatibility without guessing ownership.
- Operational backup correctness on Windows must account for active writers,
  WAL state, interrupted copy, and atomic replacement behavior.
- Full 5A-5C normalized persistence could create excessive schema breadth;
  canonical immutable JSON plus indexed identity/link columns should be favored
  unless a query requirement proves normalization necessary.
- Strict read-only replay may expose incomplete historical reports. It must
  block rather than repair or silently synthesize missing facts.
- Quantitative execution evidence remains unavailable from current categorical
  provider storage, limiting executable-opportunity reporting but not honest
  chart/gap reporting.
