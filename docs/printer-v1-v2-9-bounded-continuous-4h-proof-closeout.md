# Printer V1 V2-9 Bounded Continuous 4h Proof Closeout

## Final verdict

`V2_9_BOUNDED_4H_PROOF_FAIL`

Lane: `V2-9 - Bounded Continuous 4h Proof`

The lane has now used three authorized attempts and remains failed. The first
preparation attempt was blocked before runtime by an unmigrated proof schema.
Runtime Attempt 1 reached the 4h phase but failed after 24 of 31 NORMAL
snapshots and incorrectly reported `COMPLETED`. V2-9.1 repaired canonical proof
preparation, and V2-9.2 repaired the known 4h terminal and budget paths.
Separately approved Attempt 2 then failed during the initial FAST 15m
collection after four snapshots; cleanup was safe, but the final report
mislabeled a DexScreener transport stop as a budget stop even though both
applicable budgets were within limits. V2-9.3 repaired that early-failure and
unreached-phase accounting defect.

A third separately approved attempt (Attempt 3) then progressed further than
either prior attempt: it completed a full, clean FAST 15m window with governed
opening/closing context and a partial (9 of 24) FAST 1h continuation, all on
clean cadence with zero source failures. It never reached the 4h phase. Attempt
3 did not fail from a source error or a budget breach; its host execution
environment terminated the runtime process outright (external kill) while it
was asleep between two scheduled 1h-continuation snapshots, before any
internal exception handler, stop path, or final-report logic in the governed
runtime could run. No further diagnostic detail on the exact trigger is
available beyond the background-task infrastructure reporting the process as
`killed`. This is a new failure mode for this lane, distinct from a source
failure or a budget breach, and it left 15 run steps and their linked scheduler
rows abandoned in `PENDING` (never executed, never cancelled) on the isolated
Attempt 3 proof DB. No lock was left held, and the persistent DB and the
Attempt 3 pre-runtime backup remained byte-identical to their pre-runtime
state.

No fourth attempt occurred and none is authorized. This closeout does not
activate generalized 4h production or begin V2-10, 12h, 24h, retrieval,
decisions, positions, trades, audits, or PnL.

## Attempt history

### Blocked preparation attempt

The original V2-9 preflight copied an older persistent DB without applying all
canonical migrations. The proof copy lacked migration-028 run-ledger tables
`printer_memory_factory_runs` and `printer_memory_factory_run_steps`. Runtime
did not begin. V2-9.1 established the sole canonical preparation path: copy the
persistent DB to a fresh isolated target, apply all canonical migrations to the
copy only, validate the complete runtime schema, then create and byte-compare
the backup.

### Runtime Attempt 1

Attempt 1 autonomously selected a NORMAL token and continuously reached its
current-run WINDOW_1H predecessor. It then collected 24 of 31 4h snapshots
before DexScreener transport failed. Six remaining token-local jobs, including
the forced close, were cancelled. No WINDOW_4H successor was created and 4h
E2Q, Lane Q, and Lane K/E2Z did not run. Cleanup and report-only replay were
safe, but the runner incorrectly returned `COMPLETED` and conflated 4h-phase
ceilings with cumulative lifecycle usage. The lane closed FAIL at commit
`4bbb0d1`.

V2-9.2 subsequently made valid terminal 4h evidence and a completed audit path
mandatory for `COMPLETED`, separated phase and cumulative accounting, and added
projected pre-call and pre-job checks. That repair passed at commit `20763c0`.

### Runtime Attempt 2

Attempt 2 is the one separately approved proof after V2-9.1 and V2-9.2. It
started once and terminated once. It was not restarted or retried.

V2-9.3 subsequently gave the current-run ledger an authoritative first-cause
resolver: it now resolves the first genuine failed runtime step in scheduled
ledger order, marks whether that failure fell in `PRE_4H_15M`, `PRE_4H_1H`, or
`FOUR_HOUR`, and stops later phase/cumulative/cleanup accounting from
overwriting it. An unreached 4h phase is now reported explicitly as
not-started rather than as an exceeded budget. That repair passed at commit
`0baefc3`.

