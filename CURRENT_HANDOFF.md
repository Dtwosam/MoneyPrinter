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

GitHub Actions run `34362009907` on terminal-report repair HEAD
`84a7fa76e6179ad2a0abd5705bc393d7123269d8` proved the production change but
exposed two stale wake-ordering fixtures:

- focused post-holder/reconciliation tests passed;
- shared-boundary suite: 329 passed, 2 failed, 2 deselected, 32 subtests passed;
- both failures monkeypatched `finalize_four_token_shared_terminal` to claim
  success while leaving `printer_memory_factory_runs.run_status='RUNNING'`;
- the real Phase-B adapter explicitly rejects that shape and cannot return
  successful shared terminal evidence until the durable factory row is
  non-running.

The fixture repair keeps the production fail-closed synchronization unchanged.
Its shared-terminal stub now preserves the already-persisted stop reason and
performs only the minimum durable factory terminal transition required by the
real Phase-B contract.

## Current audit checkpoint

Discovery/admission hardening found a structural multi-source starvation defect.
The active authority allows exact present-market candidates from DexScreener and
GeckoTerminal without Pump lineage, but fresh nominations were filtered by
provider venue and every above-floor row was forced through a PumpSwap-only pool
decoder. Valid non-Pump/unknown-origin present pools therefore could never reach
`MEMORY_OBSERVATION_ELIGIBLE`.

The repair keeps one conversion owner and one stage budget. Pump/PumpSwap rows
retain the existing exact PumpSwap decoder. Other above-floor rows use one new
Source-Governed Solana request kind,
`generic_present_pool_account_batch`, which proves the supported SPL/Token-2022
mint program, exact provider mint/base/allowed-quote relationship, exact pool
account owner, and that the exact owner program account is executable. Provider
venue remains provenance only and is never promoted to program authority.

Promotion now preserves the exact observed token program, pool program and venue
instead of hardcoding SPL/PumpSwap identities. Campaign fresh-MOE rehydration is
no longer PumpSwap-only, so the same generic carriers are available to Cycle 1
post-holder resume and Cycle 2 cooperative resume. Cooperative protocol stage
sequence reconstruction includes both governed conversion request kinds.

This does not add a second selector, source preference, retry, endpoint rotation,
or request budget. Holder/safety/tradeability remain their existing downstream
categorical evidence surfaces; this repair only restores the already-defined
`MARKET_PRESENT_POOL` memory-observation admission authority.

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

Run focused GitHub verification for the generic present-pool conversion repair.
Then continue the read-only discovery/admission audit for false-shortage
conditions in cohort caps, durable work-remaining/universe-exhaustion
classification, Cycle-1 refresh opportunity, Cycle-2 cooperative quantum
opportunity, freeze surplus handling and exact two-slot admission. No operational
authorization, provider contact, Printer run, Scheduler operational execution,
or authoritative DB mutation is permitted by this handoff.
