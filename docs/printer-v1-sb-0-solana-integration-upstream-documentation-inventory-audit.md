# Printer V1 SB-0 Solana Integration and Upstream Documentation Inventory Audit

**Lane:** SB-0
**Type:** Audit and inventory only — read-only. No code changes. No tests. No DB mutation. No live RPC.
**Executor:** Claude Sonnet 4.6 (lane specified Fable 5; actual executor is Sonnet 4.6 — reported honestly)
**Date:** 2026-07-12
**Verdict:** `AUDIT_COMPLETE_WITH_BLOCKERS`

---

## 0. Lane Constraints and What This Document Is Not

This audit does not:
- Change production code, tests, migrations, or any DB rows
- Run live RPC, discovery, or source fetching
- Mutate any DB
- Run scheduler or runtime
- Generate memory, activate retrieval, create paper decisions
- Unlock BUY/SELL/HOLD, create positions/trades/audits/PnL
- Unlock A3 or V2-3
- Resume the T3 live proof
- Adopt a new source-of-truth stack
- Make architecture decisions (deferred to SB-1 with Opus)

Items that cannot be verified from local repo + upstream docs alone are marked
`UNKNOWN_REQUIRES_RESEARCH`. Architecture conflicts and authority gaps are flagged
but not resolved.

---

## 1. Required Source-of-Truth Reads Completed

| Document | Confirmed Read |
|---|---|
| `AGENTS.md` | YES |
| `docs/printer-v1-clean-master-spec.md` | YES |
| `docs/printer-v1-post-rc-build-order.md` | YES |
| `docs/printer-v1-memory-factory-guide.md` | YES |
| `docs/printer-v1-current-state-memory-growth-audit.md` | YES |
| `docs/printer-v1-memory-growth-build-order-v2.md` | YES |

Additional docs read for Solana/T3 context:

| Document | Purpose |
|---|---|
| `docs/printer-v1-v2-2ai-t3-solana-rpc-token-age-readiness-audit.md` | T3 readiness audit |
| `docs/printer-v1-v2-2aj-t3-solana-rpc-token-age-evidence-design.md` | T3 design |
| `docs/printer-v1-v2-2al-4-t3-page-cap-provenance-readiness-review.md` | Failure provenance review |
| `docs/printer-v1-v2-2al-4a-t3-failure-provenance-repair.md` | V2-2AL.4A repair record |

---

## 2. V1 Scope Constraints (from master spec)

Printer V1 is Solana-only. Solana memecoin-only. Paper trading only.

- Chain: Solana mainnet-beta only
- Asset class: Solana memecoins (SPL Token and Token-2022 program mints)
- Data: free/public data only; no paid APIs; no private keys
- Decision: memory comparison only; no scoring, no confidence, no weighted logic
- Output: BUY, SELL, HOLD, WAIT, AVOID, NO_ACTION — all paper-only
- Live execution, wallet signing, real funds: explicitly out of scope for V1

---

## 3. Full Source Registry (11 registered sources)

Source registry: `src/printer_v1/sources/registry.py`

| Source Name | Type | Solana | Request Kinds | Adapter File | Network Execution |
|---|---|---|---|---|---|
| `dexscreener` | free_public | YES (via solana chain filter) | `pair_discovery`, `pair_reference`, `smoke_check`, `token_profile_reference`, `trending_reference` | `dexscreener.py` | fixture_only |
| `geckoterminal` | free_public | YES (solana network) | `geckoterminal_new_pool_discovery`, `geckoterminal_trending_pool_reference` | `geckoterminal.py` | fixture_only |
| `pumpportal` | free_public | YES | `pumpfun_launch_stream`, `pumpfun_migration_stream` | `pumpportal.py` | live (WebSocket transport implemented) |
| `alternative_me` | free_public | NO (broad crypto) | `fear_greed_reference` | `alternative_me.py` | fixture_only |
| `coingecko` | free_public | YES (SOL price) | `market_reference`, `chain_heat_reference` | `coingecko.py` | fixture_only |
| `defillama` | free_public | YES (Solana TVL) | `chain_tvl_reference`, `chain_heat_reference` | `defillama.py` | fixture_only |
| `goplus` | free_public | YES (Solana token safety) | `safety_reference` | `goplus.py` | fixture_only (network transport available but not wired) |
| `solana_rpc` | free_or_user_supplied | YES (native) | `onchain_reference`, `mint_account_reference`, `pool_reference`, `holder_concentration_reference`, `mint_creation_time_reference` | `solana_rpc_holder.py` + `solana_rpc_token_age.py` | holder: fixture_only; token_age: LIVE (network transport implemented) |
| `helius_free` | free_tier_optional | YES (native) | `onchain_reference`, `mint_account_reference`, `pool_reference` | **NO ADAPTER FILE FOUND** | — |
| `pumpswap` | free_public | YES (native) | `pumpswap_pool_confirmation`, `pumpswap_migration_pool_reference`, `pumpswap_liquidity_reference` | `pumpswap.py` | fixture_only |
| `jupiter_quote` | free_public | YES (Solana AMM routing) | `paper_quote_realism` | `jupiter_quote.py` | fixture_only |

---

## 4. Solana Core — JSON-RPC

**Official authority:** https://solana.com/docs/rpc/http/

### 4.1 RPC Endpoint Used

| Item | Value | Source |
|---|---|---|
| Public mainnet-beta URL | `https://api.mainnet-beta.solana.com` | `src/printer_v1/sources/solana_rpc_holder.py` (`SOLANA_PUBLIC_RPC_URL`) |
| Protocol | JSON-RPC 2.0 over HTTP POST | Solana docs |
| Operator override | supported (URL injected at transport build time) | solana_rpc_token_age.py, solana_rpc_holder.py |

**Upstream authority verified:** `https://solana.com/docs/references/clusters` lists
`api.mainnet-beta.solana.com` as the official public mainnet-beta endpoint.

### 4.2 RPC Methods in Production Use

| Method | Adapter | Commitment | Purpose | Max Calls Per Token | Upstream Docs |
|---|---|---|---|---|---|
| `getAccountInfo` | `solana_rpc_token_age.py` | `confirmed` | Validate mint account owner program and decode mint data | 1 (per T3 run) | https://solana.com/docs/rpc/http/getaccountinfo |
| `getSignaturesForAddress` | `solana_rpc_token_age.py` | `confirmed` | Paginate transaction signature history for mint address | max 3 pages × 20 sigs | https://solana.com/docs/rpc/http/getsignaturesforaddress |
| `getTransaction` | `solana_rpc_token_age.py` | `confirmed` | Inspect transaction for initializeMint/initializeMint2 instruction | max 3 calls | https://solana.com/docs/rpc/http/gettransaction |
| `getBlockTime` | `solana_rpc_token_age.py` | — | Fallback block timestamp from slot number | max 1 call | https://solana.com/docs/rpc/http/getblocktime |
| `getTokenLargestAccounts` | `solana_rpc_holder.py` | — | Holder concentration — top accounts by balance | 1 (per holder check) | https://solana.com/docs/rpc/http |
| `getTokenSupply` | `solana_rpc_holder.py` | — | Total supply for concentration percentage calc | 1 (per holder check) | https://solana.com/docs/rpc/http |

