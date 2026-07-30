# Solana Core RPC Reference

**Status:** SB-2 CORE MODULE. V2-9.7D.1D PUBLIC-RPC CONTRACT ADOPTED,
DOCUMENTATION ONLY. NETWORK USE REMAINS GOVERNED AND LOCKED TO EXPLICIT LANES.

## Restored Factory Compatibility Reset (2026-07-30)

The current adopted public fallback is
`https://api.mainnet.solana.com`. The legacy
`api.mainnet-beta.solana.com` hostname is not an adopted official runtime
literal. `PRINTER_SOLANA_RPC_URL`, when supplied by the operator, is preferred
after absolute-HTTPS, hostname, no-userinfo, no-fragment and non-placeholder
validation. Reports expose only a redacted endpoint identity. The public
endpoint remains a bounded fallback, not a production-availability promise.

Restored migration reads are one finalized `getSignaturesForAddress` page,
bounded finalized `getTransaction` calls, and finalized account reads for the
exact PumpSwap join. They have no cursor, backfill or recovery authority.

## 1. Purpose

This module defines the read-only Solana JSON-RPC evidence contract available
to Printer V1. It covers only `getAccountInfo`, `getSignaturesForAddress`,
`getTransaction`, `getBlockTime`, `getTokenLargestAccounts`, and
`getTokenSupply`.

RPC is evidence transport, never proof of every fact inferred from a response.
It cannot authorize transaction construction, signing, submission, wallet use,
retrieval, decisions, positions, trades, audits, or PnL.

## 2. Official Upstream Authorities

Official Solana documentation was accessed on `2026-07-18`.

| Tier | Resource | Canonical URL |
|---|---|---|
| A3 | Clusters and public RPC endpoints | `https://solana.com/docs/references/clusters` |
| A3 | RPC overview and commitment | `https://solana.com/docs/rpc` |
| A3 | HTTP methods index | `https://solana.com/docs/rpc/http` |
| A3 | `getAccountInfo` | `https://solana.com/docs/rpc/http/getaccountinfo` |
| A3 | `getSignaturesForAddress` | `https://solana.com/docs/rpc/http/getsignaturesforaddress` |
| A3 | `getTransaction` | `https://solana.com/docs/rpc/http/gettransaction` |
| A3 | `getBlockTime` | `https://solana.com/docs/rpc/http/getblocktime` |
| A3 | `getTokenLargestAccounts` | `https://solana.com/docs/rpc/http/gettokenlargestaccounts` |
| A3 | `getTokenSupply` | `https://solana.com/docs/rpc/http/gettokensupply` |
| A3 | `minimumLedgerSlot` | `https://solana.com/docs/rpc/http/minimumledgerslot` |
| A3 | Shared JSON structures | `https://solana.com/docs/rpc/json-structures` |

Hosted documentation has no pinned commit or protocol version. Public limits
are explicitly subject to change and must be rechecked before implementation or
activation. No endpoint was probed in this audit.

## 3. Version, Transport, Access, and Cost

- Protocol: JSON-RPC 2.0 over HTTPS POST.
- Solana support: Mainnet is the only Printer V1 chain/cluster in scope.
- Authentication: no API key is documented for the official public endpoints.
- Access: shared, keyless public infrastructure with rate limiting and possible
  blocking.
- Cost: no per-request charge is documented for the public endpoints. This is
  not an SLA, production guarantee, or permission for unbounded use.
- Printer remains free/public-source only. Dedicated, private, or paid RPC is
  outside this adopted contract.
- Public endpoints are not intended for production applications, and Solana
  warns that limits or access can change without notice.

## 4. Authority and Permission

| Dimension | Adopted value |
|---|---|
| `upstream_lifecycle` | `ACTIVE_BUT_CHANGEABLE` |
| `printer_readiness` | `PARTIAL_WITH_IMPLEMENTATION_GAPS` |
| `printer_role` | `TOKEN_AGE` and `SAFETY_CONTEXT` read-only evidence |
| `access_policy` | `KEYLESS_PUBLIC_SHARED` |
| `v1_permission` | `ALLOWED_GOVERNED_ONLY` for already-approved read-only paths; no new activation |

This adoption documents a provider boundary. It does not create a source
request, implementation lane, operational command, or campaign permission.

