# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-operator-review-readonly-lockout-audit`.

Latest fully verified code/test HEAD before this handoff-only update:
`58adc67614c3af4c0ce4df3f16ab8117abdf7c31`.

GitHub Actions run `34411148811`, job `102665605816`, is green on that HEAD:

- focused reporting/operator-review boundary:
  **526 passed, 3 subtests passed** in 415.43s;
- affected report-module compile: passed;
- diff whitespace check: passed.

The previous broad downstream/lifecycle verification remains green on
`d6a8839d5b18d15b586e9b9dc108d9a06e8e9e92` via run
`34401666253`: 29 focused + 27 clean-memory consumer + 46 paper-financial +
399 shared, 2 deselected, 32 subtests, plus compile and diff checks. This
reporting-only lane did not re-run that unrelated shared lifecycle suite.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler is the sole
Scheduler owner. `WINDOW_5M_MICRO_EVENT` is support-only; `WINDOW_12H` and
`WINDOW_24H` remain locked.

Current capability locks remain false:

- `RETRIEVAL_ACTIVATION_ENABLED = False`;
- `PAPER_DECISIONS_ENABLED = False`;
- `PAPER_POSITIONS_ENABLED = False`;
- `PAPER_AUDITS_ENABLED = False`;
- `PAPER_PNL_ENABLED = False`.

The verified discovery -> two-cycle 15m/1h/4h -> clean-memory path and the
clean-memory/downstream lockout repairs remain unchanged.

The reporting/operator-review boundary is now explicitly fail-closed:

- E2U 15m closeout and E2W 5m linkage readers no longer fall back from
  `mode=ro` to an ordinary writable SQLite connection;
- E2U and E2W require an existing DB, open with `mode=ro`, enable
  `PRAGMA query_only=ON`, and propagate read-only-open failure;
- post-RC Lane 7 clean-memory retrieval reporting, Lane 8A conservative-action
  readiness review, and Lane 8C conservative-decision audit review share a
  strict read-only opener with the same `mode=ro` + `query_only` contract;
- Lane V clean-memory retrieval reporting is likewise physically read-only;
- those report/review functions contain no write SQL and do not call retrieval,
  decision, position, monitor, audit, or PnL producer APIs;
- Lane 7 explicitly reports current retrieval activation as disabled/locked;
- Lane 8A and Lane 8C explicitly report current paper-decision creation as
  disabled/locked;
- Lane 8A may still report that clean memory is suitable for *review*, but while
  `PAPER_DECISIONS_ENABLED` is false it can no longer recommend proceeding to
  Lane 8B decision creation. Its next step is the separate deliberate
  capability-change requirement;
- legacy fields such as `retrieval_eligible` and
  `memory_window_retrieval_eligible` remain evidence/review classifications
  only. Targeted search found no production consumer using them as activation
  authority;
- dedicated `operator_review` report persistence remains intentional and is
  limited to `printer_operator_review_*` tables. Its evidence/summarization
  reads do not mutate retrieval/paper/lifecycle tables;
- operator DB historical state labels are descriptive status outputs. Targeted
  search found no production consumer treating those state constants as
  permission to activate a locked subsystem.

## Latest meaningful result

The audit found two concrete reporting defects and one semantic authorization
defect.

1. E2U and E2W claimed to be read-only but caught any read-only-open failure and
   silently reopened SQLite writable.
2. Lane V and the post-RC Lane 7/8A/8C report/review functions also claimed
   report-only behavior while opening ordinary writable SQLite connections.
3. Lane 8A could synthesize the operator recommendation
   `operator_may_proceed_to_lane8b_conservative_decision_creation` solely from
   clean-memory review readiness even though the real paper-decision capability
   lock remained false.

All three are repaired. The focused regression proves the relevant connections
are physically non-writable, cannot retry as writable when a read-only open
fails, leave all locked capability tables unchanged, and expose current
capability-lock state separately from evidence/review eligibility.

## Proven blocker / adjacent defect

No blocker remains in the scoped reporting/operator-review read-only lane.

A separate, concrete adjacent legacy bypass is now proven in
`src/printer_v1/operator_cli/commands.py`:

- `build_conservative_paper_decision_payload()` (post-RC Lane 8B) opens the DB
  writable;
- after local eligibility checks it calls
  `_lane8b_insert_conservative_decision()`;
- that helper directly inserts into `printer_paper_decisions`;
- this path does not call `require_paper_decisions_enabled()`.

Therefore the earlier statement that all direct paper-decision creation
surfaces are locked is incomplete: the primary recorder is locked, but this
legacy Lane 8B command is still a reachable direct-write bypass. It was not
modified in the reporting-only lane because Lane 8B is deliberately mutating
and belongs to the next engineering boundary.

This is **not** operational authorization and does not establish authoritative
database or live-run readiness. No operational Printer run, live provider/RPC
or WebSocket execution, Scheduler operation, wallet/signing action, or
authoritative database mutation was performed.

Default branch `master` remains historically divergent from this active
development lineage and is not a safe blind merge/rebase target.

## Exact next permitted action

Begin a narrow development/test-only repair of the legacy post-RC Lane 8B paper
decision creation boundary in `src/printer_v1/operator_cli/commands.py`.

Prove that `build_conservative_paper_decision_payload()`,
`_lane8b_insert_conservative_decision()`, and the Lane 8B CLI entry cannot
emit decision-authority output or insert `printer_paper_decisions` while
`PAPER_DECISIONS_ENABLED` is false. Reuse the existing capability-lock owner;
do not create an independent permission system. Preserve disposable historical
tests by enabling the future capability only inside their test fixture where
needed.

Repair only this concrete reachable bypass and any directly necessary
Scheduler/command seam exposed by focused tests. Do not activate retrieval,
paper positions, monitoring, audits, PnL, live execution, or any operational
Printer path.

Do not run Printer operationally, use live providers, operate Scheduler jobs, or
mutate the authoritative database without a new explicit authorization
boundary.
