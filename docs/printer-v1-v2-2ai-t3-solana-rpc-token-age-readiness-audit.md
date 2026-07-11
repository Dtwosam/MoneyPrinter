# Printer V1 V2-2AI T3 Solana RPC Token-Age Readiness Audit

Status: AUDIT ONLY
Lane: V2-2AI - T3 Solana RPC Token-Age Evidence Readiness Audit
Executor/model: Codex, standard/balanced mode
Verdict: READINESS_COMPLETE_WITH_BLOCKERS

V2-3 remains paused. A3 remains locked. The staged/native 15m blocker remains
PARTIAL - DEFERRED, NOT RESOLVED.

This lane did not run Solana RPC, Helius, PumpPortal, PumpSwap, discovery,
source fetching, scheduler/runtime, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL. It did not edit
source code, tests, migrations, data, or operator artifacts.

## Prior-Lane Confirmation

The V2-2AH report is tracked and committed.

| Check | Result |
| --- | --- |
| Prior-lane commit | `2e30c59 Add V2-2AH observed live launch proof` |
| Report path | `docs/printer-v1-v2-2ah-observed-live-launch-live-proof.md` |
| Commit verification | confirmed by `git show --stat --oneline 2e30c59` |

## Source Stack Read

The audit used the active source stack together, not as a single-document source
of truth:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-v2-2x-token-age-evidence-source-readiness-review.md`
- `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md`
- `docs/printer-v1-v2-2ae-pumpportal-live-event-diagnostics.md`
- `docs/printer-v1-v2-2af-pumpportal-launch-timestamp-evidence-design-update.md`
- `docs/printer-v1-v2-2ag-1-observed-live-launch-tier-verification.md`
- `docs/printer-v1-v2-2ah-observed-live-launch-live-proof.md`

## Existing RPC Infrastructure Found

Static inspection found an existing Solana RPC holder/safety reference path, but
not a T3 token-age enrichment path.

| Area | Finding |
| --- | --- |
| Solana RPC module | `src/printer_v1/sources/solana_rpc_holder.py` |
| Existing purpose | holder concentration fallback using `getTokenLargestAccounts` and `getTokenSupply` |
| Source name | `solana_rpc` |
| Existing request kind | `holder_concentration_reference` |
| Default endpoint | `https://api.mainnet-beta.solana.com` |
| Operator-configurable endpoint | supported by existing holder flow through RPC URL plumbing and redacted host reporting |
| Source Governor boundary | existing holder adapter validates governed context and source request kind |
| Existing network behavior | read-only RPC only; no wallet, signing, transaction build, or send path |
| Existing 429 behavior | rate-limit failure maps to `solana_rpc_rate_limited` in holder fallback |
| Current token-age support | not implemented |

The existing RPC holder path is useful architecture precedent, but it is not a
token creation-time source. It should not be reused by silently expanding holder
fallback semantics; a future T3 lane needs an explicit token-age request kind,
normalizer, provenance contract, and bounded proof.

## Current Token-Age Boundary

Static inspection found the token-age boundary remains strict.

| Boundary | Current status |
| --- | --- |
| `token_created_at` parser field | exists |
| `token_age_seconds` parser field | exists |
| `token_age_evidence_tier` parser field | exists |
| `pair_age_context_label` parser field | exists as diagnostic context |
| Pair age copied into token age | not found |
| `captured_at` copied into token creation time | not found |
| `derive_age_bucket()` | reads `token_age_seconds` only |
| A3 late-buy trap gate | requires `token_age_seconds is not None` |
| Recent-active tier | derives from token-age bucket and activity bucket |
| OBSERVED_LIVE_LAUNCH | metadata tier only; leaves token creation and token age null |

The current parser can carry token-age evidence when a valid source supplies it,
but no current Solana RPC path populates it.

## Candidate T3 Evidence Method

Recommended T3 method for a future design lane:

1. Start from the token mint address only, not the pair address, pool address, or
   first observed trade.
2. Through Source Governor, issue a bounded `getAccountInfo` request to confirm
   the target account is a mint account owned by SPL Token or Token-2022.
3. Through Source Governor, issue bounded `getSignaturesForAddress` requests for
   the mint address.
4. Walk backward only within an approved request/page cap to find the earliest
   available candidate signature.
5. Fetch candidate transaction details with `getTransaction`.
6. Accept T3 only if the transaction contains a mint-initialization instruction
   targeting the same token mint and the transaction has a defensible block time.
7. If `getTransaction.blockTime` is null, optionally query `getBlockTime` for
   the same slot within the same bounded request budget.
8. Populate `token_created_at`, `token_age_seconds`, and
   `token_age_evidence_tier = T3` only when the mint-initialization target and
   block-time evidence are both proven.

This method is defensible because it targets mint-account creation semantics
instead of pair creation, pool creation, migration timing, or first trade timing.

## Why T3 Is Not Yet Complete

T3 is feasible, but not ready as current runtime behavior.

