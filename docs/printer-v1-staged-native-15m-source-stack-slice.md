# Printer V1 - Staged/Native 15m Evidence Source-Stack Slice

**Status:** PARTIAL IMPLEMENTATION VERIFIED; PRODUCTION LIVE HANDOFF BLOCKED.

**Verdict:** `STAGED_NATIVE_15M_EVIDENCE_PARTIAL_WITH_LIVE_OR_WIRING_BLOCKER`

This document records the state verified after commit `54509d7` (`Integrate
governed 15m market evidence`). It supersedes the earlier design-only wording
in this file. The commit adds bounded evidence helpers and Source Governor
request-kind registration, but normal governed discovery and snapshot runtime
do not yet execute the 15m enrichment path.

## 1. Scope And Locks

This slice covers only:

- GeckoTerminal completed 15m OHLCV evidence for `price_change_15m` and
  `volume_15m`;
- GeckoTerminal bounded pool-trade evidence for safely complete `txns_15m`;
- candidate normalization and snapshot persistence compatibility;
- protection against staged derivation overwriting provider candle evidence.

It does not enable memory creation, retrieval, paper decisions, BUY, SELL,
HOLD, positions, trade events, paper audits, or PnL. No paid API, scoring,
ranking, confidence, weighted logic, A3, A4, PumpPortal, or broad
GeckoTerminal expansion is part of this slice.

## 2. Commit Record

Commit `54509d7` changed only:

- `src/printer_v1/sources/geckoterminal_15m.py` (new);
- `src/printer_v1/sources/geckoterminal.py`;
- `src/printer_v1/sources/registry.py`;
- `src/printer_v1/snapshots/staged_derivation.py`;
- `tests/test_v2_2h_geckoterminal_15m_evidence.py` (new);
- `tests/test_v2_2h_geckoterminal_15m_bounded_proof.py` (new);
- this document.

The commit did not change a discovery runner, scheduler runner, snapshot runner,
memory path, retrieval path, or paper-trading path.

## 3. Implemented Evidence Logic

The helper module implements:

- `enrich_candidate_15m_ohlcv()` using a completed, fresh 15m candle;
- `price_change_15m = ((close - open) / open) * 100`;
- `volume_15m` from that candle's native USD volume;
- `enrich_candidate_15m_trades()` over an exact 15m interval;
- `txns_15m` only when trade-history completeness is proven;
- `txns_15m = NULL` with `TRADE_HISTORY_TRUNCATED` when completeness is not
  proven;
- provenance labels `PROVIDER_CANDLE_DERIVED` and
  `PROVIDER_TRADES_WINDOW`.

`apply_staged_derivation()` protects both `NATIVE_SOURCE` and
`PROVIDER_CANDLE_DERIVED` price evidence from overwrite.

The Source Governor registry and GeckoTerminal adapter contract allow:

- `geckoterminal_ohlcv_15m`;
- `geckoterminal_pool_trades_15m`.

These facts prove helper and contract readiness. They do not prove production
runtime invocation.

## 4. Production Call-Path Trace

The normal governed discovery path is:

1. `main_discover_candidates_once()` parses the operator command.
2. `build_discover_candidates_once_payload()` creates a bounded source plan.
3. `_execute_plan_item()` builds a governed request and executes the
   GeckoTerminal adapter through governed source recording.
4. `normalize_geckoterminal_payload()` normalizes a pool-list response.
5. `normalize_candidates()` creates candidate dictionaries.
6. `process_discovery_payload()` persists accepted discovery and tracking
   handoff rows.

The production path does not import or invoke either 15m enrichment helper.
Repository references to `enrich_candidate_15m_ohlcv()` and
`enrich_candidate_15m_trades()` are confined to the helper module and tests.

The production request plan contains only GeckoTerminal new-pool and trending
channels. The endpoint map contains only those two endpoints. Supplying a 15m
request kind inserts it into the plan, but endpoint resolution falls back to
the new-pools endpoint. The adapter then uses pool-list normalization rather
than OHLCV/trades normalization.

