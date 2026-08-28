# Printer V1 Current-State Memory Growth Audit

## Audit Metadata

Task: V2-0 current-state memory growth audit.

Status: AUDIT ONLY. This document does not implement a lane, mutate a DB, run a
runner, fetch sources, activate retrieval, create paper decisions, unlock BUY,
open positions, create trade events, create paper trade audits, or create PnL.

Primary objective: reset the operator view of where Printer V1 is today and
provide a factual base for a possible Memory Growth Build Order V2 proposal.

Todo / checklist:

- [x] Read the active authority stack and memory-growth source files.
- [x] Inspect git history, tags, and working tree status.
- [x] Inspect X14 operator-run artifacts.
- [x] Inspect live DB counts using SQLite read-only mode.
- [x] Inspect X14 proof DB counts using SQLite read-only mode.
- [x] Inspect CLI/source/test references for 15m, 1h, and longer-window paths.
- [x] Create this audit document.
- [ ] Operator review and decide whether to adopt a V2 reset build order.

Files and artifacts inspected:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-growth-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-memory-growth-automation-audit.md`
- `docs/printer-v1-lane-x11-1h-activation-readiness.md`
- `docs/printer-v1-lane-x13-1h-operator-proof-readiness.md`
- `lane-x14-attempt-3c-fixed-bomless-writer-output.txt`
- `operator-runs/lane-x14-attempt-3c-fixed-bomless-writer/x14_attempt3c_runner_output_20260708-123543.json`
- `operator-runs/lane-x14-attempt-3c-fixed-bomless-writer/x14_attempt3c_refresh_snapshot_20260708-123543.json`
- `operator-runs/lane-x14-attempt-3c-fixed-bomless-writer/x14_attempt3c_track_fast_token_list_20260708-123543.json`
- `data/printer_v1.sqlite3` read-only
- `data/proof_runs/printer_v1_x14_attempt3_20260708-123214.sqlite3` read-only
- Relevant CLI/source/test files found by static `rg` inspection.

Important gap: `docs/printer-v1-lane-x12-1h-structural-implementation.md` was
requested as source of truth but was not present in `docs/` during this audit.
X12 is represented by commit/tag history, source code, tests, and the X13
runbook's summary of what X12 built.

## 1. Executive Summary

Current active source-of-truth stack:

- Highest local rule file: `AGENTS.md`.
- Core product law: `docs/printer-v1-clean-master-spec.md`.
- Historical post-RC road map: `docs/printer-v1-post-rc-build-order.md`.
- Active memory-growth road map: `docs/printer-v1-memory-growth-build-order.md`.
- Required supporting audit/readiness source: `docs/printer-v1-memory-growth-automation-audit.md`.
- Memory Factory policy guide: `docs/printer-v1-memory-factory-guide.md`.
- Recent 1h readiness/runbook docs: Lane X11 and X13 docs.

Current active memory-growth roadmap:

- `docs/printer-v1-memory-growth-build-order.md` is the active memory-growth
  build order according to `AGENTS.md`.
- That document still declares current active lane as Lane X1, but git history
  and artifacts show the repo has advanced through X13 and X14 proof attempts.
- This is drift. The active roadmap has not been reset after the X14 proof
  result.

Current lane status:

- Repo HEAD is `827b4c3 Add Lane X13 1h operator proof readiness runbook`.
- The X14 Attempt 3C proof artifact exists but is not committed/tagged as a
  closeout lane.
- X14 must be classified as `PARTIAL_READY_WITH_BLOCKER`, not a clean passing
  1h proof.

Whether we have drifted:

- Yes. The active memory-growth doc still starts at X1 while the actual repo,
  source code, tests, and operator artifacts have moved to X13/X14.
- X12 structural implementation is committed/tagged, but the requested X12 doc
  is missing.
- Many untracked operator output files and proof artifacts exist, making it hard
  to tell which artifacts are official proof evidence without a reset map.

Whether a new V2 build order is justified:

- Yes. V2 is justified because the next practical work is not simply "continue
  X15". The system needs a reset build order that closes X14 honestly, repairs
  the 1h audit/integrity boundary, and stabilizes one-command 15m memory growth
  before broader multi-timeframe claims.

Top 10 blockers to useful money-relevant memory growth:

1. E2Q memory window audit is still hardcoded to `WINDOW_15M`, blocking real
   `WINDOW_1H` closeout.
2. X14 proved 1h collection runtime behavior, but not 1h memory audit,
   fingerprinting, clean episode creation, or retrieval eligibility.
3. The active memory-growth roadmap is stale relative to actual completed X
   work and proof artifacts.
4. There is no committed X14 closeout doc/tag, only untracked artifacts.
5. One-command memory factory remains fragmented across multiple lane-specific
   commands and manual proof scripts.
6. Discovery/selection still risks over-representing active/trending tokens and
   under-representing dead tokens, revivals, wrong waits, and wrong avoids.
7. 4h/12h/24h have fixture/staged code but no operational approval or real
   proof.
8. Clean retrieval is still not activated; retrieval matches remain zero.
9. Paper decision usefulness is still locked behind clean retrieval and later
   conservative review.
10. Artifact sprawl and untracked proof outputs make operator workflow fragile.

Verdict:

```text
CURRENT_STATE_AUDIT: PASS
MEMORY_GROWTH_ROADMAP_STATE: DRIFTED
X14_STATUS: PARTIAL_READY_WITH_BLOCKER
V2_BUILD_ORDER_JUSTIFIED: YES
FINANCIAL_LOCKS: PRESERVED
```

## 2. Source-of-Truth Compliance Map

| Current behavior | Source file / section | Status | Audit note |
|---|---|---:|---|
| Solana-only, paper-only, no wallet/private keys/live execution | `AGENTS.md`, Locked V1 Rules; Clean Master Spec final locked rule | Aligned | No inspected X14 artifact showed live execution or wallet behavior. |
| Dirty memory must not support decisions | `AGENTS.md` Memory Rules; Clean Master Spec Part 10 | Aligned | Retrieval matches are zero; paper positions/trades/PnL are zero. |
| `WINDOW_5M_MICRO_EVENT` is support-only | `AGENTS.md`; Memory Growth Build Order; Memory Factory Guide | Aligned | 5m rows exist only as audit/support rows; they are not retrieval or paper unlocks. |
| 15m is the first main memory-growth target | Memory Growth Build Order; Memory Factory Guide | Aligned | Live DB has 154 `WINDOW_15M` memory windows and clean 15m episodes. |
| Multi-token 15m was the active X1 starting point | Memory Growth Build Order | Drift | Repo history advanced through X13/X14 artifacts. Active doc was not reset. |
| X12 built 1h structural support | X13 runbook; source/tests | Partially aligned | Code/tests exist, but requested X12 doc is missing. |
| Real 1h proof should be isolated and operator-reviewed | X13 runbook | Aligned | X14 Attempt 3C used proof DB under `data/proof_runs/`. |
| 1h proof should create/close valid 1h memory | X13 expected outcome | Blocked | Proof DB has one `WINDOW_1H` row, but E2Q blocked it as non-15m. |
| 4h/12h/24h remain staged/later | Memory Growth Build Order; X13 | Aligned | No live/proof DB rows for 4h/12h/24h. |
| Retrieval and paper decisions remain locked | AGENTS.md; Lane 9/10 docs | Aligned | Retrieval matches zero; paper positions/trades/PnL zero. |
| No scoring/ranking/confidence/weighted logic | AGENTS.md; Clean Master Spec | Aligned | No audit evidence shows a scoring unlock. |

Blunt compliance summary: the safety rules held. The planning state did not.
Printer is safer than it is organized.

## 3. Repo State

Current HEAD:

```text
827b4c3 Add Lane X13 1h operator proof readiness runbook
```

Recent commits:

```text
827b4c3 Add Lane X13 1h operator proof readiness runbook
bfc6e2d Add Lane X12 1h structural implementation
4ae4313 Add Lane X11 1h activation readiness review
0627d61 Add Lane X10.10B track normal 15m runner
d0d337e Add Lane X10.10A mixed-lane memory growth audit
8b18a1b Add X10.8 closeout and X10.9 freshness audit docs
8984fb4 Add Lane X10.9 pre-snapshot freshness gate
6d81049 Add Lane X10.7 manual discovery 15m proof report
67b64b1 Add Lane X10.6 discovery selection traceability repair
d89ecb3 Add Lane X10.5 discovery selection audit
dc4b2a3 Add Lane X10 memory growth yield report
0fa9856 Repair X5 cadence and clean memory promotion
22e32a7 Add Lane X9 conservative memory growth proof
90f1a74 Add Lane X8 5m support evidence integration
12a47dc Add Lane X7 bounded discovery-to-tracking review
4f99ecf Add Lane X6 discovery selection repair
4c6ae04 Add Lane X5 five-token source-budget proof
8f63fb0 Add Lane X4 three-token 15m proof runner
5f60410 Add Lane X3 post-cycle lifecycle wiring
bb97a5c Add Lane X2 two-token 15m proof runner
```

Relevant tags observed:

- `printer-v1-memory-growth-build-order-adoption`
- `printer-v1-lane-x11-1h-activation-readiness`
- `printer-v1-lane-x12-1h-structural-implementation`
- `printer-v1-lane-x13-1h-operator-proof-readiness`
- Multiple earlier lane X tags, X5 through X10.

Working tree status:

- No tracked source/doc modifications were present before this audit doc was
  created.
- Many untracked run artifacts are present under root, `data/`, and
  `operator-runs/`.
- This audit creates one new tracked-candidate doc:
  `docs/printer-v1-current-state-memory-growth-audit.md`.

Untracked audit/run artifact sprawl includes:

- Many `lane-x*-output.txt` files in repo root.
- `operator-runs/` proof folders.
- `data/` and `data/proof_runs/` DB artifacts.

Whether code changes exist:

- No tracked code diff was observed before this audit.
- The audit did not modify source code.

Whether docs are ahead/behind the active roadmap:

- Both. The active memory-growth road map is behind actual lane history, while
  X13/X14 proof artifacts are ahead of the active roadmap anchor.

## 4. DB State Audit

All DB values below were read with SQLite read-only connections using `mode=ro`.
No live or proof DB was mutated.

### Live DB: `data/printer_v1.sqlite3`

Important table counts:

| Table | Count |
|---|---:|
| `printer_tokens` | 17 |
| `printer_pairs` | 21 |
| `printer_tracking_queue` | 15 |
| `printer_token_snapshots` | 1012 |
| `printer_memory_windows` | 156 |
| `printer_episodes` | 53 |
| `printer_memory_fingerprints` | 23 |
| `printer_source_requests` | 1118 |
| `printer_source_responses` | 1071 |
| `printer_source_failures` | 47 |
| `printer_scheduler_jobs` | 989 |
| `printer_paper_decisions` | 2 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 1 |
| `printer_memory_retrieval_queries` | 10 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_discovery_candidates` | 15 |
| `printer_solana_safety_evidence` | 12 |
| `printer_paper_quote_evidence` | 20 |