**Total T3 per-token RPC budget:** max 8 operations (1 getAccountInfo + 3 sig pages + 3 getTransaction + 1 getBlockTime). Constant: `_T3_MAX_REQUESTS_PER_TOKEN = 8`.

### 4.3 Commitment Level Policy

| Commitment | Where Used | Meaning |
|---|---|---|
| `confirmed` | T3 (all getAccountInfo, getSignaturesForAddress, getTransaction calls) | Transaction confirmed by supermajority of cluster; may still be rolled back in rare cases |
| (none specified) | getBlockTime, getTokenLargestAccounts, getTokenSupply | RPC node default applies |

**Note for SB-1:** `confirmed` is weaker than `finalized`. For token-age evidence, `confirmed` vs `finalized` may matter if the mint transaction is very recent. This is an architecture question for SB-1.

### 4.4 Solana Request/Response Encoding Used

| Field | Value |
|---|---|
| T3 getAccountInfo encoding | `"base64"` |
| T3 getTransaction encoding | `"jsonParsed"` |
| T3 JSON-RPC id tracking | sequential integers per call, tracked in `request_ids` list |

---

## 5. Solana Core — SPL Token Program

**Official authority:** https://spl.solana.com/token  
**GitHub:** https://github.com/solana-program/token  
**Solana Explorer:** https://explorer.solana.com/address/TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA

| Item | Value | Verified |
|---|---|---|
| Program ID | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | YES — confirmed in spl.solana.com, solana-program/token repo, and Printer source |
| Mint account size | 82 bytes (`Mint::LEN = 82`) | YES — V2-2AL.1 confirmed from spl source |
| initializeMint instruction | type `"initializeMint"` in jsonParsed | YES — `_INIT_MINT_INSTRUCTION_TYPES` in solana_rpc_token_age.py |
| initializeMint2 instruction | type `"initializeMint2"` in jsonParsed | YES — same constant |
| WSOL mint | `So11111111111111111111111111111111111111112` | YES — in jupiter_quote.py and geckoterminal.py filter |
| USDC mint | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej` | YES — in geckoterminal.py `_SOLANA_NATIVE_QUOTE_MINTS` filter |
| USDT mint | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | YES — in geckoterminal.py filter |

---

## 6. Solana Core — Token-2022 Program

**Official authority:** https://spl.solana.com/token-2022  
**GitHub:** https://github.com/solana-labs/solana-program-library/tree/master/token/program-2022

| Item | Value | Verified |
|---|---|---|
| Program ID | `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` | YES — in Printer source and confirmed vs SPL repo |
| Base Mint layout bytes | `[0..82]` — same as SPL Token (`Mint::LEN = 82`) | YES — V2-2AL.1 |
| Padding region | `[82..165]` — 83 zero bytes (`Account::LEN - Mint::LEN = 165 - 82`) | YES — V2-2AL.1, confirmed from SPL source |
| AccountType discriminant | `[165]` — byte value `1` = Mint (`BASE_ACCOUNT_LENGTH = 165`) | YES — V2-2AL.1 |
| TLV extension data start | `[166..]` (`BASE_ACCOUNT_AND_TYPE_LENGTH = 166`) | YES — V2-2AL.1 |
| Minimum valid size | 166 bytes | YES — V2-2AL.1 |
| Printer constants | `_SPL_TOKEN_ACCOUNT_SIZE=165`, `_TOKEN_2022_ACCOUNT_TYPE_OFFSET=165`, `_TOKEN_2022_EXTENSION_DATA_START=166` | YES — solana_rpc_token_age.py |

**Root cause note:** V2-2AL live proof failure was caused by reading AccountType at byte 82 (padding) instead of byte 165 (correct offset). Repaired in V2-2AL.1 (commit `7aad246`).

---

## 7. Solana Core — Features NOT Found in Production Code

| Feature | Status in Printer V1 |
|---|---|
| Associated Token Accounts (ATAs) | NOT in production code |
| Metaplex Token Metadata Program | NOT in production code |
| Metaplex token name/symbol lookup | NOT in production code (name/symbol come from DEX data, not on-chain metadata) |
| Account compression / cNFT | NOT found |
| System Program (`11111111111111111111111111111111`) | NOT directly referenced |
| Stake program | NOT found |
| Vote program | NOT found |
| Compute budget instruction | NOT found |
| Priority fees | NOT found |

**Note for SB-1:** Metaplex token metadata could be relevant if Printer ever needs on-chain name/symbol verification. Currently the system trusts name/symbol from DexScreener/GeckoTerminal/PumpPortal. If token metadata spoofing is a safety concern, this is a gap for SB-1 to evaluate.

---

## 8. Protocol — Pump.fun / PumpPortal

### 8.1 Pump.fun Program IDs (from web research)

| Program | Program ID | In Printer Source |
|---|---|---|
| Pump.fun bonding curve | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` | NOT FOUND in production source |
| PumpSwap AMM | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | NOT FOUND in production source |

**Status:** Printer does not validate against these program IDs directly. Migration detection comes from the PumpPortal WebSocket `newRaydiumPool` field, not from on-chain program ID inspection. This is an architecture gap for SB-1.

### 8.2 PumpPortal WebSocket Adapter

**Official docs:** https://pumpportal.fun/data-api/real-time/  
**Adapter:** `src/printer_v1/sources/pumpportal.py`

| Item | Value | Verified |
|---|---|---|
| WebSocket URL | `wss://pumpportal.fun/api/data` | YES — official docs confirm this base URL (with optional `?api-key=` parameter) |
| subscribeNewToken | `{"method": "subscribeNewToken"}` | YES — official docs list this as a free method |
| subscribeMigration | `{"method": "subscribeMigration"}` | YES — official docs list this as a free method |
| API key required? | NO for `subscribeNewToken` and `subscribeMigration` (free) | YES — confirmed from pumpportal.fun/data-api/real-time |
| Max events default | 5 | Printer internal limit |
| Duration limit | 30.0 seconds | Printer internal limit |
| Connect timeout | 10.0 seconds | Printer internal limit |
| Python package dependency | `websockets` | Printer source |
| Network execution | YES — live WebSocket transport implemented | in pumpportal.py |

### 8.3 PumpPortal Event Fields for Token-Age Evidence

