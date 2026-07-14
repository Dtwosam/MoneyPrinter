# Printer V1 V2-7 Bounded Continuous First-Hour Proof Closeout

## Status

`V2_7_BOUNDED_1H_PROOF_PASS`

V2-7 proved one bounded, autonomous, same-run lifecycle from support-only 5m evidence through a continuous 15m window and an immediate 45-minute continuation to a `WINDOW_1H` close. The proof did not create clean memory and does not activate any later lane. The 15m result remained dirty on an independent chart gate, and the 1h result remained partial.

## Scope And Anchors

- Starting implementation anchor: `29c22c2 Integrate continuous lifecycle runtime`.
- Readiness repair commit: `f15da82 Repair V2-7 continuous first-hour readiness`.
- Proof run ID: `ae196d79-9d79-49fd-af3b-32f25a412d02`.
- Selection batch ID: `b632e4a7-35f9-4f34-bfd6-29bccb0722de`.
- Selection seed: `9b9b8d36ad177022e88a957d4049a166`.
- Proof DB: `data/printer_v1_v2_7_bounded_continuous_1h_proof.sqlite3`.
- Proof backup: `data/printer_v1_v2_7_bounded_continuous_1h_proof.backup.sqlite3`.
- Mode: `PROOF_ONLY`, operator-approved, one autonomous token, `WINDOW_15M` main-window scope.
- The proof and backup DBs and operator-run JSON are local evidence only and are not committed.

## Readiness Repair

The readiness gate added the minimum current-run linkage and lifecycle controls:

- The CLI exposes the bounded `--continuous-first-hour` mode.
- Continuous mode requires exactly one autonomously selected token.
- The resolver accepts only the exact fresh preceding 15m window and closing snapshot attached to the current run step.
- Manual, historical, mismatched, and already-consumed continuation linkage is rejected.
- The same run, token, pair, and tracking lane are handed into continuation automatically at the 15m close.
- The continuation deadline is fixed at `15m close + 2700 seconds`.
- `CONTINUITY_BLOCKED` is terminal for that token and cancels only its pending continuation jobs.
- Support-only 5m evidence retains exact run, token, pair, lane, and snapshot boundaries.
- Replay remains idempotent across jobs, snapshots, windows, episodes, and fingerprints.

No source contract, classification threshold, memory-quality rule, retrieval path, or financial path was loosened.

## Tests And Checks

Focused readiness and nearby regression coverage passed with normal summaries:

- V2-7 readiness: `5 passed`.
- V2-6.3 continuous runtime integration: `8 passed`.
- V2-6.2 continuity deadline/support/15m checks: `23 passed`.
- V2-6.2 current-run DB resolver checks: `3 passed`.
- V2-6.2 clean exact E2O check: `1 passed`.
- V2-6.2 remaining E2O checks: `4 passed`.
- V2-6.2 downstream-lock check: `1 passed`.
- Cadence checks: `22 passed`.
- One-command focused groups: `16 passed` total.
- X12 Source Governor check: `1 passed`.
- X12 scheduler, hard-lock, and cadence checks: `3 passed`.
- E2O focused checks: `5 passed`.
- E2Q focused checks: `5 passed`.
- Scheduler focused checks: `5 passed`.
- Python compilation check: passed.
- `git diff --check`: passed before the proof.

The suite was deliberately split into stable focused groups because the local Windows pytest environment can terminate larger accumulated temporary-DB invocations without a summary. No test was skipped or weakened; only pytest cache warnings remained.

## Proof Setup

The production one-command path ran exactly once with these effective constraints:

- one autonomous selected token;
- at most two discovery requests;
- five-second source timeout;
- zero automatic retries;
- 4,200-second total cap;
- Source Governor for all live source requests;
- Central Scheduler for all timed snapshots and closes;
- no endpoint rotation and no post-start code or budget change.

The run started at `2026-07-14T13:01:37.219858+00:00`, finished at `2026-07-14T14:01:46.144122+00:00`, returned exit code 0, and stopped as `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`.

