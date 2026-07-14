# Printer V1 V2-7.1 Long-Window Snapshot Cadence Foundation Closeout

## Status

`V2_7_1_LONG_WINDOW_CADENCE_FOUNDATION_PASS`

V2-7.1 completes the deterministic cadence contracts for `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`. It does not activate real long-window collection, implement chained continuity, run sources or scheduler jobs, create memory, or begin V2-8.

## Source Stack And Scope

The lane was completed from `ae5f3e6 Close V2-7 bounded continuous first-hour proof` under the active Printer V1 stack, the V2-6.1 cadence adoption/proof closeouts, the V2-7 first-hour proof, and the applicable Source Governor evidence rules.

This lane changed cadence policy, deterministic tests, and disabled-window E2Q reporting only. No migration, database, source adapter, source loop, live runner, scheduler runtime, continuity chain, retrieval path, or financial path was added.

## Audit Finding

The authoritative cadence module already governed 5m, 15m, and 1h, and Lane Q consumed it. Long windows were represented by three wildcard placeholder rows:

- 4h: `300 / 450 / 600`, full 14,400-second duration, count `2`;
- 12h: `900 / 1350 / 1800`, full 43,200-second duration, count `2`;
- 24h: `1800 / 2700 / 3600`, full 86,400-second duration, count `2`.

Those rows did not distinguish FAST from NORMAL, did not model continuation durations, did not enforce one-versus-two missing snapshots, and could not classify forced-close freshness. E2Q correctly blocked long-window activation but did not report the exact future cadence or budget for the token's actual tracking lane.

## Adopted Cadence Contract

Expected counts include the first continuation snapshot and the forced closing snapshot.

| Window | Lane | Continuation | Nominal interval | Clean max gap | Dirty gap | Blocked at | Expected snapshots |
|---|---|---:|---:|---:|---:|---:|---:|
| 4h | FAST | 10,800s | 180s | 225s | `>225s and <360s` | `>=360s` | 61 |
| 4h | NORMAL | 10,800s | 360s | 450s | `>450s and <720s` | `>=720s` | 31 |
| 12h | FAST | 28,800s | 300s | 375s | `>375s and <600s` | `>=600s` | 97 |
| 12h | NORMAL | 28,800s | 600s | 750s | `>750s and <1200s` | `>=1200s` | 49 |
| 24h | FAST | 43,200s | 300s | 375s | `>375s and <600s` | `>=600s` | 145 |
| 24h | NORMAL | 43,200s | 600s | 750s | `>750s and <1200s` | `>=1200s` | 73 |

All six policies remain `enabled_for_real_collection = False`.

## Quality And Closing Rules

The authoritative evaluator now supports explicit long-window fixture evaluation while production evaluation remains blocked.

- CLEAN requires the exact expected count, full anchored continuation duration, every gap at or below the clean maximum, and a forced closing snapshot no more than 60 seconds late.
- One missing snapshot is DIRTY when the remaining evidence satisfies the other rules.
- Two or more missing snapshots are BLOCKED.
- A gap immediately above the clean maximum is DIRTY.
- A gap at or above the blocked threshold is BLOCKED.
- A closing snapshot over 60 seconds late but less than one nominal interval late is DIRTY.
- A closing snapshot one nominal interval late or more is BLOCKED.
- A missing closing snapshot or one preceding the anchored deadline is BLOCKED.
- An inadequate anchored duration is BLOCKED.
- Missing snapshots are never interpolated.

Anchored duration, observed first-to-last span, closing lateness, and closing-freshness status are reported separately. Cadence gaps are measured against the anchored deadline, so permitted close lateness is not double-counted as an interior gap. The established start/snapshot/end gap-report shape remains backward compatible.

## Policy-Derived Budgets

`cadence_resource_budget()` provides the future runner, scheduler-plan, close-path, report, and source-budget boundary. It includes the first continuation snapshot and the close job's forced snapshot, with zero automatic retries.

Per-token ceilings are:

