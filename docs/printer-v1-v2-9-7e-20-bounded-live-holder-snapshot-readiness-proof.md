# V2-9.7E.20 Bounded Live Holder and Snapshot Readiness Proof

**Verdict:** `V2_9_7E_20_BLOCKED_INSUFFICIENT_ELIGIBLE_POOL`

**Full-pilot readiness:** NOT READY

## Exact baseline and authorization

- Baseline commit: `d29dc2b4ef9e0a643be7c322f1eb67034ac319c8`.
- Baseline message: `Repair holder eligibility and live clean-memory blockers`.
- The tracked tree was clean immediately before execution.
- The operator authorized exactly one bounded live readiness cycle. The first
  external Pump-origin request consumed that authorization.
- The cycle ran once from `2026-07-22T16:44:08.289227+00:00` through
  `2026-07-22T16:48:28.064078+00:00`. It was not retried or rerun.
- No full pilot, lifecycle runner, fixture plan, compressed clock, snapshot
  fallback, endpoint rotation, paid source or expanded ceiling was used.

## Isolated DB and paths

- Fresh proof root: `C:\Users\dtwof\PrinterPilot\E20\`.
- Isolated DB: `printer-v1-e20-readiness.sqlite3`.
- Redacted evidence: `e20-redacted-evidence.json`.
- Canonical migrations applied: 36.
- Initial DB state: zero source requests, campaigns, token snapshots, memory
  windows and memory rows.
- The authoritative corpus was neither opened as the target nor mutated.

## Source and request accounting

All live requests remained behind the committed Source Governor and Central
Scheduler ownership boundaries.

| Work | Governed count | Result |
|---|---:|---|
| Finalized Pump origin | 12 | 3 signature pages and 9 transaction decodes |
| GoPlus safety/holder contribution | 8 | 8 COMPLETE / CLEAN_DATA responses; holder concentration remained unavailable/unknown |
| Solana RPC holder primary + existing one backup | 16 | 12 rate-limited failures and 4 transport failures |
| Combined discovery/origin validation accounting | 9 | Existing zero-new-transport validation work over acquired proofs |
| DexScreener exact-pair snapshots | 0 | Correctly not reached because no two candidates were eligible |

Lifecycle-wide governed accounting was 45, exactly the committed campaign
ceiling of 45. Actual external transport attempts were 36: 12 Pump, 8 GoPlus
and 16 holder-RPC calls. The isolated DB contained 32 governed request rows,
16 response rows and 16 failure rows; Pump acquisition additionally retained
its committed operation accounting. No ceiling was raised or exceeded.

The holder RPC path used exactly one primary and the already-approved one
distinct backup per candidate. There was no retry loop, third endpoint, endpoint
rotation or paid fallback.

## Candidate and holder-eligibility funnel

- Finalized candidates discovered: 8.
- Fixed bounded candidates evaluated: 8 of the maximum 8.
- Deterministic candidate order: stable on independent recomputation.
- Holder-evidence eligible: 0.
- Holder-evidence ineligible: 8.
- Successful replacements: 0.
- Ineligible candidates skipped while seeking replacements: 8.
- Selected active identities: none.
- Atomic activation: blocked with
  `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`; token slots remained zero.

Every candidate identity in the evidence report is represented only by a
SHA-256 prefix. For all eight candidates:

1. GoPlus completed with clean source evidence but did not provide a usable
   holder-concentration label.
2. The primary holder RPC attempt failed.
3. The single governed backup holder RPC attempt also failed.
4. The candidate remained ineligible; it was not labelled safe and was not
   activated.

The E.19 summary reason was `HOLDER_EVIDENCE_TARGET_MISMATCH` for all eight,
while the authoritative source-failure ledger shows the factual causes were
rate limiting or transport failure. This happens because the current E.19
eligibility helper checks the empty failed-response target before classifying
the failed source status. The candidate outcome is safely ineligible, but the
summary reason ordering is confusing and must be treated as a reporting defect,
not evidence of eight genuine target mismatches.

No scoring, ranking, confidence, weighting or manual identity choice entered
ordering, eligibility or selection.

## Snapshot-readiness evidence

No candidates were selected because the holder gate failed two-or-none.
Consequently the Scheduler correctly issued zero readiness snapshot jobs and
DexScreener received zero requests.

There are therefore no selected-candidate values for:

- price or liquidity;
- 5m/15m price change;
- 5m/15m volume;
- 5m/15m transactions;
- wider-window activity.

No missing value was converted to zero. No
`SNAPSHOT_VERIFIED_INACTIVE` provenance was created. Snapshot readiness remains
unproven rather than inferred from absent evidence.

## Cleanup, integrity and replay

- Campaign-owned `DISCOVERY_REFRESH` jobs cancelled: 6.
- Campaign-owned pending/running discovery jobs after cleanup: 0.
- Pending/running/cooldown lifecycle jobs: 0.
- First-15m handoff jobs created: 0.
- Token slots created: 0.
- Token snapshots created: 0.
- Memory windows, episodes and memory rows created: 0.
- Discovery work terminal states: 5 succeeded, 1 failed; none active.
- Campaign, run and cycle states: `TERMINAL_BLOCKED` with the exact E.20
  verdict as first terminal cause.
- SQLite integrity: `ok`.
- Foreign-key violations: 0.
- Forbidden-capability deltas: 0 for retrieval, paper decisions, positions,
  trade events, paper audits and PnL-related surfaces.

Deterministic zero-source replay reopened only the persisted DB and redacted
report. The aggregate projection and report bytes were identical, it created
zero new source requests, and the redacted report SHA-256 was
`ffe7e1a09f3acc6e38216d767ffb4b5cbddf502a63e9b2354fbeec8f21a81ba2`.

## Money-usefulness contribution

This proof prevented a full four-hour pilot from spending snapshot and memory
capacity on candidates whose mandatory holder evidence could not be established.
It demonstrates that the repaired pre-activation gate blocks honestly before
dirty memory, fake yield or unsupported snapshot claims can be produced. It
also shows that free holder-source availability, not candidate discovery, is
the immediate live-readiness constraint.

## What remains locked

This proof did not unlock or create retrieval, paper decisions, BUY/SELL/HOLD,
positions, trade events, paper audits, PnL, wallets, private keys, signing, real
fund movement, live execution, paid APIs, scoring, ranking, confidence,
weighted logic, embeddings or vectors. The 5m window remains support-only.
V2-9.7F and V2-9.8 remain untouched.

## Proof required before another full pilot

Printer is not ready for a newly authorized E.15-style full pilot. Before one
can be considered, a separate operator-approved lane must first address or
formally accept:

1. the observed inability of the existing free primary-plus-one-backup holder
   RPC path to produce exact holder evidence for a bounded live candidate pool;
2. the misleading failed-response target-mismatch summary precedence; and
3. a new, separately authorized one-shot readiness proof that produces exactly
   two holder-eligible candidates and then proves both candidates' exact-pair
   snapshot fields under the E.19 zero-normalization contract.

This consumed proof must not be rerun as part of E.20.

## Functionality Risks / Setbacks / Efficiency Blockers

- All eight candidates exhausted the maximum existing holder path, consuming
  24 holder calls without producing one eligible candidate.
- The complete cycle reached the exact 45-call governed ceiling before any
  DexScreener readiness snapshot. A future design must account for discovery,
  holder eligibility and snapshot readiness together without increasing the
  ceiling merely to force a pass.
- GoPlus availability did not imply holder-field availability for these fresh
  candidates.
- Twelve holder calls were rate-limited and four failed at transport, so the
  free RPC path remains operationally fragile for an eight-candidate burst.
- Summary-reason precedence obscures those factual failures as target mismatch,
  reducing operator clarity even though eligibility remains safely blocked.
- Snapshot sufficiency and zero-normalization could not be tested after the
  mandatory holder gate blocked, and must remain unproven.

## Final readiness decision

`V2_9_7E_20_BLOCKED_INSUFFICIENT_ELIGIBLE_POOL`

Do not run the full pilot, rerun E.20, or begin V2-9.7F/V2-9.8.