Memory windows by kind/status/data quality/do_not_train:

| Window kind | Memory status | Data quality | do_not_train | Count |
|---|---|---|---:|---:|
| `WINDOW_15M` | `PARTIAL_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | 102 |
| `WINDOW_15M` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 0 | 30 |
| `WINDOW_15M` | `AUDIT_ONLY_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | 14 |
| `WINDOW_15M` | `DIRTY_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | 4 |
| `WINDOW_15M` | `CLEAN_MEMORY` | `CLEAN_DATA` | 0 | 3 |
| `WINDOW_5M_MICRO_EVENT` | `AUDIT_ONLY_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | 2 |
| `WINDOW_15M` | null | `CLEAN_DATA` | 0 | 1 |

Memory windows by kind:

| Window kind | Count |
|---|---:|
| `WINDOW_15M` | 154 |
| `WINDOW_5M_MICRO_EVENT` | 2 |

Episodes by window/status:

| Window kind | Memory status | Data quality | do_not_train | Episode kind | Episode status | Count |
|---|---|---|---:|---|---|---:|
| `WINDOW_15M` | `CLEAN_MEMORY` | `CLEAN_DATA` | 0 | `WINDOW_15M_CLEAN_MEMORY` | `COMPLETE` | 30 |
| `WINDOW_15M` | `AUDIT_ONLY_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | `TOKEN_WINDOW_EPISODE` | `EPISODE_AUDIT_ONLY` | 14 |
| `WINDOW_15M` | `DIRTY_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | `TOKEN_WINDOW_EPISODE` | `EPISODE_DIRTY` | 4 |
| `WINDOW_15M` | `CLEAN_MEMORY` | `CLEAN_DATA` | 0 | `TOKEN_WINDOW_EPISODE` | `EPISODE_AUDIT_ONLY` | 3 |
| `WINDOW_5M_MICRO_EVENT` | `AUDIT_ONLY_MEMORY` | `MISSING_CRITICAL_DATA` | 1 | `TOKEN_WINDOW_EPISODE` | `EPISODE_AUDIT_ONLY` | 2 |

Fingerprints by data quality/do_not_train:

| Data quality | do_not_train | Count |
|---|---:|---:|
| `MISSING_CRITICAL_DATA` | 1 | 20 |
| `CLEAN_DATA` | 0 | 3 |

Token snapshots by lane/status/data quality:

| Tracking lane | Source status | Data quality | Count |
|---|---|---|---:|
| `TRACK_FAST` | `COMPLETE` | `CLEAN_DATA` | 924 |
| `TRACK_NORMAL` | `COMPLETE` | `CLEAN_DATA` | 88 |

Source requests by source/kind:

| Source | Request kind | Count |
|---|---|---:|
| `dexscreener` | `pair_market_snapshot` | 1057 |
| `dexscreener` | `token_discovery` | 17 |
| `jupiter_quote` | `paper_quote_realism` | 20 |
| `goplus` | `safety_reference` | 7 |
| `solana_rpc` | `holder_concentration_reference` | 6 |
| `coingecko` | `broad_market_context` | 4 |
| `solana_rpc` | `mint_account_reference` | 3 |
| `alternative_me` | `fear_greed_context` | 1 |
| `defillama` | `chain_liquidity_context` | 1 |
| `geckoterminal` | `geckoterminal_new_pool_discovery` | 1 |
| `geckoterminal` | `geckoterminal_trending_pool_reference` | 1 |

Source responses by source/status/data quality:

| Source | Status | Data quality | Count |
|---|---|---|---:|
| `dexscreener` | `COMPLETE` | `CLEAN_DATA` | 1033 |
| `jupiter_quote` | `COMPLETE` | `CLEAN_DATA` | 18 |
| `goplus` | `COMPLETE` | `CLEAN_DATA` | 7 |
| `solana_rpc` | `COMPLETE` | `CLEAN_DATA` | 5 |
| `coingecko` | `COMPLETE` | `CLEAN_DATA` | 4 |
| `geckoterminal` | `COMPLETE` | `CLEAN_DATA` | 2 |
| `alternative_me` | `COMPLETE` | `CLEAN_DATA` | 1 |
| `defillama` | `COMPLETE` | `CLEAN_DATA` | 1 |

