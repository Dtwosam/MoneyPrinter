# Printer V1 Lane D Scheduler, Tracking Queue, and Window-Close Readiness

## 1. Status

This is Post-Lane 10 Proposed Lane D - Scheduler, Tracking Queue, and Window-Close Readiness.

Lane D is documentation/static readiness verification only.

Lane D does not implement Memory Factory.

Lane D does not run scheduler jobs, runtime, source fetching, snapshot collection, memory creation, retrieval, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper audits, or PnL.

Lane D does not authorize wallet logic, private keys, signing, live trading, real funds, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

## 2. Source-of-Truth Documents Checked

This readiness review is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`
- `docs/printer-v1-lane-b-conservative-15m-memory-factory-readiness-review.md`
- `docs/printer-v1-lane-c-source-budget-governor-verification.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`
- `docs/printer-v1-paper-position-reactivation-review.md`

The current active roadmap extension is:

- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

## 3. Purpose of Lane D

Lane D verifies, by static inspection only, whether the existing Central Scheduler, tracking queue, token snapshot, window-close, and memory-window components appear ready for a later bounded 15m Memory Factory cycle.

Lane D must answer readiness questions before implementation starts.

The first Memory Factory implementation must keep paper decisions off.

The 5m window remains support-only.

15m remains the first main Memory Factory target.

A Memory Factory cycle may validly produce zero clean memories if evidence is dirty, stale, incomplete, failed, mismatched, missing critical fields, conflicting, or audit-only.

Clean memory must never be forced.

## 4. Current Locked Capabilities

The following remain locked:

- BUY
- SELL
- HOLD
- paper positions
- trade events
- paper audits
- PnL
- runtime expansion
- scheduler execution for this lane
- source fetching
- snapshot creation
- memory creation
- retrieval activation
- paper decision creation
- wallet logic
- private keys
- signing
- live trading
- real funds
- paid API dependencies
- scoring systems
- ranking systems
- confidence percentage systems
- weighted decision logic
- embeddings
- vectors

WAIT, AVOID, and NO_ACTION remain conservative non-position outcomes only under existing approved gates. Lane D does not create them.

## 5. Preflight Cleanup Performed

The initial `git status --short` check showed that the only dirty-tree item was:

- `lane_c_source_budget_governor_verification_commit_tag_summary.txt`

The operator explicitly authorized cleanup of that exact temporary Lane C summary file. It was deleted before Lane D work continued, and a follow-up `git status --short` check confirmed the tree was clean.

## 6. Read-Only Inspection Commands Used

Static inspection used only read-only commands:

- `git status --short`
- `git status --short`
- `Get-Content AGENTS.md | Select-Object -Skip 155 -First 35`
- `Get-Content docs\printer-v1-post-lane10-proposed-next-build-order.md | Select-Object -Skip 1 -First 220`
- `Get-Content docs\printer-v1-lane-b-conservative-15m-memory-factory-readiness-review.md | Select-Object -First 140`
- `Get-Content docs\printer-v1-lane-c-source-budget-governor-verification.md | Select-Object -First 160`
- `Get-Content docs\printer-v1-memory-factory-guide.md | Select-Object -Skip 500 -First 180`
- `Get-Content docs\printer-v1-buy-unlock-preconditions.md | Select-Object -First 80`
- `Get-Content docs\printer-v1-paper-position-reactivation-review.md | Select-Object -First 90`
- `rg --files src tests migrations | rg "scheduler|tracking|snapshot|memory|window|lifecycle"`
- `Get-ChildItem src\printer_v1\scheduler`
- `Get-ChildItem src\printer_v1\lifecycle`
- `Get-ChildItem src\printer_v1\snapshots`
- `Get-ChildItem src\printer_v1\memory`
- `rg -n "printer_scheduler_jobs|scheduler|JobStatus|claim|lock|max_jobs|running|bounded|priority|scheduled" src\printer_v1 tests migrations`
- `rg -n "tracking_queue|TrackingAction|TRACK_FAST|TRACK_NORMAL|WATCH_ONLY|ARCHIVED|window close|window_close|snapshot_mode|captured_at" src\printer_v1 tests migrations`
- `rg -n "record_snapshot|token_snapshots|printer_token_snapshots|snapshot_start_id|snapshot_end_id|window_start_at|window_end_at|WINDOW_15M|WINDOW_5M|memory_window" src\printer_v1 tests migrations`
- `Get-Content migrations\001_database_foundation.sql | Select-Object -Skip 70 -First 55`
- `Get-Content migrations\003_scheduler_resource_governor.sql | Select-Object -First 120`
- `Get-Content migrations\004_token_lifecycle_tracking_queue.sql | Select-Object -First 140`
- `Get-Content migrations\006_token_level_snapshot_system.sql | Select-Object -First 110`
- `Get-Content migrations\014_episode_memory_engine.sql | Select-Object -First 120`
- `Get-Content migrations\021_repeatable_evidence_windows.sql | Select-Object -First 180`
- `Get-Content src\printer_v1\scheduler\contracts.py | Select-Object -First 180`
- `Get-Content src\printer_v1\scheduler\scheduler.py | Select-Object -First 240`
- `Get-Content src\printer_v1\scheduler\scheduler.py | Select-Object -Skip 150 -First 160`
- `Get-Content src\printer_v1\scheduler\resource_governor.py | Select-Object -First 220`
- `Get-Content src\printer_v1\lifecycle\contracts.py | Select-Object -First 160`
- `Get-Content src\printer_v1\lifecycle\tracking_queue.py | Select-Object -First 260`
- `Get-Content src\printer_v1\lifecycle\tracking_queue.py | Select-Object -Skip 220 -First 140`
- `Get-Content src\printer_v1\snapshots\coverage.py | Select-Object -First 240`
- `Get-Content src\printer_v1\snapshots\recorder.py | Select-Object -First 240`
- `Get-Content src\printer_v1\memory\windowing.py | Select-Object -First 240`

## 7. Existing Central Scheduler Files and Components Found

Static inspection found:

- `src/printer_v1/scheduler/contracts.py`
- `src/printer_v1/scheduler/scheduler.py`
- `src/printer_v1/scheduler/resource_governor.py`
- `src/printer_v1/scheduler/__init__.py`
- `migrations/001_database_foundation.sql`
- `migrations/003_scheduler_resource_governor.sql`

The scheduler contract defines job kinds for:

- `OPEN_PAPER_TRADE_MONITOR`
- `ACTIVE_EXIT_RISK_TOKEN`
- `TRACK_FAST_MICRO_EVENT`
- `TRACK_FAST_FIRST_15M`
- `TRACK_NORMAL_FIRST_15M`
- `MEMORY_WINDOW_CLOSE`
- `TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH`
- `DISCOVERY_REFRESH`
- `MARKET_REGIME_CONTEXT`
- `SOLANA_CHAIN_HEAT_CONTEXT`
- `BACKUP_SOURCE_CHECK`

The priority order keeps paper monitoring and exit-risk work above tracking snapshots, keeps `MEMORY_WINDOW_CLOSE` above safety refresh and discovery work, and keeps broad context below token-level work.

`scheduler.py` includes helper paths for enqueuing jobs, preventing active duplicate jobs, listing due jobs, selecting next jobs, claiming due jobs, completing jobs, and failing jobs with cooldown handling.

`resource_governor.py` separates token-level job kinds from broad-context job kinds, includes priority aging, and delays broad context under higher-priority token pressure.

Lane D did not execute any scheduler job.

## 8. Existing Scheduler Tables or Migrations Found

`migrations/001_database_foundation.sql` defines `printer_scheduler_jobs` with:

- `job_name`
- `job_kind`
- `target_table`
- `target_id`
- `priority`
- `status`
- `scheduled_for`
- `started_at`
- `finished_at`
- `locked_at`
- `lock_owner`
- `retry_count`
- `last_error`
- timestamps

`migrations/003_scheduler_resource_governor.sql` adds indexes for:

- due job lookup by status, schedule, priority, and creation time
- lock owner lookup
- active duplicate detection

These structures appear suitable for a later bounded 15m Memory Factory implementation to describe job order and lock behavior, but Lane D does not prove runtime execution.

## 9. Existing Tracking Queue and Token Tracking Components Found

Static inspection found:

- `src/printer_v1/lifecycle/contracts.py`
- `src/printer_v1/lifecycle/tracking_queue.py`
- `src/printer_v1/lifecycle/state_machine.py`
- `src/printer_v1/lifecycle/__init__.py`
- `migrations/001_database_foundation.sql`
- `migrations/004_token_lifecycle_tracking_queue.sql`

The lifecycle contract includes states for:

- `DISCOVERED`
- `WATCH_ONLY`
- `TRACK_NORMAL`
- `TRACK_FAST`
- `PAPER_MONITORING`
- `COOLDOWN`
- `ARCHIVED`
- `INSTANT_REJECT_MEMORY_ONLY`

The queue status contract includes:

- `QUEUED`
- `ACTIVE`
- `PAUSED`
- `COOLDOWN`
- `ARCHIVED`
- `SKIPPED`

`tracking_queue.py` includes active duplicate checks, queue insertion, lane updates, status changes, due-item selection, lifecycle event recording, and scheduler synchronization.

The tracking-to-scheduler mapping routes:

- `TRACK_FAST` to `TRACK_FAST_FIRST_15M`
- `TRACK_NORMAL` to `TRACK_NORMAL_FIRST_15M`
- `WATCH_ONLY` to `DISCOVERY_REFRESH`
- `PAPER_MONITORING` to `OPEN_PAPER_TRADE_MONITOR`
- `COOLDOWN` to `BACKUP_SOURCE_CHECK`

Because paper positions remain locked, future Memory Factory work must avoid entering `PAPER_MONITORING` unless a later operator-approved position lane exists.

## 10. Existing Snapshot and Window-Close Components Found

Static inspection found:

- `src/printer_v1/snapshots/contracts.py`
- `src/printer_v1/snapshots/quality.py`
- `src/printer_v1/snapshots/frequency.py`
- `src/printer_v1/snapshots/coverage.py`
- `src/printer_v1/snapshots/recorder.py`
- `src/printer_v1/memory/windowing.py`
- `migrations/001_database_foundation.sql`
- `migrations/006_token_level_snapshot_system.sql`
- `migrations/014_episode_memory_engine.sql`
- `migrations/021_repeatable_evidence_windows.sql`

`printer_token_snapshots` stores token and pair snapshot fields, tracking lane, snapshot mode, source status, data quality, raw payload JSON, normalized payload JSON, and captured time.

`record_token_snapshot` resolves token/pair identity, classifies snapshot quality, stores raw and normalized payloads, and returns an existing row for an exact token/pair/captured_at/snapshot_mode duplicate.

`coverage.py` calculates expected snapshot count, actual snapshot count, missing count, max gap seconds, window coverage label, snapshot gap audits, and missed close snapshot handling.

`memory/windowing.py` defines supported memory durations:

- `WINDOW_5M_MICRO_EVENT`
- `WINDOW_15M`
- `WINDOW_1H`
- `WINDOW_4H`
- `WINDOW_12H`
- `WINDOW_24H`

It includes helpers to open memory windows, determine when a window can close, close memory windows, and list due memory windows.

`migrations/021_repeatable_evidence_windows.sql` adds repeatable evidence-window identity fields for snapshot ranges, window bounds, cycle/source reference, evidence role, evidence fingerprint, evidence identity hash, duplicate guard status, and diversity/concentration labels.

## 11. Existing Related Tests Found

Static inspection found relevant tests including:

- `tests/test_phase3_scheduler_resource_governor.py`
- `tests/test_phase35_scheduler_single_tick_executor.py`
- `tests/test_phase36_bounded_multi_tick_operator_runtime.py`
- `tests/test_phase37_long_run_paper_validation.py`
- `tests/test_phase4_token_lifecycle_tracking_queue.py`
- `tests/test_phase6_token_level_snapshots.py`
- `tests/test_phase27_controlled_token_snapshots.py`
- `tests/test_phase14_episode_memory_engine.py`
- `tests/test_phase29_first_real_memory_windows.py`
- `tests/test_post_rc_lane2_repeatable_evidence_windows.py`
- `tests/test_post_rc_lane3_context_freshness_window_targeting.py`
- `tests/test_post_rc_new_memory_build_safety_quote_evidence_read.py`

These tests indicate there is existing coverage around scheduler priority and locking, tracking queue behavior, token snapshots, memory windows, repeatable evidence identity, and fresh memory build safety.

Lane D did not run these tests because this lane is documentation/static verification only.

## 12. Suitability for a Later Bounded 15m Memory Factory Cycle

The current scheduler, tracking queue, snapshot, window coverage, and memory-window components appear directionally suitable for a later bounded 15m Memory Factory cycle because:

- Central Scheduler already has token-level job kinds for `TRACK_FAST_FIRST_15M`, `TRACK_NORMAL_FIRST_15M`, and `MEMORY_WINDOW_CLOSE`.
- Scheduler jobs have due-time, priority, status, lock owner, lock time, retry count, completion, failure, and cooldown fields.
- Tracking queue states can represent `TRACK_FAST`, `TRACK_NORMAL`, `WATCH_ONLY`, cooldown, pause, archive, and skipped states.
- Tracking queue items can synchronize into scheduler jobs.
- Snapshot recording has idempotent duplicate handling by token/pair/captured_at/snapshot_mode.
- Snapshot coverage can detect missing close snapshots and broken windows.
- Memory window helpers support `WINDOW_15M`.
- Repeatable evidence identity prevents old dirty or audit-only memory from permanently blocking newer distinct evidence while preserving duplicate no-op behavior for indistinguishable evidence.

This is not a final implementation approval. A later implementation lane must still prove bounded operation, operator approval, source-governed evidence collection, exact job choreography, correct stop reasons, no running jobs after exit, no active locks after exit, and paper decisions off.

## 13. Unresolved Scheduler Readiness Questions

Before implementation, scheduler readiness must answer:

- Which exact scheduler job kind opens the first 15m cycle?
- Which exact scheduler job kind performs the forced window-close snapshot?
- Which exact scheduler job kind attempts the memory-window build?
- How will the later cycle prove operator approval?
- How will max jobs, max seconds, max tokens, and source budget be enforced?
- How will each job report terminal success, honest failure, cooldown, or skip?
- How will stop reasons be recorded?
- How will the implementation prove zero running jobs and zero active locks after exit?
- How will source failures be kept visible without retry loops?
- How will broad context jobs remain lower priority than token-level snapshots?
- How will paper decision job kinds stay off in the first implementation?

## 14. Unresolved Tracking Queue Readiness Questions

Before implementation, tracking queue readiness must answer:

- What is the maximum active token count for the first 15m Memory Factory cycle?
- How many `TRACK_FAST` and `TRACK_NORMAL` items may run at once?
- How does a token move from discovery or manual selection into the first 15m cycle?
- How does a token leave the cycle after clean, dirty, audit-only, failed, or skipped output?
- How are revived tokens reopened without duplicate flooding?
- How are stale, low-liquidity, malformed, unsupported, or source-failed tokens archived or paused?
- How does the cycle prevent one token/pair from dominating future clean memory?
- How are tracking queue deltas reported to the operator?
- How are `WATCH_ONLY` rows prevented from silently becoming main memory candidates?
- How is `PAPER_MONITORING` kept unreachable while positions remain locked?

## 15. Unresolved Snapshot and Window-Close Readiness Questions

Before implementation, snapshot and window-close readiness must answer:

- What exact snapshot cadence applies to `TRACK_FAST` during the first 15m cycle?
- What exact snapshot cadence applies to `TRACK_NORMAL` during the first 15m cycle?
- How is the window-close snapshot scheduled and verified near the 15m close?
- What is the allowed close-snapshot tolerance?
- What is the minimum snapshot count for a clean 15m window under the first implementation?
- What happens when source budget is exhausted before window close?
- What happens when source data is partial, stale, failed, or conflicting?
- How are snapshot gap audits reported?
- How are stale old snapshots prevented from filling a fresh 15m window?
- How is a zero-clean-memory cycle reported without forcing clean output?
- How does 5m support evidence remain support-only and avoid satisfying the main 15m outcome requirement?

## 16. Risks and Gaps Before Implementation

Risks and gaps before a future implementation lane:

- The scheduler and tracking queue can describe the needed pieces, but the exact Memory Factory job choreography has not been implemented in Lane D.
- Static inspection does not prove real runtime bounds, job caps, source caps, or lock release.
- Static inspection does not prove the forced window-close snapshot can be collected under live source limits.
- Static inspection does not prove enough clean context will be available at window close.
- Static inspection does not prove a later cycle will produce clean memory; zero clean memories remains a valid outcome.
- Tracking queue concentration and token diversity must remain visible in reports.
- `PAPER_MONITORING` exists as a state, but it must remain locked until later BUY and position lanes approve it.
- 5m support evidence must not be accidentally treated as a main memory window.

## 17. Stop Conditions for Future Implementation

A future implementation lane must stop if any of these occur:

- unbounded runtime appears
- scheduler jobs run without operator approval
- source fetching bypasses Source Governor
- Central Scheduler is bypassed
- max jobs, max seconds, or source caps are not enforced
- a job remains running after exit
- a lock remains active after exit
- source failures are hidden
- stale or failed snapshots are used as clean evidence
- missing close snapshot is ignored
- dirty, audit-only, or do_not_train memory becomes retrievable
- clean memory is forced to meet a target
- 5m support evidence is treated as a main outcome window
- paper decisions are created
- BUY, SELL, or HOLD is created
- paper positions are created
- trade events, paper audits, or PnL are created
- wallet, private-key, signing, transaction, live-trading, paid API, scoring, ranking, confidence, weighted, embedding, or vector logic appears

## 18. What Must Not Be Built Yet

Lane D must not build:

- Memory Factory implementation
- scheduler/runtime execution
- source fetching
- token snapshot collection
- memory creation
- retrieval
- paper decision creation
- BUY, SELL, or HOLD paths
- paper position creation
- trade event creation
- paper audit creation
- PnL calculation
- wallet or private-key logic
- signing or transaction logic
- live-trading logic
- paid API dependency
- scoring, ranking, confidence, or weighted logic
- embedding or vector logic

## 19. Lane D Acceptance Checklist

Lane D is acceptable when:

- source-of-truth documents are identified
- Central Scheduler files and job kinds are identified
- scheduler tables and indexes are identified
- tracking queue files, states, and scheduler mapping are identified
- token snapshot files and storage fields are identified
- window-close and coverage helpers are identified
- memory-window duration and due-close helpers are identified
- related tests are identified
- suitability for a later bounded 15m Memory Factory cycle is stated conservatively
- unresolved scheduler, tracking, and window-close questions are visible
- future implementation stop conditions are explicit
- locked capabilities remain locked
- first Memory Factory implementation remains paper-decisions-off
- 5m remains support-only
- 15m remains the first main Memory Factory target
- zero clean memories remains an allowed outcome when evidence fails

## 20. Next Recommended Lane

The next recommended lane is Proposed Lane E - Conservative 15m Memory Factory Implementation, only if the operator explicitly approves starting it.

Lane E must remain bounded, operator-approved, source-governed, scheduler-controlled, paper-decisions-off, and willing to produce zero clean memories when evidence does not pass.
