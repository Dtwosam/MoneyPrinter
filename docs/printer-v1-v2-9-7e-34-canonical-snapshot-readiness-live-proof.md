# Printer V1 V2-9.7E.34 Canonical Snapshot Readiness Live Proof

## Verdict

`V2_9_7E_34_BLOCKED_SNAPSHOT_READINESS`

The one authorized live execution of the committed canonical
`run(mode=SNAPSHOT_READINESS)` path was consumed exactly once. It acquired two
bounded candidates, proved both holder-eligible through exact-target
authenticated Helius evidence, and attempted the fixed two snapshot bundles.
Neither bundle satisfied the strict exact-15m readiness contract. The first
candidate had a complete exact-pool base response with positive price and
liquidity, but its fresh pool had no completed 15-minute OHLCV candle from which
price change and volume could be derived. The second candidate had the same
missing completed-candle condition and its final GeckoTerminal trades request
was rate-limited. Zero readiness snapshots were persisted.

This is an honest operational snapshot-readiness blocker. It is not a PASS, does
not authorize the full two-token lifecycle pilot, and does not unlock any later
capability.

## Scope and authorization

- Exact launch HEAD:
  `eefbe8d0c02cb13b47ba9ea0507a14bc3621ea28`.
- Branch: `master`.
- Tracked tree and index at launch: clean.
- Pre-existing untracked artifacts were present and preserved.
- Authorized mode: `SNAPSHOT_READINESS`.
- Canonical dispatcher invocations: exactly one.
- `FULL_PILOT` invocations: zero.
- Manual provider calls, retries, endpoint rotation, reconnects, successor
  executions, and second executions: zero.
- Isolated proof identity:
  - campaign: `v2-9-7e-34-campaign`;
  - run: `v2-9-7e-34-run`;
  - cycle: `v2-9-7e-34-cycle`;
  - configuration: `v2-9-7e-34-config`;
  - policy: `v2-9.7e.34`;
  - configuration hash:
    `de0ba8a8deec79e121bdb8fc232fcbbb37b36cdafdc7a25986e2c986b1a813aa`.
- Executor: CPython `3.12.10` from the committed workspace virtual
  environment.
- The existing user-scoped `PRINTER_HELIUS_API_KEY` was loaded into the proof
  process without printing or persisting its value. No secret material appears
  in this closeout or the deterministic report.

## Preflight

Preflight completed before the live call.

| Gate | Result |
|---|---|
| Exact HEAD | PASS |
| Clean tracked tree and index | PASS |
| Canonical mode set contains exactly `ACTIVATION_ONLY`, `SNAPSHOT_READINESS`, and `FULL_PILOT` | PASS |
| `SNAPSHOT_READINESS` dispatches only to `run_snapshot_readiness` | PASS |
| Helius secret presence, without disclosure | PASS |
| Source-contract preflight | `READY`, no issues, zero external requests |
| Operation ceiling | `45` |
| Derived holder candidate cap | `3` |
| Snapshot reservation | `6` (`2` base plus `4` completion operations) |
| Worst-case total | `43/45` |
| Primary/readiness source identity | GeckoTerminal exact-pool plus exact 15m GeckoTerminal evidence |
| Exact readiness window | `900` seconds |
| Lifecycle and memory owner reachability | Unreachable in readiness mode; focused E.33 proof passed |
| Second-run refusal | Committed operation-ledger marker check proved offline |

The focused E.33 canonical-boundary suite passed all 16 tests, including
lifecycle/memory-owner non-invocation, pre-provider configuration blocking,
single-use refusal, cleanup, zero-source replay, integrity, foreign keys, and
zero forbidden-capability deltas.

## Live execution evidence

The durable operation evidence records the authorized flow:

```text
preflight
-> single-use admission
-> governed finalized Pump acquisition
-> bounded secondary enrichment
-> holder eligibility
-> two snapshot bundle attempts
-> deterministic report/replay
-> cleanup
-> stop
```

### Pump acquisition and operation accounting

- Finalized Pump acquisition used the fixed public Solana RPC owner.
- Durable Pump transport operations: `13/13` complete:
  - `3` `getSignaturesForAddress`;
  - `10` `getTransaction`.
- Pump retries, endpoint rotation, and reconnects: zero.
- Bounded secondary-enrichment transport operations represented in the
  campaign ledger: `3`.
