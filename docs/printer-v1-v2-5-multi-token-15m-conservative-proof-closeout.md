# Printer V1 V2-5 Multi-Token 15m Conservative Proof Closeout

## Status

Verdict: `V2_5_MULTI_TOKEN_15M_PROOF_PASS`

The V2-5 readiness repair was implemented and verified, and one bounded,
isolated three-token `WINDOW_15M` proof ran to completion with three independent
terminal window outcomes, honest dirty gating, correct token isolation, bounded
budgets, report-only replay safety, and zero downstream activation. The
persistent database SHA-256 and all critical table counts were identical before
and after. No second proof was run. This closeout does not start or approve V2-6.

## Repair And Tests (Gates 1–2)

Repair (`src/printer_v1/operator_cli/one_command_15m_factory.py`, CLI flag
`--v2-5-proof-mode`):

- **Explicit three-token proof mode** permits exactly three autonomous tokens.
  Normal mode stays capped at two; four or more is rejected in both modes.
- **Token-local failure isolation.** A token-local terminal failure (exact-pair
  source failure, invalid opening snapshot, target mismatch, token-local close
  blocker, or an unexpected per-step exception) marks only that token blocked
  and cancels only its pending jobs (`_cancel_pending_for_token`); other tokens
  continue within their own budgets. Global integrity/budget breaches
  (`_GlobalStop`), total-duration exhaustion, ambiguous job state, and operator
  interrupt still cancel the entire run.
- **Hard ceilings enforced before every call**, never silently exceeded: 2
  discovery requests, 47 governed requests run-wide, 15 per token, 1 holder RPC
  fallback per token, 33 scheduler rows, 1,200 seconds, zero retries.
- **Run-local reporting separated from historical Lane K.** `per_token_outcomes`,
  `terminal_window_outcomes`, `run_local_yield` (authoritative by run-step
  attached `memory_window_id`s), `run_budgets`, and an explicit
  `historical_report_note` labelling embedded Lane K/E2Z pipeline summaries as
  non-authoritative for yield or verdict.

Tests: `tests/test_v2_5_multi_token_15m_conservative.py` (14 focused tests) plus
the updated `tests/test_v2_4_one_command_15m_factory.py` (15). All 29 pass. The
verified properties: three-token mode accepted while normal stays two and four
is rejected; token A failure does not cancel B/C; token-local cancellation is
scoped; a projected per-token/run breach raises a global stop; no cross-token
snapshot or memory-window evidence; run/per-token/scheduler budgets within
ceilings; `TRACK_NORMAL` six and `TRACK_FAST` ten per token; three independent
first-snapshot anchors; report-only replay creates no writes; retrieval and
financial tables are zero-delta; run-local yield excludes historical noise.

The readiness repair was committed before the live-proof boundary
(`ae2d549 Repair V2-5 three-token conservative proof readiness`).

## Proof Setup (Gate 3)

- Command path: `run_one_command_15m_factory` in explicit V2-5 proof mode,
  operator-approved, proof-mode, `WINDOW_15M` only, no manual candidates.
- Database: a fresh isolated copy of the persistent DB with all migrations
  applied, plus a separate verified backup of that proof copy (identical hash).
  The command rejects the canonical persistent path (verified).
- Autonomous selection: exactly three qualified active tokens from live governed
  GeckoTerminal discovery; seed `237da02d8a8435ce266027ed37b04bc8`; eligible
  pool size 28.
- Zero automatic retries, zero endpoint rotation, five-second source timeout,
  1,200-second hard duration cap. No code or budget changes after start.
- run_id `e2103dfd-3b33-4bf5-84fa-637acaeb41e5`.

## Per-Token Results

All three tokens reached an independent terminal window with at least 900
seconds of persisted evidence. All three closed honestly dirty (`do_not_train`,
`E2Q_AUDIT_DIRTY`); none was promoted clean.

| Token (mint prefix) | Lane | Snapshots | Evidence duration | Safety | Flow | E2Q / window | Terminal |
|---|---|---:|---:|---|---|---|---|
| `5UUH9RTDiS…` | TRACK_NORMAL | 6/6 | 903.7 s | ACCEPTABLE_FOR_15M_MEMORY_ONLY | FLOW_DISTRIBUTION / STRONG_OUTFLOW | E2Q_AUDIT_DIRTY / DIRTY_MEMORY | DIRTY |
| `FAu1PPYSaV…` | TRACK_NORMAL | 6/6 | 907.0 s | SAFETY_BLOCKED_FOR_15M_MEMORY (holder unknown) | FLOW_EXHAUSTION / BALANCED | E2Q_AUDIT_DIRTY / DIRTY_MEMORY | DIRTY |
| `FeMbDoX7R1…` | TRACK_FAST | 10/10 | 909.4 s | ACCEPTABLE_FOR_15M_MEMORY_ONLY | FLOW_CHOPPY / STRONG_INFLOW | E2Q_AUDIT_DIRTY / DIRTY_MEMORY | DIRTY |

