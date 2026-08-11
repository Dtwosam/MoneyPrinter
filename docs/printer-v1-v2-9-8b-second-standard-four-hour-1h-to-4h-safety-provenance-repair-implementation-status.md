# Printer V1 V2-9.8B — Second Standard Four-Hour 1h→4h Safety/Provenance Repair Implementation Status

> **SUPERSEDED.** This document is the historical partial/blocked checkpoint. The implementation was afterwards completed and proven; the controlling verdict is now
> `V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`
> in `docs/printer-v1-v2-9-8b-second-standard-four-hour-1h-to-4h-safety-provenance-repair-implementation-closeout.md`.
> The tooling blocker and "required canonical integration still unapplied" sections below no longer describe current state.

## Verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_PARTIAL_BLOCKED_TOOLING`

Implementation is **not complete**, bounded offline proof has **not passed**, and this branch is **not runnable or merge-ready**.

This status is a durable implementation checkpoint, not a repair closeout and not authorization for any runtime activity.

## Baseline and branch

- implementation parent baseline: `04abb0f77156fc23a895c3b540e06b997217e70a`
- repair branch: `agent/v2-9-8b-second-standard-4h-safety-provenance-repair`
- audit commit: `303227dd76b96b144dab75c11bf1cb827563babc`
- design commit: `695fd3e53781b1faba13d21226f323d1e586cbb1`
- frozen consumed launch branch remains `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`
- frozen consumed launch HEAD remains `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`

The consumed standard-four-hour authorization remains permanently non-reusable.

## Audit and design status

Audit completed PASS:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_SCOPE_AUDIT_PASS`

Design completed PASS:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_DESIGN_PASS`

The approved repair remains:

1. fresh governed safety collection inside Scheduler-owned `CONTINUATION_CLOSE`;
2. persist that fresh safety/composite against the exact first-hour closing snapshot;
3. close the exact `WINDOW_1H` memory;
4. bind the exact fresh `safety_composite_id` into that memory before outcome/audit/E2Z;
5. retain the unchanged B.2 exact safety consumer and all freshness/provenance/safety hard gates;
6. reserve three first-hour safety transport operations in addition to the exact-pair close observation;
7. raise request ceilings accordingly without adding Scheduler jobs.

Reusing the earlier 15m safety composite remains prohibited because the committed safety freshness contract is 30 minutes and the first-hour close occurs beyond that boundary.

## Production-code implementation completed so far

### 1. Exact first-hour safety-binding helper

Added:

`src/printer_v1/operator_cli/first_hour_safety_binding.py`

Commit:

`11d0d66bdcb144d1c4eb7b830df31633f10bcf18`

The helper is source-free and fail-closed. It validates exact:

- `WINDOW_1H` target;
- token identity;
- pair identity;
- closing snapshot identity;
- safety composite identity;
- composite token/pair/mint/pair-address identity;
- composite snapshot identity;
- supporting-context shape;
- conflicting prior safety binding.

On success it preserves existing supporting context and writes only the exact `memory_build_evidence_overlays.safety_composite_id` linkage.

### 2. First-hour transport reservation constant

Updated:

`src/printer_v1/sources/measured_transport.py`

Commit:

`9ec4bd1eece94764bf247fde2e8b3f0b9aae91cb`

Added:

`FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3`

and changed the hard `CONTINUATION_CLOSE` transport reservation from `1` to `4`:

- exact closing observation: 1;
- first-hour safety context worst-case reserve: 3.

No Scheduler count was added.

### 3. Policy-derived lifecycle request components

Updated:

`src/printer_v1/operator_cli/one_token_4h_runtime.py`

Commit:

`c4b6590667d238a8c0467e8091545f6ba489ae8d`

Added the explicit first-hour safety request component to one-token and standard two-token lifecycle budget derivation.

Expected standard both-eligible ceilings become:

| lanes | request ceiling | Scheduler ceiling |
|---|---:|---:|
| FAST + FAST | 236 | 210 |
| FAST + NORMAL | 188 | 162 |
| NORMAL + NORMAL | 140 | 114 |

Scheduler ceilings remain unchanged.

### 4. Focused offline proof staged but not executed

Added:

`tests/test_v2_9_8b_first_hour_safety_provenance_repair.py`

The focused proof is designed to check:

- `CONTINUATION_CLOSE == 4` transport reservations;
- explicit first-hour safety reservation family;
- exact 236/188/140 request ceilings;
- unchanged 210/162/114 Scheduler ceilings;
- exact fresh composite binding while preserving existing context;
- fail-closed target/snapshot/window mismatches;
- fresh-safety collection → exact snapshot → persistence → 1h close → binding → outcome/audit ordering;
- 236 standard outer request ceiling;
- no live providers, Scheduler runtime, authoritative corpus DB, retrieval, decisions, positions, trades, audits, or PnL.

This test has **not** produced a passing execution result yet.

## Required canonical integration still unapplied

A compare against the implementation baseline confirms these two required files are still unchanged on the repair branch:

1. `src/printer_v1/operator_cli/one_command_15m_factory.py`
2. `src/printer_v1/operator_cli/operational_standard_4h.py`

Therefore the implementation is incomplete.

### Remaining `one_command_15m_factory.py` changes

The exact approved integration still needs to:

