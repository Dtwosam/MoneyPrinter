# Printer V1 V2-8 4h Readiness Review

## Status

`V2_8_4H_READINESS_PASS`

Printer is ready for a narrow, one-token `WINDOW_4H` runtime implementation
lane. It is not ready to run or prove 4h collection today. The cadence and
continuity foundations are deterministic and reusable, while the runner,
scheduler integration, close/audit path, context refresh plan, and replay
reporting still require implementation and focused proof.

This review is audit and design only. It did not activate long windows, execute
runtime or scheduler work, call a source, mutate a database, or begin a 4h
proof.

## Source Stack And Scope

This review started from commit
`b34e2e7 Establish V2-7.2 long-window continuity foundation` and used the
active Printer V1 source stack:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`.

The review also used:

- the V2-7 bounded continuous 1h proof closeout;
- the V2-7.1 long-window cadence foundation closeout;
- the V2-7.2 chained continuity foundation closeout;
- the applicable Solana Builder source-governance README and Source Governor
  evidence rules.

Upstream-provider behavior not already represented by the approved adapters and
governed contracts remains `UNKNOWN_REQUIRES_RESEARCH`. No new provider is
needed for the proposed implementation scope.

## Readiness Verdict

The approved 4h cadence and 1h-to-4h continuity contracts are complete enough
to prevent architecture invention during a narrow implementation lane. The
current production command cannot execute that contract yet. A PASS here means
"ready to implement under the design below," not "4h collection is active."

The existing staged Lane I 4h classifier must not be repaired into the new
runtime authority. It is a historical, pure dictionary classifier with a
two-snapshot minimum, a full 240-minute standalone-duration assumption, no
current-run predecessor resolution, and no scheduler or source path. Its
statement that 4h evidence cannot continue from a 1h window conflicts with the
adopted V2-7.2 chained-continuity contract. Preserve it for historical fixture
compatibility, but replace its production role with the shared cadence,
continuity, context, and audit architecture.

## Current Path Audit

| Area | Current state | Readiness finding |
|---|---|---|
| 4h runner | Only `lane_i_4h_staged_memory_factory.py`; pure dict-in/dict-out | No production 4h runner exists; new narrow integration is required. |
| Cadence | Authoritative FAST/NORMAL policies exist in `cadence_policy.py` | Ready and must remain unchanged. |
| Continuity plan | Disabled 1h-to-4h plan derives exact predecessor, close snapshot, deadline, lane, and count | Ready for runtime wiring; activation is deliberately false today. |
| Predecessor resolution | Current-run, exact token/pair/lane, terminal and unused predecessor resolver exists | Ready and must be the only planning entry point. |
| Terminal stop | Replay-safe token-local block marker cancels only matching pending long jobs | Ready for reuse. |
| Scheduler plan | No 4h run-step planner or handlers exist | Missing implementation. |
| Snapshot collection | Existing governed token snapshot path is proven for shorter windows | Reuse is appropriate; it must consume 4h policy values and fixed deadline. |
| Context collection | The one-command close path has governed market/chain, safety, quote, optional holder, chart, and flow evidence | Reusable components exist, but no 4h opening/closing refresh schedule exists. |
| E2Q | Accepts 15m and genuine 1h; explicitly blocks 4h | Must add genuine 4h structural and continuity audit. |
| Lane Q | Hard-coded to `WINDOW_15M` and 900 seconds | Must be generalized through window policy or given a shared 4h guard. |
| Lane K | Current wiring is 15m-specific | Must gain a 4h-safe promotion path that consumes E2Q and Lane Q without bypass. |
| Cleanup | Central Scheduler cancellation and zero-running-job checks exist | Reuse, with 4h step kinds included. |
| Replay | Run ledger, exact step keys, window linkage, and terminal block markers exist | Reuse, but deterministic 4h report-only replay must be tested. |
| Real collection gate | Both 4h policies have `enabled_for_real_collection=False` | Correct; remains false until implementation tests pass and a proof lane is approved. |

## Approved Cadence

The V2-7.1 values are authoritative and are not redesigned by this review.
Counts include the first continuation snapshot and the forced closing snapshot.

| Lane | Continuation | Nominal interval | Clean max gap | Dirty gap | Blocked at | Expected snapshots |
|---|---:|---:|---:|---:|---:|---:|
| `TRACK_FAST` | 10,800s | 180s | 225s | `>225s and <360s` | `>=360s` | 61 |
| `TRACK_NORMAL` | 10,800s | 360s | 450s | `>450s and <720s` | `>=720s` | 31 |

The fixed 4h deadline is the exact predecessor 1h close plus 10,800 seconds.
Neither delayed planning nor a delayed first 4h snapshot may move that deadline.
The first transition snapshot must satisfy the same lane-specific clean, dirty,
and blocked boundaries.

## Continuity And Quality Contract

A future 4h runtime may proceed only after
`resolve_current_run_long_predecessor()` resolves exactly one predecessor with:

- the same run, token, pair, and tracking lane;
- `WINDOW_1H` kind and terminally closed status;
- the exact closing snapshot referenced by the successful current-run close
  step;
- no prior successor consumption;
- no existing token-local terminal block.

The successor must preserve the predecessor window ID and closing snapshot ID,
capture a real first continuation snapshot, and use the fixed policy deadline.
Manual IDs, historical windows, identity changes, consumed predecessors,
interpolation, aggregation, restarts, and clock resets remain rejected.

Quality behavior remains fail closed:

- CLEAN requires the exact expected count, full anchored 10,800-second duration,
  every gap within the clean maximum, a fresh forced close, complete traceable
  context, and all existing Lane Q/E2Q/Lane K safety gates.
- DIRTY permits only the already approved one-missing-snapshot or dirty-gap /
  dirty-close cases and forces `do_not_train = 1`.
- BLOCKED applies at the transition or cadence block threshold, with two or more
  missing snapshots, insufficient anchored duration, missing/stale closing
  evidence, identity/provenance failure, or structural audit failure. It creates
  no quality successor and terminally stops only that token.
- No missing observation is interpolated, and zero clean memory remains valid.

## Context Refresh Design

The smallest bounded plan reuses the approved one-command adapters and splits
their current close-only bundle across the successor boundaries:

1. At the first real 4h continuation snapshot, the same scheduler-owned step
   collects one governed market/chain context response and one exact-target
   ENTRY realism quote. Exact predecessor close context may be linked for audit,
   but it does not replace these opening observations.
2. Normal token snapshots continue at the lane cadence. Trading Flow and
   Chart/Volatility are derived from the exact persisted snapshot sequence; they
   add no independent source loop.
3. Immediately before the forced deadline snapshot, the scheduler-owned close
   step collects one governed market/chain refresh, one exact-target safety
   response, and one exact-target EXIT realism quote.
4. If the safety response cannot establish holder concentration, exactly one
   governed public Solana RPC holder fallback is allowed for the token. It has
   zero retries and no endpoint rotation.
5. Every response is bound to the same run/token/pair/window. Missing, stale,
   failed, mismatched, conflicting, or untraceable critical context blocks clean
   promotion rather than extending the deadline or triggering a retry.

This produces five planned context calls and at most one conditional holder
call. Bundling opening context into the first snapshot job and closing context
into the forced-close job preserves Central Scheduler ownership without adding
an independent timed loop. Existing source-specific freshness rules still
apply at audit time; this review does not relax them.

## Realistic One-Token Costs

The V2-7.1 `cadence_resource_budget()` value counts token snapshot requests
only. It is not the total Source Governor ceiling. The future runner must report
the following categories separately.

| Cost | FAST | NORMAL | Notes |
|---|---:|---:|---|
| Token snapshot requests | 61 | 31 | Includes first continuation and forced close. |
| Market/chain context refreshes | 2 | 2 | Opening and closing boundaries. |
| Safety refreshes | 1 | 1 | Exact-target preclose evidence. |
| ENTRY/EXIT realism requests | 2 | 2 | ENTRY at opening, EXIT at close. |
| Conditional holder fallback | 0-1 | 0-1 | Public/read-only RPC, one attempt. |
| 4h phase Source Governor total | 66-67 | 36-37 | No retries. |
| Discovery overhead | 0 new / up to 2 carried | 0 new / up to 2 carried | Continuation must not rediscover; full-run accounting retains the original bounded discovery cost. |
| Full-run ceiling including discovery | 69 | 39 | Conservative hard ceiling with holder fallback. |
| Planned 4h scheduler rows | 61 | 31 | Context is owned by opening/close jobs. |
| Cleanup capacity reserve | 2 | 2 | Headroom for terminal cleanup/reporting; not evidence calls. |
| 4h scheduler hard ceiling | 63 | 33 | Excludes the already-created discovery handoff row. |
| Full-run scheduler accounting ceiling | 64 | 34 | Includes at most one historical/cancelled discovery handoff row. |

The phase must safe-stop before a projected call or row breaches its ceiling.
Public RPC rate limiting is a token-local evidence failure: it may make safety
unknown and the window dirty/blocked, but it must not rotate endpoints, consume
another token, or cause repeated work. The one-token scope prevents cross-token
starvation in the first proof.

## Narrow Implementation Scope

The approved next implementation lane may do only the following:

1. Extend the existing one-command run ledger and report for one automatic
   current-run `WINDOW_1H -> WINDOW_4H` handoff.
2. Call the existing current-run predecessor resolver; accept no manual window,
   snapshot, token, or pair linkage.
3. Add policy-derived 4h snapshot and close run steps plus Central Scheduler
   handlers, using the exact 61/31 counts and fixed deadline.
4. Reuse the existing governed snapshot and context collectors under the
   budgets above.
5. Add genuine 4h E2Q validation, shared Lane Q integrity/cadence validation,
   and a Lane K path that cannot bypass either result.
6. Add 4h reporting, token-local cleanup, interruption recovery, and report-only
   replay with no duplicate calls, jobs, snapshots, windows, episodes, or
   fingerprints.
7. Keep 4h real collection disabled by default; permit it only in explicit,
   operator-approved proof mode against an isolated DB after focused tests pass.

The implementation should extend the proven shared one-command, cadence, and
continuity architecture. It should not expand the historical staged Lane I
classifier into a second runtime.

## Tests Required Before Runtime

Focused fixture and temporary-DB tests must prove:

- both lane plans derive exact interval, count, gap, close, request, and scheduler
  values from policy;
- exact current-run predecessor and closing-snapshot resolution;
- wrong run/token/pair/lane/kind, manual/historical linkage, consumed predecessor,
  and prior terminal-block rejection;
- clean, dirty, and blocked transition boundaries for FAST and NORMAL;
- fixed deadline despite delayed planning or first snapshot;
- exact 61/31 cadence, one/two missing snapshots, gap boundaries, duration, and
  forced-close freshness;
- opening and closing context schedule, target matching, freshness, provenance,
  holder fallback cap, and source-budget stops;
- E2Q, Lane Q, and Lane K agreement for clean, dirty, and blocked 4h evidence;
- chart and safety blockers remain independent and fail closed;
- interruption recovery, token-local cancellation, no repeated blocked retry,
  and zero running jobs after stop;
- replay creates no duplicate source calls, jobs, snapshots, windows, episodes,
  or fingerprints;
- 5m/15m/1h behavior and all V2-7.1/V2-7.2 contracts remain unchanged;
- 12h/24h remain disabled;
- retrieval and every financial table remain at zero delta.

## Bounded Proof Requirements

Only after implementation and all focused tests pass may a separately approved
proof run once with:

- a fresh isolated proof DB and backup; never the persistent DB;
- one autonomously selected Solana memecoin carried through the same current run;
- the exact terminal `WINDOW_1H` predecessor; no manual mint or linkage;
- one 10,800-second 4h continuation and no second attempt;
- FAST or NORMAL cadence determined by the stored lane;
- maximum 69 full-run governed requests and 64 scheduler rows;
- zero automatic retries, endpoint rotation, budget expansion, or post-start
  code change;
- a 11,700-second 4h-phase wall-clock cap, including bounded cleanup;
- persistent DB hash and critical counts before and after;
- report-only replay after completion.

The proof must stop immediately and honestly for identity mismatch, unresolved
predecessor, transition block, projected budget breach, DB isolation failure,
source-governor or scheduler-boundary failure, blocked cadence, missing forced
close, or inability to clear running jobs. A naturally dirty or blocked outcome
is acceptable when the runtime, reporting, cleanup, replay, and locks behave
correctly.

The report must include predecessor and successor IDs, token/pair/lane, first and
close snapshots, transition and all cadence gaps, fixed deadline and drift,
context and safety evidence, every source request/response/failure, scheduler
states, quality/audit decisions, cleanup, replay, all DB deltas, and the exact
stop reason.

## Persistent DB, Replay, And Locks

The first 4h proof must use an isolated copy and confirm the persistent DB hash
and critical row counts are unchanged. Replay is report-only and must add zero
source requests, responses, failures, scheduler rows, snapshots, windows,
episodes, fingerprints, retrieval rows, or financial rows.

The lane does not unlock 12h or 24h, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, funds, signing,
execution, paid APIs, scores, ranks, confidence, weights, embeddings, or
vectors. The 5m window remains support-only. Source Governor and Central
Scheduler remain mandatory boundaries.

## Money Usefulness

A correctly chained 4h window measures whether a first-hour move continues,
consolidates, decays, or fails without silently changing asset identity or
resetting time. The proposed controls make that longer outcome evidence useful
for future memory while preventing sparse, stale, mismatched, or rate-limited
observations from being promoted as clean history.

## What V2-8 Improves

- Converts the deterministic cadence and continuity foundations into one
  implementation-ready boundary.
- Separates snapshot count from total source and scheduler cost.
- Defines when context is refreshed and how holder fallback is bounded.
- Names the exact E2Q, Lane Q, Lane K, runner, cleanup, and replay work still
  required.
- Supplies a one-token proof ceiling and objective stop conditions.

V2-8 does not implement, activate, or prove any long window and does not change
memory quality or financial policy.

## Functionality Risks / Setbacks / Efficiency Blockers

1. No production 4h runner, scheduler plan, close handler, or one-command handoff
   exists yet.
2. E2Q blocks 4h, Lane Q is 15m-only, and Lane K is 15m-specific. All three must
   be aligned before any clean 4h promotion is possible.
3. The historical staged 4h classifier conflicts with the adopted continuation
   duration and snapshot count. It must not become a parallel runtime authority.
4. The 66-67-call 4h phase has not been proved against free/public source rate
   limits. The single holder fallback is especially vulnerable to public RPC
   rate limiting and must fail closed.
5. The opening/closing context schedule is designed but not implemented or
   proved. Unsupported provider behavior remains `UNKNOWN_REQUIRES_RESEARCH`.
6. The V2-7 proof produced dirty/partial memory and exposed a secondary elapsed
   reporting inconsistency. Future 4h reporting must use anchored duration and
   canonical cadence output only.
7. Interruption after hours of collection increases replay and cleanup risk;
   deterministic step keys and projected-budget checks require direct tests.
8. This review covers one token only. Multi-token 4h capacity, starvation, and
   fairness remain out of scope.

## Final Verdict And Next Step

`V2_8_4H_READINESS_PASS`

The approved cadence, continuity, isolation, budget, context, quality, cleanup,
replay, and proof boundaries are sufficiently explicit for implementation
without redesign. Runtime itself remains absent and disabled.

The next recommended lane is a narrow
`V2-8.1 - One-Token 1h-to-4h Runtime Implementation` that implements only the
scope above, runs focused deterministic tests, and stops before any live proof.
It requires explicit operator approval and must not begin automatically.
