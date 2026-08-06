# Printer V1 V2-9.8B WINDOW_15M Checkpoint 5 — Checkpoint 3 Guard Import-Order Blocker Analysis

## Status

`CROSS_CHECKPOINT_ARCHITECTURAL_BLOCKER`

Checkpoint 5 remains open and blocked before focused proof completion.

- Checkpoint 5 baseline: `421e409628a0db443f1c417835a9d5b06bbdc834`
- Audit commit: `601297c338b6ec50d5006ce6302b473496763f6f`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation`
- Linear: `DTW-31`

No production or test change is made by this analysis.

## Reproduction

The corrected Checkpoint 5 proof reached the exact audit commit and passed the pure-AST static contracts:

```text
CHECKPOINT5_SYNTAX_STATIC_CONTRACTS_PASS:fail_job_calls=3:work_scopes=4
```

Pytest then failed during collection of:

```text
tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py
```

The import error occurred before any test ran:

```text
ImportError: cannot import name 'AbstractCampaignCommand' from partially initialized module
'printer_v1.operator_cli.abstract_campaign_command'
```

No Checkpoint 5 PASS marker printed.

## Exact import cycle

```text
authoritative lifecycle test
-> operator_cli.abstract_campaign_command
-> operator_cli.final_campaign_report
-> operator_cli.campaign_authority_adapters
-> operator_cli.one_command_15m_factory
-> discovery.scheduler_parity
-> discovery package __init__
-> install_checkpoint3_guards()
-> discovery.combined_executor
-> operator_cli.abstract_campaign_command (still partially initialized)
-> ImportError
```

The cycle is deterministic when `abstract_campaign_command` is the first relevant operational module imported in a fresh interpreter.

## Root cause

`src/printer_v1/discovery/__init__.py` performs eager package-import side effects:

```python
install_checkpoint3_guards()
```

`install_checkpoint3_guards()` immediately imports both:

- `printer_v1.discovery.combined_executor`
- `printer_v1.discovery.permanent_discovery_availability`

`combined_executor` imports `AbstractCampaignCommand`. When the discovery package was reached through the ordinary report/factory dependency chain, `abstract_campaign_command` has not completed initialization, so the eager guard installation re-enters it and fails.

The failure was introduced by the Checkpoint 3 package-level guard installation architecture. It is not caused by provider state, database state, Scheduler state, test data, or the Checkpoint 5 proof wrapper.

## Why this is not another proof-command defect

The first Checkpoint 5 attempt failed because the proof script itself directly imported `one_command_15m_factory`. That was correctly classified as a harness defect.

The second attempt removed that direct import and passed all static assertions. The failure then occurred inside normal pytest collection of the authoritative lifecycle test. Therefore the remaining failure belongs to repository import behavior, not the shell wrapper.

## Reachability and checkpoint impact

The defect is import-order dependent, but deterministic for a fresh interpreter that imports `abstract_campaign_command` before `combined_executor`. It prevents isolated collection of an existing authoritative lifecycle proof and leaves module startup dependent on unrelated prior imports.

Checkpoint 5 cannot claim Scheduler/lifecycle readiness while its authoritative lifecycle owner cannot be imported reliably in isolation.

Primary classification:

```text
CROSS_CHECKPOINT_ARCHITECTURAL_BLOCKER
```

Supporting classification:

```text
DETERMINISTIC_BLOCKER_CONFIRMED
```

## Safety disposition

Do not:

- remove the authoritative lifecycle tests from the proof;
- pre-import another module only to hide the cycle;
- swallow the `ImportError`;
- conditionally skip Checkpoint 3 guards when a module is partially initialized;
- weaken any Checkpoint 3 discovery, handoff, pair-identity, or request-root contract;
- continue to Checkpoint 6.

Any repair must preserve all three Checkpoint 3 contracts while removing eager package-import side effects.

## Required next sequence

1. Present and approve a narrow cross-checkpoint repair design.
2. Add a minimal RED test that imports the affected operational modules in fresh subprocesses and proves the current cycle.
3. Implement only the approved import-boundary repair.
4. Run the import-order RED/GREEN proof and the minimum Checkpoint 3 regression set.
5. Rerun the unchanged Checkpoint 5 focused proof.
6. Close Checkpoint 5 only if all evidence passes.

## Money-usefulness contribution

Reliable import and startup ownership is defensive money-usefulness. A future bounded paper-only memory campaign cannot safely produce evidence if activation depends on accidental module import order. Repairing this blocker would improve startup determinism without adding any source, trading, retrieval, wallet, or financial capability.

## What remains locked

All providers, public runtime, authorization, authoritative DB mutation, memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, longer windows, wallets, keys, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- The Checkpoint 3 guards currently patch large owner modules at import time; changing only import order can silently leave guards uninstalled.
- A workaround that passes one test order may still fail in another fresh interpreter.
- Directly integrating the three guards into their owner modules is cleaner but changes already-closed Checkpoint 3 code and needs focused regression evidence.
- Checkpoint 5 proof cannot continue until one approved repair preserves both import stability and all three Checkpoint 3 contracts.
