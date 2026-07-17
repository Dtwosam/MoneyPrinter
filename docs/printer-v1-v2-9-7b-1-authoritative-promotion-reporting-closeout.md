# Printer V1 V2-9.7B.1 Authoritative Promotion Reporting Closeout

## Verdict

V2_9_7B_1_AUTHORITATIVE_PROMOTION_REPORTING_PASS

V2-9.7B.1 is complete. Top-level factory reporting now counts clean run-local
yield from eligible, run-attached printer_episodes promotion rows instead of
mistaking the pre-promotion memory-window candidate label for the final clean
yield verdict.

This is a reporting-only repair. It does not activate operational memory
growth and does not change E2Q, Lane Q, Lane K, or E2Z promotion behavior.

## Preflight

- Required starting commit: c928aa4
- Observed starting HEAD: c928aa4
- Tracked tree at start: clean
- Active Python/runtime processes at start: 0
- Active V2-9 one-proof lock: absent
- Persistent corpus DB: data/printer_v1.sqlite3
- Persistent DB SHA-256 before work:
  97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
- Persistent DB size before work: 13,017,088 bytes
- Unrelated untracked artifacts: observed and left untouched

No discovery, source adapter, runtime, proof launcher, or memory-generation
command was run.

## Repair

one_command_15m_factory.py now performs a read-only reconciliation for the
current run:

1. Run-step-attached memory-window IDs define the run-local candidate scope.
2. Eligible printer_episodes rows define authoritative clean promotion.
3. Episode ownership must match the outcome's exact token, pair, window ID,
   and window kind.
4. The exact close-step E2Z result distinguishes creation from idempotent
   replay after the eligible episode has been confirmed.
5. Duplicate eligible rows for one attached window cannot increase yield;
   reporting counts the window once.
6. The source memory-window memory_status and memory_quality_label remain
   visible as candidate evidence.

Per-token outcomes, run_local_yield, memory_results, and the final report now
share these statuses:

- CLEAN_PROMOTED
- DIRTY_OR_BLOCKED
- ALREADY_EXISTS_IDEMPOTENT
- NO_PROMOTION

A successfully promoted episode can therefore be reported as clean while its
source candidate remains PARTIAL_MEMORY. An unpromoted partial candidate is
reported as NO_PROMOTION, not as clean and not as a failed clean yield.

## Verification Results

Focused V2-9.7B.1 verification:

- 3/3 authoritative promotion reporting tests passed.
- One eligible clean promoted episode counted exactly once.
- Pre-promotion PARTIAL_MEMORY remained visible and did not suppress clean
  promoted yield.
- Dirty and blocked candidates remained non-clean.
- E2Z_ALREADY_EXISTS reported as ALREADY_EXISTS_IDEMPOTENT and remained one
  clean result without a second insert.
- Two-token outcomes remained isolated by token, pair, and window.
- The authoritative episode query was read-only and ignored ineligible,
  unrelated-run, and duplicate rows.
- Reporting did not write an episode or any downstream row.

Nearest fixture-only regressions:

- 38/38 tests passed across the V2-4 one-command factory, V2-5 multi-token
  factory, and V2-6.3 continuity integration suites.
- Retrieval and financial forbidden-delta checks remained zero in the
  existing factory regression coverage.
- Python compilation passed for the modified report module and focused test.
- git diff --check passed.

Persistent DB verification:

- SHA-256 after implementation and tests:
  97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
- Size after implementation and tests: 13,017,088 bytes
- Result: byte-for-byte hash unchanged.

All verification databases were temporary and isolated.

## Money-Usefulness Contribution

This repair makes reported corpus yield economically trustworthy. Operators
can now see whether governed evidence actually became an authoritative clean
episode, instead of receiving a false zero from an intentionally partial
source candidate. It also keeps dirty, blocked, missing-promotion, and replay
outcomes distinct, preventing row-count inflation and misleading campaign
productivity conclusions.

It does not claim profit, trading performance, or decision quality.

## What This Lane Improves

- Reconciles per-token outcomes with authoritative E2Z promotion.
- Reconciles run-local yield, memory results, and final report totals.
- Preserves source-window candidate state for forensic inspection.
- Makes clean creation and idempotent replay separately observable.
- Prevents duplicate episode rows from inflating one window's yield.
- Preserves exact two-token token/pair/window isolation.
- Removes the V2-9.7A clean-promotion reporting under-count blocker.

## What Remains Locked

- Operational memory growth
- V2-9.7C, V2-9.7D, V2-9.7E, and V2-9.8 activation
- Retrieval and similarity use
- Paper decisions
- BUY, SELL, and HOLD
- Paper positions and trade events
- Paper audits and PnL
- Live trading, wallets, private keys, signing, and real funds
- Paid APIs
- Scoring, ranking, confidence percentages, and weighted logic
- Historical row rewrites and migrations

The safety-label timeframe issue, queue/lifecycle behavior, heartbeat
supervision, and embedded Git provenance were not repaired in this lane.

## Proof Requirements Completed

- Authoritative clean episode counted once: complete
- Partial source candidate not misreported as failed yield: complete
- Dirty and blocked candidates remain non-clean: complete
- Idempotent replay remains idempotent and separately labeled: complete
- Two-token token/pair/window isolation: complete
- Forbidden downstream deltas remain zero: complete
- Compilation: complete
- Persistent DB hash unchanged: complete
- Static inspection and git diff --check: complete

No live proof or further four-hour proof was required or run.

## Functionality Risks / Setbacks / Efficiency Blockers

### Functionality Risks

- Creation versus idempotent replay is taken from the exact attached close
  step's E2Z result only after the episode row independently proves clean
  eligibility. If a future report format removes that exact E2Z event, the
  episode still counts as clean but is conservatively labeled CLEAN_PROMOTED
  rather than inferred as replay.
- The authoritative query deduplicates by memory-window ID for reporting.
  Unexpected duplicate eligible episode rows remain a separate data-integrity
  concern and are not rewritten by this lane.

### Setbacks

- The first broader regression attempts were blocked before test execution by
  the Windows filesystem sandbox denying SQLite access in Python temporary
  directories. The same fixture-only suites were rerun outside that wrapper
  and passed 38/38.
- The packaged patch helper was inaccessible under the Windows app sandbox.
  Exact-match workspace edits were used instead; source inspection,
  compilation, tests, and diff checks validated the result.

### Efficiency Blockers

- Reporting still reads embedded E2Z result JSON to distinguish newly created
  from already-existing promotion because no separate run-local promotion
  event table exists. Adding provenance storage or a migration was outside
  this lane.
- The other V2-9.7A operational blockers remain pending their separately
  approved repair lanes.

## Files Changed

- src/printer_v1/operator_cli/one_command_15m_factory.py
- tests/test_v2_5_multi_token_15m_conservative.py
- tests/test_v2_9_7b_1_authoritative_promotion_reporting.py
- docs/printer-v1-v2-9-7b-1-authoritative-promotion-reporting-closeout.md

## Final Status

V2_9_7B_1_AUTHORITATIVE_PROMOTION_REPORTING_PASS

The next work remains a separately authorized V2-9.7B repair lane. This
closeout does not start V2-9.7C/D/E, operational memory growth, V2-9.8, or
V2-10.