# Printer V1 V2-9.8B — Second Standard Four-Hour Public Budget Authority Repair Design

## Verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_DESIGN_PASS`

Adopt one derived standard-four-hour capacity contract and make every public/authorization surface consume that contract.

The arithmetic remains policy-derived in `one_token_4h_runtime`; `operational_standard_4h` becomes the single public standard policy projection; `operational_memory_factory_command` and `standard_four_hour_one_shot_wrapper` consume that projection instead of maintaining independent numeric capacity.

This design authorizes only the narrow implementation described below plus focused offline proof. It authorizes no provider/source fetching, Scheduler runtime, authoritative DB mutation, memory generation, authorization creation/review, or standard-four-hour execution.

## Baseline

- repair-scope audit branch: `agent/v2-9-8b-public-budget-authority-repair-scope-audit`
- repair-scope audit commit: `146261d41cdd5ac9a13054bd3e8237d78d98db83`
- audit verdict: `V2_9_8B_SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_SCOPE_AUDIT_PASS`
- repaired safety/provenance implementation: `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`

## Design goal

Restore exact capacity agreement across:

```text
policy-derived lifecycle arithmetic
-> standard public policy contract
-> public command / preflight / immutable campaign configuration
-> one-shot authorization generation / validation
```

without adding a new budget engine or changing runtime behavior beyond truthful capacity projection.

## 1. Arithmetic owner remains unchanged

`src/printer_v1/operator_cli/one_token_4h_runtime.py`

Existing function:

`standard_campaign_lifecycle_budget(tracking_lanes, continuing_mask)`

remains the canonical arithmetic owner.

Do not duplicate its cadence/context/4h-phase summation elsewhere.

For the standard maximum, use the already-approved worst-case operational shape:

```text
tracking_lanes = (TRACK_FAST, TRACK_FAST)
continuing_mask = (True, True)
```

Current derived result:

- request ceiling: `236`;
- Scheduler ceiling: `210`;
- shared discovery requests: `2`;
- per-token non-shared request contribution: `(236 - 2) / 2 = 117`.

No change to `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3`.

## 2. Public standard contract owner

`src/printer_v1/operator_cli/operational_standard_4h.py`

This module remains the canonical **public standard-four-hour policy contract**, but its numeric capacity must be derived from the arithmetic owner instead of independently maintained.

Implement one small source-free helper, for example:

`standard_four_hour_capacity_contract()`

It should:

1. call `standard_campaign_lifecycle_budget(("TRACK_FAST", "TRACK_FAST"), (True, True))`;
2. read the shared `discovery` component from the returned request components;
3. require exactly two standard token slots;
4. require the non-shared request remainder to divide exactly across those two worst-case FAST slots;
5. return immutable/plain deterministic values for:
   - `lifecycle_request_outer_ceiling`;
   - `lifecycle_requests_per_token`;
   - `lifecycle_scheduler_outer_ceiling`;
   - optionally the derivation inputs/components needed for focused proof.

Then derive the existing module-level public constants from that helper:

- `LIFECYCLE_REQUEST_OUTER_CEILING = 236` derived, not literal arithmetic authority;
- add/derive a clearly named per-token standard request value = `117` if required by downstream public command projection;
- `LIFECYCLE_SCHEDULER_OUTER_CEILING = 210` derived and unchanged in value.

`standard_four_hour_policy_contract()` should expose the same derived capacity values so callers can project one public contract.

No source, DB, filesystem, Scheduler, or environment access is allowed in capacity derivation.

## 3. Public command projection

`src/printer_v1/operator_cli/operational_memory_factory_command.py`

Remove independent standard-four-hour numeric ownership.

The existing public names may remain for compatibility, but their values must come from the standard public policy contract rather than literals:

- `STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING` -> derived `236`;
- `STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN` -> derived `117`;
- `STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING` -> derived `210`.

`STANDARD_FOUR_HOUR_POLICY` then continues to feed:

- `build_standard_four_hour_preflight()`;
- `_run_operational_campaign()`;
- `_create_campaign_command()`;
- immutable `inner_15m_ceilings` configuration.

No change to ordinary 15m or historical selective-1h policy in this implementation unless strictly required for import compatibility. The adjacent selective `92/45` versus `98/48` drift remains out of scope for behavior changes.

## 4. One-shot authorization projection

`src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py`

Remove independent request/Scheduler outer numeric ownership.

The wrapper should import/consume the same deterministic standard public policy contract and project:

- request outer ceiling `236`;
- Scheduler outer ceiling `210`;
- all existing duration/window/eligibility/lock fields unchanged.

`fixture_authorization_document()` must therefore produce `campaign_policy.lifecycle_request_outer_ceiling = 236`.

`validate_standard_four_hour_authorization_document()` must require the repaired derived campaign policy exactly.

An authorization document containing historical `230` under a new repaired HEAD must fail closed with campaign-policy mismatch.

Historical already-consumed authorization files remain untouched evidence and are not retroactively rewritten.

## 5. Import/coupling rule

Required dependency direction:

```text
one_token_4h_runtime
        ↓
operational_standard_4h
        ↓                 ↓
public command       one-shot wrapper
```

