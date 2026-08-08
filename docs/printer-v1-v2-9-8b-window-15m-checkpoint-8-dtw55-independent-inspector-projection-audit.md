# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-55 Independent Inspector Projection Audit

Date: 2026-08-08

Linear: `DTW-55`

Baseline / consumed proof closeout:
`c7fc658cf0310a9f48091e7ad74e4db82258a9d4`

Consumed proof:
`C8_REPROOF_AFTER_DTW53_20260808`

Approved immutable proof HEAD:
`ee32b325f96c672e21247ac43395290931781da5`

Frozen artifact:
- Actions run `31231155572`
- job `93035124603`
- artifact ID `9014056017`
- ZIP SHA-256 `0022488af2c99d3ba36c205af3b19fae689af762ddc2a7610a7b5cdf1a237bd3`
- frozen evidence SHA-256 `a016b9fe7d7a71f050b56e7f5473d6b1190444053df3305cd7027edc7f09c8a5`

## Verdict

`DTW55_AUDIT_CONFIRMS_INDEPENDENT_INSPECTOR_STRUCTURAL_PROJECTION_GAPS_DESIGN_REQUIRED`

The consumed controlling campaign is not the blocker. It reached `CAMPAIGN_PASS`, and the DTW-53 accounting repairs held.

The mandatory independent inspector failed first at:

`CURRENT_RUN_GRAPH_MISSING`

Read-only audit proves the current inspector has multiple structural projection assumptions that do not match the real durable C8 schema. Repairing only the first exception would be incomplete and would expose deterministic later failures.

No implementation, test repair, provider/network work, DB mutation, runtime, or proof rerun occurred in DTW-55.

## 1. Controlling campaign truth remains PASS

The consumed proof froze:

- campaign `20260808T005025Z-21b2b5c7cf1b-campaign`
- campaign run `20260808T005025Z-21b2b5c7cf1b-campaign-run`
- cycle `20260808T005025Z-21b2b5c7cf1b-cycle`
- factory run `5ad2b0e6-7d45-4ce1-9017-09f44c744695`
- `campaign_acceptance_verdict = CAMPAIGN_PASS`
- `owner_action_local_equal_non_vacuous = true`
- `reservation_attempt_outcomes_complete = true`
- two terminal campaign-owned `WINDOW_15M` windows
- two clean promoted episodes and two fingerprint rows
- network attempts 0
- report-only replay zero-work
- DB integrity `ok`, FK 0
- protected capability deltas 0
- longer-window counts 0

DTW-55 therefore audits only the independent reconstruction layer. It does not reopen or reinterpret the controlling campaign result.

## 2. Defect A — campaign-run identity is used as factory-run identity

Current inspector flow reads top-level frozen `run_id`, which is the campaign-run identity, then directly queries `printer_memory_factory_run_steps.run_id` with it.

Real durable schema separates these identities:

`printer_memory_factory_campaign_runs`

- `run_id = 20260808T005025Z-21b2b5c7cf1b-campaign-run`
- `authoritative_run_id = 5ad2b0e6-7d45-4ce1-9017-09f44c744695`
- exactly one matching campaign-run binding exists

`printer_memory_factory_run_steps`

- 0 rows for the campaign-run ID
- 18 rows for factory run `5ad2b0e6-7d45-4ce1-9017-09f44c744695`

The first observed exception is therefore a projection bug, not a missing run graph.

Required design invariant:

1. resolve exactly one current campaign-run row by exact `campaign_id + campaign_run_id`;
2. require one non-empty `authoritative_run_id`;
3. require exactly one matching `printer_memory_factory_runs` row;
4. use only that resolved factory-run identity for factory run steps;
5. fail closed on missing, duplicate, conflicting, or drifted bindings;
6. never infer one identity from the shape of the other.

## 3. Defect B — graph reconstruction starts from factory steps instead of campaign-owned windows

The original C8 design requires the independent inspector to prove the exact campaign/run/cycle/configuration/factory graph and exactly two campaign-owned terminal 15m windows with memory-window linkage.

The current inspector instead starts its window projection from factory run steps.

The frozen DB has the stronger canonical campaign-owned surface already available:

`printer_memory_factory_campaign_windows`

Exactly two current rows exist and both bind:

- exact campaign ID;
- exact campaign-run ID;
- exact cycle ID;
- exact token-slot ID;
- `window_kind = WINDOW_15M`;
- `window_state = CLEAN_PROMOTED`;
- a concrete `memory_window_row_id`.

Required design direction:

