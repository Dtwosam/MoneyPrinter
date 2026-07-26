# Printer V1 V2-9.8B.3 — Insufficient Graduated Pool Outcome Audit

## Verdict

`V2_9_8B_3_OUTCOME_AUDIT_PASS`

This is an audit-only closeout of the audited execution. It does **not** mark
V2-9.8B complete, does **not** authorize another production campaign, restart,
successor, retry, tag, or push, and does **not** unlock retrieval or any
financial capability.

## Scope and identities

| Item | Value |
|---|---|
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Audited HEAD | `d7b402a63e1d2d6486ee7d4cf9ee481ae8cf2a03` |
| Execution | `20260726T172119Z-941d6d86aa56` |
| Campaign | `20260726T172119Z-941d6d86aa56-campaign` |
| Configuration | `20260726T172119Z-941d6d86aa56-configuration` |
| Run | `20260726T172119Z-941d6d86aa56-campaign-run` |
| Cycle | `20260726T172119Z-941d6d86aa56-cycle` |
| Supervision | `20260726T172119Z-941d6d86aa56-supervision` |
| Report | `20260726T172119Z-941d6d86aa56-report` |
| Report hash | `9d520e7429842cebcd27f82381cdc8ae3df3159ea6b1ab6ea034aa672efd09c2` |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Pre-campaign backup | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260726T172119Z-941d6d86aa56/printer_v1.pre-campaign.backup.sqlite3` |

Baseline verification:

- `git rev-parse HEAD` matched the expected commit.
- Working tree was clean before this audit lane.
- Both SQLite files were present and comparable read-only.

## Campaign outcome

| Field | Observed |
|---|---|
| Campaign state | `TERMINAL_COMPLETED` |
| First terminal cause | `BLOCKED_INSUFFICIENT_GRADUATED_POOL` |
| Run state | `TERMINAL_COMPLETED` |
| Cycle state | `TERMINAL_COMPLETED` |
| Lifecycle started | `false` (`run_status` surface `NOT_STARTED`) |
| Token capacity | `2` |
| Main window | `WINDOW_15M` |
| Support 5m only | `true` |
| Restart created | `false` |
| Successor created | `false` |
| Supervision | `TERMINAL` / `COMPLETED` |
| Cleanup completed | yes |
| Lease released | yes |
| Active / locked Scheduler work | `0` |
| Integrity | `ok` |
| Foreign-key violations | `0` |

The campaign closed safely as an honest market-supply block before lifecycle,
tracking, retrieval, or financial work.

## Candidate evidence

Two candidates were evaluated under the graduated-pool / `$3,000` exact-pool
market boundary.

### 1. Eligible candidate

| Field | Value |
|---|---|
| Mint | `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump` |
| Source path | PumpPortal migration → PumpSwap signature pool resolution → DexScreener pair snapshot |
| Stage reached | PumpSwap confirmed + liquidity floor proven |
| Migration signature | `3WEvqcaMEaziN1Uc88oQvyMVSc5LUKVNVdskBUbkMbxW19hC2T2sxUP6MPiauE7m9dqvvtY3p2kpcfZCbELKKkDs` |
| PumpSwap pool | `A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu` |
| Pool confirmation | confirmed (`confirmed_pumpswap_pool` / `resolved_unique_pumpswap_pool`) |
| Liquidity USD | `10248.29` |
| Market cap | `25247.0` |
| Eligibility | **eligible** — at or above the `$3,000` exact-pool floor |
| Rejection reason | none |

Registry observation for this mint is campaign-time:

```text
first_observed_at: 2026-07-26T17:21:19.127768+00:00
lifecycle_state: PUMPSWAP_GRADUATED_CONFIRMED
```

### 2. Rejected candidate

| Field | Value |
|---|---|
| Mint | `4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump` |
| Source path | Prior graduated registry entry re-enriched by DexScreener pair snapshot |
| Stage reached | PumpSwap confirmed historically; market floor failed this cycle |
| PumpSwap pool | `9G3n5P93x4mfxMZqoH6pN9aMv2SJEkoZFs7eGR7qrWUh` |
| Liquidity USD | `9.06` |
| Market cap | `5.0` |
| Eligibility | **rejected** |
| Rejection reason | `LIQUIDITY_BELOW_SELECTION_FLOOR` / below `$3,000` exact-pool floor |

Registry first observation for this mint is earlier than the audited campaign
(`2026-07-26T14:13:21.783720+00:00`, previous operation window). This campaign
re-evaluated it for market eligibility and correctly rejected it.

### Capacity math

```text
required_token_capacity = 2
candidates_observed     = 2
eligible_candidates     = 1
result                  = BLOCKED_INSUFFICIENT_GRADUATED_POOL
```

One candidate qualified; two were required. This is a correct market-supply
block, not a Source Governor, Scheduler, lease, or holder-budget fault.

## Source activity

Read-only main-vs-backup delta for the audited execution:

| Evidence | Pre-campaign backup | Authoritative after campaign | Delta |
|---|---:|---:|---:|
| `printer_source_requests` | 1121 | 1125 | **+4** |
| `printer_source_responses` | 1074 | 1078 | **+4** |
| `printer_holder_campaign_operation_ledgers` | 0 | 1 | **+1** |
| `printer_pumpswap_graduated_candidate_registry` | 1 | 2 | **+1** (new mint) |
| Campaign / run / cycle / report / supervision rows | baseline | +1 each | campaign graph |

Four governed source requests and four clean responses were persisted:

| Request id | Source | Request kind | Response status / quality |
|---:|---|---|---|
| 1122 | `pumpportal` | `pumpfun_migration_stream` | `COMPLETE` / `CLEAN_DATA` |
| 1123 | `pumpswap` | `pumpswap_signature_pool_resolution` | `COMPLETE` / `CLEAN_DATA` |
| 1124 | `dexscreener` | `pair_market_snapshot` | `COMPLETE` / `CLEAN_DATA` (CrR3… liquidity `$10,248.29`) |
| 1125 | `dexscreener` | `pair_market_snapshot` | `COMPLETE` / `CLEAN_DATA` (4hi84… liquidity `$9.06`) |

Holder operation ledger for this campaign run/cycle:

```text
run_id: 20260726T172119Z-941d6d86aa56-campaign-run
cycle_id: 20260726T172119Z-941d6d86aa56-cycle
operation_ceiling: 45
governed_requests: 4
underlying_transport_operations: 4
zero_transport_operations: 9
reserved_snapshot_operations: 2
reserved_snapshot_completion_operations: 4
```

Authoritative campaign source total from durable campaign-attributable evidence:

```text
campaign_source_calls = 4
campaign_scheduler_calls = 0
```

No Scheduler work rows were created. No active or locked work remains.

## Report reconciliation

### What the terminal surfaces currently show

`terminal-summary.json` and `write_campaign_terminal_report` return surface:

```text
report.source_calls: 0
report.scheduler_calls: 0
```

`report-only` style replay surfaces:

```text
new_source_calls: 0
```

### What is correct

- `report-only` / replay **new** source calls = `0` is correct when replay
  performs no new Source Governor work.
- The durable campaign ledger and source request/response delta prove the
  original campaign performed **four** governed source operations.
- Campaign closed with one terminal report row and one durable artifact; no
  restart or successor was created.

### What is incorrect / incomplete

- Terminal report write surface records `source_calls: 0`, which erases the
  original campaign total and confuses campaign activity with report-write /
  replay activity.
- The durable terminal report payload does not expose campaign-attributable
  source totals, required vs eligible capacity, or per-candidate pass/fail
  reasons.
- An operator reading only the terminal summary cannot reconstruct:

```text
required 2 vs eligible 1
CrR3… eligible at $10,248.29
4hi84… rejected at $9.06 for liquidity floor
campaign_source_calls = 4
```

Classification of this reporting gap is secondary to the market block:

```text
MIXED_BLOCKER
primary:   HONEST_MARKET_SUPPLY_BLOCK
secondary: REPORTING_VISIBILITY_DEFECT
```

## Blocker classification

```text
MIXED_BLOCKER
primary: HONEST_MARKET_SUPPLY_BLOCK
secondary: REPORTING_VISIBILITY_DEFECT
```

| Class | Meaning for this execution |
|---|---|
| Primary | Honest insufficient graduated / market-eligible pool: 1 of 2 required tokens passed the exact-pool `$3,000` floor after real free-public governed enrichment. |
| Secondary | Reporting visibility defect: durable evidence proves 4 governed source operations and explicit candidate outcomes, but the terminal report surface hides campaign source totals and candidate eligibility detail. |
| Not this run | Not a holder-budget accounting defect (ledger persisted correctly with 4). |
| Not this run | Not lease/supervision contention replacing terminal cause. |
| Not this run | Not Scheduler residue, foreign-key, or integrity failure. |
| Not this run | Not a retrieval/financial unlock or lifecycle start. |

## Money-usefulness contribution

This blocked outcome is money-useful even without activation:

1. **Capital protection** — Printer refused to start lifecycle/tracking when only
   one market-eligible graduated token existed.
2. **Honest market boundary** — The `$3,000` exact-pool floor rejected a
   `$9.06` graduated pool instead of manufacturing a second slot.
3. **Real free-public source path** — Migration, PumpSwap confirmation, and two
   DexScreener snapshots were governed, recorded, and quality-labeled.
4. **Selective memory growth discipline** — No dirty activation, no forced
   second token, no retrieval or paper decision from an incomplete pool.
5. **Operator truth gap remains** — Without reporting repair, the next operator
   cannot cheaply separate “market could not supply two eligible tokens” from
   “sources never ran,” which wastes retry judgment and obscures productivity.

## What was proved

- Campaign safely closed as `BLOCKED_INSUFFICIENT_GRADUATED_POOL`.
- Two candidates were evaluated; one eligible, one liquidity-floor rejected.
- Four governed source requests and four clean responses were persisted.
- Holder ledger records four governed/transport operations under ceiling 45.
- Integrity `ok`; zero foreign-key violations; zero active/locked work.
- No restart or successor.
- No retrieval or financial delta.
- Terminal report incorrectly surfaces `source_calls: 0` while durable campaign
  evidence shows four campaign source operations.
- Report-only new-source-call zero is correct for replay, not for original
  campaign accounting.

## What remains locked

- retrieval
- paper decisions
- BUY / SELL / HOLD
- paper positions
- trade events
- paper audits
- PnL
- live execution / wallets / private keys / signing
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- V2-9.8B complete claim
- automatic production retry authorization

## Proof required before another retry

Before any operator-authorized production retry, the secondary reporting defect
must be repaired and proved offline:

1. Original campaign totals come from durable campaign-attributable evidence
   (holder ledger / stage-local governed operations), not from the report-write
   call count.
2. Report-only replay totals remain separate and zero when no new work runs.
3. Blocked-supply reports show required capacity, observed count, eligible
   count, and exact per-candidate pass/fail reasons.
4. Terminal report replay remains deterministic and idempotent with no
   duplicate report row and no campaign evidence mutation.
5. Focused disposable fixtures prove the above without live sources or
   production `-Mode run`.

After reporting repair PASS, the next permitted lane remains:

```text
V2-9.8B.5 — Operational Discovery Productivity Audit
```

That later audit, not this document, decides whether discovery productivity is
adequate for another bounded production attempt. This outcome audit alone does
not authorize a retry.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / setback / blocker | Impact | Mitigation / status |
|---|---|---|
| Terminal `source_calls: 0` hides real campaign source activity | Operator may think sources never ran and mis-classify the block | Repair in V2-9.8B.4 using durable ledger + stage-local evidence |
| Candidate eligibility detail not in terminal report payload | Retry judgment lacks exact mint-level pass/fail and liquidity | Persist blocked-supply candidate surface into terminal report JSON at write time |
| Report-only zero totals easily confused with campaign totals | Replay correctness is real but semantics are overloaded | Split `campaign_*` vs `replay_new_*` fields |
| Market supply may remain thin at next attempt | Another honest insufficient-pool close is still possible | Treat as market fact; do not loosen `$3,000` floor or two-token requirement |
| Prior mint reuse from registry can re-enter evaluation | Low-liquidity graduated mints can consume a DexScreener call and still fail | Keep floor categorical; improve productivity audit later (V2-9.8B.5) |
| Expanding repair into ceilings/schemas/lifecycle unlock | Would over-scope and risk policy drift | Reporting-only repair; no ceiling, capacity, eligibility, schema, or unlock change |
| Broad regression expansion | Credit and time waste on unrelated baseline noise | Focused disposable reporting/terminal-closure tests only |

## Stop conditions honored

- No production campaign run.
- No live source calls during this audit.
- No restart, successor, tag, or push.
- No retrieval or financial activation.
- No claim that V2-9.8B is complete.
