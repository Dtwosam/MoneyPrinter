# Printer V1 V2-9.8B Selective-1h Liquidity Evidence Repair Closeout

## Verdict

`V2_9_8B_SELECTIVE_1H_LIQUIDITY_EVIDENCE_REPAIR_PASS`

PASS means the narrow categorical lineage/reporting defect is designed,
implemented, and proven offline. It authorizes only a fresh read-only
selective-1h operator-readiness review. It does not authorize another live
proof, source call, campaign execution, or capability unlock.

## Baseline

- Repository: `/Users/Dtwo1/Developer/MoneyPrinter`
- Branch: `master`
- Required and verified starting HEAD:
  `43511ca19413853fa9f7e7f3626eab72d69aa08a`
- Starting worktree: clean
- Authoritative DB: `data/printer_v1.sqlite3`
- Authoritative DB SHA-256 before:
  `6b63a30fca36bac52ce6af418a0cfcbe9b1711b5671baeaef34add307460aa59`
- Authoritative DB SHA-256 after:
  `6b63a30fca36bac52ce6af418a0cfcbe9b1711b5671baeaef34add307460aa59`
- Authoritative DB changed: no
- Operational proof/source/campaign/Scheduler/lifecycle runtime executed: no

## Files changed

- `docs/printer-v1-v2-9-8b-selective-1h-liquidity-evidence-repair-design.md`
- `src/printer_v1/discovery/graduated_liquidity_front_door.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py`
- `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py`
- `docs/printer-v1-v2-9-8b-selective-1h-liquidity-evidence-repair-closeout.md`

## Root cause

The primary classification was `COMMITTED_CODE_DEFECT`.

The exact-pool front door created durable governed request and failure rows, but
reduced the stage result to counts. Candidate conversion then discarded the
liquidity reason and source status, eligible-supply aggregation counted only a
PumpPortal discovery failure as a provider failure, and the operational caller
did not pass campaign/execution/run/cycle ownership to exhaustion persistence.
The terminal path consequently converted 24 DexScreener transport failures into
`provider_failures=0`, no unavailable channel, budget exhaustion, and finally
`BLOCKED_INSUFFICIENT_GRADUATED_POOL`.

Fail-closed admission itself was correct and remains unchanged.

## Implemented categorical contract

Candidate current-attempt evidence now carries:

- exact mint and PumpSwap pool;
- source request ID;
- source response or failure ID;
- failure type;
- stable reason and detailed provider reason;
- source status;
- current liquidity value when exact and valid;
- one categorical outcome.

The categorical outcomes are:

- `LIQUIDITY_EXACT_ABOVE_FLOOR`;
- `LIQUIDITY_EXACT_BELOW_FLOOR`;
- `LIQUIDITY_SOURCE_UNAVAILABLE`;
- `LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE`;
- `LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL`;
- `LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH`;
- `LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN`;
- `LIQUIDITY_IDENTITY_UNCONFIRMED`.

The existing three-state admission contract remains unchanged:
`LIQUIDITY_PROVEN`, `LIQUIDITY_BELOW_SELECTION_FLOOR`, or
`LIQUIDITY_UNPROVEN`.

Shortage precedence now prevents a budget consumed by failed provider
operations from hiding their cause:

1. transport/provider unavailability -> `SOURCE_AVAILABILITY_FAILURE`;
2. rate limit/stale -> `STALE_EVIDENCE_SHORTAGE`;
3. malformed/partial -> `SOURCE_VISIBILITY_SHORTAGE` with exact candidate
   categories retained;
4. duration -> `DURATION_EXHAUSTION`;
5. healthy governed-budget exhaustion -> `BUDGET_EXHAUSTION`;
6. lawful unexplored work -> `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`;
7. fully examined healthy supply -> `TRUE_MARKET_SUPPLY_SHORTAGE`.

Only true market-supply shortage maps to the compatibility terminal
`BLOCKED_INSUFFICIENT_GRADUATED_POOL`. Other shortage classifications remain the
first terminal cause.

## Persistence and ownership behavior

No migration was required.

- The existing Source Governor ledger remains authoritative for durable
  request-to-response/failure linkage.
- The bounded exhaustion certificate JSON now preserves candidate-level
  liquidity lineage, category counts, liquidity-stage provider-failure count,
  and unavailable channels.
- Existing exhaustion columns are now bound by the operational owner to exact
  campaign, execution, run, and cycle IDs.
- Blocked-supply reporting and the terminal artifact preserve the certificate,
  shortage classification, candidate reason/source status/category, and source
  IDs.
- `printer_graduated_market_floor_state` remains latest-attempt state. It never
  treats an old value as current proof.
- `printer_eligible_token_reserve` continues to preserve the last successful
  exact value as historical evidence while current eligibility becomes
  `REMOVED`. Reports explicitly separate `historical_reserve_evidence` from
  `current_liquidity_evidence` and mark the historical value not admitted.
- Historical authoritative rows were not rewritten or cleaned.

## What was built

- Full candidate liquidity lineage through front door, supply conversion,
  reserve/exhaustion diagnostics, blocked-supply reporting, and terminal output.
- Liquidity-stage provider-failure and unavailable-channel aggregation.
- Truthful distinction among transport/provider, rate/stale, malformed/partial,
  exact-pair identity, below-floor, budget, and true-supply outcomes.
- Operational exhaustion ownership binding.
- Truthful pre-lifecycle terminal selection with zero lifecycle/Scheduler start.
- Explicit current-attempt versus historical-reserve report semantics.
- A dedicated fixture/temp-DB offline proof matrix.

