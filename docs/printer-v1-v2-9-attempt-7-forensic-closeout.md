# Printer V1 V2-9 Attempt 7 Forensic Closeout

## Verdict

`V2_9_ATTEMPT_7_PROOF_PASS`

**V2-9 final-closeout readiness: YES.** Attempt 7 satisfies the V2-9 acceptance
gate: one isolated, supervised, bounded current-run lifecycle produced a genuine
`WINDOW_4H`, completed its audit/promotion path, stayed inside both budget
scopes, stopped naturally, and preserved every downstream lock. This closes the
bounded proof lane only. It does not enable generalized 4h production, V2-10,
12h/24h, retrieval, financial activity, or operational memory growth.

## Scope and provenance

- Audit date: 2026-07-17; no source, runtime, recovery, replay mutation, or test
  command was run.
- Starting/current commit: `f936e6f1eb83ea7163e795ae007c4e620ae72870`.
  The commit predates the proof, remains HEAD, and the tracked tree is clean.
  The launcher did not persist Git HEAD/status inside its artifacts, so exact
  launch-time Git provenance is reconstructed from repository history and the
  unchanged current state rather than independently embedded evidence.
- Execution: `23de3778-7c5a-409c-86c1-081421aeda8e`; run:
  `622434c6-dc6e-46ac-8f33-191afc746836`; Attempt 7 prefix:
  `v2-9-attempt7-20260717-105211`.
- Canonical preparation applied all 30 migrations, returned integrity `ok`,
  found zero foreign-key errors, and made the initial proof DB and backup
  byte-identical at SHA-256
  `BBF5787A9E1D83D7CDA26F860DAB4DBA46DA0FF7238C873EE9212AD88ACE54D9`.
  Runtime changed only the isolated proof copy, whose final SHA-256 is
  `39CCAAC72CE085E84B3BAC098EE7ECDD0537B48FA0EE78C9B6780D8D730B9F8B`.
