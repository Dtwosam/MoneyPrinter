# Printer V1 V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit

Date: 2026-08-01

Lane:
`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

Type: audit-only.

Starting HEAD:
`daa27aca4ef5938423ceff98de39f5cc50982251`

Ending HEAD: the documentation-only commit containing this audit; reported in the final handoff.

## Verdict

`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_BLOCKED`

Block class:

`BLOCKED_AUTHORITATIVE_MIGRATION_050_NOT_APPLIED`

The repaired C1-C15 code path is statically ready, and the authoritative database is internally healthy and free of active operational residue. The authoritative database is not campaign-ready because its applied migration ledger ends at `049_candidate_acquisition_integration.sql`, while the repository canonical ledger ends at `050_campaign_scheduler_ownership_scope.sql`.

The active repaired path reads stage-scoped Scheduler ownership fields introduced by migration 050. The authoritative table still has the pre-050 window-bound shape and lacks the required V2 ownership-contract, stage, scope, target, and factory-run fields. A campaign must not be attempted against this schema.

This audit did not apply migration 050, execute a campaign, contact a provider, run discovery or Scheduler runtime, generate memory, or unlock retrieval or financial capabilities.

## Scope and method

The audit used:

- static inspection of the active public `WINDOW_15M` command path and repaired C1-C15 acceptance/replay surfaces;
- an operator-run local evidence collector against the exact audit branch and starting HEAD;
- SQLite URI `mode=ro` with `PRAGMA query_only=ON`;
- before/after SHA-256, size, and modification-time checks for the authoritative DB and possible SQLite sidecars;
- existing artifact and terminal-summary inspection;
- redacted local configuration-presence and URL-structure checks.

No application command was executed. No repository tests were run. No migration, provider, RPC, WebSocket, source fetch, discovery run, campaign, report-only application command, memory generation, or database mutation occurred.

## Git and launch provenance

Local evidence reported:

- branch: `agent/v2-9-8b-post-accounting-repair-window-15m-readiness-audit`;
- HEAD: `daa27aca4ef5938423ceff98de39f5cc50982251`;
- exact branch match: true;
- exact HEAD match: true;
- tracked worktree clean: true;
- untracked paths: zero.

Status: `READY`.

## Static command-path readiness

Static inspection confirms:

- the ordinary public campaign entry point requires explicit operator approval;
- the ordinary policy is fixed to token capacity 2 and main window `WINDOW_15M`;
- the ordinary policy keeps `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` locked;
- authorization marker construction and canonical digest persistence occur before accountable campaign work;
- one campaign-supervision owner and exact lease path are acquired;
- Source Governor and Central Scheduler ownership checks fail closed;
- the coordinator creates one full-run accounting owner and independent action-local ledger before accountable work;
- C1-C15 acceptance is on the active finalization path;
- unified cleanup and durable lease evidence precede Campaign PASS;
- exact report-only replay uses the repaired marker, cleanup, factory-config, Scheduler-ownership, hash, and acceptance reconstruction contract;
- automatic campaign retries, restarts, resumes, and successors remain forbidden;
- retrieval and financial capabilities remain locked.

The separate selective-1h command surface exists historically but is not authorized by this lane. Any future authorization must pin the ordinary `run` mode and `WINDOW_15M` policy only.

Status: `READY`.

## Authoritative file immutability

Authoritative DB:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`;
- size before and after: `65,654,784` bytes;
- mtime before and after: `1785510479935495533` ns;
- SHA-256 before and after: `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`.

Sidecars before and after:

- `printer_v1.sqlite3-wal`: absent;
- `printer_v1.sqlite3-shm`: absent;
- `printer_v1.sqlite3-journal`: absent.

Collector results:

- SQLite query-only value: `1`;
- connection total changes: `0`;
- authoritative files unchanged: true;
- sidecar set unchanged: true;
- network calls: `0`;
- application commands: `0`;
- migrations applied: `0`.

Status: `READY`.

## Database integrity and residue

Read-only checks reported:

- `PRAGMA integrity_check`: `ok`;
- `PRAGMA foreign_key_check`: zero rows;
- active campaigns: `0`;
- active campaign runs: `0`;
- active campaign supervision: `0`;
- active campaign Scheduler work: `0`;
- active Scheduler jobs: `0`;
- locked Scheduler jobs: `0`;
- active discovery work: `0`;
- active factory steps: `0`;
- active proof supervision: `0`.

All inspected supervision rows are terminal, carry cleanup and lease-release timestamps, and have no remaining lease-lock file. Existing Scheduler history includes succeeded, failed, and cancelled terminal rows; none is active or locked. Historical retry-count values do not represent an active automatic campaign retry or successor and remain historical evidence only.

