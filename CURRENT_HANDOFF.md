# Printer V1 Handoff

## Current capability
Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`. Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor remains the sole source-request owner and Central Scheduler the sole scheduler owner. Strict evidence/provenance/freshness gates remain fail-closed.

## Latest meaningful result
Standard-4H campaign `20260913T151547Z-599b54616a7e-campaign` failed in `CAMPAIGN_PRE_LIFECYCLE` with `MARKET_CANDIDATE_NOMINATION_SOURCE_UNSUPPORTED` for mint `2sQ7wuUtRWNir3CEu9HWfLDSut4AszDrcZXLobzJpump` after 13 source calls, 0 scheduler runtime calls, and 6 DB writes. Cleanup completed and the lease was released. Authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260913T151024Z_a54bd06d` was consumed and is permanently non-reusable.

## Proven blocker and repair
Generic/current-market discovery may lawfully produce `MARKET_PRESENT_POOL` candidates whose current pool program is PumpSwap while origin remains unknown. `_legacy_pump_reserve_projection_allowed()` previously treated the PumpSwap program alone as sufficient for the legacy `printer_eligible_token_reserve`, whose `mint_identity` FK requires a `printer_pumpswap_graduated_candidate_registry` parent. That false Pump-graduation projection caused the first pre-lifecycle FK failure.

The projector now honors explicit admission authority: any explicit authority other than `DIRECT_PUMP_PUMPSWAP` is excluded from the Pump-registry-bound legacy reserve. Authority-absent legacy carriers preserve historical fail-closed compatibility, and the PumpSwap program check remains unchanged. No FK, provenance, source, scheduler, or admission gate was weakened.

The second FK projection was proven in `run_dexscreener_batch_market_resolution()`: both its exact-pool-present and exact-pool-no-match paths attempted to persist `printer_graduated_market_floor_state`, a child of the immutable graduated registry, based on current PumpSwap program identity alone. The market-floor projection now requires an exact immutable graduation parent matching both mint and pool. Generic current-market truth remains in exact-market state and reserve-layer persistence; no parent is fabricated and the FK remains enforced. Focused disposable-state regression coverage proves parentless present/no-match cases and exact graduated-parent preservation.

The latest failure was a nomination-provenance handoff defect, not a validator defect. The target's governed exact-market observation was DexScreener request `6194` / response `5718` at pool `4vqphqf4v7MSou7o57pTfzFcM7pJxtkmK3XRKBJP1jBK`; durable reserve and exact-market provenance retain `source: dexscreener`. `run_dexscreener_batch_market_resolution()` carried legacy inventory `provenance` but omitted `nomination_source` when it materialized the market-present candidate, causing the downstream validator to see unsupported `PERSISTED_GRADUATED` instead of the canonical governed source. The repair preserves `provenance["source"]` as `nomination_source`; it adds no allowlist entry and retains rejection of missing or unsupported sources.

## Verification
TDD RED was proven for the parentless present-pool and no-match paths: both failed at `record_market_floor_state()` with `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. A source-handoff RED also reproduced `MARKET_CANDIDATE_NOMINATION_SOURCE_UNSUPPORTED` from the actual market-resolution candidate before the source-preservation repair. Focused disposable-state regression coverage passes after repair, including lawful DexScreener admission and unsupported-source rejection; run the repair-family shared-boundary suite before any promotion.

## Exact next permitted action
Development-only verification and a fresh read-only preflight may continue. Do not rerun or reuse any consumed/stale authorization. Any later operational action remains separate and requires then-current authority, exact GitHub HEAD/DB binding, migration/integrity/FK/zero-active-work proof, and new explicit operator approval.
