# Printer V1 V2-9.7E.25 Helius Holder and Snapshot Readiness Proof

## Verdict

`V2_9_7E_25_BLOCKED_SNAPSHOT_READINESS`

The single authorized bounded live cycle produced exactly two deterministic,
exact-target, holder-evidence-eligible candidates through the fixed Helius Free
backup. It also made exactly two governed DexScreener requests and persisted
two clean source responses. Neither persisted snapshot is ready for a future
15-minute lifecycle: both lack liquidity and all 15-minute microstructure
fields, while both show positive wider-window activity. E.19 therefore forbids
converting the missing fields to zero. No second execution was run.

## Baseline and authorization

- Exact baseline: `ac839798d36a3692ce890db68e08b2d0879f7c49`
- Baseline message: `Repair holder source and reporting reliability`
- Authorization: exactly one bounded live readiness cycle
- Consumed at: `2026-07-22T19:41:20.899909+00:00`
- Execution count: one
- Second execution, retry loop, endpoint rotation, reconnect, automatic restart,
  second backup and paid fallback: none
- Lifecycle windows, 5-minute support evidence, memory, retrieval, decisions,
  positions, trades and PnL: not created or activated

The durable single-use marker is
`C:\Users\dtwof\PrinterPilot\E25\single-live-authorization-consumed.json`.
Its maximum execution count is one. The cycle was not rerun after the snapshot
block was established.

## Preflight and isolation

Before provider contact:

- `HEAD` exactly matched the baseline; staged and unstaged tracked changes were
  absent. Pre-existing untracked operator artifacts were not touched.
- Process inspection found no Printer Python process or Printer runtime owner.
- Historical E.15 proof supervision was terminal, its lease had expired and
  been released, its lock file was absent, and no owner process existed. Its
  isolated campaign graph still contains stale `RUNNING`/`PLANNED` labels; this
  was treated as non-live historical metadata and was not mutated.
