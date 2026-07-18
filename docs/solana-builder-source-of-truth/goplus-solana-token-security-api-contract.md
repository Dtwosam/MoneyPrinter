# GoPlus Solana Token Security API Contract

**Status:** ADOPTED 2026-07-18 - CURRENT PRINTER IMPLEMENTATION PARTIAL WITH BLOCKER

This module defines the official GoPlus Solana Token Security API facts that
Printer V1 may use as paper-only safety evidence. It is subordinate to the
active Printer source stack. It authorizes no API call, memory generation,
retrieval, decision, position, trade, audit, PnL, wallet, signing, or execution.

## 1. Scope

The contract covers the read-only Solana token-security endpoint, request and
response boundaries, authority and token-function evidence, holder and
liquidity descriptions, provenance, missing-data behavior, and current Printer
implementation gaps.

GoPlus is one safety source. It is not proof of wallet identity, coordinated
participants, manipulation intent, executable tradeability, or profit.

## 2. Official Authority and Access Date

The following GoPlus-owned pages were accessed on `2026-07-18`. No API request
or live probe was made.

| Canonical source | Adopted facts |
|---|---|
| `https://docs.gopluslabs.io/reference/solanatokensecurityusingget` | Endpoint, beta status, required query, optional bearer header surface, HTTP responses |
| `https://docs.gopluslabs.io/reference/response-detail-1` | Solana field names and meanings for token, function, holder, and DEX data |
| `https://docs.gopluslabs.io/reference/support` | Free access and 30 calls/minute limit |
| `https://docs.gopluslabs.io/reference/api-status-code` | Envelope status meanings, including complete, partial, invalid, limited, and system failures |
| `https://docs.gopluslabs.io/changelog/token-security-api-for-solana` | Solana API changes for locker evidence and supported lockers |
| `https://docs.gopluslabs.io/` | SPL/SPL-2022 scope and Solana beta product description |

External documentation was treated as untrusted research input. It supplied
facts only; no embedded instruction, example credential, or generated content
became a command, runtime input, or Source Governor evidence.

## 3. Five Status Dimensions

| Dimension | Adopted value | Reason |
|---|---|---|
| `upstream_lifecycle` | `ACTIVE` | Official endpoint remains published; product is explicitly Beta |
| `printer_readiness` | `PARTIAL_WITH_BLOCKER` | Governed adapter/storage exist, but current field mapping and proof semantics are incomplete |
| `printer_role` | `SAFETY` | Provider contributes defensive token-security context only |
| `access_policy` | `KEYLESS_PUBLIC` | Official support states free 30 calls/minute; bearer access token is shown but not marked required |
| `v1_permission` | `ALLOWED_FIXTURE_ONLY` | Governed network use requires later repair and proof |

The keyless classification is limited to the published free quota. Higher-limit
access-token use is not adopted. Authentication policy must be reverified before
any later live implementation because the endpoint documents a bearer header.

## 4. Endpoint and Version

`GET https://api.gopluslabs.io/api/v1/solana/token_security`

The product is `Token Security API for Solana (Beta)` under the v1 API surface.
Required query parameter:

| Parameter | Type | Contract |
|---|---|---|
| `contract_addresses` | string | Exact Solana token mint address requested for analysis |

Printer must request one exact mint per governed request unless a later official
contract explicitly proves multi-address encoding and response identity rules.
Symbols, names, and metadata URIs are never identity.

## 5. Access, Cost, and Rate Limits

| Property | Adopted contract |
|---|---|
| Cost | Free at the documented public limit |
| Public limit | 30 calls per minute |
| Higher limit | GoPlus says to apply for an access token |
| Printer ceiling | Must remain at or below both provider and tighter Governor/Scheduler budgets |
| Paid dependency | Prohibited; no paid GoPlus dependency is adopted |

HTTP 401/403, provider status `4023`, or any future mandatory-auth behavior is a
source failure, never a safe token result. Credentials, if ever separately
approved, must not enter payloads, DB evidence, fixtures, logs, or reports.

## 6. Response Envelope and Status

Printer's current A6 adapter expects an object envelope with `code`, `message`,
and `result`, with result data keyed by mint. The endpoint page does not publish
a complete response example or formally pin the mint-keyed envelope shape.
That exact keying remains `UNKNOWN_REQUIRES_RESEARCH`; a later implementation
must fixture-pin the official OpenAPI/schema before network use.