- Persistent DB SHA-256 remains
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`,
  exactly matching both preparation-side hashes. Its critical counts were
  unchanged before/after preparation. No WAL/SHM sidecars existed before the
  immutable read-only audit.

Artifact SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| launcher JSONL | `8CF3C4F70F137E6E1B53F1EA3CE8D48D558348DBF34CFD0491C395A0BB6366BB` |
| preparation JSON | `414C77DB8A6D71412533A0142FD1A9665291DB8DEEA50E1DE3861FCF4587E485` |
| stdout | `313952C17DD9DBC863BC4FE90E38A0FCEBD22506CD33A0FDA77DE6CA9A698154` |
| stderr (empty) | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |

## Identity, cadence, and continuity

The autonomous selection chose token `18`, mint
`BCdwQBAn8dYB5YjTsoB6TdHAWokxv28k2oZUodERpump`, pair `22`, address
`2DVbU5h8JCd37gaXAJUZ4t77HsjJW22LLduTZk7GSa43`, lane `TRACK_FAST`.
All 102 ledger steps carry that one exact identity/lane. Snapshot IDs are
unique in the run ledger; no predecessor, unrelated, wrong-run, wrong-token, or
wrong-pair snapshot entered a window.

| Stage | Exact ledger snapshots | Expected/actual | Maximum gap | Result |
|---|---:|---:|---:|---|
| 15m | `1013-1028` | 16/16 | 67.415s | closed, cadence/coverage pass |
| 1h continuation | `1029-1052` | 24/24 | 129.849s | closed, continuous |
| 4h continuation | `1053-1113` | 61/61 | 190.889s | cadence pass, zero missed |

- 15m to 1h transition: 3.381s, clean. The fixed 1h deadline drift was 0s.
- 1h to 4h transition: 6.912s, clean. Window `160` is anchored to
  `2026-07-17T11:52:24.509295Z + 10,800s`; deadline drift was 0s.
- The 4h forced close arrived 5.247s after the logical deadline, inside the
  approved 60s closing-freshness allowance. Anchored duration is exactly
  10,800s; observed first-to-last snapshot span is 10,798.335s.
- The 15m resolver retained its distinct zero-second evidence allowance:
  cutoff equals `2026-07-17T11:07:22.201750Z`, its exact closing boundary.
  The 4h cutoff is separately `2026-07-17T14:53:24.509295Z`. Both shared
  contexts report `non_ledger_snapshot_ids=[]` and no boundary blocker.

## Evidence and memory result

The 4h shared resolver reports `clean_memory_context_ready=true` and zero
blockers. Chart evidence is clean (`PATH_ROUND_TRIP`, `CHART_CONTEXT_ACCEPTABLE`),
so the negative/round-trip market path did **not** become dirty merely for being
unfavourable. Flow is honestly partial/caution (`TRADING_FLOW_CONTEXT_PARTIAL`,
`FLOW_CONTEXT_CAUTION`, wallets unknown) but provenance-clean and permitted by
the approved flow contract; wash detection remains unavailable rather than
fabricated.

Opening quote `23` is attached to snapshot `1053`; closing quote `24` is attached
to snapshot `1113`. Both are exact-target, fresh, complete Jupiter evidence with
ENTRY/EXIT routes available. Closing safety composite `2` is exact-target,
fresh, complete, provenance-complete, and attached to snapshot `1113`; mint,
freeze, metadata, supply, holder concentration, and token-program checks passed.
Liquidity-lock/burn and known-risk flags remain explicitly optional unknowns.
The legacy contract label remains `SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY` and
`safety_action_label=BLOCK_CLEAN_MEMORY`, although the approved shared 4h gate
records no safety blocker. That naming mismatch should be clarified before any
future productionization; it did not bypass the V2-9 gate as currently defined.

E2Q returned `E2Q_AUDIT_CLEAN_CANDIDATE`, Lane Q returned `LANE_Q_VALID`, and
Lane K returned `LANE_K_COMPLETED`. E2Z created exactly one clean episode:
episode `55`, window `160`, kind `WINDOW_4H_CLEAN_MEMORY`, status `COMPLETE`,
`CLEAN_MEMORY`, `CLEAN_DATA`, `do_not_train=0`. The source window correctly
remains the pre-promotion `PARTIAL_MEMORY` candidate with no rejection reasons.

There is one report defect: top-level `memory_results`, `run_local_yield`, and
`per_token_outcomes` classify the run as zero-clean/`BLOCKED_QUALITY` by reading
the source window label, while the nested Lane K result and authoritative
`printer_episodes` row record the successful clean promotion. The audit uses the
promotion row as authoritative. This under-reporting did not create an unsafe
memory or unlock anything, but should be repaired before an operational campaign.

## Sources, budgets, scheduler, and supervision

- Full lifecycle: 113 requests, 112 responses, one failure; 102 scheduler rows.
  Sources were DexScreener 101 requests/100 responses, GeckoTerminal 3/3,
  CoinGecko 3/3, GoPlus 2/2, Jupiter 4/4.
- The only failure was a DexScreener TLS `BAD_RECORD_MAC` at 15m snapshot step
  14. The already-governed single GeckoTerminal fallback supplied snapshot
  `1027`; there was no retry or endpoint rotation and the exact failure remains
  persisted.
- 4h phase: 66/69 requests and 61/64 scheduler rows; zero holder fallback,
  automatic retries, or endpoint rotation. Cumulative lifecycle: 113/116
  requests and 102/105 rows. All projected/actual checks report within ceiling.
- Run jobs: 101 succeeded plus one cancelled discovery handoff; no failed,
  pending, or running proof step/job remained. Historical pending jobs copied
  from the persistent DB are not Attempt 7 jobs.
- Launcher JSONL has 6,665 valid lines, 471 successful renewals, one transient
  atomic lock-file renewal failure, and a maximum heartbeat-event gap of
  53.080s against a 90s lease. The next renewal succeeded; supervision never
  expired. Child PID `12524` completed naturally, forced termination is false,
  the one-proof lock is absent, and no Attempt 7 process remains.
- Terminal supervision is `COMPLETED` with first reason
  `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`; cleanup reports zero running jobs.
  Stdout is complete and parseable; stderr is empty; launcher JSONL is healthy.

## Replay, deltas, and locks

The database has no duplicate run snapshot attachment, no duplicate stage
window, and exactly one episode for window `160`. Recovery/report deltas are all
zero. No post-run live replay was invoked during this audit; replay/idempotency
therefore rests on the duplicate-free artifact plus the focused V2-8.1/V2-9.4
fixture contract, not on a second live Attempt 7 close.

Full-run deltas reconcile to 101 snapshots, four windows (5m support, 15m, 1h,
4h), 102 run steps/jobs, 113 requests, 112 responses, one failure, four quote
rows, two safety composites, and the one clean episode. Retrieval queries and
matches, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade
audits, paper audit reports, and PnL all have zero delta. The final report also
records retrieval, paper decisions, and financial locks preserved.

## Money-usefulness and final assessment

Attempt 7 supplies the first continuous, exact-ledger, real-cadence 4h lesson:
the token moved through a low-volatility round-trip/choppy regime while entry
and exit remained realistic and safety/provenance remained traceable. That is a
useful loss/avoidance-pattern memory, not winner-only selection. It proves the
medium-term evidence machine can preserve an unfavourable outcome without
calling trustworthy evidence dirty.

### Functionality Risks / Setbacks / Efficiency Blockers

1. Top-level yield reporting understates the clean E2Z promotion; reconcile
   window-candidate and episode-promotion reporting before operational use.
2. The safety label says 15m-only/`BLOCK_CLEAN_MEMORY` while the approved 4h
   shared gate accepts the exact evidence. Clarify timeframe-specific naming or
   policy before generalized 4h production; do not silently broaden it.
3. One transient heartbeat lock replacement failed. Lease continuity remained
   safe, but repeated Windows atomic-replace contention could still threaten a
   later long run.
4. Wallet-level flow authenticity remains unknown, so wash-like behavior cannot
   be proven from this provider payload. No claim beyond partial flow is valid.
5. Attempt 7 is one token and cannot establish diversity or corpus yield.
6. Git HEAD/clean status is not embedded in launcher artifacts, and live
   report-only replay was not separately executed. Both are auditability gaps,
   not evidence-integrity failures in this run.

V2-9 may be closed on this PASS. Any later repair or operational campaign needs
separate operator scope. No next lane is started here.
