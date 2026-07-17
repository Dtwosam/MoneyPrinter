# Printer V1 V2-9.7B.3 Tracking Lifecycle Reconciliation Closeout

## Verdict

V2_9_7B_3_TRACKING_LIFECYCLE_RECONCILIATION_PASS

V2-9.7B.3 is complete. The one-command factory now reconciles every selected
token after natural completion, safe stop, cancellation, blocked collection, or
failure. The exact discovery tracking handoff and its associated scheduler work
cannot remain active after terminal cleanup.

The repair is lifecycle/reporting-only. It does not change discovery,
collection, memory promotion, safety acceptance, continuation, proof
supervision, retrieval, or financial behavior.

## Implemented Repair

`tracking_lifecycle_reconciliation.py` adds
`reconcile_factory_post_cycle_lifecycle()`, a reusable connection-scoped
terminal reconciliation function. The factory invokes it from its existing
`finally` cleanup path before the durable final report is stored.

For each selected token/pair, the function:

1. resolves the exact discovery handoff by supplied queue identity, with a
   token/pair/lane active-row fallback for backward-compatible handoffs;
2. derives lifecycle only from the main-window per-token outcome;
3. terminalizes the handoff as `COOLDOWN`, `ARCHIVED`, or `SKIPPED`;
4. cancels active scheduler work attached to the handoff and support step;
5. records one existing lifecycle event and a categorical terminal reason;
6. embeds the reconciliation in the factory final report;
7. remains no-op idempotent after the exact terminal state is reached.

No schema migration, historical rewrite, campaign loop, rotation policy, or new
classification was introduced.

## Exact Categorical Mapping

| Main outcome | Explicit lifecycle policy | Queue disposition | Existing lifecycle event | Evidence label |
|---|---|---|---|---|
| `CLEAN`, terminal main window | `cooldown` | `COOLDOWN` | `ENTER_COOLDOWN` | `CLEAN_DATA` |
| `DIRTY`, terminal main window | `cooldown` | `COOLDOWN` | `ENTER_COOLDOWN` | `CLEAN_DATA` for the lifecycle fact only; memory remains dirty |
| `NO_PROMOTION`, terminal main window | `cooldown` | `COOLDOWN` | `ENTER_COOLDOWN` | `CLEAN_DATA` for the lifecycle fact only; no clean result is invented |
| Any terminal main result above | explicit `archive` | `ARCHIVED` | `ARCHIVE_AFTER_MEMORY_WINDOW` | unchanged memory status |
| Incomplete, cancelled, blocked, or failed main lifecycle | not eligible for cooldown/archive | `SKIPPED` | `MANUAL_REVIEW` | `DO_NOT_TRAIN` |

The factory passes the existing conservative `cooldown` policy explicitly.
`archive` remains available only as an explicit existing categorical policy.
The function does not choose replacements, rotate candidates, or reopen tokens.

## Terminal Queue and Scheduler Behavior

- The original discovery handoff row is terminalized; no replacement active
  queue row is created.
- Active queue-targeted scheduler jobs in `PENDING`, `RUNNING`, or `COOLDOWN`
  are cancelled and their locks are cleared.
- Pending or running `SUPPORT_5M` steps become `CANCELLED`, and any attached
  scheduler job is cancelled.
- Natural completion, operator stop, duration stop, token-local failure, and
  global safe-stop all reach the same factory `finally` reconciliation path.
- Two selected tokens are reconciled independently by exact token and pair.
- One token's failure cannot change the other token's disposition.

## Replay and Idempotency

The existing lifecycle-event payload carries
`factory_reconciliation_key = run_id:token_id:pair_id`. Reconciliation searches
for that exact key before writing an event.

A repeated call:

- creates no duplicate lifecycle event;
- creates no queue row;
- does not refresh an already-correct terminal queue timestamp;
- does not re-cancel terminal scheduler jobs;
- reports `idempotent_replay=true`.

Report-only replay continues to read the stored final report and performs no
reconciliation, source call, or evidence write.

## WINDOW_5M_MICRO_EVENT Contract

`WINDOW_5M_MICRO_EVENT` remains support-only.