- Pre-snapshot ledger after holder evaluation:
  - governed requests: `22`;
  - underlying transport operations: `24`;
  - zero-transport validation operations: `9`;
  - reserved snapshot operations: `2`;
  - reserved snapshot-completion operations: `4`.
- Actual fixed snapshot operations consumed from the reservation: `6`.
- Reconciled actual totals:
  - governed requests: `28`;
  - underlying transport operations: `30`;
  - zero-transport operations: `9`;
  - charged plus zero-transport work: `39/45`.
- The operation ceiling and the six-operation snapshot reservation were not
  breached.

The Source Governor tables contain `12` holder/snapshot requests, `9`
responses, and `3` failures. The three failures were two primary public Solana
RPC `429` holder responses and one GeckoTerminal `429` trades response. The
fixed Helius backup succeeded for both holder candidates. No failed operation
was retried.

### Candidates and holder results

Two candidates entered the bounded holder funnel. Identities are redacted as
SHA-256 values.

| Candidate | Mint hash | Exact mint/pair hash | GoPlus | Public Solana RPC | Authenticated Helius | Holder result |
|---|---|---|---|---|---|---|
| 1 | `83295fd3fcd7cb8e0fb53c2bcf041c0a871c630d92645b70e68bbe66a0d660ad` | `e8376787aeacef560a0e0a3c550e5261bdac8de06ec687824cfc0fd6f184da1b` | complete/clean, concentration unknown | `solana_rpc_rate_limited` | complete/clean, exact target, finalized context, `HOLDER_CONCENTRATION_EXTREME` | eligible |
| 2 | `fca2f000dcaedae3cd88b6c345754aff13c36d08c9391b04fd21d93b7c326928` | `277533cfeccf451bc54c1d730c6aa08eb132156fd6e3f9a4654a376a8befff86` | complete/clean, concentration unknown | `solana_rpc_rate_limited` | complete/clean, exact target, finalized context, `HOLDER_CONCENTRATION_EXTREME` | eligible |

Both maturation rows were Scheduler-owned, immediately due under
`UNPROVEN_DISABLED`, and completed with immutable first cause
`EVIDENCE_EVALUATED`. There were no holder-eligibility rejections after the
fixed backup evidence resolved the primary failures.

### Snapshot provenance and completeness

Candidate 1:

- pair creation time: `2026-07-23T11:03:55Z`;
- exact-pool base request time: `2026-07-23T11:07:58.013118Z`;
- base age was about `243` seconds;
- exact Solana mint/pair identity: PASS;
- GeckoTerminal base price: positive;
- GeckoTerminal `reserve_in_usd` liquidity: positive and exact-pair
  provenance-backed;
- exact-pool base, OHLCV, and trades transports: all complete/clean;
- completed exact 15m candle: unavailable;
- derived `price_change_15m`, `volume_15m`, and `txns_15m`: unavailable;
- persisted readiness snapshot: none.

Candidate 2:

- pair creation time: `2026-07-23T11:04:15Z`;
- exact-pool base request time: `2026-07-23T11:08:16.032552Z`;
- base age was about `241` seconds;
- exact Solana mint/pair identity: PASS;
- GeckoTerminal base price and `reserve_in_usd` liquidity: positive;
- exact-pool base and OHLCV transports: complete/clean;
- completed exact 15m candle: unavailable;
- GeckoTerminal trades transport: `geckoterminal_rate_limited`;
- derived exact-15m fields: unavailable;
- persisted readiness snapshot: none.

Bundle completeness was therefore `0/2`, with zero
`SNAPSHOT_READINESS_COMPLETE` rows. The fixed result mapping is
`BLOCKED_SNAPSHOT_READINESS`: holder eligibility was at least two, but fewer
than two complete bundles existed.

## First terminal cause

The first candidate-level terminal blocker was the absence of a completed
provider 15-minute candle for a roughly four-minute-old exact pool. The strict
readiness contract consequently retained:

- missing/invalid `price_change_15m`;
- missing/invalid `volume_15m`;
- missing/invalid `txns_15m`;
- missing exact-15m price, volume, and transaction provenance.

The later GeckoTerminal `429` on candidate 2 is additional source-reliability
evidence, not the first terminal cause.

## Terminal report and zero-source replay