| Field | Printer Priority | When Present | Maps To |
|---|---|---|---|
| `tokenCreatedAt` | 1 (highest) | Some events | T2 evidence tier |
| `createdTimestamp` | 2 | Some events | T2 evidence tier |
| `timestamp` | 3 | Some events | T2 evidence tier |
| (none) | — | When all 3 missing | OBSERVED_LIVE_LAUNCH tier |

**Status of field definitions:** PumpPortal official docs do NOT document which specific fields are returned for subscribeNewToken events. The priority chain is derived from V2-2AF design and V2-2AE live diagnostics, not from official PumpPortal schema documentation.

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** PumpPortal does not publish a stable schema for subscribeNewToken event fields. The `tokenCreatedAt`, `createdTimestamp`, `timestamp` priority chain is inferred from observed live events, not from official docs. Any PumpPortal API change could silently break T2 evidence without a schema contract to detect it.

### 8.4 PumpPortal Migration Stream Fields

| Field | Purpose in Printer |
|---|---|
| `newRaydiumPool` | Extracted as migration pool address |
| `dex` label set to | `"raydium"` (when request_kind is `pumpfun_migration_stream`) |

**Note:** Despite the field name `newRaydiumPool`, web research confirms Pump.fun graduated to PumpSwap (not Raydium) starting March 20, 2025. The `newRaydiumPool` field name appears to be legacy nomenclature retained by PumpPortal even for PumpSwap-destination migrations. This is an `UNKNOWN_REQUIRES_RESEARCH` item — whether the `newRaydiumPool` field still contains the correct pool address for PumpSwap-destination migrations requires verification against live data.

---

## 9. Protocol — PumpSwap

**Official PumpPortal docs:** https://pumpportal.fun/data-api/pump-swap/  
**Adapter:** `src/printer_v1/sources/pumpswap.py`

| Item | Value |
|---|---|
| AMM Program ID (web research) | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` |
| Printer adapter mode | `fixture_transport_only=True`; `supports_network_execution=False` |
| Allowed request kinds | `pumpswap_pool_confirmation`, `pumpswap_migration_pool_reference`, `pumpswap_liquidity_reference` |
| Registry restriction | `read_only_confirmation` |
| Source governor | enabled_by_default=False; requires governor context |
| Launch date | March 20, 2025 (from web research) |

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** PumpSwap program ID `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` is confirmed from web research but is NOT hardcoded in Printer's PumpSwap adapter. If future implementation needs to validate that a pool address belongs to the PumpSwap program, this program ID must be added. Architecture decision for SB-1.

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** PumpSwap pool state RPC structure (account layout, instruction set) is not documented in Printer source. The adapter is fixture-only and contains no network read path.

---

## 10. Protocol — Jupiter

**Official docs:** https://developers.jup.ag/docs/swap/get-quote  
**Adapter:** `src/printer_v1/sources/jupiter_quote.py`

| Item | Printer Value | Current Upstream Value | Status |
|---|---|---|---|
| Current base URL (primary) | `https://lite-api.jup.ag/swap/v1/quote` | `https://api.jup.ag/swap/v1/quote` | **MISMATCH — UNKNOWN_REQUIRES_RESEARCH** |
| Legacy URL in code | `https://quote-api.jup.ag/v6/quote` (`JUPITER_QUOTE_LEGACY_V6_URL`) | Not in current docs | UNKNOWN |
| API key required? | NOT in Printer's transport (no key header) | YES per current Jupiter docs (`x-api-key` header required) | **POSSIBLE BREAKING CHANGE** |
| WSOL mint (input for quotes) | `So11111111111111111111111111111111111111112` | Confirmed WSOL mint address | YES |
| Paper simulation only | YES — `restriction="paper_simulation_only"` | — | Printer policy |
| Network execution | NO — `fixture_transport_only=True` | — | Printer policy |
| Response fields used | `outAmount`, `priceImpactPct`, `routePlan` | Present in Metis API | YES |
| Metis API status | In use | "No longer actively maintained; superseded by Swap V2" | **BREAKING RISK** |

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** Whether `lite-api.jup.ag/swap/v1/quote` still works without an API key is not confirmed from official upstream docs. The current official endpoint is `api.jup.ag/swap/v1/quote` and requires an API key. SB-1 must verify whether the lite endpoint remains usable for free paper simulation or whether a Jupiter API key is now required.

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** Jupiter Swap V2 has superseded the Metis API. The Printer adapter uses Metis-era Swap V1 behavior. SB-1 must determine whether Swap V2 response schema differs enough to require adapter changes.

---

## 11. Protocol — Raydium

**Production status in Printer V1:** LABEL ONLY — no Raydium adapter, no Raydium RPC calls, no Raydium program ID referenced.

Raydium appears only in:
- `src/printer_v1/discovery/contracts.py`: `RAYDIUM_POOL_CONFIRMATION = "RAYDIUM_POOL_CONFIRMATION"` (enum value)
- `src/printer_v1/sources/pumpportal.py`: `"dex": "raydium"` label set when request kind is `pumpfun_migration_stream`; `newRaydiumPool` field extracted as migration pool address

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** With Pump.fun graduating to PumpSwap (not Raydium) since March 2025, the `dex: "raydium"` label for migration events may be inaccurate for post-March-2025 tokens. SB-1 must evaluate whether migration events now reflect PumpSwap destinations and whether the dex label and `RAYDIUM_POOL_CONFIRMATION` enum need updating.

---

## 12. Protocol — Meteora / Orca / Whirlpool / Serum / OpenBook

| Protocol | Status |
|---|---|
| Meteora | NOT in production source. Found only in historical phase-era test fixtures (pre-V2 era). |
| Orca / Whirlpool | NOT in production source. Found only in historical test fixtures. |
| Serum / OpenBook | NOT found in any source file. |

No audit action required for Meteora, Orca, Serum, or OpenBook at SB-0 level. These are out of scope for current V1 implementation.

---

## 13. Provider — Solana Public RPC

| Item | Value |
|---|---|
| URL | `https://api.mainnet-beta.solana.com` |
| Constant | `SOLANA_PUBLIC_RPC_URL` in `solana_rpc_holder.py` |
| Cost | Free / public |
| Rate limits | Not formally documented; subject to cluster-level throttling |
| Auth required | None |
| Printer usage | T3 token-age enrichment (live, bounded); holder concentration (fixture_only, network transport available) |
| Operator override | Supported via URL injection in both adapters |
| Official cluster docs | https://solana.com/docs/references/clusters |

---

## 14. Provider — Helius Free Tier

**Registry entry:** `helius_free` in `src/printer_v1/sources/registry.py`  
**Adapter file:** NOT FOUND (`src/printer_v1/sources/helius*.py` — no results)

