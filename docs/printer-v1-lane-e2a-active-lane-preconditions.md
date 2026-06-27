# Printer V1 Lane E2A Active-Lane Preconditions

## 1. Status

This is Post-Lane 10 Lane E2A — Conservative 15m Memory Factory Active-Lane Preconditions.

Lane E2A is a preconditions and readiness gate only. It does not run the bounded cycle.

Lane E2A does not implement source fetching, scheduler execution, snapshot creation, memory creation, DB mutation, retrieval activation, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper audits, PnL, wallet logic, private keys, signing, live trading, real funds, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

Lane E2A asks: is the repo ready for a later Lane E2 bounded 15m Memory Factory active cycle, and if so, what must still be proven?

## 2. Source-of-Truth Documents Checked

This preconditions review is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`
- `docs/printer-v1-lane-b-conservative-15m-memory-factory-readiness-review.md`
- `docs/printer-v1-lane-c-source-budget-governor-verification.md`
- `docs/printer-v1-lane-d-scheduler-tracking-window-close-readiness.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`
- `docs/printer-v1-paper-position-reactivation-review.md`

The current active roadmap extension is:

- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

## 3. Purpose of Lane E2A

Lane E2A verifies, by static inspection and test execution only, whether the Lane E1 dry-run scaffold satisfies the minimum preconditions for planning a Lane E2 active bounded 15m Memory Factory cycle.

Lane E2A does not run the cycle.

Lane E2A does not implement any component of the cycle.

Lane E2A produces this readiness document and answers each precondition explicitly.

## 4. Current Locked Capabilities

The following remain locked throughout Lane E2A and must remain locked in any future Lane E2:

- BUY
- SELL
- HOLD
- paper positions
- trade events
- paper audits
- PnL
- scheduler execution (for the current lane)
- source fetching (for the current lane)
- snapshot creation (for the current lane)
- memory creation (for the current lane)
- DB mutation (for the current lane)
- retrieval activation
- paper decision creation (for the current and first Memory Factory lane)
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
- 5m as main outcome memory
- 5m unlocking retrieval or decisions

## 5. Lane E1 Anchor and Command Confirmed

Lane E1 was committed and tagged at:

- Commit: `7245a1b`
- Tag: `printer-v1-post-lane10-lane-e1-memory-factory-dry-run-scaffold`
- Command registered in `pyproject.toml`:
  `printer-plan-conservative-15m-memory-factory-once = "printer_v1.operator_cli.commands:main_plan_conservative_15m_memory_factory_once"`

The `printer-plan-conservative-15m-memory-factory-once` command produces a dry-run planning report with no DB interaction, no source fetching, no scheduler execution, no snapshot writes, no memory writes, no retrieval, no paper decisions, no BUY/SELL/HOLD, no positions, no PnL.

Lane E1 tests: 90 tests, all passing.

The E1 anchor satisfies the first required future gate (`operator_approves_lane_e1_active_lane_commit_and_tag`).

## 6. E1 Dry-Run Fields — Minimum Gate for E2 Planning

The following required dry-run fields were confirmed present in the Lane E1 payload:

| Field | Value | Status |
|---|---|---|
| `operator_approved` | `True` | Confirmed |
| `dry_run` | `True` | Confirmed |
| `mode` | `"conservative"` | Confirmed |
| `target_window_kind` | `"WINDOW_15M"` | Confirmed |
| `support_window_kind` | `"WINDOW_5M_MICRO_EVENT"` | Confirmed |
| `support_window_only` | `True` | Confirmed |
| `source_fetching_enabled` | `False` | Confirmed |
| `scheduler_execution_enabled` | `False` | Confirmed |
| `memory_creation_enabled` | `False` | Confirmed |
| `paper_decisions_enabled` | `False` | Confirmed |
| `buy_enabled` | `False` | Confirmed |
| `positions_enabled` | `False` | Confirmed |
| `pnl_enabled` | `False` | Confirmed |
| `zero_clean_memories_allowed` | `True` | Confirmed |
| `clean_memory_forced` | `False` | Confirmed |
| `max_active_tokens` | `10` (default) | Confirmed |
| `max_track_fast` | `3` (default) | Confirmed |
| `max_track_normal` | `7` (default) | Confirmed |
| `locked_capabilities` | 20 items (BUY, SELL, HOLD, paper_positions, pnl_calculation, source_fetching, memory_creation, paper_decisions, live_execution, real_funds, wallet_private_key_signing, paid_api_dependencies, scoring_ranking_confidence_weighted, embeddings_vectors, 5m_as_main_outcome_memory, 5m_unlocking_retrieval_or_decisions, and more) | Confirmed |
| `stop_conditions` | 18 items | Confirmed |
| `required_future_gates` | 10 items | Confirmed |

The E1 dry-run fields satisfy the minimum structural gate for E2 planning. All locked capabilities, stop conditions, and required future gates are recorded.

**E2 planning may proceed.** Proceeding does not authorize implementation. Each remaining precondition below must be satisfied before a Lane E2 implementation lane commits.

## 7. Required Future Gates from E1 — Assessment

The `required_future_gates` list from the E1 payload contains ten gates. Status of each:

### Gate 1 — `operator_approves_lane_e1_active_lane_commit_and_tag`

**SATISFIED.**

Commit `7245a1b` tagged `printer-v1-post-lane10-lane-e1-memory-factory-dry-run-scaffold` was committed and tagged with operator authorization on 2026-06-27.

### Gate 2 — `source_budget_headroom_confirmed_for_approved_token_list`

**NOT YET SATISFIED.**

Lane C verified static source definitions only. No specific approved token list exists. No per-cycle source request budget has been calculated against a real candidate set. Per-source rate limits and stale windows exist in `src/printer_v1/sources/registry.py` and `src/printer_v1/sources/governor.py`, but an aggregate per-cycle budget for a conservative 10-token set has not been confirmed.

This gate requires:

- operator approves a specific initial token list or discovery policy for the first E2 cycle
- per-cycle source budget is calculated against that list
- headroom above rate limits is confirmed before the cycle starts

### Gate 3 — `scheduler_end_to_end_cycle_confirmed_in_test`

**NOT YET SATISFIED.**

Lane D verified static scheduler components and job kind definitions. No fixture-based test has proven that a bounded sequence of TRACK_FAST/NORMAL jobs can be enqueued, claimed, completed, and closed with zero running jobs and zero active locks after exit.

This gate requires:

- a new bounded-cycle integration test (fixture-based, no real sources, no real snapshots)
- the test must prove: job enqueue → claim → completion → MEMORY_WINDOW_CLOSE → completion → clean exit
- the test must verify no unbounded behavior, no lock leakage, and no source bypass

### Gate 4 — `lane_7_eligibility_confirmed_for_each_new_window`

**NOT YET SATISFIED.**

Existing clean eligible memory windows (IDs 19, 21, 23 from prior work) satisfy Lane 7 policy, but those are pre-existing. Any new window produced by an E2 cycle must independently satisfy the Lane 7 eligibility policy:

- memory_quality_label = CLEAN_MEMORY
- data_quality_label = CLEAN_DATA
- do_not_train = 0
- window_status = WINDOW_CLOSED
- window_kind != WINDOW_5M_MICRO_EVENT
- not AUDIT_ONLY
- not MISSING_CRITICAL_DATA

This gate cannot be confirmed until E2 actually attempts a cycle.

### Gate 5 — `memory_audit_passes_for_each_new_window`

**NOT YET SATISFIED.**

No new memory windows have been attempted. The memory audit path (Lane 8C review command, `printer-review-conservative-paper-decision-once`) exists and passes tests, but it has not been exercised on any E2-cycle-produced window.

This gate cannot be confirmed until E2 produces windows and the audit runs.

### Gate 6 — `operator_reviews_cycle_report_before_next_cycle`

**NOT YET SATISFIED.**

No cycle has run, so no cycle report exists. A future Lane E2 must produce a cycle report and receive operator review before a second cycle is authorized.

### Gate 7 — `full_test_suite_passes`

**SATISFIED (current state).**

- Lane E1 tests: 90/90 passing
- Nearby operator CLI tests (Lane 8A, 8B, 8C): 173/173 passing
- Historical test suite state at Lane E1 commit: passing

This gate must be re-verified after any new E2 implementation lane adds code.

### Gate 8 — `buy_remains_locked_throughout`

**SATISFIED.**

The E1 dry-run payload confirms `buy_enabled: False`. No BUY path exists in the Lane E1 code addition. The existing commands.py does not unlock BUY. AGENTS.md explicitly prohibits BUY without a future operator-approved BUY unlock lane.

### Gate 9 — `positions_remain_locked_throughout`

**SATISFIED.**

The E1 dry-run payload confirms `positions_enabled: False`. AGENTS.md explicitly prohibits paper positions without a valid clean-memory-backed paper decision. The tracking queue `PAPER_MONITORING` state exists but must remain unreachable while paper positions are locked.

### Gate 10 — `pnl_remains_locked_throughout`

**SATISFIED.**

The E1 dry-run payload confirms `pnl_enabled: False`. No PnL path exists in the Lane E1 addition. AGENTS.md explicitly prohibits PnL until separately approved.

### Gate Summary

| Gate | Status |
|---|---|
| `operator_approves_lane_e1_active_lane_commit_and_tag` | SATISFIED |
| `source_budget_headroom_confirmed_for_approved_token_list` | NOT YET |
| `scheduler_end_to_end_cycle_confirmed_in_test` | NOT YET |
| `lane_7_eligibility_confirmed_for_each_new_window` | NOT YET (requires live cycle) |
| `memory_audit_passes_for_each_new_window` | NOT YET (requires live cycle) |
| `operator_reviews_cycle_report_before_next_cycle` | NOT YET (requires live cycle) |
| `full_test_suite_passes` | SATISFIED (current state) |
| `buy_remains_locked_throughout` | SATISFIED |
| `positions_remain_locked_throughout` | SATISFIED |
| `pnl_remains_locked_throughout` | SATISFIED |

**4 of 10 gates satisfied. 3 require a live cycle. 3 require pre-cycle implementation work.**

## 8. Scheduler Readiness Remaining

Static inspection (Lane D) confirmed:

- scheduler job kinds for `TRACK_FAST_FIRST_15M`, `TRACK_NORMAL_FIRST_15M`, and `MEMORY_WINDOW_CLOSE` exist
- `printer_scheduler_jobs` schema has due-time, priority, status, lock owner, retry count, completion, failure, and cooldown fields
- `scheduler.py`, `resource_governor.py`, and `contracts.py` exist and define the job lifecycle

Still unresolved before an E2 active lane:

- Which exact job kind opens the first 15m Memory Factory cycle? (TRACK_FAST_FIRST_15M is the strongest candidate, but no E2 implementation has specified the exact job sequence)
- Which job kind triggers the forced window-close snapshot near 15m end?
- Which job kind triggers the memory-window build attempt?
- How will operator approval be asserted by the implementation at job-queue entry time?
- How will max jobs, max active seconds, max active tokens, and source budget be enforced as hard caps?
- How will each job report terminal success, honest failure, cooldown, or skip in the DB?
- How will stop reasons be recorded and returned to the operator report?
- How will the bounded cycle prove zero running jobs and zero active locks after exit?
- How will source failures remain visible without retry loops?
- How will broad context job kinds remain lower priority than token-level snapshots under load?
- How will paper decision job kinds be kept absent in the first implementation?

These must be answered in a fixture-based integration test before the first active cycle runs.

## 9. Source Governor and Source Budget Readiness Remaining

Static inspection (Lane C) confirmed:

- Source Governor exists in `src/printer_v1/sources/governor.py`
- all registered sources are free/public
- per-source rate limits, stale windows, and retry fields exist
- source recording tables exist

Still unresolved before an E2 active lane:

- No approved token list has been selected; source budget cannot be calculated without knowing which tokens are tracked
- No per-cycle aggregate budget has been calculated for a conservative 10-token run
- No operator-facing cycle budget report field exists yet
- Stale and partial response handling under real network conditions has not been live-tested
- The `printer_source_rate_limits` table is populated by governor calls; its behavior under a bounded multi-token cycle has not been tested end-to-end

## 10. Tracking Queue Readiness Remaining

Static inspection (Lane D) confirmed:

- `tracking_queue.py`, `contracts.py`, and `state_machine.py` exist
- states for TRACK_FAST, TRACK_NORMAL, WATCH_ONLY, COOLDOWN, ARCHIVED exist
- tracking-to-scheduler mapping routes TRACK_FAST to TRACK_FAST_FIRST_15M and TRACK_NORMAL to TRACK_NORMAL_FIRST_15M

Still unresolved before an E2 active lane:

- Max active token count (10, 3 fast, 7 normal) is defined in E1 dry-run constants but not enforced in any scheduler integration test
- No token has been moved from discovery or manual selection into a bounded 15m cycle and exited cleanly
- How a token exits the cycle after clean, dirty, audit-only, failed, or skipped output has not been proven
- How WATCH_ONLY rows are prevented from silently becoming main memory candidates has not been tested
- PAPER_MONITORING must remain unreachable while paper positions are locked; no test explicitly verifies this state boundary

## 11. 15m Snapshot and Window-Close Readiness Remaining

Static inspection (Lane D) confirmed:

- `record_token_snapshot` exists with idempotent duplicate handling
- `coverage.py` calculates expected snapshot count, gap rate, and missed close snapshot detection
- `memory/windowing.py` supports WINDOW_15M open, due-close, and close helpers

Still unresolved before an E2 active lane:

- Exact snapshot cadence for TRACK_FAST (1-3 min) and TRACK_NORMAL (5-10 min) during first 15m has not been implemented or tested end-to-end
- Close-snapshot timing and tolerance window has not been specified for E2
- Minimum snapshot count for a clean 15m window under the first implementation has not been confirmed
- Source budget exhaustion before window close has not been tested
- Stale or partial snapshots must not satisfy the window-close requirement; this gate has not been verified in an E2-specific test

## 12. Memory Audit Readiness Remaining

Lane 7 eligibility policy (CLEAN_MEMORY + CLEAN_DATA + do_not_train=0 + WINDOW_CLOSED + not WINDOW_5M_MICRO_EVENT + not AUDIT_ONLY + not MISSING_CRITICAL_DATA) was confirmed for existing windows 19, 21, 23.

Still unresolved before an E2 active lane:

- Lane 7 eligibility must be confirmed for each window produced by a new E2 cycle
- Memory audit (`printer-audit-memory-quality-once`) must pass for each new window before it is treated as retrieval-eligible
- The audit command exists and passes tests, but it has not been exercised on a freshly-produced E2 cycle window

## 13. Proof That Paper Decisions Remain Off

From the E1 dry-run payload:

```json
"paper_decisions_enabled": false
```

From the Lane E1 `_LANE_E1_LOCKED_CAPABILITIES` list in `commands.py`:

```python
"paper_decisions",
```

From `AGENTS.md`:

> The first Memory Factory implementation must keep paper decisions off.

From `docs/printer-v1-post-lane10-proposed-next-build-order.md`, Proposed Lane E:

> Not allowed: paper decisions, including WAIT, AVOID, or NO_ACTION creation

From `docs/printer-v1-memory-factory-guide.md`, Section 18:

> The Memory Factory does not unlock BUY.
> Stage A (WAIT/AVOID/NO_ACTION) still requires clean-memory-aware reporting and operator gates.

**Paper decisions are structurally and policy-blocked for the first Memory Factory implementation lane.**

No paper decision row count changes may occur in E2 unless a later operator-approved lane explicitly allows conservative WAIT/AVOID/NO_ACTION.

## 14. Proof That BUY, SELL, HOLD, Positions, and PnL Remain Locked

From the E1 dry-run payload:

```json
"buy_enabled": false,
"positions_enabled": false,
"pnl_enabled": false
```

From the Lane E1 `_LANE_E1_LOCKED_CAPABILITIES` list:

```python
"BUY",
"SELL",
"HOLD",
"paper_positions",
"trade_events",
"paper_trade_audits",
"pnl_calculation",
"live_execution",
"real_funds",
"wallet_private_key_signing",
```

From `AGENTS.md`:

> Do not unlock BUY without an explicit future operator-approved BUY unlock lane.
> Do not open paper positions without a valid clean-memory-backed paper decision.

From `docs/printer-v1-post-lane10-proposed-next-build-order.md`, Lane J:

> BUY, positions, and PnL remain locked until later explicit approved lanes.

From `docs/printer-v1-buy-unlock-preconditions.md` and `docs/printer-v1-paper-position-reactivation-review.md` (both documentation-only policy): BUY and position review thresholds have not been met. 50-100 clean 15m memories are required before serious BUY review begins (Memory Factory Guide, Section 18 Stage B). No clean memories from an active E2 cycle exist yet.

**BUY, SELL, HOLD, paper positions, trade events, paper audits, and PnL are structurally, policy, and precondition-blocked.**

The tracking queue `PAPER_MONITORING` state exists in the schema but must remain unreachable until paper positions are explicitly approved.

## 15. Whether E2 Should Proceed, Proceed with Limits, or Stay Blocked

**Decision: PROCEED WITH LIMITS.**

Proceed because:

- Lane E1 commit and tag satisfy Gate 1
- BUY/positions/PnL locks satisfy Gates 8, 9, 10
- Full test suite currently passes (Gate 7)
- All required source-of-truth docs confirm the bounded 15m approach is the correct next direction
- Static inspection across Lanes B, C, D confirmed architectural components are directionally suitable
- The E1 dry-run payload provides a machine-readable record of all locks, stop conditions, and required gates

Limits before E2 active implementation:

- Gate 2 (source budget for approved token list) must be satisfied — requires selecting and approving a token list and calculating budget
- Gate 3 (scheduler end-to-end cycle confirmed in test) must be satisfied — requires a new bounded-cycle integration test
- Gates 4, 5, 6 (lane 7 eligibility, memory audit, cycle report) are only satisfiable after a live cycle run
- Lanes E2B and E2C must be scoped separately and committed only after their own preflight passes

**E2 active implementation must not start as a single monolithic commit.** It must be sliced as:

- E2B: Bounded-cycle integration test (fixture-based, no real sources)
- E2C: First real bounded source-governed cycle attempt (operator-approved, bounded, one or two tokens)

## 16. Exact Recommended Next Slice — Lane E2B

**Lane E2B — Scheduler End-to-End Bounded Cycle Integration Test**

Goal: Write a fixture-based test that proves the Central Scheduler can execute a complete, bounded, clean-exit 15m Memory Factory cycle sequence without real sources.

Allowed:

- new test file: `tests/test_post_rc_lane_e2b_scheduler_bounded_cycle.py`
- temporary in-memory or temp-file SQLite database
- fixture-based job insertion, claim, complete sequence
- verification of zero running jobs and zero active locks after exit
- verification that MEMORY_WINDOW_CLOSE job fires after TRACK_FAST_FIRST_15M and TRACK_NORMAL_FIRST_15M complete
- verification that max_active_tokens cap is respected
- verification that PAPER_MONITORING state is unreachable while positions are locked
- verification that paper decision job kinds are absent

Not allowed:

- real source fetching
- real snapshot creation
- real memory creation
- real DB (use temp file)
- scheduler runtime loop
- background workers
- unbounded execution
- BUY, SELL, HOLD
- paper positions
- PnL
- migrations
- code changes to existing production modules unless a specific bug is found and reported

Acceptance gate for E2B:

- test file added
- tests pass
- git diff --check clean
- no production code changes except minor fixes explicitly reported
- operator commits and tags E2B before E2C begins

## 17. Stop Conditions for Future E2 Implementation

A future E2 active lane must stop immediately if any of these occur:

- source fetching runs without Source Governor approval
- Central Scheduler is bypassed
- max_active_tokens cap is violated
- max_jobs or max_seconds cap is not enforced
- a job remains running after the bounded cycle exits
- a lock remains active after the bounded cycle exits
- a source failure is hidden or retried without recording
- a stale snapshot satisfies a window-close requirement
- a missing window-close snapshot is silently skipped
- dirty, audit-only, or do_not_train memory is treated as retrieval-eligible
- clean memory is forced when evidence does not pass
- 5m support evidence is treated as a main outcome window
- a paper decision is created
- BUY, SELL, or HOLD is created
- a paper position is created
- a trade event, paper audit, or PnL is created
- wallet, private-key, signing, live-trading, paid API, scoring, ranking, confidence, weighted, embedding, or vector logic appears
- unbounded runtime appears

## 18. E2A Acceptance Checklist

Lane E2A is acceptable when:

- source-of-truth documents are identified and confirmed checked
- Lane E1 anchor commit and tag are confirmed
- Lane E1 command is confirmed in pyproject.toml and in commands.py
- all E1 dry-run fields are confirmed present and correct
- all 10 required future gates from E1 are assessed
- satisfied gates are listed with evidence
- unsatisfied gates are listed with what is needed
- scheduler readiness remaining questions are enumerated
- source governor / source budget remaining questions are enumerated
- tracking queue remaining questions are enumerated
- 15m snapshot and window-close remaining questions are enumerated
- memory audit remaining questions are enumerated
- paper decisions remaining off is proven from payload and policy
- BUY/SELL/HOLD, positions, and PnL remaining locked is proven from payload and policy
- E2 proceed/limit/block decision is stated
- exact recommended next slice is described
- stop conditions for future E2 are explicit
- locked capabilities remain locked throughout this lane
- no code was changed
- no DB mutation occurred
- no source fetching occurred
- no scheduler execution occurred

## 19. Next Recommended Lane After E2A

Lane E2B — Scheduler End-to-End Bounded Cycle Integration Test.

Lane E2B must not begin until:

- the operator explicitly approves starting E2B
- this E2A document is committed and tagged

Lane E2B does not authorize real source fetching, memory creation, retrieval, paper decisions, BUY, SELL, HOLD, paper positions, or PnL.

The first Memory Factory implementation must keep paper decisions off.

5m remains support-only.

15m remains the first main Memory Factory target.

Zero clean memories is an allowed and expected outcome when evidence does not pass.

Clean memory must never be forced.
