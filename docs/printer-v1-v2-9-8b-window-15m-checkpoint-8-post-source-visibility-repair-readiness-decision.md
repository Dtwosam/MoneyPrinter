# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-Source-Visibility Repair Readiness Decision

Date: 2026-08-07

Repair closeout HEAD: `84bef12d17344333dcfb8c56dcc39c0ad495d824`

## Decision

The offline source-visibility fixture accounting repair is complete and sufficiently verified to propose one new ordinary `WINDOW_15M` Checkpoint 8 controlling re-proof.

No proof entitlement is currently active. Both prior explicit authorizations are consumed by their respective one-shot attempts.

## Required next gate

Before any new controlling proof starts, the operator must explicitly authorize exactly one new Checkpoint 8 re-proof attempt after the source-visibility fixture accounting repair.

Generic continue/rerun/handle-everything language is insufficient.

## Mandatory next-runner behavior

A later authorized one-shot runner must:

1. freeze the exact authorized repaired Git SHA;
2. run the controlling harness exactly once;
3. upload/preserve frozen evidence regardless of campaign result;
4. parse `checkpoint8-controlling-proof-summary.json`;
5. require `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS` before invoking the independent success inspector;
6. if the campaign is honestly blocked, stop with that terminal and do not invoke the success inspector;
7. never retry, rerun, resume, restart, or create a successor from the same authorization.

## Current verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_NEXT_REPROOF_PROPOSAL_READY_AWAITING_NEW_EXPLICIT_OPERATOR_AUTHORIZATION`

## Money-usefulness contribution

The readiness proof can now test whether exactly accounted graduated-token evidence reaches the complete ordinary observation and clean-memory path instead of being lost at fixture accounting.

## What remains locked

No new controlling proof, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL until their explicit gates are satisfied.

## Functionality Risks / Setbacks / Efficiency Blockers

- Checkpoint 8 itself is still incomplete; only the blocking fixture seam is repaired.
- A fresh proof may expose a later independent blocker; any such blocker must be audited and repaired through the same audit/design/implementation/proof/closeout discipline.
- The previous `SOURCE_VISIBILITY_SHORTAGE` proof and its authorization remain consumed historical evidence and cannot be recycled.
