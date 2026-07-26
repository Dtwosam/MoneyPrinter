# Printer V1 V2-9.8B.4 — Blocked-Supply and Source-Activity Reporting Repair Closeout

## Verdict

`V2_9_8B_4_BLOCKED_SUPPLY_REPORTING_REPAIR_PASS`

V2-9.8B.3 outcome audit and V2-9.8B.4 reporting repair are closed PASS. This does
**not** mark V2-9.8B complete and does **not** authorize another production
campaign, restart, successor, retry, tag, or push.

Next permitted lane:

```text
V2-9.8B.5 — Operational Discovery Productivity Audit
```

## Scope and identities

| Item | Value |
|---|---|
| Baseline HEAD before lane | `d7b402a63e1d2d6486ee7d4cf9ee481ae8cf2a03` |
| Audited execution | `20260726T172119Z-941d6d86aa56` |
| Repair commit | `5e86c305055a36618ba1dc550e46459a21db21e0` (`Repair V2-9.8B blocked-supply reporting`) |
| Closeout commit | this document |
| Audit doc | `docs/printer-v1-v2-9-8b-insufficient-graduated-pool-outcome-audit.md` |
| Design doc | `docs/printer-v1-v2-9-8b-blocked-supply-source-reporting-design.md` |

## Root cause

### Primary outcome (unchanged, honest)

The audited campaign closed as:

```text
BLOCKED_INSUFFICIENT_GRADUATED_POOL
```

because only **one** of **two** required market-eligible graduated candidates
passed the exact-pool `$3,000` floor:

| Mint | Liquidity | Result |
|---|---:|---|
| `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump` | `$10,248.29` | eligible |
| `4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump` | `$9.06` | rejected (`LIQUIDITY_BELOW_SELECTION_FLOOR`) |

Durable evidence also proved four governed source operations and four clean
responses (PumpPortal migration, PumpSwap pool resolution, two DexScreener
snapshots). Holder ledger:

```text
governed_requests = 4
underlying_transport_operations = 4
operation_ceiling = 45
```

### Secondary reporting defect (repaired)

Terminal reporting overloaded “zero work by this report action” onto
`source_calls`, so the original campaign total was hidden:

- `write_campaign_terminal_report` always returned `source_calls: 0`
- `build_campaign_terminal_report` omitted campaign activity and candidate
  pass/fail detail
- report-only `new_source_calls: 0` was correct for replay but easy to mistake
  for the campaign total

Classification:

```text
MIXED_BLOCKER
primary: HONEST_MARKET_SUPPLY_BLOCK
secondary: REPORTING_VISIBILITY_DEFECT
```

## Exact source-total semantics (after repair)

| Field | Meaning |
|---|---|
| `campaign_source_calls` | Original campaign governed source operations from durable holder ledger / packaged terminal evidence |
| `campaign_scheduler_calls` | Original campaign Scheduler work created (0 for this pre-lifecycle block) |
| `replay_new_source_calls` | New Source Governor work performed by report-only/replay (0 when none) |
| `replay_new_scheduler_calls` | New Scheduler work performed by report-only/replay (0 when none) |
| `source_calls` on original terminal write return | Compatibility alias of **campaign** total |
| `source_calls` on status / preflight / report-only action | Action-local “this mode performed no source work” |

No second source-accounting owner was introduced. Campaign totals prefer the
existing holder operation ledger; candidate detail is packaged from front-door
outcomes already produced by the graduated supply path.

## Candidate reporting contract

Blocked-supply terminal payloads now include:

```text
required_token_capacity
candidates_observed
candidates_validated
eligible_candidates
blocked_supply_reason
blocked_supply.candidates[]
```

Each candidate report includes:

```text
mint
source_path
stage_reached
migration_evidence
pool_confirmation
liquidity
market_cap (when present on existing snapshot evidence; else null)
eligibility_result
rejection_or_exclusion_reason
```

For the audited market class:

```text
required_token_capacity = 2
candidates_observed = 2
eligible_candidates = 1
blocked_supply_reason = BLOCKED_INSUFFICIENT_GRADUATED_POOL
```

## Implementation files

| File | Change |
|---|---|
| `docs/printer-v1-v2-9-8b-insufficient-graduated-pool-outcome-audit.md` | V2-9.8B.3 outcome audit (`V2_9_8B_3_OUTCOME_AUDIT_PASS`) |
| `docs/printer-v1-v2-9-8b-blocked-supply-source-reporting-design.md` | V2-9.8B.4A design (`V2_9_8B_4A_REPORTING_DESIGN_PASS`) |
| `src/printer_v1/operator_cli/unified_terminal_closure.py` | Campaign totals loader, blocked-supply assembler, terminal build/write/replay surfaces |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | Package front-door candidates + ledger totals on insufficient-pool lifecycle return |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Wire terminal write + report-only to authoritative reporting surface |
| `tests/test_v2_9_8b_4_blocked_supply_source_reporting.py` | Focused disposable proofs |

