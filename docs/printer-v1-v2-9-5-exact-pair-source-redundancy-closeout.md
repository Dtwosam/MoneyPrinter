# Printer V1 V2-9.5 Exact-Pair Source Redundancy Closeout

## Verdict

`V2_9_5_SOURCE_REDUNDANCY_PASS`

Lane: `V2-9.5 - Unified Exact-Pair Snapshot Source Redundancy`

V2-9.5 removes DexScreener as a single point of failure for the mandatory
exact-pair market snapshot by adding one safe, Source-Governed GeckoTerminal
fallback. DexScreener stays primary; GeckoTerminal is attempted **at most once**,
and only after an *eligible transient* DexScreener transport failure. The
fallback is deterministic-proof green, changes no cadence, deadlines, budgets,
supervision, replay, isolation, or downstream locks, and never runs a live
source during tests. No live source call, Attempt 5, or V2-10 work was
performed.

## Gate 1 - provider compatibility result

GeckoTerminal can safely satisfy the mandatory exact-pair snapshot contract via
its free/public single-pool endpoint
(`/api/v2/networks/solana/pools/{pool_address}`). Every mandatory field maps
1:1; no field is weakened and no partial fields are combined across providers:

| Mandatory field | DexScreener (primary) | GeckoTerminal (fallback) |
| --- | --- | --- |
| Exact Solana token identity | `baseToken.address` | `relationships.base_token.data.id` (strip `solana_`) |
| Exact pair identity | `pairAddress` | `attributes.address` (pool address) |
| Price | `priceUsd` | `attributes.base_token_price_usd` |
| Liquidity | `liquidity.usd` | `attributes.reserve_in_usd` |
| Volume | `volume.{m5,h1,h24}` | `attributes.volume_usd.{m5,h1,h24}` |
| Transactions | `txns.{...}.buys+sells` | `attributes.transactions.{m5,h1,h24}.{buys,sells}` |
| FDV or market cap | `fdv` / `marketCap` | `attributes.fdv_usd` / `attributes.market_cap_usd` |
| Pair age | `pairCreatedAt` | `attributes.pool_created_at` |
| Timestamp / freshness | `received_at` + `source_status` | `received_at` + `source_status` |
| Source attribution | `source_name=dexscreener` | `source_name=geckoterminal` |
| Data-quality handling | normalized `data_quality_label` | normalized `data_quality_label` |

Compatibility result: **not blocked.** The fallback normalization requires every
mandatory field (identity, price, liquidity, FDV-or-market-cap, 24h volume, 24h
transactions, pair age); any missing mandatory field, wrong pair, wrong token,
non-Solana network, staleness, or malformed body fails closed with
`MISSING_CRITICAL_DATA` so the fallback never persists partial or wrong-pair
evidence.

## Gate 2/3 - exact implementation and source/budget behavior

Smallest necessary production changes:

- `src/printer_v1/sources/registry.py`: add `pair_market_snapshot` to
  GeckoTerminal's `allowed_request_kinds` (the registry is the source of truth
  the Source Governor and adapter contract validate against). Same request kind
  as the DexScreener primary; the `source_name` distinguishes the provider.
- `src/printer_v1/sources/geckoterminal.py`: add the single-pool transport
  (`build_geckoterminal_pair_snapshot_transport`) and a strict exact-pair
  normalizer (`_normalize_geckoterminal_pair_snapshot`) that enforces
  network=solana, exact pool address, exact base-token mint, non-stale, and all
  mandatory fields, emitting the identical `pairs:[{...}]` snapshot shape the
  DexScreener path already produces. `execute()` now also passes the requested
  `token_mint` for identity matching.
- `src/printer_v1/sources/dexscreener.py`: refine the transport failure
  taxonomy so eligibility is precise -- TLS/connection/read-timeout ->
  `dexscreener_transport_failure` (eligible), HTTP 5xx ->
  `dexscreener_http_server_error` (eligible), HTTP 429 -> rate-limited
  (eligible), while JSON/decode defects and non-object bodies ->
  `dexscreener_malformed_payload` and HTTP 4xx -> `dexscreener_http_client_error`
  (both **not** eligible). The existing `dexscreener_transport_failure` and
  `dexscreener_rate_limited_fixture` strings (asserted by existing tests) are
  preserved.
- `src/printer_v1/operator_cli/exact_pair_source_redundancy.py` (new): the
  eligibility allowlist, `is_eligible_transient_primary_failure`, the default
  real GeckoTerminal fallback adapter builder, and the governed fallback
  executor.
