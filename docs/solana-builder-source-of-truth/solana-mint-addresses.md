# Solana Mint Addresses

**Status:** SB-2 CORE MODULE, DOCUMENTATION ONLY. SB-2.1 VERIFIED AND CORRECTED.

---

## 1. Purpose

This module documents the three Solana infrastructure mint addresses that
Printer V1 uses for routing context, pair identification, and paper-realism
quote filtering. These addresses are reference constants only — Printer is
Solana memecoin-only and must never select these addresses as target memecoin
candidates.

Scope: exactly three addresses (WSOL, USDC, USDT). No other assets.

---

## 2. Official Upstream Authorities

| Address | Tier | Authority | Official resource | Verified date |
|---|---|---|---|---|
| WSOL (`So111...112`) | A1 | SPL Token program | `https://github.com/solana-program/token` (native_mint.rs or equivalent) | 2026-07-12 |
| USDC (`EPjF...TDt1v`) | A4 | Circle Inc. developer documentation | `https://developers.circle.com/stablecoins/usdc-contract-addresses.md` | 2026-07-12 |
| USDT / USDt (`Es9v...YB`) | A4 | Tether Ltd. official documentation | `https://tether.to/en/supported-protocols` | 2026-07-12 |

**WSOL pinning note:** Wrapped SOL's native mint address is a canonical constant
in the SPL Token program. SB-2.2 pinned repository HEAD
`405c9172df3aeb508712142aae1caf0d31ada671`; the module should verify the exact
file path `interface/src/native_mint.rs` in SB-2.3 before adoption.

**USDC pinning note:** Circle's official contract-address page now lists Solana
mainnet USDC as `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`. Printer's
current implementation still uses `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej`.
SB-2.2 classifies this as an implementation gap requiring a later production
repair/proof lane. No code is changed here.

**USDT/USDt pinning note:** Tether's official supported-protocols page contains
the Solana USDt address `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`.

The addresses are reference-only. SB-2.2 found that Printer's USDC constant is
not consistent with Circle's current official source; that mismatch must be
repaired or explicitly resolved before source-stack adoption.

---

## 3. Last Verified Date and Version

- Verified: 2026-07-12
- WSOL: stable canonical constant; unchanged since SPL Token inception.
- USDC on Solana: official Circle source now differs from Printer's current
  constant; classify Printer constant as implementation gap until repaired.
- USDT on Solana (USDt): stable; Tether has not migrated the Solana USDt address.
- Risk-based freshness: re-verify within 30 days before any live quote or routing
  use that depends on exact address matching.

---

## 4. Authority/Status Dimensions

| Dimension | Value |
|---|---|
| `upstream_lifecycle` | `ACTIVE` (all three addresses are active on Solana mainnet) |
| `printer_readiness` | `REFERENCE_ONLY` (hardcoded reference constants; no live source adapter for these addresses by themselves) |
| `printer_role` | `CONTEXT_ONLY` (route context, pair-side identification, quote filtering; not memecoin targets) |
| `access_policy` | `KEYLESS_PUBLIC` (hardcoded constants; no API call required) |
| `v1_permission` | `ALLOWED_GOVERNED` (as reference constants in governed adapters; no execution) |

---

## 5. Allowed Capabilities

- Use as hardcoded constants in discovery pair filtering, quote routing context,
  and liquidity interpretation.
- Use to identify quote-side (base/route) assets in DEX pair data.
- Use as exclusion filter: these addresses must never become memecoin tracking
  candidates.
- Use in paper-realism context (e.g., Jupiter quote routes involving WSOL/USDC).
- All uses must flow through governed adapters; no direct free-standing source
  loop may use these constants to bypass the Source Governor.

---

## 6. Prohibited Capabilities

- Do not trade, swap, route, or transfer WSOL, USDC, or USDT in V1. No wallet
  interaction, signing, or real fund movement.
- Do not select these addresses as Printer V1 memecoin tracking targets.
- Do not use these addresses to claim a paired memecoin is safe or high-quality.
  Pairing with WSOL/USDC/USDT does not make a memecoin safe.
- Do not open paper positions denominated in or targeting these infrastructure
  tokens.
- No BUY/SELL/HOLD decisions. No paper positions. No PnL.

---

## 7. Authentication and Cost Model

