# Printer V1 V2-9 Attempt 6 Forensic Audit Closeout

## Executive verdict

`V2_9_ATTEMPT_6_AUDIT_COMPLETE_PARTIAL_PROOF_REPAIR_REQUIRED`

Attempt 6 produced a genuine, current-run, terminal `WINDOW_4H` result. The
FAST path closed with 61/61 snapshots, no misses, clean cadence, exact
1h-to-4h continuity, a successful forced close, budgets within both approved
scopes, zero running jobs, and an honest `DIRTY_MEMORY` / `do_not_train=1`
result with no memory creation. A clean 4h memory is **not** required by the
active V2-9 proof contract: V2-8.1 explicitly permits a clean, dirty, or
blocked result when it is reported honestly and the complete runtime path is
safe. The dirty result therefore does not itself fail V2-9.

Attempt 6 does not close V2-9, however. The manual launcher stopped logging and
renewing its filesystem lease about three minutes after launch, so continuous
launcher supervision was not proven. In addition, the shared-context resolver
used a wall-clock interval that included the 1h predecessor snapshot and
excluded the valid, slightly-late 4h closing snapshot and its governed closing
context. That defect created three misleading blockers. The runtime evidence
listed below remains reusable; the launcher/supervision result and the affected
shared-context conclusions are non-closing evidence.

Audit scope was read-only except for this document. No source, runtime, test,
recovery, heartbeat, lock deletion, or database write was performed.

## Identity and accepted runtime evidence

| Item | Audited value |
| --- | --- |
| Starting commit | `3db418442e2331af9660f9cdfead5a8ed2d39163` |
| Execution ID | `1a5dfdb6-8b02-422b-8ddd-50cea16cfaca` |
| Run ID | `c2d0b9f9-5f2b-42be-88de-de5bff45ba91` |
| Token / pair / lane | `4ko5tSr5o3H4v1sFtjTSd9MPUW7yx5AFCpkNPoL6pump` / `68nVMrVPyxGJGbGH2P92E93SYhJcbe6QociZrqoqdjcB` / `TRACK_FAST` |
| Predecessor / successor | `WINDOW_1H` ID 159 / `WINDOW_4H` ID 160 |
| 4h opening / closing snapshot | 1053 / 1113 |
| 1h close / fixed 4h deadline | `2026-07-16T15:14:02.343549Z` / `2026-07-16T18:14:02.343549Z` |
| Transition | 2.046 seconds, `TRANSITION_CLEAN` |
| 4h cadence | 61 expected, 61 actual, 0 missed; maximum gap 187.959 seconds; `CADENCE_POLICY_PASS` |
| Duration / close | anchored 10,800.000 seconds; observed span 10,801.614 seconds; closing lateness 3.660 seconds; deadline drift 0.000 seconds |
| Terminal path | forced close step 102 `SUCCEEDED`; audit path complete; window ID 160 closed |
| Memory result | `DIRTY_MEMORY`, `DIRTY_DATA`, `do_not_train=1`; 0 memories created |
| Cleanup | 0 pending/running run steps; 0 running scheduler jobs; process PID 24240 absent; one-proof lock absent |

The proof DB final report and the child stdout agree on `COMPLETED` /
`COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`. The DB supervision row was
terminally finalized by the child at `2026-07-16T18:14:06.457989Z` as
`COMPLETED` with that same first-stop reason. This establishes natural child
completion; it does not retroactively establish continuous launcher
supervision.

## Accepted versus non-closing evidence

Accepted and reusable:

- canonical V2-9.1 preparation, migration validation, proof/backup initial
  byte identity, and persistent-DB before/after record;
- autonomous token/pair selection and the same run/token/pair/lane through
  15m, 1h, and 4h;
- current-run-ledger cadence and continuity, including all 61 4h snapshots and
  the successful forced close;
- source request/response/failure provenance, exact-pair fallback provenance,
  scheduler/run-step rows, separate phase/cumulative budgets, and cleanup;
- E2Q's dirty result, Lane Q's block, Lane K/E2Z non-promotion, zero memory,
  and all downstream zero deltas;
- the complete child stdout stream: 830,668 bytes containing 106 valid
  concatenated JSON objects, including the final report; empty stderr is
  consistent with a successful child;
- the launcher JSONL up to its failure: all 133 lines are valid JSON and prove
  launcher start, child PID, and six completed heartbeat renewals.

Non-closing or limited:

- the launcher JSONL has no `LAUNCHER_FAULT`, final heartbeat-success event,
  or `LAUNCHER_FINISH`; it ends mid-heartbeat output and cannot prove
  supervision after `2026-07-16T14:16:58.863479Z`;
