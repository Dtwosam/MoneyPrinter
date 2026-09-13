# Printer V1 Handoff

## Current capability
Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`. Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor remains the sole source-request owner and Central Scheduler the sole scheduler owner. Strict evidence/provenance/freshness gates remain fail-closed.

## Latest meaningful result
Standard-4H campaign `20260913T114345Z-6c9919a4d178-campaign` failed in `CAMPAIGN_PRE_LIFECYCLE` with `IntegrityError:FOREIGN KEY constraint failed` after 12 source calls, 0 scheduler runtime calls, and 6 DB writes. Cleanup completed and the lease was released. Authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260913T113221Z_13446eb3` was consumed and is permanently non-reusable.

## Proven blocker and repair
Generic/current-market discovery may lawfully produce `MARKET_PRESENT_POOL` candidates whose current pool program is PumpSwap while origin remains unknown. `_legacy_pump_reserve_projection_allowed()` previously treated the PumpSwap program alone as sufficient for the legacy `printer_eligible_token_reserve`, whose `mint_identity` FK requires a `printer_pumpswap_graduated_candidate_registry` parent. That false Pump-graduation projection caused the first pre-lifecycle FK failure.

The projector now honors explicit admission authority: any explicit authority other than `DIRECT_PUMP_PUMPSWAP` is excluded from the Pump-registry-bound legacy reserve. Authority-absent legacy carriers preserve historical fail-closed compatibility, and the PumpSwap program check remains unchanged. No FK, provenance, source, scheduler, or admission gate was weakened.

The second FK projection was proven in `run_dexscreener_batch_market_resolution()`: both its exact-pool-present and exact-pool-no-match paths attempted to persist `printer_graduated_market_floor_state`, a child of the immutable graduated registry, based on current PumpSwap program identity alone. The market-floor projection now requires an exact immutable graduation parent matching both mint and pool. Generic current-market truth remains in exact-market state and reserve-layer persistence; no parent is fabricated and the FK remains enforced. Focused disposable-state regression coverage proves parentless present/no-match cases and exact graduated-parent preservation.

## Verification
TDD RED was proven for the parentless present-pool and no-match paths: both failed at `record_market_floor_state()` with `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. The focused disposable-state regression module passes after repair, as does `py_compile`; run the repair-family shared-boundary suite before any promotion.

## Exact next permitted action
Development-only verification may continue on disposable state. Do not rerun or reuse any consumed/stale authorization. A later fresh read-only preflight remains separate from this repair and requires then-current authority, exact GitHub HEAD/DB binding, migration/integrity/FK/zero-active-work proof, and new explicit operator approval before any future operational action.