- Authentication: none. These are hardcoded string constants; no API call is
  required to use them.
- Cost: zero. Reference constants have no API rate-limit impact.
- Any external source call that uses these addresses as parameters (e.g., a
  DEX pair lookup or quote call) inherits that source's cost model.

---

## 8. Programs, Endpoints, Methods, and Request Contracts

This module does not define RPC endpoints or request contracts by itself. The
addresses are constants used within other adapters.

### 8.1 Wrapped SOL (WSOL)

| Item | Value | Authority |
|---|---|---|
| Mint address | `So11111111111111111111111111111111111111112` | A1: `github.com/solana-program/token` |
| Token program | SPL Token (`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`) | A1 |
| Nature | Wrapped native SOL; the SPL representation of SOL for token program compatibility | A1 |
| On-chain supply | Reflects wrapped SOL balance; unbounded as SOL can always be wrapped | A1 |

### 8.2 Solana USDC

| Item | Value | Authority |
|---|---|---|
| Mint address | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` | A4: Circle Inc. official documentation (`https://developers.circle.com/stablecoins/usdc-contract-addresses.md`) |
| Token program | SPL Token (`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`) | A4 |
| Issuer | Circle Inc. | A4 |
| Nature | Solana-native USDC stablecoin | A4 |

### 8.3 Solana USDT / USDt

| Item | Value | Authority |
|---|---|---|
| Mint address | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | A4: Tether Ltd. official documentation (`https://tether.to/en/supported-protocols`) |
| Token program | SPL Token (`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`) | A4 |
| Issuer | Tether Ltd. | A4 |
| Nature | Solana-native USDt stablecoin; Tether uses "USDt" for Solana to distinguish from USDT on other chains | A4 |

---

## 9. Response and Field Semantics

These addresses appear in DEX pair data (e.g., DexScreener `baseToken.address`
or `quoteToken.address`), GeckoTerminal pool data, and Jupiter quote route data.
Their semantic role in each context:

- **Quote/route token:** paired with a memecoin as the liquidity denominator.
  Their presence confirms the pair's quote currency.
- **Pair-side filter:** discovery logic uses these addresses to confirm a pair
  has a known quote asset before tracking.
- **Filter recognition does not prove safety:** a memecoin paired with WSOL is
  not automatically safe. Liquidity, volume, flow, and safety checks still apply.

---

## 10. Nullable/Missing-Field Behavior

These are hardcoded constants; there is no nullable response. If a DEX pair
response returns a base or quote token address that matches these constants,
the match is exact-string comparison. No fuzzy matching.

If a pair response does not include a token address, the pair data is incomplete
and the pair should be filtered out by normal data-quality gates.

---

## 11. Rate Limits and Bounded-Use Rules

No direct rate limits; these are string constants. Any API call that passes
these addresses as parameters is subject to that API's rate limits.

In Jupiter quote context: see `jupiter-quote-api-contract.md` (planned for
SB-3+). Jupiter quote is paper-realism-only in Printer V1.

---

## 12. Evidence Strength

These addresses do not produce evidence tiers (T1–T5 / OBSERVED_LIVE_LAUNCH).
They are infrastructure reference constants used for context and filtering.
Their presence in a pair record contributes:
- **Routing context:** confirms a tradeable quote asset exists.
- **Paper-realism context:** WSOL/USDC/USDT are required for realistic slippage
  and price-impact simulation.

Not an evidence source for token age, safety classification, or memory quality.

---

## 13. Normalization and Failure Rules

- Address matching is exact-string, case-sensitive.
- Unrecognized addresses in pair quote slots are not treated as infrastructure
  mints. Unknown quote assets may reduce data quality but do not fail the record.
- A memecoin whose address matches one of the three infrastructure mints must
  be rejected as an INSTANT_REJECT before tracking begins. This prevents
  infrastructure mints from being tracked as memecoins.

---

## 14. Security/Redaction Rules

- These addresses are public blockchain identifiers; no redaction is needed.
- They must not be used as private keys, wallet addresses, or credentials.
- Pairing them in logs or DB rows alongside token data is safe.

---

## 15. Known Upstream Quirks

- **USDT symbol on Solana:** Tether uses "USDt" (lowercase t) for the Solana
  version to distinguish it from "USDT" on other chains. Printer code may use
  "USDT" as the symbol constant; the address is authoritative, not the symbol.
