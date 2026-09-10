# Printer V1 Handoff

## Current implementation

Branch: `assistant/v2-9-8b-cycle1-cycle2-four-hour-admission-proof`.

The current branch HEAD contains the four-token Standard-4H pre-consumption
composition repair described below. The immediately preceding fully verified
four-clean-memory production anchor is
`7b3f7ae2253ae20ee58c1193b2b5b60f57129cc2`.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor
remains the sole governed source-request owner and Central Scheduler remains the
sole Scheduler owner. Retrieval, decisions, positions, PnL, signing, wallets and
live trading remain locked. `WINDOW_5M_MICRO_EVENT` is support-only;
`WINDOW_12H` and `WINDOW_24H` remain locked.

The deterministic four-token/two-cycle path still proves exactly two Cycle-1
slots plus a fresh/disjoint two-slot Cycle 2 can progress through owned
`WINDOW_15M -> WINDOW_1H -> WINDOW_4H` lifecycles and form four exact clean 4h
episode/fingerprint pairs when governed evidence is clean.

The operational four-token one-shot wrapper now also performs the existing
zero-I/O source/composition construction preflight before it creates the
irreversible application marker. A deterministic missing, disabled,
transportless, wrong-source or invalid RPC configuration therefore blocks while
the authorization is still unconsumed and before any child launch.

No network reachability probe, retry, endpoint rotation, source ownership,
Scheduler ownership, evidence gate or clean-memory threshold was added or
relaxed.

## Latest meaningful result

A read-only wall-clock operational-readiness audit found a real one-shot
sequencing defect: unlike the hardened ordinary and two-token Standard-4H
wrappers, the four-token Standard-4H wrapper could consume its one-use marker
before running the concrete composition preflight. The child would detect that
same deterministic local dependency failure only after consumption, while
retry/rerun/resume/restart/successor are all forbidden.

The repair adds the same zero-I/O pre-launch guard before pre-marker staging and
a focused regression proving a forced `ConcreteCompositionError` sees no marker,
launches no child and returns an `authorization blocked before consumption`
error.

TDD was demonstrated in an isolated CI checkout: the new test first failed
because `FourTokenStandardFourHourOneShotWrapperError` was not raised, then
passed after the repair. The focused wrapper/operational-command/composition set
then passed with **44 passed, 7 subtests passed**, followed by compile and
whitespace checks. Treat completion claims as contingent on fresh verification
of the clean final branch HEAD after temporary CI scaffolding is removed.

## Proven blocker

No additional deterministic code blocker is currently proven in the audited
pre-consumption wrapper boundary after this repair.

Two operational dependencies remain intentionally outside this deterministic
proof:

- provider/RPC reachability is learned through the governed runtime, not by an
  unowned pre-authorization network probe;
- the one-shot campaign has no generic resume/restart takeover path. A process or
  host interruption is fail-closed and consumes that authorization, so successful
  real operation requires the supervised child/host to remain viable through the
  bounded campaign lifetime.

These are not authorization to add retries, endpoint rotation, ungoverned source
calls or restart semantics.

No live provider/RPC execution, Scheduler operation, authoritative database
mutation, wallet/signing or trading operation was performed in this lane.

Default branch `master` remains historically divergent from this development
lineage and is not a safe blind merge/rebase target.

## Exact next permitted action

Freshly verify and review the clean branch HEAD containing this repair. If that
is green, the next narrow read/test-only readiness boundary is host/process
continuity for the full bounded Standard-4H wall-clock lifetime and governed
provider/RPC failure handling. Do not run Printer operationally or mutate the
authoritative database without a new explicit authorization boundary.
