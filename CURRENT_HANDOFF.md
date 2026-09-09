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

Standard-4H pre-marker preparation had one proven provenance blocker: approved
four-token admission-checkpoint authorization files were visible under their
own root, but that root was omitted from the Standard-4H historical
authorization roots. The Standard-4H profile now enumerates that root as
historical evidence only. Explicit current-document approval remains required;
unapproved packages still fail closed, and checkpoint documents cannot become
current Standard-4H authority. Focused disposable-state preparation coverage
passes, including multiple approved checkpoint IDs and the pre-marker parity
boundary.

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

Read-only verification/review of this repair is permitted. The next operational
workflow step, if explicitly requested after re-resolving the new commit, is
`RE-RUN_READ_ONLY_STANDARD_4H_READINESS_AND_PREPARE_FRESH_AUTHORIZATION_ON_NEW_HEAD`.
No authorization preparation/consumption, provider contact, Printer run,
Scheduler operational execution, or authoritative DB mutation is permitted by
this handoff.

A new engineering lane may begin from the exact current branch HEAD after
re-resolving it and reading `AGENTS.md` plus this file. Any future operational
readiness work must begin with read-only HEAD/DB/migration/integrity/FK/
zero-active-work/prior-authorization-non-reuse checks and still requires fresh
explicit operator approval before execution.