- **WSOL address trailing `2`:** the native SOL mint has the unusual trailing
  `2` to make it a valid base58-encoded public key (the first 31 bytes are
  all zeros; `2` encodes the last byte as 1 in base58). This is expected and
  correct.
- **Circle's Solana USDC mismatch:** Circle's current official page lists
  `EPjF...TDt1v`; Printer currently uses `EPjF...CH8Ej`. Treat Printer's
  constant as an implementation gap until a later production repair/proof lane
  updates or otherwise resolves it.
- **Tether USDt vs third-party USDT clones:** `Es9v...YB` is the official
  Tether USDt. Impersonator tokens with similar names exist; exact address
  matching is the only safe identification method.

---

## 16. Known Printer Mistakes

| Mistake | Status |
|---|---|
| Printer's current USDC infrastructure mint constant differs from Circle's current official Solana USDC mint | Implementation gap found by SB-2.2; requires later production repair/proof before hard-policy adoption |
| USDT symbol listed as "USDT" in some source files where Tether uses "USDt" for Solana | Cosmetic; address is correct; no functional impact; noted for documentation accuracy |
| Official URL for USDC and USDT not pinned in current source-stack modules | Resolved by SB-2.2 for Circle and Tether pages; exact static file path for WSOL remains to be confirmed |

---

## 17. Required Fixtures/Proofs

Before these addresses are used as hard policy in any adoption lane:

1. Repair or explicitly justify the USDC implementation gap in a later
   production lane with targeted tests for discovery exclusion and route
   interpretation.
2. Pin the A1-tier WSOL path in `github.com/solana-program/token` with commit
   hash and file path.
3. Verify that Printer's existing constants in `geckoterminal.py` and
   `jupiter_quote.py` match the pinned A1/A4 sources after the USDC repair.
4. Confirm that discovery logic correctly excludes these mints from memecoin
   candidate selection.

---

## 18. Code and DB Integration Points

**Files where these constants appear (A6):**
- `src/printer_v1/sources/geckoterminal.py`: `_SOLANA_NATIVE_QUOTE_MINTS` set
  containing WSOL, USDC, and USDT - used to filter infrastructure tokens out
  of memecoin candidate selection. The USDC value is currently mismatched
  against Circle's official source and requires later repair.
- `src/printer_v1/sources/jupiter_quote.py`: WSOL and USDC used as quote
  currency references for paper-simulation quote routing.

**DB:** no dedicated table for infrastructure mints; they appear in pair data
tables as token addresses.

---

## 19. Unresolved Questions

| Item | Status |
|---|---|
| Official Circle USDC documentation URL for Solana USDC address | Resolved in SB-2.2: `https://developers.circle.com/stablecoins/usdc-contract-addresses.md` |
| Official Tether USDt documentation URL for Solana USDt address | Resolved in SB-2.2: `https://tether.to/en/supported-protocols` |
| WSOL exact file path in `github.com/solana-program/token` | Repository HEAD pinned in SB-2.2 as `405c9172df3aeb508712142aae1caf0d31ada671`; exact file path `interface/src/native_mint.rs` still needs final static verification |
| Whether Circle or Tether has changed / plans to change the Solana mint address | `UNKNOWN_REQUIRES_RESEARCH` — both are stable historically; monitor official changelogs |

---

## 20. Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | SB-2: module authored; 20 sections, original structure | Claude Opus 4.8 / SB-2 |
| 2026-07-12 | SB-2.1: restructured to exact 20-section template; each address documented with per-address authority table; USDT/USDt symbol distinction from Tether documented; WSOL trailing-2 explanation added; Circle/Tether impersonator-token warning added; `UNKNOWN_REQUIRES_RESEARCH` for exact official URLs preserved; status dimensions updated to SB-1 section 6 vocabulary | Claude Sonnet 4.6 / SB-2.1 |
| 2026-07-12 | SB-2.2: pinned Circle and Tether authority pages, corrected official USDC address to Circle's current Solana mainnet address, recorded Printer's current USDC constant as an implementation gap, and pinned the official `solana-program/token` repository HEAD for WSOL follow-up | Codex standard/balanced / SB-2.2 |
