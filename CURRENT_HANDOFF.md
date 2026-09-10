# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

The 2026-09-10 second four-token Standard-4H operational attempt ran on HEAD
`ed5c82f950b56f332e6894a5b2375fd1b234316a` under one-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260910T175519Z_b7431591`. It passed the
previous duplicate `PROTOCOL_CONFIRMATION|2` failure, then failed closed before
Cycle-1 admission with `BUDGET_EXHAUSTION`.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole source-request owner and Central Scheduler the sole scheduler owner.
`WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and `WINDOW_24H`
remain locked. Retrieval, decision, position, PnL, wallet, signing and live
trading capabilities remain locked.

The second live failure proved a market-stage accounting defect. Permanent
supply consumed one `market_batching` reservation before calling the canonical
market resolver, even when the resolver emitted zero measured market calls.
After a temporal refresh marked the two retained eligible candidates stale for
mandatory revalidation, the false pre-charge could exhaust the two-slot market
stage while 13 flat source operations and acquisition time still remained.

The repair preserves the two-operation `market_batching` ceiling. It keeps the
pre-call capacity gate but charges the stage only after the resolver returns,
using the resolver's measured `market_calls`; zero-transport suppressed rounds
consume zero stage capacity.

## Latest meaningful result

Focused local verification after this repair:

- later-cycle mint-market replay repair boundary: 13 passed;
- integrated four-token Standard-4H audit: 3 passed;
- affected-module compile: passed;
- `git diff --check`: passed.

The second failed operational campaign is terminal failed, cleanup complete,
lease released, and has zero active Scheduler work. Its authorization is
permanently consumed and must never be reused.

## Proven blocker

The false `market_batching` pre-charge is repaired at code/test level. No new
operational run has been authorized or performed on the repaired HEAD, so
literal Cycle-1 admission and four clean 4h memories are not yet proven.

## Exact next permitted action

Review and commit/push this repair, then require a fresh operational authorization
bound to the exact repaired HEAD and current authoritative DB before any further
Printer/provider/RPC/Scheduler execution. Do not reuse either consumed 2026-09-10
authorization.
