# Printer V1 V2-9.8B Four-Token Final Integration Independent Review

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_FINAL_INTEGRATION_INDEPENDENT_REVIEW_BLOCKED_REARM_ACCOUNTING_AND_DB_OWNER_GAPS`

This review is static/read-only apart from this documentation commit. It authorizes no migration application, source fetching, operational runtime, four-token proof, proof authorization, 12h/24h work, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Reviewed identity

- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Implementation baseline: `16982ae7f7f15a270741384b563ff4b4b374bc06`
- Claimed implementation closeout HEAD: `b46a58ba6594eeb83aa28aff4822391b7873381c`
- GitHub confirms the closeout HEAD is directly descended from the baseline with no ancestry drift.
- GitHub exposes no commit status checks or workflow runs for the closeout HEAD, so Codex-local test counts are treated as supporting evidence rather than independent CI evidence.

## What passed review

The implementation substantially follows the frozen design in these areas:

- neutral token/pair identity projection with new `token_status` left NULL before activation;
- reuse of the permanent `GraduatedSupply` owner for the later cycle;
- cycle-1 legacy and cycle-2 `c0002` step namespaces;
- derived four-token Scheduler ceiling rather than copied numeric authority;
- pre-created proof `WINDOW_15M` campaign windows and stage-scoped Scheduler ownership;
- fresh admission health projection before discovery and again after `PAIR_READY` before atomic cycle admission;
- Scheduler-owned cycle identity for claimed proof lifecycle jobs;
- cycle-local 15m and standard 1h/4h barrier routing;
- two-phase cycle-local/shared terminal helpers;
- public `four_token_proof_controller=None` default preserved.

These accepted parts should be preserved. Do not redesign them during repair.

## Blocker 1 - healthy admission rearm can sleep past earlier lifecycle work

The frozen design requires the single factory wake to be:

```text
min(next due lifecycle work, next lawful admission opportunity, proof deadline)
```

`next_four_token_factory_wake(...)` implements that rule correctly. However, `decide_four_token_admission_disposition(...)` reconstructs its own DEFER candidates. For future lifecycle work it adds `next_due_work_at` only when `health_projection.recheck_on_lifecycle_change` is true.

A fully healthy authoritative health projection normally sets `recheck_on_lifecycle_change=False`. During the normal `<300s` spacing defer, the disposition can therefore become `REARM` at the 300-second admission boundary even when a lifecycle Scheduler job is due earlier.

The canonical factory loop handles `REARM` by sleeping directly to `disposition.at` and continuing. That can delay legitimate earlier lifecycle work and violates the frozen one-loop priority law.

Gate H did not prove this path: it exercised the component helpers directly and never executed `run_one_command_15m_factory(...)` through the real event-loop sleep/wake sequence.

### Required repair

Make the disposition/wake path use the existing authoritative wake result so every future lifecycle boundary participates regardless of whether health itself needs a lifecycle-change recheck. Preserve priority:

1. cancellation/lease/DB/shared-terminal stop;
2. due/future lifecycle work at its real boundary;
3. proof deadline;
4. fresh admission/rearm.

Add a real canonical-factory-loop test with:

- healthy 12-field projection;
- cycle-2 spacing still deferred;
- a lifecycle job scheduled before the 300-second admission boundary;
- proof that the factory wakes/runs lifecycle work first and does not sleep through it.

No busy polling or invented retry timer.

## Blocker 2 - final cycle accounting evidence is still caller-synthesized

Design decision 9 requires a multi-cycle accounting adapter that builds one existing-style two-token accounting result per admitted cycle from durable Scheduler-owned facts, including exact selected targets, lifecycle Scheduler correspondence, source/Scheduler attribution, quality/slot disposition, cycle id, and shared factory-run id.

The implementation correctly made the standard-four-hour budget helper cycle-aware and strengthened `aggregate_four_token_cycle_acceptance(...)` to validate two accounting-package dictionaries. But no production owner currently builds those final accounting-package dictionaries from durable cycle evidence.

Gate F constructs `accounting_package` by hand in the test. Gate H also manually supplies `source_requests` and `scheduler_jobs` before invoking aggregate acceptance. That proves the aggregate validator, not the required production accounting adapter.

### Required repair

Add/factor one proof-only production adapter that, for an exact Scheduler-owned cycle:

- starts from the existing two-token lifecycle/full-run accounting owners;
- scopes factory steps through `cycle_scoped_factory_step_ids(...)`;
- derives actual attributable source-request and Scheduler-job counts from durable ownership/evidence;
- retains `expected_token_capacity=2`;
- returns the exact package consumed by `aggregate_four_token_cycle_acceptance(...)`;
- fails closed on missing/extra/ambiguous ownership.

Gate H must consume two packages built by that real adapter, not hand-authored dictionaries.

Do not create a second accounting policy or copy canonical budget arithmetic.

## Blocker 3 - later-cycle operational identity writes bypass the canonical SQLite connection owner

`build_later_cycle_graduated_supply(...)` is wired into the operational four-token path. It opens a raw `sqlite3.connect(str(db_path))` before calling `ensure_neutral_token_pair_identity(...)`, which may write `printer_tokens` / `printer_pairs`.

The active Python Builder Guide requires operational connection creation to use the approved repository connection owner so busy timeout, foreign-key, row-factory, and transaction behavior do not drift. The repository already provides `connect_operational(...)` and `short_write_transaction(...)` for this purpose.

### Required repair

Use the canonical operational connection owner. Keep the neutral identity write in one short explicit write transaction after provider/holder I/O is finished. Do not hold a write transaction across source work, pacing, sleeps, or long computation. Read source lineage after the write transaction is released.

Preserve the neutral identity rule: no tracking queue, Scheduler work, cycle/window/memory creation, or TRACK_NORMAL transition at this stage.

## Test-evidence correction

The closeout statement that Gate H proved the canonical one event loop is too strong. Gate H validates a disposable composed graph and component seams, but it does not invoke the canonical factory function through the actual event-loop timing path.

The existing local results (`266 passed, 43 subtests passed`, Gate H `1 passed`, and the documented unrelated baseline public timing failure) are not rejected by this review. They are simply insufficient to close the three gaps above.

## Money-usefulness contribution

Closing these gaps preserves the intended benefit of overlapping four Solana memecoin trajectories in one factory while ensuring fresh-cycle admission can never steal timing from already-owed evidence work and that the resulting proof report is based on real attributable accounting rather than caller-authored totals.

## What this review does not unlock

- migration 055 application;
- operational four-token readiness;
- proof authorization or runtime;
- 12h/24h activation;
- retrieval;
- paper decisions or financial actions.

## Minimum repair proof before re-review

1. focused RED -> GREEN test for healthy spacing defer with an earlier lifecycle wake through the canonical factory loop;
2. focused RED -> GREEN tests for the production cycle-accounting adapter using durable ownership, plus ambiguity/peer-cycle isolation;
3. focused RED -> GREEN test proving the later-cycle identity write uses the canonical operational SQLite owner and leaves no write transaction across source work;
4. rerun the directly affected four-token/factory/standard-4h tests only;
5. `py_compile` touched production modules and `git diff --check`;
6. preserve the known unrelated baseline public timing failure as a documented baseline fact unless the repair changes that path.

## Stop boundary

Repair only these three review blockers. Stop after focused repair closeout and push the same branch for independent re-review. Do not apply migration 055 or begin readiness, authorization, or runtime.