# Printer V1 V2-9.8B Four-Token Independent Rereview

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_INDEPENDENT_REREVIEW_BLOCKED_TERMINAL_AND_ACCOUNTING_COMPLETENESS`

This rereview is static/read-only apart from this documentation commit. It authorizes no migration application, operational DB mutation, source fetching, Scheduler runtime, four-token proof, authorization, 12h/24h work, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Reviewed identity

- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Rereview baseline: `55bf7d87a4a5277ba28be063359151ee6af4744d`
- Repair closeout HEAD: `64c4142eb29479061fb959badd9d23a1aa0c86e4`
- GitHub confirms the repair is seven commits directly ahead of the rereview baseline with no ancestry drift.
- GitHub exposes no workflow runs/status checks for the repair HEAD; Codex-local test counts remain supporting evidence, not independent CI evidence.

## Original three review blockers

### 1. Wake ordering — PASS

The repair adds a canonical factory-loop test that enters `run_one_command_15m_factory(...)`, places lifecycle work at +100s while cycle-2 admission remains at +300s, intercepts the real sleep boundary, and proves the loop wakes at 100s.

The GREEN routes future lifecycle, admission/rearm, and proof-deadline boundaries through `next_four_token_factory_wake(...)`, preserving lifecycle tie priority and removing the prior dependency on `recheck_on_lifecycle_change` for ordinary future lifecycle work.

### 2. Durable production accounting owner — PARTIAL PASS / COMPLETENESS BLOCKER REMAINS

The repair correctly removes caller-authored source/Scheduler totals. `build_four_token_cycle_accounting_package(...)` now derives exact two-slot ownership, cycle-scoped factory steps, stage-scoped Scheduler ownership, and source-request attribution from durable rows. Gate H consumes this production adapter.

However, the adapter marks `structurally_safe=True` without proving the existing two-token through-4h stage/accounting completeness required by the frozen design. Its focused test intentionally passes when only two opening `snapshot_00` steps exist. It does not require exact WINDOW_15M / WINDOW_1H / WINDOW_4H Scheduler correspondence as applicable, canonical two-token stage evidence, quality consistency, or slot disposition before returning a structurally-safe cycle package.

As a result, `aggregate_four_token_cycle_acceptance(...)` can accept two cycle packages before the through-4h lifecycle evidence exists. This is not sufficient for the designed four-token through-4h capacity proof.

### 3. Operational SQLite owner — PASS

The later-cycle identity path now uses `connect_operational(...)` and `short_write_transaction(...)`. Permanent-supply/holder/evidence preparation occurs before the write transaction; only neutral token/pair identity writes occur inside it; lineage is read afterward; and the connection is closed explicitly. The neutral `token_status=NULL` rule remains intact.

## Blocker A — two-phase terminal helpers are not wired into the canonical factory terminal path

Gate G implemented `reconcile_four_token_cycle_terminal(...)` and `finalize_four_token_shared_terminal(...)`, but the canonical `run_one_command_15m_factory(...)` terminal/finally path does not call them.

Current proof-mode factory finalization still follows the legacy run-global path:

- `_cancel_pending(...)` for the whole factory run;
- run-global continuation cleanup;
- run-global discovery cleanup using the original cycle id;
- run-global tracking lifecycle reconciliation;
- final shared factory-run report/status update;
- connection close/return.

The frozen integration design requires, in proof mode:

1. Phase A cycle-local reconciliation for each admitted cycle without terminalizing shared run/campaign/lease;
2. Phase B shared terminal reconciliation only after every admitted cycle is terminal, exactly once.

The existing helper `finalize_four_token_shared_terminal(...)` also requires exactly two cycle rows. That cannot close the lawful honest-block path where cycle-2 discovery fails before admission and only cycle 1 was admitted. The active design explicitly requires that path to end as an honest blocked capacity proof with lawful cleanup and no retry/successor.

## Blocker B — accounting package must reuse/retain canonical two-token lifecycle completion evidence

The production cycle adapter must not treat mere ownership consistency as through-4h structural completion.

Before a cycle package may set `structurally_safe=True` for aggregate proof acceptance, it must retain/verify the existing two-token accounting evidence required by the design, including as applicable:

- exact selected pair;
- exact WINDOW_15M, WINDOW_1H and WINDOW_4H Scheduler/window correspondence;
- canonical two-token required stage/accounting evidence;
- quality consistency;
- slot disposition;
- cycle-local source/Scheduler attribution;
- exact cycle id and shared factory-run id.

Reuse/factor the existing full-run accounting owners; do not invent a second stage policy or copied required-stage set.

A focused negative test must prove that a cycle with only opening/15m-planned work cannot be emitted as a structurally-safe through-4h package or accepted by aggregate proof acceptance.

## What remains accepted

Preserve without redesign:

- neutral identity projection;
- permanent GraduatedSupply later-cycle ownership;
- durable pre-admission one-shot attempt;
- fresh pre/post-discovery health checks;
- cycle-aware step namespace and request accounting;
- exact stage-scoped Scheduler ownership;
- cycle-local 15m/1h/4h routing;
- fixed canonical wake ordering;
- canonical operational SQLite ownership;
- public two-token defaults/capacity/provider ceilings.

## Minimum repair before next rereview

1. RED -> GREEN canonical proof-mode terminal integration test that executes the real factory terminal path and proves Phase A per-cycle then Phase B shared once.
2. Cover both terminal shapes:
   - successful two-cycle four-token completion;
   - honest blocked pre-admission path with only cycle 1 admitted and no cycle-2 retry/successor.
3. RED -> GREEN accounting-completeness test proving opening-only/partial lifecycle state cannot produce a structurally-safe through-4h package.
4. Production accounting package must reuse/factor existing two-token full-run/stage/quality/slot-disposition owners and keep expected capacity 2.
5. Gate H must exercise the real complete cycle-package path; do not fake through-4h completeness by hand-authored flags.
6. Focused directly affected four-token/factory/full-run/standard-4h tests, `py_compile`, and `git diff --check`.
7. Preserve known unrelated baseline failures as documented facts.

## Money-usefulness contribution

Closing these final gaps ensures the four-token proof can actually demonstrate four overlapping through-4h trajectories without premature shared cleanup and without declaring capacity success from incomplete lifecycle evidence.

## What this still does not unlock

- migration 055 application;
- proof readiness/authorization/runtime;
- 12h/24h activation;
- retrieval;
- paper decisions or financial actions.

## Stop boundary

Repair only the terminal integration and accounting-completeness gaps, then stop for independent rereview. Do not apply migration 055 or begin operational readiness, authorization, or runtime.