### Runtime Attempt 3

Attempt 3 is the one separately approved proof after V2-9.3. It started once
and its host process was terminated once by the execution environment. It was
not restarted or retried.

## Attempt 2 preflight

All pre-runtime gates passed:

- HEAD: `20763c0b874ca0fc96eef7bced8e1a7f4fee3158`;
- tracked tree: clean;
- free disk: `313,430,331,392` bytes;
- fresh proof and backup paths did not exist before preparation;
- the failed Attempt 1 proof and backup were not reused;
- V2-9.1 canonical preparation status: `PROOF_DB_SCHEMA_READY`;
- applied/canonical migrations: `29 / 29`, latest
  `029_composite_safety_evidence.sql`;
- integrity: `ok`; foreign-key errors: `0`; runtime schema issues: `[]`;
- required run-ledger tables, columns, indexes, checks, unique keys, and foreign
  keys: valid;
- prepared proof and backup SHA-256:
  `97893AFB6B3D649C9E3105F407D5C0C2A8D689F0A377D84FBFF70ED443FA92F6`;
- proof/backup byte-identical before runtime: true;
- persistent SHA-256 before runtime:
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`;
- V2-9.1 schema-readiness tests: `10 passed`;
- V2-9.2 terminal/budget tests: `10 passed`;
- WINDOW_12H and WINDOW_24H real collection: disabled for FAST and NORMAL.

The canonical preparation report recorded `sources_run=false` and
`scheduler_runtime_run=false`. No gate failed before runtime.

## Attempt 2 identity and lifecycle anchors

| Field | Observed |
| --- | --- |
| Run | `e119034c-17a2-42c0-91b5-3b3c400d270b` |
| Token | ID `18`; `2vvw3cSwibzGD6SgW9QzRaBdmjkYrvs218DUy6VWpump` |
| Pair | ID `22`; `5smCoCy9FVw3g1APyzyhxD2ozyAseWkozjmtgSpHjSjg` |
| Stored lane | `TRACK_FAST` |
| Selection seed | `137735914fce99b2db4a87be002a6fc1` |
| Eligible pool | `25` |
| Run start | `2026-07-15T15:50:32.732509+00:00` |
| First snapshot | `2026-07-15T15:50:34.795586+00:00` |
| Failure finish | `2026-07-15T15:54:41.127213+00:00` |
| Run finish | `2026-07-15T15:54:41.146511+00:00` |
| 5m / 15m / 1h / 4h window IDs | None / None / None / None |
| Exact current-run 1h predecessor | Not reached |
| 4h successor | None |

Identity and lane selection were autonomous. No mint, pair, predecessor,
snapshot, or window identity was manually supplied or linked. Same-run,
token, pair, and lane continuity remained internally consistent for the four
collected rows, but no lifecycle transition became eligible for evaluation.

## Cadence, duration, and continuity (Attempt 2)

FAST 15m collection expected 16 snapshots. Four current-run-ledger snapshots
were created: IDs `1013-1016`. Their gaps were:

`60.480669, 59.987700, 60.046476` seconds.

Maximum gap was `60.480669s`; observed snapshot span was `180.514845s`.
Snapshot 5 was attempted at its scheduled point and failed, leaving 12 expected
15m snapshots absent: one failed execution and 11 cancelled run steps.

The failed step was scheduled for `2026-07-15T15:54:34.795586+00:00` and began
`0.007688s` late. The 15m forced close remained fixed at
`2026-07-15T16:05:34.795586+00:00`; it was never extended, so deadline drift
was `0s`. Runtime stopped about `653.649075s` before that deadline. Closing
lateness and a valid 15m duration are unavailable because the forced close did
not run.

The expected 4h cadence for FAST was 61 snapshots at 180 seconds. Actual 4h
snapshots, gaps, missed count, duration, closing lateness, transition gap, and
deadline drift were respectively `0`, none, `61`, unavailable, unavailable,
unavailable, and unavailable because 1h and the 4h plan were never reached.
No WINDOW_1H predecessor or fixed `1h close + 10,800s` deadline existed.

Continuity therefore remained `CONTINUITY_UNKNOWN`; it did not pass, become
dirty, or bypass a gate.

## Source failure and terminal behavior (Attempt 2)

Discovery used two governed GeckoTerminal requests and received two successful
responses. Five governed DexScreener snapshot requests followed. The first four
received successful responses and created four snapshots. Request `1125` for
`t1_snapshot_04` produced no response and created source failure `48`:

- source: `dexscreener`;
- failure type: `dexscreener_transport_failure`;
- exact failure message:
  `<urlopen error _ssl.c:993: The handshake operation timed out>`;
- retry-after: none.

The failed run step preserved `dexscreener_transport_failure`, source request
`1125`, and failure `48`. The affected token's 11 remaining run jobs were
cancelled, including its 15m forced close. No other token existed. There was no
endpoint rotation and no second source execution. Scheduler `retry_count=1` on
the failed row records the failed execution transition; all other new rows have
`retry_count=0`, and no retry job or second request was created.

The run returned:

- DB status: `SAFE_STOPPED`;
- reported stop reason: `SAFE_STOP_BUDGET_CEILING_EXCEEDED`;
- per-token terminal status: `TOKEN_LOCAL_FAILED`;
- terminal window outcomes: `0`.

The safe stop and cleanup are valid, but the stop reason is not. The V2-9.2
4h terminal validator saw no long-window step, marked both 4h and cumulative
usage `available=false / within_ceiling=false`, and converted that absence into
a budget stop. It did not promote the earlier 15m source failure into the final
run reason. The exact transport reason survives in the step and source-failure
ledger, but not in the final stop reason. This is a reporting-classification
defect, not a real budget breach.

## Phase and cumulative budgets (Attempt 2)

Actual usage reconstructed from canonical DB deltas:

| Scope | Requests | Request ceiling | Scheduler rows | Scheduler ceiling | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| FAST 4h phase | 0 | 69 | 0 | 64 | Not reached; numerically within |
| FAST cumulative lifecycle | 7 | 116 | 17 | 105 | Within |

Cumulative requests were two discovery calls plus five snapshot calls.
Cumulative scheduler rows were one discovery handoff plus 16 planned 15m run
rows. The 4h projected guards were never reached. Holder fallback usage was
zero. Automatic retry executions were zero. Endpoint rotation was zero.

The final report's `four_hour_phase_usage` and `cumulative_lifecycle_usage`
objects both said `available=false` and `within_ceiling=false`. Those fields are
not honest accounting for this early stop: unavailable 4h evidence must not be
reported as an exceeded budget, and known cumulative usage must still be
reported against its policy-derived ceiling.

## Context, safety, realism, chart, and flow (Attempt 2)

The 15m forced close was cancelled, so WINDOW_5M support derivation and the
15m governed close context never ran. No opening/closing market-chain bundle,
safety close evidence, paper ENTRY/EXIT quote evidence, completed chart/flow
window evidence, or exit-realism conclusion was created for this run.

The four token snapshots were COMPLETE/CLEAN_DATA source rows, but they are not
a completed window and cannot establish clean memory, entry realism, exit
realism, chart outcome, or flow outcome. Nothing was promoted from partial
snapshot evidence.

## Scheduler and cleanup (Attempt 2)

Attempt 2 added 17 scheduler rows:

- one discovery handoff, cancelled after selection;
- four succeeded run snapshot jobs;
- one failed run snapshot job;
- 11 cancelled remaining run jobs.

The 16 run steps have the same `4 succeeded / 1 failed / 11 cancelled` shape.
After cleanup:

- pending/running run steps: `0`;
- running jobs: `0`;
- locks/owners left behind: `0`;
- forced close: cancelled;
- invalid successor windows: `0`.

Cleanup therefore behaved safely despite the failed terminal classification.

## E2Q, Lane Q, Lane K/E2Z, memory quality, and locks (Attempt 2)

No memory window was created. E2Q, Lane Q, and Lane K/E2Z were not reached and
were not bypassed. The run created no clean, partial, dirty, or do-not-train
memory outcome, no memory row, and no fingerprint. Run-local yield was
`clean=0, dirty=0, blocked=0, token_local_failed=1`.

Proof deltas remained zero for:

- memory windows, memories, and fingerprints;
- retrieval queries and matches;
- paper decisions;
- paper positions;
- paper trade events and trade audits;
- paper audit reports;
- paper quote evidence;
- safety composite/contribution evidence.

BUY/SELL/HOLD, retrieval activation, positions, PnL, wallet/private-key/signing,
live execution, paid sources, scoring, ranking, confidence, weighted logic,
embeddings, and vectors remained locked.

## Replay and database isolation (Attempt 2)

Report-only replay for run
`e119034c-17a2-42c0-91b5-3b3c400d270b` recorded:

- mode: `REPORT_ONLY`;
- new source calls: `0`;
- new evidence rows: `0`.

Proof SHA-256 before and after replay was byte-identical:

`3DA17416D4E479FFA146CADC8E2B5EE3648A0379BBB8299C7ABDE8ABF17427F9`.

The prepared backup remained at its pre-runtime hash
`97893AFB6B3D649C9E3105F407D5C0C2A8D689F0A377D84FBFF70ED443FA92F6`.
The proof changed only through the authorized runtime.

Persistent SHA-256 after runtime and replay remained:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.

Persistent critical counts stayed unchanged:

- source requests / responses / failures: `1118 / 1071 / 47`;
- scheduler jobs: `989`;
- token snapshots: `1012`;
- memory windows / fingerprints: `156 / 23`;
- retrieval queries / matches: `10 / 0`;
- paper decisions: `2`;
- positions / trade events / trade audits: `0 / 0 / 0`.

Attempt 2 proof deltas were seven requests, six responses, one failure, 17
scheduler jobs, four snapshots, one run, and 16 run steps. Persistent deltas
were zero.

## Attempt 2 verdict rationale

FAIL.

Attempt 2 did not produce a continuous 5m -> 15m -> 1h -> 4h lifecycle or an
audited WINDOW_4H result. A public-source TLS handshake timeout is an acceptable
external failure only when the runtime preserves and reports it honestly. The
runtime safely cancelled jobs and avoided invalid evidence, but the final
report replaced the source failure with a nonexistent budget breach. That
violated the required terminal reporting contract and prevented PASS or an
honest evidence-quality block. V2-9.3 subsequently repaired this defect (see
above); Attempt 3 exercised the repaired accounting path.

## Attempt 3 preflight

All pre-runtime gates passed:

- HEAD: `0baefc36517e25f20ac81d6c81158dd698b7dc01`;
- tracked tree: clean (confirmed again immediately before and after runtime);
- free disk: `312,617,013,248` bytes;
- fresh proof and backup paths (`printer_v1_v2_9_attempt3_bounded_continuous_4h_proof.sqlite3`
  and its `.backup.sqlite3`) did not exist before preparation;
- the failed Attempt 1 and Attempt 2 proofs and backups were not reused;
- outbound reachability to both live sources was confirmed with a single
  request each (no repeated retries): `geckoterminal` HTTP 200,
  `dexscreener` HTTP 200;
- V2-9.1 canonical preparation status: `PROOF_DB_SCHEMA_READY`;
- applied/canonical migrations: `29 / 29`, latest
  `029_composite_safety_evidence.sql`;
- integrity: `ok`; foreign-key errors: `0`; runtime schema issues: `[]`;
- prepared proof and backup SHA-256 (byte-identical before runtime):
  `FC58C844CEA47D09134F45D0AFB74F43512F4A7A7126857D2523291F75C04C10`;
- persistent SHA-256 before preparation and before runtime:
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`
  (identical to the value recorded after Attempt 2, confirming no
  intervening persistent-DB change);
