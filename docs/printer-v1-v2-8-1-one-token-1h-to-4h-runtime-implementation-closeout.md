# Printer V1 V2-8.1 One-Token 1h-to-4h Runtime Implementation Closeout

## Status

Lane: V2-8.1 - One-Token 1h-to-4h Runtime Implementation

Verdict: V2_8_1_4H_RUNTIME_IMPLEMENTATION_PASS

This lane implements and deterministically verifies the one-token, current-run
WINDOW_1H to WINDOW_4H runtime boundary. It does not run a live 4h proof.
Real 4h collection remains disabled unless a later explicit proof-mode lane is
operator approved.

## Source Stack and Scope

The implementation remains subordinate to AGENTS.md, the Clean Master Spec,
the active memory-growth build order, the V2-7 proof closeout, the V2-7.1
cadence contract, the V2-7.2 continuity contract, and the V2-8 readiness
review. Source calls remain Source-Governor-owned and timed work remains
Central-Scheduler-owned.

The lane changes no 5m, 15m, or 1h cadence contract. WINDOW_12H and
WINDOW_24H remain disabled.

## Completed Runtime Path

The one-command runner can now, behind the explicit 4h proof gate:

1. resolve the exact terminal current-run WINDOW_1H predecessor;
2. require the same run, token, pair, and tracking lane;
3. reject manual, historical, mismatched, consumed, partial, conflicting, or
   ambiguous predecessor and replay plans;
4. anchor the fixed deadline at exact 1h close plus 10,800 seconds;
5. enqueue policy-derived 4h snapshots and one forced close;
6. collect governed opening and closing context;
7. evaluate current-run-ledger-only cadence and chained continuity;
8. attach shared 4h context evidence;
9. run E2Q, Lane Q, and Lane K/E2Z in fail-closed order;
10. cancel only the affected token's pending work after a terminal block;
11. emit lifecycle, budget, context, quality, and lock reporting; and
12. support report-only replay without duplicate calls, jobs, snapshots,
    windows, episodes, or fingerprints.

The cadence evaluator no longer accepts unrelated historical snapshots merely
because their IDs fall between the opening and closing snapshot IDs. Every 4h
cadence row must be linked through the exact current run ledger. The closing
snapshot must be uniquely attached to the current run close step.

## Cadence and Continuity

| Lane | Interval | Expected snapshots | Fixed continuation | Clean max gap | Blocked gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| TRACK_FAST | 180s | 61 | 10,800s | 225s | >=360s |
| TRACK_NORMAL | 360s | 31 | 10,800s | 450s | >=720s |

The first continuation snapshot and forced closing snapshot are included in
the expected count. Delayed scheduling cannot extend the deadline. Dirty
transition or cadence evidence forces do_not_train = 1; blocked evidence
creates no quality successor and terminally stops only that token.

## Scheduler Priority Contract

The authoritative priority order is:

1. open paper-trade monitoring;
2. active exit-risk token;
3. TRACK_FAST micro-event;
4. TRACK_FAST first 15m;
5. TRACK_FAST 1h;
6. TRACK_FAST 4h;
7. TRACK_NORMAL first 15m;
8. TRACK_NORMAL 1h;
9. TRACK_NORMAL 4h;
10. memory-window close;
11. tracked-token safety/liquidity refresh;
12. discovery;
13. market regime;
14. Solana chain heat; and
15. backup source check.

This preserves short-before-long ordering inside each tracking lane, keeps all
FAST token evidence ahead of NORMAL evidence, and keeps dependent close work
after snapshot collection but before safety, discovery, and broad context.
Cleanup and final reporting are synchronous terminal actions rather than
independent scheduler job kinds. The historical Phase 3 expected tuple was
updated to include the adopted 1h and 4h kinds; production ordering was not
changed.

## Budgets

| Lane | Full request ceiling | Full scheduler ceiling | 4h phase scheduler ceiling | Holder fallback |
| --- | ---: | ---: | ---: | ---: |
| TRACK_FAST | 69 | 64 | 63 | maximum 1 |
| TRACK_NORMAL | 39 | 34 | 33 | maximum 1 |

