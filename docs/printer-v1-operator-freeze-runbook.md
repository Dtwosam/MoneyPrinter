# Printer V1 Operator Freeze Runbook

## 1. Purpose

This document freezes the safe operator procedure after Phase 21 and before Phase 23.

Printer V1 is structurally built and operator-controllable. It has a schema-only persistent local database, one-shot operator commands, synthetic validation, reporting, hardening checks, and a completed future build order anchor.

Printer has not started real Solana memecoin learning.

Printer has not started runtime.

Printer has not started memory generation.

Printer has not started paper trading.

This runbook exists to stop drift before real source work begins. It defines what the operator must check before and after future phases, what is allowed during the freeze, when DB backups are required, what commands are safe, and what conditions require an immediate stop.

## 2. Current Frozen State

Current repo and checkpoint state:

* Phase 0-20 checkpoint complete and tagged: `printer-v1-synthetic-checkpoint`
* Phase 21 operator CLI complete and tagged: `printer-v1-phase21-operator-cli`
* Future Build Order Anchor committed and tagged: `printer-v1-future-build-order-anchor`
* Latest commit: `ce3b67e Add future build order anchor`
* Working tree clean
* Persistent DB exists at `data/printer_v1.sqlite3`

Expected safe early DB and readiness state:

* readiness_label: `READY_SCHEMA_ONLY`
* DB state: `PERSISTENT_DB_EMPTY_SCHEMA_ONLY`
* migrations applied: 20
* real token rows: 0
* real source rows: 0
* real snapshot rows: 0
* real memory rows: 0
* real paper decision rows: 0
* real paper position rows: 0
* `memory_has_started`: false
* `paper_trading_has_started`: false
* `runtime_has_started`: false
* `source_scan_result`: `VALIDATION_PASS`
* `runtime_scan_result`: `VALIDATION_PASS`

This is the correct frozen state before Phase 23. Schema exists, operator commands work, and Printer remains inert with no real operational data.

## 3. Phase 22B Scope

Phase 22B is documentation-only.

Allowed:

* operator runbook text
* readiness policy text
* DB backup/checkpoint policy text
* rollback policy text
* source-limit policy text
* stop-condition policy text
* phase acceptance checklist

Not allowed:

* code
* migrations
* tests
* adapters
* live fetches
* runtime
* scheduler execution
* memory
* paper decisions
* paper positions

Phase 22B must not change source code, migration files, test files, runtime behavior, source adapter behavior, scheduler behavior, memory behavior, paper-decision behavior, or paper-position behavior.

## 4. Pre-Phase Operator Checks

Before any future phase after Phase 22B, the operator must run read-only/operator checks and confirm the phase starts from a known state.

Allowed read-only/operator checks:

* `printer-readiness-check`
* `printer-db-status`
* `printer-db-counts`
* `printer-migration-status`
* `printer-operator-report`
* `printer-synthetic-validation`

Git checks:

* `git status`
* `git log --oneline -5`
* `git tag --list "printer-v1-*"`

Expected pre-phase results:

* working tree clean before starting a new phase
* latest committed state known
* current checkpoint/tag known
* DB remains schema-only before Phase 23
* `readiness_label` remains `READY_SCHEMA_ONLY`
* DB state remains `PERSISTENT_DB_EMPTY_SCHEMA_ONLY`
* migrations applied remains 20
* no runtime started
* no memory started
* no paper trading started
* no real-data rows created accidentally

If any expected result differs, stop and inspect before continuing.

## 5. Post-Phase Operator Checks

After Phase 22B and after every later phase, the operator must check what changed and whether the phase respected its boundary.

For Phase 22B specifically, expected post-phase state:

* only documentation changed
* no source files changed
* no migration files changed
* no test files changed
* no DB writes
* no source requests
* no source responses
* no token rows
* no pair rows
* no snapshot rows
* no memory rows
* no paper decisions
* no paper positions
* no runtime state change

Required post-phase checks:

* `git status`
* `git diff --stat`
* `git diff --name-only`
* verify changed files are `docs/` and/or `AGENTS.md` only
* `printer-db-status`
* `printer-db-counts`
* `printer-readiness-check`
* `printer-operator-report`

For Phase 22B, `docs/printer-v1-operator-freeze-runbook.md` should be the only required changed file.

## 6. DB Backup / Checkpoint Expectations

This section documents policy only. Phase 22B must not create a DB backup unless the operator explicitly requests it later.

Before any phase that may write to the DB, the operator must create a timestamped DB backup.

The backup must preserve `data/printer_v1.sqlite3` before the phase starts.

The operator must record:

* backup filename/path
* current git commit
* current tag/checkpoint
* migration count
* DB state
* row counts for real tokens
* row counts for source requests/responses/failures
* row counts for snapshots
* row counts for memory windows/episodes/fingerprints
* row counts for paper decisions
* row counts for paper positions

For documentation-only phases like Phase 22B, no DB backup is required unless the operator wants an external/manual copy.

DB backup creation must not be hidden inside Codex. Codex may create a backup only when the operator explicitly requests that specific action.

## 7. Allowed Operator Commands

Allowed safe commands at this stage:

* `printer-readiness-check`
* `printer-db-status`
* `printer-db-counts`
* `printer-migration-status`
* `printer-operator-report`
* `printer-synthetic-validation`
* `git status`
* `git diff`
* `git diff --stat`
* `git diff --name-only`
* `git log --oneline -5`
* `git tag --list`

