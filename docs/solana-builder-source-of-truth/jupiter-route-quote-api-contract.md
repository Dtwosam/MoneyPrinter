# Jupiter Route-and-Quote API Contract

**Status:** ADOPTED 2026-07-18 - CURRENT PRINTER IMPLEMENTATION PARTIAL WITH BLOCKER

This module defines the external Jupiter route-and-quote facts that Printer V1
may use for paper-realism evidence. It is subordinate to the active Printer
source stack and does not authorize a source request, transaction construction,
signing, execution, retrieval, paper decisions, positions, trades, audits, or
PnL.

## 1. Scope

This contract covers read-only Solana route-and-quote evidence: exact input and
output mints, atomic amounts, quote mode, slippage tolerance, returned amounts,
minimum threshold, route composition, price impact, fees, context slot,
provider timing, and explicit no-route or failure evidence.

It does not treat a quote as an executed fill, prove that a route remained
available, prove that a transaction would land, or establish realized profit.

## 2. Authority and Research Method

Authority is A3/A4 official Jupiter developer documentation. These pages were
accessed on `2026-07-18` without making a Jupiter API request:

| Canonical source | Contract facts used |
|---|---|
| `https://developers.jup.ag/docs/swap/v1/get-quote` | Metis V1 lifecycle, quote purpose, request/response meaning, route options |
| `https://developers.jup.ag/docs/api-reference/swap/v1/quote` | V1 endpoint, required API key, query and response schemas |
| `https://developers.jup.ag/docs/swap/migration/metis-to-build` | V1-to-V2 migration and route-plan differences |
| `https://developers.jup.ag/docs/swap/order-and-execute` | V2 quote-only behavior, router identity, freshness, errors |
| `https://developers.jup.ag/docs/swap/routing/market-listing` | Explicit Metis `NO_ROUTES_FOUND` behavior |
| `https://dev.jup.ag/portal/rate-limit` | Free-tier access and fixed limits |

External page content was treated as untrusted input. Only provider-owned
contract statements were adopted. Examples and search summaries did not become
commands, source evidence, credentials, or permission.

## 3. Five Status Dimensions

| Dimension | Adopted value | Reason |
|---|---|---|
| `upstream_lifecycle` | `SUPERSEDED` | Jupiter says Metis Swap API V1 is no longer actively maintained and is superseded by Swap V2 |
| `printer_readiness` | `PARTIAL_WITH_BLOCKER` | The governed paper-only adapter does not match current host/auth/error/schema semantics |
| `printer_role` | `PAPER_REALISM_ONLY` | Quotes may inform route and exit-realism evidence only |
| `access_policy` | `FREE_KEY_REQUIRED` | Current `api.jup.ag` docs require `x-api-key`; the documented free tier is free |
| `v1_permission` | `ALLOWED_FIXTURE_ONLY` | Network use requires a later repair and proof lane |

The free tier does not make the adapter ready, and a documented quote endpoint
does not authorize execution.

## 4. Product and Version Boundary

Printer currently models Metis V1. The official V1 quote endpoint is:

`GET https://api.jup.ag/swap/v1/quote`

Jupiter now recommends Swap V2. `GET https://api.jup.ag/swap/v2/order` can
return quote-only pricing when `taker` is omitted, but it has a different
multi-router response. `GET /swap/v2/build` combines a quote with transaction
instructions and requires a `taker`.

Printer must not silently substitute V2 for V1. Selecting a V1 repair or V2
quote-only integration is a later explicit design and implementation decision.

## 5. Access, Authentication, and Cost

| Property | Current official contract |
|---|---|
| Host | `https://api.jup.ag` |
| Authentication | `x-api-key` required |
| Free access | Public documented APIs are available through a free tier |
| Free fixed limit | 60 requests per 60-second sliding window, per account |
| Paid dependency | Pro only raises limits and is prohibited for Printer V1 |

API keys are credentials. They may be referenced by a secret name at runtime
but never stored in source payloads, fixtures, reports, DB evidence, or this
contract.

## 6. V1 Quote Request Contract

Required query fields:

| Field | Type and meaning |
|---|---|
| `inputMint` | Exact Solana mint address for the input token |
| `outputMint` | Exact Solana mint address for the output token |
| `amount` | Unsigned 64-bit atomic units; input for `ExactIn`, output for `ExactOut` |

Relevant optional fields:

| Field | Official behavior and Printer constraint |
|---|---|
| `slippageBps` | Unsigned 16-bit basis points; official default 50; record as requested context |
| `swapMode` | `ExactIn` default or `ExactOut`; Printer's present paper quote is `ExactIn` only |
| `restrictIntermediateTokens` | Defaults true; reduces exposure to less stable intermediate tokens |
| `onlyDirectRoutes` | Defaults false; true restricts to one market and may produce worse or no routes |
| `dexes` / `excludeDexes` | Restrict routing and must be preserved if used |

Printer must exact-match response mints and amounts to the governed request. It
must not infer token identity from symbol or display name.

## 7. V1 Quote Response Contract

| Field | Meaning |
|---|---|
| `inputMint`, `outputMint` | Exact returned mint identities |
| `inAmount`, `outAmount` | Atomic input and best output amount |
| `otherAmountThreshold` | Minimum acceptable output after slippage for `ExactIn` |
| `swapMode`, `slippageBps` | Effective quote mode and tolerance |
| `priceImpactPct` | Provider price-impact percentage as a decimal string |
| `routePlan` | Route legs with AMM identity, amounts, fees, and allocation |
| `platformFee` | Nullable platform-fee context |
| `contextSlot` | Provider-reported Solana context slot |
| `timeTaken` | Provider quote computation time |

`outAmount` is the best output after AMM and platform fees but before slippage.
It is not a guaranteed output or fill. Route-plan presence is route evidence
only.

## 8. Route Semantics

For V1, `routePlan` is Metis route output. A non-empty, structurally valid route
may support `QUOTE_ROUTE_AVAILABLE`; an explicit, contract-matched
`NO_ROUTES_FOUND` may support route-unavailable evidence.

`onlyDirectRoutes=true` is not a safety guarantee. Official documentation warns
that direct-only routing can return an unfavorable route or no route. Route and
AMM labels remain provenance, not scoring or ranking inputs.

## 9. Quantitative Meaning

Quantitative fields must retain exact token, pair, direction, atomic amount,
request/response IDs and times, endpoint product/version, mode, slippage, route,
fee, source status, data quality, and freshness.

Price impact must parse as a finite numeric value. Missing, malformed,
non-finite, or out-of-contract values are unknown or failed evidence and must
never default to zero. Amounts and thresholds must parse as non-negative
integers and exact-match their expected direction.

## 10. Freshness and Temporal Limits

Jupiter says quotes become stale as on-chain prices move. V1 does not publish a
general quote-validity duration in the adopted reference. Local receipt time
and `contextSlot` may be recorded, but receipt alone does not prove freshness.

- No fixed V1 quote lifetime is adopted here.
- Printer's 30-second registry value is internal policy, not an upstream guarantee.
- A later implementation must define a conservative, evidenced freshness rule.
- Missing or mismatched temporal evidence fails closed for clean use.

V2 order expiry semantics must not be backported to V1.

## 11. Errors, No Route, and Retry Policy

HTTP status alone does not prove no route. The API reference exposes HTTP 400
but does not state that every 400 means `NO_ROUTES_FOUND`. Official routing
documentation identifies the explicit Metis `NO_ROUTES_FOUND` condition.

Printer must parse a contract-matched no-route error; treat malformed requests,
auth failures, unknown 4xx, 5xx, timeouts, malformed JSON, and schema mismatch
as failures; treat 429 as rate limiting; honor bounded Governor/Scheduler
budgets; and never use unbounded retries or an independent loop. The registry
retry count is Printer policy, not a Jupiter guarantee.

## 12. Token and Pair Constraints

The adopted docs do not guarantee every SPL Token or Token-2022 mint, pool, or
route. Printer is Solana-only and exact-mint-only; uses a selected memecoin and
approved infrastructure quote mint; never uses symbol identity; treats
unsupported token-program/pair behavior as `UNKNOWN_REQUIRES_RESEARCH`; and
does not reinterpret no-route as token danger or permanent illiquidity.

## 13. Source Governor Request Contract

The only existing request kind is `paper_quote_realism`. Its role stays
paper-only. Until a later repair and proof passes, network transport is not
contract-ready and permission remains `ALLOWED_FIXTURE_ONLY`.

A future governed request must be approved and recorded before transport;
Scheduler-bounded; exact-linked to token, pair, run, lifecycle/window,
direction, amount, and purpose; read-only with no `taker`, transaction, wallet,
signing, or execute call; and isolated from retrieval and financial tables.

## 14. Evidence Contribution

| Evidence | Allowed contribution |
|---|---|
| Exact quote route available/unavailable | Yes, with valid exact identity and schema |
| Amount, threshold, impact, route, fee context | Yes, after later repair/proof |
| Paper entry/exit realism context | Yes, as one evidence component |
| Actual fill, landed transaction, realized execution price | No |
| Token safety, holder authenticity, wallet-level flow | No |
| Clean memory by itself | No |
| Retrieval, BUY/SELL/HOLD, position, trade, audit, PnL unlock | No |