Source failures:

| Source | Request kind | Failure type | Count |
|---|---|---|---:|
| `dexscreener` | `pair_market_snapshot` | `dexscreener_transport_failure` | 39 |
| `dexscreener` | `token_discovery` | `dexscreener_transport_failure` | 2 |
| `jupiter_quote` | `paper_quote_realism` | `jupiter_quote_transport_failure` | 2 |
| `solana_rpc` | `holder_concentration_reference` | `solana_rpc_rate_limited` | 2 |
| `solana_rpc` | `holder_concentration_reference` | `solana_rpc_holder_transport_error` | 1 |
| `solana_rpc` | `holder_concentration_reference` | `solana_rpc_http_error` | 1 |

Scheduler job counts by kind/status:

| Job kind | Status | Count |
|---|---|---:|
| `TRACK_FAST_FIRST_15M` | `SUCCEEDED` | 952 |
| `TRACK_FAST_FIRST_15M` | `FAILED` | 8 |
| `TRACK_FAST_FIRST_15M` | `PENDING` | 6 |
| `TRACK_NORMAL_FIRST_15M` | `SUCCEEDED` | 7 |
| `TRACK_NORMAL_FIRST_15M` | `PENDING` | 8 |
| `BACKUP_SOURCE_CHECK` | `SUCCEEDED` | 7 |
| `DISCOVERY_REFRESH` | `PENDING` | 1 |

Tracking queue by lane/status:

| Lane | Status | Count |
|---|---|---:|
| `TRACK_FAST` | `QUEUED` | 6 |
| `TRACK_NORMAL` | `QUEUED` | 8 |
| `WATCH_ONLY` | `QUEUED` | 1 |

Paper/retrieval locks:

- `printer_paper_decisions`: 2 (`NO_ACTION / PAPER_DECISION_BLOCKED`: 1,
  `WAIT / PAPER_DECISION_PROPOSED`: 1).
- `printer_paper_positions`: 0.
- `printer_paper_trade_events`: 0.
- `printer_paper_trade_audits`: 0.
- `printer_memory_retrieval_matches`: 0.

Missing expected or old-name tables:

- `printer_memories`: missing.
- `printer_retrieval_candidates`: missing.
- `printer_retrieval_results`: missing.
- `printer_selection_batches`: missing.
- `printer_active_job_locks`: missing.
- `printer_scheduler_locks`: missing.

These names may be historical/proposal names rather than required active tables.
They must not be assumed active just because docs mention similar concepts.

### X14 Attempt 3 proof DB

Proof DB:

```text
data/proof_runs/printer_v1_x14_attempt3_20260708-123214.sqlite3
```

Important proof DB deltas relative to live DB:

- `printer_token_snapshots`: 1031 vs 1012 live.
- `printer_memory_windows`: 157 vs 156 live.
- `printer_source_requests`: 1137 vs 1118 live.
- `printer_source_responses`: 1090 vs 1071 live.
- `printer_scheduler_jobs`: 1005 vs 989 live.
- Paper/retrieval rows remained locked.

Proof DB memory windows by kind:

| Window kind | Count |
|---|---:|
| `WINDOW_15M` | 154 |
| `WINDOW_1H` | 1 |
| `WINDOW_5M_MICRO_EVENT` | 2 |

Proof DB additional 1h row:

- `WINDOW_1H`, status null, `CLEAN_DATA`, `do_not_train=0`, count 1.
- Artifact identifies it as memory_window_id `157`.
- It was created by the 1h close boundary but blocked by E2Q before valid 1h
  memory closeout/promotion.

Proof DB scheduler additions:

- `TRACK_FAST_1H SUCCEEDED`: 15.
- `TRACK_FAST_1H FAILED`: 1.

Proof DB locks:

- `printer_memory_retrieval_matches`: 0.
- `printer_paper_positions`: 0.
- `printer_paper_trade_events`: 0.
- `printer_paper_trade_audits`: 0.
- No active lock table was present; X14 closeout artifact reported active locks
  as 0 and running jobs as 0.

## 5. Memory Growth Status

Has Printer grown memory?

- Yes for 15m.
- No for valid/clean 1h.
- No for operational 4h/12h/24h.

Which timeframes have real rows?

- Live DB: `WINDOW_15M` and `WINDOW_5M_MICRO_EVENT`.
- Proof DB: `WINDOW_15M`, `WINDOW_5M_MICRO_EVENT`, and one blocked
  `WINDOW_1H` row.

Which timeframes are clean?

- Clean rows/episodes are present only for 15m.
- Live DB has 3 `printer_memory_windows` rows marked `CLEAN_MEMORY` and 30
  `printer_episodes` rows with `episode_kind='WINDOW_15M_CLEAN_MEMORY'` and
  `episode_status='COMPLETE'`.
- The clean corpus appears to live mainly in episodes/fingerprints, not in a
  separate `printer_memories` table.

Which are dirty/partial/audit-only?

- Most live `WINDOW_15M` memory windows are partial or audit-only.
- Live `WINDOW_5M_MICRO_EVENT` rows are audit-only/support.
- Proof `WINDOW_1H` row is incomplete from a closeout perspective because E2Q
  blocked it.

Are there 15m clean memories?

- Yes. The strongest live evidence is 30 clean 15m complete episodes and 3 clean
  fingerprints. Do not overstate this as a mature corpus; it is still small.

Is 1h proven?

- No. X14 proved bounded 1h runtime/snapshot behavior. It did not prove valid
  1h memory audit, clean 1h episode creation, fingerprint readiness, or retrieval
  eligibility.

Are 4h/12h/24h structurally present?

- Partially in contracts, window duration helpers, and staged fixture tests.
- They are not operationally approved.
- They have no live/proof DB memory rows in the audited DBs.

What is the clean-vs-dirty yield?

- Live memory windows: 3 clean `WINDOW_15M` window rows out of 156 total windows.
- Live episodes: 30 complete clean 15m memory episodes out of 53 episodes.
- This discrepancy means the memory window table and episode table are not the
  same corpus view. Future reports must state which table they use.

What is blocking clean memory creation now?

- For 15m: mostly incomplete/dirty/audit-only evidence windows and selection
  quality, not a total lack of machinery.
- For 1h: the immediate blocker is E2Q's `WINDOW_15M` hard gate.
- For 4h/12h/24h: lack of active operational lane/proof.

Are repeated evidence windows working?

- Yes for 15m: the DB contains many 15m windows and episodes, including repeated
  evidence/cycle rows.
- This does not automatically prove clean memory is useful or diverse.

Are context/memory windows repeatable by evidence window/cycle/window_kind?

- Schema includes evidence identity fields such as `snapshot_start_id`,
  `snapshot_end_id`, `window_start_at`, `window_end_at`, `cycle_id`,
  `source_reference`, `evidence_role`, `evidence_fingerprint`, and
  `evidence_identity_hash`.
- X14's 1h row shows `window_kind` can be stored beyond 15m, but downstream
  audit acceptance is still not generalized.

## 6. X14 Status

Latest inspected X14 attempt:

```text
lane-x14-attempt-3c-fixed-bomless-writer-output.txt
operator-runs/lane-x14-attempt-3c-fixed-bomless-writer/
data/proof_runs/printer_v1_x14_attempt3_20260708-123214.sqlite3
```

