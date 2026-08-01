# Printer V1 V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Readiness Audit

Date: 2026-08-01

Lane:
`V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Readiness Audit`

Review type: independent read-only audit and documentation only.

## 1. Verdict

`V2_9_8B_POST_MIGRATION_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_PASS`

The authoritative Printer V1 database and the repaired ordinary two-token
`WINDOW_15M` campaign path are structurally ready to proceed to the separate
campaign final-authorization gate.

This PASS does not authorize or execute a campaign. It does not authorize source
fetching, discovery, Scheduler runtime, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, real
funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, vectors,
or any later memory window.

## 2. Controlling identities

| Item | Value |
| --- | --- |
| Repository | `Dtwosam/MoneyPrinter` |
| Audit branch | `agent/v2-9-8b-post-migration-window-15m-readiness-audit` |
| Audit starting HEAD | `fcef6ff55affaec6cc95326105300b6ffe2b59fe` |
| Migration-application closeout commit | `fcef6ff55affaec6cc95326105300b6ffe2b59fe` |
| Uploaded evidence SHA-256 | `7a3db962b2d99e83d7732da746a3fa5fb73ea4d03434c4a6be9305ae5a1dd5f5` |
| Uploaded evidence size | `70281` bytes |
| Evidence collector status | `V2_9_8B_POST_MIGRATION_AUTHORITATIVE_WINDOW_15M_READINESS_EVIDENCE_READY` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Authoritative database | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Authoritative post-050 SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| Authoritative post-050 size | `65671168` bytes |
| Migration count and tip | `50 / 050_campaign_scheduler_ownership_scope.sql` |
| Migration 050 Git blob SHA | `3a5bf6de05deb202316b6689a2d7f4206359e6e9` |

The audit ran from the exact expected branch and HEAD with a clean tracked
worktree. No protected untracked migration, source, or test file existed.

## 3. Audit methods

The audit used only:

- static repository inspection;
- SQLite URI `mode=ro` access;
- `PRAGMA query_only=ON`;
- integrity and foreign-key checks;
- read-only schema, ledger, index, trigger, row-count, supervision, lease, and
  residue inspection;
- immutable local migration-application package inspection;
- a deterministic zero-I/O source-contract preflight;
- configuration presence and structural-validity checks with secret redaction;
- before/after file metadata and SHA-256 comparison;
- process-list inspection for active Printer operational processes.

It did not run:

- providers, RPC calls, WebSockets, or source fetching;
- discovery or Central Scheduler runtime;
- campaign or report-only application commands;
- migration, `VACUUM`, checkpoint, or journal-mode mutation;
- memory generation or promotion;
- retrieval or paper decisions;
- BUY, SELL, HOLD, positions, trade events, audits, or PnL.

## 4. Non-controlling collector false blocker

The first helper invocation returned:

`MISSING_STATIC_MARKER:src/printer_v1/operator_cli/abstract_campaign_command.py:TOKEN_CAPACITY`

This was a collector ownership mistake, not a repository defect. The literal
`TOKEN_CAPACITY = 2` is owned by the public operational command. The abstract
command independently enforces the same law through:

`if command.token_capacity != 2`

The corrected read-only collector checked the actual ownership boundary and
passed. The first helper invocation made no database change, external request,
source fetch, Scheduler action, campaign action, or memory action. It is retained
as non-controlling audit history and creates no retry concern because the audit
was read-only.

## 5. Authoritative database immutability

The database identity before and after the controlling audit was identical:

| Field | Before | After |
| --- | --- | --- |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| Size | `65671168` | `65671168` |
| `mtime_ns` | `1785617072867102156` | `1785617072867102156` |

SQLite reported:

- `query_only = 1`;
- `total_changes_before = 0`;
- `total_changes_after = 0`;
- journal mode `delete`;
- no `-wal`, `-shm`, or `-journal` sidecar before or after.

Verdict: the readiness audit did not mutate the authoritative database.

## 6. Migration and schema readiness

The repository and authoritative database both contain exactly 50 canonical
migrations with exact tip:

`050_campaign_scheduler_ownership_scope.sql`