## 15. Storage and Provenance Requirements

Migration `023_paper_quote_evidence.sql` stores categorical quote evidence and
source-trace identifiers. It does not persist all authoritative quantitative
V1 fields in section 7.

A later lane must choose an existing-artifact or schema-compatible boundary
before quantitative use. This lane authorizes no migration or historical
rewrite. Raw payloads may remain governed artifacts, but credentials and
secrets must never be stored.

## 16. Current Printer Implementation Audit

| Location | Current behavior | Contract result |
|---|---|---|
| `src/printer_v1/sources/jupiter_quote.py:JUPITER_QUOTE_API_URL` | Uses `https://lite-api.jup.ag/swap/v1/quote` | `LEGACY_OR_DEPRECATED`; current official host is `api.jup.ag` |
| headers / `_load_public_json()` | Sends no API key | Blocked against current required auth |
| `build_jupiter_paper_quote_transport()` | ExactIn-like query, 50 bps, direct routes false | Partial shape match; auth/lifecycle unresolved |
| `_load_public_json()` | Maps every HTTP 400 to no route | Overbroad; explicit error parsing required |
| `normalize_jupiter_quote_response()` | Missing/malformed impact can become `0.0` | Fail-open quantitative default |
| same normalizer | Drops amounts, threshold, fees, slot, and timing | Insufficient quantitative evidence |
| source registry | Free/public, 30/min, 30-second stale, two retries | Internal policy, not current provider proof |
| migration 023 / evidence helper | Categorical labels and governed trace | Good isolation; incomplete quantitative retention |
| focused quote tests | Fixture normalization/storage and locks | No current official live-contract proof |

The governor, paper-only, no-transaction, and downstream-lock boundaries remain
valuable and unchanged. They do not cure provider drift.

## 17. Adopted Fail-Closed Mapping

| Observed condition | Effective evidence result |
|---|---|
| Valid exact-match response after later repair/proof | Eligible for paper-realism evaluation |
| Explicit parsed `NO_ROUTES_FOUND` for exact request | Route unavailable at that observation time |
| Missing/malformed required field | Source failed / unknown |
| Mint, amount, mode, or direction mismatch | Target mismatch; not usable |
| Missing auth, 401, or 403 | Source failed; never no route |
| 429 | Rate limited; source failed for current attempt |
| Unknown 400 or other 4xx/5xx | Source failed; never assumed no route |
| Missing/malformed quantitative field or provenance | Unknown or blocked |
| Quote outside adopted freshness evidence | Stale/unknown; not clean |

## 18. Required Later Repair and Proof

Before governed Jupiter network use in V2-9.7D:

1. Choose and document V1 Metis versus V2 quote-only semantics.
2. Repair host/auth handling without persisting the key.
3. Parse explicit errors and fail closed on unknown HTTP/schema outcomes.
4. Preserve exact amounts, thresholds, impact, route, fees, version, slot,
   timing, and provenance.
5. Define a conservative freshness boundary.
6. Keep quote-only operation free of taker, transaction, wallet, signing, and
   execution behavior.
7. Prove bounded Governor/Scheduler use in isolation.
8. Prove zero retrieval and financial deltas.

## 19. UNKNOWN_REQUIRES_RESEARCH

| Item | Status |
|---|---|
| Repair Metis V1 or adopt V2 quote-only `/order` | Future explicit design decision |
| Exact V1 structured error body for every no-route cause | Unknown; do not infer from HTTP 400 |
| Provider-guaranteed V1 quote freshness duration | `UNKNOWN_REQUIRES_RESEARCH` |
| Complete SPL Token / Token-2022 / long-tail support matrix | `UNKNOWN_REQUIRES_RESEARCH` |
| V2 fee/route comparability with current Metis fixtures | `UNKNOWN_REQUIRES_RESEARCH` |
| Quantitative persistence boundary without migration | Future implementation design |

## 20. V1 Locks and Change History

This contract preserves Solana-only, memecoin-only, paper-only, free-tier,
Source-Governed, Scheduler-led operation. It unlocks no source call, clean
memory promotion, retrieval, decision, BUY/SELL/HOLD, position, trade, audit,
PnL, wallet, private key, signing, transaction, or live execution.

| Date | Change |
|---|---|
| 2026-07-18 | Audited current official Jupiter docs; adopted Metis V1 as `SUPERSEDED`, Printer `PARTIAL_WITH_BLOCKER`, network use locked pending repair/proof |