Selected token:

- `token_id`: 7
- `pair_id`: 7
- `token_mint`: `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`
- `pair_address`: `6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp`

Runner status:

- Command: `printer-run-lane-x12-fast-1h-cycle`.
- `lane_x12_status`: `LANE_X12_COMPLETED`.
- Actual duration: 3620.032 seconds.
- Cadence cycles completed: 15.
- Selected token count: 1.
- Snapshots created: 15.
- Source requests created: 15.
- Source responses created: 15.
- Source failures created: 1.
- Pair drift detected: false.
- Total pair drift events: 0.
- Stop reason: duration limit reached at 1h.
- Freshness gate: `FRESH_WITHIN_PREFERRED_LIMIT`.

Hard locks preserved:

- Paper decisions created: 0.
- Positions created: 0.
- Trade events created: 0.
- Paper trade audits created: 0.
- PnL created: 0.
- Retrieval rows created: 0.
- BUY/SELL/HOLD enabled: false.

Close-window blocker:

```text
E2Q_BLOCKED: window_kind must be 'WINDOW_15M'; got 'WINDOW_1H'; 5m is not a valid main outcome window
```

Proof DB result:

- A `WINDOW_1H` memory window row was created as id 157.
- Runner summary reported:
  - `total_1h_windows_created`: 0
  - `total_window_closes`: 0
  - `clean_memory_rows_created`: 0
  - `dirty_or_blocked_memory_count`: 1

X14 classification:

```text
PARTIAL_READY_WITH_BLOCKER
```

X14 proved:

- The 1h runner can run for the full 1h duration profile.
- Fresh TRACK_FAST evidence can pass the freshness gate.
- Repeated Source-Governor/Central-Scheduler-led snapshots can be collected.
- Pair drift stayed clean.
- Locks stayed preserved.
- No retrieval/paper/BUY/positions/PnL were unlocked.

X14 did not prove:

- Valid 1h memory closeout.
- Clean 1h memory creation.
- E2Q approval for `WINDOW_1H`.
- 1h fingerprint/readiness.
- Retrieval eligibility.
- Paper decision readiness.

Whether live DB was touched:

- The inspected X14 attempt ran against a proof DB. The live DB did not receive
  the proof DB's added 1h row or added proof snapshots.

Whether X14 can be closed:

- It can be closed only as partial/blocked, not as a successful 1h proof.
- Closing X14 should preserve the proof artifacts and explicitly call out E2Q as
  the blocker.

What needs to happen before closing X14 as successful:

- A dedicated lane must inspect and generalize or stage-replace the E2Q audit
  path for `WINDOW_1H`.
- Then rerun a bounded 1h proof on an isolated proof DB.

## 7. One-Command Memory Factory Readiness

Current relevant CLI commands:

- `printer-discover-candidates-once`
- `printer-run-memory-factory-cycle`
- `printer-run-lane-x2-two-token-cycle`
- `printer-run-lane-x3-post-cycle-lifecycle`
- `printer-run-lane-x4-three-token-cycle`
- `printer-run-lane-x5-five-token-cycle`
- `printer-run-lane-x6-discovery-selection-repair`
- `printer-run-lane-x8-5m-support-integration`
- `printer-run-lane-x9-6h-conservative`
- `printer-run-lane-x10-10-normal-15m-cycle`
- `printer-run-lane-x12-fast-1h-cycle`
- `printer-run-lane-x12-normal-1h-cycle`

Does Printer currently have one safe command that can discover/select tokens,
build tracking queue, collect snapshots, close memory windows, audit clean/dirty
memory, grow clean memories, produce reports, stop safely, handle multiple
tokens, and handle multiple timeframes?

- No.

Current state by capability:

| Capability | Status | Notes |
|---|---:|---|
| Discover/select tokens | Partial | Discovery exists and records candidates, but selection diversity needs stronger memory-diet policy. |
| Build tracking queue | Partial | Tracking queue exists; post-cycle rotation/cooldown/archive remains uneven. |
| Collect snapshots | Proven for 15m, partial for 1h | 15m has many live snapshots. X14 proved 1h snapshot collection on proof DB. |
| Close memory windows | Proven for 15m, blocked for 1h | E2Q still accepts only `WINDOW_15M`. |
| Audit clean/dirty memory | Proven for 15m | 1h audit blocked. |
| Grow clean memories | Proven for 15m, small corpus | 30 clean 15m episodes, but corpus diversity/yield still need review. |
| Produce reports | Partial | Many reports exist but output artifacts are scattered. |
| Stop safely | Proven in bounded runs | X14 stopped safely at duration limit with locks preserved. |
| Handle multiple tokens | Partial | X2/X4/X5 runners exist for 15m; one-command general runner still fragmented. |
| Handle multiple timeframes | Not ready | 1h structural runner exists but downstream audit blocks; longer windows not operational. |

One-command readiness verdict:

```text
ONE_COMMAND_MEMORY_FACTORY_READY: NO
REASON: Too many lane-specific runners and a hard 1h audit blocker.
```

## 8. Multi-Token Readiness

Token-list validators:

- Older E2I/E2J pipeline enforced exactly one approved TRACK_FAST token.
- Later X2/X4/X5 runners widened proof coverage for exactly two, three, and
  five tokens in bounded 15m lanes.
- X12 1h runner supports FAST mode and NORMAL mode token lists, but it is a
  separate 1h runner, not the universal one-command Memory Factory.

Runner token caps:

- X12 FAST supports 1 to 5 tokens according to X13.
- X12 NORMAL supports 1 to 7 tokens according to X13.
- Lane U `max_active_tokens` exists but was historically not enough to make
  multi-token runtime functional by itself.

TRACK_FAST support:

- Strongest support in current system.
- Used heavily in live DB snapshots.
- X14 FAST 1h proof collected 15 snapshots on proof DB.

TRACK_NORMAL support:

- Present and proven for 15m through X10.10B.
- 1h NORMAL runner is implemented structurally but not live/proof proven.

Source budget:

- DexScreener is heavily used: 1057 live pair snapshot requests.
- X14 one-token 1h proof added 15 requests/responses with one source failure.
- Scaling beyond a small number of active tokens still needs hard budget/backoff
  proof in the current command shape.

Scheduler locks:

- Scheduler job table shows heavy use.
- No running jobs in audited post-run states.
- No explicit lock table found under searched names; active lock checks appear
  report-derived.

Pair drift detection:

- X14 artifact reports `pair_drift_detected=false` and
  `total_pair_drift_events=0`.
- Pair drift handling is present in X12 runbook and runner output.

Rotation/cooldown/archive:

- Still a gap. Discovery and queue states exist, but a fully automatic memory
  diet lifecycle is not proven.

Multi-token proof results:

- 15m multi-token proof work exists across X2/X4/X5.
- 1h multi-token proof is not proven.
- Multi-token plus multi-timeframe plus discovery is not one-command ready.

Verdict:

```text
MULTI_TOKEN_15M: PARTIAL_TO_PROVEN_BY_LANE
MULTI_TOKEN_1H: NOT_PROVEN
GENERAL_MULTI_TOKEN_FACTORY: PARTIAL
```

## 9. Timeframe Readiness