Do not reverse this dependency.

Specifically:

- `one_token_4h_runtime` must not import the public command or wrapper;
- `operational_standard_4h` must not import the public command or wrapper;
- command and wrapper may consume the source-free public standard capacity contract;
- avoid a new generic budget module unless implementation proves the above dependency direction cannot be made import-safe.

Current static import inspection shows no cycle through `operational_selective_1h`, so no new module is presently justified.

## 6. Exact values and invariants

After implementation, under current committed cadence/runtime policy:

| surface | requests | per-token non-shared | Scheduler |
|---|---:|---:|---:|
| canonical FAST+FAST both-eligible lifecycle | 236 | 117 | 210 |
| `operational_standard_4h` public contract | 236 | 117 | 210 |
| public command standard policy | 236 | 117 | 210 |
| standard preflight projection | 236 | 117 | 210 |
| immutable standard campaign config | 236 | 117 | 210 |
| one-shot authorization campaign policy | 236 | n/a | 210 |

For mixed/normal actual lifecycle subsets, existing `standard_campaign_lifecycle_budget()` remains authoritative:

- FAST + NORMAL both eligible: `188 / 162`;
- NORMAL + NORMAL both eligible: `140 / 114`;
- FAST + FAST no 4h continuation: `98 / 82`.

The wrapper/public outer ceiling remains the worst-case standard authorization envelope; it does not force all requests to occur.

## 7. Focused TDD/proof

Use minimum sufficient offline verification.

### RED first

Extend the existing directly affected standard test surface to prove current drift before production edits:

- canonical derived maximum is `236/210`;
- public command standard policy must equal derived contract (`236/117/210`);
- wrapper authorization document must equal derived contract (`236/210`);
- a document manually changed back to `230` must be rejected;
- public standard policy contract must equal arithmetic owner.

Current HEAD should fail the new cross-owner equality assertions because command/wrapper still carry `230/114`.

### GREEN

After the narrow implementation, run only directly affected tests initially:

- `tests/test_v2_9_8b_first_hour_safety_provenance_repair.py`;
- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py`;
- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py`;
- any existing wrapper-specific standard authorization test file if separate and directly affected.

Also run `py_compile`/import smoke checks for:

- `one_token_4h_runtime.py`;
- `operational_standard_4h.py`;
- `operational_memory_factory_command.py`;
- `standard_four_hour_one_shot_wrapper.py`.

Do not run a broad suite unless a focused failure points to wider coupling.

## 8. No runtime proof in this repair lane

The defect is deterministic policy/authorization propagation. The proof must stay offline.

Do not:

- invoke providers;
- start Central Scheduler runtime;
- open a write connection to the authoritative DB;
- generate memories;
- create an authorization package;
- apply a one-shot marker;
- run standard-four-hour preflight against the authoritative host as a substitute for unit proof;
- start another standard-four-hour campaign.

Fresh host operational rereadiness comes only after implementation closeout PASS.

## 9. Rollback / stop conditions

Stop implementation and report blocked if:

- deriving capacity introduces an import cycle;
- derivation requires DB/source/Scheduler/filesystem/environment access;
- repaired outer value does not compute to `236` under the current committed policy;
- per-token non-shared value cannot be derived exactly as `117` from the two-token worst-case contract;
- Scheduler value changes from `210` without an independently approved reason;
- wrapper cannot validate authorization without importing a side-effectful runtime owner;
- ordinary 15m policy changes;
- selective-1h behavior changes unintentionally;
- any hard safety/freshness/provenance/identity/continuity gate is weakened.

## Money-usefulness contribution

The design makes mandatory first-hour safety work and the one-use authorization envelope describe the same bounded resource reality. This protects the next memory-growth attempt from consuming scarce authorization on a preventable policy mismatch while adding no financial or market-risk capability.

## What this lane improves

- removes the architectural cause of `230`/`236` split-brain;
- preserves policy-derived capacity rather than fixing only literals;
- keeps authorization deterministic and fail-closed;
- adds the missing cross-owner equality proof;
- preserves the already-approved fresh-safety repair unchanged.

## What this lane still does not unlock

- implementation until the next lane;
- operational rereadiness PASS;
- new authorization;
- provider/source fetching;
- Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- another standard-four-hour attempt;
- 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Import coupling:** command/wrapper consumption of the public contract must stay acyclic and side-effect free.
- **Derived constant initialization:** module-import derivation must remain deterministic under committed policy and must not silently swallow malformed policy.
- **Per-token naming:** `117` is a worst-case non-shared standard-token contribution, not a standalone one-token campaign ceiling.
- **Historical authorization evidence:** old `230` files remain valid historical consumed evidence but invalid as fresh repaired authorization policy.
- **Selective adjacency:** this design deliberately does not silently repair/re-activate selective-1h; any shared helper impact must be proven semantic-neutral.
- **Host rereadiness pending:** even a green offline implementation does not authorize a run.

## Next permitted lane

`SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_IMPLEMENTATION`

Implement only this design, run the minimum sufficient offline proof, then write a closeout only if exact-head proof passes.
