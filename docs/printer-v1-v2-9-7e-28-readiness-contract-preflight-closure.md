# Printer V1 V2-9.7E.28 Readiness Contract Preflight Closure

## Verdict

`V2_9_7E_28_READINESS_CONTRACT_PREFLIGHT_PASS`

The E.27 pre-request block was valid. The committed GeckoTerminal runtime sent
API version `20230302` while the current official keyless Public API contract
publishes `20230203`, and Printer allowed 30 requests/minute while the official
public limit is approximately 10 requests/minute. E.28 aligns the header and
Governor registry to the verified contract, enforces six-second request
spacing, removes GeckoTerminal retries, and adds one offline fail-closed gate
covering every source required by a bounded readiness cycle. No provider was
contacted and no live authorization was consumed.

## Baseline, scope and authorization

- Exact baseline: `cc94db5883fa8d71bf7707d349a1ee84d8f10e2f`
- Baseline message: `Prove snapshot readiness after contract repair`
- HEAD and tracked tree at entry: exact baseline and clean
- Scope: official-document audit, minimum GeckoTerminal repair, consolidated
  offline preflight, focused fixture proof, contract documentation and closeout
- Live/provider API requests: zero
- Readiness cycle, pilot, authoritative corpus, lifecycle, memory, retrieval,
  financial capabilities, V2-9.7F and V2-9.8: untouched
- Pre-existing unrelated untracked workspace artifacts: not read as authority,
  changed, staged or committed

## Official-contract audit and frozen design

Official documentation was read as documentation only. No production endpoint
was called.

| Source | Official contract checked | Production finding | E.28 disposition |
|---|---|---|---|
| GoPlus | Fixed Solana token-security GET with exact `contract_addresses`; optional bearer surface; free limit 30/min; documented response/error envelope | Fixed endpoint, headers, request kind, one operation and Printer 20/min were compliant. Unknown or incomplete holder data already fails closed. | No transport change. Contract permission clarified for a separately authorized readiness proof. |
| Solana public RPC | Fixed public mainnet endpoint; JSON-RPC POST; finalized `getTokenLargestAccounts` and `getTokenSupply`; public limits 100 requests/10s globally and 40/10s per method | Fixed endpoint, keyless headers, two-operation holder unit, Printer 30/min and exact-mint/finalized rules were compliant. | No transport change. Holder request-kind permission recorded. |
| Helius Free | Fixed `mainnet.helius-rpc.com`; query API key; standard RPC methods; Free RPC limit 10/s; one credit per standard method | Fixed host, redacted environment secret, two-method/two-operation holder unit, Printer 30/min and finalized exact-mint rules were compliant. | No transport change. Adopted backup contract added to Governor rules. |
| DexScreener | Fixed exact-pair path `/latest/dex/pairs/{chainId}/{pairId}`; keyless GET; pair endpoint limit 300/min; documented nullable market fields | Fixed Solana pair endpoint, headers, one operation, Printer 60/min and exact pair/mint fail-closed normalization were compliant. | No transport change. Readiness request-kind permission recorded. |
| GeckoTerminal | Fixed Public API v2 OHLCV and pool-trades paths; `Accept: application/json;version=20230203`; keyless; approximately 10/min; OHLCV minute aggregate 15 and exact pool trades | Runtime used version `20230302`; registry allowed 30/min and two retries. These contradicted the adopted public contract. Endpoints and strict exact-pool/15m response handling were otherwise correct. | Header fixed to `20230203`; registry reduced to 10/min and zero retries; shared Scheduler pacer now applies at least six seconds between GeckoTerminal transports. |

The frozen minimum design changes only the proven GeckoTerminal mismatch and
the documentation needed to make the already-committed readiness request kinds
unambiguous. Every source remains fixed-endpoint, single-attempt and
non-rotating. The Helius secret remains runtime-only and is represented in the
preflight solely by a presence boolean.

## Consolidated offline authorization preflight

`readiness_source_contract_preflight.py` independently freezes the adopted
official values instead of deriving expected values from the runtime constants
it verifies. Before a newly authorized readiness cycle can begin, its assertive
entry point requires all of the following to agree:

- endpoints, required headers, authentication mode and approved request kinds;
- provider ceilings, stricter Printer ceilings and derived minimum pacing;
- transport-operation costs, response-field obligations and error-safe
  single-attempt/no-rotation behavior;
- the configured Helius secret's presence without recording secret material;
- campaign ceiling 45, candidate cap 3 and six readiness operations reserved;
- DexScreener base plus GeckoTerminal exact completed 900-second provenance.

Any mismatch returns `BLOCKED` with a deterministic reason; the authorization
assertion raises before source execution. The report is secret-free and records
`external_requests = 0`.

Representative offline mutations proved blocking for endpoint, header, auth,
rate, pacing, registered request kind, operation cost, missing Helius secret
and budget drift.

## Source and operation accounting

The operation ceiling is unchanged:

| Reserved work | Operations |
|---|---:|
| Pump finalized discovery worst case | 12 |
| Combined zero-source validation | 9 |
| Three candidates x five holder transports | 15 |
| Two exact-pair DexScreener bases | 2 |
| Two GeckoTerminal OHLCV plus two trade requests | 4 |
| Worst-case total | **42** |
| Ceiling / margin | **45 / 3** |

Candidate cap 3 and the complete six-operation two-candidate snapshot
reservation remain unchanged. Each actual HTTP/JSON-RPC transport costs one
operation; the two-method public-RPC or Helius holder evaluation therefore
costs two. Retries, endpoint rotation, reconnects and hidden successors remain
zero.

## Snapshot safety and provenance

E.28 does not alter E.26 normalization or acceptance semantics. DexScreener
must still provide an exact Solana mint/pair base with usable price, liquidity,
5m fields and wider-window activity. GeckoTerminal may supply only the exact
completed 15m OHLCV and complete-window transaction evidence for that same
pool. Missing, stale, malformed, mismatched, truncated or conflicting evidence
continues to fail closed. No absent value is converted to zero outside the
existing verified-inactivity predicate.

## Offline proof and checks

- Consolidated E.28 plus E.26 focused proof: **20 passed**.
- Nearest registry/Governor, E.19, E.22, E.24, E.26, E.28 and GeckoTerminal
  evidence/runtime/bounded regressions: **118 passed**.
- Changed Python compilation: PASS.
- `git diff --check`: PASS; only line-ending notices were emitted.
- Deterministic preflight status with secret presence represented as `true`:
  `READY`, issues `[]`, external requests `0`.
- Fixed endpoint/no retry/no rotation assertions: PASS for all five readiness
  source profiles.
- Exact-pair and 15m provenance regression: PASS.
- No test weakened and no live source fixture substituted.

## Money-usefulness contribution

The repair prevents a future readiness proof from consuming its single live
authorization with an invalid version header or an over-permissive Governor
rate. More importantly, the consolidated gate makes source-contract drift a
deterministic pre-transport failure, protecting future clean-memory evidence
from ambiguous provider behavior and preserving scarce campaign operations for
the two evidence-complete candidate snapshots that can actually inform later
paper-only usefulness.

## Functionality Risks / Setbacks / Efficiency Blockers

- Official public/free limits and provider schemas can change; a future live
  proof must rerun this static contract gate against then-current official
  documentation before authorization is consumed.
- GeckoTerminal's public limit is described approximately. Printer adopts the
  stricter 10/min ceiling and deterministic six-second spacing; a provider may
  still enforce shared-IP or undisclosed anti-abuse controls.
- GoPlus may return absent holder data for a fresh target, public RPC may be
  shared or rate-limited, and Helius Free still requires an operator-owned key.
  The preflight proves configuration consistency, not future availability.
- Provider response fields may be nullable or unavailable for very young
  pools. E.28 deliberately does not weaken exact-pair, liquidity or 15m gates.
- The preflight is offline and does not prove that two candidates or two
  complete snapshots exist now. It authorizes no network execution by itself.

## Readiness and remaining locks

Printer is ready only for consideration of **one newly and separately
authorized bounded readiness proof**. That proof must independently confirm a
clean baseline, isolation, Helius secret presence, the consolidated `READY`
result, and every existing one-cycle/no-retry/no-successor constraint.

This PASS does not authorize a readiness cycle, full pilot, corpus mutation,
lifecycle windows, memory generation or promotion, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trade events, audits, PnL, V2-9.7F or V2-9.8.
