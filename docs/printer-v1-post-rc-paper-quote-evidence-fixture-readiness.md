# Paper Quote Evidence Fixture Readiness

This is a pre-Lane-7 Post-RC planning and fixture-readiness document.

It is not Lane 7. It is not Jupiter implementation. It is not live quote collection. It is not source adapter work. It is not a paper decision task.

Printer V1 remains Solana-only, Solana memecoin-only, paper-trading only, free/public-source only, no live wallet, no private keys, no real funds, no live execution, no paid API dependency, no scoring, no ranking, no confidence percentages, no weighted decision logic, no dirty-memory retrieval, no BUY unlock, no paper positions, no paper trade events, and no PnL.

## Current Blocker Summary

Lane 6 is complete. Fresh context validation is complete. Missing source candidates have been evaluated. Jupiter paper quote realism readiness has been documented.

Current validated state:

- Fresh 15m memory evidence exists from snapshots `32, 33, 34, 35, 36`.
- Snapshot coverage was complete.
- Context collection for snapshot `36` created seven fresh context rows.
- Source quality was acceptable for the evidence window.
- Historical source failures remained visible.
- Clean memory still does not exist.
- Retrieval is still blocked.
- Paper decisions are still blocked.
- Paper positions remain `0`.
- Paper trade events remain `0`.

Remaining blockers:

- `chain_heat_label: SOLANA_UNKNOWN`
- `market_regime_label: UNKNOWN`
- `safety_status_label: SAFETY_UNKNOWN`
- `entry_realism_label: ENTRY_UNKNOWN`
- `exit_realism_label: EXIT_UNKNOWN`
- `flow_direction_label: FLOW_UNKNOWN`
- `flow_pressure_label: FLOW_UNKNOWN`

This task exists because future paper quote evidence may help only two blockers:

- `entry_realism_label`
- `exit_realism_label`

Lane 7 remains blocked because paper quote evidence cannot solve chain heat, market regime, safety, flow direction, or flow pressure by itself. It also cannot create clean memory by itself.

## Paper Quote Evidence Contract

Future paper quote evidence should be represented as paper-realism evidence only. The exact storage schema and exact Jupiter field names must be verified later before any adapter work.

Candidate evidence shape:

| Field | Purpose | Notes |
|---|---|---|
| `token_id` | Links quote evidence to the tracked token | Required for any future persisted evidence |
| `pair_id` | Links quote evidence to the tracked pair | Required for any future persisted evidence |
| `snapshot_id` | Links quote evidence to the nearest stored token snapshot | Required for window targeting |
| `memory_window_id` or `evidence_window_id` | Links quote evidence to the reviewed evidence window | Required before quote evidence can support memory audit |
| `quote_direction` | `ENTRY` or `EXIT` | Categorical only |
| `quote_purpose` | `PAPER_REALISM_ONLY` | Any other purpose is invalid for V1 |
| `input_mint` | Candidate source field | Exact source-specific field name must be verified later |
| `output_mint` | Candidate source field | Exact source-specific field name must be verified later |
| `input_amount` | Paper quote input amount | Must be paper size only, never real funds |
| `output_amount` | Candidate quoted output amount | Exact units and source field name must be verified later |
| `route_available` | Whether a route exists | Boolean or categorical future field |
| `route_plan_present` | Whether source returned a route plan | Candidate field to verify later |
| `slippage_bps` | Paper slippage assumption or source parameter | Must not become a score |
| `price_impact_label` or candidate price impact field | Categorical price-impact realism | Candidate source-specific details must be verified later |
| `quote_captured_at` | Quote capture time | Required for freshness checks |
| `quote_freshness_label` | Fresh/stale/missing/unknown status | Categorical only |
| `source_status` | Source status | Must follow existing source-status rules |
| `data_quality_label` | Data quality | Must follow existing data-quality rules |
| `failure_reason` | Failed quote reason | Required when source request fails |
| `no_route_reason` | No-route reason | Required when route is unavailable |
| `source_request_id` | Source Governor request link | Required for persisted source-governed evidence |
| `source_response_id` | Source Governor response link | Present on successful source response |
| `source_failure_id` | Source Governor failure link | Present on failed source request |

No field in this contract implies live execution, transaction building, transaction signing, wallet use, real funds, BUY, paper position creation, or clean-memory eligibility by itself.

## Fixture States

Fixture states for future tests and adapter-readiness review:

| Fixture state | Required fixture shape | Expected evidence result |
|---|---|---|
| Fresh entry route available | `quote_direction=ENTRY`, `quote_purpose=PAPER_REALISM_ONLY`, route present, fresh captured time, clean source/data labels | May map to `ENTRY_ROUTE_AVAILABLE` |
| Fresh exit route available | `quote_direction=EXIT`, `quote_purpose=PAPER_REALISM_ONLY`, route present, fresh captured time, clean source/data labels | May map to `EXIT_ROUTE_AVAILABLE` |
| No entry route | `quote_direction=ENTRY`, no route, no-route reason present | Maps to `ENTRY_ROUTE_UNAVAILABLE`; remains blocking/caution evidence |
| No exit route | `quote_direction=EXIT`, no route, no-route reason present | Maps to `EXIT_ROUTE_UNAVAILABLE`; remains blocking/caution evidence |
| Stale quote | route may exist, but quote freshness is stale or captured outside allowed tolerance | Audit-only; cannot support clean entry/exit realism |
| Failed quote | source failed or critical quote data missing | Audit-only; failure must remain visible |
| Missing quote | no quote evidence linked to the target snapshot/window | `ENTRY_REALISM_UNKNOWN` or `EXIT_REALISM_UNKNOWN` |
| Quote target mismatch | quote links to the wrong token, pair, snapshot, or evidence window | Dirty/audit-only; cannot support clean eligibility |
| Quote not paper-only | quote purpose is anything other than `PAPER_REALISM_ONLY` | Invalid for V1 and must be blocked |

