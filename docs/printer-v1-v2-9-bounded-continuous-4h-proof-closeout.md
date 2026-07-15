# Printer V1 V2-9 Bounded Continuous 4h Proof Closeout

## Status

Lane: `V2-9 - Bounded Continuous 4h Proof`

Final verdict: `V2_9_BOUNDED_4H_PROOF_FAIL`

Exactly one new proof ran after V2-9.1. The same autonomous Solana memecoin
reached 5m support, WINDOW_15M, and WINDOW_1H, then collected 24/31 required
NORMAL 4h snapshots. DexScreener transport failed on snapshot 25. Zero automatic
retries ran; remaining work was cancelled and running jobs cleared. The proof
did not reach the fixed deadline, forced close, WINDOW_4H, or quality gates.
The top-level COMPLETED label and lifecycle budget accounting also failed
closedness expectations. This does not activate 4h production or begin V2-10,
12h, 24h, retrieval, decisions, positions, trades, audits, or PnL.

## Preserved History

The first V2-9 attempt at `3776716` stopped before runtime because its raw
persistent-DB copy lacked canonical migration-028 run-ledger tables. It made no
source call and created no run. V2-9.1 proved migrations had been skipped,
added canonical isolated preparation, and passed at `06fed48`. The unusable
first proof/backup were discarded. No runtime was retried.

## Preflight

All gates passed: exact HEAD `06fed4840155f6e6ed3b736f63f552c003ec5aa4`,
clean tracked tree, `316,946,014,208` free bytes, canonical isolated
preparation, all 29 migrations, complete V2-8.1 schema/integrity/foreign-key
validation, and backup only after validation. Prepared proof/backup were
byte-identical at
`7D3632A1541EAFDF74EF513B839DA61DDC3370D392DEC5BD0D208CBC167C11AC`.
Persistent SHA-256 stayed
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
Focused schema, cadence, continuity, runtime, E2Q, Lane Q, Lane K/E2Z,
scheduler/resource, replay/isolation, retrieval-lock, and financial-lock tests
exited green. WINDOW_12H/WINDOW_24H remained disabled. No code, budget,
endpoint, cadence, or configuration changed during runtime.

## Identity And Anchors

| Field | Observed |
| --- | --- |
| Run | `34777faa-b2e8-4f27-943c-85c0129cce65` |
| Token | `18`; `E6TwnwYzhFt8pvREAzy7tnZb2QYXN543byVSW5m7pump` |
| Pair | `22`; `78Wc7TzBUXd4pPhYuY9e8tAktNXWccVq4BoFM1D67xrq` |
| Lane | `TRACK_NORMAL` |
| 5m / 15m / 1h IDs | `158 / 157 / 159` |
| 4h successor | None |
| 1h close | `2026-07-15T10:55:24.013464+00:00` |
| Fixed deadline | `2026-07-15T13:55:24.013464+00:00` |
| 1h-to-4h gap | `2.212684s`; clean range |
| Deadline drift | `0s`; never extended |

Identity/linkage was automatic and current-run-only. Nothing was manually
linked.

## Cadence And Outcome

NORMAL required 31 snapshots at 360s. Twenty-four snapshots, IDs `1035-1058`,
were current-run-ledger-only. Every gap was:

`358.624397, 360.127869, 359.869216, 360.134458, 360.046636,
359.546946, 360.322822, 359.842878, 359.936638, 360.659897,
359.271337, 360.189808, 360.255420, 359.941686, 359.732430,
360.133075, 359.843685, 360.043887, 360.047288, 360.040695,
360.143288, 359.636377, 360.242621`.

Maximum gap: `360.659897s`; observed span: `8,278.633354s`; missing: 7.
Closing lateness is unmeasurable because close never ran. Stop was about
`2,159.38s` before deadline, so no final duration, freshness, cadence, or
continuity verdict exists.

Step `t18_p22_4h_snapshot_024` scheduled
`2026-07-15T13:19:24.013464+00:00` failed with
`dexscreener_transport_failure` (request `1174`, failure `49`). Long steps:
24 succeeded, one failed, six cancelled including forced close. Terminal token
status: `TOKEN_LOCAL_FAILED`; terminal 4h outcomes: zero.

## Context, Quality, Realism

