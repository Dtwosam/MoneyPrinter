# Printer V1 V2-9.7E.26 Snapshot Readiness Contract Audit/Repair

## Verdict

`V2_9_7E_26_SNAPSHOT_READINESS_REPAIR_PASS`

The E.25 block was reproduced from its isolated evidence without contacting a
provider. Both DexScreener results matched the requested Solana mint and pair,
but each very young pair lacked usable liquidity and DexScreener's adopted
schema has no exact 15m bucket. E.19 correctly refused zero normalization
because wider-window activity was positive and liquidity was missing. E.26
therefore preserves DexScreener as the exact base snapshot and adds two fixed,
governed GeckoTerminal operations per selected pair solely for exact completed
15m activity. The strict owner refuses to persist a readiness snapshot unless
the composed evidence satisfies the whole contract.

## Baseline, scope and authorization

- Exact baseline: `bc28fc52520f8079a917e2d9140879c8d8c3c478`
- Baseline message: `Prove Helius holder and snapshot readiness`
- Scope: audit, one frozen minimum design, production repair, isolated offline
  fixture/proof DBs, focused tests and documentation
- Provider contact/live calls: none
- E.25 DB, report and redacted evidence: inspected read-only
- Authoritative corpus, lifecycle windows, memory, retrieval, paper decisions,
  positions, trades, audits and PnL: untouched
- Operation ceiling: retained at 45

## E.25 evidence audit

The audited DB was
`C:\Users\dtwof\PrinterPilot\E25\printer-v1-e25-readiness.sqlite3`; its
reports and redacted source evidence remained unchanged.

| Question | Finding |
|---|---|
| Source absence | Each normalized exact-pair DexScreener response contained price and active m5/h1/h24 fields but `liquidity_usd = null`; all 15m fields were absent. The Dex contract explicitly declares `liquidity.usd` nullable. |
| Indexing maturity | The two `pairCreatedAt` values were approximately 13 and 22 seconds before their snapshot receipts. Pair youth is the strongest evidence-backed explanation for incomplete indexed fields, but remains an inference rather than a provider guarantee. |
| Target mismatch | Rejected as the cause. Each response contained exactly one selected Solana pair and its mint/pair hashes matched the candidate requested by E.25. |
| Transport shape | Both requests were one-attempt `COMPLETE` / `CLEAN_DATA` responses. No transport error, rate limit, malformed envelope or competing pair caused the block. Raw provider bodies were not retained, but the committed normalizer maps `liquidity.usd` directly and did not discard a supported 15m field because none exists. |
| Normalization | E.19 behaved correctly: missing fields remained null because liquidity was not positive and wider-window volume/transactions were positive. The defect was that generic persistence success could be mistaken for readiness, not an invalid zero conversion. |
| Unsupported expectation | DexScreener exposes m5, h1 and h24 pair buckets, not an exact m15 bucket. Relabeling or interpolating them would fabricate window semantics. |

Candidate 1 retained price `0.000006003`, 5m price change `175%`, 5m
volume `54.45`, 5m transactions `13`, and equal positive 1h activity.
Candidate 2 retained price `0.000002179`, 5m price change `-34.03%`, 5m
volume `1406.16`, 5m transactions `8`, and equal positive 1h activity.
Both lacked liquidity and all exact-15m fields; neither was eligible for
verified-inactivity zero normalization.

## Frozen minimum repair design

1. Make one fixed exact-pair DexScreener call per selected candidate. It owns
   exact mint/pair identity, current price, positive USD liquidity, complete 5m
   activity and complete wider-window activity.
2. Fail immediately when any base field is absent or invalid. GeckoTerminal may
   not fill or replace base liquidity, price, 5m or wider-window evidence.
3. Only when the base passes but exact 15m fields remain missing, make exactly
   one fixed GeckoTerminal 15m OHLCV request and one fixed unfiltered pool-trade
   request for the same exact Solana pair.
4. Accept the newest completed, fresh, exact 900-second OHLCV candle without
   trusting provider row order. Use it only for `price_change_15m` and
   `volume_15m`.
5. Accept `txns_15m` only from well-formed unfiltered trades aligned to that
   exact candle, with bounded returned-set coverage. A malformed row, 300-row
   truncation that does not reach the window start, stale data or identity
   mismatch fails closed.
6. Preserve request/response lineage, endpoint identity, capture/evaluation
   times, raw field names and exact-window bounds. Supplemental evidence fills
   missing 15m fields only and cannot overwrite or conflict with primary facts.
7. Make one attempt per endpoint. No retry, rotation, reconnect, second source,
   paid dependency, scoring, ranking, weighting or confidence is permitted.
8. Preserve the E.19 verified-inactivity path. It may produce exact zeros only
   with positive base price/liquidity, exact identity, clean/fresh primary
   evidence and zero wider-window volume and transactions.

This is the minimum compliant design because DexScreener remains authoritative
for the base snapshot while GeckoTerminal supplies only the window it actually
supports. A GeckoTerminal metadata/liquidity fallback was rejected because it
would weaken base consistency and add another governed operation. Treating h1
as 15m, treating absent fields as zero, or accepting a filtered/incomplete
trade list was rejected as fabricated evidence.

## Source Governor and campaign budget

Migration `039_snapshot_readiness_contract_repair.sql` adds a fixed four-operation
completion reservation alongside the existing two DexScreener operations. The
complete path therefore reserves six operations for two selected candidates:

| Work | Worst-case operations |
|---|---:|
| Pump finalized discovery | 12 |
| Combined zero-source validation | 9 |
| Three candidates x five holder transports | 15 |
| Two DexScreener base snapshots | 2 |
| Two GeckoTerminal OHLCV + two trades | 4 |
| Total | **42** |
| Ceiling / remaining margin | **45 / 3** |

The deterministic candidate cap is now three:
`floor((45 - 12 - 9 - 6) / 5) = 3`. The ledger stores the base and completion
reservations separately, charges actual transports, and the report exposes
both plus their total. Existing E.25 DB-only replay remains byte-stable because
the reporter detects the historical schema and does not invent migration-039
fields.

## Implementation

- `snapshot_readiness_contract.py` owns strict base/readiness validation,
  exact-15m merge rules, provenance checks and E.19 zero validation.
- `snapshot_readiness_owner.py` owns the bounded one-Dex/one-OHLCV/one-trades
  sequence, actual operation count and early base failure.
- Snapshot persistence has an explicit strict-readiness mode. It validates
  primary and supplemental lineage/freshness before inserting, labels the
  contract, and stores the exact 15m provenance and six-operation reservation.
  Generic historical persistence remains compatible.
- GeckoTerminal OHLCV selection is response-order independent. Trades are now
  unfiltered, malformed rows fail the entire evidence item, and transaction
  counting uses the identical OHLCV window.
- Runtime composition passes the selected OHLCV window directly into the trade
  collector so in-memory ordering cannot change semantics.
- The bounded report understands both migration-038 historical ledgers and the
  migration-039 readiness reservation.

## Offline proof

The isolated E.26 fixture/proof suite proves:

- one exact-mint/pair base response plus exact completed 15m OHLCV and aligned
  trades produces one accepted strict readiness snapshot;
- positive price/liquidity, 5m and wider activity remain Dex-owned;
- missing liquidity blocks before either GeckoTerminal operation;
- missing 15m evidence fails closed in strict persistence;
- E.19 verified inactivity accepts contract-supported zero normalization, while
  invalid zero provenance and positive wider activity are rejected;
- stale, malformed, exact-target mismatch and conflicting supplemental evidence
  are rejected;
- OHLCV selection does not depend on response order and uses exact 900-second
  boundaries;
- filtered or malformed trade evidence cannot be called complete;
- three governed transports are charged for a fully composed candidate and no
  hidden retry/rotation exists;
- the candidate cap is three, the full two-candidate snapshot reservation is
  six, the ceiling remains 45 and worst case is 42;
- durable DB-only replay retains source lineage and exact-window provenance;
- campaign cleanup is terminal, integrity is `ok`, foreign-key violations are
  zero, and all forbidden memory/financial deltas are zero.

## Deterministic replay, cleanup and forbidden capabilities

The proof uses canonically migrated isolated databases only. Rebuilding the
strict readiness report from persisted rows requires no fixture transport or
lost process state. The strict path writes no tracking lifecycle, main/support
window, memory, retrieval, decision, position, trade-event, audit or PnL row.
Cleanup assertions require no pending/running campaign-owned discovery work.
Integrity and foreign keys pass after closeout.

No source ceiling changed; no endpoint rotation, paid source, retry loop,
scoring/ranking/confidence, wallet, private key or execution capability was
added. V2-9.7F and V2-9.8 were not begun.

## Money-usefulness contribution

The repair prevents a clean transport response or successful row insertion from
masquerading as market readiness. It protects future clean memory and paper
outcome realism from missing liquidity, fabricated 15m activity, filtered
transaction undercounts and window mismatch. Reserving the complete source path
also prevents holder evaluation from exhausting the evidence needed to assess
both selected candidates within the existing free budget.

## Functionality Risks / Setbacks / Efficiency Blockers

- GeckoTerminal network behavior is only fixture/offline proven in this lane.
  A separately authorized bounded readiness proof must confirm the fixed live
  endpoints, current schemas, cache/freshness behavior and exact-window
  returned-set assumptions.
- Very young pairs may still have absent DexScreener liquidity. The design
  intentionally blocks them without spending the two supplemental operations;
  it does not create source data that does not exist.
- GeckoTerminal returns at most 300 recent trades. Highly active pools whose
  returned history does not reach the exact window start fail closed rather
  than report a partial transaction count.
- Raw E.25 DexScreener bodies were not retained, so the audit can prove the
  normalized null and direct mapping but cannot distinguish provider omission
  from provider-emitted null at the byte level.
- The lower candidate cap may reduce replacement opportunity from four to
  three. That is the required cost of preserving two complete readiness paths
  without raising the 45-operation ceiling.
- The strict owner is readiness-proof-only. It does not activate lifecycle
  windows or authorize operational memory growth.

## Readiness and what remains locked

The contract repair is ready only for consideration of one separately approved
bounded live readiness proof. Such a proof must produce exactly two
holder-eligible candidates, two positive-liquidity DexScreener bases, four
valid exact-window GeckoTerminal supplements (unless E.19 verified inactivity
legitimately avoids them), correct operation accounting, clean cleanup and
zero-source deterministic replay.

This PASS does not authorize that proof, a full pilot, lifecycle activation,
5m/15m/1h/4h memory, corpus mutation, retrieval, decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL, wallets, paid sources, V2-9.7F or V2-9.8.