- establish current campaign/cycle/configuration/run cardinality first;
- establish exactly two current token slots;
- use the two campaign-window rows as the ownership boundary;
- join their `memory_window_row_id` to the exact memory/episode/fingerprint graph;
- use factory run steps to corroborate lifecycle execution and close-step linkage, not as a substitute for campaign-window ownership.

## 4. Defect C — fingerprint validation requires a field that does not exist

Current `validate_checkpoint8_graph_projection()` requires a 64-character `fingerprint_sha256` per projected window.

Real `printer_memory_fingerprints` schema contains:

- `id`
- `episode_id`
- `fingerprint_kind`
- `fingerprint_payload_json`
- `memory_status`
- `data_quality_label`
- `do_not_train`
- `created_at`

There is no `fingerprint_sha256` or `memory_fingerprint_sha256` column, and the persisted fingerprint payload does not provide the synthetic SHA field expected by the inspector.

The consumed proof has exactly two real fingerprint rows, each linked to one clean episode.

The original C8 law requires both clean episodes to **have fingerprints**. It does not require a nonexistent fingerprint SHA column.

Required design invariant:

- prove fingerprint existence and uniqueness through durable linkage:
  `campaign window -> memory_window_row_id -> clean episode -> fingerprint episode_id`;
- require the expected clean fingerprint state/type/quality according to the canonical schema;
- do not synthesize a hash or weaken the one-fingerprint-per-clean-episode requirement.

## 5. Defect D — governance projection searches for owner-name strings not persisted by these tables

Current inspector loads campaign supervision, campaign Scheduler work, Scheduler jobs, and discovery work, then searches arbitrary row values for literal normalized strings matching `Source Governor` and `Central Scheduler`.

Read-only inspection of the frozen DB shows those literal owner labels are not persisted in those tables.

This makes the current owner-name heuristic schema-incompatible.

There is a second Scheduler-specific defect: `printer_scheduler_jobs` has no `campaign_id`, `run_id`, or `campaign_run_id` columns, so the generic `_rows_for_identity()` helper returns no Scheduler rows.

The exact campaign Scheduler relationship is already durable:

`printer_memory_factory_campaign_scheduler_work.scheduler_job_id`
`-> printer_scheduler_jobs.id`

The consumed proof has 28 campaign Scheduler ownership rows and 28 exact joined Scheduler rows.

Required design direction for Central Scheduler evidence:

- scope `printer_memory_factory_campaign_scheduler_work` by exact campaign/run/cycle;
- require the expected ownership contract/version;
- join each non-null `scheduler_job_id` to `printer_scheduler_jobs.id`;
- derive terminal/locked/retry truth from those exact joined rows;
- fail closed on missing, duplicate, extra-attributed, ambiguous, or nonterminal correspondence;
- do not scan all Scheduler jobs or infer ownership from strings.

Required design direction for Source Governor evidence:

- do not search unrelated rows for a human-readable owner label;
- use the authoritative governed source-request/response/failure/accounting relationships already persisted by the campaign/source pipeline;
- design must identify the exact durable source-governance correspondence before implementation and preserve the existing Source Governor law rather than inventing a new owner marker.

## 6. Defect E — report/replay identity validation expects noncanonical packaging fields

Current validator requires campaign/run identity in:

- top-level frozen summary;
- terminal/report packaging;
- top-level `report_only.campaign_id` and `report_only.run_id`.

The real frozen result carries identity differently:

- frozen summary top-level campaign/run: present;
- terminal top-level campaign/run: present;
- terminal `report.campaign_id`: present;
- terminal `report.run_id`: absent;
- top-level `report_only.campaign_id`: absent;
- top-level `report_only.run_id`: absent;
- `report_only.requested_identity`: exact campaign/run present;
- `report_only.full_run_terminal_evidence.identity`: exact campaign ID, campaign-run ID, cycle, configuration, factory-run, execution and supervision IDs present;
- nested replay full-run terminal evidence carries the same exact identity graph.

The current test fixture fabricated the missing top-level fields, so it did not exercise the canonical public result shape.

Required design invariant:

- validate identity parity only across canonical carriers that the public report/replay contract actually owns;
- compare exact campaign-run and factory-run identities without collapsing them;
- fail closed on missing/conflicting canonical identity carriers;
- do not add duplicate packaging fields merely to satisfy the inspector.

## 7. Existing independent-inspection tests did not model the real C8 schema

Two original test modules were reviewed:

- `tests/test_v2_9_8b_window_15m_checkpoint8_independent_inspection_completion.py`
- `tests/test_v2_9_8b_window_15m_checkpoint8_independent_inspection_integration.py`

The completion fixture simplifies several contracts in ways the real proof does not:

