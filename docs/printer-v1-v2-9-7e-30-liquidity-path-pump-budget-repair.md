# Printer V1 V2-9.7E.30 Liquidity Path and Pump Budget Audit/Repair

## Verdict

`V2_9_7E_30_LIQUIDITY_BUDGET_REPAIR_PASS`

E.29's block was valid. Both selected pairs were exact and active, but the
adopted DexScreener schema permits nullable liquidity and both normalized
responses had `liquidity_usd = null`. E.30 replaces DexScreener only in the
bounded-readiness base composition with one fixed GeckoTerminal exact-pool
metadata operation. That operation owns positive `reserve_in_usd`, current
price, m5 activity and wider activity; the existing completed-15m OHLCV and
complete-window trade operations remain gated behind it. The full snapshot
path therefore remains three operations per candidate and six for two.

The Pump preflight defect was also broader than the observed one-operation
shortfall. E.29 actually used three signature pages plus ten transaction
lookups, while E.28 froze 12 total operations. Before this repair, the source
allowed three pages plus twelve decodes, so its real structural maximum was 15.
E.30 bounds the decode ceiling at ten and derives the preflight arithmetic from
the production source constants. Pump's maximum is now exactly 13 operations.

## Baseline, scope and locks

- Exact baseline: `b2dc1901f6b962d0b832210dd1359e46e2dfe9e8`
- Baseline message: `Prove readiness after source contract preflight`
- Entry HEAD: exact baseline
- Entry tracked tree: clean
- Existing unrelated untracked workspace files: preserved and excluded
- E.29 DB/report/evidence: inspected read-only
- Official provider documentation: documentation reads only
- Provider/live source calls: zero
- Isolated fixture/proof databases only
- Operation ceiling: unchanged at 45
- Retry, rotation, reconnect and successor count: zero
- Lifecycle, memory, corpus, retrieval and financial capabilities: untouched

## E.29 evidence audit