- V2-9.1/9.2/9.3 focused tests: `26 passed` (10 + 10 + 6, plus 2 subtests);
- WINDOW_12H and WINDOW_24H real collection: structurally disabled (no
  proof-mode override parameter exists for either window in the runner,
  unlike the explicit `four_hour_proof_mode` escape hatch for WINDOW_4H).

The canonical preparation report recorded `sources_run=false` and
`scheduler_runtime_run=false`. No gate failed before runtime.

## Attempt 3 identity and lifecycle anchors

| Field | Observed |
| --- | --- |
| Run | `4c78ec5e-bd43-420b-b624-a5fb9dae9d2f` |
| Token | ID `18`; `FeMbDoX7R1Psc4GEcvJdsbNbZA3bfztcyDCatJVJpump` |
| Pair | ID `22`; `5ByL7MZoLABYnwMPZKPKjf4MGkZ7FeBzrAnos19Pre2z` |
| Stored lane | `TRACK_FAST` |
| Selection seed | `971d96ef09d877a46f9da1f26c0a6381` |
| Eligible pool | `30` |
| Run start | `2026-07-15T17:11:30.023312+00:00` |
| Last completed step | `t1_continuation_snapshot_08`, finished `2026-07-15T17:42:27.904463+00:00` |
| First abandoned step | `t1_continuation_snapshot_09`, scheduled `2026-07-15T17:44:24.607066+00:00`, never started |
| Run finish | none recorded; `run_status` remains `RUNNING`, `stop_reason` is `NULL` |
| 5m / 15m / 1h / 4h window IDs | `158` (support) / `157` / none / none |
| Exact current-run 1h predecessor | WINDOW_15M `157`, same run, same token/pair/lane throughout |
| 4h successor | None (4h phase never started) |

