# Printer V1 V2-9.7D.1D Public-RPC Limits Audit and Adoption Closeout

## Verdict

`V2_9_7D_1D_PUBLIC_RPC_LIMITS_AUDIT_ADOPTION_PASS`

PASS means the current official Solana public-RPC contract was audited and
adopted with implementation gaps and unknowns explicit. It does not mean an
endpoint, provider implementation, runtime, campaign, or downstream capability
is activated.

## Preflight and Scope

- Starting HEAD: `f0d1de5db5dab99d61a6df28f508fb02949343f1`
- Starting tracked tree: clean
- Existing unrelated untracked artifacts: observed and untouched
- Work performed: official-documentation research and static repository
  inspection only
- RPC calls, endpoint probes, source fetching, tests, DB commands, and runtime:
  none
- Code, tests, migrations, schemas, databases, roadmaps, Builder index, and
  Source Governor evidence rules: unchanged

## Executive Finding

The official contract is sufficient for conservative adoption. Current Solana
documentation publishes a keyless shared Mainnet endpoint, five numeric
IP-level limits, commitment semantics, HTTP 403/429 behavior, and method-level
request/response contracts for all six Printer methods.

The audit also found material implementation gaps, but none requires an unsafe
claim for documentation adoption. Current English official pages use
`api.mainnet.solana.com`, while Printer uses `api.mainnet-beta.solana.com` and
older/localized official material still exposes that name. Equivalence remains
`UNKNOWN_REQUIRES_RESEARCH`. The holder fallback is third-party PublicNode and
cannot inherit official Solana limits. Top-level Governor accounting also does
not prove control of actual per-method operations, connections, or bytes.

These gaps block later implementation or operational reliance where relevant.
They do not block this lane because no request path is activated and all
unknown, null, partial, pruned, rate-limited, and mismatched evidence remains
fail-closed.

## Adoption Gate

| Requirement | Result |
|---|---|
| Current official endpoint/access/cost contract identified | PASS |
| Total, per-method, connection, concurrency, and bandwidth limits recorded | PASS |
| Commitment, timeout, 403/429, null, pruning, and transport boundaries recorded | PASS |
| Six Printer RPC request paths reconciled | PASS |
| Upstream ceilings separated from stricter Printer budgets | PASS |
| Provenance and fail-closed retry rules adopted | PASS |
| Unsupported proof boundaries explicit | PASS |
| Unknown facts remain `UNKNOWN_REQUIRES_RESEARCH` | PASS |
| No capability activation or scope expansion | PASS |

## Official Sources

Accessed `2026-07-18`:

- `https://solana.com/docs/references/clusters`
- `https://solana.com/docs/rpc`
- `https://solana.com/docs/rpc/http`
- `https://solana.com/docs/rpc/http/getaccountinfo`
- `https://solana.com/docs/rpc/http/getsignaturesforaddress`
- `https://solana.com/docs/rpc/http/gettransaction`
- `https://solana.com/docs/rpc/http/getblocktime`
- `https://solana.com/docs/rpc/http/gettokenlargestaccounts`
- `https://solana.com/docs/rpc/http/gettokensupply`
- `https://solana.com/docs/rpc/http/minimumledgerslot`
- `https://solana.com/docs/rpc/json-structures`

Only official Solana documentation was used as external authority. No example,
endpoint, request body, or command was executed.

## Findings

- Current English primary pages identify the Mainnet public endpoint as
  `https://api.mainnet.solana.com`; it is keyless shared infrastructure with no
  documented per-request cost.
- Solana warns that public endpoints are not intended for production, limits
  can change without notice, and high-traffic clients can be blocked.
- Current published ceilings are 100 requests/10s/IP, 40 requests/10s/IP for
  one method, 40 concurrent connections/IP, 40 connection attempts/10s/IP, and
  100 MB/30s/IP.
- HTTP 403 means the IP or site is blocked. HTTP 429 requires slowing down and
  respecting `Retry-After`.