Status: `READY`.

## Migration and schema readiness

Applied migration ledger:

- applied count: `49`;
- latest applied: `049_candidate_acquisition_integration.sql`.

Repository canonical ledger:

- canonical count: `50`;
- latest canonical: `050_campaign_scheduler_ownership_scope.sql`.

Result:

- exact ledger match: false;
- migration 050 applied: false.

The authoritative `printer_memory_factory_campaign_scheduler_work` table still exposes the pre-050 columns:

- `scheduler_work_id`;
- campaign/run/cycle identity;
- mandatory token-slot/window identity;
- work intent/state and Scheduler/source linkage;
- terminal cause and timestamps.

It does not expose the V2 stage-scoped fields required by the repaired code and conformance contract:

- `ownership_contract_version`;
- `stage_id`;
- `work_scope`;
- `target_category`;
- `target_identity`;
- `factory_run_id`.

The table currently contains no campaign Scheduler ownership rows, so no existing ownership row needs automatic repair. That does not permit bypassing migration 050. The canonical ledger mismatch causes the operational preflight to fail closed and prevents the C1-C15 V2 stage-scoped ownership path from running safely.

Status: `BLOCKED`.

## Existing artifact readiness

The artifact root exists and the collector reviewed 38 JSON artifacts. All collected files parsed as JSON. Existing campaign reports are terminal historical `PILOT_CAMPAIGN_TERMINAL` artifacts. Terminal summaries preserve their historical outcomes, including honest supply blockers, safe stops, prior persistence/lease faults, and the July 31 accounting blocker.

The July 31 first authoritative attempt remains historical and unrepaired:

- execution: `20260731T002406Z-7612696c7295`;
- accounting status: `SIX_UNIT_ACCOUNTING_BLOCKED`;
- report written: false;
- report block reason: `SIX_UNIT_EVIDENCE_MISSING`.

The later July 31 historical successful terminal artifact predates the repaired C1-C15 evidence contract. No historical artifact is treated as repaired V2 proof, and no artifact implies retrieval or financial activation.

Existing authoritative configurations consistently show token capacity 2, `WINDOW_15M`, and zero automatic retries. Later configurations keep `WINDOW_1H` and longer windows locked.

Status: `READY` for historical preservation; `NOT_APPLICABLE` as repaired C1-C15 proof.

## Local configuration readiness

Safe redacted checks reported:

- `PRINTER_SOLANA_RPC_URL`: set, non-placeholder, valid HTTPS structure;
- redacted hostname: `solana-mainnet.g.alchemy.com`;
- URL userinfo: absent;
- URL fragment: absent;
- `PRINTER_HELIUS_API_KEY`: set, non-placeholder;
- `SOLANA_TRACKER_API_KEY`: set, non-placeholder;
- official public RPC fallback remains available by static contract;
- no paid API dependency is required;
- no endpoint was contacted.

Status: `READY`.

## Memory and locked-capability state

Current memory evidence remains `WINDOW_15M`-centered:

- 3 `CLEAN_MEMORY` / `CLEAN_DATA` windows;
- 7 `PARTIAL_MEMORY` / `CLEAN_DATA` windows;
- 136 dirty `WINDOW_15M` rows marked `DO_NOT_TRAIN`;
- 14 audit-only `WINDOW_15M` rows marked `DO_NOT_TRAIN`;
- 2 support-only `WINDOW_5M_MICRO_EVENT` audit rows;
- 23 memory fingerprints.

Historical locked-capability baselines remain present:

- retrieval queries: 10;
- retrieval matches: 0;
- paper decisions: 2;
- paper decision audits: 0;
- paper audit reports: 1;
- paper quote evidence: 32;
- paper positions: 0;
- trade events: 0;
- trade audits: 0.

These historical rows are not activation. Positions, trades, and PnL remain absent, and this audit created zero deltas.

Status: `READY` for lock preservation.

## Readiness matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Git and launch provenance | READY | Exact branch/HEAD; clean tracked and untracked state |
| Static ordinary `WINDOW_15M` command path | READY | Two-token policy, operator approval, C1-C15 gate and repaired replay are wired |
| Source Governor and Central Scheduler ownership | READY | Fail-closed owner checks remain on the active path |
| Authoritative file immutability | READY | DB SHA/size/mtime identical; no sidecars created |
| Database integrity | READY | Integrity `ok`; zero FK violations |
| Active-work and lease residue | READY | Every active/locked count is zero; all lease files absent |
| Source configuration | READY | Redacted variables are present and structurally valid; no network call |
| Historical artifact preservation | READY | Existing artifacts retained as historical truth; no silent upgrade |
| Backup/rollback prerequisite | READY WITH LATER RECONFIRMATION | Existing command requires verified backup/restore; must be freshly reconfirmed immediately before migration application |
| C1-C15 static conformance | READY | Final independent review PASS at the starting HEAD |
| Canonical migration ledger | BLOCKED | Applied 49, canonical 50 |
| V2 stage-scoped Scheduler ownership schema | BLOCKED | Migration 050 absent; required columns/index/constraints unavailable |
| Authoritative campaign execution | NOT_APPLICABLE | Prohibited in this audit |
| Retrieval and financial capabilities | NOT_APPLICABLE | Remain locked |

