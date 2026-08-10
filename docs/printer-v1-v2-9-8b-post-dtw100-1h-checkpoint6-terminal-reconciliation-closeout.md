# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 6 Terminal-Reconciliation Closeout

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_6_TERMINAL_RECONCILIATION_PASS`

Checkpoint 6 closes the first-hour lifecycle truth gap. A completed or failed/cancelled first-hour path can no longer leave the exact campaign `WINDOW_1H` or its owning token slot falsely active after the real work is finished.

This PASS authorizes no live run, fresh authorization, 4h continuation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, or execution capability.

## Baseline and branch

- Checkpoint-5 exact-closeout baseline: `e659d9354ce13b1930fd6c1ea5ee3c3877198cac`.
- Branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint6-terminal-reconciliation`.
- Audit commit: `2bd655c5e2ca2e920254c883d2a4f6d39a6d433c`.
- Design commit: `83cd2d870e61d6ba900b35f5ddd5c8765efc2e3c`.
- RED test commit: `4ea3fa520d217623d180000b955a4ddd10396e12`.
- Implementation commit: `e52edfc22328819bf586f2c6a346ad9098d0f038`.

No source fetching, operational Scheduler execution, authorization creation, authoritative DB mutation, operational memory generation, 4h activation, retrieval, paper decision, or financial capability ran.

## Audit result

Audit verdict:

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_6_TERMINAL_RECONCILIATION_AUDIT_BLOCKED_WINDOW_AND_TOKEN_STATE_RECONCILIATION_REQUIRED`

The audit confirmed Scheduler/work cleanup was already healthy. The remaining defects were lifecycle-state drift:

- success could bind the physical first-hour row but leave the campaign window `CLOSE_PENDING`;
- success could leave the token slot `WINDOW_1H_CONTINUING`;
- token-local failure could block the window while leaving the token active;
- run-wide cancellation could cancel the window while leaving the token active;
- successful campaign-window terminal classification was not derived from authoritative first-hour memory truth.

## Repair design

Design verdict:

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_6_TERMINAL_RECONCILIATION_REPAIR_DESIGN_PASS`

The design reused existing ownership/state tables and exact continuation Scheduler ownership. No schema, migration, retry path, Scheduler job type, cadence rule, source contract, or 4h successor was introduced.

Terminal mapping is now explicit:

| First-hour result | Campaign `WINDOW_1H` | Token slot |
|---|---|---|
| exact eligible clean first-hour episode | `CLEAN_PROMOTED` | `WINDOW_1H_CLOSED` |
| dirty / do-not-train / non-clean first-hour row | `DIRTY` | `WINDOW_1H_CLOSED` |
| valid close with no authoritative clean object | `NO_PROMOTION` | `WINDOW_1H_CLOSED` |
| token-local continuation execution failure | `BLOCKED` | `FAILED` |
| run-wide safe-stop cancellation while still active | `CANCELLED` | `MANUAL_REVIEW` |

`WINDOW_1H_CLOSED` is a completed first-hour checkpoint, not 4h permission.

## TDD evidence

### Valid RED

Exact RED HEAD: `4ea3fa520d217623d180000b955a4ddd10396e12`.

Disposable PR #117 was closed unmerged.

Workflow:
- run `31369512382`;
- job `93395116465`.

Result:
- 120 tests ran;
- 114 passed;
- exactly 6 CP6 lifecycle assertions failed;
- the CP6 identity-conflict test passed;
- all Checkpoints 1-5 and directly affected Scheduler/cadence regressions passed.

The six RED failures matched the audit exactly: three successful terminal classifications, success idempotency, token-local failure token state, and run-wide cancellation token state.

## Implementation

Implementation commit:

`e52edfc22328819bf586f2c6a346ad9098d0f038` — `Reconcile first-hour terminal lifecycle truth`

Production changes were limited to:

- `src/printer_v1/operator_cli/operational_selective_1h.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`

One superseded Checkpoint-4 assertion was modernized in:

- `tests/test_v2_9_8b_post_dtw100_checkpoint4_1h_close_boundary.py`

The CP6 RED test itself was unchanged by implementation.

### Atomic first-hour lifecycle reconciliation

`reconcile_1h_terminal_lifecycle(...)` now owns one exact campaign `WINDOW_1H` plus its exact token slot in one SQLite transaction.

It:

- requires exact window kind and durable window/slot campaign-run-cycle-token-pair identity equality;
- validates exact physical `WINDOW_1H` token/pair identity on successful close;
- binds the physical row only on the exact success owner;
- advances success `CLOSE_PENDING -> AUDITING -> terminal`;
- advances success token `WINDOW_1H_CONTINUING -> WINDOW_1H_CLOSED` without inventing a terminal failure cause;
- maps token-local block to `FAILED` with the same immutable cause;
- maps shared/run-wide cancellation to `MANUAL_REVIEW` with the same immutable cause;
- preserves already terminal window/token state on exact idempotent replay;
- rejects conflicting terminal state, first cause, memory binding, or target identity;
- reads back state before the transaction commits.

### Authoritative successful classification

The factory now derives first-hour campaign terminal state from the physical memory row plus exact clean-episode truth:

- exact eligible `WINDOW_1H_CLEAN_MEMORY` -> `CLEAN_PROMOTED`;
- dirty / do-not-train / non-clean data -> `DIRTY`;
- otherwise -> `NO_PROMOTION`.

A runtime/source/continuity failure is not converted into normal no-promotion; it remains `BLOCKED`.

### Failure/cancellation isolation

The existing exact continuation Scheduler-job -> campaign-window owner is reused.

- token-local failure reconciles only its exact window and token slot;
- peer lifecycle state is untouched;
- run-wide cleanup reconciles only still-active first-hour windows/tokens;
- already completed/terminal peers retain their state and first cause.

Scheduler completion/failure/cancellation and campaign Scheduler-work synchronization were not changed.

## GREEN proof

Disposable PR #119 was closed unmerged.

Exact tested implementation HEAD:

`e52edfc22328819bf586f2c6a346ad9098d0f038`

Workflow:
- run `31370426763`;
- job `93397925385`.

Results:
- compile PASS;
- **120/120 tests PASS**.

The GREEN set includes:

- seven CP6 terminal-reconciliation tests;
- Checkpoints 1-5;
- standard-first-hour harness/reporting alignment;
- operational first-hour tests;
- campaign Scheduler ownership/schema regressions;
- shared cadence/continuity regressions.

## Money-usefulness contribution

Printer's first-hour evidence, clean-memory result, campaign window, token slot, and Scheduler work can now agree on whether the first hour actually finished. This removes stale active-state ambiguity that could otherwise corrupt later rotation, reporting, or 1h->4h predecessor decisions.

It improves the reliability and learning value of the first-hour corpus. It does not establish profitability or authorize a paper action.

## What Checkpoint 6 improves

- exact first-hour campaign-window terminal truth;
- exact first-hour token lifecycle truth;
- authoritative clean/dirty/no-promotion mapping;
- token-local failure isolation;
- shared safe-stop/manual-review distinction;
- first-terminal-cause immutability and exact replay idempotency;
- trustworthy first-hour predecessor boundary for later roadmap review.

## What remains locked

- no live first-hour run;
- no fresh authorization/wrapper execution;
- no source fetching or operational Scheduler runtime from this closeout;
- no standard 1h->4h continuation yet;
- no 12h/24h;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid APIs;
- no scoring, ranking, confidence, weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently authorize continuation, memory outcome, retrieval, or decisions.

## Proof still required before operational use

This is an offline composition proof. It does not authorize a live first-hour run or fresh one-use authorization.

Before any operational first-hour execution, the later roadmap must still provide the required rereadiness/authorization/proof boundary.

Before implementing the user's proposed standard 1h->4h policy, a separate current-state 4h audit/design must verify the actual operational 4h owner, two-token budget/cadence/Scheduler envelope, predecessor continuity, source-stack assumptions, and downstream locks.

## Functionality Risks / Setbacks / Efficiency Blockers

- First-hour lifecycle reconciliation is intentionally strict: identity/cause conflicts fail closed rather than being repaired heuristically.
- Physical first-hour coverage remains the 2700-second continuation segment while semantic outcome covers the continuous first hour; future refactors must preserve that distinction.
- `WINDOW_1H_CLOSED` is not implicit `WINDOW_4H_CONTINUING` authority.
- Run-wide cancellation maps a still-active token to `MANUAL_REVIEW`, not token-local `FAILED`; future cleanup must preserve this distinction.
- Scheduler/work reconciliation remains a separate existing owner; lifecycle code must not duplicate Scheduler state transitions.
- A future 4h expansion must rederive bounded two-token resource use rather than assuming the existing one-token/proof-oriented 4h machinery is operationally sufficient.

## Next permitted work

After this closeout receives exact-head verification, the first-hour Checkpoint 1-6 chain may be treated as offline-composition closed.

The next roadmap-safe step is a **read-only Standard Four-Hour Lifecycle Current-State Audit** before any 1h->4h policy/source-stack amendment or implementation.

Do not create a fresh operational authorization automatically.
