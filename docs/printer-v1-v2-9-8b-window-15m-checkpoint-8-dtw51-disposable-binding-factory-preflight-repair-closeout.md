# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-51 Disposable Binding Factory Preflight Repair Closeout

Date: 2026-08-07

Linear: `DTW-51`

Design HEAD: `998de4bada7ab51ed8042b9a880dc2fdd6111e4a`

Implementation commit: `9d33a097b45988e60d98541af180dfe1767fb891`

Verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW51_DISPOSABLE_BINDING_FACTORY_PREFLIGHT_REPAIR_OFFLINE_PASS`

## Proven defect

The consumed post-DTW50 controlling proof stopped with `SAFE_STOP_PREFLIGHT_FAILED` / `operational persistent mode requires the authoritative corpus` after pilot-input readiness. Outer fifteen-minute binding acceptance already validated the C8 disposable binding, but the lifecycle handoff dropped it before factory operational-persistent preflight, which only accepted the canonical corpus or a production binding.

## Deterministic RED

At the approved design baseline, the focused regression proved:

1. outer disposable validation passes;
2. factory under C8-mapped flags without disposable acceptance emits the corpus reason;
3. factory-run count remains 0.

Classification: `DTW51_DISPOSABLE_BINDING_LOST_BEFORE_FACTORY_PREFLIGHT_RED_CONFIRMED`.

## Repair

- Owner → driver forwards `disposable_public_composition_proof_binding`.
- Driver → factory forwards the same object unchanged.
- Factory operational-persistent preflight ordered law:
  1. production binding present → existing production validation (precedence);
  2. else disposable binding present → durable disposable expectation (or rebuild from the same binding) + existing disposable validator;
  3. else unchanged corpus / production missing-binding fail-closed path.

No second binding authority. No fabricated production binding. No proof-mode remapper substitute. Secondary terminal `run_id` packaging intentionally not included.

## Offline GREEN

- changed-file `py_compile`: PASS
- dedicated DTW-51 regression: `5 passed`
- existing C8 real-consumer compatibility: `9 passed`
- complete focused C8 suite: `110 passed`
- exact four-file implementation manifest: PASS
- `git diff --check`: PASS
- provider/network execution: NONE
- controlling C8 proof: NONE

## Money-usefulness contribution

Restores the only lawful disposable path for Checkpoint 8 factory lifecycle entry after pilot readiness, without weakening production database-target law.

## What remains locked

Checkpoint 8 remains open pending independent DTW-51 review/readiness and a separately authorized future one-shot proof. Operational `WINDOW_15M` memory activation, `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked. Secondary terminal `run_id` packaging remains a separate optional lane.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A future C8 attempt can expose another downstream blocker; do not rerun automatically.
2. Secondary harness packaging (`CHECKPOINT8_TERMINAL_IDENTITY_MISSING`) remains unfixed by design.
3. Another controlling proof requires a new explicit authorization after independent readiness review.