- the filesystem lease expired at `2026-07-16T14:18:28.863479Z`, almost four
  hours before natural child completion;
- `SNAPSHOT_BOUNDARY_MISMATCH`, exact-target safety absence, and exact-target
  exit-quote absence are resolver false negatives and cannot be used as factual
  claims that the closing evidence was absent;
- chart and flow labels in the stored shared-context report were derived from
  the wrong 61-row interval. A read-only recomputation from run-ledger IDs
  1053-1113 confirms that the chart remains conservatively blocked and flow
  remains partial, but that recomputation is audit evidence, not a stored
  replacement report;
- `recovery_evidence_deltas` are all zero because no abandoned-run recovery
  was needed or invoked. They remain correctly separate from full-run deltas,
  but are not evidence of an independently executed replay/recovery pass.

## Proven root causes and confidence

### Launcher logging and stale supervision

At `14:16:58.863479Z` the filesystem-only `heartbeat` command succeeded and
atomically renewed the lease to `14:18:28.863479Z`. `Invoke-Supervision` then
captured that native Python command through `2>&1` and logged its output one
line at a time. The launcher JSONL contains the returned object through its
`updated_at` member but not the final `}`; it also lacks the immediately
following `HEARTBEAT_RENEWED`. The operator-observed exception was `Stream was
not readable`. Therefore the heartbeat persistence did not fail: the failure
was in the PowerShell native-output capture/logging boundary after the renewal
had succeeded. The launcher process then stopped emitting heartbeats and final
events while the separately redirected proof child continued and completed.

Confidence is high for that sequence and fault boundary. The artifacts contain
no PowerShell stack trace or persisted `LAUNCHER_FAULT`, so the exact .NET
stream object and why the generic catch/finally path did not persist a fault or
stop the child are `UNKNOWN_REQUIRES_RESEARCH`. Static code shows that logging
inside the catch uses the same `Write-LauncherEvent` path and process-state
handling uses the same redirected `Process` object, leaving the fault path
unable to guarantee its own observability. This is an implementation defect,
not operator cancellation, source failure, or proof-DB contention.

### Shared close-boundary mismatch

The 4h window's logical end is the fixed deadline
`18:14:02.343549Z`. Approved closing-freshness policy accepted snapshot 1113 at
`18:14:06.003279Z` (3.660 seconds late). The shared resolver nevertheless
selects all token/pair snapshots with `captured_at >= window_start_at` and
`captured_at <= window_end_at`, rather than consuming the current run ledger or
the approved close boundary. The inclusive start admitted predecessor snapshot
1052 at exactly `15:14:02.343549Z`; the strict end excluded closing snapshot
1113. The coincidental 61-row set was therefore 1052-1112, not 1053-1113.

The same strict `target_time=window_end_at` filter excluded closing GoPlus
safety evidence captured at `18:14:04.817838Z` and Jupiter exit-quote evidence
captured at `18:14:05.307071Z`. Both rows actually exist on exact snapshot
1113, are fresh, `TARGET_MATCH`, `COMPLETE`, `CLEAN_DATA`, and have clean
governed traces. The safety composite has complete provenance, no blockers or
conflicts, and is accepted by the existing composite contract; the exit quote
reports a route available. This is an implementation defect caused by an
unreconciled logical-deadline versus allowed-closing-freshness model.

### Conservative chart and partial flow

Read-only recomputation using only run-ledger snapshots 1053-1113 still yields
61 candles, a 100% round trip, `PATH_ROUND_TRIP`, clean chart payload, and
`CHART_CONTEXT_DO_NOT_TRAIN`. That block is expected conservative policy, not
a defect. The corrected set changes the price result from -7.147% to -11.470%
but not the safety verdict.

The closing DexScreener payload supplies buys/sells and aggregate volume but
does not supply `buy_volume_5m`, `sell_volume_5m`, or
`unique_wallets_5m`. The current flow classifier therefore reports
`TRADING_FLOW_CONTEXT_PARTIAL` / `FLOW_CONTEXT_CAUTION`. This is a provider
limitation against the current clean-field contract. The stored generic
`FLOW_DIRECTION_OR_PRESSURE_NOT_CLEAN` blocker is misleading: direction and
pressure were known; the section failed because the snapshot boundary set was
wrong. With the correct set it remains partial but has
`FLOW_CHOPPY` / `PRESSURE_MODERATE_INFLOW`.

## Blocker classification