Identity and lane selection were autonomous. No mint, pair, predecessor,
snapshot, or window identity was manually supplied or linked. Same-run, token,
pair, and lane continuity held for every row this attempt produced.

## Cadence, duration, and continuity (Attempt 3)

FAST 15m collection expected and got 16 snapshots (IDs `1013-1028`, the last
being the forced closing snapshot). Consecutive scheduled-for gaps were
approximately 60-63s throughout, inside the FAST 15m clean-gap policy
(target 60s, dirty above 90s, block above 120s). The 15m window closed at
`2026-07-15T17:26:48.085327+00:00` with `expected_snapshot_count=16`,
`actual_snapshot_count=16`, `missing_snapshot_count=0`,
`coverage_state=COVERAGE_PASS`, `data_quality_label=CLEAN_DATA`, and
`e2q_audit_status=PARTIAL_MEMORY` (the correct continuous-mode label: a 15m
window stays provisional until its 1h continuation closes). Full governed
opening/closing context was captured and attached: chain heat, chart
volatility, liquidity/exit realism entry and exit quotes, a safety composite,
market regime, and trading flow, each `CONTEXT_FRESH` and target-matched to
the closing snapshot. The same-stream WINDOW_5M_MICRO_EVENT support window
(`158`) was derived and closed cleanly alongside it.