| Timeframe | Purpose | Current implementation | DB evidence | CLI support | Activation gate | Blocker | Next lane |
|---|---|---|---|---|---|---|---|
| `WINDOW_15M` | First main outcome memory | Implemented and proven | 154 live windows; 30 complete clean episodes | Multiple X and Lane U commands | Already active for memory growth | Corpus quality/diversity and one-command stability | V2-2/V2-4 |
| `WINDOW_1H` | Short-term continuation/failure memory | Structural runner and handlers exist | 1 proof DB row only, blocked | `printer-run-lane-x12-fast-1h-cycle`, `printer-run-lane-x12-normal-1h-cycle` | E2Q/Audit must accept staged 1h evidence | E2Q hardcoded to `WINDOW_15M` | V2-5 |
| `WINDOW_4H` | Medium-term memory | Fixture/staged files/tests exist | 0 live/proof rows | Staged module only, not active runtime | 1h must be proven first | Not operationally approved | V2-6 |
| `WINDOW_12H` | Long continuation/lifecycle memory | Fixture/staged files/tests exist | 0 live/proof rows | Staged module only, not active runtime | 4h proof first | Not operationally approved | V2-7 |
| `WINDOW_24H` | Full lifecycle/day memory | Fixture/staged files/tests exist | 0 live/proof rows | Staged module only, not active runtime | 12h proof first | Not operationally approved | V2-7 |
| `WINDOW_5M_MICRO_EVENT` | Support-only micro-event evidence | Implemented as support/audit | 2 live audit-only rows | Support integration lanes exist | Must remain support-only | Must never be main outcome/retrieval unlock | Keep support-only in all lanes |

## 10. Discovery and Selection Audit

Current discovery/selection is useful but not yet enough to build a money-useful
memory corpus. It is built around auditable categories and source-governed data,
which is good. The risk is memory diet, not safety scoring.

Coverage by learning category:

| Category Printer should learn | Current status | Audit note |
|---|---:|---|
| Winners | Partial | Active DexScreener surfaces are likely to include winners. |
| Losers | Partial | Dirty/partial windows exist, but deliberate loser sampling is not clearly automatic. |
| Traps | Partial | 5m support and audit labels exist, but broad trap capture is not proven at scale. |
| Dead tokens | Weak | Discovery surfaces active tokens; dead-token memory requires lifecycle/archive/revisit design. |
| Fake pumps | Partial | Memory Factory Guide requires them; proof corpus diversity not yet shown. |
| Wick-only pumps | Partial | Support labels exist conceptually; selection quotas not proven. |
| Late-buy traps | Partial | Required by guide, not proven as a balanced corpus bucket. |
| Revivals | Weak | Reopen/revival tracking is a known gap. |
| Liquidity rising | Partial | DexScreener snapshots likely capture liquidity; selection reason buckets need review. |
| Liquidity falling | Partial | Possible from snapshots, not clearly quota-managed. |
| Liquidity removed | Weak | Needs specific lifecycle monitoring and exit realism capture. |
| Volume rising | Partial | DexScreener snapshots include volume fields. |
| Volume decaying | Partial | Needs post-cycle monitoring, not just first active window. |
| Transaction spikes | Partial | Side-aware flow fields now exist in later snapshots, but older rows may lack them. |
| Transaction decay | Partial | Needs repeated windows and memory grouping. |
| Consolidation | Weak/partial | Needs selection buckets beyond active pumps. |
| Hot pair behavior | Partial | Pair snapshots and drift detection exist. |
| Migration behavior | Weak | Pump/migration coverage not proven as a corpus bucket. |
| Suspicious safety behavior | Partial | Safety evidence exists, but safety as memory bucket needs more deliberate sampling. |
| Realistic exit behavior | Partial | Quote evidence exists; paper position/PnL remain locked. |
| Unrealistic exit behavior | Partial | Quote failures/no-route can teach, but corpus balance unknown. |
| Correct avoids | Not proven | Paper decisions are locked; avoid usefulness not yet trained from retrieval. |
| Wrong avoids | Not proven | Requires later paper-decision audit lanes. |
| Correct waits | Not proven | Requires later paper-decision audit lanes. |
| Wrong waits | Not proven | Requires later paper-decision audit lanes. |

Do not fix this with scoring/ranking/confidence. The roadmap-compliant shape is:

- Auditable selection reasons.
- Memory-diet buckets.
- Quotas for winners, losers, traps, dead/stale tokens, revivals, liquidity
  decay, and exit realism.
- Explicit `TRACK_FAST`, `TRACK_NORMAL`, `WATCH_ONLY`, and archive/revisit
  transitions.
- Reports that show corpus balance before retrieval/paper review.

Discovery/selection verdict:

```text
DISCOVERY_SELECTION: PARTIAL
MONEY_USEFUL_CORPUS_SELECTION: NOT_PROVEN
NEXT NEED: memory-diet upgrade, not alpha scoring
```

## 11. Source Governor and Central Scheduler Audit

Source Governor:

- Source request/response/failure rows are present and visible.
- Approved free/public source names are represented: DexScreener, CoinGecko,
  DefiLlama, Alternative.me, GoPlus, Solana RPC, Jupiter quote, GeckoTerminal.
- X14 used governed DexScreener snapshot requests in proof DB.
- Source failures remain visible, especially DexScreener transport failures and
  Solana RPC rate limits.

Central Scheduler:

- Scheduler job table is active.
- 15m jobs dominate live DB.
- X14 proof DB created `TRACK_FAST_1H` jobs: 15 succeeded, 1 failed.
- Post-run outputs report running jobs and active locks as zero.

Direct adapter bypass risk:

- Static inspection did not prove an active bypass in X14.
- However, the command landscape is broad. Future V2 lanes should require source
  trace deltas and scheduler job deltas in every proof report.

Timeout/backoff behavior:

- X12 CLI supports throttle/backoff and source budget failure limits according
  to X13.
- X14 had one source failure and stopped safely at duration.
- Larger multi-token operation still needs runner-level budget proof.

Stale data handling:

- TRACK_FAST 1h freshness gate passed in X14.
- Earlier docs show strict freshness gates for 15m and 1h.

Pair drift handling:

- X14 pair drift stayed clean.
- Runner has pair drift reporting and reset behavior according to X13.

Dirty data handling:

- Dirty/partial/audit-only rows remain non-retrieval.
- E2Q blocked unsupported 1h audit, which is conservative and safe.

Verdict:

```text
SOURCE_GOVERNOR: PARTIAL_PASS
CENTRAL_SCHEDULER: PARTIAL_PASS
SCALING_BUDGET_FOR_MULTI_TOKEN_MULTI_TIMEFRAME: NOT_PROVEN
```

## 12. Data Quality and Clean Memory Gates

COMPLETE/CLEAN_DATA requirements:

- Token snapshots are overwhelmingly `COMPLETE / CLEAN_DATA`.
- Clean memory eligibility still depends on more than clean snapshots; context,
  evidence identity, source trace, safety, quote realism, coverage, and audit
  gates matter.

MISSING_CRITICAL_DATA handling:

- Live DB preserves `MISSING_CRITICAL_DATA` on audit-only and dirty windows.
- Source failures remain visible.

Stale handling:

- X14 used a hard freshness gate and passed it.
- Future proofs must continue to block stale evidence rather than force memory.

Malformed fixture handling:

- Prior X14 artifact names include malformed fixture inspection outputs. This
  should remain evidence of hardening, not a source of real memory.

Dirty memory blocking:

- Dirty and audit-only rows have `do_not_train=1`.
- Retrieval matches remain zero.

Memory promotion criteria:

- 15m promotion exists but is not represented consistently across windows and
  episodes. This needs clear reporting.
- 1h promotion is blocked at audit/integrity gate.

Clean memory retrieval eligibility:

- Clean-only reporting exists from Lane V, but retrieval activation remains off.
- `printer_memory_retrieval_matches` is zero.