## 5. Public Endpoints and Naming Conflict

The current English official clusters and RPC pages identify:

- Mainnet: `https://api.mainnet.solana.com`
- Devnet: `https://api.devnet.solana.com`
- Testnet: `https://api.testnet.solana.com`

Printer V1 is Mainnet-only. Current Printer adapters use
`https://api.mainnet-beta.solana.com`. Older or localized official Solana pages
also expose the `mainnet-beta` name, while the current English primary pages use
`mainnet`.

No official statement reviewed in this lane guarantees that the two hostnames
are permanent aliases or behaviorally identical. Because probes were forbidden:

- canonical current documentation name: `api.mainnet.solana.com`;
- current implementation name: `api.mainnet-beta.solana.com`;
- equivalence and long-term alias policy: `UNKNOWN_REQUIRES_RESEARCH`;
- Printer must not silently rotate between them or call one a verified backup.

The holder adapter's `https://solana-rpc.publicnode.com` fallback is a
third-party endpoint, not an official Solana public endpoint. Its authentication,
cost, limits, retention, and service contract are
`UNKNOWN_REQUIRES_RESEARCH` under this module.

## 6. Official Shared-Endpoint Limits

The official Mainnet public endpoint page currently publishes:

| Limit | Published ceiling |
|---|---:|
| Total requests | 100 per 10 seconds per IP |
| Requests to one RPC method | 40 per 10 seconds per IP |
| Concurrent connections | 40 per IP |
| Connection attempts | 40 per 10 seconds per IP |
| Data transfer | 100 MB per 30 seconds per IP |

These are shared upstream ceilings, not quotas promised to Printer. They may
change without notice, and high-traffic clients may be blocked. Printer must
remain below both upstream ceilings and its stricter Source Governor and Central
Scheduler budgets.

## 7. Commitment and Finality

- `processed`: newest observed block state; rollback remains possible.
- `confirmed`: a supermajority has voted on the block.
- `finalized`: the strongest documented commitment level.
- Solana says omitted commitment is typically `finalized`; typically is not
  an immutable per-endpoint guarantee.

Printer evidence must carry an explicit requested commitment and the response
context where supplied. The token-age adapter explicitly requests `finalized`.
The holder adapter currently omits commitment for `getTokenLargestAccounts` and
`getTokenSupply`; this is an implementation gap. A default must not be promoted
into proven finality merely because current docs describe it as typical.

`minContextSlot`, where supported, is a minimum evaluation slot, not a request
to wait for that slot. It is not implemented in the inspected adapters.

## 8. Method Contracts

### 8.1 `getAccountInfo`

- Input: exact account public key plus optional encoding, commitment, and
  `minContextSlot`.
- Output: context plus account value, or `null` when the account does not exist
  at the requested commitment.
- Supported evidence: exact mint-account existence, program owner, data, size,
  lamports, executable state, and response context.
- Not proof of mint creation time, beneficial ownership, safety, or tradeability.
- Printer use: T3 mint validation with base64 data and explicit `finalized`.

### 8.2 `getSignaturesForAddress`

- Input: exact address plus optional `commitment`, `minContextSlot`, `limit`,
  `before`, and `until`.
- Output: confirmed transaction-signature records newest first.
- Record fields include `signature`, `slot`, nullable `err`, nullable `memo`,
  nullable `blockTime`, and `confirmationStatus`.
- `before` pages toward older records. Exact `until` inclusivity and a current
  official numeric maximum for `limit` are `UNKNOWN_REQUIRES_RESEARCH` in the
  reviewed primary page; Printer's `1000` value remains an implementation
  assumption until fixture- or source-pinned.
- An empty or bounded response is not proof that no earlier initialization
  exists. It may reflect request bounds or node retention.
- Printer use: locator only; never creation proof by itself.

### 8.3 `getTransaction`

- Input: exact signature plus optional encoding, commitment, and
  `maxSupportedTransactionVersion`.
- Output: transaction object or `null` when the transaction is not found or not
  confirmed at the requested commitment.
- `blockTime` and `meta` can be null.
- Printer uses `jsonParsed`, `finalized`, and
  `maxSupportedTransactionVersion: 0`.
- Supported T3 evidence requires a successful transaction, exact requested
  mint attribution, `initializeMint` or `initializeMint2`, and valid time.
