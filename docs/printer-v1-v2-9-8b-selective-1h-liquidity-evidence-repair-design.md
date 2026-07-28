# Printer V1 V2-9.8B Selective-1h Liquidity Evidence Repair Design

## Status and authority

`APPROVED_FOR_NARROW_IMPLEMENTATION`

This design implements the repair authorized by
`docs/printer-v1-v2-9-8b-selective-1h-liquidity-evidence-blocker-audit.md`.
It is subordinate to `AGENTS.md`, the Clean Master Spec, the active V2 memory-
growth build order, the Memory Factory Guide, and the Python Builder Guide.

Baseline: `43511ca19413853fa9f7e7f3626eab72d69aa08a` on `master`, clean.

Primary blocker classification: `COMMITTED_CODE_DEFECT`. The external transport
outage was an expected operational event and admission correctly failed closed.
The committed defect was that liquidity-stage failures and their lineage were
discarded, exhaustion ownership was not bound by the operational owner, and the
terminal path converted source unavailability into
`BLOCKED_INSUFFICIENT_GRADUATED_POOL`.

## Scope

Allowed:

- enrich the existing exact-pool liquidity evidence value object;
- preserve candidate lineage through the graduated front door, eligible supply,
  exhaustion certificate JSON, blocked-supply report, and terminal artifact;
- aggregate liquidity-stage provider failures and unavailable channels;
- bind existing exhaustion ownership fields to campaign, execution, run, cycle;
- select truthful existing shortage classifications as pre-lifecycle causes;
- add focused offline tests using fixtures and temporary databases.

Forbidden:

- live source calls or any discovery/Scheduler/campaign/lifecycle proof runtime;
- retries, provider fallback, restart, resume, successor, or budget changes;
- mint-wide or alternative-pair liquidity;
- historical liquidity reuse as current evidence;
- authoritative database mutation or historical-row cleanup;
- 4h/12h/24h enablement, retrieval, decisions, positions, trades, audits, PnL,
  wallets, signing, real funds, scores, ranks, confidence, weights, vectors, or
  embeddings.

## Canonical owners

- `graduated_liquidity_front_door.py` owns exact mint/pool evaluation and the
  candidate-local liquidity evidence envelope.
- Source Governor and the shared source ledger remain the sole request,
  response, and failure persistence owners.
- `eligible_token_supply.py` owns campaign aggregation, current reserve
  eligibility, shortage classification, and exhaustion certificate persistence.
- `authoritative_live_operational_campaign.py` owns operational identity binding
  and the pre-lifecycle terminal cause.
- `unified_terminal_closure.py` owns blocked-supply normalization and terminal
  artifact surfacing.

No owner may perform a second source call or reconstruct a provider result.

## Candidate liquidity evidence contract

Every attempted candidate carries one immutable in-process/report envelope:

- `mint`;
- exact confirmed PumpSwap `pool`;
- `source_request_id`;
- exactly one of `source_response_id` or `source_failure_id` when a governed
  operation completed;
- `failure_type`, nullable on a successful response;
- stable categorical `reason`;
- human/provider `detailed_reason` without replacing the categorical reason;
- `source_status`;
- categorical `outcome_category`;
- current `liquidity_usd`, nullable unless exact current evidence supplied it.

The source-ledger IDs are copied from `GovernedSourceExecutionResult`; they are
never inferred from whole-table counts or request-key parsing. A cooldown or
identity skip has null source IDs because no source operation occurred.

## Categorical outcome contract

The smallest new candidate-local category set is:

| Category | Meaning | Current admission |
|---|---|---|
| `LIQUIDITY_EXACT_ABOVE_FLOOR` | Fresh COMPLETE response, exactly one Solana mint+PumpSwap pool match, finite non-negative USD liquidity at/above $3,000 | eligible for later unchanged gates |
| `LIQUIDITY_EXACT_BELOW_FLOOR` | Same exact proof, observed below $3,000 | rejected |
| `LIQUIDITY_SOURCE_UNAVAILABLE` | Transport, timeout, connection, provider/server, authentication, or otherwise failed provider operation | rejected; unavailable channel |
| `LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE` | Source Governor/provider rate limit or stale result | rejected; unavailable for current proof |
| `LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL` | Malformed, parse-invalid, missing-critical, or PARTIAL response | rejected; no current proof |
| `LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH` | No exact pair, ambiguity, wrong mint, wrong pool, wrong chain, or exact identity mismatch in a completed response | rejected; provider is not called unavailable solely for this |
| `LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN` | A prior exact below-floor observation is still in categorical cooldown; no current call | rejected; historical only |
| `LIQUIDITY_IDENTITY_UNCONFIRMED` | Graduation/market identity gate failed before liquidity I/O | rejected; no current call |

Detailed source failure types remain visible and are not collapsed into the
category. The existing `LIQUIDITY_PROVEN`,
`LIQUIDITY_BELOW_SELECTION_FLOOR`, and `LIQUIDITY_UNPROVEN` status contract is
preserved.

## Aggregation and shortage precedence

The eligible-supply owner aggregates distinct liquidity failure IDs, categorical
outcome counts, and unavailable channels from candidate envelopes. It does not
infer failures from a null liquidity value.

When capacity is unmet, classification precedence is:

1. liquidity transport/provider unavailability -> existing
   `SOURCE_AVAILABILITY_FAILURE`;
2. rate-limited/stale current evidence -> existing `STALE_EVIDENCE_SHORTAGE`;
3. malformed/partial responses -> existing `SOURCE_VISIBILITY_SHORTAGE`, with
   candidate categories and lineages preserving the exact distinction;