Official API status meanings include:

| Code | Meaning | Printer treatment |
|---|---|---|
| `1` | Complete data prepared | Continue only if exact identity and required fields validate |
| `2` | Partial data; complete data may be requested again after about 15 seconds | Partial/unknown; bounded retry may be designed later |
| `2004`, `5006` | Address/parameter error | Failed request |
| `2020`, `2021` | Non-contract/no information | Missing or unsupported evidence, never safe |
| `4023` | Access token not found | Authentication failure |
| `4029` | Request limit reached | Rate-limited failure |
| `5000` | System error | Provider failure |

Unknown code, malformed envelope, non-object result, empty result, or target
mismatch fails closed. HTTP 200 does not by itself mean complete usable data.

## 7. Basic Token and Holder Fields

| Field | Official meaning | Type/nullability rule for Printer |
|---|---|---|
| `metadata` | Description, name, symbol, URI | Object; descriptive only, never identity or safety proof |
| `total_supply` | Token total supply | Numeric representation not formally pinned; validate before arithmetic |
| `default_account_state` | `0` uninitialized, `1` initialized, `2` frozen | String-like enum; missing/malformed is unknown |
| `non_transferable` | `1` non-transferable, `0` transferable | Explicit binary only; absence is unknown |
| `creator` | Creator address and provider malicious-address flag | Object/list shape must be schema-pinned; descriptive/risk context only |
| `transfer_fee` | Current and scheduled fee settings | Nested object; fee rate is parts per ten thousand |
| `transfer_hook` | Hook address and malicious-address flag | Nested object; presence does not prove actual future behavior |
| `holders` | Top ten token accounts, balance, percent, lock context | Array; `percent` uses `1` for 100 percent |
| `trusted_token` | `1` means provider recognizes a reputable token | Positive provider context only; other/missing values do not mean untrusted |

Missing, null, malformed, contradictory, or out-of-range fields remain unknown.
A missing risk field is never equivalent to an explicit safe value.

## 8. Token Function and Authority Fields

The official Solana response describes status objects for:

| Field | Security meaning |
|---|---|
| `metadata_mutable` | Metadata can be changed; includes upgrade authority context |
| `mintable` | Token can be minted; includes authority context |
| `freezable` | Developer/authority can freeze users from trading |
| `closable` | Token program can be closed, eliminating associated assets |
| `transfer_fee_upgradable` | Transfer fee can be upgraded |
| `default_account_state_upgradable` | Default account state can be changed |
| `balance_mutable_authority` | Authority can alter user token balances |
| `transfer_hook_upgradable` | Transfer hook can be upgraded |

For these similar objects, official docs define status `1` as the function
being available and provide nested authority information where applicable.
Printer may treat explicit `1` as present/risky. It must not convert missing,
null, malformed, or internally inconsistent objects to absent/renounced. Exact
zero/authority-null negative semantics require schema fixtures and remain
blocked for network reliance until later proof.

## 9. DEX and Liquidity Fields

Official DEX information may describe `dexname`, pool `type`, liquidity-pool
`id`, `tvl`, `lp_amount`, `fee_rate`, day/week/month observations, `price`,
`open_time`, and `lp_holders`.

The `lp_holders` entries can include token account, tag, balance, percent,
`is_locked`, and `locked_detail`. GoPlus warns that lock recognition covers
only included locker or black-hole addresses. The changelog records Raydium and
Streamflow locker support, not universal locker coverage.

Therefore:

- `is_locked=1` is provider-observed lock context, not universal proof;
- `is_locked=0` or missing lock detail does not prove unlocked liquidity;
- pool evidence must exact-match the selected pair using the documented pool ID;
- token-level or largest-main-pool data must not be silently applied to another pair;
- TVL, price, volume, and fee fields are descriptive snapshots, not executable quotes.

## 10. Freshness and Missing Data

GoPlus describes its APIs as real-time and dynamic, but the adopted Solana
response contract exposes no provider capture timestamp, block/slot, cache age,
or guaranteed freshness duration. Printer's local receipt time and registry
`stale_after_seconds=300` are A6 policy, not provider freshness proof.