- `src/printer_v1/operator_cli/e2m_snapshot_persistence.py`: accept a governed
  response from `{dexscreener, geckoterminal}` only (coingecko and every other
  source stay blocked), and record the true provider in the snapshot's
  normalized payload for honest attribution. `E2M_SOURCE_NAME` is unchanged.
- `src/printer_v1/operator_cli/one_command_15m_factory.py`: `_execute_snapshot`
  now performs the DexScreener primary call, and on an eligible transient
  failure performs exactly one governed GeckoTerminal fallback, threaded from
  `run_one_command_15m_factory` through the 15m / 1h / 4h step handlers.

Source and budget behavior:

- Both attempts pass through the Source Governor
  (`execute_source_request_with_governor`) and are Central-Scheduler owned (the
  fallback runs synchronously inside the already-scheduled step -- no new job,
  no new step, no cadence anchor or deadline movement).
- Both attempts are separately persisted: the primary DexScreener failure row is
  preserved, and the GeckoTerminal attempt records its own request/response or
  failure rows with request key `{run}:{step}:geckoterminal_fallback`.
- Both attempts are separately budgeted: the fallback is rate-budgeted against
  GeckoTerminal's own recent-request window, and the run-level request count
  (`_run_request_count`) counts both, so the fallback consumes real budget and
  is visible in phase-local and cumulative accounting.
- At most one snapshot per scheduled observation: the fallback runs only when
  the primary produced no snapshot; a valid fallback yields exactly one snapshot
  (attributed to GeckoTerminal); an invalid or failing fallback yields zero and
  fails closed on the preserved primary cause.
- No retry loops, no recursion, no endpoint rotation, no automatic proof reruns.
  Non-eligible primary failures (malformed, parser defect, HTTP 4xx, governor /
  budget rejection) never fall back.

## Gate 4 - proof results

Focused deterministic proof `tests/test_v2_9_5_exact_pair_source_redundancy.py`
(fixture-only, no live sources): **12 passed, 6 subtests passed.** It proves:

- primary success makes no fallback call (fallback adapter raises if built);
- each eligible transient failure (`dexscreener_transport_failure`,
  `dexscreener_http_server_error`, `dexscreener_rate_limited_fixture`) plus a
  valid fallback creates exactly one GeckoTerminal-attributed snapshot;
- both attempts stay visible (2 requests, primary failure + fallback response)
  and budgeted (`_run_request_count == 2`), primary failure preserved;
- identity mismatch (pair or token), non-Solana network, stale, missing
  mandatory field (liquidity; FDV-and-market-cap), and malformed
  (missing-`data`) fallback responses all stay blocked with zero snapshots;
- non-transient primary failures (`dexscreener_malformed_payload`,
  `dexscreener_http_client_error`, `dexscreener_fixture_failure`) do not fall
  back (1 request only, zero GeckoTerminal calls);
- a fallback failure fails closed on the preserved primary cause (2 requests,
  2 failures, zero snapshots);
- no duplicate snapshots (exactly one per observation, or zero).

Nearby regressions (fixture-only), all green:

- V2-8.1 4h runtime, V2-9.2 terminal budget, V2-9.3 early-failure accounting,
  V2-9.4 durable supervision, V2-4 / V2-5 full-runner, Source Governor / adapter
  contract, e2m persistence, DexScreener disabled-adapter: `222 passed, 14
  subtests` (excluding pre-existing drift, below).
- Cadence, continuity, long-window cadence/continuity, continuous lifecycle and
  runtime integration, 1h audit gate, Lane Q, Lane K/E2Z, E2Z clean-memory, E2Q
  audit, financial-action lock, scheduler single-tick, scheduler resource
  governor: `597 passed, 68 subtests, 0 failed`.

Cadence and fixed deadlines are unchanged (the fallback is synchronous inside
the scheduled step; the full continuous-runtime suite is green). Replay remains
source-free and read-only, and supervision, cancellation, isolation, and locks
remain green (their suites pass unchanged, and the fallback never fires on the
success path they exercise).

### Pre-existing, out-of-scope failures (not caused by V2-9.5)

Two tests fail on clean HEAD `99d2f25` **before any V2-9.5 change** and remain
failing identically after it (verified by `git stash`):

1. `tests/test_phase25_one_shot_real_source_smoke_check.py::
   test_malformed_live_style_payload_creates_no_downstream_rows` -- expects an
   empty-`pairs` payload to be `FAILED`, but the DexScreener normalizer maps
   empty pairs to `PARTIAL`. V2-9.5 does not touch that branch.