Automatic retries and endpoint rotation remain zero. Opening context is
limited to market/chain plus entry realism. Closing context is limited to
market/chain, safety, and exit realism.

## Quality and Promotion Gates

Clean promotion requires all of the following:

- exact current-run continuity;
- policy-valid cadence and closing freshness;
- genuine 4h E2Q structural/continuity acceptance;
- Lane Q integrity acceptance;
- shared 4h context evidence with clean_memory_context_ready = true; and
- E2Z's independent window and Lane Q checks.

Missing, dirty, stale, mismatched, untraceable, or incomplete shared context
cannot promote through Lane K or E2Z. A clean cadence alone is insufficient.

## Files Changed

- src/printer_v1/context_evidence/__init__.py
- src/printer_v1/context_evidence/window_15m.py
- src/printer_v1/operator_cli/e2q_memory_window_audit.py
- src/printer_v1/operator_cli/e2z_clean_memory_creation.py
- src/printer_v1/operator_cli/lane_q_15m_window_integrity_guard.py
- src/printer_v1/operator_cli/one_command_15m_factory.py
- src/printer_v1/operator_cli/one_token_4h_runtime.py
- src/printer_v1/scheduler/contracts.py
- src/printer_v1/scheduler/resource_governor.py
- src/printer_v1/snapshots/lifecycle_continuity.py
- tests/test_phase3_scheduler_resource_governor.py
- tests/test_post_lane10_lane_q_15m_window_integrity_guard.py
- tests/test_v2_8_1_one_token_4h_runtime.py
- this closeout

## Verification

Stable, small pytest invocations produced normal summaries and exit code zero:

- V2-8.1 runtime: 6 tests and 2 subtests;
- V2-7.1 long-window cadence: 12 tests and 6 subtests;
- V2-7.2 chained continuity: 8 tests and 62 subtests;
- bounded first-hour readiness: 5 tests;
- continuous runtime integration: 8 tests;
- shared context evidence: 8 tests;
- one-command factory: 16 tests;
- scheduler/resource governor: 25 tests;
- scheduler single-tick boundaries: 8 tests;
- E2Q focused audit, write-back, replay, and window-kind checks: 54 tests;
- Lane Q/Lane K integrity, isolation, replay, and lock checks: 31 tests; and
- E2Z focused promotion, idempotency, and lock checks: 12 tests.

Total unique tests: 193. Total subtests: 70.

Python compilation passed for every changed Python file. git diff --check
passed.

## Preserved Locks

The verified fixture and temporary-DB paths created zero retrieval queries,
retrieval matches, paper decisions, positions, trade events, paper trade
audits, and PnL. No live source, scheduler runtime, wallet, key, signing,
execution, paid API, scoring, ranking, confidence, weighted logic, embedding,
or vector capability was added or activated.

## Money Usefulness

This lane makes later 4h memory evidence more realistic by preserving the
exact observed trajectory from the current 1h close, enforcing honest cadence
and context quality, and preventing historical snapshot contamination or
premature clean promotion. It improves the reliability of future paper-only
memory comparison without creating a decision or trading path.

## Functionality Risks / Setbacks / Efficiency Blockers

- No bounded live 4h proof has run.
- Public source latency and rate-limit behavior over a real 10,800-second
  continuation remain unproven.
- Real opening/closing context freshness over a full 4h run remains unproven.
- The runtime is intentionally one-token and explicit-proof-only.
- Aggregate pytest execution remains unstable in this Windows environment;
  verification used stable small slices with complete summaries.
- WINDOW_12H and WINDOW_24H runtime work remains out of scope and disabled.

## Next Step

A separate, operator-approved, one-token bounded 4h proof lane is permissible.
That lane must use a fresh isolated proof DB, preserve the persistent DB, run
no retries or endpoint rotation, and accept clean, dirty, or blocked evidence
honestly. This closeout does not start that proof.
