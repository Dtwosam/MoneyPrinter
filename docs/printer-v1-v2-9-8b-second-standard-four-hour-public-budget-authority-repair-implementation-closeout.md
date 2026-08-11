# Printer V1 V2-9.8B — Second Standard Four-Hour Public Budget Authority Repair Implementation Closeout

## Verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

The standard-four-hour `230`/`236` split-brain is removed at its architectural cause. One canonical lifecycle arithmetic owner now feeds one derived public standard capacity contract, and every downstream public/authorization surface projects exactly that contract instead of maintaining an independent number.

## Baseline

- implementation branch: `agent/v2-9-8b-public-budget-authority-repair-implementation`
- baseline HEAD: `ba2843f0e26d67ad6175d27adce0ab63e30bb308`
- repair-scope audit: `146261d41cdd5ac9a13054bd3e8237d78d98db83`
- design: `docs/printer-v1-v2-9-8b-second-standard-four-hour-public-budget-authority-repair-design.md`
- repaired safety/provenance implementation: `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`
- frozen consumed launch branch `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation` at `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`: **unchanged, not reused, not run**

## Implemented dependency direction

```text
one_token_4h_runtime
        ↓
operational_standard_4h
        ↓                 ↓
public command       one-shot wrapper
```

Verified acyclic by import smoke: importing `operational_standard_4h` loads neither the public command nor the wrapper.

## What changed

### 1. `one_token_4h_runtime.py`

Unchanged. `standard_campaign_lifecycle_budget(tracking_lanes, continuing_mask)` remains the sole owner of cadence/context/4h-phase summation. `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3` unchanged.

### 2. `operational_standard_4h.py`

- added `standard_four_hour_capacity_contract()`, deriving the standard worst-case public capacity from the canonical FAST+FAST / both-eligible lifecycle calculation;
- it reads the shared `discovery` component, requires exactly two token slots, and requires the non-shared remainder to divide exactly across those slots, failing closed with `StandardFourHourOperationalError` otherwise;
- `LIFECYCLE_REQUEST_OUTER_CEILING`, the new `LIFECYCLE_REQUESTS_PER_TOKEN`, and `LIFECYCLE_SCHEDULER_OUTER_CEILING` are now derived from that contract rather than maintained as literals;
- `standard_four_hour_policy_contract()` additionally projects `lifecycle_requests_per_token`;
- derivation is deterministic and source-free — no source, DB, Scheduler, filesystem, or environment access.

### 3. `operational_memory_factory_command.py`

- removed independent standard-4h `230`/`114` capacity ownership;
- `STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING`, `STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN`, and `STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING` now project the derived public contract;
- `STANDARD_FOUR_HOUR_POLICY` therefore carries the same truth into `build_standard_four_hour_preflight()`, `_run_operational_campaign()`, `_create_campaign_command()`, and the immutable `inner_15m_ceilings` campaign configuration — all of which already read `policy.*`, so no projection site needed rewriting.

### 4. `standard_four_hour_one_shot_wrapper.py`

- removed independent `230` request authority;
- `LIFECYCLE_REQUEST_OUTER_CEILING` / `LIFECYCLE_SCHEDULER_OUTER_CEILING` now project the same derived contract;
- `fixture_authorization_document()` generates and `validate_standard_four_hour_authorization_document()` requires `236/210`;
- a newly constructed authorization document changed back to `230` fails closed with campaign-policy mismatch.

Historical consumed authorization evidence was not rewritten. The untracked `operator-runs/` evidence directories were not added, deleted, or modified.

## Exact proof

### `py_compile` / import smoke — all PASS

`one_token_4h_runtime.py`, `operational_standard_4h.py`, `operational_memory_factory_command.py`, `standard_four_hour_one_shot_wrapper.py`.

### RED first

`tests/test_v2_9_8b_second_standard_four_hour_public_budget_authority_repair.py` was added before production edits and failed at baseline `ba2843f0`:

`12 failed, 6 passed` — including `test_newly_constructed_stale_230_authorization_fails_closed`, which proved the wrapper still *accepted* `230`.

### GREEN

```text
pytest tests/test_v2_9_8b_first_hour_safety_provenance_repair.py \
       tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py \
       tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py \
       tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_final_public_wiring.py \
       tests/test_v2_9_8b_second_standard_four_hour_public_budget_authority_repair.py
-> 48 passed, 14 subtests passed
```

