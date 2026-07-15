# Printer V1 V2-9 Bounded Continuous 4h Proof Closeout

## Final verdict

`V2_9_BOUNDED_4H_PROOF_FAIL`

Lane: `V2-9 - Bounded Continuous 4h Proof`

The lane used all authorized attempts and remains failed. The first preparation
attempt was blocked before runtime by an unmigrated proof schema. Runtime
Attempt 1 reached the 4h phase but failed after 24 of 31 NORMAL snapshots and
incorrectly reported `COMPLETED`. V2-9.1 repaired canonical proof preparation,
and V2-9.2 repaired the known 4h terminal and budget paths. Separately approved
Attempt 2 then failed during the initial FAST 15m collection after four
snapshots. Cleanup was safe, but the final report mislabeled a DexScreener
transport stop as a budget stop even though both applicable budgets were within
limits.

No second Attempt 2 run occurred. This closeout does not activate generalized
4h production or begin V2-10, 12h, 24h, retrieval, decisions, positions,
trades, audits, or PnL.

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

## Cadence, duration, and continuity

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

## Source failure and terminal behavior

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

## Phase and cumulative budgets

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

## Context, safety, realism, chart, and flow

The 15m forced close was cancelled, so WINDOW_5M support derivation and the
15m governed close context never ran. No opening/closing market-chain bundle,
safety close evidence, paper ENTRY/EXIT quote evidence, completed chart/flow
window evidence, or exit-realism conclusion was created for this run.

The four token snapshots were COMPLETE/CLEAN_DATA source rows, but they are not
a completed window and cannot establish clean memory, entry realism, exit
realism, chart outcome, or flow outcome. Nothing was promoted from partial
snapshot evidence.

## Scheduler and cleanup

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

## E2Q, Lane Q, Lane K/E2Z, memory quality, and locks

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

## Replay and database isolation

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

## Verdict rationale

FAIL.

Attempt 2 did not produce a continuous 5m -> 15m -> 1h -> 4h lifecycle or an
audited WINDOW_4H result. A public-source TLS handshake timeout is an acceptable
external failure only when the runtime preserves and reports it honestly. The
runtime safely cancelled jobs and avoided invalid evidence, but the final
report replaced the source failure with a nonexistent budget breach. That
violates the required terminal reporting contract and prevents PASS or an
honest evidence-quality block.

No additional proof is authorized in this lane.

## Files changed

- `docs/printer-v1-v2-9-bounded-continuous-4h-proof-closeout.md`

Local untracked evidence retained for operator inspection:

- `operator-runs/v2-9-attempt2-proof-preparation.json`;
- `operator-runs/v2-9-attempt2-bounded-continuous-4h-proof.json`;
- `operator-runs/v2-9-attempt2-bounded-continuous-4h-replay.json`;
- the isolated Attempt 2 proof DB and its pre-runtime backup.

## What was not touched

No implementation, migration, cadence, budget, configuration, source adapter,
or endpoint changed after runtime began. The persistent DB was read only. No
second proof, V2-10, 12h, 24h, retrieval activation, paper decision, position,
trade, audit, PnL, live wallet, key, signing, or execution work began.

## Functionality risks / setbacks / efficiency blockers

1. Early pre-4h source failure is not propagated into the final terminal reason
   when `continuous_four_hour=true` and no long-window rows exist.
2. Unreached phase usage is treated as an exceeded budget, and known cumulative
   usage is discarded as unavailable.
3. Scheduler `retry_count=1` represents a failed no-retry execution, which is
   easy to misread operationally even though no second request/job ran.
4. No real Attempt 2 evidence exists for 5m support, 15m close, 1h continuity,
   4h cadence, closing context, or quality-gate ordering beyond fail-closed
   non-entry.

## Next recommended phase

Stop in V2-9. Do not rerun the proof and do not begin V2-10, 12h, or 24h. Any
future repair or proof requires a new explicit operator-approved lane.