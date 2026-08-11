# Printer V1 V2-9.8B Fourth Standard Four-Hour Manifest/Budget Root-Cause Audit

## Verdict

`V2_9_8B_FOURTH_STANDARD_FOUR_HOUR_MANIFEST_BUDGET_ROOT_CAUSE_AUDIT_PASS`

Classification:

- `COMMITTED_CODE_DEFECT__STANDARD_4H_ELIGIBILITY_MANIFEST_CURRENT_CLOSE_LOST_UPDATE`
- secondary directly related defect: `COMMITTED_CODE_DEFECT__STANDARD_4H_REPORTING_USES_ONE_TOKEN_BUDGET_SHAPE`

The fourth standard-four-hour authorization is consumed and must never be rerun, resumed, restarted, or reused. No fifth authorization or live standard-four-hour run is allowed from this audit.

## Baseline and lane

- Frozen launch/preparation branch: `agent/v2-9-8b-fresh-standard-4h-authorization-preparation`
- Exact launch HEAD: `8d67099bf314564fc9c3465bf99f33554d00062c`
- Fourth authorization: `V2_9_8B_STANDARD_4H_AUTH_20260811T181829Z`
- Factory run: `ebde54e8-010e-4335-8be0-f35ddafc11cd`
- Audit branch starts from the exact frozen launch HEAD and does not move or rewrite the preparation branch.
- Audit activity was static/read-only only. The authoritative DB remained byte-identical during the final scope inspection and tracked Git state remained clean.

The active V2-9.8B restrictions remain unchanged: Solana-only, Solana memecoin-only, paper-only, free/public sources only, Source Governor and Central Scheduler mandatory, no scoring/ranking/confidence/weighted logic, no retrieval, no paper decisions, no BUY/SELL/HOLD, no positions/trades/audits/PnL, and no 12h/24h activation.

## What happened

The fourth attempt progressed materially farther than the prior attempts:

1. Both selected tokens completed clean `WINDOW_15M` lifecycles.
2. Both completed clean `WINDOW_1H` closes.
3. The first 1h close reached the standard-four-hour barrier with `AWAITING_PEER_FIRST_HOUR_CLOSE`.
4. The second 1h close reached `STANDARD_FOUR_HOUR_BARRIER_RELEASED`.
5. Both tokens were evaluated `CONTINUE_TO_WINDOW_4H`.
6. The barrier planned 62 long-continuation Scheduler jobs: 31 per token.
7. The barrier's correct two-token TRACK_NORMAL subset budget was 140 governed requests and 114 Scheduler rows.
8. Before any 4h source request occurred, the first `LONG_CONTINUATION_SNAPSHOT` safe-stopped with:
   - scope `STANDARD_FOUR_HOUR_SUBSET`
   - detail `partial standard four-hour eligibility manifest`
9. The remaining long-window work was cancelled and cleanup completed with zero active owned work.

This was not real source-budget exhaustion. At the stop boundary there were 58 run-local governed requests. The final read-only report showed source requests still within the reported ceiling and zero 4h source requests had occurred.

## Root cause 1 - current-close eligibility manifest lost update

The standard-four-hour handoff persists a durable `standard_four_hour_eligibility` manifest into each successful first-hour close row.

The observed durable state proves an asymmetric result:

- slot 1 retained a valid `STANDARD_4H_ELIGIBILITY_V1` manifest;
- slot 2 did not retain its manifest;
- nevertheless the second close's barrier result proves that both slots had been evaluated eligible and 62 4h jobs were planned.

The committed call path explains the asymmetry:

1. `run_standard_four_hour_campaign_barrier(...)` calls the standard handoff owner.
2. The handoff persists both eligibility manifests into the two first-hour close `result_json` payloads.
3. Control returns to the current second `CONTINUATION_CLOSE` execution with an older in-memory `result` mapping that predates the manifest insertion.
4. The runner then sets `result["standard_four_hour_barrier"] = barrier` and calls `_update_step(..., "SUCCEEDED", result)`.
5. `_update_step` replaces the current close row's complete `result_json` from that stale in-memory mapping.
6. The second slot's just-persisted eligibility manifest is therefore erased, while the already-finished first close retains its manifest.
7. The first 4h pre-step budget check calls `load_standard_four_hour_eligibility_manifests(...)`, sees exactly one of two required manifests, raises `partial standard four-hour eligibility manifest`, and correctly fail-closes as `STANDARD_FOUR_HOUR_SUBSET`.

The safe-stop is correct. The defect is the write ordering/merge contract that destroys the current close's durable manifest after barrier persistence.

## Root cause 2 - standard two-token reporting uses historical one-token budget shape

The final reporting path has a second directly related standard-four-hour truth defect.

Observed report values included:

- 4h Scheduler rows: 62, reported against a one-token phase ceiling of 34;
- cumulative Scheduler rows: 106, reported against a one-token cumulative ceiling of 57;
- both were therefore reported `EXCEEDED`.

But the standard barrier had already derived the exact two-token TRACK_NORMAL subset budget:

- governed request ceiling: 140;
- Scheduler ceiling: 114;
- 62 4h rows and 106 cumulative rows are inside that standard subset Scheduler envelope.

Static inspection shows the execution-time long-step guard correctly uses `_standard_four_hour_cumulative_budget_for_run(...)` when `standard_four_hour_campaign` is true, but `_run_budgets(...)` still uses the historical `_cumulative_lifecycle_budget_for_run(...)` plus a single-lane `runtime_budget(...)` shape for reporting.

This reporting mismatch did not cause the observed first 4h step stop; the missing second eligibility manifest did. However, it must be repaired in the same bounded section before another authorization because otherwise a successful standard two-token 4h execution can still be reported against the wrong one-token Scheduler ceilings.

## Rejected hypotheses

The audit rejects these as the fourth-attempt root cause:

- holder-backup exhaustion;
- 48-request first-hour per-token exhaustion;
- governed source-request exhaustion;
- the generic campaign `source_calls=45` value as the proven first-4h stop owner;
- provider failure;
- Scheduler failure to create 4h work.

The exact stop owner is the standard-four-hour subset manifest reconstruction path.

## Minimum repair boundary

A repair design may address only the directly proven standard-four-hour durability/reporting boundary:

1. Preserve both immutable standard-four-hour eligibility manifests after the peer barrier releases.
2. Eliminate the stale full-payload overwrite of the current close, either by merging/reloading authoritative row state before the final close update or by giving one canonical owner responsibility for the post-barrier close payload.
3. Keep manifest identity/conflict checks fail-closed.
4. Make standard-four-hour reporting derive its request and Scheduler ceilings from the same standard subset budget owner used by execution.
5. Preserve per-token/phase semantics without converting one token's budget into a hidden aggregate bypass.
6. Do not raise any approved public worst-case ceiling, Source Governor ceiling, Scheduler authority, provider allowance, retry count, or endpoint-rotation allowance.
7. Do not change cadence, eligibility decisions, memory-quality gates, source contracts, schema, migrations, authorization semantics, or downstream locks unless a later audit proves a separate need.

## Minimum sufficient proof before completion

Before any future live authorization, the repair must pass focused offline proof covering at least:

- two successful 1h closes where the first waits for its peer and the second releases the barrier;
- both close rows retain exact immutable eligibility manifests after the current close's final update;
- `load_standard_four_hour_eligibility_manifests(...)` returns both manifests after the barrier transaction and after the caller's final close write;
- first 4h opening pre-step budget admission succeeds when the standard subset has capacity;
- a deliberately partial manifest still fails closed with `STANDARD_FOUR_HOUR_SUBSET`;
- conflicting/mismatched manifest identity still fails closed;
- standard two-token reporting uses the same derived subset request/Scheduler ceilings as execution for both-eligible and one-eligible cases;
- historical non-standard one-token/proof reporting remains unchanged;
- no source fetch, real runtime, authoritative DB mutation, authorization creation, retrieval, decisions, positions, trades, audits, or PnL during the offline proof.

Risk-based verification applies: focused changed tests plus the nearest standard-four-hour budget/barrier regressions are sufficient for implementation; broad/full suites are reserved for major closeout or pre-live-proof validation.

## Money-usefulness contribution

This repair prevents a valid two-token first-hour learning cycle from wasting its approved 4h opportunity because durable eligibility state is accidentally erased. It also prevents false budget-exceeded reporting from misclassifying legitimate bounded standard-four-hour work. That improves the chance that scarce one-use operational attempts produce trustworthy longer-horizon memory instead of deterministic wiring failures.

It does not claim profitability and does not unlock any trading capability.

## What this audit improves

- identifies the exact fourth-attempt stop owner;
- separates real budget exhaustion from manifest reconstruction failure;
- proves the safe-stop itself behaved correctly;
- identifies the lost-update write ordering that made the manifest partial;
- identifies the directly related one-token-vs-standard-two-token reporting mismatch before another live attempt.

## What remains locked

This audit unlocks no runtime or downstream capability. In particular it does not authorize:

- a fifth standard-four-hour authorization or run;
- 12h/24h collection;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet, signing, private keys, or real funds.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Required control |
|---|---|---|
| Fix only the loader and tolerate partial state | Hides the lost update instead of repairing ownership | Preserve both manifests before any 4h step; partial state must still fail closed |
| Reorder writes without conflict protection | Eligibility can be silently replaced | Retain exact manifest identity/conflict validation |
| Fix manifest but leave one-token reporting | Next run may finish work yet report false budget exhaustion | Standard reporting must use the same subset budget owner as execution |
| Inflate ceilings to make reports pass | Weakens bounded safety | Derive existing approved ceilings; do not increase them |
| Broad refactor of lifecycle runner | Adds regression risk | Narrow repair around post-barrier close persistence and standard budget reporting only |
| Consume another authorization before offline proof/closeout | Wastes a one-use live attempt | No authorization until implementation proof, closeout, and rereadiness pass |

## Next permitted lane

`V2-9.8B - Fourth standard-four-hour manifest/budget repair design`

Design only. No production code, runtime, source fetching, DB mutation, authorization creation, or live proof in the design lane.
