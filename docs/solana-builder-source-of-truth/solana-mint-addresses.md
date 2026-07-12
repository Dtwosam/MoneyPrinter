# Solana Mint Addresses

Status: SB-2 CORE MODULE, DOCUMENTATION ONLY

## 1. Module Identity

- Module: Solana Mint Addresses
- Scope: Infrastructure mint addresses and their permitted Printer roles.
- Source-stack lane: SB-2.

## 2. Five-Dimension Status

- `upstream_lifecycle`: CURRENT_BUT_EXTERNAL_AUTHORITIES_MAY_CHANGE_REFERENCE_PAGES.
- `printer_readiness`: PARTIAL_IMPLEMENTED_NOT_ADOPTED.
- `printer_role`: INFRASTRUCTURE_MINT_REFERENCE_AND_PAPER_REALISM_CONTEXT.
- `access_policy`: READ_ONLY_REFERENCE_ONLY.
- `v1_permission`: ALLOWED_AS_REFERENCE, NOT_ALLOWED_AS_TRADE_UNLOCK.

## 3. Authority Boundary

External issuers and Solana/SPL references define official infrastructure mint addresses. Printer implementation defines where those addresses are used. A mismatch is an implementation gap requiring later review.

## 4. Upstream Sources

- Solana/SPL token documentation for native SOL wrapping references.
- Circle official USDC supported-chain documentation for Solana USDC.
- Tether official supported-network or transparency documentation for Solana USDt/USDT.
- Current Printer constants in source code.

Exact upstream URLs and retrieval dates should be pinned in a later verification lane for any address used as hard policy.

## 5. Current Printer References

Current Printer source references include:

- Wrapped SOL: `So11111111111111111111111111111111111111112`
- Solana USDC: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej`
- Solana USDT: `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`

Observed implementation files:

- `src/printer_v1/sources/geckoterminal.py`
- `src/printer_v1/sources/jupiter_quote.py`

## 6. Wrapped SOL

Wrapped SOL is infrastructure context for quote routing, pair identification, and liquidity interpretation. It is not a memecoin target and does not by itself create a paper decision.

## 7. USDC

USDC is infrastructure context for quote routing and paper-realism reference. It is not a Printer V1 target asset.

## 8. USDT

USDT is infrastructure context for quote routing and pair/reference interpretation. It is not a Printer V1 target asset.

## 9. Target-Asset Boundary

Printer V1 is Solana memecoin-only. Infrastructure mint addresses can support route and quote context, but they cannot be selected as target memecoin candidates unless a future lane explicitly defines a safe reference-only exception.

## 10. Quote Context

Infrastructure mints may appear in Jupiter quote or DEX pair routes. Quote evidence remains paper-realism-only and cannot enable live execution.

## 11. Discovery Context

Discovery may encounter infrastructure tokens in pairs. Selection logic must prevent infrastructure addresses from masquerading as target memecoin candidates.

## 12. Safety Context

Infrastructure mints may be used to interpret liquidity pairs, but their official status does not make an associated memecoin safe.

## 13. Source Governor Boundary

Any source data using these mints must still flow through the Source Governor. Hardcoded reference constants do not authorize live source bypass.

## 14. Central Scheduler Boundary

Reference mint addresses do not create scheduler jobs or source loops by themselves.

## 15. Known Gaps

- Official address pinning should be tightened with exact upstream pages and retrieval dates.
- Non-USDC/USDT stable or wrapped assets are out of scope for this module.
- Token-list allow/deny behavior remains implementation-specific and not changed by SB-2.

## 16. Forbidden Uses

This module does not allow:

- Trading infrastructure tokens.
- BUY/SELL/HOLD decisions.
- Paper positions.
- Wallet/signing/execution.
- Paid source dependency.
- Ranking or scoring.

## 17. Evidence Labels

Mint address recognition may contribute categorical context such as route asset or quote-side asset. It must not become a score or standalone trade signal.

## 18. Tests and Verification Expectations

Verification should prove:

- Known infrastructure mints remain reference-only.
- Memecoin target identity is not replaced by pair-side infrastructure mints.
- Quote logic remains paper-only.
- Jupiter quote evidence remains non-executing.

## 19. Adoption Requirements

This module is not adopted by SB-2. Later verification should pin official references and compare them to Printer constants.

## 20. SB-2 Conclusion

Infrastructure mint addresses are useful for safe Solana context, but they do not expand target assets, source permissions, or paper-trading unlocks.
