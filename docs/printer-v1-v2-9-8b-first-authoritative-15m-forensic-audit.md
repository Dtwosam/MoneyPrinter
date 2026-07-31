# Printer V1 V2-9.8B First Authoritative WINDOW_15M Campaign Forensic Audit

Date: 2026-07-30

Audit baseline:
`1de7da6c97017c3a9a4119ac2870e9d9134df60e`

Audited execution:
`20260731T002406Z-7612696c7295`

Audit verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_FORENSIC_AUDIT_PASS`

Campaign verdict remains:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`

## 1. Boundary

This was a read-only forensic audit of the authoritative database and retained
operator artifacts. It performed no provider/RPC call, project runtime command,
database mutation, report repair, recovery, campaign rerun, memory generation,
retrieval, paper decision, position, trade, audit, or PnL action.

The authoritative database remained byte-identical during the audit:

```text
before: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
after:  f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
```

Integrity was `ok`, foreign-key check returned zero rows, and the Git worktree
remained clean at the exact audit baseline.

## 2. Preserved Attempt Identity

```text
execution_id:     20260731T002406Z-7612696c7295
campaign_id:      20260731T002406Z-7612696c7295-campaign
run_id:           20260731T002406Z-7612696c7295-campaign-run
cycle_id:         20260731T002406Z-7612696c7295-cycle
configuration_id: 20260731T002406Z-7612696c7295-configuration
supervision_id:   20260731T002406Z-7612696c7295-supervision
```

The permanent attempt marker exists, identifies attempt number one, pins launch
commit `b5761b6501ad757eecdfc8cfabce6828d5a899bd`, and records
`rerun_authorized=false`.

The verified pre-campaign backup and restore-rehearsal databases both retain the
pre-attempt SHA-256:

```text
e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6
```

## 3. Underlying Campaign Outcome

The durable exhaustion certificate proves that the first terminal market/source
outcome was correctly classified as:

```text
SOURCE_VISIBILITY_SHORTAGE
```

It was not proven to be a true market-supply shortage.

Exact durable facts:

| Fact | Value |
|---|---:|
| Required eligible capacity | 2 |
| Eligible reserve count | 1 |
| Unique tokens observed | 30 |
| Rejected candidates | 29 |
| Pools confirmed | 48 |
| Fresh market checks | 25 |
| Discovery rounds | 5 |
| Source operations used | 30 |
| Source operations remaining | 0 |
| Provider failures | 15 |
| Liquidity-stage provider failures | 12 |
| Stale-evidence exclusions | 3 |

Liquidity outcomes:

| Outcome | Count |
|---|---:|
| Exact liquidity above floor | 1 |
| Exact liquidity below floor | 12 |
| Malformed or partial liquidity response | 12 |

Rejection reasons:

| Reason | Count |
|---|---:|
| `LIQUIDITY_BELOW_SELECTION_FLOOR` | 12 |
| `LIQUIDITY_SOURCE_dexscreener_malformed_fixture` | 12 |
| `DUPLICATE_ACTIVE_TRACKING` | 2 |
| `TERMINAL_TRACKING_STATE` | 3 |

The certificate states:

```text
last_reason_discovery_could_not_continue:
DISCOVERY_OPERATION_BUDGET_EXHAUSTED

unexplored_work_prevented_by_hard_ceiling: true
```

The unavailable channels were:

- `direct_pump_finalized_live_tail`;
- `dexscreener_exact_pool_market`.

Therefore the source/supply result is an honest bounded shortage: only one of
two required eligible candidates was proven before the 30-operation discovery
budget was exhausted, with material malformed/partial exact-liquidity evidence
and provider failures.

## 4. Six-Unit Accounting Defect

The public command correctly failed closed with:

```text
SIX_UNIT_ACCOUNTING_BLOCKED
```

It did not fabricate a synthetic zero report.

However, the retained terminal summary proves an accounting completeness defect:

```text
campaign_source_calls: 30
stage_evidence_count: 1
report_written: false
report_block_reason: SIX_UNIT_EVIDENCE_MISSING
```

The only retained partial six-unit stage evidence is
`DIRECT_PUMP_NOMINATION`. It contains four transport operations:

- one successful `getSignaturesForAddress` operation with three normalized rows;
- three failed `getTransaction` operations.

The later governed discovery and exact-liquidity work that drove the durable
30-operation exhaustion certificate was not present in the campaign accounting
owner's completed stage-evidence sequence when the shortage exception reached
terminalization.

This is not evidence that the remaining operations did not occur. The command
output and durable exhaustion certificate independently agree on 30 source
operations. It is evidence that the canonical six-unit accounting handoff did
not close or ingest all executed stages before terminal reporting.

Root-cause classification:

```text
MISSING_COMPLETE_STAGE_EVIDENCE_HANDOFF_ON_BOUNDED_SHORTAGE
```

A code change is justified, but only after a dedicated design lane.

## 5. Exact-Identity Report-Only Defect

No terminal report row exists for the July 31 campaign because terminalization
correctly set `report_written=false` when mandatory six-unit evidence was
missing.