The authoritative ledger equals the complete canonical ordered migration list.
Migration 050 identity is unchanged:

- Git blob SHA: `3a5bf6de05deb202316b6689a2d7f4206359e6e9`;
- SHA-256: `230153ec73f94208ac733155aca3d9ec86bcc75e3f0891dc1a5502c2dfe1c254`.

Database health passed:

- integrity exactly `ok`;
- zero foreign-key violations;
- zero duplicate non-null Scheduler-job ownership rows;
- no `__v2_9_8b_050` replacement-table residue;
- no `_mig050_guard_*` residue.

## 7. Stage-scoped Scheduler ownership contract

The authoritative
`printer_memory_factory_campaign_scheduler_work` table contains the required
post-050 columns:

- `ownership_contract_version`;
- `stage_id`;
- `work_scope`;
- `target_category`;
- `target_identity`;
- `factory_run_id`;
- all preserved campaign, cycle, slot, window, Scheduler, source-provenance,
  status, terminal-cause, and timestamp fields.

The approved contract markers are present for:

- `V1_WINDOW_BOUND`;
- `V2_STAGE_SCOPED`;
- `DISCOVERY_SELECTION`;
- `FIRST_15M_HANDOFF`;
- `WINDOW_LIFECYCLE`;
- `TERMINAL_CLEANUP`.

Required indexes are present:

- `idx_campaign_work_owner`;
- `idx_campaign_work_scheduler_job_unique`;
- `idx_campaign_work_scope_stage`.

`idx_campaign_work_scheduler_job_unique` is confirmed unique and partial.

Required triggers are present:

- `printer_campaign_work_identity_immutable`;
- `printer_campaign_work_provenance_insert`.

The authoritative Scheduler-ownership table currently contains zero rows. That
is the correct pre-campaign state. Historical row-copy behavior remains supported
by the earlier accepted non-empty disposable migration proof; this audit does not
pretend the zero-row authoritative table independently reproves non-empty copy
behavior.

## 8. Operational residue and lease readiness

All active counts are zero:

| Surface | Active count |
| --- | ---: |
| Campaigns | 0 |
| Campaign runs | 0 |
| Campaign supervision | 0 |
| Campaign Scheduler work | 0 |
| Scheduler jobs | 0 |
| Discovery work | 0 |
| Factory run steps | 0 |
| Proof supervision | 0 |

Locked Scheduler jobs are zero.

Every inspected campaign-supervision row is terminal, has durable cleanup and
lease-release timestamps, and has no live lease-lock file. No stale or incomplete
lease row was found. Process inspection found no active Printer operational
process.

## 9. Protected data and capability counts

The following protected counts remain exactly equal to the migration-application
closeout baseline:

| Table | Count |
| --- | ---: |
| `printer_memory_windows` | 162 |
| `printer_episodes` | 59 |
| `printer_memory_retrieval_queries` | 10 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 2 |
| `printer_paper_decision_audits` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 1 |
| `printer_paper_quote_evidence` | 32 |
| `printer_scheduler_jobs` | 1365 |
| `printer_source_requests` | 1748 |
| `printer_source_responses` | 1609 |
| `printer_source_failures` | 139 |

The pre-existing retrieval-query, paper-decision, audit-report, and quote-evidence
rows are preserved historical records. Their unchanged presence is not retrieval
or paper-trading activation.

Positions, trade events, decision audits, trade audits, and retrieval matches
remain zero.

## 10. Migration package continuity

The exact migration execution package remains present under:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Required records are present:

- `preflight.json`;
- `backup_restore_preflight.json`;
- `rollback_rehearsal.json`;
- `preauthorization_evidence.json`;
- `final_authorization.json`;
- `application_started.json`;
- `application_stdout.txt`;
- `application_stderr.txt`;
- `post_migration_proof.json`;
- `closeout_inputs.json`.

The final authorization SHA-256 remains:

`eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835`