## Label Mapping

These are categorical labels only. They are not scores, rankings, confidence values, weighted logic, or decision triggers.

ENTRY mapping:

| Fixture condition | Candidate label |
|---|---|
| Fresh governed entry quote with available route | `ENTRY_ROUTE_AVAILABLE` |
| Fresh governed entry quote with no route | `ENTRY_ROUTE_UNAVAILABLE` |
| Fresh entry route exists but slippage/price-impact/source caveat needs caution | `ENTRY_REALISM_CAUTION` |
| Missing, stale, failed, mismatched, or invalid entry quote | `ENTRY_REALISM_UNKNOWN` |

EXIT mapping:

| Fixture condition | Candidate label |
|---|---|
| Fresh governed exit quote with available route | `EXIT_ROUTE_AVAILABLE` |
| Fresh governed exit quote with no route | `EXIT_ROUTE_UNAVAILABLE` |
| Fresh exit route exists but slippage/price-impact/source caveat needs caution | `EXIT_REALISM_CAUTION` |
| Missing, stale, failed, mismatched, or invalid exit quote | `EXIT_REALISM_UNKNOWN` |

Quote evidence must not create or imply:

- `BUY`
- `SELL`
- `HOLD`
- paper decision permission
- paper position permission
- PnL
- clean memory by itself

## Source Governor Rules

Future paper quote evidence must be source-governed.

Requirements:

- Source request recorded.
- Source response recorded when a response exists.
- Source failure recorded when collection fails.
- Quote linked to token, pair, snapshot, and evidence window.
- Stale quote evidence visible.
- Failed quote evidence visible.
- No-route evidence visible.
- Source status recorded.
- Data quality label recorded.
- No direct calls from the memory engine.
- No direct calls from the paper decision engine.
- No direct calls through scheduler bypass.
- No external API loop outside the Source Governor path.
- No transaction-build, transaction-sign, or transaction-send source path.

Future request naming should be reviewed later. A planning-only candidate name is `jupiter_paper_quote_context`, but no source adapter is approved by this document.

## Central Scheduler Rules

Future paper quote collection must be scheduler-controlled.

Requirements:

- Bounded job.
- Operator-approved during manual proof.
- No continuous loop.
- No source spam.
- No runtime expansion without roadmap approval.
- No direct clean-memory unlock.
- No direct retrieval unlock.
- No direct paper decision unlock.
- No BUY unlock.
- No paper position creation.
- Token snapshots and memory-window close snapshots keep priority over paper quote checks.

Paper quote jobs, if ever approved, should run only as narrowly scoped paper-realism evidence jobs near an approved memory/audit target.

## Clean-Memory Safety Gates

Paper quote evidence alone cannot make memory clean.

Quote evidence can only help entry/exit realism:

- It may help move `ENTRY_UNKNOWN` toward `ENTRY_ROUTE_AVAILABLE`, `ENTRY_ROUTE_UNAVAILABLE`, `ENTRY_REALISM_CAUTION`, or `ENTRY_REALISM_UNKNOWN`.
- It may help move `EXIT_UNKNOWN` toward `EXIT_ROUTE_AVAILABLE`, `EXIT_ROUTE_UNAVAILABLE`, `EXIT_REALISM_CAUTION`, or `EXIT_REALISM_UNKNOWN`.

Quote evidence cannot solve:

- `SOLANA_UNKNOWN`
- `UNKNOWN` market regime
- `SAFETY_UNKNOWN`
- `FLOW_UNKNOWN` direction
- `FLOW_UNKNOWN` pressure

Safety gates:

- Unknown safety, market, chain, or flow context still blocks clean memory.
- Stale quote remains audit-only.
- Failed quote remains audit-only.
- Missing quote remains unknown.
- Quote target mismatch remains dirty/audit-only.
- Non-paper-only quote evidence is invalid.
- Dirty memory cannot enter retrieval.
- Audit-only memory cannot become clean because quote evidence exists.
- No paper decision, BUY, position, trade event, or PnL may occur without valid clean-memory-backed gates.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Route-available fixture can map to route-available label.
- No-route fixture maps to route-unavailable label.
- Stale fixture remains audit-only.
- Failed fixture remains audit-only.
- Missing fixture remains unknown.
- Target mismatch blocks clean eligibility.
- Non-paper-only evidence blocks clean eligibility.
- Quote evidence alone does not make memory clean.
- Quote evidence alone does not unlock retrieval.
- Quote evidence does not create paper decisions.
- Quote evidence does not create positions.
- Quote evidence does not create trade events.
- Quote evidence does not create PnL.

The tests must not:

- Call Jupiter.
- Fetch live data.
- Require environment variables.
- Require API keys.
- Mutate the persistent DB.
- Add source adapters.
- Add runtime behavior.

## Non-Goals

This task does not:

- Implement a Jupiter adapter.
- Call Jupiter.
- Fetch live quote data.
- Add source fetching.
- Mutate the persistent database.
- Create real token snapshots.
- Create real context rows.
- Rebuild memory.
- Run retrieval.
- Create paper decisions.
- Create BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Start Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

Create a fixture-only schema design for quote evidence storage.

That task should decide whether future paper quote evidence needs a dedicated table or can be stored through existing governed source response/context payloads. It should remain documentation/test-only unless the operator separately approves a minimal schema migration.

Alternative safe tasks:

- Solana public RPC/token safety readiness plan.
- GoPlus-style token safety source readiness plan.

Do not recommend Lane 7 until clean memory exists.
