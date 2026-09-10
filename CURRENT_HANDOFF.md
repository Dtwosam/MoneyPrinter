# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

The 2026-09-10 third four-token Standard-4H operational attempt ran untouched
from Terminal on HEAD `b56c4366acf5f27e4ffe2e936b1ff7a726185ee3` under one-shot
authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260910T185027Z_e8409028`.
It passed the prior protocol-sequence and zero-call market-budget defects, reached
holder/safety enrichment, then failed closed before Cycle-1 admission with
`ACTIVATION_REPORT_ALTERNATES_INCOMPLETE`.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole source-request owner and Central Scheduler the sole scheduler owner.
`WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and `WINDOW_24H`
remain locked. Retrieval, decision, position, PnL, wallet, signing and live
trading capabilities remain locked.

The third live failure proved a residual four-candidate assumption in the memory
activation validator. The canonical freeze gate correctly requires only two fresh
observation-eligible candidates (`MINIMUM_FREEZE_DEPTH = 2`), and surplus target
8 is diagnostic only, but activation still required exactly two report-only
alternates in addition to the two selected slots.

The repair removes only the mandatory alternate-count gate. Exactly two selected
candidates remain mandatory and retain all identity, tracking, expiry, evidence
role, manifest, transport and source-response validation. Any 0-2 alternates
remain report-only diagnostics and do not acquire activation authority.

## Latest meaningful result

Focused local verification after this repair:

- dedicated activation-route boundary: 5 passed;
- targeted retained-evidence/zero-alternate checks: passed;
- integrated four-token Standard-4H audit: 3 passed;
- affected-module compile: passed;
- `git diff --check`: passed.

Targeted Cycle-1 admission search found no other production gate requiring 3, 4
or 8 freeze-ready candidates. Remaining `alternates[:2]` uses are report/state
projections and tolerate fewer than two items.

The third failed campaign is terminal failed, cleanup complete, lease released,
and has zero active locked Scheduler work. Its authorization is permanently
consumed and must never be reused.

## Proven blocker

`ACTIVATION_REPORT_ALTERNATES_INCOMPLETE` is repaired at code/test level. Literal
Cycle-1 admission and four clean 4h memories remain unproven until a separately
authorized operational attempt on the repaired exact HEAD.

## Exact next permitted action

Review and commit/push this repair. Any further operational attempt requires a
fresh one-shot authorization bound to the repaired exact HEAD and current
authoritative DB after the normal integrity/FK/zero-active-work/non-reuse gates.
Do not reuse any consumed authorization.