Can dirty/audit memory leak into decisions?

- No evidence of leakage found in current DB/artifacts.
- Paper decisions count is 2 and predates current memory-growth runs; positions,
  trades, audits, and PnL remain zero.

## 13. Money-Usefulness Gap

The user's real goal is money-useful learning. V1 must remain paper-only, but it
still needs to become useful before any later paper BUY review makes sense.

What is still needed:

- A larger, diverse clean memory corpus, starting with 15m.
- Clean retrieval that can explain similar memories without dirty leakage.
- WAIT/AVOID/NO_ACTION usefulness: not just locked caution, but evidence-backed
  conservative decisions.
- Paper decision realism once retrieval is reactivated.
- Paper BUY readiness only after clean retrieval and paper realism are proven.
- Realistic entry/exit checks from safety and quote evidence.
- Liquidity, slippage, price impact, route/no-route, and exit realism labels.
- Memory corpus balance across winners, losers, traps, dead tokens, revivals, and
  wrong/correct avoid/wait outcomes.
- No fake chart profit: chart movement without realistic entry/exit must remain
  fragile/unrealistic, not money.

Current money-usefulness verdict:

```text
MEMORY_FOUNDATION: PARTIAL
CLEAN_RETRIEVAL_USEFULNESS: NOT_ACTIVE
PAPER_DECISION_USEFULNESS: NOT_READY
PAPER_BUY_READINESS: LOCKED
REAL_MONEY_READINESS: OUT_OF_SCOPE_FOR_V1
```

## 14. Drift and Complexity Audit

Where we digressed:

- The active memory-growth build order still says Lane X1 while actual work
  reached X13 and X14 proof attempts.
- X14 output exists as untracked run artifacts, not as a committed closeout doc.
- The requested X12 structural implementation doc is missing even though X12
  code/tests/commit/tag exist.
- Many root-level output files make current state hard to understand.

Unnecessary or fragile manual workflow:

- Token-list creation and BOM/encoding fixes happened manually in X14 attempts.
- Proof DB selection and backup path handling are spread across output files.
- Operator must inspect multiple JSON/text files to reconstruct a proof.

Repeated failed/partial proof attempts:

- X14 had multiple attempts (one-token proof, attempt 2, 2b, 3, 3b, 3c).
- Attempt 3C is the cleanest artifact and should be kept as the canonical X14
  evidence.

Active vs proposal-only docs:

- Active: `AGENTS.md`, clean master spec, post-RC build order, memory factory
  guide, memory-growth build order.
- Supporting audit: memory-growth automation audit.
- Recent actuals: X11/X13 docs and X14 artifacts.
- Proposal-only docs should not be treated as active unless explicitly adopted.

What should be archived or ignored:

- Keep X14 Attempt 3C artifacts as canonical current 1h proof evidence.
- Keep proof DBs under `data/proof_runs/` as audit artifacts.
- Treat older failed X14 attempt output files as background debugging unless a
  later closeout doc cites them.
- Do not use untracked root output files as active source of truth without
  committing or summarizing them in docs.

What should be kept as evidence:

- Attempt 3C runner JSON.
- Attempt 3C token list.
- Attempt 3C proof DB.
- Attempt 3C root output log.
- Read-only DB count reports in this audit.

## 15. Recommended New Build Order Shape

```text
PROPOSED ONLY - NOT ACTIVE
```

This proposed V2 shape does not supersede the active build order unless the
operator explicitly adopts it in a later task.

### V2-0: Current-State Audit

Goal: establish the factual reset map.

Allowed: docs/read-only DB and artifact inspection.

Not allowed: implementation, DB writes, source fetching, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL.

Files/docs likely affected: this document.

DB/tables likely affected: none.

Tests/checks: git status, read-only DB queries, diff checks.

Proof artifacts: current audit doc.

Acceptance gate: operator can tell what is proven, partial, blocked, and drifted.

Stop condition: any need to mutate DB or run proof.

Locks preserved: all financial/retrieval/source runtime locks.

### V2-1: Adopt/Reset Build Order

Goal: adopt a new Memory Growth Build Order V2 and update AGENTS only after
operator approval.

Allowed: documentation only.

Not allowed: code, DB writes, source fetching, memory generation.

Files/docs likely affected: new V2 build-order doc, possibly `AGENTS.md`.

DB/tables likely affected: none.

Tests/checks: docs diff, risky language scan.

Proof artifacts: adoption doc/tag if operator chooses.

Acceptance gate: active roadmap no longer points at stale X1 state.

Stop condition: operator does not approve adoption.

Locks preserved: all.

### V2-2: One-Command 15m Memory Factory Stabilization

Goal: stabilize a bounded operator-approved command for 15m memory growth without
paper decisions.

Allowed: minimal runner/reporting fixes, isolated/proof DB tests, operator report.

Not allowed: retrieval activation, paper decisions, BUY/SELL/HOLD, positions,
PnL, source bypass, unbounded runtime.

Files/docs likely affected: Memory Factory runner, CLI help, tests, report docs.

DB/tables likely affected: proof DB source/snapshot/memory tables only during
explicit proof.

Tests/checks: targeted runner tests, source/scheduler lock tests.

Proof artifacts: one-command 15m proof JSON and closeout.

Acceptance gate: bounded command grows or honestly blocks 15m memory and stops
safely.

Rollback/stop: source failure spike, running locks, financial row delta, dirty
memory marked clean.

Locks preserved: retrieval/paper/financial locks.

### V2-3: Discovery/Selection Memory-Diet Upgrade

Goal: improve selection diversity without scoring/ranking/confidence.

Allowed: auditable categories, quotas, selection reasons, bucket reports.

Not allowed: alpha scoring, BUY probability, ranking, confidence, paid data.

Files/docs likely affected: discovery/selection helpers, tests, docs.

DB/tables likely affected: discovery candidates/tracking queue reason fields if
already supported; migrations only if explicitly approved.

Tests/checks: fixtures for winners, losers, traps, dead tokens, revivals,
liquidity decay, no duplicate selection.

Proof artifacts: selection report with bucket coverage.

Acceptance gate: selected tokens are memory-useful and not winner-only.

Rollback/stop: scoring language or direct trade signal appears.

Locks preserved: all financial/retrieval locks.

### V2-4: Multi-Token 15m Conservative Proof

Goal: prove small multi-token 15m memory growth from one bounded command.

Allowed: exactly scoped multi-token proof on isolated DB, source budget gates,
pair isolation, per-token reports.

Not allowed: longer windows, retrieval, paper decisions, BUY/positions/PnL.

Files/docs likely affected: runner/tests/report docs.

DB/tables likely affected: proof DB source/snapshot/scheduler/memory tables.

Tests/checks: no token mixing, per-token evidence identity, source budget,
locks zero after exit.

Proof artifacts: proof DB, runner JSON, report.

Acceptance gate: multiple tokens can create or honestly fail 15m windows with no
cross-token contamination.

Rollback/stop: source budget breach, pair drift unhandled, dirty clean promotion.

Locks preserved: all.

### V2-5: 1h Integration and Proof

Goal: fix the 1h audit/integrity boundary and rerun a 1h proof.

Allowed: inspect/generalize E2Q or create staged 1h audit gate, tests, proof DB
run after operator approval.

Not allowed: fake 1h from 15m, 4h/12h/24h, retrieval, paper decisions, BUY,
positions, PnL.

Files/docs likely affected: E2Q/audit code, X12 runner tests, 1h proof report.

DB/tables likely affected: proof DB `printer_memory_windows`, source/snapshot,
scheduler rows.

