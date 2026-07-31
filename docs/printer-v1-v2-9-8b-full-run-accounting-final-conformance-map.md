# Printer V1 V2-9.8B Full-Run Accounting Final Conformance Map

Date: 2026-07-31

Implementation branch:
`codex/v2-9-8b-full-run-accounting-terminal-evidence-implementation`

Audited implementation HEAD:
`ec8a5b57789116a8969800b910d29b18daa98bb2`

Document type: read-only implementation map and acceptance contract.

Current audit verdict:
`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_CONFORMANCE_AUDIT_BLOCKED`

Block reason:
`BLOCKED_CONSOLIDATED_DESIGN_CONFORMANCE_GAPS`

This document freezes the remaining implementation scope. It does not authorize a live campaign, a bounded proof, a migration, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## 1. Governing source stack

Use together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-9-8b-post-repair-authoritative-window-15m-full-run-accounting-and-terminal-evidence-design.md`
- `docs/printer-v1-v2-9-8b-post-repair-window-15m-full-run-accounting-and-terminal-evidence-implementation.md`

The approved design remains controlling where the implementation report differs.

## 2. Completion law

A requirement is complete only when every column below is satisfied:

```text
design requirement
-> real execution boundary
-> single owner evidence
-> independent action-local evidence
-> canonical report field
-> acceptance-gate check
-> negative fail-closed test
```

Green unit tests are supporting evidence only. A helper-only or post-hoc reconstruction is not sufficient where the design requires execution-time observation.

## 3. Single-owner target architecture

| Concern | Required owner |
| --- | --- |
| Source access and measured attempts | Source Governor / existing measured-transport boundary |
| Scheduler work and terminal state | Central Scheduler |
| Lifecycle execution and cadence | Memory Factory |
| Campaign/run/cycle/factory identity | Operational campaign coordinator |
| Window and Scheduler campaign ownership | Existing campaign ownership layer |
| Full-run six-unit aggregation | One coordinator-created `CampaignSixUnitOwner` |
| Independent verification | One coordinator-created `CampaignActionLocalLedger` |
| Slot/campaign terminalization | Unified terminal closure |
| Persisted terminal artifact and replay | Existing canonical report owner and exact-identity `report-only` path |

No second accounting owner, report owner, Scheduler, source path, or terminal owner may be introduced.

## 4. Frozen implementation map

### C1 - One full-run accounting owner

**Design law**

One accounting owner must cover the ordinary campaign from the first discovery stage through terminal reconciliation.

**Current defect**

`operational_memory_factory_command.py` creates `campaign_units` for pre-lifecycle evidence, while `finalize_full_run_ownership_and_report()` creates a replacement `CampaignSixUnitOwner` for lifecycle evidence. The repaired path therefore has two owners and no single full-run evidence object.

**Required files/functions**

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
  - `_run_operational_campaign`
  - `_finalize_operational_six_unit_accounting`
  - `_apply_full_run_campaign_acceptance`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
  - `finalize_full_run_ownership_and_report`
- `src/printer_v1/sources/campaign_six_unit_accounting.py`

**Required correction**

- Create one `CampaignSixUnitOwner` and one `CampaignActionLocalLedger` before the first accountable stage.
- Pass both through the operational owner, driver, factory, terminal cleanup, final report, and replay paths.
- Ingest pre-lifecycle, discovery/Scheduler, both slot stages, and terminal reconciliation into the same owner.
- Remove lifecycle-started action-local skipping for repaired operational runs.
- Finalization may close and verify the owner; it may not create a replacement owner.

**PASS evidence**

One owner ID and one action-local ledger identity appear in the final report and reconstruct the complete stage manifest.

**Negative proof**

Replacing or dropping the owner between stages must block with an explicit owner-continuity reason.

---

### C2 - Complete immutable identity flow before lifecycle work

**Design law**

The factory must receive campaign ID, campaign run ID, cycle ID, configuration ID, factory run ID, `WINDOW_15M`, and token capacity 2 before lifecycle planning or source work.

**Current defect**

The coordinator passes only campaign/run/cycle into the factory before the generated factory run ID is known. The complete `OperationalLifecycleOwnershipContext` is constructed only after the factory returns, weakening the drift check.

**Required files/functions**

- `operational_memory_factory_command.py`
- `authoritative_live_operational_campaign.py`
- `origin_lifecycle_campaign.py`
- `one_command_15m_factory.py`
  - `run_one_command_15m_factory`
  - factory-run initialization callback

**Required correction**

- Split factory initialization from lifecycle execution if needed.
- Generate the factory run ID, bind it authoritatively to the campaign run, construct the complete immutable context, then begin lifecycle planning.
- Fail before lifecycle work on any missing or drifting identity.
- Preserve exact token mint, pair address, stage, step, and operation ordinal in every accountable identity.

**Negative proof**

Missing or mismatched factory-run identity before the first lifecycle job must produce zero lifecycle Scheduler jobs and zero source calls.

---

### C3 - Every attributable source attempt observed exactly once

**Design law**

Every actual governed attempt belongs to exactly one stage, including success, failure, primary, fallback, backup, snapshot, close, context, discovery, and selection calls.

**Current defect**

The factory emits one observation only for the final exact-pair result with both request and response IDs. Five pre-close context calls, failed attempts, primary failures followed by fallback success, and backup attempts are omitted.

**Required files/functions**

- Source Governor/measured-transport execution boundary used by existing adapters
- `one_command_15m_factory.py`
  - `_execute_snapshot`
  - pre-close context execution helper
  - fallback/backup paths
- discovery/selection source execution path
- `campaign_full_run_accounting.py`
  - transport identity construction

**Required correction**

- Instrument the common governed outbound-attempt boundary, not only the final step result.
- Emit one immutable attempt identity per real attempt, whether succeeded or failed.
- Assign each attempt to the correct campaign stage at execution time.
- Include the close observation plus all five pre-close context calls.
- Preserve source name, request kind, target, attempt ordinal, request/response/failure IDs, result, bytes, and normalized rows.

**Negative proofs**

- Drop one context attempt -> block.
- Drop a failed primary before fallback -> block.
- Duplicate an attempt across two stages -> block.

---

### C4 - Byte and normalized-row equality

**Design law**

Owner and action-local evidence must agree on complete transport records and all derived totals.

**Current defect**

Action-local observations do not carry canonical response bytes or normalized rows. Owner finalization derives bytes with `LENGTH(normalized_payload_json)` and hardcodes one normalized row. Transport identity comparison does not prove byte/row equality.

**Required files/functions**

- `measured_transport.py`
- `campaign_six_unit_accounting.py`
  - transport identity key/reconciliation
- Source Governor normalization boundary
- `campaign_full_run_accounting.py`

**Required correction**

- Measure canonical bytes and normalized rows once at the governed response-normalization boundary.
- Store those values in both the owner record and independently observed action-local record.
- Compare complete records or compare identity plus explicit byte/row totals per operation.
- Remove `LENGTH(normalized_payload_json)` and hardcoded normalized-row assumptions from repaired operational evidence.

**Negative proof**

Equal request identities with one byte or row mismatch must fail reconciliation.

---

### C5 - Real reservation boundaries

**Design law**

`LIFECYCLE_RESERVED_TRANSPORT_OPERATION` is observed when governed capacity is actually reserved, not inferred from Scheduler enqueue.

**Current defect**

Reservations are minted from `SCHEDULER_ENQUEUE` using a duplicated `PRECLOSE_CONTEXT_REQUEST_COUNT` constant.

**Required files/functions**

- authoritative source-budget/reservation owner
- `one_command_15m_factory.py`
- `campaign_full_run_accounting.py`
  - remove duplicated reservation policy

**Required correction**

- Use one shared authoritative reservation policy.
- Emit reservation identities at the real reservation boundary.
- Preserve operation family and ordinal so the close observation and five context reservations remain distinct.
- Report reserved, attempted, succeeded, and failed operations separately.

**Negative proof**

Reservation-policy drift or one missing reservation identity must block before PASS.

---

### C6 - Real named validation boundaries

**Design law**

Named validations are observed when they actually execute.

**Current defect**

Slot evidence records only exact-pair validation. Discovery and terminal validation identities are synthesized post-hoc from durable rows. Cadence, budget, close, coverage, quality, ownership, active-work, lease, and forbidden-delta validations are not independently observed.

**Required files/functions**

- discovery/selection validation boundary
- factory cadence, identity, budget, close, coverage, and quality gates
- unified terminal cleanup/reconciliation
- `CampaignActionLocalLedger`

**Required correction**

Observe named identities for applicable:

- selection/handoff;
- identity;
- cadence;
- budget;
- exact pair;
- close;
- coverage;
- quality;
- terminal ownership;
- zero active work;
- zero locked work;
- lease release;
- forbidden deltas;
- no retry/restart/resume/successor.

Do not create validation identities merely because finalization found a row.

**Negative proof**

Remove each required validation family independently and prove PASS is impossible.

---

### C7 - Complete Scheduler ownership and observation

**Design law**

Every attributable Scheduler job is owned once and its enqueue, claim, and terminal state are independently observed.

**Current defect**

The new projection covers lifecycle snapshot/close jobs only. Discovery, selection, first-15m handoff, and cleanup cancellation jobs are not completely included. Action-local observation records enqueue only.

**Required files/functions**

- Central Scheduler enqueue/claim/complete/fail/cancel boundaries
- discovery/selection Scheduler path
- executor handoff path
- `campaign_ownership.project_campaign_scheduler_job`
- unified terminal cleanup

**Required correction**

- Project existing IDs for discovery, selection, handoff, opening snapshots, anchored snapshots, closes, and cleanup cancellations.
- Observe enqueue, claim, and terminal operations.
- Preserve actual terminal state and first terminal cause.
- One Scheduler job may belong to one stage only.

**Negative proofs**

Missing, extra, duplicate, active, locked, failed, cancelled, or cross-stage-conflicting job ownership must be visible and block according to the design.

---

### C8 - Full-manifest equality

**Design law**

Operational PASS requires bidirectional equality across the complete stage manifest and all six units.

**Current defect**

Operational reconciliation passes `owner_equality_stage_ids=slot_stage_ids`, excluding discovery and terminal stages.

**Required files/functions**

- `campaign_six_unit_accounting.reconcile_full_run_owner_to_action_local`
- `campaign_full_run_accounting.finalize_full_run_ownership_and_report`

**Required correction**

- Do not scope repaired operational equality to the two slot stages.
- All pre-lifecycle and four mandatory stages must participate.
- Compatibility scoping may remain for historical/unit callers but must be reported and must block repaired operational PASS.

**Negative proof**

A run with all four stage names present but equality limited to two stages must return `BLOCKED_UNSAFE`.

---

### C9 - Window registration before slot terminalization

**Design law**

Unified terminal closure must see exact owned windows and persist lawful queue/slot outcomes.

**Current defect**

Cleanup and `reconcile_campaign_terminal()` run before post-hoc window registration. Selected slots can therefore become `MANUAL_REVIEW`; the later full-run report merely describes a `COOLDOWN` disposition and defaults missing queue evidence to `COOLDOWN`.

**Required files/functions**

- real `WINDOW_CLOSE` transaction in `one_command_15m_factory.py`
- `campaign_ownership.register_campaign_window_close`
- `unified_terminal_closure.reconcile_campaign_terminal`
- `campaign_full_run_accounting.resolve_campaign_slot_terminal_disposition`

**Required correction**

- Prefer exact campaign-window registration inside the close transaction before the close step becomes succeeded.
- Where atomicity is impossible, perform explicit compensation before slot reconciliation.
- Read actual tracking queue state; remove default `COOLDOWN`.
- Persist slot `COOLDOWN` only when an owned terminal window and real tracking `COOLDOWN` are proven.
- Derive campaign-window terminal state from authoritative promotion/quality outcome, not `memory_status` alone.

**Negative proof**

A completed owned window must leave the DB slot at `COOLDOWN`; a report-only `COOLDOWN` with a persisted `MANUAL_REVIEW` row must block.

---

### C10 - Cadence, coverage, and close completeness

**Design law**

PASS requires exact cadence evidence and exactly two succeeded terminal closes.

**Current defect**

The gate checks two terminal window rows but not expected/actual/missing snapshots, snapshot IDs, coverage status, or exact succeeded close count. Current tests permit three snapshots per token and still PASS.

**Required files/functions**

- cadence policy owner
- factory step/snapshot/coverage tables
- `build_full_run_terminal_report`
- `evaluate_campaign_acceptance_gate`

**Required correction**

Per token prove and report:

- cadence policy and lane;
- expected snapshot count;
- exact snapshot IDs;
- actual and missing counts;
- coverage status;
- one succeeded close step;
- exact memory row and cycle ID;
- window status and quality.

For two `TRACK_NORMAL` tokens, focused proof must show 16 snapshots total plus two closes.

**Negative proofs**

Missing one snapshot, duplicate snapshot ownership, incomplete coverage, or a non-succeeded close must block.

---

### C11 - Prevent unlawful clean episode creation

**Design law**

A non-clean or `DO_NOT_TRAIN` window must not create a clean authoritative episode.

**Current defect**

The implementation detects inconsistency after querying already-created episodes. It does not prevent insertion.

**Required files/functions**

- actual episode-creation/promotion owner invoked by the 15m close pipeline
- quality gate before episode insertion
- `evaluate_quality_consistency`

**Required correction**

- Gate clean episode creation before insertion using exact memory status, data-quality label, and `do_not_train`.
- Preserve actual episode ID/kind when lawful.
- Record `NO_CLEAN_EPISODE_CREATED` when no lawful non-clean episode kind exists.

**Negative proof**

Attempted clean episode insertion for a partial/dirty/`DO_NOT_TRAIN` window must create zero clean episode rows and block clean promotion.

---

### C12 - One complete canonical report and strict gate

**Design law**

One persisted canonical report must contain every exact identity and every acceptance fact.

**Current defect**

The full-run section omits selection-batch identity, per-token step/job IDs, snapshot/coverage evidence, complete quality/episode details, six-unit identity sets or hashes, complete terminal graph, locked-work proof, retry/restart/resume/successor state, marker hashes, and artifact hashes. It also labels a campaign-window string as `memory_window_id`.

**Required files/functions**

- existing canonical final-report owner
- `campaign_full_run_accounting.build_full_run_terminal_report`
- `unified_terminal_closure.build_campaign_terminal_report`
- `evaluate_campaign_acceptance_gate`

**Required correction**

Extend the existing canonical persisted report. Include:

- execution, campaign, run, cycle, configuration, supervision, factory;
- selection batch and token slots;
- exact token/pair identities;
- per-token factory steps and Scheduler IDs;
- snapshots and coverage;
- campaign-window ID and numeric memory-window row ID as separate fields;
- window quality and lawful episode ID/kind;
- complete stage statuses and first causes;
- six-unit identities or canonical hashes;
- complete Scheduler attribution;
- campaign/run/cycle/supervision/factory terminal states;
- active and locked work;
- actual lease release;
- forbidden deltas;
- authorization/invocation evidence;
- retry/restart/resume/successor evidence;
- DB, marker, report, and artifact hashes.

The gate must explicitly require each approved design §11 condition and report completeness. Do not use default-true values for omitted Scheduler evidence.

**Negative proof**

Remove each mandatory report family and prove the gate blocks.

---

### C13 - Terminal safety and authorization truth

**Design law**

PASS requires one actual authorization/invocation, zero active and locked campaign work, released lease, zero forbidden deltas, and no retry/restart/resume/successor.

**Current defect**

`active_work_result` is carried but not fully gated. Active projected lifecycle jobs are counted, but complete active and locked campaign work is not. Authorization is inferred from one campaign-run row with a non-null factory binding.

**Required files/functions**

- authorization/no-rerun evidence owner
- campaign active-work owner
- supervision cleanup
- terminal report and acceptance gate

**Required correction**

- Derive exactly-one invocation from actual authorization/marker evidence.
- Gate on zero active and zero locked work across all campaign-owned families.
- Gate on real lease release and zero forbidden deltas.
- Gate on no retry, restart, resume, or successor.
- Preserve hashes and first terminal cause.

**Negative proofs**

Authorization count 0 or 2, active work, locked work, unreleased lease, forbidden delta, retry, restart, resume, successor, or missing marker hash must independently block.

---

### C14 - Exact public report-only replay

**Design law**

The public exact-identity `report-only` path must reconstruct the complete repaired run without source, Scheduler, or writes.

**Current defect**

The new replay test directly calls `build_full_run_terminal_report()` using previously supplied in-memory arguments. It does not exercise the public report-only owner or independently reconstruct complete evidence from stored identities.

**Required files/functions**

- public `report-only` command path in `operational_memory_factory_command.py`
- canonical terminal replay in `unified_terminal_closure.py`
- durable full-run report/evidence loading

**Required correction**

- Require exact campaign/run/report identities.
- Load stored canonical report and durable full-run evidence.
- Independently reconstruct ownership, stages, six-unit identities/totals, cadence, quality, Scheduler attribution, and terminal safety.
- Compare canonical bytes and hashes.
- Make zero source calls, zero Scheduler actions, and zero writes.
- Never select by fallback and never upgrade historical V1 evidence to repaired V2 PASS.

**Negative proofs**

Wrong identity, missing evidence, byte mismatch, historical V1 evidence, or any attempted source/Scheduler/write side effect must block replay.

---

### C15 - Truthful stage terminal status and first cause

**Design law**

Every started stage seals once with actual `COMPLETED`, `BLOCKED`, or `FAILED` status and immutable first terminal cause.

**Current defect**

The four new stages are sealed as `COMPLETED` even when a Scheduler job or later gate fails. Discovery and terminal stages are constructed post-hoc as completed.

**Required files/functions**

- stage sealing calls across discovery, slot, and terminal boundaries
- `seal_campaign_stage_evidence`
- owner idempotency/close behavior

**Required correction**

- Start and terminalize stages at real boundaries.
- Preserve first terminal cause.
- A failed operation must not leave its stage completed.
- Repeated finalization/replay must not create duplicate stages or change terminal truth.

**Negative proof**

Inject one failed operation in each stage family and assert the stage status/cause and overall verdict remain truthful and idempotent.

## 5. Expected file-level change map

The builder should inspect first and change only what is required. Likely touched files:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/campaign_ownership.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/sources/measured_transport.py`
- the actual source-budget/reservation owner
- the actual episode-creation owner
- focused tests and the implementation report

