# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

Current working repair is based on HEAD `3fea021169f87d25c773daeb5866863f2d840c44`.
The latest operational four-token Standard-4H attempt used consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260911T125355Z_fd058235` and campaign
`20260911T125702Z-7722e529dce2-campaign`. That authorization is permanently
non-reusable. The attempt terminalized safely with zero active Scheduler/factory
work and exposed a Cycle-2 six-unit stage collision after Cycle 1 completed its
15-minute lifecycle work.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is the
sole governed source-request owner and Central Scheduler the sole scheduler owner.
`WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and `WINDOW_24H`
remain locked. Dirty, partial, conflicting, stale, or missing-critical evidence
must not become training memory.

## Latest meaningful result

A line-by-line audit of the Cycle-2 path found four concrete correctness issues.

1. Protocol-stage sequence allocation ignored `generic_present_pool_account_batch`
   while sharing the same `protocol-qN-*` namespace with PumpSwap. The allocator
   now reconstructs sequence ownership from both lawful protocol request kinds.
2. Supply-exception terminalization reused the Scheduler-quantum start timestamp
   after source work completed. Failure terminal/job timestamps now use completion
   time so durable chronology is truthful.
3. Four-token through-4h validation accepted truthful `DIRTY` / `NO_PROMOTION`
   outcomes as proof completion. Ordinary Standard-4H still reports those outcomes,
   but the four-token proof now requires clean-promoted/idempotently clean 4h memory.
4. Cycle-2 temporal refresh still passed hard-coded `required_capacity=4`. It now
   uses canonical `MINIMUM_FREEZE_DEPTH` (2), matching the two-token-per-cycle
   contract without lowering evidence or safety gates.

The downstream audit found no additional cross-cycle identity leak: materialization,
Scheduler ownership, 15m execution, selective 1h handoff, 4h handoff, peer-cycle
terminal isolation, and 12h/24h exclusion remain cycle-scoped.

Focused verification:
- mixed generic/PumpSwap sequence RED `[1,1,2,2]` is repaired to `[1,2,3,4]`;
- terminal chronology RED is repaired;
- non-clean 4h proof now fails closed;
- Cycle-2 refresh uses `MINIMUM_FREEZE_DEPTH`;
- positive proof fixtures create genuine clean 4h episode/fingerprint objects;
- focused affected verification: 39 passed;
- full disposable two-cycle Standard-4H factory audit passes with clean 4h objects.

One unrelated callback fixture remains baseline debt: its nominal PAIR_READY carrier
lacks the now-required frozen tracking-lane identity. An untouched detached
`3fea0211` checkout reproduces the same failure, so it is not a regression here.

## Proven blocker

The latest provider-driven run did not complete four clean 4h memories. Its direct
Cycle-2 blocker was the now-repaired mixed protocol stage-sequence collision. No
fresh provider-driven attempt has yet proven the repaired path end-to-end.

## Exact next permitted action

Commit/push this repair and verify CI on the exact pushed HEAD. Only after CI is
green may a new operational attempt be considered. Any operational attempt requires
a fresh one-shot authorization bound to that exact HEAD and the then-current
authoritative DB after migration/integrity/FK/zero-active-work/non-reuse gates.
Never reuse any consumed authorization.