4. duration ceiling -> existing `DURATION_EXHAUSTION`;
5. governed operation ceiling -> existing `BUDGET_EXHAUSTION`;
6. unexamined lawful work -> existing
   `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`;
7. all reachable exact candidates examined with healthy current evidence but
   insufficient eligibility -> existing `TRUE_MARKET_SUPPLY_SHORTAGE`.

Provider/source evidence classifications take precedence over a budget that was
consumed by those failed operations. Therefore 24 transport failures at a zero
remaining budget classify as `SOURCE_AVAILABILITY_FAILURE`, never market supply.
By contrast, healthy exact responses that consume the budget before all
inventory is examined remain `BUDGET_EXHAUSTION`.

## Terminal contract

No new terminal constant is required. Existing shortage classifications are
canonical, truthful pre-lifecycle causes for non-market blockers:

- `SOURCE_AVAILABILITY_FAILURE`;
- `STALE_EVIDENCE_SHORTAGE`;
- `SOURCE_VISIBILITY_SHORTAGE`;
- `BUDGET_EXHAUSTION`;
- `DURATION_EXHAUSTION`;
- `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`.

Only `TRUE_MARKET_SUPPLY_SHORTAGE` may map to the compatibility terminal
`BLOCKED_INSUFFICIENT_GRADUATED_POOL`. If no eligible-supply certificate exists,
the older compatibility behavior remains unchanged. First-terminal-cause
preservation remains authoritative.

The blocked-supply object and terminal artifact carry `shortage_classification`,
the full exhaustion certificate, candidate liquidity reason/source status/
category/lineage, provider-failure totals, and unavailable channels.

## Ownership and persistence contract

The operational owner supplies:

- `campaign_id = command.campaign_id`;
- `execution_id = selection_seed` (the canonical operational execution identity);
- `run_id = command.run_id`;
- `cycle_id = cycle_id`.

The exhaustion owner persists all four in existing columns and duplicates them
inside the canonical certificate JSON. Missing ownership is rejected when an
operational campaign command is the caller; lower-level fixture callers may
remain nullable for backward-compatible unit isolation.

Candidate lineage is durable in two existing locations: the canonical source
ledger remains authoritative for source rows, while the exhaustion certificate
JSON and terminal artifact preserve the action-local candidate join. No schema
migration is required.

## Floor and reserve state contract

`printer_graduated_market_floor_state` remains latest-attempt state. A failed or
unproven latest attempt may replace the former floor status/value, but the
candidate envelope records why and links it to the source ledger. The floor row
does not reuse an old value as current proof.

`printer_eligible_token_reserve` remains two-axis state: its liquidity fields are
the last successful exact evidence, while `eligibility_status` and
`exclusion_reason` express current eligibility. Failed revalidation changes only
current eligibility. Reports label the old fields as
`historical_reserve_evidence` and the new failed attempt as
`current_liquidity_evidence`; historical values never count toward current
capacity.

Historical authoritative rows are not rewritten or cleaned.

## Safety invariants

- fresh current-cycle exact mint+PumpSwap pool liquidity remains mandatory;
- Source Governor remains the only source execution/persistence owner;
- shared operation ledger and Central Scheduler ownership remain unchanged;
- no mint-wide/alternative-pair fallback and no historical-value admission;
- blocked admission starts zero lifecycle and zero Scheduler work;
- no retry, restart, resume, or successor is introduced;
- normal production remains 15m; selective 1h remains separately authorized;
- 4h/12h/24h and every retrieval/financial capability remain locked.

## Offline proof plan

Focused tests on fixtures and temporary migrated databases cover:

1. exact above-floor success;
2. exact below-floor success;
3. 24 identical transport failures and source-availability precedence;
4. rate limit;
5. malformed payload;
6. partial response;
7. no exact pair;
8. mint/pool mismatch;
9. mixed successes and failures;
10. governed-budget exhaustion;
11. true eligible-supply exhaustion;
12. request/response/failure lineage;
13. certificate campaign/execution/run/cycle ownership;
14. truthful blocked-supply and terminal payload;
15. historical reserve evidence preserved but not admitted;
16. zero lifecycle/Scheduler work on blocked outcomes;
17. zero retry/restart/successor;
18. 4h and downstream capability locks.

Nearest affected front-door, eligible-supply, campaign-owner, and terminal-
reporting regressions will run. No broad/full suite is required because the
repair does not change Source Governor, Central Scheduler, migrations, cadence,
or runtime ceilings.

## Stop conditions and rollback

Stop with BLOCKED if focused proof reveals Source Governor bypass, non-exact
liquidity admission, historical-value admission, ownership loss, false terminal
classification, Scheduler/lifecycle start, retry/successor creation, capability
unlock, authoritative DB mutation, or a required schema change not justified by
this design.

Rollback is one commit revert. No database rollback is required because no
migration is designed and authoritative rows are untouched.

## Functionality Risks / Setbacks / Efficiency Blockers

- Existing historical artifacts remain as originally recorded; this repair does
  not rewrite their false summary fields.
- Certificate JSON becomes larger because it carries bounded candidate lineage;
  the candidate set remains bounded by the existing operation/evaluation limits.
- A healthy response with no exact pair remains a market/identity observation,
  not a provider outage; operator interpretation still depends on the preserved
  candidate category counts.
- The repair reports repeated route failure truthfully but intentionally adds no
  circuit breaker, retry, fallback, or budget-policy optimization.
- A future normalized failure vocabulary change may require a separately audited
  mapping update; unknown FAILED outcomes remain fail-closed as source unavailable.