A migration is not expected. If a necessary invariant cannot be enforced by the existing schema, stop and return a narrow design amendment instead of adding a convenience migration.

## 6. Minimum focused test contract

Use disposable databases and injected transports only.

Required positive proof:

- one ordinary two-token `WINDOW_15M` path;
- two distinct `TRACK_NORMAL` token/pair identities;
- 16 snapshot steps and two close steps;
- complete context bundle accounting;
- complete discovery/handoff/lifecycle/cleanup Scheduler ownership;
- exactly two owned terminal windows with exact cycle IDs;
- persisted slot `COOLDOWN` truth;
- full stage manifest;
- non-vacuous all-stage equality;
- complete canonical report;
- public exact-identity zero-side-effect replay;
- zero active/locked residue;
- zero retrieval and financial deltas.

Required negative families:

1. missing/conflicting window ownership;
2. missing/extra/duplicate Scheduler ownership;
3. missing action-local surface;
4. missing context/fallback/failed source attempt;
5. byte/row mismatch;
6. reservation or validation mismatch;
7. missing stage or scoped equality;
8. cadence/coverage/close incompleteness;
9. slot/report state disagreement;
10. unlawful clean episode attempt;
11. active/locked work or lease failure;
12. authorization or retry/restart/resume/successor drift;
13. report field/hash omission;
14. replay identity/evidence/side-effect failure;
15. idempotent repeated registration, terminalization, and replay;
16. historical V1 evidence remains historical only.

