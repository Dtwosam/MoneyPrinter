# Printer V1 V2-9.7D.4B Conditional Support-Only 5m Capture Closeout

## Status

`V2_9_7D_4B_CONDITIONAL_SUPPORT_ONLY_5M_CAPTURE_PASS`

V2-9.7D.4B adds a pure, fail-closed eligibility policy and immutable
`WINDOW_5M_MICRO_EVENT` support-capture representation. It consumes existing
governed observations only and performs no source request, scheduling,
persistence, main-window mutation, or hidden retry.

## Money-Usefulness Contribution

Conditional support capture preserves short-lived pump, dump, wick, exit,
liquidity, breakdown, and reclaim evidence that can explain why a larger main
window behaved as it did. Restricting capture to exact governed evidence avoids
spending scarce source and scheduler budgets on ordinary movement and prevents
hindsight from turning a completed chart into a fabricated early signal.

## What 4B Improves

- Fixes the six approved trigger families as categorical policy vocabulary.
- Separates valid no-capture from blocked support capture.
- Exact-links campaign, run, cycle, token slot, token, mint, pair, root 15m
  lifecycle, active containing main window, triggering snapshots, governed
  provenance, scheduler work, trigger time, and evidence cutoff.
- Allows support capture inside active 15m, 1h, and 4h main windows while
  preserving the root 15m lifecycle identity.
- Fails closed for stale, mismatched, untraceable, future-leaking, ineligible,
  terminal, cancelled, unsupported, or budget-exhausted requests.
- Makes support failure token-local and leaves every containing main window
  unchanged.

## What Remains Locked

4B does not fetch sources, collect snapshots, execute scheduler work,
orchestrate campaigns, migrate or mutate a database, promote memory, create
trajectory/checkpoint/manipulation/opportunity objects, rotate tokens, or add
an operational command. 5m support cannot become main memory, replace 15m,
trigger 1h/4h continuation, count toward main clean-memory thresholds, choose a
lifecycle disposition, activate retrieval, create paper decisions, authorize
any action, create positions/trades/audits/PnL, or enable live execution.

## Proof Completed

Focused proof covers all six trigger families; ordinary no-capture; unsupported
labels; stale, mismatched, untraceable, and future-leaking evidence; exact root
and containing-window linkage; active 15m/1h/4h containment; token-local failure
isolation; every budget scope; deterministic replay; immutable permanent
non-authority; unchanged 4A continuation verdicts; and zero locked-capability
row creation. Directly affected E2V/window, 3A identity, and 4A continuation
regressions are included in bounded verification.

Verification passed with syntax/import checks; 13 focused 4B tests plus 27
subtests; 101 authoritative E2V 5m/window tests; 23 V2-9.7D.3A tests plus 23
subtests; and 13 V2-9.7D.4A tests plus 18 subtests. Pytest cache was disabled,
hard timeouts were applied, and temporary-directory creation and cleanup were
proven in the sandbox-approved visualization root before pytest ran.

## Functionality Risks / Setbacks / Efficiency Blockers

- The policy trusts existing categorical trigger proof; it does not infer
  manipulation intent or invent quantitative thresholds.
- Every capture requires at least two exact, ordered governed snapshots, so
  sparse evidence safely blocks support rather than manufacturing a transition.
- Production budget values and scheduler execution remain future orchestrator
  inputs; exhaustion blocks with no retry.
- The immutable representation is not persistence authorization. A later lane
  must preserve these identities and non-authority flags if storage is approved.
- Missing support evidence can reduce explanatory detail but cannot silently
  dirty or change an otherwise valid main window.

## Next Recommended Phase

Stop after the scoped PASS commit. Do not begin trajectory, checkpoint,
manipulation, opportunity, or any later V2-9.7D work without explicit operator
approval.
