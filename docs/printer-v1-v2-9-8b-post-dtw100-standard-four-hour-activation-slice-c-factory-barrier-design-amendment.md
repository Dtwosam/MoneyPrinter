# Printer V1 Post-DTW100 Standard Four-Hour Activation — Slice C Factory Barrier Design Amendment

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_ACTIVATION_SLICE_C_FACTORY_BARRIER_DESIGN_PASS`

This amendment narrows the already-approved activation design to the exact factory/runtime owner needed for implementation. It changes no runtime capability by itself.

## Exact owner and barrier

Add one campaign-level standard-four-hour barrier owner in `operational_standard_4h.py`. The factory calls it only from the dedicated standard production mode, after a successful `CONTINUATION_CLOSE` has been durably reconciled to its owned campaign `WINDOW_1H` and the step/Scheduler transaction is committed.

The owner:

1. requires exact campaign/configuration/run/cycle/factory-run identity and exactly two owned token slots;
2. requires the exact authoritative factory-run binding;
3. reads both owned `WINDOW_1H` predecessors and each exact `CONTINUATION_CLOSE`;
4. returns `AWAITING_PEER_FIRST_HOUR_CLOSE` with zero 4h mutation while either close is still pending/running;
5. fails closed if either first-hour close is failed, cancelled, ambiguous, mismatched, unbound, or cannot establish exact successful close truth;
6. for two successful closes, derives each token's hard-gate facts from the existing authoritative promotion/safety adapters, physical 1h memory row, exact continuity, campaign identity, and existing bounded resource contract;
7. evaluates the canonical token-local `1h -> 4h` policy with no learning-need, score, rank, confidence, or weighted authority;
8. constructs the exact two standard composer candidates and explicit `0/1/2` eligible slot set;
9. calls `plan_standard_campaign_4h_handoff(...)` exactly once under `FourHourExecutionAuthority.STANDARD_CAMPAIGN`;
10. returns the durable eligibility manifests, subset plan, and policy-derived subset budget for reporting.

A successful but hard-gate-ineligible 1h close remains in the two-slot manifest and gets no 4h window/work. A failed/ambiguous 1h close is not rewritten into an ineligible verdict merely to let its peer continue.

## Factory authority

Add a dedicated categorical factory input/config marker for standard production 4h authority. It is mutually exclusive with `four_hour_proof_mode` and with the historical compressed/natural proof disposition modes.

Standard production requires:

- operational persistent mode;
- exact campaign/run/cycle/configuration identity;
- token capacity 2;
- `selective_1h_continuation` / genuine first-hour path;
- `continuous_four_hour=True`;
- `four_hour_proof_mode=False`;
- current 4h cadence enabled;
- 12h/24h cadence disabled.

The existing immediate per-token `plan_current_run_4h(... explicit_proof_mode=...)` branch remains historical proof-only and is bypassed in standard production. Standard production composes 4h only through the two-slot campaign barrier.

## Runtime handoff

Only after the barrier implementation is GREEN may `standard-four-hour-run` stop returning its temporary `IMPLEMENTATION_REQUIRED` blocker. The public command must pass the dedicated standard factory authority and the existing exact campaign ownership context. Direct invocation without the already-proven standard one-shot binding remains blocked.

## Budget/reporting

Standard mode must use the existing policy-derived `standard_campaign_lifecycle_budget(...)` subset budget after the durable eligibility set exists. The configured outer maxima remain 230 governed lifecycle requests / 210 lifecycle Scheduler rows; actual subset ceilings are lower where only one or zero tokens continue. Already-consumed first-hour prefix cost for both tokens remains included.

## Proof boundary

Minimum sufficient Slice C proof:

- first successful 1h close creates no 4h work while peer is not terminal;
- second successful close releases the barrier;
- both eligible -> both successors/work;
- one hard-gate blocked -> only peer continues;
- zero eligible -> valid zero-work manifest/no-op;
- failed/ambiguous first-hour peer -> fail closed, no manufactured manifest;
- exact replay is idempotent and subset drift fails closed;
- standard path requires explicit STANDARD_CAMPAIGN authority and never routes through `four_hour_proof_mode`;
- historical proof path remains intact;
- standard budget/reporting uses the exact subset contract;
- 12h/24h remain zero/disabled;
- no retrieval or financial table delta.

No source fetch, runtime invocation, real authorization, authoritative-DB mutation, or live proof is permitted in Slice C implementation/proof.

## Money-usefulness contribution

The barrier prevents a fast first token from starting a long 4h lifecycle before Printer knows the exact two-token first-hour state. That keeps long-window budget use, corpus composition, and later clean-memory comparisons attributable and prevents one token's timing from silently deciding campaign resource allocation.

## What remains locked

Real standard-four-hour execution remains unproven until Slice C implementation, independent exact-head proof, activation closeout, and fresh operational rereadiness pass. 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- The second close must observe committed first-hour truth. Calling the barrier before commit risks a separate read-only authority adapter missing the current close; therefore the standard barrier runs after close/Scheduler commit.
- Existing 1h safety/promotion evidence may legitimately make a token ineligible. That is a hard-gate outcome, not an implementation failure.
- A missing successful close on either owned slot blocks composition rather than fabricating a negative verdict.
- Standard subset budget reporting must not reuse the historical one-token cumulative helper, which would understate two-token prefix use.