- one flat `run-c8` identity is used instead of distinct campaign-run/factory-run identities;
- projected windows contain synthetic `fingerprint_sha256` fields;
- governance projection is supplied with literal `Source Governor` / `Central Scheduler` strings;
- terminal/report/replay payloads are supplied with top-level run/campaign fields absent from the real public result.

The integration test does not construct a representative successful durable graph. Its DB derivation test applies migrations to an empty DB, checks that certain source-code strings exist, and expects `CURRENT_RUN_GRAPH_MISSING`.

Therefore the previous GREEN suite proved helper behavior against synthetic projections, but did not prove compatibility with the actual successful C8 persistence graph.

## 8. Minimum safe design scope

A later design lane should remain inspector-only unless static design evidence proves another file is necessary.

It must specify one coherent independent reconstruction pipeline:

1. frozen campaign/run identity validation;
2. exact campaign-run -> authoritative factory-run binding;
3. exact configuration/cycle/token-slot cardinality;
4. exact two campaign-owned `WINDOW_15M` rows;
5. exact memory-window -> clean episode -> fingerprint linkage;
6. factory-run step corroboration using the resolved factory UUID;
7. exact campaign Scheduler-work -> Scheduler-job joins;
8. durable Source Governor/source-accounting reconstruction from authoritative source relationships, with no owner-name heuristic;
9. canonical terminal/report/report-only/replay identity parity;
10. existing frozen safety, DB integrity, zero-delta, no-reuse and no-longer-window checks;
11. independent artifact written only after every reconstructed fact passes.

The design must keep the independent inspector independent: no call to `run_operational_campaign()`, no `report_only()` execution, no provider/source work, and no acceptance of the controlling runner's final booleans as substitutes for reconstruction.

## 9. Required future proof/testing pattern

DTW-55 does not authorize these steps, but the next approved repair program should follow:

1. design/specification;
2. deterministic RED using a representative DB fixture with distinct campaign/factory IDs and canonical real schemas;
3. minimal inspector/test implementation;
4. focused GREEN for all discovered projection classes;
5. read-only regression against a copied/frozen DTW-54 artifact if the test harness can do so without mutating the consumed evidence;
6. closeout;
7. independent readiness review;
8. only then may a new one-shot C8 authorization be requested.

No future test should pass only by fabricating fields the canonical DB/report schema does not own.

## Money-usefulness contribution

The controlling campaign now proves Printer can complete and accept a clean two-token 15m composition. The remaining value of C8 is independent trust: another reader must be able to reconstruct that success from durable evidence without relying on the campaign's own PASS booleans.

Repairing the inspector correctly will reduce false blockers and, more importantly, prevent a false independent PASS caused by guessed identities or synthetic evidence. That protects the integrity of the clean-memory foundation needed before later paper-only decision work.

## What this audit improves

- identifies the first blocker as an inspector identity-projection defect;
- proves the durable run graph is present;
- exposes the deterministic downstream inspector defects before another proof is attempted;
- explains why the prior synthetic tests missed them;
- defines the bounded surface a design must address together.

## What this audit still does not unlock

- inspector implementation;
- test changes;
- another C8 proof;
- operational WINDOW_15M activation;
- WINDOW_1H/4H/12H/24H;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- source/provider/network work;
- authoritative DB mutation;
- live wallet/private keys/signing/real funds;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Why it matters | Required mitigation before implementation |
|---|---|---|
| Fixing only campaign-run -> factory-run | Later deterministic inspector failures remain and could consume another proof | Design all discovered projection classes together |
| Ambiguous campaign/factory binding | Could inspect the wrong factory graph | Exact-one cardinality and conflict checks |
| Using factory steps as ownership truth | Could accept unrelated windows | Start from exact campaign-owned window rows and corroborate with factory steps |
| Synthetic fingerprint hashes | Could claim fingerprint evidence the DB never stored | Validate actual episode/fingerprint linkage and canonical fields |
| Owner-name string heuristics | Could fail valid runs or pass accidental text | Use durable Source Governor/Scheduler relationships |
| Unscoped Scheduler reads | Could hide active/locked unrelated or misattributed work | Exact campaign-work -> scheduler-job joins |
| Fabricated report/replay identity fields | Tests can pass while public shape fails | Test canonical public result carriers exactly |
| Reusing consumed DTW-54 proof as runtime input | Violates one-shot history | Frozen artifact is read-only evidence only |

## Stop condition / next lane

DTW-55 stops at audit.

Next lawful lane: **design/specification only** for the complete independent-inspector reconstruction repair.

No new C8 proof authorization should be requested until that design is implemented, deterministically verified, closed out, and independently reviewed for readiness.
