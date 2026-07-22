# Printer V1 V2-9.7E.29 Post-Preflight Bounded Readiness Proof

## Verdict

`V2_9_7E_29_BLOCKED_SNAPSHOT_READINESS`

The exactly one authorized live cycle completed once. It produced two
deterministic finalized Pump-origin candidates and exactly two holder-evidence-
eligible selections through the fixed Helius Free backup. Both exact-pair
DexScreener requests then returned clean, identity-matched responses with
positive current/wider activity but no usable liquidity. The strict E.26 owner
therefore stopped before GeckoTerminal and persisted no readiness snapshot.
No retry, restart, successor or second execution occurred.

## Baseline and authorization

- Exact baseline: `6b027d969b9d844b834a4231ab7a48641bc84bfe`
- Baseline message: `Close readiness source contract preflight`
- Tracked tree at entry and immediately before live use: clean
- Authorization: exactly one bounded live readiness cycle
- Authorization consumed at: `2026-07-22T22:25:23.954724+00:00`
- Live execution count: 1
- Second execution: none
- Durable single-use marker:
  `C:\Users\dtwof\PrinterPilot\E29\single-live-authorization-consumed.json`
- Marker SHA-256:
  `9edc3af21952693ea36398a4663ce65b92b7456d247bd863b1b74e7288df404a`

The marker was written immediately before the first possible Pump request. The
live runner was not invoked again after the block.

## Preflight and isolation

- No Python/Printer runtime process, active proof supervision, active campaign
  supervision or lock/lease file existed.
- The historical E.15 database retains a stale `RUNNING` campaign label, but
  its proof supervision is terminal, its lease is expired, its process ID is
  absent and its lock file is absent. It was not an active campaign and was not
  mutated.
- E.29 did not exist before preparation. A new canonically migrated,
  non-authoritative database was created at
  `C:\Users\dtwof\PrinterPilot\E29\printer-v1-e29-readiness.sqlite3`.