The application proof remains:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_APPLICATION_PROOF_PASS`

It records one migration invocation, no failures, no campaign authorization, and
no provider, RPC, WebSocket, discovery, Scheduler-runtime, memory-generation,
retrieval, or financial execution.

No authoritative `rollback.json` exists because rollback was not entered.

The verified pre-050 backup remains byte-identical:

- SHA-256:
  `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`;
- size: `65654784` bytes.

The one-shot migration marker remains controlling. Migration 050 must not be run
again.

## 11. Ordinary WINDOW_15M route readiness

Static inspection confirms the public ordinary route remains bounded to:

- exactly two token slots;
- main memory window `WINDOW_15M`;
- exact main-window duration 900 seconds;
- bounded command duration 1,200 seconds;
- zero automatic retries;
- ordinary mode `run`;
- selective-1h continuation disabled for the ordinary policy;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` locked;
- verified backup/restore preflight;
- complete source-contract preflight;
- Source Governor ownership;
- Central Scheduler ownership;
- exact canonical migration-ledger validation;
- locked-capability table accounting.

The abstract command independently requires token capacity exactly two and fails
closed if Source Governor or Central Scheduler ownership is unavailable. It
forbids successor creation and automatic restart.

The module's separate selective-1h proof surface is not authorized by this audit.
Any later final authorization must pin only the ordinary `run` route.

## 12. Zero-I/O source-contract readiness

The deterministic source-contract preflight returned:

- status `READY`;
- issues `[]`;
- external requests `0`;
- secret material recorded `false`;
- Source Governor owner `SOURCE_GOVERNOR`;
- Central Scheduler owner `CENTRAL_SCHEDULER`;
- direct source bypass `false`.

The configured Solana RPC was structurally valid HTTPS and was represented only
by a redacted endpoint identity. The operator-configured endpoint origin is:

`OPERATOR_CONFIGURED_APPROVED_HTTPS`

The optional Helius holder backup is present and redacted. No secret value is
stored in this audit.

Source contracts preserve:

- free-public compatibility for active mandatory dependencies;
- no wallet, private key, signing, funding, transaction submission, or execution
  endpoint;
- no paid dependency;
- zero automatic retries;
- no endpoint rotation;
- registered request-kind compatibility;
- Pump and PumpSwap program/IDL pins;
- 45-operation readiness ceiling;
- three-candidate readiness cap;
- six-operation snapshot reservation;
- worst-case total 43, within the ceiling;
- exact 900-second GeckoTerminal readiness provenance.

This is configuration and contract readiness only. It is not evidence that a
provider will respond successfully during a future campaign.

## 13. Readiness matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Exact audit branch and HEAD | PASS | Branch and HEAD match expected values |
| Clean tracked repository | PASS | No tracked changes; no protected untracked files |
| Canonical ledger 50/050 | PASS | Exact complete migration sequence |
| Migration 050 identity | PASS | Blob SHA and SHA-256 match |
| Database integrity | PASS | `ok` |
| Foreign-key integrity | PASS | 0 violations |
| Stage-scoped ownership schema | PASS | Columns, constraints, indexes, triggers present |
| Duplicate Scheduler-job ownership | PASS | 0 |
| Migration residue | PASS | None |
| Active operational residue | PASS | All active counts 0 |
| Locked Scheduler work | PASS | 0 |
| Lease cleanup/release | PASS | All terminal and released |
| Protected count equality | PASS | Exact baseline equality |
| Migration evidence continuity | PASS | Full immutable package present |
| Verified backup continuity | PASS | Exact pre-050 hash and size |
| Ordinary two-token 15m route | PASS | Static contract markers aligned |
| Source/Scheduler ownership | PASS | No bypass |
| Source configuration | PASS | Zero-I/O preflight `READY` |
| Paid/wallet/live capabilities | PASS locked | All prohibited |
| Database immutability during audit | PASS | Exact before/after equality |
| Campaign executed | NO | Explicitly not authorized or run |

## 14. Readiness conclusion

The migration blocker that caused the earlier post-accounting-repair readiness
audit to return BLOCKED is resolved.

The authoritative database now carries the exact canonical migration 050 schema
required by the repaired C1-C15 accounting and terminal-evidence implementation.
The ordinary two-token `WINDOW_15M` route, source contracts, Scheduler ownership,
residue state, protected counts, and migration evidence chain are aligned.

No remaining structural readiness blocker was found within this audit's approved
scope.

