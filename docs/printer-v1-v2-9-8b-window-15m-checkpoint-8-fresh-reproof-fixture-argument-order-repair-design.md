# Printer V1 V2-9.8B Checkpoint 8 Fresh Re-proof Fixture Argument-Order Repair Design

## Design verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_FRESH_REPROOF_FIXTURE_ARGUMENT_ORDER_REPAIR_APPROVED_OFFLINE_ONLY`

## Defect being repaired

The canonical production seam is:

`verifier_transport_factory(mint, signature)`

The proof fixture currently selects `args[1]` as the mint, while the compatibility helper calls the fixture in the reversed `(signature, mint)` order. The two proof-only components agree with each other but disagree with production.

## Exact repair

1. In `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`, the `graduated_supply.verifier_transport_factory` route must interpret two positional arguments as:
   - `args[0]` = mint;
   - `args[1]` = migration signature.
2. Candidate lookup must use the mint from `args[0]`.
3. When a signature is supplied, it must equal that candidate's fixture `migration_signature`; mismatch fails closed with a proof-only error rather than silently returning a transport for a different identity.
4. Existing single-context adapter handling remains unchanged.
5. In `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`, the shared PumpSwap verifier probe must call `verifier(first_mint, first_signature)`.
6. Production discovery code is not changed.

## Regression contract

Add one focused proof-only regression that:

- materializes the Checkpoint 8 fixture composition;
- resolves a real fixture candidate mint/signature pair;
- calls the verifier factory in canonical `(mint, signature)` order and proves the returned PumpSwap transport is accepted by the real adapter boundary;
- calls the same fixture in reversed `(signature, mint)` order and proves it fails closed;
- retains the existing 20-route real-consumer compatibility tests.

## Verification

Minimum sufficient verification:

- new argument-order regression;
- existing `test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py` tests;
- directly affected blocked-repair tests;
- harness and compatibility-helper `py_compile`;
- focused Checkpoint 8 wildcard suite only at repair closeout;
- static guard confirming no public `run_operational_campaign()` is called by verification and no network/provider fallback is used.

No live proof is part of this repair.

## Money-usefulness contribution

This repair makes the deterministic proof fixtures conform to the real production PumpSwap verification seam, reducing the chance that an offline GREEN gate masks a runtime contract mismatch before clean-memory automation is accepted.

## What remains locked

No second Checkpoint 8 proof, no provider/network execution, no public campaign runtime, no memory generation, no `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallet, signing, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Correcting only the fixture without correcting the compatibility helper would make the existing compatibility gate fail but would not close the blind spot cleanly.
- Correcting both without the canonical-order regression could allow a future coupled reversal to pass again.
- Signature validation must remain proof-only and must not invent a production behavior change.
- Any later re-proof remains separately operator-authorized and one-shot.

## Stop condition

Design complete. Implement only this proof-only argument-order repair and its focused regression.