- Existing capture continues to exact-link the support window to run, token,
  pair, lane, and parent `WINDOW_15M`.
- Reconciliation scopes support cleanup to the same run/token/pair.
- Completed support remains audit evidence.
- Pending or running support and its scheduler work terminate with the parent.
- Support status is not read when choosing lifecycle disposition.
- 5m cannot create cooldown, archive, reopen, 1h continuation, or 4h
  continuation independently.
- 5m remains excluded from authoritative clean yield and main thresholds.
- Dirty or blocked 5m evidence remains audit-only.
- Conditional micro-event capture was not implemented.

## Authoritative Promotion and Safety Regression

V2-9.7B.1 remains unchanged. Authoritative clean yield still comes only from
eligible `printer_episodes` promotion rows joined to exact run-attached memory
windows. The lifecycle repair does not read or modify E2Q, Lane Q, Lane K, E2Z,
or promotion policy.

V2-9.7B.2 remains unchanged. Effective safety reporting continues to separate
raw evidence from `SAFETY_CONTEXT_ACCEPTABLE`, `SAFETY_CONTEXT_BLOCKED`, and
`SAFETY_CONTEXT_UNKNOWN`. No acceptance gate was broadened.

## Verification Results

Focused isolated-DB reconciliation suite: 5/5 PASS.

- clean main completion: one `COOLDOWN` disposition and no active handoff job;
- dirty main completion: explicit archive policy produces one `ARCHIVED`
  disposition without inventing clean memory;
- failed token plus replay: `SKIPPED` / `MANUAL_REVIEW`, one event, no timestamp
  churn on replay;
- mixed two-token stop: independent `COOLDOWN` and `SKIPPED` outcomes;
- pending 5m support: support step and scheduler job cancel, while the clean
  parent main outcome alone selects `COOLDOWN`.

Existing cooldown/archive/reopen focused regressions: 4/4 PASS.

Nearest one-command factory regressions: 4/4 PASS.

- natural completion and stored report replay;
- duration-stop pending-job cleanup;
- zero retrieval and financial deltas;
- two-token independent opening anchors.

V2-9.7B.1 and V2-9.7B.2 regressions: 6/6 PASS.

Focused tracking-queue and scheduler regressions: 6/6 PASS.

Python compilation, accidental-unlock scan, persistent DB hash comparison,
approved-file inspection, and `git diff --check` complete successfully.

## Persistent DB Isolation

Only temporary isolated databases were used by tests. No discovery, source,
runtime, proof launcher, memory generation, or persistent campaign was run.

Persistent DB before and after:

- path: `data/printer_v1.sqlite3`
- size: `13017088` bytes
- SHA-256: `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`
- mutation delta: zero

No historical queue row was rewritten in the persistent DB.

## Zero Retrieval and Financial Deltas

The nearest factory regression confirms zero deltas for retrieval queries,
retrieval matches, paper decisions, paper positions, paper trade events, paper
trade audits, and paper audit reports. The new module writes only the existing
tracking queue, scheduler job, run-step, and lifecycle-event surfaces.

## Money-Usefulness Contribution

The repair prevents stale active-token state from inflating workload,
reselecting already-consumed token/pairs, or obscuring whether a collected
lesson reached a trustworthy terminal state. Clean and negative outcomes now
leave an auditable lifecycle fact, while failed or incomplete evidence is
closed fail-safe for manual review instead of being silently recycled.

This improves corpus efficiency and operator trust without treating lifecycle
state as profit, a decision signal, or a clean-memory substitute.

## What This Lane Improves

- Reconciles discovery handoffs after every factory terminal path.
- Integrates existing cooldown/archive vocabulary with explicit policy.
- Provides one terminal disposition and reason per selected token.
- Prevents stale queue and scheduler work after completion, stop, or failure.
- Adds run-keyed idempotency without migration.
- Preserves two-token isolation.
- Makes support-5m terminal cleanup explicit and non-authoritative.
- Adds lifecycle reconciliation to the durable final report.

## What Remains Locked