| Observed blocker or condition | Classification | Finding |
| --- | --- | --- |
| `SNAPSHOT_BOUNDARY_MISMATCH` | implementation defect | Time-range lookup used 1052-1112 instead of current-run ledger 1053-1113 and ignored approved close lateness. |
| `NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE` | implementation defect | Fresh exact-target row 14/composite 2 existed but was filtered because capture followed the logical deadline during governed close work. |
| `NO_VALID_EXACT_TARGET_EXIT_QUOTE_EVIDENCE` | implementation defect | Fresh exact-target quote 24 existed but was filtered for the same reason. |
| `CHART_OR_VOLATILITY_NOT_CLEAN` | expected conservative policy | Corrected run-ledger evidence remains `PATH_ROUND_TRIP` and `DO_NOT_TRAIN`. |
| `FLOW_DIRECTION_OR_PRESSURE_NOT_CLEAN` | implementation defect | Generic reason masked the boundary failure; direction and pressure were not unknown. |
| `TRADING_FLOW_CONTEXT_PARTIAL` | provider limitation | DexScreener lacks the required separated buy/sell volume and unique-wallet fields. |
| Missing GoPlus/Jupiter/CoinGecko source-stack contract files named in the audit prompt | missing design | The repository README explicitly marks these provider modules as planned for SB-3+ and not authored; only the applicable existing source-governor rules and A6 implementation evidence could be used. Upstream details not proved locally remain `UNKNOWN_REQUIRES_RESEARCH`. |
| Launcher `Stream was not readable` low-level .NET object/catch escape | `UNKNOWN_REQUIRES_RESEARCH` | Failure locus and sequence are proven, but no persisted stack trace identifies the exact stream instance. |

## Source, scheduler, snapshot, and budget reconciliation

The full run created 113 source requests, 112 responses, and one preserved
failure. Breakdown: DexScreener pair snapshots 101 requests/100 responses plus
one TLS `BAD_RECORD_MAC` failure; one governed GeckoTerminal exact-pair
fallback supplied that missing snapshot; GeckoTerminal discovery used two
requests/responses; CoinGecko used 3/3; GoPlus 2/2; Jupiter quote 4/4. Thus
101 token snapshots reconcile to 100 successful DexScreener snapshots plus one
successful GeckoTerminal fallback. The failure remained visible and no
automatic retry or endpoint rotation occurred.

There are 102 run steps, all `SUCCEEDED`: 15 initial snapshots, one 15m close,
one 5m support step, 23 1h snapshots, one 1h close, 60 4h continuation
snapshots, and one 4h close. There are 102 scheduler deltas: 101 successful
run-step jobs plus one cancelled discovery handoff. Every retry count is zero,
and terminal cleanup left zero pending/running steps and jobs.

| Budget scope | Requests | Ceiling | Scheduler rows | Ceiling | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| FAST 4h phase | 66 | 69 | 61 | 64 | within |
| FAST cumulative lifecycle | 113 | 116 | 102 | 105 | within |

Holder-RPC fallbacks were 0/2 under the later V2-9.6 primary-plus-one-backup
policy; endpoint rotation and automatic retries were zero. Full-run evidence
deltas remain distinct from the all-zero recovery deltas.

## Database isolation, integrity, and locks

Before any SQLite open, no proof, backup, or persistent WAL/SHM file existed.
All three databases were then opened with read-only immutable URIs. Each
returned `integrity_check=ok` and zero foreign-key violations.

| Artifact | SHA-256 |
| --- | --- |
| Prepared backup | `2C47713AB9F1D9F96CA6F44714A322B586CB909E717C291238DE83786BF0BB40` |
| Completed proof DB | `B378DA98CDCB3D2106C257AF3620D2BE7FF01003E350B31D3EDED0C1C379A116` |
| Preparation JSON | `14ADAD02B00D87CE8F1A1BA2B082A4F4E18684F7E987018508318D9F40ABB1EF` |
| Child stdout | `BF0227FF449BEEDD74A8AE904BE2A4FFC83F4D919A0B3B57B911FA3A15682E67` |
| Empty child stderr | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| Launcher JSONL | `84A255082D0E48500572EDD4C38FA85A35715BFAE35BD7838BAFB9F0D7687D0B` |