- `C:\Users\dtwof\PrinterPilot\E25\` did not exist.
- A fresh non-authoritative proof DB was created at
  `C:\Users\dtwof\PrinterPilot\E25\printer-v1-e25-readiness.sqlite3`.
- Reports are under `C:\Users\dtwof\PrinterPilot\E25\reports\`; the pre-live
  isolated backup is
  `C:\Users\dtwof\PrinterPilot\E25\backups\printer-v1-e25-pre-live.sqlite3`.
- The DB was canonically migrated through
  `038_holder_source_reporting_repair.sql`.
- Initial integrity was `ok`, foreign-key violations were zero, and all locked
  memory/financial tables had zero rows.
- Source Governor and Central Scheduler owner ports were required and present.
- The committed ceiling was 45, the configured candidate cap was four, and two
  DexScreener operations were reserved.
- The Helius key was resolved only from `PRINTER_HELIUS_API_KEY` in the
  operator-owned runtime environment. The value was never printed or included
  in command arguments, logs, the DB, the marker, or redacted evidence.
- No fixture plan, compressed clock or lifecycle activation was supplied.

The live owner used Pump finalized-origin acquisition, deterministic finalized
candidate order, committed E.24 holder collection, actual transport charging,
and a readiness-only terminal driver. The driver could only request the two
DexScreener observations after exactly two holder-eligible candidates and did
not create lifecycle work.

## Exact request timeline

All times are UTC. Pump timing is durably stored in
`printer_external_source_operations` rather than process memory.

| Time | Operation | Result | Charged transport operations |
|---|---|---|---:|
| 19:41:20.907882-19:41:22.304108 | Pump `getSignaturesForAddress` page 1, finalized | complete | 1 |
| 19:41:22.313354-19:41:22.924409 | Pump `getSignaturesForAddress` page 2, finalized | complete | 1 |
| 19:41:22.934893-19:41:23.490577 | Pump `getSignaturesForAddress` page 3, finalized | complete | 1 |
| 19:41:23.492584-19:41:29.700376 | Nine sequential Pump `getTransaction` calls, finalized | all complete | 9 |
| 19:41:29.776634 | Candidate 1 GoPlus `safety_reference` | complete exact target; holder unknown | 1 |
| 19:41:30.827551 | Candidate 1 public RPC `getTokenLargestAccounts`, finalized | `solana_rpc_rate_limited` | 1 |
| 19:41:31.499518 | Candidate 1 Helius backup, two finalized RPC methods | complete exact target | 2 |
| 19:41:32.777693 | Candidate 2 GoPlus `safety_reference` | complete exact target; holder unknown | 1 |
| 19:41:33.593859 | Candidate 2 public RPC `getTokenLargestAccounts`, finalized | `solana_rpc_rate_limited` | 1 |
| 19:41:34.208404 | Candidate 2 Helius backup, two finalized RPC methods | complete exact target | 2 |
| 19:41:35.655721 | Candidate 1 DexScreener `pair_market_snapshot` | complete source response; readiness blocked | 1 |
| 19:41:36.453192 | Candidate 2 DexScreener `pair_market_snapshot` | complete source response; readiness blocked | 1 |

Requests were sequential. Each candidate followed GoPlus, public Solana RPC,
then Helius only after the eligible transient primary rate-limit failure. There
was no duplicate request, retry, rotation or fallback beyond the fixed Helius
backup. Both Helius attempts used the fixed redacted host
`mainnet.helius-rpc.com`, `getTokenLargestAccounts+getTokenSupply`, and explicit
`finalized` commitment.

## Candidate and holder-evidence funnel

Pump performed 12 finalized operations and yielded two evaluated finalized
candidates. Because two candidates were already sufficient, the four-candidate
cap required no replacement or additional evaluation. Order was deterministic
and no score, rank, confidence or weighting was used.

| Order | Redacted mint identity | GoPlus | Public RPC | Helius Free | Eligibility |
|---:|---|---|---|---|---|
| 1 | `sha256:39a240f1b1de6c5ca339c83f0ee5a44d124e623ff8301ee867f984e4273cca88` | exact target, clean, concentration unknown | finalized rate limit | exact target, clean, `HOLDER_CONCENTRATION_EXTREME` | eligible |
| 2 | `sha256:7d9a21ef655cf0958217752d2f6a03b1edda1b6cd3aef3a397d6b923049f65d6` | exact target, clean, concentration unknown | finalized rate limit | exact target, clean, `HOLDER_CONCENTRATION_EXTREME` | eligible |

The selected eligible identities equal those two identities in the same order.
GoPlus unknown evidence did not become eligibility evidence. Transport/rate-limit
failure precedence was preserved for both public-RPC failures; neither was
misreported as target mismatch. No conflicting pair of usable holder facts was
observed: Helius was the only source with a known clean concentration category
for each exact mint.

## Source and campaign accounting

| Account | Operations |
|---|---:|
| Combined zero-source validation allocation | 9 |
| Pump finalized-origin transport | 12 |
| Holder transport: two GoPlus | 2 |
| Holder transport: two public RPC failures | 2 |
| Holder transport: two two-method Helius facts | 4 |
| Exactly two DexScreener readiness requests | 2 |
| Total charged | **31** |
| Ceiling | **45** |

The durable holder ledger records 18 governed requests through holder closeout,
20 underlying operations through that point, nine zero-transport validations,
and the original two-operation snapshot reservation. Adding the two actual
DexScreener operations gives 20 governed transport-facing requests and 31 total
charged operations. The reservation was fully consumed by exactly two snapshots;
14 operations remained below the ceiling.

## Snapshot-readiness evidence

Both DexScreener responses were `COMPLETE` / `CLEAN_DATA` and each produced one
exact-mint snapshot row, but persistence alone is not the E.25 readiness gate.

| Field | Candidate 1 | Candidate 2 |
|---|---:|---:|
| Price USD | 0.000006003 | 0.000002179 |
| Liquidity USD | missing | missing |
| Price change 5m | 175.0% | -34.03% |
| Price change 15m | missing | missing |
| Volume 5m | 54.45 | 1,406.16 |
| Volume 15m | missing | missing |
| Transactions 5m | 13 | 8 |
| Transactions 15m | missing | missing |
| Volume 1h / transactions 1h | 54.45 / 13 | 1,406.16 / 8 |
| Price change 1h | 175.0% | -34.03% |
| Volume 24h / transactions 24h | 54.45 / 13 | 1,406.16 / 8 |

Ready snapshot count is zero. The known missing-microstructure blocker therefore
remains. In particular, a future clean 15-minute outcome cannot prove entry and
exit realism without positive liquidity evidence, and the missing 15-minute
price/volume/transaction fields cannot support the repaired short-window
contract.

### Zero-normalization provenance

No zero normalization occurred. E.19 permits filling missing short-window
activity only when exact target/source quality are valid, price and liquidity
are positive, and wider-window volume and transactions are both present and
zero. Here liquidity was missing and wider-window activity was positive for
both candidates. Converting any missing field to zero would have fabricated
evidence, so the fields remained null.

## Cleanup, integrity and replay

After the honest block:

- Campaign, run and cycle are all `TERMINAL_BLOCKED` with first terminal cause
  `V2_9_7E_25_BLOCKED_SNAPSHOT_READINESS`.
- Active tracking-queue rows: zero.
- Pending/running/cooldown Scheduler jobs: zero.
- Pending/running/cooldown campaign-owned Scheduler work: zero.
- Waiting/due holder-maturation work: zero; both rows are completed.
- Integrity: `ok`.
- Foreign-key violations: zero.
- Memory windows, paper decisions, positions, trade events and paper audits:
  zero before and zero after.
- The canonical report was built twice from SQLite only. Both hashes were
  `709019e6cc1420a0686bcdcf902d7da074ffe0739595b9abfa4012383b4ed2f2`.
- Replay source requests: zero.
- A byte-level DB secret scan and redacted-report scan found no Helius key.

The initial automated closeout treated two persisted snapshots as ready. A
subsequent offline E.19 field audit corrected the isolated campaign state and
redacted report to this snapshot blocker without making another provider
request or changing any source fact. This distinction is material: source
persistence success is not snapshot-readiness success.

## Money-usefulness contribution

The proof establishes that the repaired fixed Helius Free backup can restore
exact-mint holder evidence when the shared public RPC rate-limits, within the
existing free 45-operation budget and without weakening provenance. That makes
future candidate intake materially more reliable. The block also protects the
money-usefulness objective: Printer did not allow missing liquidity or invented
15-minute microstructure to become the basis of clean memory, paper decisions,
or apparent profit.

## What remains locked and proof required next

This block does not authorize a full E.15-style pilot. Lifecycle activation,
5m/15m/1h/4h windows, memory creation/promotion, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, paid APIs,
scoring/ranking/confidence/weighting, V2-9.7F and V2-9.8 remain locked.

Before another live readiness cycle can be considered, a separate audit/design
lane must explain why a `COMPLETE` / `CLEAN_DATA` DexScreener response can persist
a snapshot with missing liquidity and missing active 15-minute fields. The
minimum repair must fail readiness closed unless both exact candidates have
positive price and liquidity plus actual 5m/15m price, volume and transaction
evidence, or satisfy every committed E.19 verified-inactivity predicate. Offline
tests must cover active wider-window data with missing 15m fields and prove that
persistence status cannot be mistaken for readiness status. Any later live
cycle requires new, explicit one-cycle authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- Snapshot persistence currently accepts a clean normalized response whose
  selected pair has missing liquidity and missing 15-minute microstructure.
- The readiness harness initially equated `E2M_SNAPSHOT_PERSISTED` with readiness;
  the offline field audit caught and corrected that reporting defect.
- DexScreener may omit 15-minute buckets for very young pairs. Positive 1h
  activity makes E.19 zero-normalization unavailable, so source timing/schema
  compatibility remains an operational blocker.
- Helius proved meaningful redundancy in this cycle, but both holder outcomes
  were `HOLDER_CONCENTRATION_EXTREME`; this lane proves evidence availability,
  not that those tokens are safe or suitable for a future lifecycle.
- The historical E.15 isolated campaign graph retains stale nonterminal labels
  despite terminal proof supervision. It had no live owner or lease and did not
  affect E.25, but a future audit should reconcile that metadata without
  touching the authoritative corpus.
- No second readiness execution is available under this authorization. The
  snapshot repair must be proven offline before requesting another bounded live
  cycle.

## Readiness for a full pilot

Not ready. Holder-source reliability passed for two candidates, accounting and
cleanup passed, and Helius secret handling passed. Snapshot readiness failed for
both candidates, so the PASS gate for a separately authorized full V2-9.7E
two-token pilot is not met.
