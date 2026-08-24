# V2-9.8B Consumed 4/2/2 Pre-Lifecycle Terminal-Accounting Repair Design

Date: 2026-08-24

## Classification and root cause

The consumed 4/2/2 attempt exposed a `CROSS_PATH_TERMINAL_ACCOUNTING_DEFECT`
and `COMMITTED_CODE_DEFECT`. `finalize_four_token_shared_terminal` has two
intentional production invocation modes, but the factory bridge introduced by
Lane 4 accepts only the accounted mode. A lawful one-cycle/no-Cycle-2-admission
terminal therefore calls the bridge with no arguments and raises `TypeError`.

The repair does not reinterpret or repair the deeper
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` condition. Its narrower
`PreAdmissionAttemptError` detail was not durably retained.

## Dual-mode bridge contract

The adapter remains the admitted-shape authority.

### One-cycle/no-admission mode

When the adapter has proved either `ONE_CYCLE_HONEST_NO_ADMISSION` or
`ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`, it invokes `shared_terminalizer()`.
The bridge must:

- require exactly one Phase-A cycle terminal result;
- consume that result's already-derived `cycle_state` and
  `first_terminal_cause`;
- map `TERMINAL_COMPLETED` to `COMPLETED`, `TERMINAL_FAILED` to `FAILED`, and
  the lawful `TERMINAL_STOPPED` / `TERMINAL_BLOCKED` states to `SAFE_STOPPED`,
  failing closed on any other state;
- invoke the canonical shared terminal/cleanup owner exactly once; and
- preserve the adapter-proved one-cycle provenance without claiming Cycle 2,
  six-unit completeness, or two-cycle completion.

No accounting object may be derived or fabricated in this mode. A missing
argument is lawful only because the adapter has already proved a one-cycle
shape.

### Two-cycle completion mode

When the adapter has proved `TWO_CYCLE_COMPLETION`, it derives canonical
two-cycle terminal accounting and invokes
`shared_terminalizer(terminal_accounting=...)`. The bridge retains its current
strict accounting behavior. Missing, malformed, active/incomplete, or
ambiguous accounting must fail closed; none may fall back to one-cycle mode.

## Cause, reporting, and non-goals

The Phase-A first cause remains primary in one-cycle mode, including
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`. Later accounting or reporting must
not replace it. Existing report construction remains unchanged: incomplete
six-unit evidence continues to block a canonical terminal report rather than
produce an overclaim.

This repair does not make Cycle 2 admission succeed, repair the underlying
persistence failure, reuse the consumed authorization, create missing evidence,
alter the authoritative database, change cleanup/reporting ownership, change
providers or budgets, or unlock any memory, retrieval, decision, financial,
Cycle 3, 12h/24h, or V2-10 capability.

## Focused TDD proof matrix

| Production condition | Required result |
| --- | --- |
| Real Cycle-2 pre-admission persistence failure leaves one admitted cycle | No bridge `TypeError`; exact Phase-A cause/status reach canonical cleanup once |
| Approved pre-lifecycle zero-attempt provenance | Same no-accounting mode; provenance retained; one terminalization |
| Valid canonical two-cycle accounting | Existing accounted path succeeds unchanged |
| Missing accounting for a two-cycle shape | Fail closed; no one-cycle fallback |
| Active/incomplete two-cycle accounting | Fail closed |
| Ambiguous two-cycle accounting | Fail closed |
| Incomplete six-unit report evidence | Report remains blocked; no fabricated completion |

Tests must create the underlying production condition on disposable databases.
They must not inject the terminal classification, admitted shape, accounting
payload for the one-cycle case, or the observed `TypeError`.
