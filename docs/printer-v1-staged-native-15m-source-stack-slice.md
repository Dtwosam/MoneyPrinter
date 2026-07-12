# Printer V1 - Governed Staged/Native 15m Evidence Runtime Handoff

**Status:** IMPLEMENTED AND BOUNDED LIVE PROOF COMPLETE.

**Verdict:** `STAGED_NATIVE_15M_EVIDENCE_PASS`

This report closes the runtime-wiring blocker identified after commit
`54509d7` and documented by commit `28cb223`. The repair connects the existing
GeckoTerminal 15m evidence calculations to the bounded, governed production
discovery handoff without changing those calculations.

## Scope And Locks

This lane implements only pool-bound GeckoTerminal evidence for:

- `price_change_15m` from completed 15m candle arithmetic;
- `volume_15m` from the same provider candle;
- `txns_15m` from bounded pool trades when completeness is proven.

It does not implement broad GeckoTerminal expansion, PumpPortal, PumpSwap,
A3, A4, GROUP_A repair, scoring, ranking, confidence logic, paid APIs, memory
generation, retrieval, paper decisions, BUY, SELL, HOLD, positions, trade
events, paper audits, PnL, or a 1h proof.

## Production Call Path

The normal opt-in governed path is:

1. `main_discover_candidates_once()` receives explicit operator approval and
   `--enrich-15m-market-evidence`.
2. `build_discover_candidates_once_payload()` executes bounded discovery
   through Source Governor.
3. `_select_discovery_candidates()` applies existing Solana, identity,
   activity, dedupe, STNP, and tracking gates.
4. Only the first accepted eligible Solana pool is passed to
   `enrich_eligible_geckoterminal_candidate_15m()`.
5. The helper issues exactly two pool-bound governed requests:
   `geckoterminal_ohlcv_15m` and
   `geckoterminal_pool_trades_15m`.
6. `GeckoTerminalAdapter.execute()` validates governor context and exact
   requested pool identity.
7. Request-kind-specific normalization preserves the provider payload only
   when network and pool match.
8. `enrich_candidate_15m_ohlcv()` and
   `enrich_candidate_15m_trades()` apply the existing fail-closed evidence
   calculations.
9. Valid evidence is merged into that exact candidate before
   `process_discovery_payload()` persists discovery/tracking handoff metadata.
10. Existing selection metadata extraction and `record_token_snapshot()` carry
    values, source kinds, provenance, and governed source IDs forward.

No source call bypasses Source Governor. The enrichment path does not enqueue
its own scheduler job or create an independent snapshot engine.

## Endpoint And Normalizer Repair

The implementation now constructs request-kind-specific endpoints containing
the intended Solana pool address:

```text
https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=15&limit=2&currency=usd&token=base
https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/trades?trade_volume_in_usd_greater_than=0
```

Neither request can fall back to `new_pools` or `trending_pools`.

OHLCV normalization requires `data.attributes.ohlcv_list`. Trades
normalization requires a `data` list. Both require exact agreement among:

- candidate `pair_address`;
- governed request `pool_address`;
- transport-bound response pool address;
- Solana network identity.

Malformed, stale, failed, mismatched, or non-Solana evidence fails closed and
is not merged.

## Evidence And Provenance Handoff

The following metadata now survives candidate normalization, discovery
persistence, selection-batch metadata, and authorized snapshot persistence:

- `price_change_15m`;
- `price_change_15m_source_kind`;
- `price_change_15m_provenance`;
- `volume_15m`;
- `volume_15m_source_kind`;
- `volume_15m_provenance`;
- `txns_15m`;
- `txns_15m_source_kind`;
- `txns_15m_completeness`;
- `txns_15m_provenance`;
- `market_15m_evidence_requests`;
- `market_15m_evidence_pool_address`.

Each provenance object carries the exact pool, request kind, endpoint,
timestamps, source request ID, and source response ID. Staged derivation still
protects `PROVIDER_CANDLE_DERIVED` evidence from overwrite.

`txns_15m` remains NULL with `TRADE_HISTORY_TRUNCATED` whenever complete
coverage cannot be proven.

## Bounded Live Proof

Persistent DB:

`data/printer_v1.sqlite3` (read-only for this proof)

Fresh isolated retry DB:

`data/printer_v1_v2_2h_15m_runtime_handoff_live_retry.sqlite3`

Eligible existing Solana pool:

`6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp`

Token mint:

`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`

Bounds:

- one eligible pool;
- one OHLCV request;
- one trades request;
- five-second timeout per request;
- no broad discovery;
- no retries or endpoint rotation inside the attempt;
- isolated DB writes only.

The first eligible pool returned only stale completed candles and therefore
produced no price/volume evidence. The lane-authorized retry used the pool
above in a fresh isolated DB and passed.

### Live Values

