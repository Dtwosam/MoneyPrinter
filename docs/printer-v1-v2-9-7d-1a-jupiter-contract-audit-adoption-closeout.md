# Printer V1 V2-9.7D.1A Jupiter Contract Audit and Adoption Closeout

## Verdict

`V2_9_7D_1A_JUPITER_CONTRACT_AUDIT_ADOPTION_PASS`

PASS means the official provider contract was audited and safely adopted with
current incompatibilities explicit. It does not mean the Jupiter network
adapter is ready and authorizes no source request or implementation work.

## Lane and Preflight

- Starting commit: `845cf7d86b462be7e554c3c3c011dffac7c04110`
- Starting tracked tree: clean
- Unrelated untracked artifacts: observed and untouched
- Work type: documentation-only audit and adoption
- Research: official Jupiter docs only; no endpoint probe, API request, MCP
  install, or connector use
- Code, tests, migrations, schemas, databases, and runtime: unchanged

## Audit Result

The audit supports adoption of a fail-closed provider contract.

Jupiter identifies Metis Swap API V1 as no longer actively maintained and
superseded by Swap V2. The documented V1 quote host is
`https://api.jup.ag/swap/v1/quote`, requires `x-api-key`, and has a free tier.
Its response includes exact amounts, threshold, price impact, route plan, fee,
slot, and timing fields.

Printer's adapter remains paper-only and governed, but uses the legacy
`lite-api.jup.ag` host without authentication, maps every HTTP 400 to no route,
defaults missing/malformed price impact to zero, treats local receipt as
freshness, and drops authoritative quantitative fields. Migration 023 retains
categorical evidence and source trace but not the complete quantitative
contract.

These gaps are visible, bounded, and remain locked for a later repair lane.
They do not require code or schema changes for this audit/adoption.

## Adoption Gate

| Requirement | Result |
|---|---|
| Canonical product/version identified | PASS - Metis V1 `SUPERSEDED`; Swap V2 recorded |
| Endpoint, auth, cost, limits, request, response, route semantics | PASS |
| Quote meanings separated from fills/execution | PASS |
| Producers, normalizers, storage, tests inspected | PASS |
| Gaps explicitly classified | PASS - `PARTIAL_WITH_BLOCKER` / `ALLOWED_FIXTURE_ONLY` |
| Unsupported semantics marked unknown | PASS |
| Governor and Scheduler boundaries preserved | PASS |
| No live call or activation | PASS |

## Current-State Reconciliation

| Component | Classification | Finding |
|---|---|---|
| Governor and paper-only boundary | READY | Exact request kind, approval, no transaction role |
| V1 endpoint and auth | BLOCKED | Legacy lite host and no current required key handling |
| Request identity | PARTIAL | Request mints/amount/slippage present; response reconciliation incomplete |
| Route/no-route interpretation | BLOCKED | Every HTTP 400 treated as no route |
| Quantitative normalization | BLOCKED | Impact can become zero; key fields dropped |
| Freshness | BLOCKED | Receipt/registry duration do not prove validity |
| Categorical storage | READY | Exact source trace and downstream locks |
| Quantitative retention | NOT_IMPLEMENTED | Existing row lacks the full adopted contract |
| Fixture regressions | PARTIAL | Categorical behavior only, not current network semantics |
| Governed live readiness | BLOCKED | Later implementation and isolated proof required |

## Adopted Source-Stack Changes

- Created `jupiter-route-quote-api-contract.md`.
- Added it to Builder task routing and the module index.
- Added fail-closed Jupiter rules to `source-governor-evidence-rules.md`.

The broader Builder stack remains subordinate and is not globally adopted by
this one provider module.

## Canonical Sources and Access Date

Accessed `2026-07-18`:

- `https://developers.jup.ag/docs/swap/v1/get-quote`
- `https://developers.jup.ag/docs/api-reference/swap/v1/quote`
- `https://developers.jup.ag/docs/swap/migration/metis-to-build`
- `https://developers.jup.ag/docs/swap/order-and-execute`
- `https://developers.jup.ag/docs/swap/routing/market-listing`
- `https://dev.jup.ag/portal/rate-limit`

External content was untrusted research input. No embedded instruction was
executed and no external content became runtime evidence.

## Money-Usefulness Contribution

This lane defines the route, amount, threshold, fee, impact, and freshness
evidence needed before a quote can support realistic paper entry or exit. It
prevents malformed responses, auth failures, or generic HTTP 400 from becoming
favorable zero-impact or valid no-route labels.

## What This Lane Improves

- Replaces implicit legacy assumptions with a dated official contract.
- Makes Metis V1 lifecycle and Swap V2 replacement explicit.
- Separates provider facts from Printer implementation behavior.
- Defines quantitative provenance and fail-closed mappings.
- Identifies the smallest later repair and proof obligations.
- Makes the module discoverable from the Builder index and evidence rules.

## What Remains Locked

- Jupiter network requests and provider activation
- V2-9.7D implementation beyond this documentation lane
- operational memory growth and V2-9.8 activation
- clean-memory creation or promotion changes
- retrieval, similarity, decisions, and BUY/SELL/HOLD
- positions, trade events, paper audits, and PnL
- wallets, private keys, signing, transactions, and live execution
- paid Jupiter tiers
- Source Governor or Central Scheduler bypass

## Proof Required Before Later Implementation Completion

- explicit V1 Metis or V2 quote-only choice;
- exact host and secret-safe free-key authentication;
- bounded governed request with no taker, transaction, signing, or execute path;
- exact request/response identity and amount reconciliation;
- strict finite parsing for impact, amounts, threshold, route, and fees;
- explicit no-route parsing instead of generic HTTP-400 mapping;
- conservative evidenced freshness;
- immutable provenance in an approved storage/artifact boundary;
- isolated fixture/contract tests, then separately authorized bounded proof;
- zero source bypass, retrieval, decision, position, trade, audit, and PnL deltas.

## Functionality Risks / Setbacks / Efficiency Blockers

- Metis V1 is superseded, so a V1 repair may have limited longevity.
- Swap V2 quote-only behavior has different multi-router and fee semantics;
  silent replacement would invalidate existing fixtures.
- The categorical schema cannot alone support the quantitative contract.
- Jupiter provides no adopted general V1 quote-validity duration.
- Current no-route handling can misclassify malformed/rejected requests.
- Current zero default for malformed impact is unsafe for paper realism.
- Wallet-level flow authenticity remains partial; quotes do not resolve it.

## Checks

| Check | Result |
|---|---|
| Static source, schema, fixture-test, roadmap, and Builder inspection | PASS |
| Official-contract source/access-date reconciliation | PASS |
| Accidental unlock and activation-language scan | PASS |
| Approved documentation scope | PASS - exactly four lane-specific docs |
| `git diff --check` (staged lane patch) | PASS |

No tests, source requests, runtime, or database commands were run; none belong
to this documentation-only lane.