1. import `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT`;
2. add that count to `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN` so continuous/selective first-hour hard ceilings cannot reject the newly approved governed calls;
3. label `CONTINUATION_CLOSE` reservation ordinal `0` as `CONTINUATION_CLOSE_OBSERVATION` and ordinals `1..3` as `FIRST_HOUR_SAFETY_CONTEXT`;
4. thread `context_adapter_factories` into `_execute_continuation_close()`;
5. inside the already Scheduler-owned close step, call existing `_collect_preclose_context(... include=frozenset({"safety"}))` before the final exact-pair snapshot;
6. after that snapshot succeeds, call existing `_persist_preclose_context()` against the exact new closing snapshot;
7. after `close_1h_memory_window_from_snapshot()` creates/resolves the exact `WINDOW_1H` row, call `attach_first_hour_safety_overlay()` before first-hour outcome derivation and before audit/E2Z;
8. preserve existing cancellation, no-retry, holder-primary-plus-one-approved-backup, Source Governor, Scheduler ownership, audit, E2Z, and terminal behavior.

No provider call may be moved into `lane_e2o_1h_window_close.py` and B.2 must not be changed to search for an arbitrary latest safety composite.

### Remaining `operational_standard_4h.py` change

Change only the standard outer request ceiling:

`LIFECYCLE_REQUEST_OUTER_CEILING = 230`

→

`LIFECYCLE_REQUEST_OUTER_CEILING = 236`

The standard Scheduler outer ceiling remains `210`.

## Why implementation stopped here

The connected GitHub API supports whole-file replacement, not a surgical line patch. `one_command_15m_factory.py` is a large canonical orchestration file; replacing the entire file from a truncated connector response would create unacceptable corruption/drift risk.

Two isolated GitHub Actions approaches were attempted solely as offline editing/test harnesses:

- workflow run `31480678969`;
- shell-only workflow run `31481278895`.

Both created GitHub job records but failed before any runner step started. The jobs exposed no executed steps and no usable logs. A direct job rerun reproduced the same pre-step failure. Therefore these were CI-startup failures, **not repair-test failures** and not proof of implementation correctness.

The local tool container also could not resolve GitHub over outbound DNS, so it could not safely clone the public branch and apply the deterministic patch there.

Temporary CI artifacts were then removed. Temporary PR `#180` was closed unmerged, and the temporary CI-base branch was force-reset to the unchanged classification baseline. No temporary workflow, trigger, or self-patching helper remains in the repair-branch final diff.

## Safety status

No Printer provider/source calls were made by this lane.

No Central Scheduler runtime was executed.

No authoritative Printer DB was opened for mutation.

No memory was generated.

No new authorization was created.

No consumed authorization was reused.

No standard-four-hour rerun/resume/restart/successor occurred.

No `WINDOW_4H`, 12h, or 24h runtime was launched.

No retrieval, paper decision, BUY/SELL/HOLD, position, trade event, audit, or PnL capability was unlocked or exercised.

The frozen consumed launch branch was not modified.

## Money-usefulness contribution

The completed portion establishes the exact safety binding and truthful lifecycle capacity needed for a first-hour memory to carry fresh, auditable safety authority into the later 4h decision boundary. It improves the correctness of the future repair without weakening the safety/freshness rules that protect memory quality.

## What this implementation checkpoint improves

- exact fresh-safety binding contract exists as isolated production code;
- transport reservation truth now models the worst-case first-hour safety bundle;
- policy-derived standard request budgets include the first-hour safety component;
- focused proof requirements are encoded in a dedicated offline test;
- the final two canonical integration edits are precisely bounded.

## What this checkpoint still does not unlock

Everything downstream remains locked, including:

- completion/merge of this repair;
- operational rereadiness;
- new authorization creation;
- another standard-four-hour attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL.

## Proof required before implementation completion

The implementation lane cannot close until all of the following are true on one exact repair HEAD:

1. the two remaining canonical source edits are applied exactly as designed;
2. the focused offline repair test executes and passes;
3. touched Python modules compile/import successfully;
4. focused directly affected budget/safety/first-hour regressions are green if required by a failure signal;
5. exact branch diff contains no temporary harness artifacts and no unrelated production changes;
6. no hard gate, Source Governor, Scheduler, Solana-only, paper-only, or downstream lock is weakened.

Only after that may an implementation closeout be written. A passing implementation closeout still does not itself authorize runtime.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Partial integration risk:** `CONTINUATION_CLOSE` now reserves four operations at the measured-transport layer while the canonical factory has not yet been wired to collect/bind the corresponding fresh safety bundle. This branch must not be run.
- **Budget-representation drift:** policy-derived budgets include first-hour safety while the canonical factory-local continuous ceiling and standard outer constant remain old until the final edits land.
- **False-confidence risk:** the staged test has not executed; no PASS may be inferred from static inspection.
- **Large-file corruption risk:** whole-file replacement from truncated connector output was rejected rather than risking damage to the canonical orchestration owner.
- **CI infrastructure blocker:** both temporary GitHub jobs failed before runner steps, so hosted CI cannot currently supply the missing edit/proof path.
- **Scope-drift risk:** no workaround may move source work into the source-free close module, weaken 30-minute freshness, reuse stale 15m safety as fresh 1h authority, or make B.2 fall back to arbitrary latest evidence.

## Current roadmap-compliant next step

Remain inside:

`SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION`

Complete the exact two remaining canonical source edits in a writable execution environment, then run the focused bounded offline proof and write the implementation closeout only if it passes.

Do **not** advance to operational rereadiness, authorization, or another 4h attempt while this verdict remains partial/blocked.