# Printer V1 V2-9.8B — Second Standard Four-Hour Public Budget Authority Repair-Scope Audit

## Verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_SCOPE_AUDIT_PASS`

The post-safety-repair rereadiness blocker is confirmed as a narrow committed cross-owner capacity-propagation defect.

The repair must restore one derived standard-four-hour request-capacity contract across lifecycle planning, public preflight/configuration, and one-shot authorization. It must not weaken the new fresh first-hour safety requirement, raise Scheduler capacity, create another budget system, or authorize runtime.

This audit authorizes design/specification only. It does not authorize implementation, provider/source fetching, Scheduler runtime, authoritative DB mutation, memory generation, authorization creation/review, or another standard-four-hour attempt.

## Baseline

- parent rereadiness branch: `agent/v2-9-8b-post-safety-repair-operational-rereadiness-audit`
- parent rereadiness anchor HEAD: `1ba60632c2dd8d11a15544a77dcf582db0550541`
- rereadiness blocker closeout: `f153a6bc24efb3b708e6fb86c1e262f258613b67`
- repaired safety/provenance implementation: `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`
- frozen consumed launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`

Both previous standard-four-hour authorizations remain permanently consumed and non-reusable.

## Audit question

Determine the narrow canonical ownership and propagation rule for the repaired standard-four-hour request budget after fresh first-hour safety added three governed transports per token.

Specifically:

1. Which code owns the arithmetic?
2. Which surfaces are only public/authorization projections?
3. Which exact stale surfaces block rereadiness?
4. What must remain unchanged?
5. Is adjacent selective-1h drift part of this repair?

## 1. Canonical arithmetic owner

`src/printer_v1/operator_cli/one_token_4h_runtime.py` already owns the policy-derived standard campaign lifecycle arithmetic through:

`standard_campaign_lifecycle_budget(tracking_lanes, continuing_mask)`.

It derives request components from the committed policies rather than accepting a caller-supplied total:

- shared discovery allowance;
- per-token `WINDOW_15M` minimum snapshots;
- per-token 15m context allowance;
- per-token `WINDOW_1H` minimum snapshots;
- per-token `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT`;
- per-eligible-token 4h phase request ceiling.

It separately derives Scheduler components.

This is the correct computational owner because the original standard-four-hour design requires campaign ceilings to be calculated from actual cadence/runtime policies rather than copied historical magic constants.

Current worst-case FAST + FAST / both eligible truth is:

```text
request = 236
Scheduler = 210
```

The corresponding per-token non-shared request contribution is:

```text
(236 - shared discovery 2) / 2 = 117
```

The new `117` consists of the previous `114` per-token contribution plus the approved three fresh first-hour safety transports.

## 2. Barrier/public policy projection

`src/printer_v1/operator_cli/operational_standard_4h.py` is the standard 1h→4h eligibility/barrier policy surface.

It now exposes:

- `LIFECYCLE_REQUEST_OUTER_CEILING = 236`;
- `LIFECYCLE_SCHEDULER_OUTER_CEILING = 210`.

That value is aligned today, but it is a projection of the standard lifecycle arithmetic, not a reason to create a second independent calculation owner.

The design lane must decide the smallest safe mechanism for this public policy surface to derive or assert exact equality with the canonical computation.

## 3. Public operational command projection is stale and live

`src/printer_v1/operator_cli/operational_memory_factory_command.py` still defines:

```text
STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING = 230
STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN = 114
STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING = 210
```

These are not dead compatibility constants.

They construct `STANDARD_FOUR_HOUR_POLICY`, which is used by:

- `build_standard_four_hour_preflight()`;
- `run_standard_four_hour_campaign()`;
- `_run_operational_campaign()`;
- `_create_campaign_command()`.

The stale values are projected into public preflight and persisted in the immutable campaign configuration under `inner_15m_ceilings`.

Therefore this file is a required repair surface.

The command should not own a separately maintained standard-four-hour arithmetic table. Its standard policy must project the canonical derived capacity.

## 4. One-shot authorization projection is stale and live

`src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py` still defines:

```text
LIFECYCLE_REQUEST_OUTER_CEILING = 230
LIFECYCLE_SCHEDULER_OUTER_CEILING = 210
```

`fixture_authorization_document()` writes those values into the authorization's `campaign_policy`.

`validate_standard_four_hour_authorization_document()` then requires exact equality with the wrapper's own stale expected campaign policy.

Thus a new authorization prepared from current code would formally bind `230`, contradicting the repaired standard lifecycle's `236` worst-case bound.

This file is a required repair surface.

The wrapper remains the authorization generation/validation owner, but it must consume/project the canonical standard policy rather than independently own stale numeric capacity.

## 5. Directly affected tests

`tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py` currently pins the stale public/authorization values:

- command request ceiling `230`;
- command per-token request ceiling `114`;
- wrapper authorization request ceiling `230`.

At the same repaired code state, `tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py` and `tests/test_v2_9_8b_first_hour_safety_provenance_repair.py` pin the repaired lifecycle value `236`.

The repair proof therefore missed a cross-owner equality requirement.

The directly affected test repair must verify equality across the canonical arithmetic, public command policy/preflight, barrier policy contract, and wrapper authorization document.

A stale `230` authorization document must fail closed after the repair.

## 6. Expected standard capacity if design confirms this audit

The audit-derived expected standard maximum is:

- request outer ceiling: `236`;
- per-token non-shared request contribution: `117`;
- Scheduler outer ceiling: `210` unchanged;
- automatic retries: `0` unchanged;
- endpoint rotation: unchanged/disabled;
- locked later windows: `WINDOW_12H`, `WINDOW_24H` unchanged.

No additional source operation is approved beyond the already-implemented fresh first-hour safety contract.

The purpose is truthful accounting/authorization, not capacity expansion for new behavior.

## 7. Adjacent selective-1h drift

The public command retains historical selective-1h values `92` total / `45` per token while the repaired factory-local selective first-hour capacity is now `98` / `48` after the same three-per-token safety reserve was added.

This is real adjacent representation drift, but the active operational target remains standard-four-hour and selective-1h is not the current main operation.

Therefore:

- record the drift as a follow-up risk;
- allow the design to inspect whether a shared derivation helper can remove duplication without changing selective-1h behavior;
- do **not** automatically widen this repair into selective-1h activation, proof reruns, runtime changes, or an unrelated policy rewrite.

If fixing the standard owner safely requires a shared helper that also makes the selective projection truthful with zero semantic change, the design must explicitly justify and bound that scope before implementation.

Otherwise selective drift remains a separately tracked blocker/cleanup item.

## 8. Canonical repair boundary

Required repair ownership chain:

```text
policy-derived standard lifecycle arithmetic
  one_token_4h_runtime.standard_campaign_lifecycle_budget
        |
        +-> standard barrier/public policy projection
        |     operational_standard_4h
        |
        +-> public command/preflight/configuration projection
        |     operational_memory_factory_command
        |
        +-> one-shot authorization generation/validation projection
              standard_four_hour_one_shot_wrapper