15m `157` was `DIRTY_MEMORY`, `MISSING_CRITICAL_DATA`,
`do_not_train=1`; 5m stayed support-only. Exact 1h predecessor `159` was
`PARTIAL_MEMORY`, `CLEAN_DATA`, with no clean promotion. Opening evidence
had fresh market/chain context, paper ENTRY route, acceptable
liquidity/impact/slippage, chart and flow evidence, but safety was
blocked/unknown and EXIT realism unknown. 4h opening context ran; closing
market/chain, safety, EXIT, chart, and flow could not complete. With no
WINDOW_4H, 4h E2Q, Lane Q, and Lane K/E2Z were not reached; ordering was not
bypassed. No memory/fingerprint was created.

## Sources, Budgets, Scheduler, Cleanup

Proof delta: 56 requests, 54 responses, two failures. Run-step-linked usage:
47 (8 initial snapshots plus close, 12 1h snapshots plus close, 25 executed 4h
snapshots). The report counted 27 4h-phase requests including opening context,
within phase ceiling 39. Holder fallback: one. Endpoint rotation: zero.
Automatic retry: zero; scheduler `retry_count=1` records the one failed
execution, not a second execution.

The 4h plan created 31 scheduler rows, within phase ceiling 34. Lifecycle total
was 54 scheduler rows. The runner reported 54 governed lifecycle requests
against its own ceiling 47 and 54 per-token against ceiling 45, both
`within_ceiling=false`, while returning `COMPLETED`. Under this prompt's
NORMAL full-run ceilings 39 requests/34 scheduler rows, lifecycle totals also
exceed limits. This budget/status inconsistency is a FAIL condition.

Cleanup: 46 succeeded, one failed, six cancelled run-named jobs; zero
pending/running steps and zero running jobs. No second proof/retry ran.

## Replay, DB Deltas, Locks

Report-only replay made zero DB delta. Proof hash before/after replay:
`B53B819ED7479DDA352C81191C7E5DEA80CFEBE3891009206968D15F71445A3E`.

Proof deltas: 54 scheduler jobs/steps, one run, 46 snapshots, three windows
(5m/15m/1h), 56 requests, 54 responses, two failures. No WINDOW_4H, clean
memory, or fingerprint.

Persistent DB stayed byte-identical at counts: sources `1118/1071/47`,
scheduler `989`, snapshots `1012`, windows `156`, fingerprints `23`,
retrieval `10/0`, decisions `2`, positions/events/trade-audits `0/0/0`,
run-ledger `0/0`. Proof deltas were zero for retrieval, decisions, positions,
trade events/audits, audit reports, memories, and fingerprints. BUY/SELL/HOLD,
PnL, wallet/key/signing/live execution, paid-source, scoring/ranking/confidence,
weighted logic, embeddings, and vectors stayed locked.

## Files Changed

- `docs/printer-v1-v2-9-bounded-continuous-4h-proof-closeout.md`
- Local evidence: `operator-runs/v2-9-bounded-continuous-4h-proof.json` and
  `operator-runs/v2-9-bounded-continuous-4h-replay.json`

## What Was Not Touched

Production code, migrations, adapters, budgets, endpoints, scheduler policy,
persistent DB, 12h/24h, retrieval activation, decisions, positions, trades,
audits, PnL, or live-trading capability.

## Functionality Risks / Setbacks / Efficiency Blockers

1. One transport failure cancels the remaining long proof.
2. Incomplete 4h token-local work is labeled `COMPLETED`.
3. Lifecycle accounting conflicts with V2-9 and report ceilings.
4. Closing context, final cadence/continuity, E2Q, Lane Q, Lane K/E2Z, and 4h
   memory quality remain unproved live.
5. This sole authorized proof cannot be retried in this lane.

## Pass/Fail Status

`V2_9_BOUNDED_4H_PROOF_FAIL`

Cleanup, replay, isolation, and locks were safe, but there was no audited 4h
result or full-runtime evidence-quality block. The run stopped early, exceeded
lifecycle ceilings, and reported completion without WINDOW_4H.

## Next Recommended Phase

Stop in V2-9. Do not begin V2-10, 12h, or 24h. A separately approved repair
lane should reconcile lifecycle budgets and make incomplete token-local 4h
termination fail closed before any new proof.