| Window | Lane | Source-request ceiling | Scheduler-row ceiling |
|---|---|---:|---:|
| 4h | FAST | 61 | 61 |
| 4h | NORMAL | 31 | 31 |
| 12h | FAST | 97 | 97 |
| 12h | NORMAL | 49 | 49 |
| 24h | FAST | 145 | 145 |
| 24h | NORMAL | 73 | 73 |

The helper scales these ceilings by token count, but this lane does not authorize any token count or real run. Future runners must consume these values rather than introduce literals.

## Consumer Alignment

- The cadence policy remains the single authoritative contract.
- Lane Q already resolves policy by exact window and stored tracking lane and embeds canonical cadence evaluation in its verdict.
- E2Q still blocks 4h/12h/24h as unsupported main windows, but now reports the exact stored token-lane policy and policy-derived resource budget.
- Lane K continues to consume the Lane Q/E2Q result; no bypass or alternate cadence path was added.
- No active long-window runner, scheduler plan, or close path exists. Their future implementation is required to use the policy and budget helpers and remains blocked until an explicit activation/continuity lane.
- 5m support, 15m, and 1h policy values and behavior remain unchanged.

## Files Repaired

- `src/printer_v1/snapshots/cadence_policy.py`
- `src/printer_v1/operator_cli/e2q_memory_window_audit.py`
- `tests/test_v2_7_1_long_window_cadence_foundation.py`
- `docs/printer-v1-v2-7-1-long-window-snapshot-cadence-foundation-closeout.md`

## Tests And Checks

Deterministic and nearby focused groups passed with normal summaries:

- V2-7.1 long-window foundation: `12 passed`.
- V2-6.1 authoritative cadence and continuity: `22 passed`.
- Legacy pure cadence policy/boundaries/production disablement: `66 passed`.
- Lane Q and Lane K DB-backed cadence enforcement: `17 passed`.
- E2Q blocked-window-kind regression: `5 passed`.
- E2Q forbidden-table/lock regression: `11 passed`.
- V2-6 long-window disablement and zero-delta locks: `5 passed`.
- V2-7 first-hour readiness regression: `5 passed`.
- Python compilation: passed.
- `git diff --check`: passed before closeout.

Total focused assertions reported by these groups: `143 passed`.

One aggregate DB-heavy invocation ended without a summary in the known Windows test environment. It was replaced by smaller identical class groups; every group produced `OK` and shell exit code `0`. No test was skipped or weakened.

## Money-Usefulness Contribution

Long-window learning is only useful when sparse or late observations cannot masquerade as clean history. This foundation gives future 4h/12h/24h work exact, reproducible coverage and close-freshness boundaries while keeping anchored time distinct from observation span. It reduces the risk of training on fabricated continuity or incomplete outcomes.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Chained 1h-to-4h, 4h-to-12h, and 12h-to-24h continuity is not implemented.
2. Real long-window runners, scheduler handlers, close paths, and Source Governor budgets are not activated; only their shared policy/budget contract now exists.
3. The approved counts imply substantial public-source and scheduler demand. Rate-limit, starvation, interruption, and replay behavior require later bounded design and proof.
4. Long-window E2Q/Lane Q/Lane K clean-promotion behavior remains disabled and must not be inferred from fixture cadence PASS results.
5. No live evidence was collected, and no claim about long-window clean-memory yield is made.

## Locks Preserved

- Solana-only, Solana memecoin-only, paper-only.
- 5m remains support-only.
- 4h/12h/24h real collection remains disabled.
- No retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- No wallet, keys, funds, signing, execution, paid API, scores, ranks, confidence, weights, embeddings, or vectors.
- No Source Governor or Central Scheduler bypass.
- No persistent DB mutation.

## Final Verdict

`V2_7_1_LONG_WINDOW_CADENCE_FOUNDATION_PASS`

The long-window cadence contracts, quality boundaries, forced-close freshness, canonical reporting, and policy-derived budgets are deterministic and regression-safe. Real long-window collection and continuity remain locked. V2-8 and continuity work were not started; the next action is operator review and an explicitly approved design lane for chained long-window continuity.