- No numeric upstream timeout or SLA was found. Printer's 10-second timeout is
  a local budget.
- `finalized` is the strongest commitment. Omitted commitment is only
  documented as typically finalized, so accepted evidence should request it
  explicitly.
- `minimumLedgerSlot` confirms that nodes can purge older ledger data. No fixed
  shared-public-endpoint retention or archival guarantee is published.
- Empty signature history or null transaction cannot prove historical
  nonexistence.
- Largest token accounts are token accounts, not proven unique wallets or
  beneficial owners.

## Limits Relevant to Printer Request Kinds

| Request kind | Actual RPC operations | Critical limits and behavior |
|---|---|---|
| `mint_creation_time_reference` | Account info, up to 3 signature pages, up to 3 transactions, optional block time; max 8 | Total and per-method IP ceilings, response bytes, finalized context, bounded retention, null transaction/time |
| `holder_concentration_reference` | Largest accounts plus token supply; optional separately governed backup repeats work | Total/per-method ceilings, explicit commitment gap, token-account semantics, third-party fallback contract |
| `mint_account_reference` | Potential account info | Exact method/schema not fully adopted in executable path |
| `onchain_reference` | Generic/unspecified | Must remain blocked until exact method, schema, and budget exist |
| `pool_reference` | Generic/unspecified | Must remain blocked until exact account/program contract exists |

The registry's 30/minute source budget is stricter than the published aggregate
upstream request rate, but it is not a complete protection. One governed source
request can issue multiple RPC operations, and global per-method, connection,
and byte accounting was not found.

## Current Implementation Gaps

| Gap | Effect | Later minimum repair |
|---|---|---|
| Code hostname differs from current primary docs | Endpoint identity and alias policy are unproven | Official clarification or separately approved bounded endpoint proof |
| PublicNode is used as holder backup | Third-party limits/provenance are not adopted here | Separate provider-contract adoption before reliance |
| Holder requests omit commitment | Typical default can masquerade as exact finality | Explicit commitment and focused fixture proof |
| Governor counts source requests, not underlying operations | Fan-out may breach method/IP/byte ceilings | Consolidated operation-level Scheduler budgeting |
| Registry retry metadata differs from adapter behavior | Retry policy is ambiguous | Path-specific finite retry contract |
| HTTP 429 does not preserve `Retry-After` | Official backoff signal is unavailable | Parse, bound, persist, and test the header |
| Signature requests assume `limit = 1000` | Numeric maximum is not pinned in reviewed primary page | Pin current official schema or use a conservative adopted bound |
| Bounded pages can be described as complete | Older initialization may be missed | Report searched bounds and incomplete coverage |
| Manual real-evidence fallback is broader than operational allowlist | Non-transient failures may rotate endpoint | Reconcile to one fail-closed allowlist |
| No fixed retention contract exists | Null/empty may be mistaken for absence | Preserve retention and coverage uncertainty |

## Provenance and Fail-Closed Boundaries

Accepted RPC evidence must retain source/provider, redacted host, exact method
and request kind, exact mint and relevant account/signature/slot, requested
commitment, response context slot when present, request and attempt identity,
capture time, endpoint role, and bounded coverage counters.

Retries must remain finite, Source-Governed, Scheduler-led, separately counted,
identity-preserving, and limited to explicitly transient failures. A 403 must
not be evaded. A 429 retry must honor a bounded `Retry-After`; inability to wait
inside the run deadline remains a failure. Endpoint substitution is a distinct
provider attempt, not a transparent retry. Missing, malformed, stale, pruned,
null, mismatched, or unsupported results remain dirty or blocked.

## Unsupported Proof Boundaries

Public RPC cannot prove complete historical coverage, token legitimacy, future
safety, beneficial wallet ownership, independent participants, coordination,
wash activity, manipulation intent, executable routes, slippage, fills, exits,
or profit. It also cannot by itself establish retrieval fitness, decision
quality, BUY/SELL/HOLD, position validity, or PnL.