Therefore normal governed discovery/selection does not actually call either
15m provider endpoint.

## 5. Candidate And Snapshot Handoff

The generic candidate parser has fields for `price_change_15m`, `volume_15m`,
and `txns_15m`. The generic snapshot recorder also has DB columns for all three
fields and stores normalized payload metadata. Fixture tests prove that a
caller-supplied enriched payload can pass through these generic layers.

Production handoff is not proven because the governed runtime never merges the
OHLCV/trades enrichment into the candidate payload. No normal runtime source
response containing the enrichment reaches candidate metadata, and no normal
snapshot runner consumes such a response.

The existing E2M snapshot persistence path is DexScreener-specific and inserts
NULL for all three 15m fields. It is not a GeckoTerminal 15m persistence path.

## 6. Bounded Live Proof

One operator-approved live call was run against isolated DB:

`data/printer_v1_54509d7_15m_handoff_proof.sqlite3`

Bounds:

- source: `geckoterminal`;
- requested kind: `geckoterminal_ohlcv_15m`;
- max source requests: 1;
- max candidates: 1;
- timeout: 5 seconds;
- chain: Solana;
- persistent DB not used for writes.

Observed result:

- source requests: +1;
- source responses: +1;
- source failures: +0;
- actual endpoint: GeckoTerminal Solana `new_pools?page=1`;
- actual source channel: `GECKOTERMINAL_NEW_POOL`;
- candidates seen: 20;
- discovery candidates persisted: 1;
- tracking queue rows: +1;
- scheduler jobs: +1;
- token snapshots: +0;
- `price_change_15m`: NULL;
- `volume_15m`: NULL;
- `txns_15m`: NULL.

This was a governed call, but it was not a valid 15m evidence call. It proves
the endpoint/normalizer/runtime wiring blocker rather than 15m evidence
success.

## 7. Downstream Lock Proof

On the isolated proof DB, the live call produced zero deltas for:

- token snapshots;
- memory windows;
- memory retrieval queries and matches;
- paper decisions;
- paper positions;
- paper trade events;
- paper trade audits;
- PnL (no active PnL table was found in the core count surface).

The persistent DB SHA-256 remained:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Its inspected core row counts were unchanged by the proof.

## 8. Blocker And Required Repair

Blocker 2 is not closed. A future narrow repair must:

1. add pool-address-aware governed endpoint construction for both 15m request
   kinds;
2. add request-kind-specific OHLCV and trades normalization rather than
   pool-list normalization;
3. invoke both enrichments for an already eligible Solana pool under explicit
   request limits;
4. merge only valid evidence into candidate metadata;
5. carry source response IDs and provenance through snapshot persistence;
6. keep `txns_15m` null unless completeness is proven;
7. prove all downstream lock deltas remain zero.

This repair should remain a narrow GeckoTerminal 15m runtime-handoff lane. It
must not become broad GeckoTerminal discovery work.

## 9. Acceptance State

- Helper arithmetic and completeness guards: PASS.
- Request-kind registry/contract allowance: PASS.
- Candidate parser field compatibility: PASS by fixture.
- Generic snapshot field compatibility: PASS by fixture.
- Normal governed endpoint invocation: FAIL / NOT WIRED.
- Production candidate enrichment: FAIL / NOT WIRED.
- Production snapshot persistence from live 15m evidence: FAIL / NOT WIRED.
- Persistent DB isolation and downstream locks: PASS.

## 10. Next Lane

Next lane:

`Narrow GeckoTerminal 15m governed runtime-handoff repair and bounded proof`

`Minimal PumpPortal launch-stream bounded transport` is allowed only after this
slice receives a clean governed live handoff pass. A3, A4, staged/native 15m
activation, V2-3, retrieval, and paper features remain paused.
