# Printer V1 V2-9.8B WINDOW_15M Checkpoint 5 — Checkpoint 3 Guard Import-Order Repair Design

## Decision

Use owner-integrated guards. Remove eager package-import mutation.

## Root cause

`printer_v1.discovery.__init__` executes `install_checkpoint3_guards()` during every discovery package import. The installer imports `combined_executor`, which imports `abstract_campaign_command`. A valid opposite import order enters:

`abstract_campaign_command -> final_campaign_report -> campaign_authority_adapters -> one_command_15m_factory -> discovery.__init__ -> checkpoint3_guards -> combined_executor -> abstract_campaign_command`

The final re-entry observes a partially initialized module and fails deterministically.

## Required behavior preserved

The repair must preserve all three accepted Checkpoint 3 contracts:

1. A direct-provider failure persists the exact governed request identity, failure identity, and work linkage before terminalization.
2. Handoff rejects an existing pair whose token row or base-token mint conflicts with the candidate mint.
3. Source-scope membership accepts only the exact request-key root or one hyphen-delimited descendant.

## Architecture

- Put the direct-provider failure logic directly in `CombinedPumpfunCampaignExecutor._run_direct_lane`.
- Put the pair/token identity validation directly in `CombinedPumpfunCampaignExecutor._handoff_one_slot`.
- Define `request_key_belongs_to_root` directly in `permanent_discovery_availability.py`.
- Remove `install_checkpoint3_guards()` from `discovery/__init__.py`.
- Delete `checkpoint3_guards.py` after no production or test import remains.

No lazy installer, conditional skip, import-order workaround, second owner, or duplicate runtime path is allowed.

## Proof

1. RED subprocess imports fail on the pre-repair commit for each order:
   - `printer_v1.operator_cli.abstract_campaign_command`
   - `printer_v1.operator_cli.authoritative_live_operational_campaign`
   - `printer_v1.operator_cli.one_command_15m_factory`
   - `printer_v1.discovery.combined_executor`
2. GREEN subprocess imports pass independently after repair.
3. Minimum Checkpoint 3 regressions prove the three preserved contracts.
4. Unchanged Checkpoint 5 focused proof passes.
5. `git diff --check` and clean disposable worktree pass.

## Boundaries

- No provider or source call.
- No public Printer command.
- No Scheduler/lifecycle runtime.
- No authorization.
- No authoritative database mutation.
- No memory generation.
- No retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- No longer-window activation.
- No Checkpoint 6 work.

## Money-usefulness contribution

A deterministic import failure can prevent the Scheduler-owned lifecycle from starting or being verified. Removing import-time mutation restores reliable startup and testability without changing market behavior, selection semantics, memory admission, or financial capabilities.

## What this does not unlock

This repair does not authorize a production run, memory generation, retrieval, paper decisions, financial actions, or any window beyond the already approved Checkpoint 5 scope.

## Functionality Risks / Setbacks / Efficiency Blockers

- Moving guard logic must be byte-for-behavior equivalent to the accepted Checkpoint 3 contracts.
- Deleting the installer must not leave any indirect import or stale test dependency.
- The very large `combined_executor.py` file increases edit risk; changes must stay limited to the two existing owner methods.
- Checkpoint 5 remains blocked until the unchanged focused proof passes after repair.