Preserved intentionally:

- two-token requirement
- `$3,000` exact-pool market floor
- admission ceiling 45
- Source Governor / Central Scheduler ownership
- no scoring/ranking/confidence/weighted logic
- no schema migration
- no rewrite of historical report row
  `20260726T172119Z-941d6d86aa56-report`

## Focused proof

Command:

```text
.venv/bin/python -m pytest tests/test_v2_9_8b_4_blocked_supply_source_reporting.py -q
```

Result:

```text
3 passed
```

Proofs covered:

1. Campaign with four durable ledger source operations reports
   `campaign_source_calls: 4` (and write-return `source_calls: 4`).
2. Report-only replay reports `replay_new_source_calls: 0` /
   `new_source_calls: 0`.
3. One eligible candidate and one rejected candidate with exact
   `LIQUIDITY_BELOW_SELECTION_FLOOR` reason and liquidity values.
4. Required capacity `2` versus eligible count `1` is explicit.
5. Replay is deterministic and hash-stable.
6. No duplicate report row or second artifact.
7. No retrieval/financial locked-table delta.
8. Supervision cleanup/lease release and zero active Scheduler work remain
   correct on the terminal path.

Directly affected existing suites also run:

```text
tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py
tests/test_v2_9_8b_1_first_operation_blocker_repair.py
-> 43 passed, 34 subtests passed
```

### Documented unrelated baseline failure (out of scope)

```text
tests/test_v2_9_8a_public_operational_command.py::
  PublicOperationalCommandTests::
  test_preflight_is_zero_source_and_zero_write_after_scheduler_terminal
```

Failed with fixture-database integrity/FK preflight rejection. Not caused by
the reporting surface changes; not expanded in this lane. Live authoritative
DB integrity remains `ok` with zero foreign-key violations under preflight-only.

## Public-mode verification

After the repair commit, without `-Mode run`:

| Mode | Result |
|---|---|
| `preflight-only` | `V2_9_8_OPERATIONAL_PREFLIGHT_READY`; `source_calls: 0`; integrity ok; FK 0 |
| `status` | Terminal supervision for audited campaign; lease released; cause `BLOCKED_INSUFFICIENT_GRADUATED_POOL` |
| `report-only` | Deterministic replay; `replay_new_source_calls: 0`; `replay_new_scheduler_calls: 0`; no writes |

Historical report note: the audited terminal payload was intentionally **not**
rewritten. Report-only therefore surfaces stored historical fields (campaign
totals absent/`0`, candidate detail absent) while durable ledger/source
evidence and the outcome audit remain the historical truth. Future blocked-supply
closes write the full surface into the terminal report JSON at original write
time.

## Money-usefulness contribution

1. Operators can distinguish an honest market-supply block from a silent source
   outage once future terminals embed campaign source totals and candidate
   pass/fail reasons.
2. Capital remains protected by the unchanged two-token and `$3,000` floor rules.
3. Report-only stays zero-source and non-mutating, preserving auditability.
4. Discovery productivity can now be judged next without confusing replay zeros
   for campaign work.

## What improved

- Authoritative campaign vs replay source-total semantics.
- Blocked-supply capacity math and per-candidate rejection reasons in terminal
  report payloads for new closes.
- Lifecycle packaging of front-door candidate outcomes for terminal assembly.
- Focused disposable proof coverage for the audited defect class.

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
- historical rewrite of the audited report row

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status / residual risk |
|---|---|
| Historical audited report still lacks embedded campaign totals | Accepted; durable ledger + audit doc preserve truth; no rewrite authorized |
| Status/preflight `source_calls: 0` still action-local | Documented; use `campaign_source_calls` for campaign totals |
| Thin market supply may recur | Expected honest block possible; next lane is discovery productivity audit |
| Fixture preflight baseline failure in 8A public command test | Documented, out of scope |
| Market cap optional when not present on front-door candidate packaging | No extra source call; field remains nullable |
| Over-expanding into ceilings/eligibility | Explicitly not done |

## Stop conditions honored

- No production `-Mode run`
- No live source calls during repair proof
- No tag or push
- No retrieval/financial unlock
- No V2-9.8B complete claim