| Item | Value |
|---|---|
| Registry purpose | "Solana onchain reference where free tier is available" |
| dependency_type | `free_tier_optional` |
| requires_paid_plan | `False` |
| allowed_request_kinds | `onchain_reference`, `mint_account_reference`, `pool_reference` |
| Adapter implementation | **NOT IMPLEMENTED** — registered in registry only |

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** Helius is registered as a source but has no adapter file, no transport, no normalizer, and no tests. The free tier URL (`https://rpc.helius.xyz/?api-key=...`) requires an API key even for the free tier. Whether a no-key path exists for Helius or whether this source requires a free signup is not verified.

**Note:** Helius registration with `free_tier_optional` means Printer's registry explicitly accounts for it as an optional enhancement, not a required dependency. However, since no adapter exists, `helius_free` cannot currently be used.

---

## 15. Provider — GoPlus

**Official docs:** https://docs.gopluslabs.io/reference/solanatokensecurityusingget  
**Adapter:** `src/printer_v1/sources/goplus.py`

| Item | Value | Status |
|---|---|---|
| API URL | `https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={token_mint}` | CONFIRMED — matches GoPlus official docs |
| API key required | NO for basic use | CONFIRMED — GoPlus docs show no auth header for public API |
| Response shape | `{"code": 1, "message": "OK", "result": {"<mint>": {...}}}` | CONFIRMED — Printer normalizer handles this shape |
| Solana API status | Beta | CONFIRMED from GoPlus changelog |
| Timeout | 10.0 seconds | Printer internal limit |
| Network execution | fixture_only in adapter, but `build_goplus_token_safety_transport()` provides real HTTP transport | available but not wired into governed path |
| Rate limit behavior | HTTP 429 maps to `STALE` with 120s retry | Printer source |

**Fields Printer normalizes from GoPlus:**
- `mint_authority_status` — MINT_AUTHORITY_RENOUNCED / PRESENT / UNKNOWN
- `freeze_authority_status` — FREEZE_AUTHORITY_DISABLED / PRESENT / UNKNOWN
- `metadata_mutability_status` — METADATA_IMMUTABLE / MUTABLE / UNKNOWN
- `supply_sanity_label`
- `holder_concentration_label` (separate from RPC holder check)
- `liquidity_lock_or_burn_label`
- `known_risk_flag_label`
- `token_program_label` — SPL_TOKEN_OR_TOKEN_2022_VERIFIED / UNKNOWN / UNSUPPORTED
- `safety_context_label` — SAFETY_CLEAN / CAUTION / SUSPICIOUS / UNSAFE / UNKNOWN / DO_NOT_USE_FOR_MEMORY

**DB table:** `printer_solana_safety_evidence` (migration `022_solana_safety_evidence.sql`)

---

## 16. Provider — DexScreener

**Official docs:** https://docs.dexscreener.com/api/reference  
**Adapter:** `src/printer_v1/sources/dexscreener.py`

| Printer URL | Current Upstream Status |
|---|---|
| `https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}` (DEXSCREENER_PAIR_URL_TEMPLATE) | Listed in current docs as `GET /latest/dex/pairs/{chainId}/{pairId}` — MATCHES |
| `https://api.dexscreener.com/latest/dex/tokens/{token_mint}` (DEXSCREENER_TOKEN_URL_TEMPLATE) | NOT listed in current docs — new docs show `/tokens/v1/{chainId}/{tokenAddresses}` — **UNKNOWN_REQUIRES_RESEARCH** |
| `https://api.dexscreener.com/latest/dex/search?q=SOL` (DEXSCREENER_SMOKE_URL) | `/latest/dex/search` listed in current docs — MATCHES |

| Item | Value |
|---|---|
| API key required | NO — no auth shown in current docs |
| Rate limit | 60 req/min (from docs, per endpoint) |
| Timeout | 5.0 seconds (smoke), adapter default for pair/token |
| Network execution | fixture_only |

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** Printer's `DEXSCREENER_TOKEN_URL_TEMPLATE` uses `/latest/dex/tokens/{token_mint}`. The current DexScreener API docs do not list this endpoint; the current equivalent is `/tokens/v1/{chainId}/{tokenAddresses}`. Whether the legacy `/latest/dex/tokens/` endpoint is still supported is unverified. This could be a silent breaking change.

---

## 17. Provider — GeckoTerminal

**Official docs:** https://apiguide.geckoterminal.com/  
**Swagger:** https://api.geckoterminal.com/docs/index.html  
**Adapter:** `src/printer_v1/sources/geckoterminal.py`

| Item | Value | Status |
|---|---|---|
| New pools URL | `https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1` | CONFIRMED — endpoint format matches GeckoTerminal docs |
| Trending pools URL | `https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?page=1` | CONFIRMED — endpoint format matches |
| API key required | NO for public use | CONFIRMED from GeckoTerminal docs |
| Accept header | `application/json;version=20230302` | In Printer adapter |
| Timeout | 8.0 seconds | Printer internal |
| Network execution | fixture_only |

**Filter constants in Printer source:**
```python
_SOLANA_NATIVE_QUOTE_MINTS = frozenset({
    "So11111111111111111111111111111111111111112",  # WSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
})
```
These mints are filtered from base_token to avoid including infrastructure assets as memecoin candidates.

---

## 18. Provider — Alternative.me

**Official docs:** https://alternative.me/crypto/api/  
**Adapter:** `src/printer_v1/sources/alternative_me.py`

| Item | Value | Status |
|---|---|---|
| URL | `https://api.alternative.me/fng/?limit=2&format=json` | CONFIRMED — matches official endpoint |
| API key required | NO — public free API | CONFIRMED |
| Update frequency | Every 5 minutes | From alternative.me docs |
| Rate limit | 60 req/min over 10-minute window | From web research |
| Timeout | 5.0 seconds | Printer internal |
| Network execution | fixture_only |
| Solana relevance | Broad crypto sentiment context only — not Solana-specific | Noted |

---

## 19. Provider — CoinGecko

**Official docs:** https://docs.coingecko.com/reference/simple-price  
**Adapter:** `src/printer_v1/sources/coingecko.py`

| Printer URL | Current Upstream Status |
|---|---|
| `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana...` | Current docs recommend `https://pro-api.coingecko.com/api/v3/simple/price` with a demo API key header (`x-cg-demo-api-key`) — **UNKNOWN_REQUIRES_RESEARCH** |

| Item | Value |
|---|---|
| Timeout | 8.0 seconds |
| Coins fetched | bitcoin, ethereum, solana — USD price, 24h change, 24h vol |
| Network execution | fixture_only |
| API key in Printer | NONE |

**UNKNOWN_REQUIRES_RESEARCH (SB-1):** CoinGecko has moved their public API to require a free demo API key (`x-cg-demo-api-key`). The old `api.coingecko.com` URL with no key may still work (rate-limited), but official docs now reference `pro-api.coingecko.com` with a demo key. SB-1 must verify whether the legacy no-key endpoint is still functional or has been deprecated.

