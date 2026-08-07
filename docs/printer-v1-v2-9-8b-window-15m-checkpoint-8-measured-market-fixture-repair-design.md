# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Measured Market Fixture Repair Design

Date: 2026-08-07

Audit HEAD: `d42878de08efd22f45a323045182984de2efed33`

## Design verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_MEASURED_MARKET_FIXTURE_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Exact repair

Change only the C8 controlling-proof fixture and focused C8 compatibility tests.

1. Add a proof-only helper that creates one `TransportOperationIdentity` and serializes it with `measured_payload_fields()` for a market-source fixture call.
2. Preserve the existing DexScreener and GeckoTerminal response bodies.
3. At the four canonical measured-market fixture routes, attach exactly one identity matching the consumer's stage/source/request semantics:
   - DexScreener fresh profiles: `DEXSCREENER_DISCOVERY` / `dexscreener_fresh_profiles`.
   - DexScreener mint batch: `MINT_MARKET_BATCH` / `candidate_market_batch`.
   - GeckoTerminal fresh nomination: `FRESH_POOL_NOMINATION` / `geckoterminal_new_pool_discovery`.
   - GeckoTerminal reconciliation: `MINT_MARKET_BATCH` / `candidate_market_batch`.
4. Do not add measured identities to unrelated fixture routes unless their canonical consumer requires this payload contract.
5. Do not change `record_payload_transports`, six-unit sealing, Source Governor, Scheduler, discovery selection, or production provider transports.

## Fail-closed contract

Each measured fixture payload must satisfy:
- `transport_operations_used == 1`;
- exactly one serialized `transport_operation_identity`;
- identity stage/source/request kind non-empty and route-correct;
- response bytes and normalized rows match the fixture response;
- canonical adapter normalization preserves the identity;
- `identities_from_payload()` returns exactly one identity without error.

No accounting fallback or inferred identity is allowed in production code.

## Minimum sufficient offline proof

1. `py_compile` changed proof/test modules.
2. New focused regression exercises all four market fixture seams through their real DexScreener/GeckoTerminal adapters and proves exactly one measured identity survives normalization for each.
3. Existing real-consumer compatibility file passes.
4. Full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` passes.
5. Process-local network tripwire remains at zero for the regression.
6. `git diff --check` passes.
7. Narrow diff contains only the C8 proof harness and focused test file.

## Money-usefulness contribution

This allows trustworthy permanent-market evidence to participate in the same six-unit accounting the real memory campaign depends on, instead of synthetic proof metadata blocking before two-token observation.

## What this lane improves

C8 market fixture fidelity for measured source operations.

## What remains locked

No controlling re-proof is authorized by this design. `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked.

## Completion rule

After offline GREEN verification, write a repair closeout and a separate readiness decision. Stop before any controlling proof and require a new explicit operator authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- A future proof may reveal a different later seam; do not pre-approve unrelated implementation.
- Do not count fixture builder calls as source transports; only the canonical source-call payload gets one identity.
- Do not broaden this into production source refactoring.
