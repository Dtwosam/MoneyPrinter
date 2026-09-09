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

## Current audit checkpoint

Checkpoint 1 repaired Cycle-1 post-holder cooperative resume so campaign-owned
durable fresh MOE carriers survive the post-holder resume boundary.

Checkpoint 2 has now repaired two independent Cycle-2 seams:

1. The hard +600s admission deadline is enforced both before a cooperative
   acquisition quantum and again after PAIR_READY returns, so a quantum cannot
   cross the admission boundary and still admit.
2. An admitted Cycle 2 that fails before creating any WINDOW_15M window or
   lifecycle work now archives its exact insert-bound tracking claims during
   shared cycle terminal reconciliation. Generic post-cycle tracking cleanup is
   rooted in the original Cycle-1 selection batch and cannot discover this
   pre-opening Cycle-2 authority on its own.

The new cleanup is restricted to non-success Cycle 2 with zero cycle-owned
windows and zero cycle-owned lifecycle work. It reuses the canonical
`terminalize_unstarted_cycle_tracking_claims` owner; started lifecycle cycles
retain their existing reconciliation path. No source budget, retry, successor,
selection, cadence policy, or Scheduler ownership is widened.

## Cycle-1 terminal-truth repair

The consumed admission-checkpoint authorization
`V2_9_8B_FOUR_TOKEN_ADMISSION_CHECKPOINT_AUTH_20260908T172327Z_884c7694`
remains permanently non-reusable. Its Cycle-1 post-holder resumed supply had
the authoritative `BUDGET_EXHAUSTION` shortage classification, but campaign
terminal truth was incorrectly collapsed to
`INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`; its deferred certificate was therefore
not persisted at the real terminal boundary.

The repair preserves an authoritative resumed-supply shortage classification
at that boundary, allowing the existing single deferred certificate owner to
persist the exact budget-exhaustion certificate. Focused disposable-state
coverage verifies the budget terminal, exact certificate persistence, ordinary
generic shortfall behavior, and the post-holder request-provenance path. This
does not change budgets, source policy, candidate selection, holder/tracking
policy, or operational readiness.

Operational readiness is not established for this branch HEAD or the
authoritative DB. The prior one-shot authorization remains consumed and
non-reusable.

## Exact next permitted action

Continue the read-only audit at the Cycle-2 WINDOW_15M opening/execution boundary,
then audit two-cycle Scheduler interleaving, WINDOW_15M close, 1h continuation,
4h continuation, canonical accounting, and shared terminal cleanup. No
operational authorization, provider contact, Printer run, Scheduler operational
execution, or authoritative DB mutation is permitted by this handoff.