Tests/checks: 1h accepted only when real 1h evidence passes; 5m cannot satisfy;
15m path unchanged.

Proof artifacts: clean or honest dirty 1h proof, no financial deltas.

Acceptance gate: E2Q no longer blocks valid `WINDOW_1H` only because it is not
15m; dirty 1h still blocks honestly.

Rollback/stop: any forced clean 1h, fake aggregation, or financial delta.

Locks preserved: all.

### V2-6: 4h Readiness/Proof

Goal: only after 1h proof, review and stage 4h operation.

Allowed: readiness doc, fixture tests, later isolated proof if approved.

Not allowed: 12h/24h, retrieval, paper decisions, BUY/positions/PnL.

Files/docs likely affected: 4h staged modules/tests/docs.

DB/tables likely affected: proof DB only after approval.

Tests/checks: 4h evidence cannot be satisfied by 15m/1h/5m.

Proof artifacts: 4h readiness and proof report.

Acceptance gate: 4h rows are real 4h evidence or honestly blocked.

Rollback/stop: fake long-window aggregation.

Locks preserved: all.

### V2-7: 12h/24h Lifecycle Proof

Goal: stage 12h and 24h only after 4h is proven.

Allowed: readiness reviews, bounded proof design, proof DB runs if approved.

Not allowed: paper trading unlocks, live execution, fake lifecycle memory.

Files/docs likely affected: 12h/24h staged modules/tests/docs.

DB/tables likely affected: proof DB only.

Tests/checks: lifecycle evidence completeness, source budget, stale handling.

Proof artifacts: 12h/24h proof reports.

Acceptance gate: long-window memory remains honest and bounded.

Rollback/stop: source budget exhaustion or stale data forced clean.

Locks preserved: all.

### V2-8: Memory Corpus Quality Report

Goal: report clean/dirty yield, diversity, timeframe coverage, and memory-diet
balance.

Allowed: read-only reports.

Not allowed: retrieval activation, decisions, scoring/ranking/confidence.

Files/docs likely affected: report command/docs/tests.

DB/tables likely affected: none for read-only report.

Tests/checks: report excludes dirty/5m support-only as main memory.

Proof artifacts: corpus quality report.

Acceptance gate: operator sees whether memory is useful enough for retrieval
review.

Rollback/stop: report hides dirty/stale/source failures.

Locks preserved: all.

### V2-9: Clean Retrieval Reactivation Review

Goal: review whether clean retrieval can be safely reactivated.

Allowed: docs/tests/read-only retrieval preview.

Not allowed: paper decisions, BUY, positions, PnL.

Files/docs likely affected: retrieval reporting/tests/docs.

DB/tables likely affected: none unless later approved.

Tests/checks: clean-only retrieval, no dirty/5m main leakage, diversity warning.

Proof artifacts: retrieval readiness report.

Acceptance gate: retrieval remains clean-only and explainable.

Rollback/stop: dirty/audit-only memory enters retrieval.

Locks preserved: paper/financial locks.

### V2-10: WAIT/AVOID/NO_ACTION Paper Decision Readiness

Goal: review conservative paper decisions only after clean retrieval is safe.

Allowed: docs/tests for conservative actions.

Not allowed: BUY/SELL/HOLD, positions, trades, PnL.

Files/docs likely affected: paper decision review docs/tests.

DB/tables likely affected: none until later approved.

Tests/checks: insufficient memory leads to WAIT/AVOID/NO_ACTION.

Proof artifacts: conservative decision readiness report.

Acceptance gate: conservative decisions are evidence-backed and non-position.

Rollback/stop: BUY appears or positions open.

Locks preserved: BUY/positions/PnL locks.

### V2-11: Paper BUY Readiness Review

Goal: only after clean retrieval and paper realism are proven, review BUY
preconditions.

Allowed: documentation/review unless operator approves a later implementation.

Not allowed: live trading, wallet/private keys, real funds, scoring/ranking,
positions without valid clean-memory-backed paper BUY.

Files/docs likely affected: Lane 9/10 style policy docs.

DB/tables likely affected: none in review.

Tests/checks: no auto-approval, no score thresholds.

Proof artifacts: BUY readiness policy review.

Acceptance gate: operator explicitly approves any future BUY lane.

Rollback/stop: BUY unlock treated as automatic.

Locks preserved: V1 paper-only and no live execution.

## 16. Final Recommendation

Should we adopt a new build order?

- Yes, but only after operator review of this audit.
- The next document should be a V2 reset build order that replaces the stale
  active memory-growth lane pointer and explicitly closes X14 as partial/blocked.

Should X14 be closed as pass, partial, or blocked?

- X14 should be closed as `PARTIAL_READY_WITH_BLOCKER`.
- It passed runtime/snapshot/lock safety.
- It failed the actual 1h memory closeout proof because E2Q remained 15m-only.

Should we pause more proof attempts?

- Yes. Pause more 1h proof attempts until the E2Q 1h audit/integrity boundary is
  fixed and tested.
- More X14-style runs will likely keep collecting snapshots and then block at
  the same closeout boundary.

Exact next safest action:

```text
V2-1 - Adopt/Reset Memory Growth Build Order
```

That lane should:

- Mark this audit as V2-0.
- Mark X14 as partial/blocked.
- Update the active memory-growth roadmap.
- Put the E2Q 1h audit gate repair before any further 1h proof attempts.
- Keep retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  PnL, live execution, wallet/private keys, paid APIs, scoring/ranking/
  confidence/weighted logic, embeddings, and vectors locked.

Final audit verdict:

```text
AUDIT_DOC_CREATED: YES
JSON_ARTIFACT_CREATED: NO
LIVE_DB_MUTATED: NO
PROOF_DB_MUTATED: NO
RUNTIME_RUN: NO
SOURCE_FETCHING_RUN: NO
RETRIEVAL_ACTIVATED: NO
PAPER_DECISIONS_CREATED: NO
BUY_SELL_HOLD_UNLOCKED: NO
POSITIONS_TRADES_AUDITS_PNL_CREATED: NO
NEXT_RECOMMENDED_LANE: V2-1 Adopt/Reset Build Order
```

## Addendum — 2026-08-26 Four-Token Standard-4H Source-Stack Adoption

This V2-0 audit body remains historical. Current active source-stack authority
for V2-9.8B operational envelope semantics is:

`docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md`

Current adopted envelope (capability only; not an authorization):

- V2-9.8B remains the active bounded operational Memory Factory lane;
- two cycles; exactly 2 concurrent active token slots; up to 4 distinct token
  identities across the campaign;
- concurrent capacity remains exactly 2;
- standard `WINDOW_15M` → hard-gated `WINDOW_1H` → hard-gated `WINDOW_4H` → stop;
- `WINDOW_12H` / `WINDOW_24H` locked;
- candidate-acquisition N2/N7/cursor/recovery deferred;
- implemented ≠ exercised ≠ authorized now.

The exact current next permitted lane is:

```text
POST-REPAIR FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION
READINESS / GOVERNANCE ONLY
```

Historical at the time of the 2026-08-26 source-stack synchronization:
`POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS /
GOVERNANCE ONLY`. That pointer is superseded by the later Cycle-1
historical-disjointness repair closeout and `CURRENT_HANDOFF.md`.

The historical `NEXT_RECOMMENDED_LANE: V2-1 Adopt/Reset Build Order` verdict
above is retained as V2-0 provenance only.

<!-- V2_9_8B_RETAINED_EVIDENCE_REPAIR_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Retained-Evidence Repair Closeout — Historical Authority

