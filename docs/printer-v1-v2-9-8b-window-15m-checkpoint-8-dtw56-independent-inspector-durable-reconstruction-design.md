# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-56 Independent Inspector Durable Reconstruction Design

Date: 2026-08-08

Linear: `DTW-56`

Audit baseline: `ade95b48e6e49655278316e850d767513439b179`

Consumed controlling proof: `C8_REPROOF_AFTER_DTW53_20260808`

Approved proof HEAD: `ee32b325f96c672e21247ac43395290931781da5`

Actions run: `31231155572`

Audit verdict:

`DTW55_AUDIT_CONFIRMS_INDEPENDENT_INSPECTOR_STRUCTURAL_PROJECTION_GAPS_DESIGN_REQUIRED`

## Verdict

`DTW56_INDEPENDENT_INSPECTOR_DURABLE_RECONSTRUCTION_DESIGN_READY_FOR_RED`

This lane is design/specification only. It does not alter code, tests, the consumed proof, the disposable DB, the authoritative DB, runtime, Source Governor, Central Scheduler, memory promotion, retrieval, decisions, or paper trading.

The design replaces the independent inspector's synthetic flat-identity assumptions with one fail-closed reconstruction of the real persisted Checkpoint 8 graph.

## Goal

Make the mandatory Checkpoint 8 independent inspection able to verify a frozen successful disposable proof by independently traversing canonical persisted identity relationships instead of:

- treating campaign `run_id` as factory `run_id`;
- deep-searching arbitrary JSON for substitute identities;
- requiring non-existent fingerprint SHA columns;
- searching for literal owner-name strings;
- querying unscoped Scheduler jobs;
- assuming report-only fields that the public replay result does not expose.

The controlling campaign remains historical `CAMPAIGN_PASS`. This design does not retroactively declare Checkpoint 8 PASS.

## Active-source-stack alignment