The FAST 1h continuation then ran 9 of its 24 expected snapshots (IDs
`1029-1037`), continuation_snapshot_00 through continuation_snapshot_08, all
`SUCCEEDED`. Scheduled-for gaps were approximately 117.4s, inside the FAST 1h
continuation clean-gap policy (target 120s, dirty above 180s, block above
240s). No gap in the executed portion exceeded the clean threshold and no
snapshot was missed up to the point of termination.

The host process was terminated while asleep between the finish of
continuation_snapshot_08 (`17:42:27.904463`) and the scheduled start of
continuation_snapshot_09 (`17:44:24.607066`) - a gap of under two minutes, well
inside the normal cadence window. The remaining 14 continuation snapshots and
the continuation-close step were never attempted; they remain `PENDING`.
Because the continuation-close step never ran, no WINDOW_1H memory window was
created, the fixed `1h close + 10,800s` 4h deadline was never established, and
the 4h phase never started. Continuity for the executed portion was internally
consistent (`CONTINUITY_UNKNOWN` at the point of termination, since no window
close or long-window audit ever evaluated it); it did not pass, become dirty,
or bypass a gate.

## Termination and source behavior (Attempt 3)

Every governed source request this attempt made succeeded: `printer_source_requests`
and `printer_source_responses` each grew by `31`, and `printer_source_failures`
grew by `0`. There was no DexScreener, GeckoTerminal, Jupiter-quote, GoPlus, or
CoinGecko failure at any point in this attempt, and no automatic retry or
endpoint rotation occurred (none was needed).