This current-state synchronization block supersedes earlier current-looking
V2-9.8B repair/readiness/next-sub-lane pointers in this document for the
retained-evidence repair chain. Historical lane text remains evidence only.

- implementation / bounded-proof baseline: `851d92627c3f5b05b1366af0d0dfef2712a330d8`
- authoritative DB SHA: `b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`
- bounded-proof verdict: `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_BOUNDED_PROOF_PASS`
- closeout verdict: `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_REPAIR_CLOSEOUT_PASS`
- consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c` remains permanently non-reusable
- candidate-acquisition N2/N7 remains deferred and is not a prerequisite
- no Source Governor or Central Scheduler bypass
- successful freeze remains 4 candidates -> 2 selected + 2 report-only alternates
- standard memory path remains 15m -> 1h -> 4h -> stop
- 5m remains support-only; 12h/24h remain locked
- retrieval and all financial capability remain locked

At retained-evidence repair closeout time, the next permitted lane was:

`POST-CLOSEOUT FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS / GOVERNANCE ONLY`

That lane is readiness/governance only. It does not itself authorize issuance,
execution, providers, RPC/WebSocket, Scheduler ticks, or authoritative DB writes.

This retained-evidence repair pointer is historical after later readiness and campaign closeout.
<!-- V2_9_8B_RETAINED_EVIDENCE_REPAIR_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_POST_CLOSEOUT_AUTH_READINESS_CURRENT_STATE_START -->
## V2-9.8B Post-Closeout Authorization Readiness — Historical Authority

Readiness verdict:

`V2_9_8B_POST_CLOSEOUT_FRESH_NEXT_BOUNDED_CAMPAIGN_AUTHORIZATION_READINESS_GOVERNANCE_PASS`

Audited closeout HEAD: `941ddd727b0e8b6aabf7eacbf9513f47979adb46`
Authoritative DB SHA: `b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`

The retained-evidence repair chain is closed. The historical authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c` remains permanently non-reusable.

At readiness time, the next permitted lane was:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

That lane may prepare and independently review a fresh exact-HEAD/exact-DB
one-shot authorization artifact. It does not authorize Printer execution.
Any fresh authorization must bind to the new readiness commit HEAD produced by
this synchronization and to the exact DB SHA above. Separate operator approval
is still required before execution.

All permanent V1 locks remain unchanged.

This readiness pointer is historical after the later authorized campaign closeout.
<!-- V2_9_8B_POST_CLOSEOUT_AUTH_READINESS_CURRENT_STATE_END -->

<!-- V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Authorization 8e43eae7 Campaign Closeout — Current Authority

- campaign closeout: `V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_PASS`
- authoritative post-campaign DB: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`
- consumed authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
- campaign classification: `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- Cycle 1: 2 tokens; 15m clean-promoted; 1h dirty; 4h ineligible/no successors
- Cycle 2: `NO_PAIR / DURATION_EXHAUSTION`
- no current-campaign active work
- retrieval/financial/12h/24h locks remain closed

The exact current next permitted lane is:

`REMOTE HOST READINESS / PORTABILITY AUDIT ONLY — INFRASTRUCTURE SUPPORT; NO CAPABILITY ADVANCEMENT`

This is infrastructure audit support only. It does not advance the active
memory-growth capability build order and does not authorize deployment,
migration, authorization issuance, provider/RPC/WebSocket calls, Scheduler
execution, another campaign, retrieval, financial capabilities, or longer
windows.
<!-- V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_REMOTE_HOST_PAUSE_MEMORY_GROWTH_RETURN_CURRENT_STATE_START -->
## V2-9.8B Remote-Host Pause / Memory-Growth Return — Current Authority

Operator decision: remote-host / VPS work is paused while Printer continues the
local Mac V2-9.8B bounded memory-growth path.

Completed remote-host work remains preserved separately on
`agent/remote-host-linux-portability-implementation` at `f61419f2db37fc5eb220c20fafeaf15501218033`. It is not discarded, merged into this
lane, or treated as current operational authority.

This block supersedes older current-looking remote-host lane pointers in this
document for current-lane selection only. Historical remote-host evidence
remains valid evidence.

Current preserved campaign/data baseline:

- branch before this synchronization: `agent/v2-9-8b-aug25-a2z-repair-application`
- pre-synchronization HEAD: `fd558c9e8a691ee1963509d7488aef05908f93c7`
- authoritative DB: `data/printer_v1.sqlite3`
- authoritative DB SHA-256: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`
- consumed authorization:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
- that authorization remains permanently non-reusable
- latest campaign classification remains
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- retrieval, financial capability, `WINDOW_12H`, and `WINDOW_24H` remain locked
- `WINDOW_5M_MICRO_EVENT` remains support-only

The exact current permitted lane is:

`POST-CAMPAIGN FRESH NEXT-BOUNDED-CAMPAIGN READINESS / GOVERNANCE ONLY`

This lane is read-only readiness/governance. It may establish exact final Git
identity, authoritative DB identity/health, tracked-tree cleanliness, runtime
quiescence, evidence continuity, and permanent-lock continuity.

It does not create or apply an authorization. It does not run Printer, contact
providers/RPC/WebSocket, run Central Scheduler, mutate the authoritative DB,
activate retrieval, activate financial capability, or unlock longer windows.

Only after a fresh exact-HEAD/exact-DB readiness PASS may the next separate lane
be considered:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

Separate operator approval remains required before any later one-shot execution.

Permanent V1 locks remain unchanged.
<!-- V2_9_8B_REMOTE_HOST_PAUSE_MEMORY_GROWTH_RETURN_CURRENT_STATE_END -->

<!-- V2_9_8B_POST_MIGRATION_062_READINESS_CURRENT_STATE_START -->
## V2-9.8B Post-Migration 062 Fresh Next-Bounded-Campaign Readiness — Current Authority

This block supersedes older current-looking migration, post-campaign,
remote-host, and next-bounded-campaign readiness pointers for current-lane
selection. Historical text remains evidence only.

- migration application verdict:
  `V2_9_8B_MIGRATION_062_CONTROLLED_APPLICATION_PASS`
- migration-application synchronization commit:
  `52bf15365bbf500ffe61f1b49a4d9ca38d1c3363`
- authoritative DB SHA-256:
  `dececa7ce402856978675c66ecbdfd23b88ed97e3ff23f282a2588a436c93836`
- migration state: `62 / 062_pre_admission_attempt_evidence.sql`
- reviewed product-code repair:
  `91ec3131318f5bff4d3c6dfed12b09c5b6747827`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
  remains permanently non-reusable
- readiness verdict:
  `V2_9_8B_POST_MIGRATION_FRESH_NEXT_BOUNDED_CAMPAIGN_READINESS_GOVERNANCE_PASS`
- historical `NO_PAIR / DURATION_EXHAUSTION` classification remains
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- no campaign, authorization, provider/RPC/WebSocket, Source Governor, Central
  Scheduler, retrieval, financial, or remote-host action occurred in readiness

Governing closeout:

`docs/printer-v1-v2-9-8b-post-migration-062-fresh-next-bounded-campaign-readiness-governance-closeout.md`

The exact current permitted lane is:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

Any fresh authorization must bind the final committed readiness HEAD and the
exact DB SHA above. Preparation/review does not execute Printer, and later
consumption/execution requires separate explicit operator approval. All
permanent V1 locks remain unchanged.
<!-- V2_9_8B_POST_MIGRATION_062_READINESS_CURRENT_STATE_END -->
