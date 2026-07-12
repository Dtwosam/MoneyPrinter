# Printer V1 A3 Live Observation Closeout

Status: `A3_WIRING_PASS_LIVE_SAMPLE_BLOCKED`

Date: 2026-07-12

Scope: bounded A3 `LATE_BUY_TRAP` observation only. A4 and GROUP_A were not
started.

## Failure-Label Audit And Narrow Repair

The prior no-pair market observation was recorded as
`dexscreener_malformed_fixture`. Static inspection found that the normalizer
used that label for both a missing/non-list `pairs` field and a valid empty
`pairs: []` response. Those cases are not equivalent.

The narrow repair now classifies a valid empty list as
`PARTIAL / ACCEPTABLE_PARTIAL_DATA`, with `no_matching_pairs=true`, reason
`source_returned_empty_pairs`, and no source failure record. A missing or
non-list `pairs` field remains `FAILED / MISSING_CRITICAL_DATA` with
`dexscreener_malformed_fixture`. No A3 threshold, acceptance rule, source
boundary, or discovery filter changed.

Focused fixture coverage proves that an empty list creates a governed response
row, no governed failure row, and no downstream rows.

## Approved Market Observation

The single approved mint and pair came from the existing local operator list
artifact `operator-runs/x5-token-list-repaired-1h-20260705-084824.json`:

| Item | Value |
|---|---|
| Mint | `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` |
| Token | BONK |
| Pair | `6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp` |
| Market source/channel | DexScreener / `DEXSCREENER_PAIR_MARKET_SNAPSHOT` |
| Proof DB | `data/printer_v1_a3_live_observation_bonk_20260712.sqlite3` |

One governed DexScreener market request completed cleanly:

| Field | Value |
|---|---|
| Source request ID | `1119` |
| Source response ID | `1072` |
| Status / quality | `COMPLETE / CLEAN_DATA` |
| Price USD | `0.000003952` |
| Liquidity USD | `221757.41` |
| `price_change_1h` | `-0.74` |
| 1h transactions | `88` |
| 5m transactions | `7` |
| 1h volume USD | `1905.39` |

The response was valid market evidence. It was not malformed and it supplied
the required negative one-hour market input.

## Governed Finalized T3 Observation

The exact same mint was enriched once through the governed, read-only finalized
Solana RPC path. Its governed request was `1120`. It failed closed before a
transaction lookup because the approved three-signature-page cap was exhausted:

| Field | Value |
|---|---|
| Source request ID | `1120` |
| Source response ID | none |
| Source failure ID | `48` |
| Failure type | `solana_rpc_token_age_page_cap_exhausted` |
| Failure stage | `signature_history` |
| RPC host | `api.mainnet-beta.solana.com` (redacted host only) |
| Methods attempted | `getAccountInfo`, then three `getSignaturesForAddress` calls |
| Signature pages fetched | `3` |
| Transaction calls | `0` |
| Block-time calls | `0` |

No prohibited substitute was used. In particular, pair age, pool time,
discovery/receipt time, migration time, first-trade time, and observed-live
status did not become token age.

## Exact A3 Inputs And Classification

| A3 input | Result |
|---|---|
| Exact Solana mint match | PASS |
| Market `price_change_1h < 0` | PASS (`-0.74`) |
| Existing activity/fast-event contract | Evaluated without threshold changes |
| T1/T2/T3 token age known | FAIL: T3 page-cap failure |
| `token_age_seconds >= 3600` | Not available |
| T3 tier / finalized provenance | Not accepted |
| A3 classification | Not emitted |

The persisted proof candidate remained `TRACK_NORMAL` with primary bucket
`B2 / VOLUME_DECAYING`; its metadata retained no accepted T3 fields. The
selection proof item retained market request/response identities `1119/1072`.
This is a valid live market observation but not a genuine A3 observation.

## Proof-Local Row Deltas And Locks

Persistent DB SHA-256 before and after was unchanged:

`97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb`

Compared with the unchanged persistent baseline, the isolated proof DB had:

| Table / capability | Delta or result |
|---|---|
| Source requests | `+2` |
| Source responses | `+1` |
| Source failures | `+1` |
| Discovery candidates | `+1` |
| Selection batches / items | `+1 / +1` |
| Tracking queue / scheduler jobs | `+1 / +1`, proof-local existing handoff rows; no runtime executed |
| Memory windows | `0` |
| Retrieval queries / matches | `0 / 0` |
| Paper decisions | `0` |
| Paper positions / trade events / trade audits | `0 / 0 / 0` |
| PnL | no PnL table in the inspected schema |

The proof did not run a scheduler or create any memory, retrieval, paper,
position, trade, audit, or PnL record. The proof-local tracking/scheduler-row
handoff is an existing persistence side effect, not runtime execution; a future
strict metadata-only proof should use a dedicated no-handoff audit path.

## Tests And Source-Stack Update

Focused tests passed for the DexScreener no-match taxonomy, DexScreener source
contracts, A3 T3 handoff, T3 evidence, fast-event normalization, and selection
metadata. The DexScreener source-stack contract now documents that an empty
`pairs` array is a valid no-match response rather than malformed source data.

## Verdict And Remaining Blocker

`A3_WIRING_PASS_LIVE_SAMPLE_BLOCKED`

The A3 contract and governed market-to-T3 handoff remain fixture-proven. The
one allowed live market sample did not produce finalized T3 evidence because
the high-history mint exhausted the non-expandable page cap. No threshold may
be weakened and no additional live call was made in this lane.

A4 and GROUP_A remain unstarted. Memory, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, paid APIs,
execution, scoring, ranking, confidence, and weighted logic remain locked.

The next action requires explicit operator approval: either accept this bounded
live observation closeout as sample-limited, or approve one distinct,
already-known recent mint/pair for a separate bounded A3 observation. Do not
begin A4 in either case.