### Exact cross-owner equality

| surface | requests | per-token non-shared | Scheduler |
|---|---:|---:|---:|
| canonical FAST+FAST both-eligible lifecycle | 236 | 117 | 210 |
| `operational_standard_4h` public contract | 236 | 117 | 210 |
| public command standard policy | 236 | 117 | 210 |
| standard preflight projection | 236 | 117 | 210 |
| immutable campaign-config projection | 236 | 117 | 210 |
| one-shot wrapper authorization | 236 | n/a | 210 |

Also proven:

- stale newly constructed `230` authorization: **rejected**;
- FAST + NORMAL both eligible: `188 / 162`;
- NORMAL + NORMAL both eligible: `140 / 114`;
- FAST + FAST no 4h continuation: `98 / 82`;
- `CONTINUATION_CLOSE` reserves exactly `4`;
- Scheduler outer ceiling remains `210` on every owner — no Scheduler increase;
- `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT == 3` per token — no stale-15m safety fallback.

### Pre-existing unrelated failures (not repaired in this lane)

Measured at baseline `ba2843f0` and again after the change — identical, so this lane regressed nothing:

- `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` and adjacent Git-provenance fixtures: `31 failed, 29 passed` both before and after. The anchor previously recorded "three" such failures; the measured current count on this branch is `31`, all worktree/fixture-state dependent and unrelated to standard-four-hour capacity.
- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_factory_barrier.py`: `4 failed, 12 passed` both before and after. These pin pre-repair subset budgets (`74` where the safety repair now yields `80`, i.e. `+2 × 3` fresh 1h safety transports). They belong to the earlier safety/provenance repair lane, not to this budget-authority lane.
- `tests/test_v2_9_8b_window_15m_final_integrated_readiness_repair.py`: pre-existing collection `ImportError` on `_attach_fingerprint_for_episode` from `lane_k_e2z_pipeline_wiring`. Untouched here.

No broad suite was run as a gate; the focused failures pointed to no wider coupling.

## Money-usefulness contribution

Mandatory first-hour safety work and the one-use authorization envelope now describe the same bounded resource reality. The next memory-growth attempt can no longer consume a scarce, non-reusable standard-four-hour authorization on a preventable capacity mismatch between the planner and the authorization document. No financial or market-risk capability was added.

## What improved

- removed the architectural cause of the `230`/`236` split-brain rather than only the literals;
- capacity stays policy-derived: a cadence/runtime policy change now moves every public standard surface together;
- authorization remains deterministic and fail-closed, and now fails closed on stale `230`;
- added the missing cross-owner equality proof as a durable regression guard;
- preserved the already-approved fresh-safety repair unchanged.

## What remains locked

- fresh host operational rereadiness;
- authorization creation/review;
- authorization reuse;
- standard-four-hour run;
- rerun/resume/restart/successor of either consumed attempt;
- provider/source calls;
- Central Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL;
- wallet, private keys, real funds, live execution.

Selective-1h behavior was not changed. The adjacent `92/45` versus `98/48` representation drift remains separately recorded; no shared helper change was necessary.

Freshness, provenance, safety, Source Governor, Scheduler, identity, continuity, and B.2 were not weakened.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Import-time derivation:** the public contract is computed once at module import. It is deterministic and source-free, but a future malformed cadence policy now fails loudly at import rather than silently publishing a stale number. That is the intended fail-closed direction.
- **Per-token semantics:** `117` is a worst-case *non-shared* standard-token contribution, not a standalone one-token campaign ceiling. It must not be reused as a single-token budget.
- **Historical authorization evidence:** already-consumed `230` files remain valid historical evidence but are invalid as fresh repaired authorization policy. The wrapper now rejects them if newly constructed.
- **Factory-barrier subset tests still stale:** four pre-existing failures pin pre-safety-repair subset budgets. They are unrelated to this lane but will need their own lane before they stop being noise.
- **Git-provenance fixture failures understated in the anchor:** the anchor recorded three; the measured count is `31`. Corrected in the anchor by this closeout.
- **Rereadiness still pending:** a green offline implementation does not authorize a run.

## Next permitted lane

Fresh post-budget-authority-repair operational rereadiness audit. It is an independent lane and is not unlocked automatically by this closeout.
