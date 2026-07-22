# Printer V1 V2-9.7E.23 Post-Repair Bounded Live Holder and Snapshot Readiness Proof

## Verdict

`V2_9_7E_23_BLOCKED_SOURCE_RELIABILITY`

The single authorized readiness cycle was consumed. The committed E.22 budget,
ordering, pacing, provenance, fixed-backup and cleanup controls held, but none of
the seven admitted candidates produced usable holder evidence. No candidate was
activated and no DexScreener readiness snapshot was requested. This is not
readiness for a full two-token operational pilot.

## Authorization consumption

- Baseline: `9275fa1e120784340bf35000bcc65821042d6fd6`
- Baseline message: `Repair holder reliability and campaign budget controls`
- Authorization: exactly one bounded live readiness cycle
- Consumed at: `2026-07-22T18:15:26.935039+00:00`
- Execution count: one
- Automatic restart, successor, retry loop, reconnect loop and endpoint rotation:
  none
- Second execution: refused by the durable authorization marker and not run
- Full pilot, lifecycle, memory and later lanes: not run

The authorization marker is
`C:\Users\dtwof\PrinterPilot\E23\authorization-consumed.json`. The isolated
redacted stored-fact projection is
`C:\Users\dtwof\PrinterPilot\E23\e23-redacted-evidence.json`.

## Exact preflight

Before live use:

- `HEAD` exactly matched the baseline and the tracked tree was clean.
- No other Printer/MoneyPrinter process, active campaign, active proof, active
  runtime, active supervision row or lease was present.
- The authoritative corpus was inspected read-only and was not mutated.
- The E.20 DB was not opened for mutation or reused.
- `C:\Users\dtwof\PrinterPilot\E23\` did not exist before preparation.
- A new empty DB was created and canonically migrated through
  `037_holder_reliability_budget_control.sql`.
- Readiness DB:
  `C:\Users\dtwof\PrinterPilot\E23\printer-v1-e23-readiness.sqlite3`
- Report directory: `C:\Users\dtwof\PrinterPilot\E23\reports\`
- DB mode: isolated proof; no authoritative-corpus clone was used.
- Initial integrity was `ok`; `PRAGMA foreign_key_check` returned no rows.
- All retrieval, paper-decision, paper-position, trade, audit and PnL tables had
  zero baseline rows.
- Source Governor and Central Scheduler owner ports were present and available.
- There was no fixture plan, compressed clock, lifecycle activation, new source,
  paid provider, wallet, key, signing or execution capability.
- The committed operation ceiling was exactly 45.
- The snapshot reservation was exactly two before holder work.
- Maturation was `UNPROVEN_DISABLED`; no threshold was enabled or invented.

## Candidate cap and 45-operation arithmetic

The full worst-case arithmetic was printed before authorization consumption:

```text
Pump finalized-origin worst case             12
Combined zero-transport validation            9
Seven candidates x three governed requests   21
Reserved DexScreener snapshots                2
                                               --