This design preserves the active Printer V1 source stack and the V2 completion pattern:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout`.

It preserves all V1 locks: Solana-only, Solana-memecoin-only, paper-only, no wallet/private keys/real funds/live execution, no paid API dependency, no scoring/ranking/confidence/weighted logic, no embeddings/vectors, no Source Governor bypass, no Central Scheduler bypass, no dirty-memory decision support, and no retrieval/decision/trading unlock.

## Frozen proof facts the design must support

The consumed DTW-54 proof contains the following real persisted identities:

- campaign: `20260808T005025Z-21b2b5c7cf1b-campaign`;
- campaign run: `20260808T005025Z-21b2b5c7cf1b-campaign-run`;
- authoritative factory run: `5ad2b0e6-7d45-4ce1-9017-09f44c744695`;
- configuration: `20260808T005025Z-21b2b5c7cf1b-configuration`;
- cycle: `20260808T005025Z-21b2b5c7cf1b-cycle`;
- two campaign token slots;
- two campaign-owned `WINDOW_15M` rows;
- memory-window row ids `1` and `2`;
- exactly two clean promoted episodes;
- exactly two fingerprint rows;
- 18 factory run steps;
- 28 campaign Scheduler-work rows;
- 28 Scheduler jobs;
- 8 discovery-work rows;
- one terminal supervision row;
- one terminal canonical campaign-report row.

The campaign-run row contains the authoritative bridge:

`printer_memory_factory_campaign_runs.authoritative_run_id -> printer_memory_factory_runs.run_id`.

The inspector must use that bridge. It must never guess a factory run id from the campaign run id.

## 1. Immutable frozen-summary and DB-safety entry

Keep the existing frozen-summary hash verification and read-only disposable-DB opening model.

Before graph reconstruction:

1. recompute `frozen_evidence_sha256` from the unsigned summary;
2. require the proof DB path to be non-canonical;
3. open SQLite read-only;
4. verify exact canonical migration ledger;
5. run integrity/FK checks;
6. hash DB bytes before and after inspection and require no change.

No repair may weaken these checks.

## 2. Exact campaign-run -> factory-run resolution

Primary input identities are the frozen summary's exact `campaign_id` and campaign `run_id`.

Resolve the factory run only through canonical durable rows:

1. query `printer_memory_factory_campaign_runs` by exact `(campaign_id, run_id)`;
2. require exactly one row;
3. require non-empty `authoritative_run_id`;
4. query `printer_memory_factory_runs` by `run_id = authoritative_run_id`;
5. require exactly one row;
6. require no second campaign-run row for the same current proof identity with a conflicting authoritative run;
7. preserve the campaign-run identity and factory-run identity as separate named values throughout inspection.

Fail closed on zero, duplicate, null, or conflicting bindings.

Forbidden:

- campaign-run/factory-run string substitution;
- arbitrary JSON deep-search fallback;
- choosing the first row when cardinality is greater than one;
- treating a factory UUID as the public campaign run id.

## 3. Canonical campaign identity graph

From `(campaign_id, campaign_run_id)` require exact current-run ownership across:

- `printer_memory_factory_campaigns`;
- `printer_memory_factory_campaign_configurations`;
- `printer_memory_factory_campaign_runs`;
- `printer_memory_factory_campaign_cycles`;
- `printer_memory_factory_campaign_token_slots`;
- `printer_memory_factory_campaign_windows`;
- `printer_memory_factory_campaign_supervision`.

For the successful C8 shape require:

- exactly one campaign row;
- exactly one configuration row for the campaign;
- exactly one campaign run row;
- exactly one current cycle row;
- exactly two current token slots;
- exactly two current campaign windows;
- exactly one current supervision row;
- all campaign/run/cycle/configuration references mutually exact;
- two distinct token mints, token row ids, pair row ids, token slot ids, and campaign window ids;
- both campaign windows `window_kind=WINDOW_15M` and `support_only=0`;
- both campaign windows terminal and clean-promoted by the campaign owner.

No unrelated rows may satisfy current-run acceptance merely because they share a token or pair.

## 4. Memory-window -> episode -> fingerprint reconstruction

The independent clean-memory chain is:

`campaign window.memory_window_row_id`
`-> printer_memory_windows.id`
`-> printer_episodes.memory_window_id`
`-> printer_memory_fingerprints.episode_id`.

For each of the two campaign windows:

### Memory window

Require exactly one referenced `printer_memory_windows` row and exact token/pair/window-kind parity.

Require:

- `window_kind=WINDOW_15M`;
- `window_status=WINDOW_CLOSED`;
- `data_quality_label=CLEAN_DATA`;
- `do_not_train=0`;
- complete expected/actual coverage with zero missing snapshots.

Do **not** require the memory-window row itself to say `CLEAN_MEMORY`.

The frozen proof truthfully has `memory_status=PARTIAL_MEMORY` / `memory_quality_label=PARTIAL_MEMORY` at the E2Q window layer while E2Z creates a valid clean episode. The inspector must preserve that separation.

### Clean episode

Require exactly one qualifying episode for the referenced memory window:

- `episode_kind=WINDOW_15M_CLEAN_MEMORY`;
- `episode_status=COMPLETE`;
- `memory_status=CLEAN_MEMORY`;
- `memory_quality_label=CLEAN_MEMORY`;
- `data_quality_label=CLEAN_DATA`;
- `do_not_train=0`;
- exact token/pair/window-kind parity.

Zero or multiple qualifying episodes fail closed.

### Fingerprint

Require exactly one fingerprint row linked by `episode_id`.

Require:

- `fingerprint_kind=STATIC_CONDITION_SUMMARY`;
- `memory_status=CLEAN_MEMORY`;
- `data_quality_label=CLEAN_DATA`;
- `do_not_train=0`;
- valid JSON `fingerprint_payload_json`;
- payload `episode_id`, `window_id`, `token_id`, `pair_id`, and `window_kind` exactly match the joined episode/window.

Do not invent or require `fingerprint_sha256` / `memory_fingerprint_sha256` columns. They do not exist in the canonical table.

The fingerprint's durable existence and exact payload linkage are the acceptance evidence.

## 5. Factory-run-step corroboration

Only after resolving the authoritative factory UUID may the inspector query:

`printer_memory_factory_run_steps.run_id = factory_run_id`.

Require the current successful C8 lifecycle shape:

- exactly 18 current factory run steps;
- for each selected token/pair, exactly eight successful `SNAPSHOT` steps and one successful `WINDOW_CLOSE` step;
- every step token/pair identity belongs to one of the two current campaign slots;
- every `scheduler_job_id` is non-null and joins exactly one current campaign Scheduler-work row and exactly one Scheduler job;
- each close step's `memory_window_id` equals the corresponding campaign window's `memory_window_row_id`.

This is corroboration of the campaign-owned window graph; run steps are not the primary owner of campaign identity.

## 6. Central Scheduler reconstruction

Do not search rows for the string `Central Scheduler`.

The durable current-campaign Scheduler ownership boundary is `printer_memory_factory_campaign_scheduler_work`.

Reconstruct as follows:

1. query Scheduler-work rows by exact campaign/run/cycle;
2. require every row has a unique non-null `scheduler_job_id`;
3. join each id to exactly one `printer_scheduler_jobs.id`;
4. require the joined job set equals the current campaign Scheduler-work job-id set;
5. require all joined jobs terminal;
6. require no current joined job remains locked or active;
7. require `ownership_contract_version=V2_STAGE_SCOPED` for stage-scoped rows;
8. validate exact work families rather than owner-name text:
   - discovery/selection;
   - first-15m handoff;
   - window lifecycle.

For lifecycle work:

- `work_scope=WINDOW_LIFECYCLE`;
- `factory_run_id` must equal the resolved factory UUID;
- Scheduler job ids must equal the factory-run-step Scheduler ids;
- each work row's source request/response linkage must be internally exact where populated.

For discovery work:

- join `printer_discovery_work.scheduler_job_id` to its campaign Scheduler-work row and Scheduler job;
- require exact campaign/run/cycle identity and terminal state.

Do not query `printer_scheduler_jobs` with campaign/run filters it does not have.

## 7. Source Governor / source-accounting reconstruction

Do not search for the literal string `Source Governor`.

Independent Source Governor evidence is reconstructed from durable governed-source accounting surfaces.

### Canonical report evidence

Load exactly one current terminal `printer_memory_factory_campaign_reports` row for the campaign/configuration.

Recompute:

`sha256(report_json UTF-8 bytes) == report_hash`.

Parse the report only after this hash passes.

From `full_run_terminal_evidence.full_run_accounting` independently recompute rather than trusting stored PASS booleans:

- owner source-transport identity set;
- action-local source-transport identity set;
- exact equality and non-vacuity;
- unique scheduler-work identity set;
- unique local-validation identity set;
- unique lifecycle-reservation identity set;
- all required governed request kinds / stage identities are non-empty;
- no duplicate identity keys.

Every source transport must carry a non-empty `governed_request_kind`, `source_name`, stage, target category/identity, ordinal, and result.

This proves governed source-accounting structure without owner-name heuristics.

### DB source linkage

Independently validate persisted source rows reachable from current campaign work:

- lifecycle `campaign_scheduler_work.source_request_id/source_response_id` -> exact `printer_source_requests` / `printer_source_responses` rows;
- discovery `printer_discovery_work_source_links` -> exact source request/response/failure rows;
- response row `source_request_id` must match the linked request id;
- source names must agree where both sides persist them;
- no linked current-campaign source failure may be silently ignored.

The report identity sets and DB source rows are complementary evidence. Neither may replace the other with a literal owner label.

## 8. Supervision, cleanup, and residue reconstruction

Use the exact current supervision row, not text search.

Require:

- `supervision_state=TERMINAL`;
- `terminal_status=COMPLETED`;
- non-null `cleanup_completed_at`;
- non-null `lease_released_at`;
- exact campaign/run/configuration identity;
- no additional conflicting current-run supervision row.

Use current campaign Scheduler-work, discovery-work, joined Scheduler jobs, and resolved factory run steps to independently count active/locked/orphan work.

Require zero active current work after cleanup.

Lease-file absence remains checked from the frozen artifact path where applicable.

No restart/resume/successor fact may be inferred from missing text. Use explicit frozen-summary/report fields plus durable current-run rows and require all relevant values false/zero.

## 9. Canonical report and artifact parity

The independent inspector must verify the terminal report without trusting its final booleans.

Require:

1. exactly one current terminal campaign-report DB row;
2. exact campaign/configuration identity;
3. `report_state=REPORT_TERMINAL`;
4. recomputed `report_hash` equals SHA-256 of `report_json` bytes;
5. exactly one `.campaign-report.json` artifact beneath the frozen proof artifact root for the current execution;
6. artifact bytes exactly equal `report_json` bytes;
7. artifact SHA-256 equals `report_hash`;
8. parsed report identity contains exact campaign, campaign-run, cycle, configuration, factory-run, execution, and supervision ids previously reconstructed independently.

Stored report acceptance booleans may be compared for parity only after independent graph/accounting reconstruction succeeds.

## 10. Canonical report-only replay parity

The public replay result's real identity carrier is:

`report_only.requested_identity`.

Do not require fabricated top-level `campaign_id` or `run_id` fields.

Require:

- `status=REPLAYED`;
- `mode=REPORT_ONLY`;
- `requested_identity.campaign_id == campaign_id`;
- `requested_identity.run_id == campaign_run_id`;
- zero `source_calls`;
- zero `scheduler_runtime_calls`;
- zero `database_writes`;
- zero replay-new source/Scheduler calls;
- replay `full_run_terminal_evidence.identity` matches the independently reconstructed identity graph;
- replay fixture/proof identity inside `full_run_terminal_evidence.authorization_and_invocation` matches the frozen proof id and manifest.

The inspector must not call `report_only()` again.

## 11. Frozen safety and downstream locks

Keep independent zero-network and downstream lock checks.

Require:

- controlling campaign `CAMPAIGN_PASS`;
- `network_attempt_count=0`;
- positive fixture transport operation count;
- replay zero-work;
- protected-capability DB deltas all zero;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` absent;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallet/private-key/signing/real-fund capability.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot satisfy the two main-window acceptance requirement.