```

No projection may independently redefine the standard request total.

The design must avoid circular imports and import-time side effects. All derivation must remain source-free, DB-free, Scheduler-free, deterministic, and safe to use during authorization preparation.

## What must not change

- fresh first-hour safety collection remains three worst-case governed transports per token;
- `CONTINUATION_CLOSE` reservation remains exactly four total: one close observation + three first-hour safety transports;
- Scheduler ceiling remains `210` for FAST + FAST;
- B.2 exact safety authority consumer remains unchanged;
- no stale 15m safety fallback;
- no new Scheduler job;
- Source Governor ownership unchanged;
- Central Scheduler ownership unchanged;
- no behavior/outcome-based continuation gate;
- no scoring/ranking/confidence/weighted logic;
- no retries, restart, resume, or successor authority;
- `WINDOW_12H` / `WINDOW_24H` remain locked;
- `WINDOW_5M_MICRO_EVENT` remains support-only.

## Minimum sufficient later proof

After a design and implementation are separately approved, focused offline proof should establish:

1. canonical FAST+FAST both-eligible computation remains `236/210`;
2. command standard policy reports `236`, `117`, `210`;
3. `build_standard_four_hour_preflight()` projects those exact values with zero source/Scheduler/write work;
4. immutable campaign configuration construction uses the same standard values;
5. wrapper-generated authorization document binds `236/210`;
6. wrapper validation accepts exact repaired policy and rejects stale `230` policy;
7. barrier/public policy contract equals canonical standard outer capacity;
8. directly affected existing standard tests are updated only for the truthful repaired contract;
9. no runtime/provider/DB proof is needed for this budget-propagation repair before fresh operational rereadiness.

Do not run a broad regression suite merely for these numeric projections unless a focused failure indicates wider coupling.

## Money-usefulness contribution

A single derived standard-four-hour capacity contract prevents another bounded learning attempt from being authorized with less capacity than its mandatory safety work requires. This improves the reliability of memory growth without increasing market-risk appetite or unlocking financial actions.

## What this lane improves

- identifies the arithmetic owner versus projection owners;
- proves the public command and authorization wrapper are both required repair surfaces;
- prevents a superficial one-file `230 -> 236` patch from leaving split-brain policy behind;
- defines a narrow test gap that must be closed;
- keeps adjacent selective drift visible without automatically widening scope.

## What remains locked

This audit does not authorize:

- implementation;
- host operational rereadiness;
- provider/source fetching;
- Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- authorization creation/review;
- authorization reuse;
- another standard-four-hour attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL;
- wallet/private-key/signing/real-funds/live execution.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Duplication recurrence:** changing literals without establishing a canonical projection rule can recreate the same drift on the next cadence/context change.
- **Authorization import risk:** wrapper derivation must remain deterministic and side-effect free; importing a runtime-heavy owner carelessly could make authorization preparation brittle.
- **Per-token semantic ambiguity:** `117` is the non-shared contribution under the standard two-token worst-case contract, not an independent one-token campaign total; the design must name it accurately.
- **Selective adjacency:** a shared helper could accidentally widen historical selective-1h behavior if not bounded carefully.
- **Historical evidence:** old authorizations and docs legitimately contain `230`; they must remain historical and must not be rewritten as if they had been authorized under `236`.
- **No host PASS yet:** a fresh host/DB operational rereadiness still must occur after repair closeout.

## Next permitted lane

`SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_DESIGN`

Design/specification only.

It must select the minimal deterministic derivation/projection mechanism, exact files, exact invariants, focused tests, and rollback/stop conditions. It may not implement code or authorize/run Printer.