Account state, signatures, transactions, block times, largest token accounts,
and supply must retain their exact descriptive meanings. None may become a
score, ranking, confidence, weight, or financial unlock.

## Unresolved Dependencies

- Guaranteed equivalence and long-term policy for `mainnet` versus
  `mainnet-beta`: `UNKNOWN_REQUIRES_RESEARCH`.
- Fixed public-endpoint archival/retention window:
  `UNKNOWN_REQUIRES_RESEARCH`.
- Current official maximum/default signature-query limit in the reviewed
  primary page: `UNKNOWN_REQUIRES_RESEARCH`.
- Exact `getBlockTime` null-versus-error behavior for every unavailable state:
  `UNKNOWN_REQUIRES_RESEARCH`.
- Public endpoint SLA and numeric timeout: `UNKNOWN_REQUIRES_RESEARCH`.
- PublicNode authentication, cost, limits, retention, and provider behavior:
  `UNKNOWN_REQUIRES_RESEARCH`.
- Consolidated operation, connection, and byte accounting: `NOT_IMPLEMENTED`.

These dependencies block affected implementation and activation claims, not the
fail-closed documentation adoption completed here.

## Money-Usefulness Contribution

This lane reduces fake memory and fake paper-profit risk by preventing a null,
pruned, rate-limited, partially searched, wrong-context, or cross-provider RPC
response from being promoted into complete token-age, holder-authenticity, or
tradeability evidence. It also makes the true cost of multi-call evidence
visible to future campaign budgeting, preserving scarce free capacity for exact
mint safety and lifecycle evidence.

## What This Lane Improves

- Establishes a dated official public-RPC endpoint and limits contract.
- Separates shared upstream ceilings from Printer's stricter operating budgets.
- Makes commitment, context, retention, null, 403, 429, and `Retry-After`
  boundaries explicit.
- Reconciles each current Printer RPC request kind with actual RPC-operation
  fan-out.
- Exposes the third-party holder fallback and generic retry metadata as separate
  provider/policy concerns.
- Defines minimum provenance and unsupported-proof boundaries without changing
  code or permissions.

## What Remains Locked

- RPC calls, endpoint probes, source fetching, provider implementation, and
  campaign implementation
- runtime, campaigns, memory generation, and operational commands
- retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL
- wallets, keys, signing, funds, paid dependencies, and live execution
- scoring, ranking, confidence, weighting, embeddings, and vectors
- Source Governor or Central Scheduler bypass
- proofs and later V2-9.7D work

## Functionality Risks / Setbacks / Efficiency Blockers

- Published limits can change without notice and are not a service guarantee.
- Public endpoints are explicitly unsuitable for production dependence.
- Endpoint naming remains inconsistent across current code and official pages.
- One logical evidence request can consume up to eight upstream operations.
- Missing operation-level and byte accounting can hide aggregate pressure.
- No fixed history-retention window makes old-mint T3 coverage inherently
  incomplete on a shared node.
- Honest 403/429 handling can reduce campaign yield and must never trigger
  evasion or unbounded retries.
- Explicit finalized context and strict fallback contracts require later code
  repair before operational reliance.
- Wallet-level flow authenticity remains partial.

## Verification

| Check | Result |
|---|---|
| Exact starting HEAD and clean tracked tree | PASS |
| Static adapter, budget, retry, endpoint, and focused-test inspection | PASS |
| Official-source reconciliation and access-date recording | PASS |
| Upstream ceilings versus Printer-budget reconciliation | PASS |
| Supported/unsupported and unsafe-assumption scan | PASS |
| Capability-unlock wording scan | PASS |
| Only approved lane documentation changed | PASS |
| `git diff --check` | PASS |

No tests, API calls, RPC probes, source requests, runtime, or database commands
were run; none belongs to this lane.

## Final Lane Result

`V2_9_7D_1D_PUBLIC_RPC_LIMITS_AUDIT_ADOPTION_PASS`

Stop after the lane-specific documentation commit. Do not begin provider
implementation, campaign implementation, proofs, or later V2-9.7D work.
