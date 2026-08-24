# V2-9.8B Consumed 4/2/2 Pre-Lifecycle Terminal-Accounting Repair Closeout

Date: 2026-08-24

Verdict:

`V2_9_8B_CONSUMED_4_2_2_PRE_LIFECYCLE_TERMINAL_ACCOUNTING_REPAIR_CLOSEOUT_PASS`

## Baseline and scope

- Starting HEAD: `9f5135abc5aaf19b2673936461fb3d6869a7b073`.
- Accepted design: `db9079fc3859374b35c9d602a1b11f9607d2de93`.
- Accepted implementation: `9f5135abc5aaf19b2673936461fb3d6869a7b073`.
- The implementation changed exactly one production file:
  `src/printer_v1/operator_cli/one_command_15m_factory.py`.
- `four_token_factory_adapter.py`, campaign accounting, reporting, cleanup,
  Scheduler, Source Governor, providers, schema/migrations, and authorization
  logic were not changed.

## Closed repair contract

The shared callback accepts optional `terminal_accounting`. `None` is lawful
only after the adapter selects a no-accounting one-cycle shape. That branch
requires exactly one Mapping Phase-A result and a non-empty
`first_terminal_cause`; maps `TERMINAL_COMPLETED` to `COMPLETED`,
`TERMINAL_FAILED` to `FAILED`, and `TERMINAL_STOPPED` or `TERMINAL_BLOCKED` to
`SAFE_STOPPED`; and fails closed for zero/multiple Phase-A results, a non-Mapping
result, missing cause, or unknown state. It invokes the existing shared terminal
owner once. The accounted two-cycle branch and its strict validation are
unchanged.

## Focused proof

The real Cycle-2 boundary test injected `PreAdmissionAttemptError` at
`link_pre_admission_source_evidence`. Production derived the attempt as
`FAILED / LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`, Cycle 1 and the campaign as
`TERMINAL_BLOCKED` with the same cause, and the factory as `SAFE_STOPPED` with
the same cause. The adapter selected `ONE_CYCLE_HONEST_NO_ADMISSION`, supplied
`terminal_accounting=None`, and called shared cleanup exactly once. No
`TypeError` or Cycle-2 fabrication occurred; lease release and zero active
Scheduler ownership were preserved.

The current pre-lifecycle zero-attempt contract passed with
`ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`, exact provenance, one terminalization,
and no fabricated accounting. The two-cycle opposite proofs passed for valid
canonical accounting and failed closed for missing progression,
`ACTIVE_INCOMPLETE`, `INTERRUPTED_AMBIGUOUS`, partial accounting, and missing
report evidence. Two Phase-A results cannot enter the `None` branch.

Focused result: 34 passed. Four historical fixture tests remain red at this
starting HEAD: one has a pre-callback opening-failure fixture defect, one expects
an obsolete projection length (11 rather than 12), one lacks current strict
two-cycle accounting completeness, and one expects completion from a shape now
canonically `INTERRUPTED_AMBIGUOUS`. These are baseline debt, not repair
regressions, and were not changed.

## Cause and reporting preservation

`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` remains the first cause from Phase A
through shared terminalization in the focused proof. Reporting was not changed.
Incomplete six-unit evidence remains blocked; no canonical report or six-unit
accounting is fabricated. The consumed campaign's null report path and
`RECONSTRUCTED` terminal truth remain historical incident evidence.

## Authoritative incident evidence

- Database SHA-256:
  `9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`.
- SQLite integrity: `ok`; foreign-key violations: `0`; unsafe sidecars: `0`.
- Authorization:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd` remains consumed.
- Marker SHA-256:
  `1ecb94577b08a1ab7cb5546a2f09a65f81373a9b819a9b1d21756f80632993f4`.
- Marker policy continues to prohibit retry, rerun, resume, restart, and a
  successor. No authorization, campaign, provider, Governor, Scheduler, or
  Printer execution occurred during closeout.

## Remaining failure and next action

This lane did not repair `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`. The consumed
real run encountered that condition, while its narrower original
`PreAdmissionAttemptError` detail was not durably retained. Existing evidence
therefore cannot truthfully establish a narrower persistence cause. This is a
separate unresolved production incident requiring audit/readiness before any
design or authorization; it cannot be dismissed as merely the focused test's
injected condition.

Exact next permitted action:

`V2-9.8B LATER-CYCLE PRE-ADMISSION PERSISTENCE FAILURE FORENSIC / READINESS AUDIT ONLY`

No new authorization or campaign is permitted by this closeout.

## Permanent locks

Solana-only, Solana-memecoin-only, paper-only, free/public-source, Source
Governor, Central Scheduler, memory-quality, and capability restrictions remain
unchanged. No wallets, keys, signing, funds, paid APIs, scoring, ranking,
confidence, weighted logic, embeddings, vectors, Cycle 3, 12h/24h, retrieval,
BUY/SELL/HOLD, positions, trades, audits, PnL, or V2-10 capability was unlocked.