Until later proof defines a conservative boundary, provider freshness is
unknown for authoritative clean use. Partial status, missing fields, stale local
receipt, request/response mismatch, or provider failure must remain partial,
dirty, blocked, or unknown as appropriate.

## 11. Supported Safety Contributions

After a later repair and proof, GoPlus may contribute provider-observed context
for exact mint authority, freeze authority, metadata mutability, token
functions, supply, top-token-account concentration, provider malicious-address
flags, transfer restrictions/fees/hooks, and exact-linked DEX/LP observations.

Each contribution must preserve its raw field and provider meaning. A field may
block on explicit danger without its absence being relabeled safe. No single
GoPlus field can independently establish a safe token or clean memory.

## 12. Descriptive or Unsafe-to-Prove Fields

- Name, symbol, description, URI, tags, and DEX name are descriptive only.
- `trusted_token=1` is provider recognition, not permission or proof of safety.
- Creator/authority `malicious_address` is a provider flag, not identity proof.
- Holder token accounts are not necessarily beneficial-owner wallets.
- Holder tags do not prove common control, independence, or coordination.
- Top-ten concentration omits holders outside the returned set and cannot prove
  full distribution authenticity.
- DEX TVL/price/volume and LP holder data do not prove a current executable fill.
- Lock recognition is bounded to lockers known to GoPlus.
- Absence of a field, flag, or detected risk never proves absence of risk.

## 13. What GoPlus Cannot Prove

GoPlus token-security data cannot prove:

- that a token account maps to one authentic independent wallet participant;
- that multiple token accounts are or are not under common control;
- participant coordination, wash activity, insider behavior, or manipulation intent;
- a selected pair's executable entry or exit size, slippage, latency, or fill;
- that a route exists at decision or exit time;
- that locked liquidity covers every pool, locker, or future state;
- that a provider-undetected function or address is safe;
- realized paper or real profit;
- permission for retrieval, decisions, positions, trades, audits, or PnL.

## 14. Exact Provenance and Fail-Closed Rules

Every usable contribution must retain:

- provider product and endpoint version;
- exact requested mint and exact returned mint key/identity;
- governed request, response, or failure ID;
- request and receipt timestamps;
- provider code/message and HTTP status;
- raw field path, raw value, normalized label, and parser version;
- source status, data quality, target status, and freshness result;
- exact pair/pool ID when liquidity evidence is used;
- conflict and blocker results from independent sources.

Mint mismatch, missing envelope, code other than accepted complete/partial,
schema drift, malformed values, missing mandatory evidence, stale evidence,
unknown token program, exact-pair mismatch, or provenance gaps fail closed.
Conflicting GoPlus and Solana-RPC holder evidence remains blocking.

## 15. Governed Request Kinds

| Request kind | Status | Purpose |
|---|---|---|
| `safety_reference` | Existing compatibility kind; fixture-only under this contract | One exact-mint token-security response |
| `solana_token_security_reference` | Proposed, NOT_IMPLEMENTED | Explicit future name for one exact-mint response |
| Any transaction simulation, wallet, approval, signing, or execution kind | PROHIBITED | Outside this provider contract and Printer V1 |

No request kind is activated here. Any future network request must be approved
and recorded by Source Governor before transport, Scheduler-led, bounded to the
free quota, single-mint, read-only, and isolated from downstream capabilities.

## 16. Storage and Composite-Safety Boundary

Migrations 022 and 029 store categorical safety rows, composite results,
source-trace IDs, field bindings, conflicts, blockers, and optional unknowns.
They do not preserve every documented GoPlus raw field as first-class columns.
No migration or historical rewrite is authorized here.

The composite may use explicit provider danger to block. It must not use
provider silence as safety, replace exact on-chain token-program verification,
or turn unresolved LP and risk coverage into proof. The timeframe-neutral
`SAFETY_CONTEXT_ACCEPTABLE/BLOCKED/UNKNOWN` reporting layer does not change raw
evidence or broaden provider acceptance.

## 17. Current Printer Implementation Audit