The run itself did not stop through any governed path. Its `printer_memory_factory_runs`
row still reads `run_status=RUNNING`, `stop_reason=NULL`, `finished_at=NULL`,
`final_report_json=NULL`. The background task running the proof was reported
by the execution environment as `killed` with no further detail. Immediately
on that notification, a check for any live `python.exe` process (via
`tasklist`) found none, confirming the process was fully gone and not merely
detached. The isolated proof DB was then read-only inspected and left exactly
as the OS left it; nothing was written to it afterward.

This is not a source failure and not a budget breach: no failed step exists
anywhere in the run's ledger, and every budget below is comfortably within
ceiling. The true first cause is an external termination of the runtime
process by the host execution environment, outside the governed Printer V1
code paths entirely. Per the standing contract from V2-9.3, an early stop
before 4h must report the 4h phase as not-started rather than invent a false
cause - this closeout does the same, and additionally does not mislabel an
environment-level kill as either a source failure or a budget stop.

## Phase and cumulative budgets (Attempt 3)

Actual usage reconstructed from canonical DB deltas:

| Scope | Requests | Request ceiling | Scheduler rows | Scheduler ceiling | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| FAST 4h phase | 0 | 69 | 0 | 64 | Not started; zero usage |
| FAST cumulative lifecycle | 31 | 116 | 41 | 105 | Within |