## What was not touched

- No Source Governor ownership, provider fallback, retry, rate budget, proof
  ceiling, or transport behavior changed.
- No Central Scheduler, cadence, lifecycle, memory close, retrieval, or paper
  system changed.
- No authoritative database or historical authoritative row changed.
- No migration was created or applied.
- No live source, discovery, campaign, Scheduler, lifecycle, or operational proof
  ran.
- No 4h/12h/24h activation or financial capability was added.

## Tests and checks

Final focused proof command:

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py \
  tests/test_v2_9_7e_43_graduated_liquidity_front_door.py \
  tests/test_v2_9_8b_21_eligible_token_supply_architecture.py \
  tests/test_v2_9_8b_4_blocked_supply_source_reporting.py \
  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py \
  tests/test_v2_9_8b_19_production_readiness_consolidation.py \
  tests/test_v2_9_8b_selective_1h_tracking_handoff_contract.py \
  tests/test_v2_9_8b_operational_selective_1h.py -x
```

Result: `146 passed, 5 subtests passed in 56.25s`.

Additional checks:

- dedicated repair proof: `11 passed in 2.53s`;
- original front-door + eligible-supply regressions: `50 passed in 12.15s`;
- campaign/report/selective-1h regressions:
  `84 passed, 5 subtests passed in 28.93s`;
- `python -m compileall`: PASS;
- changed-module `py_compile`: PASS;
- `git diff --check`: PASS;
- authoritative DB before/after SHA-256 equality: PASS.

No unrelated baseline failure was encountered. A broad/full suite was not run;
the repair did not change Source Governor, Central Scheduler, cadence, migration,
or runtime ceilings.

## Minimum offline proof coverage

PASS coverage includes:

1. exact success above floor;
2. exact success below floor;
3. 24 identical transport failures;
4. rate limiting;
5. malformed payload;
6. partial response;
7. no exact pair;
8. mint and pool mismatch;
9. mixed successful and failed candidates;
10. governed-budget exhaustion;
11. true eligible-supply exhaustion;
12. candidate request/response/failure lineage;
13. exhaustion campaign/execution/run/cycle ownership;
14. truthful blocked-supply and terminal artifact;
15. historical reserve evidence preserved but not admitted;
16. zero lifecycle and Scheduler work on blocked outcomes;
17. no retry, restart, or successor;
18. WINDOW_4H and downstream capabilities remain locked.

The 24-failure reproduction specifically proves:

- 24 exact-pool request rows;
- 24 linked `dexscreener_transport_failure` rows;
- `provider_failures=24`;
- `liquidity_stage_provider_failures=24`;
- `channels_unavailable=["dexscreener_exact_pool_market"]`;
- 24 mint/pool/request/failure lineage envelopes;
- shortage and terminal cause `SOURCE_AVAILABILITY_FAILURE`, even with no
  remaining governed operation budget.

## Money-usefulness contribution

Printer still refuses unknown current liquidity, protecting memory from fake
entry/exit realism. The repair adds truthful causal evidence: an operator can now
distinguish infrastructure reachability from actual below-floor or exhausted
eligible supply. This prevents source outages from being interpreted as market
facts and makes future paper-only memory quality and exit-realism auditing more
trustworthy. It does not claim or create profit.

## What the repair improves

- Action-local forensic joins are no longer required to identify each candidate's
  exact source request and result.
- Provider failures and unavailable channels agree with the durable source
  ledger.
- Terminal cause describes the actual blocker.
- Historical reserve evidence remains useful for audit without leaking into
  current eligibility.
- Operator reports preserve the distinction across replayable terminal output.

## What remains locked

- another selective-1h live proof or any live source call;
- discovery, campaign, Scheduler, or lifecycle runtime without a later explicit
  authorization;
- retries, fallback, restarts, resumes, successors, or changed proof ceilings;
- 4h, 12h, and 24h operation;
- memory generation from this repair;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper
  audits, and PnL;
- wallets, private keys, signing, transactions, real funds, and live trading;
- paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

## Proof required before completion

The repair's completion proof was the focused offline fixture/temp-DB matrix and
nearest regressions listed above; it passed. No live proof is required or
authorized for this repair. Before any later operational action, a separate
fresh read-only selective-1h operator-readiness review must reconcile this
contract against the canonical command, current repository/DB state, capability
locks, and exact operator authorization.

## Rollback

Revert the single repair commit after it is created. No schema or database
rollback is required. Do not edit or clean historical authoritative rows.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical artifacts retain their original false summary fields; this repair
  deliberately does not rewrite authoritative history.
- Certificate/report JSON is larger because bounded candidate lineage is now
  retained.
- Unknown future FAILED failure types conservatively classify as source
  unavailable until separately audited; admission remains fail closed.
- Healthy completed responses with no exact pair are not provider outages. Their
  exact absence/mismatch category must be read alongside the aggregate shortage.
- Repeated route failures can still consume the governed budget. This lane fixes
  truthfulness only and adds no retry, fallback, circuit breaker, or budget-policy
  optimization.
- The next readiness review must confirm every operational caller continues to
  use the canonical ownership binding; ad hoc or legacy callers are not
  authorized by this closeout.

## Exact next permitted lane

Fresh read-only selective-1h operator-readiness review.

That review may inspect code, configuration, capability locks, reports, and the
authoritative database read-only. It may not run another live proof.

