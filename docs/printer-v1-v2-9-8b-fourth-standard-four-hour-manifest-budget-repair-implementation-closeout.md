# Printer V1 V2-9.8B Fourth Standard Four-Hour Manifest/Budget Repair Implementation Closeout

## Verdict

`V2_9_8B_FOURTH_STANDARD_FOUR_HOUR_MANIFEST_BUDGET_REPAIR_IMPLEMENTATION_PASS`

Implementation commit:

`ad6c75b54cf65a850842eb9fccbc834503aaaf52`

Design baseline:

`f2fab0468df1e8297e0d3e423777e5f9eafb6982`

Audit baseline:

`3920a193cb73af2a5fd210364d48b8eb9908c91a`

The fourth authorization `V2_9_8B_STANDARD_4H_AUTH_20260811T181829Z` remains permanently consumed. This closeout does not authorize a retry, rerun, resume, restart, successor authorization, source fetch, Scheduler/runtime execution, or authoritative DB mutation.

## Implemented repair

The implementation fixes the two proven fourth-attempt defects without widening operational authority:

1. `COMMITTED_CODE_DEFECT__STANDARD_4H_ELIGIBILITY_MANIFEST_CURRENT_CLOSE_LOST_UPDATE`
   - the post-barrier caller now re-reads the exact successful `CONTINUATION_CLOSE` row and merges only `standard_four_hour_barrier` into the authoritative persisted payload;
   - the standard handoff remains the sole writer of `standard_four_hour_eligibility`;
   - equal barrier replay is idempotent and conflicting replay fails closed.

2. `COMMITTED_CODE_DEFECT__STANDARD_4H_REPORTING_USES_ONE_TOKEN_BUDGET_SHAPE`
   - standard execution and reporting now share the exact durable standard subset budget owner;
   - canonical standard budget projection exposes aggregate eligible `WINDOW_4H` request, Scheduler, and holder-fallback phase ceilings;
   - partial/invalid standard manifests make reporting unavailable with the exact reason rather than silently substituting a one-token ceiling;
   - exact token-local usage remains visible without inventing a scalar per-token ceiling from an aggregate subset budget.

The long-step execution admission path also uses the aggregate eligible standard `WINDOW_4H` request-phase ceiling, so execution and reporting no longer disagree about the same standard subset.

## Scope

Production files changed:

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`

One historical regression fixture was corrected:

- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_factory_barrier.py`

The fixture had pre-existing request-ceiling expectations six requests below the already-committed measured-transport contract. The difference was the established two-token first-hour safety reserve: `2 * FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT(3)`. Only those four stale request-ceiling assertions were changed; Scheduler expectations were already current.

No schema migration, provider change, cadence change, source-policy change, Scheduler-ownership change, retry increase, endpoint rotation, authorization change, or financial capability was introduced.

## TDD and focused proof

RED baseline commit:

`98ec2db71bb5500820bed7609c9878b383fa53fc`

The focused RED test produced 10 expected failures covering the absent authoritative barrier merge and absent standard aggregate reporting projection.

Final focused GREEN verification after implementation and stale-fixture correction:

- compile: PASS;
- focused repair plus nearest standard-four-hour regressions: `78 passed, 11 subtests passed`;
- canonical current budget contract: PASS;
- mixed `TRACK_FAST` / `TRACK_NORMAL` subset request/Scheduler ceilings:
  - both eligible: `188 / 162`;
  - one eligible: `149 / 128`;
  - none eligible: `80 / 64`;
- two `TRACK_NORMAL` canonical standard subset remains `140 / 114` cumulative and `78 / 68` aggregate 4h phase;
- `git diff --check`: PASS;
- authoritative DB SHA-256 before and after offline proof remained exactly:
  `6efd019969b0b457a650b4e1948bf8a06f2565f920dcc3dbe3849fc5f3580e7a`.

No real source fetch or operational run was used for implementation proof. Risk-based verification remained focused on the changed standard-four-hour contracts; no broad suite was required for this narrow repair.

## Money-usefulness contribution

The repair prevents a valid two-token 15m -> 1h learning path from losing one token's durable 4h eligibility state at the barrier boundary. It also prevents standard two-token bounded work from being falsely reported against a one-token budget shape. This improves reliability of longer-horizon paper-only memory growth; it does not claim profitability or authorize trading.

## What this lane improves

- both durable eligibility manifests can survive the standard 1h -> 4h barrier release;
- the first 4h step can reconstruct the intended exact standard subset instead of seeing a caller-created partial manifest;
- standard execution admission and reporting share canonical subset phase/cumulative budget authority;
- partial manifests remain fail-closed;
- approved ceilings are preserved rather than inflated.

## What this lane still does not unlock

- no fifth standard-four-hour authorization or run;
- no source fetching or Scheduler/runtime execution for rereadiness;
- no `WINDOW_12H` or `WINDOW_24H` activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trade events, paper trade audits, or PnL;
- no wallet, signing, private keys, real funds, or live execution.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current control |
|---|---|
| Stale caller result erases barrier-owned manifest | authoritative post-barrier DB re-read and narrow merge |
| Partial manifest is accidentally tolerated | strict two-slot manifest loader remains fail-closed |
| Execution/reporting budget drift | same standard subset budget owner feeds both paths |
| Aggregate standard usage mislabeled as one-token usage | aggregate subset ceilings plus separate token-local actual counts |
| Historical fixture drift hides current transport reserve | corrected only the four stale request-ceiling assertions and preserved canonical measured-transport owner |
| Another one-use run is consumed before readiness is re-established | no authorization is permitted by this closeout; post-repair rereadiness must close first |

## Next permitted lane

`V2-9.8B - Post-fourth-repair standard-four-hour rereadiness review`

That lane is read-only/readiness-only. It must verify exact committed implementation provenance, clean tracked state, authoritative DB identity/schema/active-state truth, locked downstream capabilities, standard-four-hour capacity and subset contracts, source/runtime zero-I/O readiness, and absence of any reusable authorization. It may not create a new authorization or run standard-four-hour collection.
