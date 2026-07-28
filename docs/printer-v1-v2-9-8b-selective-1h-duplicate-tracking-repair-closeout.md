# Printer V1 V2-9.8B Selective-1h Duplicate Tracking Repair Closeout

## Verdict

`V2_9_8B_SELECTIVE_1H_DUPLICATE_TRACKING_REPAIR_PASS`

This PASS authorizes only a repeat of the selective-1h operator-readiness
review. It does not authorize another operational proof.

## Baseline and scope

- baseline branch: `master`
- baseline HEAD: `65bb0ad75b1555d95c7748d38c3fd8322959cfb2`
- baseline worktree: clean
- primary classification: `COMMITTED_CODE_DEFECT`
- blocked execution: `20260728T174735Z-5c86dd14b245`
- blocked cause: `DUPLICATE_ACTIVE_TRACKING`
- actual exact conflicting row: queue id `26`, `COOLDOWN`

No operational proof was run. No real source call, discovery runtime, Scheduler
runtime, campaign runtime, or authoritative DB write was performed.

## Implementation

### Canonical queue assessment

The queue owner now exposes a read-only latest exact token/pair/lane handoff
assessment. It distinguishes:

- fresh;
- genuine `QUEUED`/`ACTIVE`/`PAUSED` ownership;
- cooldown requiring canonical reopen;
- terminal `SKIPPED`/`ARCHIVED` state;
- unsupported fail-closed state.

`enqueue_tracking_item()` refuses every non-fresh category. Its public tuple
contract is preserved, while callers that require truthful detail use the
assessment before enqueue.

### Budget-aware reserve continuation

The authoritative operational holder funnel assesses queue state before
candidate admission, maturation, or holder source work. A known conflict is
recorded categorically and the bounded reserve continues. The pre-lifecycle
terminal classifier preserves that queue reason if fewer than two candidates
remain.

### Selection and handoff

The combined executor applies the same assessment before uniform selection.
One conflict therefore does not block two lawful alternatives. The handoff
rechecks immediately before queue insertion and reports the actual state.

The existing two-slot savepoint was not replaced: both queue rows, both first
15m Scheduler jobs, both slots, and both links still commit together or roll
back together.

### Revival

The committed `REOPEN_REVIVED_TOKEN` owner is unchanged. The repair does not
invent a cooldown override, does not silently reactivate cooldown, and does not
promote a reopened `WATCH_ONLY` row into `TRACK_NORMAL`.

## Proof results

All proof used temporary databases, fixtures, and mocks.

Covered behavior:

1. fresh identity creates exactly one queue row;
2. `QUEUED`, `ACTIVE`, and `PAUSED` are excluded before handoff;
3. cooldown without reopen is excluded;
4. committed revival records `REOPEN_REVIVED_TOKEN`, preserves history, and
   creates one live canonical row;
5. `SKIPPED` and `ARCHIVED` refuse implicit reopen;
6. same mint/same pair conflicts while same mint/new pair remains distinct;
7. one conflict is replaced from the eligible reserve;
8. initial two-slot handoff remains atomic;
9. a true active collision remains `DUPLICATE_ACTIVE_TRACKING`;
10. cooldown shortfall reports `COOLDOWN_REOPEN_REQUIRED`;
11. success and rollback leave no duplicate queue rows or orphan first-15m jobs;
12. Source Governor and Central Scheduler ports remain mandatory;
13. no 1h/4h job, support-5m authority, retrieval, or financial table unlock is
    introduced.

Focused results:

| Scope | Result |
|---|---|
| repair contract + atomic handoff + Phase 4 queue | 42 passed, 5 subtests passed |
| selective-1h command + origin/lifecycle integration | 32 passed |
| authoritative live operational owner | 40 passed |
| combined discovery + V2-2 selection + canonical revival | 226 passed |
| Python compilation | passed |
| `git diff --check` | passed |
| authoritative DB SHA-256 | unchanged at `dd5ecc835bf21e91a01470000d2d1738a271acbe20a8c1d9539594f30aa28aea` |

No broad/full suite was run because this is a narrow repair and the risk-based
verification policy calls for focused plus nearest regressions. Static checks
also include lock scans and final clean-worktree verification after commit.

One nearest regression remains red at the required baseline and after the
repair: `test_insufficient_pool_cleanup_report_replay` expects terminal cleanup
to cancel at least one Scheduler job, while the discovery owner has already
terminalized all linked jobs and cleanup truthfully reports zero cancellations.
An isolated export of exact baseline `65bb0ad75b1555d95c7748d38c3fd8322959cfb2`
produced the same result (`1 failed, 1 passed`). The test was not weakened or
edited, and its failure does not overlap this repair.

## Money-usefulness contribution

The repair protects scarce governed and holder budget from candidates already
known to be unactivatable, allows eligible reserve candidates to reach clean
memory collection, and preserves honest lifecycle categories. This improves
corpus-growth efficiency without increasing proof ceilings or weakening memory
quality. It creates no trade signal and no financial capability.

## What remains locked

- another live/selective-1h proof until a fresh operator-readiness PASS and
  explicit operator authorization;
- 4h and later windows;
- runtime expansion and unbounded campaigns;
- retrieval and dirty-memory use;
- paper decisions and BUY/SELL/HOLD;
- positions, trades, paper audits, and PnL;
- wallet, keys, signing, real execution, and paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings, and vectors;
- retries, automatic restarts, and successors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A correctly excluded queue-owned candidate can leave fewer than two eligible
  candidates; the campaign will stop honestly rather than force activation.
- Revival remains intentionally operator/lifecycle-owned and may reduce reuse
  until explicit fresh evidence satisfies that contract.
- No schema uniqueness constraint was added because migrations were prohibited;
  the canonical assessment and atomic transaction are the enforcement boundary.
- The terminal report does not yet persist a separate structured list of every
  queue-excluded reserve candidate; categorical holder facts and first cause are
  truthful, while richer reporting would be a separate approved reporting lane.

## Rollback

Revert commit `Repair selective 1h tracking handoff`. No migration, data repair,
or historical queue-row mutation is needed.

## Next permitted lane

Repeat the selective-1h operator-readiness review only. A PASS there still does
not itself authorize a live proof; proof execution requires a separate explicit
operator authorization.