Cumulative requests were 2 discovery calls, 5 governed 15m-closing context
calls, plus source calls behind the 16 FAST 15m snapshots and the 9 executed
1h-continuation snapshots. Cumulative scheduler rows were 1 discovery handoff
(cancelled after selection, matching Attempt 2's pattern), 15 FAST 15m
scheduler jobs (14 snapshots plus window close - the 15m phase's 16th
snapshot is the window-close snapshot itself), 9 succeeded 1h-continuation
jobs, and 15 `PENDING` 1h-continuation jobs (14 remaining continuation
snapshots plus the continuation-close job) that never ran and were never
cancelled. Holder fallback usage was zero. Automatic retry executions were
zero. Endpoint rotation was zero. The 4h projected guards were never reached
because no `LONG_CONTINUATION_*` step was ever planned.

## Context, safety, realism, chart, and flow (Attempt 3)

The completed 15m window carries a full opening/closing evidence set: chain
heat (`SOLANA_WARM`, clean), chart volatility (16 candles, `CLEAN_DATA`,
`TREND_SIDEWAYS`), liquidity/exit realism entry and exit quotes (both
`ROUTE_AVAILABLE`, `CLEAN_DATA`), a safety composite (`SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY`,
mint authority renounced, freeze authority disabled, metadata immutable), a
market-regime snapshot (`CHOPPY`, `CLEAN_DATA`), and a trading-flow snapshot
(`CLEAN_DATA`, strong buy-side inflow). All were `CONTEXT_FRESH` and
target-matched to the closing snapshot, and the window's own E2Q audit passed
with `CLEAN_DATA` and `COMPLETE_WINDOW_COVERAGE`.

No closing context, safety re-evaluation, or realism conclusion exists for the
1h continuation phase, because its close step never ran. No 4h opening or
closing context, chart/flow window evidence, or exit-realism conclusion exists,
because the 4h phase never started. Nothing was promoted from the partial
continuation snapshots.

## Scheduler and cleanup (Attempt 3)

Attempt 3 added 41 scheduler rows and 40 run steps (one discovery handoff has
no run-step row):

- one discovery handoff, cancelled after selection;
- 15 succeeded FAST 15m scheduler jobs (14 snapshots + window close);
- 9 succeeded FAST 1h-continuation scheduler jobs;
- 15 `PENDING` scheduler jobs never executed and never cancelled: 14 remaining
  1h-continuation snapshots plus the continuation-close job.

After the process was terminated and inspection completed:

- pending/running run steps: `15` (all `PENDING`, none `RUNNING`);
- running jobs: `0` (none were mid-execution or locked at the moment of
  termination - `locked_at` and `lock_owner` are `NULL` on every row);
- locks/owners left behind: `0`;
- forced close: never reached, still `PENDING`;
- invalid successor windows: `0` (none were created at all).

Cleanup is therefore **not** complete and **not** a governed safe stop: the
15 abandoned rows exist only because the host process was killed before the
runtime's own cancellation-on-stop logic could run. Nothing here is unsafe
for the isolated, non-persistent Attempt 3 proof DB - no lock is held, no
partial write is in flight - but it does not meet the COMPLETED or a
governed-SAFE_STOPPED bar.

## E2Q, Lane Q, Lane K/E2Z, memory quality, and locks (Attempt 3)

The 15m window (`157`) was audited by E2Q and closed `PARTIAL_MEMORY` /
`CLEAN_DATA`, the correct continuous-mode outcome pending 1h closure - it was
not promoted to a standalone clean-memory row because continuous mode defers
that promotion to the 1h close. No WINDOW_1H memory window exists because the
continuation-close step never ran, so Lane Q's 1h integrity guard and Lane
K/E2Z clean-memory creation were never reached for this attempt - not
bypassed, simply not reached. `printer_memories`, `printer_memory_fingerprints`,
`printer_memory_retrieval_queries`, `printer_memory_retrieval_matches`,
`printer_paper_decisions`, `printer_paper_positions`, `printer_paper_trade_events`,
`printer_paper_trade_audits`, and `printer_paper_audit_reports` all show a
zero delta for this attempt.

BUY/SELL/HOLD, retrieval activation, positions, PnL, wallet/private-key/signing,
live execution, paid sources, scoring, ranking, confidence, weighted logic,
embeddings, and vectors remained locked.

## Replay and database isolation (Attempt 3)

No report-only replay was run: replay requires a `final_report_json`, and none
exists because the runtime never returned. The isolated proof DB was frozen by
inspection only (read-only queries), not by any write.

- proof SHA-256 immediately before runtime:
  `FC58C844CEA47D09134F45D0AFB74F43512F4A7A7126857D2523291F75C04C10`;
- proof SHA-256 at freeze (after the abandoned runtime):
  `4077E5E03C88185B4FC18920CC5CA28C6E9990CE76DD85263D92965D0C695E4D`;
- backup SHA-256 at freeze: `FC58C844CEA47D09134F45D0AFB74F43512F4A7A7126857D2523291F75C04C10`
  (unchanged - the backup was never touched by runtime);
- persistent SHA-256 before and after: `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`
  (unchanged);
- tracked worktree: clean before and after.

Persistent critical counts stayed unchanged throughout (identical to the
values recorded after Attempt 2): source requests / responses / failures
`1118 / 1071 / 47`; scheduler jobs `989`; token snapshots `1012`; memory
windows / fingerprints `156 / 23`; retrieval queries / matches `10 / 0`; paper
decisions `2`; positions / trade events / trade audits `0 / 0 / 0`.

Attempt 3 proof deltas (isolated DB only, persistent deltas remain zero):
`+31` requests, `+31` responses, `+0` failures, `+41` scheduler jobs, `+25`
token snapshots, `+2` memory windows (one WINDOW_15M, one support
WINDOW_5M_MICRO_EVENT), `+0` memories/fingerprints/retrieval/paper rows of any
kind.

## Attempt 3 verdict rationale

FAIL.

Attempt 3 produced real, clean evidence further into the lifecycle than either
prior attempt - a fully closed, audited, `CLEAN_DATA` FAST 15m window with
complete governed context, plus 9 of 24 clean FAST 1h-continuation snapshots -
and it did so with zero source failures and every budget comfortably within
ceiling. It still did not produce a continuous 5m -> 15m -> 1h -> 4h lifecycle
or an audited WINDOW_4H result, because its host process was terminated by the
execution environment before the 1h continuation could close, let alone before
the 4h phase could begin. That termination is external to the governed
runtime: it is not a source failure, not a budget breach, and not a code
defect surfaced by this attempt. It nonetheless leaves 15 run steps and
scheduler rows abandoned in `PENDING` on the isolated proof DB, which is not a
governed clean stop and cannot be reported as `COMPLETED` or a valid
`SAFE_STOPPED`.

No additional proof is authorized in this lane.

## Files changed (cumulative across Attempts 2 and 3)

- `docs/printer-v1-v2-9-bounded-continuous-4h-proof-closeout.md`

Local untracked evidence retained for operator inspection:

- `operator-runs/v2-9-attempt2-proof-preparation.json`;
- `operator-runs/v2-9-attempt2-bounded-continuous-4h-proof.json`;
- `operator-runs/v2-9-attempt2-bounded-continuous-4h-replay.json`;
- the isolated Attempt 2 proof DB and its pre-runtime backup;
- `operator-runs/v2-9-attempt3-proof-preparation.json`;
- `operator-runs/v2-9-attempt3-frozen-state.json` (no final report exists for
  Attempt 3, so this file records the run/step/scheduler ledger, hashes, and
  deltas exactly as found after the external kill);
- `operator-runs/run_v2_9_attempt3.py` (the ad hoc operator invocation script,
  not part of the governed runtime itself);
- `operator-runs/v2-9-attempt3-stdout.log` (empty - the process was killed
  before it could print or write anything);
- the isolated Attempt 3 proof DB and its pre-runtime backup.

## What was not touched

No implementation, migration, cadence, budget, configuration, source adapter,
or endpoint changed after either runtime began. The persistent DB was read
only across both attempts (hash-verified unchanged before Attempt 2, before
Attempt 3, and at Attempt 3's freeze). No fourth attempt, V2-10, 12h, 24h,
retrieval activation, paper decision, position, trade, audit, PnL, live
wallet, key, signing, or execution work began.

## Functionality risks / setbacks / efficiency blockers

1. (Attempt 2, repaired by V2-9.3) Early pre-4h source failure was not
   propagated into the final terminal reason when `continuous_four_hour=true`
   and no long-window rows existed; unreached phase usage was treated as an
   exceeded budget.
2. (Attempt 3, open) The governed runtime has no resilience to its own host
   process being terminated mid-run: there is no periodic checkpoint, no
   external heartbeat/watchdog, and no on-restart cancellation sweep. A killed
   process leaves run steps and scheduler rows stuck `PENDING` indefinitely on
   whatever DB it was using, with `run_status` frozen at `RUNNING` and no
   `stop_reason`. For a proof-only isolated DB this is inert, but the same gap
   would apply to any longer-lived run.
3. (Attempt 3, open) There is no operator-facing signal distinguishing "the
   governed runtime safe-stopped" from "the process running it disappeared."
   Both currently surface only as an unfinished proof DB; telling them apart
   required manual DB inspection (this closeout's Attempt 3 sections).
4. No real Attempt 3 evidence exists for a closed 1h window, 4h cadence, 4h
   closing context, or the E2Q/Lane Q/Lane K 1h-and-4h quality-gate ordering,
   because termination happened before the 1h continuation could close.

## Next recommended phase

Stop in V2-9. Do not rerun the proof and do not begin V2-10, 12h, or 24h. Any
future repair or proof requires a new explicit operator-approved lane. If a
fourth attempt is ever separately approved, first address risk 2/3 above (a
long-running-process supervision or checkpoint gap) so that a host-level
interruption produces an honest, immediate terminal report instead of an
indefinitely `RUNNING` row that requires manual forensics to interpret.