These are inspection/validation commands only. They must not start tracking, fetch real data, execute scheduler jobs, build memory, create paper decisions, open paper positions, or start runtime.

## 8. Disallowed Commands / Actions Before Their Phase

Before the correct Future Build Order phase, the operator must not run or ask Codex to run:

* source fetch commands
* source adapter execution
* discovery commands
* token/pair intake commands
* snapshot collection
* context collection
* memory building
* memory retrieval
* paper decision creation
* paper position creation
* scheduler execution
* runtime execution
* bounded runtime
* long-run validation
* wallet/signing/transaction commands
* live trading commands

Biggest future unlocks:

* Phase 23: contracts/fixtures only, no real HTTP.
* Phase 24: one disabled adapter only.
* Phase 25: first real source fetch, source tables only.
* Phase 26: controlled token/pair intake.
* Phase 27: controlled real token snapshots.
* Phase 29: first real memory windows.
* Phase 31: real memory retrieval.
* Phase 32: paper decisions.
* Phase 33: simulated paper positions.
* Phase 35: one scheduler job, then exit.
* Phase 36: bounded multi-tick runtime.

No future unlock permits live trading in Printer V1.

## 9. Readiness Checks

Readiness labels must be interpreted conservatively.

For the current state, `READY_SCHEMA_ONLY` means Printer schema exists and operator commands work, but no real operation has started.

`READY_SCHEMA_ONLY` does not mean Printer is ready for source adapters, live data, runtime, memory, or paper trading.

`READY_SCHEMA_ONLY` is the correct frozen state before Phase 23.

If readiness changes unexpectedly, stop and inspect before continuing.

Do not continue to a write-enabled phase if any of these become true unexpectedly:

* memory has started
* paper trading has started
* runtime has started
* real token rows exist before controlled intake
* real source rows exist before real source smoke checks
* real snapshot rows exist before the snapshot phase
* DB classification is unclear

## 10. Source Limits

No real source fetching is allowed in Phase 22B, Phase 23, or Phase 24 by default.

Source limits:

* Phase 23 may define contracts and fixtures only.
* Phase 24 may implement one adapter disabled by default.
* Phase 25 is the first phase allowed to fetch real data.
* Phase 25 must be one source only, one-shot only, limited calls only, and source tables only.
* Engines must never call external sources directly.
* Every future source call must pass through Source Governor after the proper phase unlock.

Source failures must be recorded honestly. Missing data must remain missing. Printer must never invent market, price, liquidity, safety, flow, chart, route, quote, or outcome data.

## 11. Stop Conditions

Codex/operator must stop immediately if any of these appear:

* source code change during Phase 22B
* migration change during Phase 22B
* test change during Phase 22B
* DB write during Phase 22B
* source adapter added
* real HTTP fetch added or run
* scheduler execution added or run
* runtime added or run
* memory generation
* paper decision
* paper position
* wallet connection
* private key handling
* transaction building
* transaction signing
* transaction sending
* live trading
* paid API dependency
* scoring/ranking/confidence system
* vector/embedding system
* web dashboard/frontend
* hidden loop, daemon, worker, cron, Celery, APScheduler, or background runtime

When a stop condition appears, do not continue to the next phase. Treat the current phase as failed until the issue is understood and corrected.

## 12. Rollback Procedure

For Phase 22B:

* If only docs changed incorrectly, revert or patch the documentation.
* If any source/migration/test/runtime file changed, stop and revert those changes.
* If the DB changed, stop and compare against the pre-phase DB status/counts.
* If any real rows were created, stop and treat the phase as failed.
* Do not continue to Phase 23 until the repo is back to documentation-only changes and DB state is safe.

For later phases:

* Use the last git checkpoint/tag.
* Use the DB backup created before write-enabled phases.
* Record what changed.
* Record why it violated the phase.
* Record what was restored.
* Do not hide or overwrite bad outcomes.

Rollback must be explicit and auditable. Bad outcomes, dirty data, failed source calls, and incorrect paper behavior must be preserved or documented honestly rather than hidden.

## 13. Phase Acceptance Checklist

Phase 22B can be accepted only if:

* `docs/printer-v1-operator-freeze-runbook.md` exists.
* The runbook references the Future Build Order.
* The runbook clearly says Phase 22B is documentation-only.
* The runbook includes current frozen state.
* The runbook includes pre-phase checks.
* The runbook includes post-phase checks.
* The runbook includes DB backup/checkpoint expectations.
* The runbook includes allowed operator commands.
* The runbook includes readiness checks.
* The runbook includes source limits.
* The runbook includes stop conditions.
* The runbook includes rollback procedure.
* No source code changed.
* No migrations changed.
* No tests changed.
* No DB rows changed.
* No runtime/source/memory/paper path started.
* Codex stops after this phase.

The Future Build Order reference for this runbook is `docs/printer-v1-future-build-order.md`.

## 14. What Codex Must Report

At the end, Codex must report exactly:

* Files changed
* What was built
* What was not touched
* Checks run
* Current DB state
* Current readiness label
* Source scan result
* Runtime scan result
* Pass/fail status
* Risks or concerns
* Next recommended phase

The next recommended phase must be:

Phase 23 - Source Adapter Execution Contract

Codex must not start Phase 23 from this phase.