## 12. Representative deterministic RED fixture

The next lane must first create a RED fixture that mirrors the real C8 schema rather than the previous synthetic inspector fixtures.

Minimum representative fixture:

- distinct campaign run id and factory UUID;
- one exact campaign-run row with `authoritative_run_id` bridge;
- one campaign/configuration/cycle/supervision graph;
- two token slots;
- two campaign-owned 15m windows;
- two memory windows whose window-layer memory label may be `PARTIAL_MEMORY` but data quality/coverage are valid;
- two exact clean episodes;
- two exact fingerprint rows using `fingerprint_payload_json`, no SHA column;
- 18 factory run steps keyed by factory UUID;
- 28 campaign Scheduler-work rows and 28 joined Scheduler jobs;
- representative discovery-work/source links and lifecycle source request/response links;
- one terminal report row with valid hash plus byte-identical artifact;
- report-only payload using `requested_identity`, not fabricated top-level ids.

RED must prove the current inspector fails the representative valid graph for the known structural reasons.

Required negative RED cases:

1. zero/multiple campaign->factory binding blocks;
2. conflicting authoritative factory id blocks;
3. campaign window -> memory window mismatch blocks;
4. zero/multiple clean episodes blocks;
5. fingerprint payload identity mismatch blocks;
6. missing/duplicate Scheduler join blocks;
7. lifecycle Scheduler-work factory UUID mismatch blocks;
8. unlinked/mismatched source request-response blocks;
9. report hash/artifact byte mismatch blocks;
10. replay requested-identity mismatch blocks.