- A located signature, parsed name, or transaction record alone is insufficient.

### 8.4 `getBlockTime`

- Input: exact slot.
- Output: estimated block-production Unix time derived from stake-weighted vote
  timestamps when available.
- Official documentation distinguishes available, unknown, and unavailable
  time states, but exact JSON null-versus-error mapping for every unavailable
  case is `UNKNOWN_REQUIRES_RESEARCH`.
- Printer accepts only a valid non-future integer time and otherwise fails T3
  closed.

### 8.5 `getTokenLargestAccounts`

- Input: exact SPL token mint plus optional commitment.
- Output: the 20 largest token accounts and token-amount fields.
- Supported evidence: concentration among returned token accounts relative to
  an exact supply observation.
- Not proof of 20 distinct wallets, beneficial owners, independent actors,
  participant coordination, or the entire holder population.

### 8.6 `getTokenSupply`

- Input: exact SPL token mint plus optional commitment.
- Output: current mint supply as raw amount, decimals, nullable `uiAmount`, and
  `uiAmountString`.
- Supported evidence: exact-mint supply at the observed context.
- Not proof of circulating supply, unlocked supply, executable liquidity, or
  economic value.

## 9. Null, Missing, Partial, and Pruned Data

| Condition | Printer treatment |
|---|---|
| `getAccountInfo.value = null` | Required account evidence missing; fail closed |
| Empty signature list | No usable history in returned coverage; never prove nonexistence |
| `getTransaction = null` | Transaction unavailable at requested context; fail closed |
| Transaction `meta = null` or `meta.err != null` | No valid initialization proof |
| Missing/null transaction `blockTime` | Use at most the approved fallback; otherwise fail closed |
| Unknown/unavailable `getBlockTime` | No time proof; fail closed |
| Missing/malformed token amount or supply | No concentration result; fail closed |
| JSON-RPC error object | Provider failure, never an evidence value |

`minimumLedgerSlot` proves that a node may delete older ledger data and that its
lowest retained slot can increase. The public service publishes no fixed history
retention window or archival guarantee. Therefore:

- exact public-node retention depth: `UNKNOWN_REQUIRES_RESEARCH`;
- empty history or null transaction does not prove historical nonexistence;
- Printer must preserve request bounds and returned coverage rather than label
  a bounded search complete.

## 10. Transport, Timeout, Rate-Limit, and Retry Behavior

- HTTP `403`: official docs describe the IP or site as blocked. Printer must
  stop that endpoint path and report the failure; it must not evade the block.
- HTTP `429`: upstream rate limit exceeded. Official docs require using the
  `Retry-After` response header to determine wait time.
- Other HTTP failures, timeout, malformed JSON, JSON-RPC error, null mandatory
  result, or identity mismatch remain failures, not empty evidence.
- No official numeric request-timeout or SLA is published. Printer's 10-second
  timeout is a local bounded budget, not an upstream promise.
- Retries must be finite, Scheduler-led, Source-Governed, separately accounted,
  and limited to explicitly classified transient failures.
- Retry must not change mint, pair, method, commitment, endpoint, or run identity.
- `Retry-After` must be bounded by the campaign/run deadline; if it cannot be
  honored safely, the request remains blocked/failed.
- Endpoint substitution is not a retry unless the alternate provider has its
  own adopted contract and provenance.

Current token-age behavior uses zero retries and no endpoint rotation. Current
holder redundancy permits one separately governed backup attempt only after a
small transient allowlist. The generic registry's `max_retries = 2` metadata is
not proof that adapters execute two safe retries.

## 11. Upstream Limits Versus Printer Budgets

| Boundary | Current Printer behavior | Relationship to upstream |
|---|---|---|
| Source registry | 30/min, stale 120s, retry-after 60s, max retries 2 | Stricter than 100/10s total but insufficient alone for method, connection, or bandwidth ceilings |
| T3 token-age total | Maximum 8 RPC operations per mint | Per-token ceiling; still requires global IP/method scheduling |
| T3 signature pages | Maximum 3 | Local coverage bound, not completeness |
| T3 transaction calls | Maximum 3 | Local coverage bound |
| T3 block-time calls | Maximum 1 | Local fallback bound |
| T3 timeout | 10 seconds per HTTP operation | Local timeout; no upstream SLA equivalent |
| Holder primary | Two RPC methods in one adapter call | One governed request consumes multiple upstream operations |
| Holder backup | At most one governed alternate attempt after classified transient failure | Third-party limits are outside official Solana limits |

