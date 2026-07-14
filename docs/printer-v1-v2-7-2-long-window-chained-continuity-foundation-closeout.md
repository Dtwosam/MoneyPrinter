# Printer V1 V2-7.2 Long-Window Chained Continuity Foundation Closeout

## Status

`V2_7_2_LONG_WINDOW_CONTINUITY_FOUNDATION_PASS`

V2-7.2 establishes deterministic, fail-closed continuity contracts for
`WINDOW_1H -> WINDOW_4H`, `WINDOW_4H -> WINDOW_12H`, and
`WINDOW_12H -> WINDOW_24H`. The contract is fixture-testable and DB-resolvable,
but real 4h, 12h, and 24h collection remains disabled. No live source call,
scheduler runtime, persistent DB mutation, long-window proof, or V2-8 work was
performed.

## Source Stack And Audit

The lane started from `06ef25b Establish V2-7.1 long-window cadence contracts`
and used the active Printer V1 source stack, the V2-6.2 continuity closeout, the
V2-6.3 runtime-integration closeout, the V2-7 bounded first-hour proof, the
V2-7.1 cadence closeout, and the applicable Source Governor evidence rules.

The audit found that `lifecycle_continuity.py` already owned the proven
5m-to-15m-to-1h identity, consumption, deadline, transition, and fail-closed
outcome contract. V2-7.1 supplied exact long-window cadence and budget policies,
but no long-chain resolver or evaluator existed. The existing
`evaluate_transition_gap()` remains specific to 15m-to-1h and has different
legacy boundaries, so it was not reused for the new long transitions.

The smallest compliant design was to extend the existing authoritative
continuity module with a disabled long-chain foundation. No runner, source loop,
close path, or real scheduler plan was added.

## Required Chain

Only these transitions are recognized:

| Successor | Exact required predecessor | Fixed deadline |
|---|---|---:|
| `WINDOW_4H` | exact fresh `WINDOW_1H` | 1h close + 10,800s |
| `WINDOW_12H` | exact fresh `WINDOW_4H` | 4h close + 28,800s |
| `WINDOW_24H` | exact fresh `WINDOW_12H` | 12h close + 43,200s |

The deadline derives only from the exact predecessor close and the unchanged
V2-7.1 successor policy. Delayed planning or a delayed first successor snapshot
cannot extend it.

## Transition Boundaries

The gap is `first real successor snapshot - exact predecessor closing snapshot`.

| Transition | Lane | CLEAN | DIRTY | BLOCKED |
|---|---|---:|---:|---:|
| 1h -> 4h | FAST | `<=225s` | `>225s and <360s` | `>=360s` |
| 1h -> 4h | NORMAL | `<=450s` | `>450s and <720s` | `>=720s` |
| 4h -> 12h | FAST | `<=375s` | `>375s and <600s` | `>=600s` |
| 4h -> 12h | NORMAL | `<=750s` | `>750s and <1200s` | `>=1200s` |
| 12h -> 24h | FAST | `<=375s` | `>375s and <600s` | `>=600s` |
| 12h -> 24h | NORMAL | `<=750s` | `>750s and <1200s` | `>=1200s` |

DIRTY forces `do_not_train = 1`. BLOCKED cannot become quality memory. Missing
or invalid first-snapshot time is BLOCKED rather than silently becoming unknown.

## Implementation

### Authoritative planning and evaluation

`src/printer_v1/snapshots/lifecycle_continuity.py` now provides:

- an explicit three-transition registry;
- policy-derived fixed-deadline calculation;
- automatic plan construction from a resolved predecessor, with no caller-
  supplied predecessor ID, closing snapshot ID, or deadline;
- exact run/token/pair/lane/window/closing-snapshot validation;
- exact long-transition gap classification from the successor policy;
- rejection of manual or historical linkage, consumed reuse, wrong predecessor,
  interpolation, fake aggregation, restart, clock reset, negative gap, and target
  drift;
- a read-only current-run DB resolver requiring exactly one terminal successful
  predecessor close step;
- replay-safe token-local terminal blocking and cancellation of only pending jobs
  for that token, pair, and successor kind.

Plans always report `activation_allowed = false`. All long-window policies remain
`enabled_for_real_collection = false`.

### Replay and isolation

Consumed predecessor IDs are read from successor supporting-context linkage. A
predecessor already used by another successor cannot reopen. A terminal block is
recorded once in the existing run-step ledger. Replaying the block returns the
same marker, creates no duplicate marker, and cancels no jobs again.

