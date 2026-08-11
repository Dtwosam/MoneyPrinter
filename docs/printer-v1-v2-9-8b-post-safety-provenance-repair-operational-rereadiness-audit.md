# Printer V1 V2-9.8B — Post-Safety-Provenance-Repair Operational Rereadiness Audit

## Verdict

`V2_9_8B_POST_SAFETY_PROVENANCE_REPAIR_OPERATIONAL_REREADINESS_BLOCKED_PUBLIC_BUDGET_AUTHORITY_DRIFT`

Fresh operational rereadiness is **BLOCKED** before host execution because static exact-HEAD inspection found contradictory live standard-four-hour request-capacity authority.

This is a read-only readiness finding. It does not invalidate the completed first-hour safety/provenance implementation closeout at `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`, and it does not authorize a repair, a fresh authorization, provider contact, Scheduler runtime, authoritative DB mutation, memory generation, or another standard-four-hour attempt.

## Baseline

- repository: `Dtwosam/MoneyPrinter`
- repair branch: `agent/v2-9-8b-second-standard-4h-safety-provenance-repair`
- repaired implementation HEAD: `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`
- repaired implementation verdict: `V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`
- frozen consumed launch branch: `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`
- frozen consumed launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`
- both historical standard-four-hour authorizations remain permanently consumed and non-reusable.

## Rereadiness scope

This lane is audit/readiness only. Static inspection was performed first because a contradiction in public policy/authorization capacity is itself a sufficient fail-closed stop condition. Host-local process, DB, lease, staging, retained-evidence, and zero-I/O dependency rereadiness were therefore deliberately not run after the static blocker became conclusive.

No production source changed in this audit.

## Blocking finding

The completed safety/provenance repair added three fresh governed first-hour safety transports per token at `CONTINUATION_CLOSE`.

The repaired canonical lifecycle budget now truthfully derives:

| lanes | 4h eligible | requests | Scheduler |
|---|---|---:|---:|
| FAST + FAST | both | 236 | 210 |
| FAST + NORMAL | both | 188 | 162 |
| NORMAL + NORMAL | both | 140 | 114 |
| FAST + FAST | none | 98 | 82 |

For the worst-case standard FAST + FAST profile, this means `236 = 2 discovery + 2 * 117` governed requests.

However, live public and authorization owners still encode the pre-repair capacity:

### 1. Public operational command is stale

`src/printer_v1/operator_cli/operational_memory_factory_command.py` still defines:

```text
STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING = 230
STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN = 114
STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING = 210
```

Those values are live. They construct `STANDARD_FOUR_HOUR_POLICY`, are returned by `build_standard_four_hour_preflight()`, are passed by `run_standard_four_hour_campaign()`, and are persisted into the immutable campaign configuration under `inner_15m_ceilings`.

### 2. One-shot authorization wrapper is stale

`src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py` still defines:

```text
LIFECYCLE_REQUEST_OUTER_CEILING = 230
LIFECYCLE_SCHEDULER_OUTER_CEILING = 210
```

`fixture_authorization_document()` writes that `230` value into `campaign_policy.lifecycle_request_outer_ceiling`, and `validate_standard_four_hour_authorization_document()` requires the authorization document to equal that stale wrapper policy exactly.

Therefore a fresh authorization prepared from the current committed wrapper would bind a `230` request contract while the repaired lifecycle requires a worst-case `236` request contract.

### 3. Existing tests pin contradictory truths

`tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py` still asserts:

- public standard-four-hour policy request ceiling `230`;
- public standard-four-hour per-token request ceiling `114`;
- wrapper authorization request ceiling `230`.

At the same exact repaired HEAD, `tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py` and the focused safety/provenance repair proof assert the repaired lifecycle truth `236 / 188 / 140` with unchanged Scheduler ceilings.

The suite therefore contains two incompatible accepted budget contracts.

## Classification

Primary classification:

`PUBLIC_STANDARD_FOUR_HOUR_BUDGET_AUTHORITY_DRIFT_AFTER_FIRST_HOUR_SAFETY_REPAIR`

This is not a provider failure, market outcome, DB condition, consumed-authorization problem, or Scheduler-runtime incident. It is committed cross-owner capacity drift introduced because the first-hour safety repair updated the lifecycle/planner/factory budget surfaces without propagating the same capacity truth through the public operational command and one-shot authorization contract.

The current evidence does not require claiming that a future run would necessarily consume all 236 requests. The blocker exists earlier: preflight, durable campaign configuration, lifecycle planning, and one-use authorization must describe one coherent worst-case bounded contract before another authorization can safely be created.

## Why host rereadiness stopped here

The prior standard-four-hour rereadiness pattern checks host quiescence, authoritative DB identity/integrity, retained evidence, zero-I/O dependency/composition readiness, and policy ceilings.

The existing rereadiness helper is itself historical and cannot be reused unchanged: it expects an older branch/DB trust anchor, historical marker state, and `230` request capacity.

Running host-local checks before repairing the static policy contradiction would add cost without changing the verdict. Risk-based verification therefore stops at the minimum sufficient blocking evidence.

A fresh host rereadiness must be run again only after the budget-authority repair chain closes PASS.

## Money-usefulness contribution

This audit prevents Printer from spending another one-use standard-four-hour authorization under contradictory request-capacity contracts. Keeping public preflight, authorization, durable campaign configuration, and actual lifecycle planning aligned protects the next 15m→1h→4h memory attempt from avoidable budget rejection or misleading capacity evidence.

It does not claim profitability and unlocks no financial action.

## What this lane improves

- catches cross-owner budget drift before another authorization is consumed;
- preserves the repaired fresh-safety requirement instead of shrinking its budget implicitly;
- separates lifecycle capacity truth from stale public/wrapper metadata;
- prevents a false rereadiness PASS based only on host quiescence;
- identifies the exact live owners that require a scoped repair review.

## What remains locked

- host operational rereadiness PASS;
- provider/source fetching;
- Central Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- fresh authorization creation or review;
- reuse of either consumed authorization;
- rerun/resume/restart/successor of either consumed attempt;
- another standard-four-hour attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, PnL;
- live wallet, private keys, signing, real funds, live execution;
- paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test needed before this blocker can close

This rereadiness blocker is not repair authority. The next repair chain must first audit and design the narrow canonical propagation of the repaired request-capacity contract.

At minimum, later proof must establish one exact standard-four-hour capacity truth across:

1. `one_token_4h_runtime` lifecycle derivation;
2. `operational_standard_4h` outer policy;
3. `operational_memory_factory_command.STANDARD_FOUR_HOUR_POLICY` and preflight;
4. immutable standard campaign configuration;
5. `standard_four_hour_one_shot_wrapper` authorization generation/validation;
6. directly affected standard-four-hour policy/authorization tests.

Expected repaired worst-case capacity, if the audit/design confirms no different canonical derivation, is:

- standard request outer ceiling: `236`;
- standard per-token request ceiling: `117`;
- standard Scheduler outer ceiling: `210` unchanged.

Do not implement those numbers merely because this audit observes them; the next lane must first confirm the exact canonical ownership and propagation design.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Authorization contradiction:** another authorization created now would encode stale `230` capacity.
- **Public preflight contradiction:** current public preflight reports a lower ceiling than the repaired lifecycle planner.
- **Durable configuration contradiction:** standard campaign configuration currently persists the stale public policy values.
- **Test split-brain:** current tests separately bless both old and repaired budget truths, so the existing focused repair proof did not cover the complete public authorization surface.
- **Selective-1h adjacent drift:** the public command also retains historical selective-1h `92/45` values while factory-local repaired selective ceilings are `98/48`. This is adjacent evidence to audit for shared ownership/coupling, but it must not automatically widen the standard-four-hour repair into an unrelated capability change.
- **Host evidence still pending:** no fresh post-repair host/DB rereadiness PASS is claimed because static readiness already blocked.
- **Consumed-attempt protection:** both previous standard-four-hour authorizations remain historical evidence only and must never be reused.

## Next permitted lane

`SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_SCOPE_AUDIT`

That lane is audit-only.

It may inspect the exact capacity owners, wrapper/authorization contract, public preflight/configuration propagation, directly affected tests, and the adjacent selective-1h representation only to determine whether it shares the same canonical owner.

It may not implement a repair, run providers, run the Scheduler, mutate the authoritative DB, generate memory, create/review an authorization, or start another standard-four-hour attempt.

Preserve the sequence:

```text
repair-scope audit
-> design/specification
-> implementation if approved
-> bounded offline proof/test
-> closeout
-> fresh operational rereadiness
-> only later fresh one-use authorization preparation/review
-> only after independent authorization closeout may another bounded standard-four-hour attempt be considered
```
