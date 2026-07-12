# Printer V1 A3 Late-Buy-Trap Repair Closeout

Status: `A3_WIRING_PASS_LIVE_SAMPLE_BLOCKED`

Date: 2026-07-12

Scope: A3 `LATE_BUY_TRAP` only. A4 and GROUP_A were not started.

## Audit

The existing `assign_bucket()` implementation already enforced the approved
categorical A3 contract:

- fast-tier liquidity plus 5m volume or transaction activity;
- real, known `token_age_seconds >= 3600`;
- known `price_change_1h < 0`;
- A2 wick-reversal precedence remains unchanged.

The blocker was not threshold logic. Governed T3 produced a separate Solana RPC
evidence payload, while the discovery candidate carrying market activity and
`price_change_1h` reached selection without an exact-mint T3 overlay. Discovery
persistence then normalized the market candidate again, so it also needed a
guarded rule to retain cross-source T3 provenance.

## Design

One explicitly requested discovery run may enrich at most one eligible A1-fast
Solana candidate before selection. The join contract is:

1. Market candidate and T3 requested mint match exactly.
2. T3 source status is `COMPLETE` and data quality is `CLEAN_DATA`.
3. `token_created_at`, `token_age_seconds`, and tier `T3` are present.
4. Commitment and finality status are both `finalized`.
5. A governed T3 response ID exists and no T3 failure ID exists.
6. Discovery and T3 request/response identities remain separately auditable.

No threshold was changed. Pair age, migration time, pool time, discovery time,
receipt time, first-trade time, and observed-live status remain prohibited as
token creation evidence.

## Implementation

- Added `enrich_candidate_with_governed_t3()` for one exact-mint, governed,
  finalized T3 overlay.
- Added optional `--enrich-t3-token-age` discovery support. It is off by
  default and enriches at most one eligible fast candidate.
- Added optional operator-approved free/read-only RPC endpoint input. Reports
  expose only the redacted host from T3 evidence.
- Applied enrichment before discovery selection and persistence.
- Preserved T3 through market-source re-normalization only when exact mint,
  finalized evidence, governed response identity, and no failure all agree.
- Added T3 governor IDs and the originating discovery response ID to candidate
  and selection metadata.

No A4 derivation, GROUP_A behavior, scheduler loop, memory, retrieval, paper
decision, position, trade, audit, or PnL path was changed.

## Deterministic Proof

Focused fixtures prove:

- qualifying T3 candidate becomes `A3 / LATE_BUY_TRAP`;
- token age below 3600 seconds remains A1;
- unknown token age remains A1;
- pair-age-only evidence remains A1;
- missing, zero, or positive one-hour price change cannot produce A3;
- complete T3 provenance survives candidate normalization and selection
  metadata;
- the normal governed discovery command applies T3 before classification,
  persists tier T3, and persists A3 without changing thresholds.

The combined targeted suite passed 392 tests and 48 subtests. The final focused
A3 command-path suite passed 7 tests.

## Bounded Live Proof

Proof DB:
`data/printer_v1_a3_cross_source_proof_20260712.sqlite3` (isolated; not committed)

Approved mint:
`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`

The one bounded market request used the free/public governed DexScreener
`token_market_snapshot` path. DexScreener returned no pairs for the approved
mint, producing:

- source request delta: 1
- source response delta: 0
- source failure delta: 1
- failure: `dexscreener_malformed_fixture`
- data quality: `MISSING_CRITICAL_DATA`
- candidates: 0

Because no market candidate existed, the T3 enrichment call was correctly not
made and no live A3 classification was claimed. This is market-sample absence,
not a production wiring failure. The deterministic production-path proof
establishes the cross-source handoff.

Persistent DB SHA-256 before and after was unchanged:
`97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb`.

Proof DB deltas were zero for memory windows, retrieval queries and matches,
paper decisions, paper positions, trade events, paper trade audits, and every
inspected downstream table. No PnL table existed in the inspected schema.

## Verdict

`A3_WIRING_PASS_LIVE_SAMPLE_BLOCKED`

A3 production wiring is repaired and fixture-proven. A live A3 observation is
still absent because the single approved live market sample returned no pair.
This does not justify another source call in this lane and does not weaken any
gate.

## Locks And Next Step

A4 and GROUP_A remain unstarted. Memory, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, paid APIs,
execution, scoring, ranking, confidence, and weighted logic remain locked.

The smallest next step is an operator-approved bounded A3 observation retry
with a separately approved mint that already has a live market pair. It must not
begin A4 or GROUP_A.
