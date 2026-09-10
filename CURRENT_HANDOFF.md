# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

The 2026-09-10 four-token Standard-4H operational attempt on HEAD
`465f55a8ad0cad46fcfde06b6f21a8f3b75fe584` consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260910T163157Z_387091e1` once and failed
closed before lifecycle admission. The exact terminal cause was a duplicate
six-unit stage identity at `PROTOCOL_CONFIRMATION|2`.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole source-request owner and Central Scheduler the sole scheduler owner.
`WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and `WINDOW_24H`
remain locked. Retrieval, decision, position, PnL, wallet, signing and live
trading capabilities remain locked.

The live failure exposed a non-cooperative protocol-stage sequencing defect:
early protocol confirmation owns stage 1; refresh ordinal N owns protocol stage
N+1; final residual protocol was incorrectly hard-coded to stage 2. After any
refresh ordinal 1 this collided with the refresh-owned stage 2 and the canonical
duplicate-stage guard correctly terminalized the campaign.

The repair preserves the duplicate guard and all source/evidence/budget/admission
contracts. Final residual protocol now advances beyond the highest refresh-owned
protocol stage, while remaining stage 2 when no refresh occurred.

## Latest meaningful result

Focused local verification after the repair:

- protocol/local-validation boundary: 6 passed;
- integrated four-token Standard-4H audit: 3 passed;
- affected-module compile: passed;
- `git diff --check`: passed.

The failed operational campaign is terminal failed, cleanup complete, lease
released, and has zero active Scheduler work. Its authorization is permanently
consumed and must never be reused.

## Proven blocker

The duplicate non-cooperative residual `PROTOCOL_CONFIRMATION|2` assignment is
repaired at code/test level. No new operational run has been authorized or
performed on the repaired HEAD, so live four-memory success is not yet proven.

## Exact next permitted action

Complete focused code review and branch verification for this repair. A later
operational attempt requires a fresh authorization bound to the exact repaired
HEAD and current authoritative DB, with the normal read-only migration,
integrity/FK, zero-active-work, provenance, and prior-non-reuse gates first.