## Autonomous Selection

- Token ID: `18`.
- Mint: `7NTs9FPw7tP2Bfjcn8eAJZUr4ApG8n9ZbXkT7Adwpump`.
- Pair ID: `22`.
- Pair: `5SGH3r8p76VcHzzY1pxRwcELbehZxBRX1DBNZvLvdfsh`.
- Lane: `TRACK_FAST`.
- Eligible pool size: `26`.
- Discovery source/channel: governed GeckoTerminal trending-pool evidence.
- No mint list, manual candidate selection, fixture candidate injection, or identity editing was used.

## Continuous Lifecycle Evidence

### Support-Only 5m To 15m

- Support window ID: `158`, `WINDOW_5M_MICRO_EVENT`.
- Main 15m window ID: `157`, `WINDOW_15M`.
- Shared opening snapshot ID: `1013`.
- First valid snapshot: `2026-07-14T13:01:40.281924+00:00`.
- 15m closing snapshot ID: `1028` at `2026-07-14T13:16:43.403337+00:00`.
- Evidence duration: `903.121` seconds.
- Snapshot count: `16`.
- Snapshot gaps: 15 gaps from `59.690150` to `62.324272` seconds.
- First post-5m gap: `59.914` seconds.
- Continuity: `CONTINUITY_CONTINUOUS`.

The 5m window remained support-only and did not substitute for the main 15m evidence.

### 15m To 1h Continuation

- Continuation window ID: `159`, `WINDOW_1H`.
- Continuation linked to 15m window ID `157` and closing snapshot ID `1028`.
- Enqueued at the 15m close: `2026-07-14T13:16:43.403337+00:00`.
- First continuation snapshot ID: `1029` at `2026-07-14T13:16:45.017742+00:00`.
- Transition gap: `1.614405` seconds, `TRANSITION_CLEAN`.
- Fixed expected and actual deadline: `2026-07-14T14:01:43.403337+00:00`.
- Deadline drift: `0.0` seconds.
- Final snapshot ID: `1052` at `2026-07-14T14:01:44.836831+00:00`.
- Continuation snapshot count: `24`.
- Continuation gaps: 23 gaps from `115.820605` to `118.551477` seconds.
- Cadence: the required `TRACK_FAST` 24-snapshot continuation shape was achieved.
- Overall lifecycle continuity: `CONTINUITY_CONTINUOUS`; exact run/token/pair/lane identity held.

## Context, Safety, And Memory Results

The 15m close attached all shared context areas through governed evidence:

- Market regime: `NEUTRAL`, clean payload.
- Solana chain heat: `SOLANA_WARM`, clean payload.
- Safety: `SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY`; exact-target governed safety evidence was present, but the safety action remained fail-closed for clean promotion.
- Liquidity/exit realism: entry and exit routes available with acceptable liquidity, slippage, and price-impact context.
- Trading flow: `FLOW_CHOPPY` / `PRESSURE_MODERATE_INFLOW`, partial/caution context.
- Chart/volatility: clean chart payload, but `CHART_CONTEXT_DO_NOT_TRAIN` remained the independent clean-promotion blocker.
- 5m support: `WICK_ONLY_PUMP`, support-only.
- Episode outcome: `HELD_TO_15M_CONSOLIDATED`.

Results:

- 15m window `157`: `DIRTY_MEMORY`, no clean promotion; blocker `CHART_OR_VOLATILITY_NOT_CLEAN`.
- 5m window `158`: `SUPPORT_EVIDENCE`, never a main outcome window.
- 1h window `159`: `PARTIAL_MEMORY`; E2O created the bounded continuation and E2Q reported `E2Q_AUDIT_CLEAN_CANDIDATE`, but no clean row was promoted.
- Clean memory rows: `0`.
- Memory fingerprints: `0` delta.
- Lane K completed with the E2Y set gate not passed; no retrieval or decision capability was activated.