---

## 20. Provider — DefiLlama

**Official docs:** https://api-docs.defillama.com/  
**Adapter:** `src/printer_v1/sources/defillama.py`

| Item | Value | Status |
|---|---|---|
| URL | `https://api.llama.fi/v2/chains` | CONFIRMED — standard DefiLlama chains endpoint |
| API key required | NO for public free endpoints | CONFIRMED |
| Pro endpoints | `https://pro-api.llama.fi` (requires key, not used) | Out of scope |
| Timeout | 8.0 seconds | Printer internal |
| Network execution | fixture_only |
| Data used | Solana TVL, chain heat context | Broad context only, not per-token |

---

## 21. Token-Age Evidence Contracts

**Source:** `src/printer_v1/discovery/parser.py` (`_derive_token_age_evidence_tier()`)

| Tier | Label | Mechanism | Source | Status |
|---|---|---|---|---|
| T1 | `"T1"` | Historically defined (V2-2O): direct token creation timestamp from a source — Solana RPC getAccountInfo blockTime of init tx, Helius enrichment, or future PumpPortal/PumpSwap feed | Depends on future source | DEFINED in historical docs (V2-2O); NOT YET IMPLEMENTED |
| T2 | `"T2"` | `tokenCreatedAt` / `createdTimestamp` / `timestamp` from PumpPortal launch event | `pumpportal` | IMPLEMENTED AND FIXTURE-PROVEN (V2-2AG, 82 tests); NOT positively live-proven — V2-2AH returned `LIVE_PROOF_INCONCLUSIVE_NO_EVENTS` (zero raw messages received in 30s) |
| T3 | `"T3"` | On-chain `initializeMint`/`initializeMint2` via Solana JSON-RPC history-walk path (getSignaturesForAddress → getTransaction → optional getBlockTime) | `solana_rpc` (`mint_creation_time_reference`) | IMPLEMENTED AND FIXTURE-PROVEN (V2-2AK, 132 tests); two live proofs failed safely (V2-2AL: Token-2022 layout error; V2-2AL.3: page-cap exhaustion on high-history mint); AL.4A+AL.4B complete; next proof V2-2AL.5 pending; direct-signature path (skip history walk) not yet designed |
| T4 | `"T4_PAIR_ONLY"` | Historically defined (V2-2O, V2-2AF): pair-age diagnostic context only — `pool_created_at` (GeckoTerminal), `pairCreatedAt` (DexScreener). Never maps to `token_created_at`. | `dexscreener`, `geckoterminal` | DEFINED (V2-2O/V2-2AF) and IMPLEMENTED as `pair_age_context_label`; counted as `T4_PAIR_ONLY` in evidence tier count dicts; does NOT produce `token_age_seconds` or satisfy A3 |
| T5 | `"T5_UNKNOWN"` | Historically defined (V2-2O): the null/unknown sentinel — no T1/T2/T3 evidence. `token_age_evidence_tier = null`. Current universal state for non-PumpPortal, non-T3-enriched tokens. | N/A | DEFINED (V2-2O) as null/unknown state; counted as `T5_UNKNOWN` in evidence tier count dicts |
| OBSERVED_LIVE_LAUNCH | `"OBSERVED_LIVE_LAUNCH"` | PumpPortal launch event observed but no timestamp field (`tokenCreatedAt`/`createdTimestamp`/`timestamp`) present | `pumpportal` | IMPLEMENTED AND FIXTURE-PROVEN (V2-2AG, 30 tests); V2-2AE diagnostics observed 4 qualifying live events (`DIAGNOSTICS_COMPLETE_PAYLOAD_SHAPE_BLOCKER`); V2-2AH live proof returned zero events — NOT positively live-proven |

**A3 gate:** `_tok_age_known = candidate.get("token_age_seconds") is not None`
- Only T2 and T3 (success path) can satisfy A3.
- OBSERVED_LIVE_LAUNCH does NOT satisfy A3.
- T3 failure provenance does NOT satisfy A3.
- T4 (`pair_age_context_label`) does NOT satisfy A3.
- T5 (null) does NOT satisfy A3.

**Tier hierarchy (descending trust):** T1 > T2 > T3 > OBSERVED_LIVE_LAUNCH > None/T5

**T1 (SB-1 note):** T1 is defined in V2-2O as the highest-trust tier: a direct token creation timestamp from a source, without needing to derive it from signature history walk. Candidate paths listed in V2-2O: Solana RPC getAccountInfo returning blockTime of the initialization tx, Helius free-tier enrichment, or a future PumpPortal/PumpSwap feed that carries a canonical on-chain token creation event. T1 has never been implemented. SB-1 should confirm whether T1 remains a target or is deferred. Note: a direct-signature T3 variant (bypass getSignaturesForAddress by using a known mint tx signature, then call getTransaction once) would be architecturally distinct from the current T3 history-walk path and potentially close the gap toward T1 in reliability; whether this constitutes T1 or an upgraded T3 is a design question for SB-1.

**T4 (SB-1 note):** T4 is defined and implemented. V2-2AF explicitly reserved the label `T4` for "pair-age diagnostic context only (V2-2X.1 Invariant 7)" and rejected using it for OBSERVED_LIVE_LAUNCH. T4 is counted as `T4_PAIR_ONLY` in evidence tier count dicts alongside T1/T2/T3/T5.

**T5 (SB-1 note):** T5 (`T5_UNKNOWN`) is defined as the null/unknown state: `token_age_evidence_tier = null`. V2-2O states: "The tier labels will all resolve to null (T5) unless a T1/T2/T3 source is activated." This is the current universal state for tokens discovered via DexScreener/GeckoTerminal without T3 enrichment.

**Historical contradiction (V2-2AA, superseded):** V2-2AA (early design, pre-V2-2O) stated "Migration events produce T1 evidence at best." This was written before the T1/T2/T3/T4/T5 hierarchy was formalized in V2-2O and V2-2AF. It is superseded. Under the current hierarchy, PumpPortal migration events do not produce T1/T2/T3 evidence; they produce no `token_created_at` and do not satisfy A3.

---

## 22. DB Schema — Solana-Related Tables

All schema is in SQLite migrations under `migrations/`.