- `price_change_15m`: `-0.029883`
- `volume_15m`: `138.904036455148`
- `txns_15m`: `15`
- `txns_15m_completeness`: `TRADE_HISTORY_COMPLETE`
- price/volume source kind: `PROVIDER_CANDLE_DERIVED`
- transaction source kind: `PROVIDER_TRADES_WINDOW`
- completed candle: `2026-07-12T15:15:00+00:00` through
  `2026-07-12T15:30:00+00:00`
- candle age after completion: `130` seconds
- candle open: `0.000004032143867780203`
- candle close: `0.000004030938956966733`

Trades completeness was proven by `oldest_reaches_window`; 300 records were
returned and 15 fell inside the exact bounded window.

### Governed Trace

OHLCV:

- source request ID: `1119`
- source response ID: `1072`
- source failure ID: NULL
- source status: `COMPLETE`
- data quality: `CLEAN_DATA`

Trades:

- source request ID: `1120`
- source response ID: `1073`
- source failure ID: NULL
- source status: `COMPLETE`
- data quality: `CLEAN_DATA`

Both actual endpoints contained the exact intended pool. No fallback discovery
channel was used.

### Snapshot Proof

The existing authorized snapshot recorder created isolated proof snapshot
`1013` with:

- `price_change_15m = -0.029883`;
- `volume_15m = 138.904036455148`;
- `txns_15m = 15`;
- all three source-kind annotations;
- completeness label;
- both governed request/response traces in normalized snapshot metadata.

Fixture integration tests additionally prove the same metadata survives normal
discovery candidate persistence and selection-batch metadata extraction.

## Row-Delta And Persistent-DB Proof

Allowed isolated proof deltas:

- source requests: `+2`;
- source responses: `+2`;
- source failures: `0`;
- token snapshots: `+1`.

Zero isolated proof deltas:

- scheduler jobs;
- tracking queue;
- memory windows;
- memory retrieval queries;
- memory retrieval matches;
- paper decisions;
- paper positions;
- paper trade events;
- paper trade audits;
- PnL tables (none present in the core count surface).

Persistent DB SHA-256 before and after:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Persistent inspected row counts were unchanged.

## Tests And Checks

Scoped suites:

- existing GeckoTerminal 15m evidence tests;
- existing bounded 15m proof tests;
- existing staged 15m derivation regression tests;
- new governed runtime-handoff tests.

Result: `130 passed` (original 124 plus 6 repair tests).

The repair tests cover endpoint construction, no fallback, request-specific
normalization, exact pool matching, provenance merge, malformed/stale/failed
fail-closed behavior, the two-request cap, truncated trades, staged overwrite
protection, ineligible candidates, discovery metadata, selection metadata,
snapshot persistence, and governor/scheduler boundaries.

## Money-Usefulness Contribution

Printer can now attach a real completed 15m price movement, native candle
volume, and safely bounded transaction activity to the same eligible pool.
This improves future memory evidence realism without treating the fields as a
trade signal or forcing clean memory.

## Remaining Limitations

- Enrichment is explicit opt-in and limited to one accepted pool per command.
- Provider candles may be absent or stale for quiet pools; evidence then stays
  unset.
- The trades endpoint can hit its record cap; `txns_15m` stays NULL unless the
  returned history reaches the window start.
- This lane proves the handoff but does not activate memory or decisions.
- Broader pool rotation and source budgeting remain later governed work.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Current control | Remaining action |
|---|---|---|
| Evidence attaches to the wrong pool | Exact request/candidate/response pool match | Preserve regression tests |
| Discovery endpoint fallback recurs | Dedicated endpoint builder by request kind | Keep fallback forbidden |
| In-progress or stale candle is used | Completed/fresh candle gate | Leave evidence unset |
| Trade history is truncated | Completeness label and NULL count | Do not infer missing trades |
| Provider requests expand with candidate count | One accepted pool, exactly two requests | Future expansion needs a separate budget lane |
| Provider evidence is overwritten | Staged-derivation source-kind guard | Preserve guard tests |
| Evidence becomes a trade signal | Fields remain metadata only | Retrieval/paper/BUY locks remain |

## Acceptance And Next Lane

- Correct pool-address endpoints: PASS.
- Request-specific normalization: PASS.
- Source Governor recording: PASS.
- Production candidate enrichment: PASS.
- Discovery and selection metadata handoff: PASS.
- Authorized snapshot persistence: PASS.
- Real governed provider proof: PASS.
- Persistent DB isolation: PASS.
- Financial and downstream locks: PASS.

Blocker 2 is genuinely closed for the bounded one-pool 15m runtime handoff.

Next lane only:

`Minimal PumpPortal launch-stream bounded transport`

Do not begin it from this report. A3, A4, V2-3, memory, retrieval, and all
paper/financial capabilities remain paused.