The proof wrapper's post-run convenience query referenced a non-existent
`printer_token_snapshots.snapshot_reason` column after the canonical owner had
already completed. That local evidence-display query lost the original stdout
summary but did not alter the canonical run, make a provider call, or change
the database. The durable DB remained authoritative.

The committed `build_bounded_readiness_report` was then executed twice against
the completed DB:

- canonical reports were byte-identical;
- report SHA-256:
  `41800e9011028aead70174c918217c4e3f506073955e7fb02f19cd5cfb841c69`;
- source-request counts were `12 -> 12 -> 12`;
- replay source calls: zero;
- integrity: `ok`;
- foreign-key violations: zero.

Under the Python Builder Guide, the convenience-query issue is a local
`TEST_HARNESS_DEFECT`; it is not a committed Printer code defect and did not
affect provider work or the proof verdict.

## Cleanup, refusal, and forbidden deltas

- Active scheduler jobs: `0`.
- Active 15m lifecycle jobs: `0`.
- Active tracking queue rows: `0`.
- Cancelled staged jobs: none required.
- Operation-ledger authorization markers for the exact run/cycle: `1`.
- A second canonical execution was not attempted. The committed pre-transport
  marker check and passing E.33 test prove that the same identity would return
  `REFUSED_SECOND_EXECUTION` with zero transport.

All forbidden deltas were zero:

| Capability/table family | Delta |
|---|---:|
| lifecycle token snapshots | 0 |
| memory windows | 0 |
| memory factory run steps | 0 |
| retrieval queries / matches | 0 / 0 |
| paper decisions / decision audits | 0 / 0 |
| paper positions | 0 |
| paper trade events | 0 |
| paper trade audits | 0 |
| PnL / financial activation | 0 |

The lifecycle driver and all memory, retrieval, decision, and financial owners
remained unreachable.

## Python Builder Guide blocker classification

### Evidence comparison

- The canonical call path, source contracts, fixed request kinds, exact-pair
  identity, budget, reservation, pacing, and no-retry rules matched the
  committed E.33 boundary.
- Holder evidence succeeded through the committed authenticated Helius backup.
- Both selected pools were only about four minutes old at the base snapshot.
- The provider returned no completed exact 15m candle usable under the strict
  readiness contract.
- One later keyless GeckoTerminal request returned a normal operational `429`.
- No malformed identity, Governor bypass, Scheduler bypass, budget drift,
  retry, persistence corruption, integrity failure, or forbidden capability
  activation was observed.

### Classification

`EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`

The missing completed candle for very young pools and the later public-provider
rate limit are expected operational/provider outcomes already named by the
E.33 hard-closure rule. They do not justify a code repair lane, a threshold
change, weaker completeness, a retry, endpoint rotation, budget expansion, or
another execution.

## Functionality Risks / Setbacks / Efficiency Blockers

- Fresh Pump candidates may be too young to possess one completed exact 15m
  provider candle during a bounded readiness cycle.
- Public Solana RPC returned `429` for both primary holder calls, although the
  fixed authenticated free-tier backup succeeded.
- GeckoTerminal returned a `429` on the sixth reserved snapshot operation.
- The campaign ledger stores the six snapshot operations as an advance
  reservation rather than folding their completed consumption into the
  persisted pre-snapshot ledger totals; the durable Source Governor rows retain
  the actual six attempts.
- The local post-run display query lost the original result stdout, so the
  verdict was reconstructed from the authoritative ledger, holder, source,
  snapshot, cleanup, integrity, and deterministic report rows.

## What remains locked

The full V2-9.7E two-token lifecycle pilot, operational memory growth,
V2-9.7F, V2-9.8, V2-10, 12h/24h work, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, live execution, wallets, private
keys, signing, real funds, paid APIs, scoring, ranking, confidence percentages,
weighted logic, embeddings, vectors, retry, rotation, reconnect, and automatic
restart remain locked.

## Closeout

V2-9.7E.34 stops here with
`V2_9_7E_34_BLOCKED_SNAPSHOT_READINESS`. No tag is applied. The actual bounded
two-token V2-9.7E lifecycle pilot is not ready to be planned from a PASS and was
not run or unlocked. Any future live readiness execution requires a new,
explicit operator authorization; this lane creates no automatic successor and
recommends no code-repair lane.