| Table | Migration | Solana Relevance |
|---|---|---|
| `printer_solana_safety_evidence` | `022_solana_safety_evidence.sql` | Safety evidence from GoPlus/holder RPC. Columns: `mint_authority_status`, `freeze_authority_status`, `metadata_mutability_status`, `supply_sanity_label`, `holder_concentration_label`, `liquidity_lock_or_burn_label`, `known_risk_flag_label`, `token_program_label`, `safety_context_label`. `token_program_label` distinguishes `SPL_TOKEN_OR_TOKEN_2022_VERIFIED` from unsupported. |
| `printer_paper_quote_evidence` | `023_paper_quote_evidence.sql` | Jupiter Quote paper realism evidence. `quote_purpose` must be `PAPER_REALISM_ONLY`. Columns: `route_available_label`, `slippage_context_label`, `price_impact_context_label`, `entry_realism_label`, `exit_realism_label`. |
| `printer_source_responses` | `002_source_registry_governor.sql` | Raw source response blobs. Contains T3 RPC raw payloads when stored. |
| `printer_token_snapshots` | `006_token_level_snapshot_system.sql` | Per-token snapshot including `token_age_seconds`, `token_age_evidence_tier`, `token_created_at` fields (added in Solana T3 lanes). |

**Note for SB-1:** `printer_solana_safety_evidence` has a `token_program_label` column with values `SPL_TOKEN_OR_TOKEN_2022_VERIFIED` / `TOKEN_PROGRAM_UNKNOWN` / `TOKEN_PROGRAM_UNSUPPORTED`. This is the only place Printer's DB schema explicitly distinguishes between SPL Token and Token-2022 at a label level. The T3 adapter is the only code that actually reads the token program ID from on-chain data.

---

## 23. Source Governor Boundary Summary

All adapters follow the same governed pattern:
- `enabled_by_default: False` — never runs unless explicitly enabled
- `requires_governor_context: True` — caller must pass `SourceAdapterContext` with `governor_approved=True`
- `execution_path` must be `GOVERNOR_ONLY_EXECUTION_PATH`
- `fixture_transport_only: True` for all non-Solana-RPC adapters (pumpportal excepted — has live WebSocket transport)
- `supports_network_execution: True` only for: `pumpportal` (WebSocket) and `solana_rpc_token_age` (T3 HTTP RPC)

**Adapters with live network capability:**

| Adapter | Network Path | Transport Type | Governed |
|---|---|---|---|
| `pumpportal.py` | `build_pumpportal_live_transport()` | WebSocket (asyncio) | YES |
| `solana_rpc_token_age.py` | `build_solana_rpc_token_age_transport()` | HTTP JSON-RPC (urllib) | YES |
| `solana_rpc_holder.py` | `build_solana_rpc_holder_transport()` | HTTP JSON-RPC (urllib) | YES (but fixture_only flag) |
| `goplus.py` | `build_goplus_token_safety_transport()` | HTTP GET (urllib) | YES (but fixture_only flag) |

---

## 24. Python Dependency Inventory (Solana-related)

| Package | Purpose | Location |
|---|---|---|
| `websockets` | PumpPortal live WebSocket | Required by `pumpportal.py`; import guarded with try/except |
| `urllib` (stdlib) | HTTP JSON-RPC calls (Solana RPC, GoPlus, CoinGecko, etc.) | Used directly in all adapters |
| `json` (stdlib) | JSON-RPC request/response serialization | All adapters |
| `asyncio` (stdlib) | WebSocket event loop | `pumpportal.py` |

**No Solana Python SDK (solders, solana-py, anchorpy) is used.** All Solana RPC calls are raw JSON-RPC over HTTP via `urllib`. This is intentional — it avoids Rust/C FFI dependencies and keeps the integration minimal and auditable.

---

## 25. Proposed `docs/solana-builder-source-of-truth/` Directory Structure

For SB-1 adoption (not a decision, just a structural proposal):

```text
docs/solana-builder-source-of-truth/
├── README.md                              # Index and authority order
│
│ # Solana core (chain-level programs and accounts)
├── solana-core-rpc-reference.md           # JSON-RPC methods, commitment levels, cluster URLs
├── solana-spl-token-program.md            # SPL Token program, Mint layout, program ID
├── solana-token-2022-program.md           # Token-2022 layout, extensions, AccountType offset
├── solana-mint-addresses.md               # 3 infrastructure mints: WSOL, USDC, USDT
│
│ # Protocol authorities (on-chain programs Printer tracks or references)
├── pump-fun-bonding-curve-protocol.md     # Pump.fun bonding curve, graduation threshold, program ID
├── pumpswap-amm-protocol.md              # PumpSwap AMM, post-graduation pools, program ID
├── raydium-amm-label-context.md          # Raydium: appears as dex label in migration stream; no Printer adapter; stale-label risk
├── jupiter-routing-protocol.md           # Jupiter DEX aggregation routing; used via Quote API only
│
│ # Provider API contracts (upstream data APIs Printer calls)
├── pumpportal-api-contract.md            # WebSocket URL, subscribeNewToken/subscribeMigration, event schema
├── jupiter-quote-api-contract.md         # Quote endpoint, params, API key policy, Swap V2/Metis status
├── dexscreener-api-contract.md           # Pair/token endpoints, rate limits, legacy URL status
├── geckoterminal-api-contract.md         # new_pools/trending_pools endpoints, version header
├── goplus-api-contract.md                # Token security endpoint, response shape, beta status
├── coingecko-api-contract.md             # simple/price endpoint, API key policy, legacy URL status
├── defillama-api-contract.md             # chains endpoint, free vs pro separation
├── alternative-me-api-contract.md        # fng endpoint, rate limits, update frequency
├── helius-rpc-contract.md                # Free tier URL, API key requirement, implementation status
│
└── token-age-evidence-tier-registry.md   # T1–T5, OBSERVED_LIVE_LAUNCH, A3 gate, T4_PAIR_ONLY, T5_UNKNOWN
```

**Note on protocol/provider separation:** Protocol authority docs describe on-chain programs and their canonical program IDs (sourced from official chain explorers and program repositories). Provider API contracts describe off-chain APIs that may aggregate or interpret on-chain data. Pump.fun and PumpSwap are separate protocols — they should not share a doc. Raydium appears in Printer only as a `dex` label string in migration normalization; it has no Printer adapter and is included for label-accuracy audit purposes only.

---

## 26. Unresolved Items for SB-1

