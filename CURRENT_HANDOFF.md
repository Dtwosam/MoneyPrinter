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

Checkpoint 2 has one retained repair: the hard +600s Cycle-2 admission deadline
is now enforced both before a cooperative acquisition quantum and again after a
PAIR_READY return, so a bounded quantum cannot cross the deadline and still
admit.

The subsequent Cycle-2 terminal-tracking concern was audited through the full
production call chain and was **not** a defect. Phase A cycle reconciliation is
immediately followed by the canonical shared terminal owner,
`reconcile_admitted_campaign_terminal`, which iterates every admitted cycle and
owns each slot/queue terminal disposition. A temporary audit patch that archived
unstarted Cycle-2 queues in Phase A was therefore reverted so it cannot preempt
the canonical Phase-B `SKIPPED/MANUAL_REVIEW` or `COOLDOWN` disposition.

Cycle-2 atomic admission, frozen tracking authority, materialization, WINDOW_15M
opening ownership, Scheduler cycle resolution/fairness, and the cycle-scoped
15m-to-1h barrier have been reviewed with no additional retained defect so far.

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

Continue the read-only line-by-line audit through standard WINDOW_1H collection,
the cycle-scoped 1h→4h progression/handoff, WINDOW_4H execution/close, canonical
two-cycle accounting, and shared terminal/cleanup. No operational authorization,
provider contact, Printer run, Scheduler operational execution, or authoritative
DB mutation is permitted by this handoff.
