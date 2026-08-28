# CURRENT_HANDOFF — Printer V1

## Current lane

`V2-9.8B 4/2/2 ORCHESTRATION CORRECTNESS REPAIR — IMPLEMENTATION + BOUNDED OFFLINE PROOF ONLY`

This is a bounded repair lane inside active V2-9.8B. It does not authorize an
operational campaign, source/provider execution, a fresh one-shot authorization,
retrieval, paper decisions, or any financial capability.

## Operator lane decision

Remote-host / VPS work remains paused.

Preserved remote-host branch:

`agent/remote-host-linux-portability-implementation`

Preserved remote-host HEAD:

`f61419f2db37fc5eb220c20fafeaf15501218033`

That work remains available for later resumption and is not part of this repair.

The operator has directed the approved 4/2/2 orchestration repair implementation
to continue.

## Exact pre-implementation baseline

Branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Design HEAD before this governance synchronization:

`8b902554889ba4422b9815705a4cb076d6e9788a`

Design commit:

`Design 4/2/2 orchestration correctness repairs`

Authoritative DB:

`data/printer_v1.sqlite3`

Authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

The authoritative DB is not an implementation/test target. It must remain
unmodified in this lane.

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

It remains permanently consumed and non-reusable.

## Governing audit/design state

The 4/2/2 orchestration correctness audit/root-cause investigation is complete.
The committed design verdict is:

`V2_9_8B_4_2_2_ORCHESTRATION_CORRECTNESS_DESIGN_PASS`

Governing design:

`docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-design.md`

Narrow Cycle-2 implementation amendment:

`docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-design-amendment.md`

The amendment supersedes only the original design's Cycle-2 micro-quantum
implementation mechanics. It does not weaken its safety/evidence invariants.

## Proven repair scope

1. Bind the exact pre-created `WINDOW_1H` campaign row to its physical memory
   row and commit/read it back before Lane Q/E2Z.
2. Make Cycle-2 direct acquisition schedulable beside TRACK_FAST cadence by
   yielding between existing Source-Governed requests, replaying already-terminal
   deterministic request-key results locally, and reusing the existing Scheduler
   attempt/refresh owners rather than introducing a parallel child-job hierarchy.
3. Preserve cumulative attempt evidence across cooperative yields so terminal
   shortage/certificate reporting is reduced from durable attempt evidence, not
   only the final in-memory invocation.
4. Restore the existing independent action-local transport observer on every
   accounting-active discovery/holder path and preserve cumulative pre-close
   reservation identities instead of overwriting prior claims.

## Exact permitted actions

Allowed now:

- documentation/governance synchronization for this repair;
- focused RED tests on disposable/offline fixtures;
- minimum production-code changes justified by those RED tests;
- additive migration `062` only for attempt-owned evidence required by the
  amended design;
- focused GREEN tests and directly affected regressions;
- implementation/bounded-proof closeout if those checks pass.

Not allowed now:

- mutate or migrate the authoritative DB;
- run Printer operationally;
- contact providers, RPC, WebSocket, or source endpoints;
- apply or create a fresh one-shot authorization;
- run Central Scheduler against the authoritative DB;
- retry/reuse/resume/restart the consumed authorization or campaign;
- weaken Source Governor, cadence, memory-quality, exact-pair, liquidity,
  holder/safety, historical-disjointness, or accounting gates;
- unlock retrieval, BUY/SELL/HOLD, paper positions, trades, audits, or PnL;
- activate `WINDOW_12H` or `WINDOW_24H`;
- give `WINDOW_5M_MICRO_EVENT` main-memory, continuation, retrieval, decision,
  position, or PnL authority.

## Next permitted action after this lane

Only after implementation + bounded offline proof + closeout PASS may the next
separate lane return to fresh exact-HEAD / exact-DB readiness/governance for a
future bounded campaign.

A repair closeout does not itself create authorization or approve execution.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No wallet/private
keys/signing/real funds/live execution. No paid API dependency. No
scoring/ranking/confidence/weighted decision logic. No Source Governor or
Central Scheduler bypass. No dirty-memory retrieval/decisions. Retrieval and
all financial capability remain locked. `WINDOW_5M_MICRO_EVENT` remains
support-only. `WINDOW_12H` and `WINDOW_24H` remain locked.

The active authority stack wins any conflict with this handoff.
