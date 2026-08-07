# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Source-Visibility Fixture Accounting Repair Design

Date: 2026-08-07

Baseline audit commit: `739e1fc2bd53ae383e882f8a3a23dbc9cebc8bec`

## Decision

Repair the Checkpoint 8 proof fixture only. Do not modify production discovery, Source Governor, Central Scheduler, selection, lifecycle, memory, or paper-trading code.

## Repair 1 — production-shaped PumpSwap measured identities

Change `_checkpoint8_pumpswap_confirmation()` in the C8 controlling harness so one synthetic successful signature-resolution response carries the same measured-operation shape as the production graduation verifier:

- one `getTransaction` transport identity;
- one `getMultipleAccounts` transport identity for the 25-key synthetic migration transaction;
- stage `PUMPSWAP_EXACT_VERIFICATION`;
- source `solana_rpc`, endpoint owner `solana`;
- governed request kind `pumpswap_signature_pool_resolution`;
- exact candidate signature/mint target identities;
- `transport_operations_used` derived from the identity list;
- `expected_transport_operations` derived from the canonical PumpSwap verification-count helper.

Use the existing `build_transport_identity`, `measured_payload_fields`, and `pumpswap_verification_transport_count` owners. Do not hand-roll a parallel identity schema.

This makes the C8 source-clean PumpSwap response acceptable to the same measured-transport accounting gate that production uses, so the direct-migration owner can persist confirmed candidates only after identity totals reconcile.

## Repair 2 — valid deterministic migration time

Replace the synthetic future epoch base (`1_800_000_000`) with one fixed deterministic past epoch (`1_786_000_000`, 2026-08-06 UTC). Preserve the existing per-candidate one-minute spacing and migration `+600s` relationship.

This is migration/graduation evidence only. It must not become token creation time or alter any token-age tier.

The fixed value preserves deterministic fixtures while satisfying the production future-time invariant for the current readiness era.

## Regression coverage

Extend the C8 real-consumer compatibility test with one direct-migration accounting regression on a fresh disposable migrated DB:

1. materialize the exact C8 composition;
2. invoke the canonical `run_direct_migration_discovery()` with the C8 migration transport and PumpSwap verifier factory under the network tripwire;
3. require zero network attempts;
4. require `status == COMPLETE`;
5. require two confirmed candidates;
6. require operation accounting reconciled;
7. require seven measured source transport operations: three direct Pump live-tail operations plus two PumpSwap transport operations per candidate;
8. require exactly two rows in the graduated-candidate registry;
9. require the fixture migration times not to exceed current UTC + the production 300-second tolerance.

Keep the existing argument-order regression and 20-route compatibility checks.

## Runner rule for any later authorized re-proof

Do not persist a new general runtime feature for this. When a later one-shot runner is created after fresh operator authorization:

1. run the harness once;
2. freeze/upload evidence regardless of outcome;
3. parse the frozen summary;
4. invoke the independent success inspector only when both `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS`;
5. otherwise fail the runner with the campaign's honest terminal and do not invoke the success inspector.

## Minimum sufficient verification

- `py_compile` for the C8 harness.
- C8 real-consumer compatibility test file.
- Full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` suite because this is a Checkpoint 8 proof-fixture closeout repair.
- offline static/network guard already owned by the focused C8 tests.
- `git diff --check`.

No controlling campaign proof is part of repair verification.

## Money-usefulness contribution

This repair ensures source evidence that later feeds clean-memory generation is measured and persisted under the same accounting law as production. It removes a false shortage that would otherwise prevent Printer from observing valid opportunities at all.

## What this still does not unlock

No new Checkpoint 8 proof entitlement. No `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- If the synthetic identity metadata diverges from the production verifier's canonical helpers, the proof could still be non-representative; therefore the repair must reuse those helpers directly.
- A green direct-migration regression proves candidate persistence, not complete Checkpoint 8 closeout; a fresh controlling proof remains separately authorization-gated.
- The independent inspector is a success closeout inspector and must not be used to reinterpret an honest pre-lifecycle block.

## Design verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_SOURCE_VISIBILITY_FIXTURE_ACCOUNTING_REPAIR_DESIGN_COMPLETE`
