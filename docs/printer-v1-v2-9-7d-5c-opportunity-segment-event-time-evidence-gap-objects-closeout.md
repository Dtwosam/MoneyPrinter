# V2-9.7D.5C Opportunity-Segment and Event-Time Evidence-Gap Objects Closeout

## Scope

V2-9.7D.5C adds pure, immutable, fail-closed representations for bounded
opportunity segments and their event-time execution-evidence gaps. It reuses
the committed 5A identity, trajectory, observation, provenance, checkpoint,
cutoff, and re-entry vocabularies; the committed 5B manipulation context and
unknown vocabulary; existing episode outcomes; and the adopted Jupiter,
GoPlus, GeckoTerminal, and public-RPC evidence boundaries.

The lane performs no source call, execution simulation, profitability
calculation, persistence, orchestration, retrieval, decision, position, trade,
audit, or PnL action.

## Money-Usefulness Contribution

Printer can now retain bounded internal opportunity paths without rewriting a
negative full-window outcome. It also distinguishes a visible chart path from
a realistically executable path and keeps observed peaks separate from exits
that could have been captured with event-time evidence. This prevents hindsight
chart returns, descriptive liquidity, or manipulation labels from becoming
fake paper profit while preserving useful path structure for later memory.

## What 5C Improves

- Fixes the twelve approved tradeable-path contexts as categorical vocabulary.
- Keeps `full_window_outcome` independent from
  `internal_trade_opportunity_outcome` and supports multiple ordered segments
  inside one exact-linked main window.
- Freezes campaign, run, cycle, slot, token, mint, pair, root 15m lifecycle,
  containing main window, trajectory, checkpoint, manipulation context,
  observations, provenance, and immutable cutoff linkage.
- Keeps `CHART_OPPORTUNITY` separate from
  `REALISTICALLY_EXECUTABLE_OPPORTUNITY`.
- Represents route, quote, freshness, usable liquidity, impact, slippage, fees,
  latency, duration, failed-route, executable-size, and exit-capability gaps
  explicitly as `CURRENT_EVIDENCE_GAP` or `UNKNOWN_REQUIRES_RESEARCH`.
- Requires exact adopted quantitative contract fields and governed Jupiter
  provenance before all event-time requirements can be called complete.
- Retains GoPlus, GeckoTerminal, and public-RPC evidence as context only; it
  cannot prove execution, wallet authenticity, or participant independence.
- Rejects foreign, mismatched, stale, unsupported, post-cutoff, untraceable,
  gap-crossing, and incomplete evidence.
- Requires a distinct fresh checkpoint and evidence cutoff for re-entry.
- Evaluates later evidence separately without mutating a frozen segment.

## What Remains Unknown or Locked

Provider freshness where not contract-proven, wallet control, beneficial
ownership, participant independence, coordination, insider status,
authenticity, intent, and identity remain unknown. Descriptive pool liquidity,
OHLCV, token-account, holder, safety, and route categories do not establish a
fill, executable size, capturable exit, or profit.

Source calls, execution simulation, profitability calculations, persistence,
runtime orchestration, retrieval, paper decisions, BUY/SELL/HOLD, WAIT, AVOID,
NO_ACTION activation, positions, trades, audits, PnL, wallets, keys, signing,
fund movement, and live execution remain locked. No locked capability row is
created.

## Proof Completed

- Syntax compilation and direct import checks passed.
- Focused 5C proof: 12 tests and 18 subtests passed in 0.14s, including all
  twelve contexts, independent outcome layers, ordered multi-segment windows,
  explicit provider gaps, anti-look-ahead, wick-only blocking, fresh re-entry,
  immutability, and determinism.
- Focused committed 5A checkpoint linkage: 12 tests and 7 subtests passed in
  0.10s.
- Focused committed 5B manipulation linkage: 15 tests and 24 subtests passed in
  0.14s.
- Jupiter paper-quote fixture contract: 11 tests and 29 subtests passed in
  21.68s.
- GoPlus normalization contract: 15 tests passed in 0.19s.
- GeckoTerminal payload/identity contract: 21 tests passed in 1.06s.
- Public-RPC safety evidence contract: 7 tests and 10 subtests passed in
  13.49s.
- `git diff --check` and staged `git diff --cached --check` passed.
- No broad regression suite, source call, runtime command, or database mutation
  ran.

## Functionality Risks / Setbacks / Efficiency Blockers

- Jupiter's current categorical fixture/storage path does not retain the full
  adopted quantitative contract, so it cannot produce complete execution proof
  without a later separately approved repair.
- Provider receipt time does not universally prove provider observation time or
  freshness; honest gaps can therefore reduce segment completeness.
- GeckoTerminal reserve/liquidity and GoPlus DEX/LP descriptions are not
  executable quote or exit evidence.
- Public RPC token accounts and transactions cannot prove beneficial ownership,
  authentic independent participants, coordination, or intent.
- Exact event-time proof is intentionally demanding and may leave many useful
  chart opportunities non-executable or unknown.
- Objects are in-memory representations only. Integration and persistence remain
  outside this lane.

## Verdict

V2_9_7D_5C_OPPORTUNITY_SEGMENT_EVENT_TIME_GAPS_PASS