Preparation proved the proof and backup byte-identical before runtime. Their
post-run difference is expected: only the proof copy received runtime rows.
The canonical persistent DB remained at
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`,
exactly matching preparation before/after. Its critical counts also match:
windows 156; snapshots 1012; scheduler jobs 989; source requests/responses/
failures 1118/1071/47; fingerprints 23; retrieval queries/matches 10/0;
paper decisions 2; paper audit reports 1; positions, trade events, trade
audits, factory runs/steps, and supervision rows all zero.

Proof-only deltas for memories, fingerprints, retrieval queries/matches,
paper decisions, positions, trade events, trade audits, audit reports, and PnL
were all zero. E2Q ran first and marked window 160 dirty; Lane Q then blocked
it; Lane K/E2Z created nothing. `WINDOW_12H` and `WINDOW_24H`, retrieval,
BUY/SELL/HOLD, positions, trades, audits, PnL, live execution, wallets, keys,
paid APIs, scoring, ranking, confidence, weighted logic, embeddings, and
vectors remain locked.

## Minimum ordered repair sequence

1. Make launcher supervision output capture and launcher-event persistence
   independent and failure-observable. A logging/capture fault must preserve
   its exact first cause, keep the heartbeat loop alive when the lease update
   succeeded, and have a separately safe terminal path. Persist a PowerShell
   stack/command boundary without relying on the failing logger itself.
2. Change 4h shared-context resolution to consume the exact current-run ledger
   IDs, not a token/pair wall-clock scan. Separate the immutable logical
   deadline from an explicit approved closing-evidence cutoff bounded by the
   existing closing-freshness policy. Accept only the exact closing snapshot's
   fresh governed safety/quote evidence; reject future, unrelated, stale, or
   non-ledger evidence.
3. Keep the round-trip chart rule unchanged. Treat flow's unavailable wallet
   and split-volume fields as a source/design question: either retain partial
   flow honestly or complete an operator-approved provider-contract design.
   Do not fabricate fields or silently weaken the clean gate. Author/verify the
   still-planned provider modules before relying on upstream claims.
4. Verify with temporary DBs and fixtures only: repeated native supervision
   output under redirected child logs; injected logger/capture faults; exact
   first-stop and cleanup behavior; close snapshots just inside/outside
   freshness; predecessor/future-snapshot exclusion; exact safety/quote
   acceptance; round-trip still dirty; partial flow still honest; zero replay,
   persistent, retrieval, and financial deltas.
5. Only after those repairs pass may the operator separately consider one new
   bounded proof. Completion proof must show uninterrupted launcher heartbeats
   and terminal logging, exact current-run context boundaries, the existing
   cadence/continuity/budget/cleanup gates, and an honestly reported clean or
   dirty terminal 4h outcome. No clean memory is required.

## Money-usefulness contribution and what improved

Attempt 6 is the first accepted full FAST 4h trajectory in this lane. It adds
no clean corpus row, but it proves that the bounded collector can preserve a
real 10,800-second path, survive one governed exact-pair transport fallback,
close on cadence, and refuse to train on a round-trip trajectory. That is
money-useful capital-protection evidence: it prevents a visually active token
from becoming false clean memory and preserves realistic entry/exit source
records for audit.

Compared with earlier attempts, schema preparation, source-failure
preservation, fallback provenance, phase/cumulative accounting, forced-close
terminal semantics, cleanup, child-side terminal supervision, artifact naming,
and full-run-versus-recovery deltas all behaved correctly. The remaining gaps
are narrowly operational (launcher observability/heartbeat continuity) and
evidence-resolution (close-boundary identity), not cadence or budget failures.

## Functionality Risks / Setbacks / Efficiency Blockers

- A completed child can currently run for hours after launcher monitoring and
  sleep-prevention ownership disappear; natural completion in this attempt
  does not make that operationally safe.
- The launcher fault left no durable stack trace or final launcher record,
  increasing forensic cost and leaving the lowest-level stream cause unknown.
- Time-range context lookup can exchange a valid close snapshot for a
  predecessor while preserving the expected count, so count-only checks are
  insufficient.
- Correct boundary repair will not make this token clean: the genuine 100%
  round trip must remain `DO_NOT_TRAIN`.
- DexScreener cannot satisfy the current full flow-field contract by itself;
  repeated live proofs will continue to report partial flow unless policy or
  governed-source design is explicitly resolved.
- Three provider modules requested for this audit do not exist and are marked
  planned in the subordinate Solana Builder README. This documentation gap
  prevents stronger local upstream-contract conclusions.
- No Attempt 7, V2-10, active memory growth, retrieval, or financial capability
  is authorized by this closeout.

## Files changed

- `docs/printer-v1-v2-9-attempt-6-forensic-audit-closeout.md` only.

## Verification performed

- static source, commit-history, launcher/supervision, cadence/continuity,
  context resolver, E2Q/Lane Q, source-governance, and closeout inspection;
- SHA-256 hashing of all Attempt 6 artifacts and the persistent DB;
- JSON validation of preparation output, all 133 launcher JSONL records, and
  all 106 concatenated child-output JSON objects;
- immutable read-only SQLite counts, row-level evidence queries, integrity
  checks, foreign-key checks, and run-ledger-only audit recomputation;
- lock/process/WAL/SHM read-only inspection;
- `git diff --check` before commit.

No tests were run, as required.
