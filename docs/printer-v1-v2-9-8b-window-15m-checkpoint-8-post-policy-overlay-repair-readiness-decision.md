# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-Policy-Overlay Repair Readiness Decision

Date: 2026-08-07

Repair closeout HEAD: `0f4923283fba4aeff749db2690f3080f644ee9c3`

## Decision

The proof-bridge operational-policy overlay repair is complete and sufficiently verified offline to propose one new ordinary `WINDOW_15M` Checkpoint 8 controlling re-proof.

The authorization consumed by Actions run `31192953880` is exhausted and cannot authorize another attempt.

## Required next gate

Before any new controlling proof starts, the operator must explicitly authorize exactly one new Checkpoint 8 re-proof attempt after the proof-bridge operational-policy overlay repair.

Generic continue, rerun, or handle-everything language is insufficient.

## Mandatory next-runner behavior

A later authorized one-shot runner must:

1. freeze the exact authorized post-repair Git SHA;
2. use fresh disposable DB, artifact root, proof identity, and sentinel namespace;
3. run the controlling harness exactly once;
4. preserve/upload frozen evidence regardless of result;
5. parse `checkpoint8-controlling-proof-summary.json` when produced;
6. invoke independent success inspection only when `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS`;
7. stop on any honest block or failure without retry, rerun, resume, restart, or successor.

## Current verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_NEXT_REPROOF_PROPOSAL_READY_AWAITING_NEW_EXPLICIT_OPERATOR_AUTHORIZATION`

## Money-usefulness contribution

The next proof can now test whether Printer's canonical permanent graduated-token supply path reaches the complete two-token ordinary observation and clean-memory closeout while retaining deterministic zero-provider proof inputs.

## What remains locked

Checkpoint 8 is not complete yet. No `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL are unlocked.

## Proof/test required before completion

Exactly one newly authorized ordinary `WINDOW_15M` controlling re-proof must produce `CAMPAIGN_PASS`, followed by a passing independent read-only inspection over the frozen evidence.

## Functionality Risks / Setbacks / Efficiency Blockers

- Another later seam may still appear because the proof has not yet reached a full clean closeout.
- The no-rerun law remains essential: a failed or blocked one-shot attempt cannot be searched repeatedly for a passing result.
- No additional implementation is justified before a new explicit authorization; current offline repair evidence is green.

## Stop condition

Readiness review is complete. Stop before runtime and await a new explicit operator authorization.