## 13. Minimum implementation surface after valid RED

If RED confirms the design, the implementation should remain inspector/test scoped unless evidence proves otherwise.

Expected files:

- `scripts/v2_9_8b_checkpoint8_independent_inspection.py`;
- `tests/test_v2_9_8b_window_15m_checkpoint8_independent_inspection_completion.py`;
- `tests/test_v2_9_8b_window_15m_checkpoint8_independent_inspection_integration.py`;
- optionally one new narrowly named representative-schema regression test file if keeping the existing synthetic unit tests separate is clearer.

No production runtime file is currently justified by DTW-55 evidence.

If RED demonstrates a production persistence gap instead, stop and re-audit before expanding scope.

## 14. Focused GREEN requirement

After implementation, minimum sufficient GREEN must prove:

- representative real-schema success fixture passes full inspector orchestration;
- all ten negative cases fail closed;
- existing frozen-summary hash/DB read-only safety tests remain green;
- inspector contains no operational campaign call and no report-only call;
- exact code/test scope and `git diff --check` pass;
- Python compile passes;
- nearest affected Checkpoint 8 independent-inspection tests pass.

Do not run a broad repository suite unless the implementation becomes unexpectedly cross-cutting or the later major closeout requires it.

## 15. Proof / closeout sequence

DTW-56 itself stops after design.