The current public `report-only` implementation selects:

```sql
WHERE report_state = 'REPORT_TERMINAL'
ORDER BY created_at DESC, report_id DESC
LIMIT 1
```

That query is global rather than bound to the intended campaign/run/report
identity. It therefore replayed the newest older terminal report:

```text
campaign_id: 20260728T224158Z-6bf2c4fd8e7e-campaign
campaign_source_calls: 14
```

This was not the July 31 attempt and could not represent its 30 source calls,
source-visibility shortage, exhaustion certificate, or accounting-blocked
summary.

The zero-source/no-write replay boundary remained safe, but the returned object
was semantically stale for the operator's current-attempt closeout.

Root-cause classification:

```text
GLOBAL_LATEST_REPORT_SELECTION_WITHOUT_EXACT_ATTEMPT_IDENTITY
```

The future design must prevent a missing current report from silently falling
back to another campaign. It must return an exact-identity blocked projection or
explicit `REPLAY_BLOCKED` result instead.

## 6. Terminal Safety and Preservation

The fail-closed terminal path preserved the following:

- first terminal cause `SOURCE_VISIBILITY_SHORTAGE`;
- accounting status `SIX_UNIT_ACCOUNTING_BLOCKED`;
- zero closure errors;
- supervision state `TERMINAL`;
- terminal status `COMPLETED`;
- lease released;
- zero active owned work after cleanup;
- zero active Scheduler jobs or locks;
- no automatic retry, restart, resume, or successor;
- no campaign windows or factory run materialized;
- locked retrieval and financial baselines unchanged;
- no position, trade event, paper-trade audit, or PnL unlock.

The terminal system therefore protected the corpus and downstream capabilities,
even though it could not produce a complete authoritative campaign report.

## 7. Campaign Classification After Forensics

The audit can now distinguish two layers:

### Underlying bounded source/supply outcome

```text
HONEST_SOURCE_VISIBILITY_SHORTAGE
```

This is supported by the durable exhaustion certificate and exact budget facts.

### Campaign closeout outcome

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE
```

This remains unchanged because the canonical campaign report and exact-identity
report-only replay are incomplete. A forensic document must not be used to
manufacture or backfill the missing canonical report.

## 8. Money-Usefulness Contribution

The audit preserves an important negative lesson without converting incomplete
reporting into clean memory: Printer saw broad candidate inventory, but exact
liquidity visibility and provider quality left only one eligible candidate
inside the bounded operation budget. This is useful capital-protection context,
but it is not yet a clean retrievable memory and cannot support a paper decision.

The audit also identifies the exact infrastructure defects that prevented this
honest shortage from becoming a trustworthy terminal campaign record.

## 9. What This Audit Improves

- reconstructs the exact July 31 attempt identity;
- proves the shortage was source-visibility driven rather than a generic supply
  claim;
- reconciles the 30-operation budget at the campaign/certificate level;
- identifies the missing stage-evidence handoff boundary;
- proves why `report-only` replayed the stale July 28 campaign;
- separates safe terminal cleanup from incomplete report truth;
- preserves the no-rerun and no-successor boundary.

## 10. What This Audit Still Does Not Unlock

This audit does not unlock:

- repair implementation;
- report mutation or backfill;
- another campaign attempt;
- provider/RPC calls;
- discovery-only supplementation;
- recovery or cursor work;
- memory generation;
- `WINDOW_1H` or longer windows;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, paper-trade audits, or PnL;
- wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

## 11. Functionality Risks / Setbacks / Efficiency Blockers

- A shortage exception can occur after substantial governed source work but
  before every stage has exposed closed accounting evidence.
- Process-local accounting evidence is insufficient when later source work is
  durable but not ingested into the campaign owner.
- Global latest-report selection can return a valid but unrelated historical
  campaign, creating misleading operator output.
- Exact-liquidity malformed/partial responses consumed 12 of 30 operations and
  materially reduced productive eligibility proof.
- The direct Pump live-tail and exact DexScreener channel were unavailable in the
  bounded attempt.
- The permanent attempt marker correctly prevents treating a repair as permission
  to rerun the same campaign.

## 12. Exact Next Permitted Task

```text
V2-9.8B First Authoritative WINDOW_15M Accounting and Exact-Identity Report-Only Repair Design
```

That lane is design/specification only. It must define:

1. how every governed operational stage closes and hands immutable six-unit
   evidence to one campaign accounting owner before a bounded shortage raises;
2. how durable source-operation truth is reconciled without inventing evidence or
   creating a second accounting authority;
3. exact campaign/run/report identity inputs for `report-only`;
4. explicit behavior when the requested attempt has an accounting-blocked
   terminal summary but no terminal report row;
5. deterministic `REPLAY_BLOCKED`/blocked-summary behavior instead of fallback to
   another campaign;
6. focused disposable-DB proof for success, honest shortage, missing stage
   evidence, stale-report prevention, zero-source replay, and no downstream
   deltas.

The design may not implement code, mutate the authoritative database, repair the
July 31 report, contact providers, or authorize another campaign.