| Item | Type | Risk Level |
|---|---|---|
| Jupiter `lite-api.jup.ag/swap/v1/quote` vs `api.jup.ag/swap/v1/quote` + API key requirement | UNKNOWN_REQUIRES_RESEARCH | HIGH — adapter may be using a deprecated endpoint without a key |
| `dex: "raydium"` label in migration normalization | ACCURACY_GAP | HIGH — Pump.fun graduated to PumpSwap (not Raydium) since March 2025; the dex label in Printer's migration normalization is likely wrong for all tokens graduated after March 2025; affects over a year of migration events |
| CoinGecko `api.coingecko.com` (no key) vs `pro-api.coingecko.com` (demo key) | UNKNOWN_REQUIRES_RESEARCH | MEDIUM — legacy endpoint may be rate-limited or deprecated |
| DexScreener `/latest/dex/tokens/{token_mint}` vs `/tokens/v1/{chainId}/{tokenAddresses}` | UNKNOWN_REQUIRES_RESEARCH | MEDIUM — legacy endpoint not listed in current docs |
| PumpPortal `newRaydiumPool` field accuracy for PumpSwap-destination migrations | UNKNOWN_REQUIRES_RESEARCH | MEDIUM — name suggests Raydium but destination changed to PumpSwap in March 2025 |
| PumpPortal event field schema (`tokenCreatedAt`, etc.) not officially documented | UNKNOWN_REQUIRES_RESEARCH | MEDIUM — schema may change without notice |
| T3 failure provenance not persisted to DB | IMPLEMENTATION_GAP | MEDIUM — `printer_source_failures` table has no `normalized_payload_json` column; V2-2AL.4B verdict was `VERIFICATION_PARTIAL_WITH_BLOCKER`; provenance survives normalizer but is lost at persistence boundary |
| PumpSwap program ID (`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`) not in Printer source | ARCHITECTURE_GAP | LOW (current adapter is fixture-only) |
| Pump.fun bonding curve program ID (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`) not in Printer source | ARCHITECTURE_GAP | LOW (not needed currently) |
| Helius registered but no adapter | INCOMPLETE_REGISTRATION | LOW (marked as optional) |
| T1 evidence tier — defined (V2-2O) but not yet implemented | NOT_IMPLEMENTED | LOW — T3 covers the most viable on-chain path; T1 requires a direct-source timestamp; SB-1 should decide whether to pursue or defer |
| Metaplex token metadata for name/symbol verification | NOT_EVALUATED | LOW — currently trust DEX sources for this |
| `confirmed` vs `finalized` commitment for T3 mint-age evidence | ARCHITECTURE_QUESTION | LOW — for SB-1 to evaluate |

---

## 27. Safety Confirmations

- No live Solana RPC calls made.
- No PumpPortal, PumpSwap, or Jupiter calls made.
- No discovery or source fetching run.
- No persistent DB rows mutated.
- No code, tests, migrations, or data files modified.
- No memory windows created.
- No retrieval activated.
- No paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- No wallet, private key, signing, live execution, paid API, score, ranking, confidence, weighted logic, embedding, or vector path added.
- No AGENTS.md modifications.
- A3 remains locked.
- V2-3 remains paused.
- T3 live proof remains paused.
- Staged/native 15m blocker: PARTIAL - DEFERRED, NOT RESOLVED.

---

## 28. Exact Next Lane

`SB-1 — Solana Builder Source-Stack Architecture and Authority Design`

SB-1 should:
- Use Opus 4.8 (per lane instruction)
- Resolve `UNKNOWN_REQUIRES_RESEARCH` items through primary-source documentation research, official changelogs, and upstream authority docs (NOT live endpoint testing — SB-1 is architecture/design and primary-source research only)
- Design the authority structure for the `docs/solana-builder-source-of-truth/` directory using the proposed protocol/provider separation
- Confirm T1 evidence tier status (defined in V2-2O as highest-trust tier but never implemented; decide whether to target or defer; T4 and T5 are already defined and T4 is implemented)
- Resolve the `newRaydiumPool` / PumpSwap destination question and the `dex: "raydium"` label accuracy issue (HIGH severity, post-March 2025)
- Establish the Jupiter API key / Swap V2 policy (HIGH severity endpoint mismatch)
- Establish the CoinGecko and DexScreener legacy endpoint policies
- Evaluate the T3 failure provenance DB persistence gap (blocker for AL.4C)
- NOT change production code, NOT unlock A3 or V2-3, NOT resume T3 live proof

---

## 29. Final Verdict

```text
VERDICT: AUDIT_COMPLETE_WITH_BLOCKERS
LANE: SB-0
EXECUTOR: Claude Sonnet 4.6 (specified Fable 5; actual Sonnet 4.6 — reported honestly)
DATE: 2026-07-12

SOURCES_INVENTORIED:
  - 11 registered sources, all confirmed with adapter files (except helius_free)
  - 6 Solana JSON-RPC methods confirmed against official docs
  - 2 SPL Token programs confirmed (TokenkegQ..., Tokenz...)
  - 3 infrastructure mint addresses confirmed (WSOL, USDC, USDT — in _SOLANA_NATIVE_QUOTE_MINTS)
  - Token-2022 extension layout confirmed from V2-2AL.1 repair record
  - PumpPortal WebSocket confirmed (subscribeNewToken, subscribeMigration free)
  - PumpSwap program ID found in web research but not in Printer source
  - Jupiter Quote API endpoint version mismatch found
  - GoPlus Solana API confirmed (beta status)
  - DexScreener: 2 of 3 URLs confirmed; 1 legacy URL unverified
  - CoinGecko: API key policy change found, legacy URL unverified
  - GeckoTerminal: confirmed
  - Alternative.me: confirmed
  - DefiLlama: confirmed

EVIDENCE_TIERS:
  T2: FIXTURE-PROVEN (V2-2AG, 82 tests); NOT positively live-proven (V2-2AH: LIVE_PROOF_INCONCLUSIVE_NO_EVENTS — zero raw messages)
  OBSERVED_LIVE_LAUNCH: FIXTURE-PROVEN (V2-2AG, 30 tests); V2-2AE diagnostics showed 4 qualifying live events; V2-2AH inconclusive; NOT positively live-proven
  T3: FIXTURE-PROVEN (V2-2AK, 132 tests); two live proofs failed safely (V2-2AL: Token-2022 layout; V2-2AL.3: page-cap exhaustion); AL.4A+AL.4B complete; V2-2AL.5 next proof pending; direct-signature path not yet designed
  T1: DEFINED in historical docs (V2-2O) as highest-trust tier; NOT YET IMPLEMENTED
  T4: DEFINED (V2-2O/V2-2AF) and IMPLEMENTED as pair_age_context_label (T4_PAIR_ONLY); does NOT produce token_age_seconds
  T5: DEFINED (V2-2O) as T5_UNKNOWN null/unknown sentinel; default universal state

DB_TABLES: 2 Solana-specific tables confirmed (022, 023)
PYTHON_SDK: none — all Solana RPC via raw urllib/JSON-RPC
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
CODE_CHANGES: NONE

BLOCKERS:
  - 2 HIGH items: Jupiter endpoint mismatch, dex:raydium label accuracy (post-March 2025)
  - 5 MEDIUM items: CoinGecko key, DexScreener URL, PumpPortal field schema, newRaydiumPool accuracy, T3 DB persistence gap
  - 5 LOW items: PumpSwap/PumpFun program IDs not in source, Helius no adapter, T1 not implemented, Metaplex not evaluated, commitment level question

SB_1_PROPOSED_STRUCTURE: docs/solana-builder-source-of-truth/ (17 files, with protocol/provider separation)
NEXT_LANE: SB-1 — Solana Builder Source-Stack Architecture and Authority Design (Opus 4.8)
A3_STATUS: LOCKED
V2_3_STATUS: PAUSED
T3_LIVE_PROOF: PAUSED (V2-2AL.4B complete; V2-2AL.5 pending — approved mint: 6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump)
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
```

---

## 30. SB-0.1 Correction Record

**Lane:** SB-0.1 — Independent Inventory Correction and Scope Verification
**Executor:** Claude Sonnet 4.6
**Date:** 2026-07-12
**Verdict:** `AUDIT_CORRECTION_PASS`

This section records corrections applied in SB-0.1 to the original SB-0 audit (committed `0907561`). All corrections were derived from static inspection of historical Printer V1 design/proof/verification documents. No production code changes. No live RPC calls. No DB mutation.

### Documents Inspected for Corrections

- `docs/printer-v1-v2-2o-token-age-evidence-repair-design.md` — T1/T2/T3/T4/T5 tier definitions
- `docs/printer-v1-v2-2af-pumpportal-launch-timestamp-evidence-design-update.md` — T4 "pair-age diagnostic context only" confirmation
- `docs/printer-v1-v2-2ah-observed-live-launch-live-proof.md` — `LIVE_PROOF_INCONCLUSIVE_NO_EVENTS` — T2/OBSERVED_LIVE_LAUNCH NOT live-proven
- `docs/printer-v1-v2-2al-4b-t3-failure-provenance-verification.md` — `VERIFICATION_PARTIAL_WITH_BLOCKER` — AL.4B complete; DB persistence gap confirmed
- `docs/printer-v1-v2-2ae-pumpportal-live-event-diagnostics.md` — 4 qualifying OBSERVED_LIVE_LAUNCH events observed in diagnostics; NOT a formal proof
- `src/printer_v1/sources/geckoterminal.py` — `_SOLANA_NATIVE_QUOTE_MINTS`: exactly 3 mints (WSOL, USDC, USDT)

### Corrections Applied

| # | Section | Original Error | Correction |
|---|---|---|---|
| 1 | §21 T2 status | "IMPLEMENTED AND LIVE-PROVEN (V2-2AH)" | "IMPLEMENTED AND FIXTURE-PROVEN (82 tests); NOT positively live-proven — V2-2AH: LIVE_PROOF_INCONCLUSIVE_NO_EVENTS (zero raw messages)" |
| 2 | §21 OBSERVED_LIVE_LAUNCH status | "IMPLEMENTED AND LIVE-PROVEN (V2-2AH)" | "IMPLEMENTED AND FIXTURE-PROVEN (30 tests); V2-2AE diagnostics observed 4 events; V2-2AH inconclusive; NOT positively live-proven" |
| 3 | §21 T3 status | "IMPLEMENTED; live proof blocked (V2-2AL.4B required)" | "FIXTURE-PROVEN (132 tests); two live proofs failed safely; AL.4A+AL.4B complete; V2-2AL.5 next proof pending; direct-signature path not yet designed" |
| 4 | §21 T1 status | "Not yet defined / Unknown / UNKNOWN_REQUIRES_RESEARCH" | "DEFINED in V2-2O (direct source timestamp, highest-trust tier); NOT YET IMPLEMENTED" |
| 5 | §21 T4 status | "Not found in production code / UNKNOWN_REQUIRES_RESEARCH" | "DEFINED (V2-2O/V2-2AF) and IMPLEMENTED as pair_age_context_label (T4_PAIR_ONLY); does NOT produce token_age_seconds" |
| 6 | §21 T5 status | "Not found in production code; referenced as unknown / UNKNOWN_REQUIRES_RESEARCH" | "DEFINED (V2-2O) as T5_UNKNOWN null/unknown sentinel; counted in evidence tier count dicts" |
| 7 | §21 post-table notes | "T1 undefined"; "T4/T5 undefined" | Replaced with accurate T1/T4/T5 descriptions and historical-contradiction note (V2-2AA superseded) |
| 8 | §25 module structure | `pump-fun-pumpswap-protocol.md` (combined); Raydium absent; no protocol/provider separation | Split into `pump-fun-bonding-curve-protocol.md` + `pumpswap-amm-protocol.md`; added `raydium-amm-label-context.md` and `jupiter-routing-protocol.md`; added protocol/provider separation note |
| 9 | §26 T1/T4/T5 in blockers | T1 listed as MEDIUM ARCHITECTURE_GAP (undefined); T4/T5 listed as LOW ARCHITECTURE_GAP (undefined) | T4/T5 removed (defined and T4 implemented); T1 reclassified as LOW NOT_IMPLEMENTED (defined but not implemented) |
| 10 | §26 T3 persistence gap | Not listed in blockers | Added as MEDIUM IMPLEMENTATION_GAP (`printer_source_failures` has no `normalized_payload_json` column; AL.4B blocker confirmed) |
| 11 | §26 `dex: "raydium"` severity | MEDIUM ARCHITECTURE_GAP | Upgraded to HIGH ACCURACY_GAP — Pump.fun moved to PumpSwap over a year ago (March 2025); label is wrong for all post-March-2025 graduations |
| 12 | §28 SB-1 scope | "live endpoint testing" listed as SB-1 activity | Removed; SB-1 is architecture/design and primary-source research only |
| 13 | §29 infrastructure mint count | "4 WSOL/stablecoin mint addresses confirmed" | Corrected to "3 infrastructure mint addresses confirmed (WSOL, USDC, USDT)" — `_SOLANA_NATIVE_QUOTE_MINTS` has exactly 3 |
| 14 | §29 evidence tier summary | "T2 confirmed and live-proven; T3 confirmed; T1/T4/T5 undefined" | Corrected to accurate per-tier status (fixture-proven vs live-proven; defined vs implemented; T4/T5 defined) |

### Corrections NOT Applied

- SB-0 original verdict (`AUDIT_COMPLETE_WITH_BLOCKERS`) — unchanged; the blockers were real even if misdescribed
- Section numbering — unchanged to preserve cross-references
- No production code, tests, migrations, or other docs modified

### Safety Confirmations (SB-0.1)

- No live RPC calls
- No DB mutation
- No code or test changes
- No memory generation or retrieval
- No paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL
- No AGENTS.md modifications
- A3 remains locked
- V2-3 remains paused
- T3 live proof remains paused
- Staged/native 15m blocker: PARTIAL - DEFERRED, NOT RESOLVED

```text
SB_0_1_VERDICT: AUDIT_CORRECTION_PASS
CORRECTIONS_APPLIED: 14
PRODUCTION_CODE_CHANGES: NONE
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
SOURCE_STACK_ADOPTION: NONE
A3_STATUS: LOCKED
V2_3_STATUS: PAUSED
T3_LIVE_PROOF: PAUSED
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
```