Context areas exercised per token close: market regime and Solana chain heat
(6 rows each area across the three closes), exact-target safety composite (3
composites, 4 contributions), holder concentration (one governed RPC fallback,
returned unknown for the safety-blocked token), exact-target ENTRY/EXIT paper
quotes (6 quote-evidence rows), side-aware trading flow (labelled per token),
and support-only 5m context. The common clean-blocker across all three was
`micro_event_state_label=MICRO_EVENT_UNKNOWN`; the safety-blocked token also
carried holder/rug/flow/chart blockers and `NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE`.
`terminal_window_outcomes = 3`.

## Failure Isolation

No token failed token-locally in this natural sample (all three reached their
windows), so no per-token cancellation fired during the proof. The isolation
machinery itself is proven by the Gate-2 fixtures: token A opening-snapshot
failure leaves B and C to complete, cancels only A's pending jobs, and yields
`terminal_window_outcomes >= 2` with `run_status = COMPLETED`. Global stop
conditions (budget/scheduler/governor/identity/DB/lock) cancel every pending
job. No retries were introduced; continuing unrelated tokens is not a retry.

## Budgets And Scheduler State

| Ceiling | Limit | Observed |
|---|---:|---:|
| Governed requests, run-wide (excl. discovery) | 47 | 35 |
| Governed requests per token | 15 | 10 / 11 / 14 |
| Discovery requests | 2 | 2 |
| Holder RPC fallbacks | 1/token | 1 total |
| Scheduler rows (run-step + cancelled handoffs) | 33 | 25 (22 + 3) |
| Automatic retries | 0 | 0 |
| Total duration | 1,200 s | within cap; natural completion |

Terminal scheduler state: `running_jobs_after_stop = 0`,
`pending_or_running_run_steps = 0`. Every run-owned scheduler row finished
`SUCCEEDED`, `FAILED`, or `CANCELLED`; no locks or ambiguous states.

## Clean/Dirty Yield

Run-local authoritative yield (by run-step attached `memory_window_id`s):
clean 0, dirty 3, blocked 0, token-local-failed 0. Zero clean is valid and
honest. Embedded Lane K/E2Z pipeline summaries are labelled non-authoritative
and did not affect per-token yield or verdict.

## Persistent DB Safety, Replay, Locked Tables

- Persistent DB SHA-256 unchanged: `97DB9A15…FB177FBB` before and after.
- All critical persistent table counts unchanged (zero diff).
- Proof-run writes landed only in the isolated proof copy (deltas: 3 discovery
  candidates, 3 windows, 22 snapshots, 25 scheduler jobs, 3 safety composites,
  6 quote-evidence rows, 1 source failure, etc.).
- Report-only replay: 0 new source calls, 0 new evidence rows; proof-DB hash and
  all counts unchanged by replay.
- Forbidden/financial and retrieval deltas all zero: retrieval queries/matches,
  paper decisions, paper positions, paper trade events, paper trade audits,
  paper audit reports. No dedicated PnL table exists; the PnL-bearing paper
  tables are all zero-delta.

## Money-Usefulness

The factory now operates safely at a minimally scaled three-token conservative
proof with per-token failure isolation. One unavailable token or a rate-limited
public RPC response cannot silently prevent other selected tokens from reaching
their natural 15-minute outcomes, and cannot bias the run. This proof produced
zero clean memories but three honest dirty windows that correctly record real
source, safety, flow, and micro-event constraints without polluting the clean
corpus — useful operational evidence about what blocks clean promotion at scale.

## Remaining Risks / Blockers

- Public holder-RPC availability is operationally unstable; one token was
  honestly safety-blocked when holder concentration returned unknown. This is
  handled (bounded one call, no retry/rotation, honest block), not repaired.
- Natural samples may lack lane/category diversity; diversity is observed, not
  manufactured. This sample was two `TRACK_NORMAL` and one `TRACK_FAST`.
- Clean yield depends on live source completeness; `MICRO_EVENT_UNKNOWN` blocked
  clean promotion for all three even when other areas were acceptable.

## What Remains Locked

Solana-only, memecoin-only, paper-only, `WINDOW_15M` only, 5m support-only. No
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, keys, funds, paid APIs, scoring/ranking/confidence/weighted logic,
embeddings/vectors, Source Governor bypass, Central Scheduler bypass, or
persistent-DB mutation. V2-5 does not unlock `WINDOW_1H`/4h/12h/24h or
main-window use of `WINDOW_5M_MICRO_EVENT`.

## Next Lane

Chosen from the evidence, not started: a bounded lane to reduce the dominant
clean-promotion blocker observed at scale — governed close-time evidence for the
`MICRO_EVENT_UNKNOWN` / `HELD_TO_15M_UNKNOWN` labels (still `WINDOW_15M`,
support-only 5m, no new window kind) — so that structurally valid three-token
windows can reach clean promotion when the live sources are complete. V2-6 is
not started.