2. `tests/test_post_rc_geckoterminal_discovery_adapter.py::
   test_non_solana_pool_rejected_as_non_solana_candidate` -- expects a
   non-Solana discovery pool to yield `FAILED`, but the CLI payload reports
   `NOT_EXECUTED`. This is the `geckoterminal_new_pool_discovery` path, which
   V2-9.5 does not modify.

These are pre-existing drift (the same class the operator handled separately in
V2-9.4's V2-6 audit-gate case). They are left untouched here to keep V2-9.5 to
the smallest necessary change and are surfaced for a separate operator decision;
they do not affect the exact-pair snapshot path or the V2-9.5 verdict.

## Money-usefulness contribution and what this improves

V2-9.5 does not itself add clean memory. Its contribution is resilience: the
single most common way the bounded 4h proof has failed (a transient TLS/transport
error on the one mandatory DexScreener price snapshot, as in Attempt 4) can now
be survived by a governed, honest, exactly-once fallback to a second free/public
Solana source. This materially increases the chance that a future authorized 4h
proof reaches and closes the 4h phase, which is the prerequisite for real
medium-term clean memory. It does so without weakening any evidence rule: a
wrong-pair, stale, or incomplete fallback is refused, not accepted.

## What remains locked

Unchanged and locked: retrieval activation, paper decisions, BUY/SELL/HOLD,
paper positions, trade events, paper trade audits, PnL, wallet/private-key/live
execution, paid API dependencies, scoring/ranking/confidence/weighted logic,
embeddings/vectors, WINDOW_12H, and WINDOW_24H. WINDOW_5M_MICRO_EVENT remains
support-only. Both DexScreener and GeckoTerminal are free/public; no paid
dependency is introduced.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The fallback covers only the mandatory exact-pair price snapshot. The
   safety-context sources (GoPlus, Solana RPC holder) that made Attempt 4's 15m
   window DIRTY have no equivalent fallback yet; a clean 4h lifecycle still
   depends on those context sources staying healthy across every window close.
2. If a transient window is broad enough to take down *both* DexScreener and
   GeckoTerminal at the same observation, the run still safe-stops. Redundancy
   reduces, but cannot eliminate, free-source transport fragility over a
   multi-hour run.
3. The pre-existing phase25 / geckoterminal-discovery test drift (above) remains
   open and should be resolved in a separate operator-approved cleanup so the
   full suite can return to fully green.
4. The eligibility split now distinguishes DexScreener 4xx vs 5xx and
   parse-vs-transport failures; any future consumer that pattern-matched the old
   single `dexscreener_http_error` string would need updating (none exists in
   the tree today).

## Whether Attempt 5 is technically ready but still unauthorized

Technically, yes: the durable launcher/supervision (V2-9.4) plus this exact-pair
redundancy (V2-9.5) together address both failure modes the prior attempts
exposed (host-process disappearance and single-source transport failure). A
future Attempt 5 launched through `scripts/Start-V2-9-Proof.ps1` would exercise
both. **However, Attempt 5 remains unauthorized.** It requires a separate,
explicit operator approval and is out of scope for this lane. No Attempt 5, no
V2-10, no live source call was performed here.

## Files changed

- `src/printer_v1/sources/registry.py`
- `src/printer_v1/sources/dexscreener.py`
- `src/printer_v1/sources/geckoterminal.py`
- `src/printer_v1/operator_cli/e2m_snapshot_persistence.py`
- `src/printer_v1/operator_cli/exact_pair_source_redundancy.py` (new)
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `tests/test_v2_9_5_exact_pair_source_redundancy.py` (new)
- `docs/printer-v1-v2-9-5-exact-pair-source-redundancy-closeout.md` (this file)

## What was not touched

No cadence policy, window deadline, budget ceiling, supervision, replay,
isolation, or one-proof lock behavior changed. No live source was called. No
persistent DB was touched. No Attempt 5, V2-10, 12h, 24h, retrieval, paper
decision, position, trade, audit, or PnL work began.

## Next recommended phase

Hold. V2-9 remains BLOCKED pending a real audited 4h result. The two capabilities
that would make a further attempt worthwhile (durable supervision and exact-pair
source redundancy) are now in place and proven. Any Attempt 5, any fallback for
the safety-context sources, or the pre-existing-test cleanup each requires a new
explicit operator-approved lane.
