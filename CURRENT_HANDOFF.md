# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

Current verified implementation HEAD before this handoff update:
`6034f52b9a3b52867c1a098dfd7455d19601e3d0`.

The failed four-token operational run was traced to Cycle-2 pre-admission /
acquisition behavior, not Cycle-1 lifecycle execution. The Cycle-2 live path now
retains the repaired +10m admission deadline, PAIR_READY deadline cancellation,
durable later-cycle StageBudget/phase diagnostics, early Cycle-2 discovery during
the spacing hold, truthful child/shared terminal reconstruction, and FAST-safe
market-vs-Gecko reconciliation separation.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor
remains the sole governed source-request owner and Central Scheduler remains the
sole scheduler owner. `WINDOW_5M_MICRO_EVENT` remains support-only;
`WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval, financial, position,
and live-trading capabilities remain locked.

For cooperative Cycle-2 acquisition:

- one MARKET_DISCOVERY quantum performs the bounded DexScreener market batch;
- unresolved exact-pool liquidity is durably left as
  `CONTRACT_BLOCKED / LIQUIDITY_UNKNOWN`;
- that state is surfaced through
  `pending_work_by_queue["RECONCILIATION_DUE"]`;
- the next lawful cooperative phase is `AUXILIARY_LIQUIDITY_BACKUP`;
- Gecko reconciliation is therefore not folded back into the FAST market
  quantum;
- `MARKET_READY` remains an intermediate reserve layer and does not by itself
  prove permanent/freeze-ready capacity.

## Latest meaningful result

GitHub Actions run `34224400136` on
`6034f52b9a3b52867c1a098dfd7455d19601e3d0` is green:

- focused post-holder/reconciliation suite: 27 passed;
- shared-boundary suite: 323 passed, 2 deselected legacy E.44 assertions,
  32 subtests passed;
- affected-module `py_compile`: passed;
- `git diff --check`: passed.

The repair from failing HEAD
`0795fe90b3cd935192a0a8c285e5951dfc1931c6` to the verified implementation
HEAD is test/fixture alignment only. No production source file was changed in
that interval. The remaining CI failures were stale fixture/contract
expectations, including migration head, campaign-pass terminal truth, canonical
attempt/FK fixtures, request-scope identity, cooperative diagnostics, and the
distinction between MARKET_READY and freeze-ready capacity.

## Proven blocker

No unresolved code blocker is proven in the audited Cycle-2 live path by the
current exact CI.

Operational readiness is not established for this branch HEAD or the
authoritative DB. The prior one-shot authorization remains consumed and
non-reusable.

## Exact next permitted action

This repair lane is closed. No authorization preparation/consumption, provider
contact, Printer run, Scheduler operational execution, or authoritative DB
mutation is permitted by this handoff.

A new engineering lane may begin from the exact current branch HEAD after
re-resolving it and reading `AGENTS.md` plus this file. Any future operational
readiness work must begin with read-only HEAD/DB/migration/integrity/FK/
zero-active-work/prior-authorization-non-reuse checks and still requires fresh
explicit operator approval before execution.