Cancellation is scoped to the exact run, token, pair, and successor kind. Jobs
for another token and jobs for a different successor of the same token remain
untouched. A blocked foundation evaluation does not create a successor memory
window.

## Files Changed

- `src/printer_v1/snapshots/lifecycle_continuity.py`
- `tests/test_v2_7_2_long_window_chained_continuity.py`
- `docs/printer-v1-v2-7-2-long-window-chained-continuity-foundation-closeout.md`

No migration was required. Existing run-step, scheduler-job, memory-window, and
supporting-context fields are sufficient for the disabled foundation.

## Tests And Checks

All deterministic and nearby groups completed with normal zero-exit summaries:

- V2-7.2 long-chain foundation: `8 passed`; includes all six transition/lane
  combinations, clean/dirty/blocked boundaries, all required rejection shapes,
  DB resolution, consumed reuse, replay, token isolation, and downstream locks.
- V2-7.1 long-window cadence foundation: `12 passed`.
- V2-6.2 continuous first-hour lifecycle: `32 passed`.
- V2-6.3 runtime integration: `8 passed`.
- V2-7 first-hour readiness: `5 passed`.
- V2-6.1 cadence continuity: `22 passed`.
- Legacy cadence import: `7 passed`.
- Legacy cadence lookup and pure evaluation: `34 passed`.
- Lane Q clean-coverage regression: `3 passed`.
- Lane Q blocked/unknown coverage regression: `4 passed`.
- Lane K coverage and downstream-lock regression: `4 passed`.
- Disabled-window, timing, span, boundary, short-window, and production-mode
  regression: `25 passed`.
- Python compilation: passed.
- `git diff --check`: passed before closeout.

One cumulative pytest invocation ended after progress output without a summary in
the known local Windows environment. The same native `unittest` classes were run
in smaller groups and each produced `OK` with shell exit code 0. No test was
skipped, removed, or weakened.

## Cadence And Budget Preservation

V2-7.1 values were not changed. Long plans derive continuation duration,
expected snapshot count, gap boundaries, and disabled status directly from
`cadence_policy.py`. The existing 5m, 15m, and 1h policies and the proven
5m-to-15m-to-1h lifecycle remain unchanged.

The policy-derived future per-token source and scheduler ceilings remain:

| Window | FAST | NORMAL |
|---|---:|---:|
| 4h | 61 | 31 |
| 12h | 97 | 49 |
| 24h | 145 | 73 |

These values are planning boundaries only and do not authorize real collection.

## Money Usefulness

Long-duration memory is useful only when it follows the same asset continuously.
This foundation prevents a later window from silently switching token, pair,
lane, run, predecessor, or clock anchor. It also prevents delayed restarts and
reused history from masquerading as continuous evidence, reducing the chance of
training on false long-horizon outcomes.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Real 4h, 12h, and 24h runners, handlers, close paths, and scheduler plans do
   not exist and remain disabled.
2. The foundation does not prove public-source capacity for the policy-derived
   31-to-145 request ceilings.
3. Long-window context freshness, quality promotion, interruption recovery, and
   rate-limit behavior still require later explicit implementation and bounded
   proof lanes.
4. The existing run ledger is rooted in a `WINDOW_15M` proof run; this foundation
   deliberately resolves chained rows within that same run rather than adding a
   new long-run schema. Any future architecture change requires separate review.
5. No claim is made about clean 4h, 12h, or 24h memory yield.

## Locks Preserved

- Solana-only, Solana memecoin-only, paper-only.
- 5m remains support-only.
- 4h, 12h, and 24h remain disabled for real collection.
- No live source, runtime, scheduler execution, persistent DB write, or proof.
- No retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or
  PnL.
- No wallet, keys, funds, signing, execution, paid API, scoring, ranking,
  confidence, weights, embeddings, or vectors.
- No Source Governor or Central Scheduler bypass.

## Final Verdict

`V2_7_2_LONG_WINDOW_CONTINUITY_FOUNDATION_PASS`

The exact long-window predecessor chain, fixed deadlines, transition boundaries,
identity and consumption rules, token-local terminal stop, replay behavior, and
downstream locks are deterministic and regression-safe. Real long-window
collection remains locked. V2-8 was not started; the next step is operator review
and explicit approval of a later long-window runtime implementation lane.