- Reports are under `C:\Users\dtwof\PrinterPilot\E29\reports\`; the byte-
  identical pre-live backup is
  `C:\Users\dtwof\PrinterPilot\E29\backups\printer-v1-e29-pre-live.sqlite3`.
- Migration head: `039_snapshot_readiness_contract_repair.sql`.
- Initial integrity: `ok`; foreign-key violations: 0.
- Initial lifecycle, memory, retrieval and financial rows: 0.
- Consolidated readiness-source preflight: `READY`, issues `[]`, external
  requests 0, Helius secret present, secret material recorded false.
- Operation ceiling: 45; candidate cap: 3; complete snapshot reservation: 6.
- Source Governor and Central Scheduler owner ports were present.
- No fixture plan, compressed clock or lifecycle activation was supplied.

The operator-owned Helius key was resolved from the user-scoped
`PRINTER_HELIUS_API_KEY` secret into the live process only. Its value was never
printed, copied into command arguments, persisted in evidence or included in
this closeout. An independent byte scan of the final DB, marker and redacted
report found no key bytes.

Preflight report SHA-256:
`36ea4af61f64b7e58b566654ecbe3f97e3ea521cbaf9b897d84671e5f85e245e`.

## Exact live request timeline

All timestamps are UTC. Requests were sequential.

| Time | Operation | Result | Transport operations |
|---|---|---|---:|
| 22:25:23.958724–22:25:26.830850 | Pump finalized `getSignaturesForAddress`, pages 1–3 | complete | 3 |
| 22:25:26.856862–22:25:33.524566 | Pump finalized `getTransaction`, 10 deterministic decodes | complete | 10 |
| 22:25:33.699663–22:25:34.664477 | Candidate 1 GoPlus exact-mint safety reference | complete; holder unknown | 1 |
| 22:25:34.666473–22:25:35.139276 | Candidate 1 public RPC holder request | `solana_rpc_rate_limited` | 1 |
| 22:25:35.139276–22:25:36.764669 | Candidate 1 fixed Helius, two finalized methods | complete exact target | 2 |
| 22:25:36.767195–22:25:37.593126 | Candidate 2 GoPlus exact-mint safety reference | complete; holder unknown | 1 |
| 22:25:37.593126–22:25:38.158290 | Candidate 2 public RPC holder request | `solana_rpc_rate_limited` | 1 |
| 22:25:38.158290–22:25:39.184886 | Candidate 2 fixed Helius, two finalized methods | complete exact target | 2 |
| 22:25:39.422163–22:25:40.243272 | Candidate 1 DexScreener exact-pair base | complete; liquidity missing | 1 |
| 22:25:40.425210–22:25:41.073684 | Candidate 2 DexScreener exact-pair base | complete; liquidity missing | 1 |

The two DexScreener starts were 1.003047 seconds apart, satisfying Printer's
60/minute local pacing. GeckoTerminal calls were zero because the committed
strict base gate rejected missing liquidity before supplemental work. Thus the
repaired GeckoTerminal six-second pacing/header contract was admitted by
preflight but not exercised live in this blocked cycle.

## Candidate and holder-eligibility funnel

Pump finalized acquisition performed 13 operations and supplied candidates in
the committed deterministic order. Exactly two were evaluated, both became
eligible, and selection stopped. Candidate replacement was not required. No
score, rank, confidence, weighting or discretionary reordering was used.

| Order | Redacted mint | Redacted pair | GoPlus | Public RPC | Helius Free | Result |
|---:|---|---|---|---|---|---|
| 1 | `sha256:e5c8202b98df1a51756682b1768e1e8e22535fcf5ff3532d15a83bee68137b5b` | `sha256:0948380fde817efaec0599dc5c8fb4efa7efdb32b89329f85274d80586c93d67` | exact, clean, holder unknown | finalized rate limit | exact, clean, slot 434594342, `HOLDER_CONCENTRATION_EXTREME` | eligible and selected |
| 2 | `sha256:46ecb43c70bf6dee46eed0a02c34785c3a7795d4ab7cb973c49a19de26997013` | `sha256:172215695955a69c20f07f250b73dc5757568b7d3f27e88bd870113f9b7458b6` | exact, clean, holder unknown | finalized rate limit | exact, clean, slot 434594349, `HOLDER_CONCENTRATION_EXTREME` | eligible and selected |

The selected identities exactly equal the two eligible identities. Helius ran
only after the allowlisted transient public-RPC failure, on the fixed redacted
host `mainnet.helius-rpc.com`, using finalized
`getTokenLargestAccounts+getTokenSupply`. The rate-limit failures retained
transport-failure precedence and were not mislabeled target mismatch.

Holder eligibility here proves the availability of exact holder evidence. The
factual `HOLDER_CONCENTRATION_EXTREME` labels are not claims that either token
is safe or suitable for memory.

## Snapshot-readiness evidence

Both DexScreener responses were `COMPLETE` / `CLEAN_DATA` and matched the exact
selected mint/pair. Neither passed the required base contract:

| Field | Candidate 1 | Candidate 2 |
|---|---:|---:|
| Price USD | 0.000002179 | 0.000002179 |
| Liquidity USD | missing | missing |
| Price change 5m | -1.65% | -1.35% |
| Volume 5m | 38.97 | 31.18 |
| Transactions 5m | 2 | 2 |
| Price change 1h | -1.65% | -1.35% |
| Volume 1h / transactions 1h | 38.97 / 2 | 31.18 / 2 |
| Price change 24h | -1.65% | -1.35% |
| Volume 24h / transactions 24h | 38.97 / 2 | 31.18 / 2 |

For both bundles the first blocker was
`READINESS_MISSING_OR_INVALID:liquidity_usd`. Under E.26, GeckoTerminal cannot
replace DexScreener base liquidity, so no OHLCV or trades request was permitted.
No 15m evidence was accepted and no token snapshot row was inserted.

### Zero normalization

No zero normalization occurred. Both candidates had missing liquidity and
positive wider-window activity. They therefore failed the existing verified-
inactivity predicate; treating missing liquidity or 15m fields as zero would
have fabricated evidence.

## Source and campaign accounting

| Account | Operations |
|---|---:|
| Pump finalized discovery | 13 |
| Combined zero-source validations | 9 |
| Two GoPlus requests | 2 |
| Two public-RPC failures | 2 |
| Two two-method Helius responses | 4 |
| Two DexScreener bases | 2 |
| GeckoTerminal OHLCV/trades | 0 |
| **Total charged** | **32** |
| Ceiling / remaining margin | **45 / 13** |

The durable ledger records 21 governed requests, 23 underlying transport
operations, 9 zero-transport validations, 2 reserved Dex operations and 4
reserved supplemental operations. Source tables contain 8 governed source
requests, 6 responses and 2 failures; the separate durable Pump ledger contains
13 operations.

Actual work remained within 45 and preserved the six-operation snapshot path.
However, E.28's static worst-case budget assumed 12 Pump operations while this
committed acquisition used 13 (three signature pages plus ten transaction
decodes). The candidate cap remained safely 3 and this cycle retained 13
operations of margin, but the frozen preflight worst-case total of 42 is
understated by at least one for the observed acquisition shape.

## Cleanup, integrity and deterministic replay

- Campaign, run and cycle: `TERMINAL_BLOCKED` with immutable first cause
  `V2_9_7E_29_BLOCKED_SNAPSHOT_READINESS`.
- Active tracking rows: 0.
- Pending/running/cooldown Scheduler jobs: 0.
- Active campaign-owned Scheduler work: 0.
- Waiting/due holder maturation rows: 0.
- Lifecycle windows, retrieval, decisions, positions, trade events, audits and
  PnL: 0.
- Integrity: `ok`.
- Foreign-key violations: 0.
- DB-only report hashes:
  `2975ca01fbf3777f1ce9a235a5e8a4bab4a4d4a0908594bf7fbfac3b35f1187e`
  and
  `2975ca01fbf3777f1ce9a235a5e8a4bab4a4d4a0908594bf7fbfac3b35f1187e`.
- Replay source requests: 0.
- Final isolated DB SHA-256:
  `885b0fba80a34016635dd1f7dd9c5d7d324c75fe2a7fcdf9a6589c6ee6ef5e6f`.
- Redacted evidence SHA-256:
  `c254d99790b3dc4df30994e2557fcfd9660567bbf05613db6565cfdc7b75078e`.

No lifecycle, support-only 5m, memory generation/promotion, corpus mutation,
retrieval or financial capability was activated.

## Money-usefulness contribution

The cycle reconfirms that fixed Helius Free redundancy can recover two exact-
mint holder facts after shared public-RPC rate limits without exceeding the
campaign ceiling. More importantly, Printer refused to call active young-pair
data ready when exit-liquidity evidence was absent. That prevents a future
clean-memory or paper-profit claim from resting on an asset whose realistic
entry/exit capacity was not observed.

## Functionality Risks / Setbacks / Efficiency Blockers

- DexScreener again returned exact active pairs without usable liquidity. The
  same base blocker seen in E.25 remains live after the 15m source repair.
- Because base liquidity failed first, GeckoTerminal OHLCV/trades and their
  repaired pacing/header contract did not receive live proof.
- The static Pump allowance is stale: the committed path performed 13 rather
  than the preflight's frozen 12 operations. This did not breach E.29, but the
  consolidated budget must represent the true bounded acquisition maximum.
- Public Solana RPC rate-limited both holder requests. Helius worked twice, but
  continued readiness still depends on the operator-owned free-tier key.
- Both holder facts were concentration-extreme. Evidence eligibility must not
  be confused with token quality or safety approval.
- A compliant way to obtain or defer until positive exact-pair liquidity is
  available remains unresolved. E.26 forbids filling Dex-owned liquidity from
  GeckoTerminal, and this proof correctly did not weaken that rule.

## Readiness for a full pilot and required next proof

Printer is **not ready** for a full V2-9.7E two-token pilot. PASS requires two
complete snapshot bundles; E.29 produced zero.

Before another live readiness cycle can be considered, a separate audit/repair
must:

1. reconcile the Pump worst-case operation budget with the observed bounded
   13-operation acquisition while keeping the ceiling at 45;
2. define a compliant fixed-source or bounded-maturity contract for positive
   exact-pair liquidity without fabricating, substituting or weakening E.26;
3. prove the revised base-liquidity path offline while preserving the complete
   two-candidate 15m reservation, deterministic order and fail-closed rules;
4. receive a new explicit one-cycle authorization.

This block does not authorize another E.29 execution, a full pilot, lifecycle
windows, memory creation/promotion, corpus mutation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, V2-9.7F or V2-9.8.