| Requirement | Current readiness | Blocker |
| --- | --- | --- |
| RPC read-only plumbing | partial | holder/safety path exists, token-age request kind does not |
| Source Governor integration | partial | existing precedent exists, but token-age method allowlist is absent |
| Token mint account validation | not implemented | no current T3 normalizer |
| Earliest signature discovery | not implemented | requires bounded pagination policy |
| Mint-initialization transaction parsing | not implemented | requires instruction parsing and target match |
| Block-time validation | not implemented | null/pruned block time must fail closed |
| Multi-call provenance | not designed | request/response/failure trace must preserve each RPC step |
| Bounded live proof | not run | no network call allowed in this audit |

## Required RPC Calls and Bounded Request Plan

Future T3 should use a conservative request budget per token.

| Step | RPC method | Purpose | Suggested cap |
| --- | --- | --- | --- |
| 1 | `getAccountInfo` | confirm mint account owner/program and target identity | 1 |
| 2 | `getSignaturesForAddress` | locate earliest available mint-account signature | 1-3 pages |
| 3 | `getTransaction` | inspect earliest candidate transaction for mint initialization | 1-3 signatures |
| 4 | `getBlockTime` | fallback only if transaction block time is null and slot is known | 0-1 |

Suggested first design cap: 3-8 RPC requests per token, depending on whether the
future lane chooses one or more signature pages. If the cap is exhausted before
earliest mint-initialization evidence is established, T3 must fail closed and
leave token age unknown.

Do not add automatic endpoint rotation, unbounded pagination, retries, background
workers, or paid archive-node dependencies.

## Source Governor Integration Assessment

The future T3 path must be Source-Governor-only.

Required future source contract additions:

- source name: `solana_rpc`
- request kind: `mint_creation_time_reference` or equivalent
- method allowlist: `getAccountInfo`, `getSignaturesForAddress`,
  `getTransaction`, optional `getBlockTime`
- max requests per token
- max pages per token
- endpoint host redaction
- source request row for each bounded operation or one parent request with
  fully audited child operation payloads
- source response row only when evidence is complete and clean
- source failure row when rate-limited, pruned, null block time, mismatched mint,
  missing instruction, or budget exhausted

No memory engine, discovery engine, parser, or selection engine may call RPC
directly.

## Free/Public Endpoint Feasibility

T3 can start with free/public Solana RPC, but it carries reliability risk.

| Endpoint path | Feasibility | Risk |
| --- | --- | --- |
| Public Solana RPC | possible for small bounded proof | rate limits, pruning, null block time, incomplete history |
| Operator-supplied free/read-only RPC | acceptable if optional | must redact host/query secrets and remain no-paid-dependency |
| Helius free tier | possible as optional future fallback | must not become paid-required |
| Paid archive node | not allowed for Printer V1 |

The future design must treat public RPC failure as normal. Rate-limited,
unavailable, pruned, null, or incomplete evidence must leave token age unknown.

## Provenance Requirements

Future T3 evidence must preserve:

- token mint requested
- source name and request kind
- redacted RPC host
- request cap and page cap used
- RPC methods attempted
- source request IDs
- source response ID or source failure ID
- signature used for accepted evidence
- slot
- block time
- parsed instruction type
- mint target matched
- token program matched
- captured_at
- derived `token_created_at`
- derived `token_age_seconds`
- `token_age_evidence_tier = T3`

If a response is partial, mismatched, stale, rate-limited, pruned, or missing
critical data, provenance should still be visible through source failure rows,
but no token-age fields should be populated.

## Failure and Fallback Behavior

T3 must fail closed.

| Failure case | Required behavior |
| --- | --- |
| HTTP 429 / rate limited | source failure; token age remains unknown |
| RPC transport error | source failure; token age remains unknown |
| missing account info | source failure; token age remains unknown |
| account is not a mint | source failure; token age remains unknown |
| signature history pruned | source failure or unknown; token age remains unknown |
| bounded page cap exhausted | source failure or unknown; token age remains unknown |
| transaction not available | source failure; token age remains unknown |
| null block time with no accepted fallback | source failure; token age remains unknown |
| transaction does not initialize the requested mint | source failure; token age remains unknown |
| migration/pool/first-trade evidence only | reject as token-age evidence |

No fallback may use pair age, observed-live capture time, migration time,
first-trade time, or current collection time as token creation time.

## T1/T2/OBSERVED_LIVE_LAUNCH Boundary Confirmation

| Tier or context | Boundary |
| --- | --- |
| T1 | approved on-chain creation-slot evidence only |
| T2 | explicit source-provided launch timestamp only |
| T3 | future governed RPC mint-creation enrichment only |
| OBSERVED_LIVE_LAUNCH | proves a mint-bearing live launch event was observed, but is not token age |
| Pair age | diagnostic context only, not token age |
| `captured_at` | collection time only, not token creation time |
| Migration time | migration context only, not token creation time |

Current code preserves these boundaries. T3 is not active.

## A3 Status

No - A3 remains locked until a future approved T3 implementation and bounded
live proof produce real token_age_seconds.