Zero clean memory is an honest valid result for this proof. The pass concerns lifecycle continuity, bounded execution, fail-closed quality handling, and lock preservation.

## Scheduler And Budgets

- Run-step jobs: `40`; total scheduler-row delta: `41`, including one cancelled discovery handoff.
- `15` first-15m snapshot jobs succeeded.
- `23` continuation snapshot jobs succeeded.
- `2` memory-window close jobs succeeded.
- Support-only 5m work succeeded as its run step.
- Failed run steps: `0`; cancelled continuation steps: `0`; pending/running run steps after stop: `0`.
- Running jobs after stop: `0`.
- Governed run requests: `44` against ceiling `47`.
- Per-token governed requests: `44` against ceiling `45`.
- Holder RPC fallbacks: `0` against ceiling `1`.
- Automatic retries: `0`.
- Proof DB source deltas: `+46` requests, `+46` responses, `+0` failures, including discovery and lifecycle context/snapshot requests.

## Replay And Database Safety

One report-only replay read the completed run and returned the same run ID, `COMPLETED` status, and stop reason. Comparison with the post-proof counts showed zero additional source requests, responses, failures, snapshots, scheduler jobs, or memory windows.

Persistent DB SHA-256 before and after:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Persistent critical counts were unchanged:

- source requests/responses/failures: `1118 / 1071 / 47`;
- token snapshots: `1012`;
- memory windows: `156`;
- retrieval queries/matches: `10 / 0`;
- paper decisions: `2`;
- paper positions/trade events/trade audits: `0 / 0 / 0`.

Proof DB allowed deltas:

- token snapshots `+40`;
- memory windows `+3`;
- scheduler jobs `+41`;
- discovery candidates `+1`;
- selection batches/items `+1 / +26`;
- tracking queue `+1`;
- market regime and chain heat snapshots `+2 / +2`;
- safety evidence/composites/contributions `+1 / +1 / +1`;
- paper quote evidence `+2`.

Proof DB locked deltas were all zero:

- memories/fingerprints `0 / 0`;
- retrieval queries/matches `0 / 0`;
- paper decisions `0`;
- positions `0`;
- trade events `0`;
- paper trade audits and audit reports `0 / 0`;
- no BUY, SELL, HOLD, or PnL path was activated.

## Residual Risks And Blockers

1. The 1h close record reports the policy anchor duration as exactly `2700.0` seconds and zero deadline drift, while a secondary first-continuation-snapshot-to-final-snapshot calculation reports `2699.819089` seconds and retains a stale `not_eligible_reason`. E2Q nevertheless classified the anchored window as a clean candidate. This is a reporting/measurement inconsistency to carry forward; it did not create clean memory or unlock any downstream capability.
2. The 15m chart gate produced `CHART_CONTEXT_DO_NOT_TRAIN`, so this run did not prove clean-memory yield.
3. The 1h result remained `PARTIAL_MEMORY`, and the historical E2Y set gate remained unmet. V2-7 does not activate generalized 1h memory production.
4. Larger token counts, long-run rate limits, and later-window operation remain outside this one-token bounded proof.

## Money-Usefulness Contribution

V2-7 proves that Printer can preserve one exact asset identity through a real first-hour observation without manual window reuse, align support and main evidence to one opening stream, honor independent scheduler deadlines, and stop with honest dirty/partial outcomes. That reduces false historical learning caused by broken continuity while preserving capital-protection locks.

## Final Verdict

`V2_7_BOUNDED_1H_PROOF_PASS`

The bounded lifecycle, same-run linkage, cadence, fixed deadline, fail-closed quality handling, replay behavior, scheduler cleanup, proof isolation, and downstream locks passed. This verdict does not claim clean-memory creation, retrieval readiness, paper-decision readiness, or any financial unlock.

V2-8 was not started. The next action is operator review of this closeout and explicit approval of any later lane, with the 1h elapsed-reporting inconsistency carried as a named follow-up risk.