## 15. Money-usefulness contribution

This audit protects future paper-only money usefulness by ensuring the next
bounded campaign would record exact stage-scoped Scheduler ownership instead of
hidden, duplicated, or invented work relationships.

It also confirms that source evidence remains governed, memory and financial
history remains unchanged, and no readiness claim depends on a live wallet,
real funds, paid data, scoring, rankings, or profit assumptions.

It makes no profit claim and creates no trading signal.

## 16. What this lane improves

- closes the post-migration structural readiness gate;
- proves the authoritative schema is now compatible with the repaired C1-C15
  path;
- confirms the exact ordinary two-token `WINDOW_15M` route remains bounded;
- confirms Source Governor and Central Scheduler ownership;
- confirms source configuration is structurally usable without network access;
- confirms zero operational residue and released leases;
- preserves migration authorization, backup, application, proof, and closeout
  continuity;
- separates readiness from campaign authorization and execution.

## 17. What this lane still does not unlock

This PASS does not unlock:

- a campaign by itself;
- provider, RPC, WebSocket, source-fetching, discovery, Scheduler-runtime, or
  report-only execution;
- memory generation or promotion;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions;
- BUY, SELL, or HOLD;
- positions, trade events, paper trade audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors;
- V2-10.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot become an outcome memory
or unlock any later capability by itself.

## 18. Proof still required before completion of the next operational action

Before one ordinary campaign may run, a separate final-authorization review must
freshly bind:

1. the exact readiness-audit commit and PASS verdict;
2. the authoritative post-050 DB hash, size, mtime, ledger, schema, and zero
   residue;
3. the exact public ordinary `run` route, excluding selective-1h modes;
4. the existing campaign design and accepted C1-C15 implementation/proof chain;
5. valid redacted source configuration;
6. the exact two-token, 1,200-second, `WINDOW_15M` ceilings;
7. one campaign invocation only;
8. no retry, restart, resume, successor, or second invocation;
9. pre-run backup/restore identity and rollback/stop law;
10. immediate terminal closeout and independent post-run audit;
11. every retrieval and financial lock.

The final-authorization lane may inspect and write authorization documentation.
It may not run the campaign itself.

## 19. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current disposition | Required next control |
| --- | --- | --- |
| Zero authoritative Scheduler-ownership rows make historical copy proof vacuous | Accepted with earlier non-empty disposable proof | Preserve both evidence sources in final authorization and post-run review |
| Static readiness cannot prove provider availability | Known limitation | Final authorization binds configuration; future campaign must fail closed on source failure |
| Optional Helius key may later fail at transport time | Configuration is structurally valid only | No retry/rotation; candidate remains unknown or blocked |
| Public command also contains selective-1h proof modes | Ordinary route is distinct but adjacent | Final authorization must pin ordinary `run` only |
| Existing historical retrieval and paper rows could be mistaken for activation | Counts are unchanged historical records | Continue zero-delta and capability-lock checks |
| Migration package is local and untracked | Required for large backup preservation | Keep execution directory and hashes intact |
| First collector produced a false static-marker blocker | Corrected without DB or runtime action | Record V1 helper as non-controlling; use V2 evidence only |
| A readiness PASS could be mistaken for campaign permission | Campaign remains unauthorized | Separate final-authorization gate is mandatory |
| Provider failure could consume bounded source budget without useful memory | Runtime risk remains | Exact ceilings, honest terminal cause, no automatic retry |
| Campaign could produce dirty or no memory | Valid possible outcome | Do not equate clean execution with favorable market outcome or profit |
| A later command could drift from the audited commit | Readiness is commit-specific | Final authorization must pin exact commit and hashes |

## 20. Exact next permitted lane

`V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Final Authorization`

Type: independent final go/no-go inspection and documentation only.

The campaign design and repaired C1-C15 implementation/proof chain already exist.
The next lane must not repeat design or implementation. It must bind this
post-migration readiness PASS to one exact future ordinary `run` invocation.

It may not execute the campaign, call providers, run discovery or Scheduler
runtime, mutate the database, generate memory, or unlock retrieval or financial
capabilities.
