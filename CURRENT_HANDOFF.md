# Printer V1 Handoff

## Current capability

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.
Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is the sole governed source-request owner and Central Scheduler the sole scheduler owner. `WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Only clean evidence may become training memory.

## Latest operational result

The latest four-token Standard-4H attempt used consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260911T162112Z_65293461` and campaign `20260911T165838Z-346816d52ab7-campaign`. The authorization is permanently non-reusable. The run terminalized safely with `DURATION_EXHAUSTION`, cleanup complete, lease released, and zero locked/pending Scheduler work.

Cycle 1 completed all 30 snapshots and all 15m close phases. Both Cycle-1 windows were `CLEAN_PROMOTED` and created two clean episodes. Cycle 2 never admitted.
## Proven blocker and repair

Real provider traffic proved the prior mixed protocol-stage collision repaired: PumpSwap used `protocol-q1-1` and generic-present-pool used `protocol-q2-1`, both `COMPLETE / CLEAN_DATA`.

The new Cycle-2 blocker was a cooperative `MARKET_DISCOVERY` starvation loop. The terminal attempt still had 18/30 discovery operations unused, 46 unexplored candidates, six eligible reserve candidates, and `freeze_ready_depth=0`. Forensic reconstruction showed all six failed only because retained `MARKET_OBSERVATION` evidence was missing.

The exact cause is negative-history front-slice starvation: after durable resume rehydrated prior completed market mints, the next deterministic 30-row slice could consist entirely of exact-pool cooldown-suppressed identities. Suppression correctly consumed zero source requests, but because it happened only inside the market owner after slicing, pollable identities behind the slice were never reached before the Cycle-2 deadline.
The repair applies the existing `decide_exact_pool_poll(...)` law before the cooperative 30-mint cap. Cooldown-suppressed identities remain durable local truth, consume zero provider budget, and are not weakened; they simply cannot starve pollable inventory behind them.

TDD proof: an exact resume fixture with 30 cooldown-suppressed rows in the post-resume front slice and one pollable row behind it was RED with zero market calls on the prior code and is GREEN after the repair, reaching the pollable row with exactly one governed market request.

Focused current-contract verification: 44 passed, including negative-history suppression semantics, the new exact resume regression, mixed protocol sequencing, generic protocol resume, and the full disposable two-cycle Standard-4H proof. The residual closeout file still has 10 stale-fixture failures; an untouched detached `aa31d26f` worktree reproduces the same 10 failures, so they are baseline debt rather than this repair.

## Exact next permitted action

Commit and push this repair, then verify CI on the exact pushed HEAD. Only after CI is green may another provider-driven four-token Standard-4H attempt be considered. Any such attempt requires a fresh one-shot authorization bound to that exact HEAD and the then-current authoritative DB after migration/integrity/FK/zero-active-work/non-reuse gates. Never reuse any consumed authorization.