A readiness PASS requires no required item to be blocked. Therefore this audit is BLOCKED.

## Required next action

Do not execute a campaign and do not run migration 050 directly from this audit.

The exact next permitted lane is:

`V2-9.8B Authoritative Migration 050 Application Design and Operator Runbook`

Type: design/specification only.

That lane must:

- use the already approved migration 050 implementation and disposable proof/closeout as inputs rather than redesigning the schema;
- define an authoritative pre-migration backup and rollback procedure;
- pin the exact migration/application commit and authoritative DB identity;
- repeat the duplicate Scheduler-job ownership invariant check immediately before application;
- require zero active/locked work and released leases;
- define pre/post ledger, schema, row-count, canonical-field equality, integrity, FK, DB-hash, and sidecar checks;
- authorize no campaign, provider call, source fetch, memory generation, retrieval, or financial capability;
- end in a separate final-authorization gate before any authoritative DB mutation.

After that design and final authorization, the migration application must be one bounded operator-approved database-maintenance action followed by a read-only post-migration proof and closeout. Only a clean migration closeout may return work to campaign readiness review.

## Money-usefulness contribution

This audit prevents a false authoritative Campaign PASS on a database that cannot yet store the repaired stage-scoped Scheduler ownership evidence. It protects future `WINDOW_15M` learning value by requiring the database to match the code and conformance contract before another campaign can create memory.

It makes no profit claim and unlocks no financial capability.

## What this audit improves

- independently proves the authoritative DB is healthy and residue-free;
- confirms all terminal leases are released;
- confirms local source configuration is structurally ready without exposing secrets;
- confirms the repaired static C1-C15 path is present;
- identifies one precise blocker instead of authorizing an unsafe campaign;
- preserves all historical artifacts and locked-capability baselines.

## What remains locked

- migration 050 application until its design and final-authorization gates pass;
- any authoritative `WINDOW_15M` campaign or bounded proof;
- provider, RPC, WebSocket, discovery, and Scheduler runtime;
- memory generation or promotion;
- `WINDOW_1H`, 4h, 12h, and 24h work;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper trade audits, and PnL;
- wallets, signing, private keys, real funds, and live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

## Proof still required

Before campaign readiness can pass:

1. authoritative migration 050 application design/operator runbook;
2. independent final authorization for the exact migration action;
3. fresh authoritative backup and rollback proof;
4. one bounded application of migration 050 only;
5. post-migration exact ledger/schema/row/integrity/FK/immutability proof;
6. migration closeout;
7. repeat post-migration authoritative `WINDOW_15M` campaign readiness audit;
8. later campaign design/final authorization if that repeat audit passes.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Effect | Required control |
| --- | --- | --- |
| Applying migration 050 without a fresh backup | A table rebuild could damage authoritative history | Exact backup hash, restore rehearsal evidence, and rollback runbook before mutation |
| Treating healthy integrity as schema readiness | The DB can be internally valid while incompatible with active code | Require exact canonical migration-ledger and schema match |
| Automatically upgrading historical V1 rows | Could create false repaired evidence | Preserve `V1_WINDOW_BOUND`; require new repaired rows to use `V2_STAGE_SCOPED` |
| Running a campaign before migration closeout | Active code would encounter missing stage-scoped ownership schema | Hard stop on any campaign/provider/runtime action |
| Applying migration and campaign in one lane | Removes the ability to isolate migration failure | Separate migration application, post-proof, closeout, and repeat readiness |
| Existing historical Scheduler retries | Could be confused with an active automatic campaign retry | Keep historical counts as evidence; require zero active/locked work at application time |
| Historical artifacts lack repaired C1-C15 evidence | They cannot prove current readiness | Never silently upgrade or replay them as repaired PASS |
| Environment can change after audit | Configuration or DB state may drift before application | Repeat redacted config and DB residue checks immediately before authorization |

## Final classification

Verdict:

`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_BLOCKED`

Blocker:

`BLOCKED_AUTHORITATIVE_MIGRATION_050_NOT_APPLIED`

Campaign execution and bounded proof remain prohibited.