The audited database was
`C:\Users\dtwof\PrinterPilot\E29\printer-v1-e29-readiness.sqlite3` in SQLite
read-only/query-only use. Integrity remained `ok` and foreign-key violations
remained zero. The redacted report was read under
`C:\Users\dtwof\PrinterPilot\E29\reports\`.

| Question | Finding |
|---|---|
| Exact pair identity | Both DexScreener responses contained exactly the requested Solana pair/base mint. Wrong-pair selection is rejected as the cause. |
| Transport and shape | Both were `COMPLETE` / `CLEAN_DATA` and included price, m5, h1 and h24 activity. There was no rate limit, malformed envelope or transport failure. |
| Liquidity | Both normalized exact-pair rows contained `liquidity_usd = null`. The normalizer maps `liquidity.usd` directly; it did not convert a supported positive value to zero. |
| Pair age | Candidate 1 was approximately 183.243 seconds old and candidate 2 approximately 171.074 seconds old at DexScreener receipt, based on provider `pairCreatedAt`. |
| Indexing maturity | Pair youth/admission timing is a plausible inference, especially because activity had appeared while liquidity had not, but no official deterministic indexing SLA supports a wait threshold. |
| Provider cause | Raw E.29 provider bodies were not retained. The evidence cannot distinguish an omitted liquidity object from provider-emitted null, nor prove why DexScreener had no value at receipt. |
| Unsupported expectation | DexScreener officially marks the liquidity object nullable. A clean exact-pair HTTP response therefore does not guarantee readiness liquidity. |

Candidate 1 retained price `0.000002179`, 5m price change `-1.65%`, 5m
volume `38.97`, two 5m transactions and the same positive 1h/24h activity.
Candidate 2 retained price `0.000002179`, 5m price change `-1.35%`, 5m
volume `31.18`, two 5m transactions and the same positive 1h/24h activity.
Neither was eligible for missing-liquidity zero conversion.

The definitive E.29 finding is source absence at the captured normalized
contract boundary, not identity mismatch, parser loss or transport failure.
Indexing maturity remains an inference rather than a fact.

## Official contract audit

The current [DexScreener API reference](https://docs.dexscreener.com/api/reference)
identifies the exact pair endpoint and declares the liquidity object nullable.
It supplies no completeness or indexing-latency guarantee that would justify a
maturity threshold.

The current [GeckoTerminal Public API documentation](https://api.geckoterminal.com/docs/index.html)
defines the fixed v2 exact-pool endpoint, version header `20230203`, one-minute
public caching, approximately 10 calls/minute and the exact-pool/OHLCV/trades
endpoint family. The official [specific-pool schema](https://docs.coingecko.com/reference/pool-address)
shows `reserve_in_usd`, base-token price, pool address, base/quote relationships,
m5/h1 buckets and nullable market fields. `reserve_in_usd` is accepted only as
provider pool-liquidity context; it is not an executable quote or exit proof.

No provider was contacted. No paid root or paid dependency was added.

## Frozen minimum repair design

1. Use one fixed keyless GeckoTerminal request per selected candidate:
   `/api/v2/networks/solana/pools/{pool}?include=base_token,quote_token,dex`.
2. Require exact `solana_{pool}`/attribute pool identity and the requested mint
   as the base-token relationship.
3. Require finite positive base-token USD price and `reserve_in_usd`, plus
   well-formed m5 and h1 volume/transaction evidence.
4. Preserve raw-field, source, endpoint, network, pool, mint, receipt and
   governed request/response lineage in the base evidence.
5. Reject missing, zero, negative, non-finite, stale, malformed or mismatched
   liquidity. If optional base/quote liquidity components are present, reject a
   material conflict with `reserve_in_usd`.
6. Only after the base passes, issue the existing fixed completed-15m OHLCV and
   complete-window trades operations. No microstructure call is permitted
   before positive base liquidity.
7. Keep one attempt per endpoint, shared six-second GeckoTerminal pacing, no
   retry/rotation/reconnect/successor and the existing exact 900-second rules.
8. Do not adopt a pair-age delay. The official cache/freshness description does
   not prove a safe deterministic maturity threshold.
9. Keep DexScreener available for its other governed roles, but do not combine
   two base sources or add a fourth readiness operation.

This is the minimum compliant repair. Adding GeckoTerminal liquidity after a
DexScreener base would cost four operations per candidate and increase the
required reservation from six to eight. Relabeling rolling provider m15 fields
as an exact completed candle, treating missing liquidity as zero, or adding an
unsupported age threshold was rejected.

## Pump cause and corrected budget

E.29 used 13 Pump operations because the shared acquisition owner made all
three bounded `getSignaturesForAddress` pages, then lazily decoded ten admitted
`getTransaction` rows before its outcome stop. E.28's value 12 was a stale
hand-entered constant; it was not derived from the production page/decode
ceilings.

E.30 changes the production decode ceiling from 12 to 10, keeps the page ceiling
at 3 and derives Pump cost as `page_ceiling + decode_ceiling`. It also derives
the candidate cap rather than comparing only to a frozen literal:

`floor((45 - 13 - 9 - 6) / 5) = 3`

| Reserved work | Operations |
|---|---:|
| Pump finalized discovery maximum | 13 |
| Combined zero-source gates | 9 |
| Three candidates x five holder transports | 15 |
| Two GeckoTerminal exact-pool bases | 2 |
| Two completed OHLCV + two trade requests | 4 |
| **Worst-case total** | **43** |
| Ceiling / remaining margin | **45 / 2** |

The consolidated preflight now blocks if the Pump source constants, computed
Pump maximum, derived candidate cap, holder-cost multiplication, six-operation
snapshot reservation or 45-operation ceiling disagree. A stale override back
to 12 is explicitly proven blocked.

## Implementation

- The GeckoTerminal base transport uses the already adopted fixed exact-pool
  include query and the E.28 `20230203` headers.
- `geckoterminal_readiness_base_snapshot` is registered and allowed only for a
  separately authorized readiness proof.
- The exact-pool normalizer retains liquidity provenance and rejects optional
  composition conflict.
- The readiness owner performs three sequential GeckoTerminal operations at
  most: base, OHLCV, trades. It stops after base failure.
- Strict snapshot persistence accepts the new governed base request kind and
  requires GeckoTerminal as the current readiness primary.
- The readiness contract requires positive liquidity and exact
  `reserve_in_usd` provenance; its source receipt TTL is 180 seconds.
- DexScreener's generic snapshot and other roles remain unchanged.
- No migration was required; existing request/response and snapshot JSON
  lineage stores the new source facts deterministically.

## Offline proof

The isolated focused proofs establish:

- a clean exact Solana pool/base-mint response with positive
  `reserve_in_usd` is accepted and persists one complete snapshot after the two
  exact-15m supplements;
- the persisted base owns price, positive liquidity, m5 and wider activity;
- missing liquidity blocks after exactly one request and produces no OHLCV or
  trade request;
- zero liquidity reaches the strict positive-liquidity gate and is rejected;
- stale, malformed and base-mint-mismatched pool evidence fails closed;
- optional component total `20,000` conflicting with reserve `25,000` is
  rejected as a liquidity conflict;
- exact completed 15m provenance, malformed/truncated trade rejection and
  verified-inactivity rules remain intact;
- three base/completion operations are charged for a complete candidate;
- Pump page ceiling 3 plus decode ceiling 10 equals the enforced maximum 13;
- candidate cap 3, snapshot reservation 6, worst-case 43 and ceiling 45 are
  deterministic;
- representative endpoint, header, request-kind, response-field and budget
  drift blocks the consolidated preflight;
- deterministic DB-only reporting, integrity, foreign keys, cleanup and zero
  forbidden capability deltas remain covered by the nearest contract proof.

Focused E.26/E.28/E.30 contract proof: **22 passed**.

## Money-usefulness contribution

The repair makes liquidity readiness source-complete without fabricating a
value or spending beyond the campaign budget. It prevents active young-pair
price/volume from masquerading as exit-liquidity evidence, while preserving
scarce operations for two completed 15m bundles. Deriving budgets from source
ceilings also prevents holder evaluation from consuming operations that the
snapshot path only appeared to have reserved.

## Functionality Risks / Setbacks / Efficiency Blockers

- GeckoTerminal exact-pool metadata is offline-proven only in this lane. A
  separately authorized live proof must confirm the current keyless response
  for fresh Pump/launchpad pools.
- The official Public API is beta, approximately rate-limited and cached. The
  180-second receipt TTL is Printer policy, not a provider completeness SLA.
- `reserve_in_usd` is pool reserve context, not executable route, slippage or
  fill evidence. Later lifecycle/paper realism gates remain mandatory.
- Some very new pools may be absent or may still have missing reserve. The path
  fails closed and does not introduce a maturity retry.
- The lower Pump decode ceiling can reduce discovery yield in unusually noisy
  signature pages. It preserves three-candidate budget headroom but should be
  measured in the next separately authorized proof.
- Optional liquidity-component conflict checking is conditional because the
  fixed keyless request does not require composition fields.
- Raw E.29 bodies were not retained, so provider omission versus explicit null
  remains unresolved.

## Readiness and remaining locks

This PASS permits only consideration of one separately authorized bounded
readiness proof. That proof must run once, show the consolidated preflight
`READY`, remain within 45 operations, obtain exactly two holder-eligible
candidates, and collect for each one exact-pool positive reserve plus completed
15m OHLCV and complete-window trades. It must also prove cleanup, integrity,
foreign keys, deterministic zero-source replay and zero forbidden deltas.

This lane does not authorize that proof, a full pilot, corpus mutation,
lifecycle windows, memory generation/promotion, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trade events, audits, PnL, wallets, private keys,
paid sources, V2-9.7F or V2-9.8.