- Operational memory growth and persistent corpus campaigns.
- Campaign loops, replacement selection, candidate rotation, and silent recycle.
- Conditional 5m capture.
- Selective 15m to 1h and 1h to 4h continuation changes.
- Heartbeat or proof-supervision repair.
- Embedded Git provenance.
- V2-9.7C, V2-9.7D, V2-9.7E, V2-9.8, and V2-10.
- Retrieval activation and retrieval-backed decisions.
- BUY, SELL, HOLD, paper decisions, positions, trade events, audits, and PnL.
- Live execution, wallets, private keys, signing, transactions, and real funds.
- Paid APIs, scoring, ranking, confidence percentages, weighted logic,
  embeddings, and vectors.

Existing reopen behavior remains unchanged. Revival still requires the explicit
existing reopen path and the governed evidence requirements enforced by the
selection contract.

## Proof Requirements Completed

- Static discovery handoff, queue, scheduler, lifecycle, and 5m inspection.
- Clean, dirty, blocked/failed, cancellation, and two-token terminal fixtures.
- Exact queue and associated scheduler cleanup.
- One lifecycle event per run/token/pair.
- Idempotent repeated reconciliation.
- Existing cooldown, archive, and reopen compatibility.
- Existing promotion-reporting and safety-reporting compatibility.
- Zero retrieval and financial deltas.
- Python compilation and static lock checks.
- Persistent DB hash preservation.

No additional 4h proof was required or run.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Current effect | Control / later lane |
|---|---|---|
| Factory currently applies `cooldown` to every completed main outcome | Archive is not automatically selected | Keep explicit categorical policy; design operational archive criteria in V2-9.7C |
| Incomplete/failed tokens end `SKIPPED` with `MANUAL_REVIEW` | No automatic replacement is chosen | Rotation/replacement remains a V2-9.7C/D campaign concern |
| Persistent DB still contains historical stale queue rows | This lane does not rewrite history | Reconcile only future selected-token runs; separately approved maintenance would be required for old rows |
| 5m capture remains unconditional in continuous proof mode | Support collection may consume avoidable capacity | Conditional capture remains locked for V2-9.7C/D |
| Operational supervision and recovery remain absent | Lifecycle cleanup is reusable but not an operational launcher | V2-9.7B.4 and later operational implementation |
| No embedded Git provenance | Final lifecycle report is not yet self-identifying to a commit | V2-9.7B.5 |
| Partial wallet-level flow authenticity remains | Lifecycle must not imply wallet authenticity | Preserve partial/caution labels and avoid authenticity claims |

## Files Changed

- `src/printer_v1/operator_cli/lane_x3_post_cycle_lifecycle.py`
- `src/printer_v1/operator_cli/tracking_lifecycle_reconciliation.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `tests/test_v2_9_7b_3_tracking_lifecycle_reconciliation.py`
- `docs/printer-v1-v2-9-7b-3-tracking-lifecycle-reconciliation-closeout.md`

## What Was Built

A reusable, idempotent selected-token terminal reconciliation path integrated
with the existing one-command factory cleanup and final report.

## What Was Not Touched

Persistent databases, migrations, schemas, historical rows, discovery/source
execution, continuation policy, proof supervision, promotion policy, safety
acceptance, retrieval, financial functions, and unrelated untracked artifacts.

## Tests / Checks Run

- Focused V2-9.7B.3 isolated-DB tests.
- Focused existing cooldown/archive/reopen tests.
- Nearest one-command factory regressions.
- V2-9.7B.1 promotion-reporting regressions.
- V2-9.7B.2 safety-reporting regressions.
- Focused queue and scheduler regressions.
- Python compilation.
- Accidental-unlock scan.
- Persistent DB hash comparison.
- Approved-file scope inspection.
- `git diff --check`.

## Pass / Fail Status

V2_9_7B_3_TRACKING_LIFECYCLE_RECONCILIATION_PASS

## Risks or Concerns

The repair closes current factory handoffs but intentionally does not clean old
persistent queue history, select replacement tokens, or define campaign-level
cooldown/archive policy. Those remain activation blockers, not defects to hide
inside this narrow lane.

## Next Recommended Phase

V2-9.7B.4: harden heartbeat/lease atomic update behavior without changing proof
supervision policy.