The Source Governor currently counts governed source requests, while one such
request can fan out into multiple JSON-RPC operations. Central scheduling must
budget actual per-method operations, connections, bytes, and all active tokens,
not merely top-level source requests. No current code proves consolidated
IP-wide accounting.

## 12. Request-Kind Mapping

| Printer request kind | RPC methods | Current boundary |
|---|---|---|
| `mint_creation_time_reference` | `getAccountInfo`, bounded signatures and transactions, optional `getBlockTime` | Implemented T3 path; explicit finalized; zero retry |
| `holder_concentration_reference` | `getTokenLargestAccounts`, `getTokenSupply` | Implemented; implicit commitment must be repaired before operational reliance |
| `mint_account_reference` | Potential `getAccountInfo` | Registry name broader than inspected executable contract |
| `onchain_reference` | Unspecified generic read-only reference | Must not execute until exact method/schema/budget is adopted |
| `pool_reference` | Unspecified generic read-only reference | Must not execute until exact account/program contract is adopted |

No new governed request kind is adopted or implemented by V2-9.7D.1D.

## 13. Provenance and Identity Rules

Every accepted RPC observation must preserve, at minimum:

- source/provider identity and redacted hostname;
- exact request kind and RPC method;
- exact mint and, where applicable, exact pair/account/signature/slot;
- requested commitment and response context slot when returned;
- request ID, attempt ordinal, capture time, and bounded coverage counters;
- endpoint role (`primary` or separately approved `backup`);
- returned null/partial/error state without relabeling it as absence;
- parser/normalizer version and run linkage where required.

URLs, query strings, credentials, environment secrets, and raw sensitive
configuration must not be persisted. Host redaction does not erase provider
identity. A response for one mint, account, signature, slot, commitment, run, or
endpoint must never satisfy another identity.

## 14. Evidence Strength and Unsupported Proof

| Method/result | Maximum supported meaning |
|---|---|
| Account info | Exact account state at returned context |
| Signature history | Bounded newest-first locators for an address |
| Successful exact-mint initialization transaction plus time | T3 mint-creation evidence |
| Block time | Estimated production time for one slot |
| Largest token accounts plus supply | Token-account concentration context |
| Supply | Mint supply observation |

Public RPC cannot by itself prove:

- complete historical coverage or token history before node retention;
- token legitimacy, absence of risk, or future safety;
- beneficial wallet ownership, wallet authenticity, or independent participants;
- participant coordination, wash activity, manipulation intent, or causation;
- pool reserves, executable routes, slippage, fills, exit realism, or profit;
- off-chain identity, social claims, or provider-wide indexing completeness;
- retrieval fitness, decision quality, BUY/SELL/HOLD, position validity, or PnL.

Optional unknowns must remain unknown. No RPC field can become a score, ranking,
confidence, weight, retrieval unlock, or financial capability.

## 15. Current Implementation Gaps and Unsafe Assumptions

| Gap | Risk | Required later repair/proof |
|---|---|---|
| Mainnet hostname differs from current primary official docs | Silent alias/equivalence assumption | Pin one approved endpoint after official clarification or a separately approved bounded probe |
| Holder backup is third-party PublicNode | Official limits are inherited by another provider | Separate provider contract before reliance |
| Holder calls omit explicit commitment | Typical default can be reported as proven finality | Send explicit commitment and fixture-test context/provenance |
| Governor counts source requests, not underlying RPC operations | Multi-call adapters can exceed method/IP/bandwidth ceilings | Operation-level Scheduler budget and bounded proof |
| Registry says max retries 2 while T3 is zero-retry and holder has one conditional backup | Retry policy appears more permissive than reality | Path-specific retry contract and focused tests |
| HTTP 429 does not preserve `Retry-After` | Backoff cannot follow official signal | Parse, bound, account, and prove header behavior |
| T3 uses `limit = 1000` without a pinned primary-page maximum | Unsupported numeric assumption | Pin official schema/source or configure conservatively |
| Bounded signature pages can be called complete | Initialization can be outside returned coverage | Report bounds and incomplete coverage explicitly |
| Generic/manual fallback is broader than operational holder allowlist | Non-retryable failures may rotate provider | Reconcile to one fail-closed transient allowlist |
| No consolidated connection/byte accounting was found | Request count can still breach limits | Add operation/connection/byte design before activation |
| No fixed public history-retention guarantee exists | Null/empty can be read as nonexistence | Preserve retention uncertainty; never infer absence |

