# V2-9.7D.6B.6 Final Campaign Report Closeout

## Result

V2-9.7D.6B.6 adds one deterministic, read-only terminal campaign-report
assembler and an atomic exact-once persistence integration. No migration was
needed: migrations 028 and 031-033 already store every required authority or
immutable link.

## Money-Usefulness Contribution

A terminal campaign is useful only when its clean yield, safety limits,
manipulation context, opportunity gaps, resource use, and stop boundary can be
reviewed together without hindsight. This report makes those independent facts
comparable in one immutable artifact. It exposes missing execution evidence and
locked capability deltas instead of turning chart movement into implied profit.

## What 6B.6 Improves

- Exact-links campaign, immutable configuration, operational run,
  authoritative B.1 run, every cycle, exactly two slots per cycle, windows,
  scheduler work, and stored 4A-5C objects.
- Requires terminal campaign/run/cycles, one immutable first cause, and one
  terminal migration 033 supervision row with completed cleanup and confirmed
  lease release.
- Loads B.1 promotion outcomes and B.2 raw/effective safety through the
  committed read-only adapters for each exact main window/checkpoint.
- Loads exactly one B.3 reconciliation event per token/pair/run and proves zero
  active associated work without executing lifecycle behavior.
- Validates every stored 4A-5C object against its canonical JSON and SHA-256
  before including the payload and exact authority links.
- Keeps 4B support-only evidence separate and preserves 5C
  `full_window_outcome` independently from
  `internal_trade_opportunity_outcome`.
- Surfaces stored `unknowns`, `gaps`, and `evidence_gaps` without filling them
  from later evidence.
- Copies B.5 launch provenance from immutable configuration storage and only
  validates it; Git is never called or recaptured.
- Includes authoritative run budgets, exact campaign-linked source/scheduler
  IDs and totals, backup/preflight references, and locked-capability
  baseline/final/current counts and deltas.
- Emits an explicit unknown gap when immutable configuration has no stored
  backup/preflight reference.
- Uses no generated assembly timestamp. Identical stored facts therefore
  produce identical canonical UTF-8 bytes and SHA-256.
- Persists a pending report, all exact object links, and the terminal canonical
  payload in one transaction. Identical repetition is idempotent; content or
  link conflict fails closed.

## What Remains Locked

This lane does not replay reports, fetch sources, run scheduler/runtime work,
execute lifecycle rotation, migrate the persistent target, expose a command,
retrieve memory, decide, BUY/SELL/HOLD, create positions, trades, audits, PnL,
wallets, signing, or live execution. Missing stored facts remain unknown or
block assembly. 6B.7 was not started.

## Proof Completed

- complete two-token terminal report assembly from disposable stored facts;
- exact campaign/configuration/run isolation;
- terminal state, first cause, lease cleanup, cancellation fields, and release
  evidence;
- B.1 promotion and B.2 effective/raw safety inclusion;
- B.3 disposition and zero-active-work evidence;
- immutable stored launch provenance equality with no recapture;
- all six required 4A-5C object kinds and exact object hashes/links;
- independent negative full-window and positive internal opportunity outcomes;
- visible manipulation unknowns and trajectory/checkpoint/segment gaps;
- exact source/scheduler identifiers, totals, budgets, and ceiling fields;
- exact backup/preflight references;
- locked-capability baseline, final, current, and zero deltas;
- repeated assembly produces identical bytes/hash;
- atomic first persistence, idempotent identical repetition, and blocked
  conflicting repetition; and
- no retrieval or financial row creation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Backup/preflight evidence has no dedicated campaign table. This lane reads
  the exact immutable configuration reference when available and reports an
  explicit gap otherwise; it does not reconstruct a 6B.2 artifact by path or
  hash discovery.
- Assembly requires all six 4A-5C object kinds. A campaign that did not persist
  a required representation blocks instead of receiving a partial final
  report.
- Locked baseline/final counts and ceiling policy come from migration 028's
  stored authoritative report. Missing or internally inconsistent values block
  final assembly.
- Current locked counts must still equal the authoritative final counts. This
  prevents a later forbidden write from being hidden by the new report.
- Report bytes include exact stored row/link fields. A future schema evolution
  needs an explicit report-schema version transition rather than silent field
  omission.

## Scope Confirmation

Verification uses disposable databases only. No persistent database, source,
runtime, lifecycle execution, replay, retrieval, decision, position, trade,
audit, or PnL path was used. Unrelated artifacts were untouched.
