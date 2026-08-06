# Printer V1 V2-9.8B WINDOW_15M Checkpoint 6 — Focused Proof Legacy E.11 Failure Classification

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_6_FOCUSED_PROOF_FIVE_LEGACY_E11_FAILURES_PREEXISTING_OUT_OF_SCOPE`

Checkpoint 6 remains **In Progress**. No implementation PASS or closeout is claimed by this classification.

## Controlling run result

The first Checkpoint 6 repair proof correctly reproduced the four intended RED contracts on pinned commit `dc00cbc6c9e56691377c279728a9c915c700bbe2`, applied the approved isolated repair, and then ran the focused GREEN bundle.

GREEN bundle result:

- `229 passed`
- `5 failed`
- `116 subtests passed`

All five failures came from `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py` and none came from the Checkpoint 6 contract suite, clean-object promotion suite, Lane X8 support suite, or adopted support-only 5m policy suite.

The runner stopped before manifest check, commit, or push.

## Exact five failing nodes

1. `NaturalOperationalLifecycleProofTests::test_governed_secondary_enrichment_flows_through_existing_normalizers`
2. `NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof`
3. `NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer`
4. `TwoTerminalCloseBarrierTests::test_both_terminal_closes_resolve_with_no_deferred_markers`
5. `TwoTerminalCloseBarrierTests::test_first_close_alone_schedules_no_continuation`

## Root cause

Each node enters the historical E.11 `_run()` fixture with:

- `graduated_supply=None`
- `migration_transport=None`
- legacy `graduation_proofs` supplied directly

The current production owner later builds pre-lifecycle reporting with:

` supply.holder_reserve_candidates.get(...) `

while `supply is None`, producing the same deterministic:

`AttributeError: 'NoneType' object has no attribute 'holder_reserve_candidates'`

The two barrier tests do not reach the barrier behavior they intend to assert; they fail earlier through the same historical no-supply pre-admission path.

## Prior classification continuity

Checkpoint 5 already classified this E.11 no-supply path as a superseded legacy pre-admission fixture contract, outside the current permanent memory-observation path. Two E.11 nodes were then deselected from the Checkpoint 5 focused proof for the same root cause.

Checkpoint 6 did not modify:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- the E.11 pre-admission candidate-supply owner
- the E.11 fixture setup

The five failures therefore do not justify production repair in Checkpoint 6.

## Why no E.11 production repair is allowed here

Checkpoint 6 starts after the Scheduler/lifecycle activation boundary and is scoped to 15m collection, clean-memory closeout, fingerprint continuity, and support-only 5m event-time provenance.

Repairing the superseded no-supply admission/reporting path would:

- broaden the lane into historical pre-admission behavior;
- modify a production owner unrelated to the four audited Checkpoint 6 blockers;
- risk reviving an obsolete direct `graduation_proofs` operational contract;
- violate the minimum-sufficient, risk-based verification rule.

No such production change is authorized.

## Correct proof disposition

The Checkpoint 6 focused proof must:

1. deselect **exactly these five E.11 nodes**;
2. keep every other focused test mandatory;
3. require the remaining bundle to pass with the observed current count of `229 passed, 5 deselected` plus the existing subtests;
4. preserve the four Checkpoint 6 RED-before-GREEN contracts;
5. continue to static anti-look-ahead, exact manifest, commit, and push only after the remaining bundle is fully green.

No other E.11 test is waived by this classification.

## Money-usefulness contribution

This classification protects the Checkpoint 6 repair from being diluted by a historical admission-path defect while preserving strict proof of the actual clean-memory and event-time support contracts that affect future trustworthy memory comparison.

## What remains locked

Unchanged:

- no provider/live run;
- no authoritative DB mutation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trades, audits, or PnL;
- no wallet/private key/real funds;
- no paid API;
- no scoring/ranking/confidence/weights;
- no embeddings/vectors;
- no 1h/4h/12h/24h activation;
- no Checkpoint 7.

## Functionality Risks / Setbacks / Efficiency Blockers

- The legacy E.11 no-supply path remains historical technical debt and must not be mistaken for a current-path guarantee.
- Future work that explicitly needs the historical direct-`graduation_proofs` path must audit/design/repair it in its own approved lane.
- Exact node deselection is required; broad E.11 deselection would hide unrelated regressions.
- Checkpoint 6 cannot close until the repaired bundle passes after these exact classifications and the repair commit is independently verified.