These gaps block provider implementation or operational reliance where stated.
They do not block documentation adoption because the contract remains
fail-closed and no new network path is activated.

## 16. Required Future Proof

Before operational public-RPC use expands beyond already approved historical
paths, the relevant implementation lane must prove with fixtures and isolated
harnesses:

1. exact endpoint approval and immutable provenance;
2. explicit commitment for every accepted evidence method;
3. actual RPC-operation accounting across tokens and methods;
4. ceilings below total, per-method, connection, and bandwidth limits;
5. bounded 403/429/timeout/JSON-RPC/null/malformed handling;
6. `Retry-After` parsing without unbounded sleep or automatic restart;
7. no endpoint rotation after identity, parser, data, or provenance failures;
8. bounded-history reporting without false completeness;
9. exact mint/account/signature/slot isolation and idempotent replay;
10. zero retrieval and financial deltas.

No network proof or probe was authorized by V2-9.7D.1D.

## 17. Code and Test Reconciliation

Inspected implementation points:

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/sources/governor.py`
- `src/printer_v1/operator_cli/safety_context_source_redundancy.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/evidence_fill/real.py`

Inspected focused tests without executing them:

- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `tests/test_post_rc_solana_rpc_safety_evidence_fixture_normalizer.py`
- `tests/test_post_rc_real_evidence_collection.py`
- `tests/test_v2_9_6_safety_context_source_redundancy.py`

Existing tests establish fixture-backed exact-mint checks, bounded T3 work,
failure provenance, holder source isolation, and one conditional backup path.
They do not prove current public-endpoint limits, endpoint alias equivalence,
fixed retention, consolidated IP-wide budgets, or operational activation.

## 18. Remaining Locks

- No RPC call, endpoint probe, source fetch, runtime, campaign, or memory growth.
- No provider or campaign implementation through this adoption.
- No transaction simulation/submission, wallet, key, signing, or funds.
- No retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- No paid dependency, scoring, ranking, confidence, weighting, embeddings, or
  vectors.
- No Source Governor or Central Scheduler bypass.
- No public-RPC limit may be treated as a target utilization level.

## 19. Unresolved Questions

| Item | Status |
|---|---|
| Guaranteed equivalence of `api.mainnet.solana.com` and `api.mainnet-beta.solana.com` | Not relied upon; legacy hostname is not an adopted runtime endpoint |
| Fixed archival/history-retention window for shared public endpoint | `UNKNOWN_REQUIRES_RESEARCH` |
| Current official maximum/default signature-query limit in reviewed primary page | `UNKNOWN_REQUIRES_RESEARCH` |
| Exact `getBlockTime` null-versus-error mapping for every unavailable state | `UNKNOWN_REQUIRES_RESEARCH` |
| Public endpoint SLA and numeric timeout guarantee | `UNKNOWN_REQUIRES_RESEARCH` |
| PublicNode fallback limits, retention, and provider contract | `UNKNOWN_REQUIRES_RESEARCH` |
| Consolidated operation/connection/bandwidth accounting in Printer | `NOT_IMPLEMENTED` |

## 20. Change History

| Date | Change | Author/lane |
|---|---|---|
| 2026-07-12 | SB-2 through SB-2.3 established the six-method reference, endpoint conflict, T3 provenance, and published shared limits | SB-2 series |
| 2026-07-18 | Re-audited current official Solana docs; adopted endpoint, access, limits, commitment, transport, retention, per-method, provenance, and fail-closed boundaries; reconciled adapters, budgets, retries, and focused tests | V2-9.7D.1D |
| 2026-07-30 | Adopted current official public fallback, validated/redacted operator HTTPS configuration, finalized direct Pump live-tail methods, and removed stale runtime hostname literals | V2-9.8B source compatibility reset |