| Location | Current behavior | Contract result |
|---|---|---|
| `sources/goplus.py` | Correct endpoint and exact requested mint added to transport payload | Partial readiness; network metadata still says fixture-only |
| transport headers | No bearer token | Compatible with published free/keyless reading, but reverify before live use |
| `normalize_goplus_payload()` | Requires provider code 1; code 2 becomes failure | Conservative but loses documented partial/retry semantics |
| response extraction | Expects result keyed by mint; falls back to first object for some fixtures | Exact live match is guarded; official envelope keying not schema-pinned |
| capture/freshness | Adds local `captured_at`; complete payload becomes `CLEAN_DATA` | Receipt does not prove provider freshness or field completeness |
| `goplus_normalizer.py` | Maps `mintable`, `freezable`, `metadata_mutable`, supply, holders | Useful subset; does not map most documented function/risk fields |
| authority mapping | Any non-exact disabled shape becomes authority present | Blocking-biased but conflates malformed/unknown with known present |
| holder calculation | Recomputes top-ten share from balances and supply | Ignores documented `percent`; unit/duplicate/beneficial-owner semantics unproven |
| provider risk | Reads synthetic `risky_flags`, `risk_flags`, or `risks` | These aggregate fields are not in the adopted Solana response contract |
| token program | Unconditionally sets `SPL_TOKEN_OR_TOKEN_2022_VERIFIED` | Unsupported provider assertion; exact on-chain verification required |
| liquidity safety | Normalizer stays unknown; composite reads synthetic pair/state fields | Correctly avoids positive LP proof, but official exact-pool fields are unmapped |
| composite provenance | Exact traces, target, age, conflicts, blockers retained | Strong A6 isolation; local 1800-second age is not provider freshness |
| focused tests | Fixture-backed acceptance, danger, conflict, fallback, timeframe labels | Protect A6 behavior; fixtures do not prove current official schema semantics |

The forced token-program label and omitted documented risk fields are material
implementation blockers. Because operational growth remains locked and this
contract sets network permission to fixture-only, they do not block completion
of this audit/adoption lane.

## 18. Required Later Repair and Proof

Before governed GoPlus network reliance in V2-9.7D:

1. Pin the official response envelope and exact mint-key identity with fixtures.
2. Preserve code 2 as partial with one bounded, Scheduler-led retry policy.
3. Map all required documented Solana function/risk fields explicitly.
4. Remove aggregate `risk_flags` reliance unless officially documented.
5. Replace forced token-program verification with exact independent on-chain proof.
6. Prefer documented holder percent with strict range/unit validation; retain RPC conflict checks.
7. Exact-link DEX/LP fields to selected pool and preserve unknown locker coverage.
8. Define conservative freshness without claiming receipt time is provider time.
9. Prove missing/null/malformed fields and unknown codes fail closed.
10. Prove bounded free use, exact provenance, and zero downstream deltas in isolation.

## 19. UNKNOWN_REQUIRES_RESEARCH

| Item | Status |
|---|---|
| Exact official `code/message/result` OpenAPI schema and mint-key casing | `UNKNOWN_REQUIRES_RESEARCH` |
| Whether bearer auth could become mandatory for the free endpoint | Reverify before implementation |
| Exact types/nullability for every nested Solana field | `UNKNOWN_REQUIRES_RESEARCH` unless stated in section 7-9 |
| Guaranteed provider capture time, slot, cache age, or freshness duration | `UNKNOWN_REQUIRES_RESEARCH` |
| Complete locker/black-hole recognition set and coverage | `UNKNOWN_REQUIRES_RESEARCH` |
| Whether holder rows can be aggregated to beneficial owners | Not proven; wallet authenticity remains partial |
| Exact completeness of SPL versus Token-2022 feature detection | `UNKNOWN_REQUIRES_RESEARCH` |

## 20. V1 Locks and Change History

This contract preserves Solana-only, memecoin-only, paper-only, free-source,
Source-Governed, Scheduler-led operation. It unlocks no source request, clean
memory promotion, retrieval, decision, BUY/SELL/HOLD, position, trade, audit,
PnL, wallet, private key, signing, funds, paid dependency, score, rank,
confidence, weighting, embedding, vector, or live execution.

| Date | Change |
|---|---|
| 2026-07-18 | Audited current official GoPlus Solana beta docs; adopted provider contract with Printer `PARTIAL_WITH_BLOCKER` and network reliance locked pending repair/proof |