Worst-case total                              44 <= 45
Derived candidate cap floor((45-12-9-2)/3)     7
```

Actual durable ledger at terminal block:

| Ledger item | Operations |
|---|---:|
| Finalized Pump-origin acquisition | 11 |
| Holder requests, 7 candidates x 3 | 21 |
| Governed transport subtotal | 32 |
| Combined zero-transport validation | 9 |
| Charged subtotal | 41 |
| Unconsumed snapshot reservation | 2 |
| Charged plus preserved reservation | 43 |
| Remaining ceiling slack | 2 |

The seven direct Pump observations persisted by the combined executor are part
of the already charged fixed zero-transport validation envelope; they are not a
second live acquisition and are not double-counted. The ledger retained
`operation_ceiling=45` and `reserved_snapshot_operations=2`. No DexScreener
operation consumed the reservation because the eligible pool was empty.

## Candidate funnel and deterministic order

- Finalized Pump-origin operations: 11
- Budget-admitted candidates: 7
- Maturation decisions: 7 `DUE` then 7 `COMPLETED/EVIDENCE_EVALUATED`
- Reuse decisions: 0 reused; the fresh DB contained no prior holder evidence
- Candidates with a known, clean holder-concentration result: 0
- Holder-eligible candidates: 0
- Selected/activated candidates: 0
- Replacement or ranking: none
- Snapshots attempted: 0

The committed order, redacted in evaluation order, was:

1. `sha256:5e56a4b547ca6187`
2. `sha256:a63fbb5ad73288a7`
3. `sha256:4fe4b9ead9067fad`
4. `sha256:0ad715302f159dbe`
5. `sha256:4d5c5a33197439c3`
6. `sha256:946efce4878f2127`
7. `sha256:a8d49513c5a47b48`

The cap, rather than an arbitrary list length, stopped evaluation. The stop-at-
two rule was never reached because no candidate qualified.

## Holder request timeline and outcomes

Every candidate followed the fixed order: GoPlus primary, Solana RPC primary,
then the single fixed Solana RPC backup only after the primary's eligible
transient failure. RPC method was `getTokenLargestAccounts`, commitment was
`finalized`, and every recorded attempt used one underlying transport operation.

| Candidate | GoPlus result/time (UTC) | RPC primary result/time (UTC) | Fixed backup result/time (UTC) | Eligibility |
|---|---|---|---|---|
| `5e56...6187` | transport failure `18:15:45.884459` | rate limited `18:15:46.506402`, retry-after `18:15:56.506402` | transport failure `18:16:18.465063` | blocked |
| `a63f...88a7` | complete exact target, holder unknown `18:16:22.546994` | rate limited `18:16:23.166900`, retry-after `18:16:33.166900` | rate limited `18:16:48.665222` | blocked |
| `4fe4...7fad` | complete exact target, holder unknown `18:16:49.482031` | rate limited `18:16:50.021107`, retry-after `18:17:00.021107` | transport failure `18:17:21.815889` | blocked |
| `0ad7...9dbe` | complete exact target, holder unknown `18:17:22.551477` | rate limited `18:17:23.188724`, retry-after `18:17:33.188724` | rate limited `18:17:51.967316` | blocked |
| `4d5c...39c3` | complete exact target, holder unknown `18:17:52.766854` | rate limited `18:17:53.385536`, retry-after `18:18:03.385536` | transport failure `18:18:25.081273` | blocked |
| `946e...2127` | complete exact target, holder unknown `18:18:25.845306` | rate limited `18:18:26.358932`, retry-after `18:18:36.358932` | rate limited `18:18:55.238982` | blocked |
| `a8d4...7b48` | complete exact target, holder unknown `18:18:55.951486` | rate limited `18:18:56.379708`, retry-after `18:19:06.379708` | transport failure `18:19:28.271438` | blocked |

Source contribution totals:

- GoPlus: 7 calls; 6 clean exact-target responses with no usable holder field,
  and 1 transport failure.
- Solana RPC primary: 7 calls; all 7 rate limited with persisted failure links
  and `Retry-After` values.
- Solana RPC fixed backup: 7 calls; 3 rate-limited failures and 4 transport
  failures. No backup response supplied holder evidence.
- No retry of a primary or backup call occurred.

## Pacing, overlap and provenance

- GoPlus starts were separated by far more than the committed 3-second minimum.
- Same-source Solana RPC starts were separated by at least the committed
  2-second minimum. Primary-to-backup starts were approximately 2.00 seconds or
  more apart.
- Each next request started only after the prior request recorded a response or
  failure. There was no concurrent holder request overlap.
- The primary role remained the fixed public Solana primary and the backup role
  remained the fixed public backup. Redacted hosts, roles, request IDs, failure
  IDs, subtype, method, commitment, operation count and retry-after evidence are
  present in the redacted artifact.
- No source response was reused. All `reused_evidence_id` and lineage-reuse
  fields were null.

The live facts also prove corrected reporting precedence: transport and
rate-limit failures were reported as those failures, not as target mismatch.
No genuine mismatch occurred live. The committed mismatch gate remains blocking
and was rechecked offline by the focused E.19 mismatch test; it was not weakened
to manufacture eligibility.

## Snapshot readiness

Exactly two holder-eligible candidates were required before snapshots. The
eligible count was zero, so:

- DexScreener readiness requests: 0
- DexScreener responses/failures: 0
- readiness snapshots: 0
- zero normalization: none
- lifecycle windows or memory created: 0

The two-operation reservation remained intact. Attempting snapshots for an
ineligible or partial pool would have violated the holder gate, so the correct
behavior was to stop without contacting DexScreener.

## Cleanup, integrity, locks and replay

- Campaign, run and cycle: `TERMINAL_BLOCKED`
- First terminal cause: `E23_INSUFFICIENT_ELIGIBLE_POOL`
- Terminal timestamp: `2026-07-22T18:19:28.393688+00:00`
- Scheduler jobs: 6 total, all `CANCELLED`, zero retries, no locks or owners
- Active `PENDING/RUNNING/COOLDOWN` scheduler jobs: 0
- Active discovery work: 0
- Active tracking queue rows: 0
- `WAITING/DUE` maturation work: 0
- Active campaign/proof lease: 0
- Integrity: `ok`
- Foreign-key violations: 0
- Retrieval/decision/position/trade/audit/PnL deltas: all 0
- Lifecycle and memory-window rows created: 0
- Zero-source report-only replay: deterministic, 0 new source requests
- Implicit second readiness execution: none

The first report-only projection hit a local extractor defect after cleanup: it
queried `printer_tracking_queue.status` instead of `queue_status`. The process
had already completed and terminalized, so it was not rerun. A separate
zero-network read-only recovery produced two byte-identical stored-fact
projections. The defect lost the harness's in-memory per-call Pump transport
timestamps; the durable 11-operation Pump count and seven persisted direct
request timestamps remain available. This is an evidence-efficiency setback,
not permission for a second live cycle.

## Money-usefulness contribution

E.23 shows that E.22 materially improved boundedness and auditability: the
candidate count was derived from the real budget, holder work was sequential,
source failures retained factual provenance, and the two costly market snapshot
slots stayed protected. That prevents source instability from creating weak
holder evidence, activating unsafe candidates, or spending snapshot budget on
tokens that cannot enter a clean future pilot.

It did not improve live holder availability. Six GoPlus responses were exact but
did not contain usable holder concentration, while both fixed Solana RPC roles
failed for every candidate. The resulting zero eligible pool means Printer still
cannot start a useful two-token memory campaign under this source combination.

## What improved

- Candidate cap was derived correctly and enforced at seven.
- The two-snapshot reservation existed before holder work and survived the block.
- Holder work was sequential and paced without retry or rotation.
- Primary failure was required before fixed-backup use.
- Transport/rate-limit precedence and request-to-failure linkage were preserved.
- Maturation remained explicitly disabled.
- Terminal cleanup and zero-source replay succeeded.

## What remains unproven

- Two live holder-eligible candidates in one bounded cycle
- Any live readiness snapshot after the E.22 repair
- Two successful exact-pair DexScreener readiness snapshots
- Snapshot field completeness and any permitted zero-normalization provenance
- Full two-token operational lifecycle behavior after this repair
- Durable external Pump call timestamps in the E.23 artifact due to the local
  post-run reporter defect

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Solana RPC remains the decisive blocker.** Every primary request was rate
   limited, and the fixed backup returned only rate-limit or transport failures.
2. **GoPlus exact-target success was insufficient.** Six clean responses still
   yielded `HOLDER_CONCENTRATION_UNKNOWN`; exact identity alone is not safety
   evidence.
3. **The fixed backup did not provide useful independence in this cycle.** It
   changed endpoint role but not the outcome.
4. **The full candidate cap was consumed.** With zero early successes, the lane
   required all 21 holder calls while correctly retaining snapshot capacity.
5. **The reporter used a wrong queue column name.** Read-only recovery succeeded,
   but in-memory Pump timing detail was lost and must not be reconstructed or
   retried as if observed.
6. **No snapshot contract was exercised.** Snapshot readiness remains wholly
   unproven, even though its budget reservation was proven.

## Full-pilot readiness

Blocked. A separately authorized full V2-9.7E two-token pilot must not run from
this result. Before any new live authorization, a design/repair lane must address
the observed fixed-source holder reliability failure without paid APIs, endpoint
rotation, hidden retry, weaker evidence, higher ceilings, scoring or ranking. A
future focused proof must also correct the reporter's queue-column query before
authorization consumption and prove exact durable Pump timing capture locally.

All later capabilities remain locked: lifecycle activation, 5m/15m/1h/4h
memory, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, keys, signing, funds, live execution, V2-9.7F and V2-9.8.