Do not run a broad repository suite unless focused failures prove a shared architectural regression.

## 7. Builder stop conditions

Return `BLOCKED` instead of narrowing the design when:

- one full-run owner cannot be preserved;
- complete action-local observation requires an unapproved second source/Scheduler path;
- a necessary DB invariant requires a migration;
- the existing canonical report/replay owner cannot represent the required evidence without a design amendment;
- focused tests expose a pre-existing architectural conflict that prevents honest completion.

## 8. Final implementation verdict

PASS requires every C1-C15 item and every completion-law column to be satisfied.

Allowed PASS label:

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

A PASS does not authorize a live campaign. It permits only independent operator review and, after acceptance/integration, the bounded disposable proof lane.

## 9. Independent reviewer contract

The independent reviewer must remain read-only and return one of:

- `CONFORMANCE_REVIEW_PASS`
- `CONFORMANCE_REVIEW_BLOCKED`

The reviewer must inspect the approved design, this map, the actual diff, tests, and claimed outputs. It must not accept a requirement merely because the builder's report says PASS.

For each C1-C15 item, the reviewer must identify:

- exact implementation location;
- exact execution boundary;
- owner evidence;
- independent action-local evidence;
- report field;
- gate check;
- positive test;
- negative test;
- verdict.

Any missing column blocks the review.