Static inspection confirms A3 still requires `token_age_seconds is not None`.
Pair age, OBSERVED_LIVE_LAUNCH, and `captured_at` do not satisfy this gate.

## Staged/Native 15m Blocker Status

The staged/native 15m blocker remains:

`PARTIAL - DEFERRED, NOT RESOLVED`

V2-2Z.3 showed staged `price_change_15m` could be useful, but existing operator
DB rows still had 0 populated `price_change_15m` values and no native 15m
coverage. This audit did not backfill, derive, or prove fresh post-hook 15m
coverage.

## Candidate Future Files

A future T3 design or implementation lane would likely touch:

- `src/printer_v1/sources/solana_rpc_holder.py` or a new
  `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/sources/contracts.py`
- `src/printer_v1/sources/recording.py`
- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`
- `src/printer_v1/operator_cli/commands.py` only if operator proof CLI is
  explicitly approved
- focused tests for T3 normalization, source failures, provenance, no fallback,
  A3 locking, and row-delta safety

This lane did not modify any of those files.

## Proof Needed Before Completion

Before T3 can be called complete, a future approved lane must prove:

1. Fixture mint-initialization transaction parses into T3 evidence.
2. Mismatched mint transaction fails closed.
3. Missing/null block time fails closed unless a bounded `getBlockTime` fallback
   succeeds.
4. Public RPC 429 maps to source failure and does not populate token age.
5. Page cap exhaustion leaves token age unknown.
6. Pair age never populates token age.
7. OBSERVED_LIVE_LAUNCH never populates token age.
8. Migration/pool/first-trade evidence is rejected for token creation time.
9. A3 fires only when real `token_age_seconds` exists and other A3 inputs pass.
10. Bounded live proof uses an isolated DB or backed-up operator-approved path.
11. Persistent DB, memory, retrieval, paper, position, trade, audit, and PnL
    locks remain unchanged.

## Money-Usefulness Contribution

T3 would improve Printer's money-usefulness by reducing false recent-launch
classification, separating old-token/new-pair resurfacing from true new mints,
and enabling honest A3 late-buy-trap classification for non-PumpPortal tokens.

It is especially useful for tokens discovered through GeckoTerminal,
DexScreener, or other pair-centric sources that provide pair age but not token
creation age.

## What This Lane Improves

- Confirms existing Solana RPC support is holder/safety only.
- Defines the safe T3 evidence shape and request plan.
- Confirms T3 must be bounded, governed, read-only, and failure-visible.
- Confirms A3 remains locked.
- Confirms pair age, observed-live, captured time, migration time, and first
  trade time cannot substitute for token creation time.

## What This Lane Does Not Unlock

- no Solana RPC calls
- no Helius calls
- no source fetching
- no implementation
- no dependency changes
- no DB mutation
- no token snapshots
- no discovery run
- no memory generation
- no retrieval activation
- no paper decisions
- no BUY/SELL/HOLD
- no positions, trades, audits, or PnL
- no V2-3

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Impact |
| --- | --- |
| Public RPC rate limits | T3 may fail often unless request budget is tiny or operator supplies an approved free endpoint |
| Historical pruning | earliest mint signature may be unavailable on public endpoints |
| Pagination pressure | true earliest signature may require more pages than V1 should allow |
| Null block time | transaction evidence may not produce a defensible timestamp |
| Instruction parsing complexity | must distinguish mint initialization from pool/trade/migration events |
| Multi-call provenance | simple one-row response may be insufficient unless designed carefully |
| Optional free endpoint variability | different free endpoints may return different history availability |

None of these justify fake token-age fallback.

## Exact Next Recommended Lane

`V2-2AJ - T3 Solana RPC Token-Age Evidence Design`

Recommended scope:

- documentation and fixture contract first
- no live RPC
- define request kind and method allowlist
- define bounded request/page caps
- define provenance storage
- define source failure taxonomy
- define fixture parser tests
- preserve all token-age and financial locks

Do not move to V2-3 before the operator explicitly accepts the remaining V2-2
blockers.

## Final Audit Summary

```text
VERDICT: READINESS_COMPLETE_WITH_BLOCKERS
V2_2AH_COMMIT_CONFIRMED: 2e30c59
CURRENT_SOLANA_RPC_PATH: holder/safety reference only
T3_TOKEN_AGE_PATH_ACTIVE: NO
RECOMMENDED_T3_METHOD: governed mint-account RPC enrichment using bounded getAccountInfo, getSignaturesForAddress, getTransaction, optional getBlockTime
TOKEN_CREATED_AT_FROM_PAIR_AGE: BLOCKED
TOKEN_CREATED_AT_FROM_CAPTURED_AT: BLOCKED
TOKEN_CREATED_AT_FROM_OBSERVED_LIVE_LAUNCH: BLOCKED
TOKEN_CREATED_AT_FROM_MIGRATION_TIME: BLOCKED
A3_STATUS: LOCKED
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
NEXT_LANE: V2-2AJ - T3 Solana RPC Token-Age Evidence Design
```