Later sequence:

1. deterministic RED against this design;
2. minimum inspector/test implementation;
3. focused GREEN;
4. implementation closeout;
5. independent readiness review;
6. only then may a new explicit one-shot C8 authorization be requested;
7. no proof may be launched automatically from the repair/readiness verdict.

The consumed DTW-54 proof remains immutable historical evidence and must not be rewritten or rerun.

## Money-usefulness contribution

This design makes the final memory-growth acceptance gate inspect what Printer actually persisted. It prevents a false failure caused by identity/schema assumptions while also preventing a false PASS produced by synthetic owner names, guessed run ids, fabricated fingerprint hashes, or unscoped Scheduler rows.

That improves confidence that a future accepted 15m memory-growth proof represents two genuinely clean, traceable, independently verifiable Solana memecoin memories.

## What this lane improves

- exact campaign/factory identity separation;
- campaign-owned memory reconstruction;
- clean episode/fingerprint truth;
- Scheduler ownership reconstruction;
- Source Governor/source-accounting verification;
- report/artifact/replay parity;
- representative inspector test realism.

## What this lane still does not unlock

- another Checkpoint 8 proof;
- operational `WINDOW_15M` activation outside an explicitly approved lane;
- `WINDOW_1H/4H/12H/24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet/private keys/signing/live execution/real funds;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Repairing only `CURRENT_RUN_GRAPH_MISSING` would expose later deterministic inspector failures and risk wasting another single-use proof.
- Over-broad JSON deep search could accidentally accept an unrelated historical identity.
- Requiring `CLEAN_MEMORY` on the memory-window row would incorrectly reject the valid E2Q -> E2Z promotion model.
- Owner-name string matching is not durable evidence and can generate both false PASS and false FAIL.
- Scheduler jobs cannot be scoped directly by campaign/run columns they do not possess; campaign Scheduler-work must own the join.
- A representative RED fixture is mandatory because the previous synthetic tests did not model the real persisted schema.
- If implementation needs production persistence changes, this design is no longer sufficient; stop and return to audit/design before touching runtime.

## Stop condition

DTW-56 is complete when this design is committed and independently scope-checked as documentation-only.

Do not add tests or implementation in the DTW-56 commit.

Next permitted gate: deterministic RED for the representative durable reconstruction contract.