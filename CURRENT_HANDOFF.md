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

Checkpoint 1 repaired Cycle-1 post-holder cooperative resume so campaign-owned
durable fresh MOE carriers survive the post-holder resume boundary.

Checkpoint 2 repaired the hard +600s Cycle-2 admission seam: the boundary is
enforced both before a cooperative acquisition quantum and again after a
PAIR_READY return.

The later lifecycle audit found Cycle-2 atomic admission/materialization,
WINDOW_15M opening, Scheduler cycle ownership/fairness, WINDOW_1H collection,
cycle-scoped 1h→4h progression, WINDOW_4H execution/close, and canonical shared
terminal cleanup structurally cycle-safe.

A separate terminal-report contradiction was then proven. The generic factory
report can be computed from Cycle-1-rooted validation before canonical Phase-B
two-cycle accounting terminalizes the shared factory row. A Cycle-2 structural
failure could therefore leave the durable factory row SAFE_STOPPED while its own
`final_report_json.run_status` still said COMPLETED.

The repair does not add another classifier. After canonical Phase B, the report
now projects the already-committed non-running factory `run_status`,
`stop_reason`, and `finished_at`. Missing/active/no-cause durable terminal
truth fails closed. Post-report integrity then runs, followed by a second exact
match check so later integrity logic cannot silently re-diverge the report from
the durable canonical terminal.

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

Verify the fixture-alignment commit in the focused GitHub Actions workflow. If
green, finish the read-only audit of the final two-cycle accounting/report and
action-local terminal-evidence surfaces, then record the resulting verified
HEAD. No operational authorization, provider contact, Printer run, Scheduler
operational execution, or authoritative DB mutation is permitted by this
handoff.
