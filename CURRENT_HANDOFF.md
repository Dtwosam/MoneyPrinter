# Printer V1 Handoff

## Current capability
Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`. Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor remains the sole source-request owner and Central Scheduler the sole scheduler owner. Strict evidence/provenance/freshness gates remain fail-closed.

## Latest meaningful result
Standard-4H campaign `20260912T213005Z-c3c0bea44b6f-campaign` failed in `CAMPAIGN_PRE_LIFECYCLE` with `IntegrityError:FOREIGN KEY constraint failed` after 12 source calls, 0 scheduler runtime calls, and 6 DB writes. Cleanup completed and the lease was released. Authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260912T211937Z_f0d06977` was consumed and is permanently non-reusable.

## Proven blocker and repair
Generic/current-market discovery may lawfully produce `MARKET_PRESENT_POOL` candidates whose current pool program is PumpSwap while origin remains unknown. `_legacy_pump_reserve_projection_allowed()` previously treated the PumpSwap program alone as sufficient for the legacy `printer_eligible_token_reserve`, whose `mint_identity` FK requires a `printer_pumpswap_graduated_candidate_registry` parent. That false Pump-graduation projection caused the pre-lifecycle FK failure.

The projector now honors explicit admission authority: any explicit authority other than `DIRECT_PUMP_PUMPSWAP` is excluded from the Pump-registry-bound legacy reserve. Authority-absent legacy carriers preserve historical fail-closed compatibility, and the PumpSwap program check remains unchanged. No FK, provenance, source, scheduler, or admission gate was weakened.

## Verification
TDD RED was proven on commit `63a099eab6238ecc9e783161e7f7d394b437bc88`: the new market-present/PumpSwap regression was the sole failure (`1 failed, 380 passed, 2 deselected, 32 subtests passed`). Focused disposable-state regression tests and `py_compile` passed on the repaired staging tree before promotion; the authoritative branch push workflow must also pass before any future operational preflight.

## Exact next permitted action
Do not rerun or reuse any consumed/stale authorization. After the repaired authoritative HEAD is green, any future Standard-4H operational attempt still requires a brand-new one-shot authorization bound to the then-current GitHub HEAD and authoritative DB identity, fresh migration/integrity/FK/zero-active-work proof, and new explicit operator approval. Development-only verification may continue on disposable state.
