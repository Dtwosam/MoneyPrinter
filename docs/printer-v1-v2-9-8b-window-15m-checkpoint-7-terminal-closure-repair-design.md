# Printer V1 V2-9.8B WINDOW_15M Checkpoint 7 — Terminal Closure Repair Design

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_7_TERMINAL_CLOSURE_REPAIR_DESIGN_APPROVED`

- Audit baseline: `b6890b7bf8788c6a2b22b4a72acc26352e776248`
- Audit commit: `48f246eda72926ee981004fa5e34ccc1e7e49371`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-7-terminal-closure-cleanup-replay-residue`
- Scope: the four audit-confirmed terminal/report blockers only

No authorization, provider/runtime execution, authoritative DB mutation, retrieval, paper decision, trading capability, longer-window activation, or Checkpoint 8 work is part of this design.

## Design goals

1. Preserve the most precise safe categorical first cause already carried by an initialized operational exception.
2. Never publish a canonical terminal report unless cleanup, lease release, and zero active owned work are proven.
3. Publish the canonical report artifact before the authoritative report row so SQLite can never claim a terminal report whose artifact was never successfully created.
4. Make artifact-first publication idempotent and compensating: if DB persistence fails after a newly created artifact, remove that newly created artifact when possible; an unrecoverable orphan artifact remains non-authoritative and replay stays blocked because no report row exists.
5. Require exact artifact parity in public `report-only` before any replay can return `REPLAYED`.
6. Preserve all current successful full-run cleanup/acceptance/replay gates, first-cause immutability, Scheduler/Source Governor ownership, and no retry/restart/resume/successor rules.

## Repair 1 — safe precise initialized first cause

Add one private owner helper in `operational_memory_factory_command.py`:

`_safe_initialized_exception_terminal_cause(exc)`

Rules:

- existing durable first cause still wins;
- heartbeat terminal cause still wins when present;
- otherwise only the existing bounded `.code` carried by `LiveOperationalError` or `LiveTransportError` is eligible;
- the code must match `^[A-Z][A-Z0-9_]{1,127}$`;
- `.detail`, `str(exc)`, provider bodies, URLs, headers, secrets, and arbitrary exception attributes are never persisted as the terminal cause;
- if no eligible code exists, preserve the current fallback `OPERATIONAL_CAMPAIGN_FAILED:<ExceptionClass>`.

This changes diagnosis precision only. It does not change source/runtime ownership or error-handling policy.

## Repair 2 — canonical failure-report publication gate

In `_terminalize_initialized_failure()` add one explicit publication gate after cleanup/reconciliation/accounting are attempted and before `build_campaign_terminal_report()` / `write_campaign_terminal_report()`.

Canonical failure report publication is allowed only when all are true:

- `cleanup_completed is True`;
- `lease_released is True`;
- `active_owned_work_after` is an integer equal to `0`;
- the cleanup result belongs to the same `supervision_id`, `campaign_id`, `configuration_id`, `run_id`, and `owner_id` as the command.

If the gate fails:

- do not call `write_campaign_terminal_report()`;
- return/write only the bounded terminal diagnostic summary and child-terminal evidence already owned by the public command path;
- preserve the original first cause plus cleanup/reconciliation closure errors;
- set `report_written=False` and `report_block_reason="TERMINAL_CLEANUP_UNPROVEN"`;
- do not invent cleanup/lease facts.

The normal success path and its stricter full-run acceptance gate remain unchanged.

## Repair 3 — artifact-first canonical publication protocol

Change `write_campaign_terminal_report()` in `unified_terminal_closure.py`.

Publication order:

1. validate six-unit evidence when required;
2. compute canonical JSON and report hash;
3. resolve the exact artifact path;
4. if artifact already exists, require exact canonical bytes before continuing;
5. if artifact does not exist, write canonical bytes to an exact sibling temporary file and atomically replace the final artifact path;
6. only after exact artifact existence/parity is proven, call `persist_terminal_report()`;
7. if DB persistence fails and this invocation created the artifact, remove that newly created artifact as compensating cleanup; never remove a pre-existing exact artifact;
8. after DB persistence, re-read/require exact artifact bytes before returning success.

Properties:

- artifact-write failure leaves no terminal report row;
- DB failure after a new artifact attempts compensation, so the authoritative DB never claims an unpublished report;
- pre-existing exact artifact + missing row can be completed idempotently;
- a pre-existing differing artifact blocks before DB mutation;
- a crash that leaves an artifact-only state is non-authoritative and repairable by exact idempotent replay of the same payload; public report-only remains blocked until the row exists;
- no schema migration is required.

Do not create a second report table or report owner.

## Repair 4 — public report-only artifact parity gate

Immediately after `replay_campaign_terminal_report()` returns in public `report_only()`:

- require `replay.get("artifact_matches") is True`;
- otherwise return the existing zero-work replay-blocked surface with:
  - `status="REPLAY_BLOCKED"`;
  - `block_reason="TERMINAL_REPORT_ARTIFACT_MISMATCH"`;
  - `source_calls=0`;
  - `scheduler_runtime_calls=0`;
  - `database_writes=0`.

No later full-run durable reconstruction may override this block.

## Required RED regressions

Add one focused Checkpoint 7 test module covering exactly:

1. safe coded initialized exception currently collapses to class fallback;
2. cleanup failure currently reaches canonical report publication;
3. artifact-write failure currently leaves committed report row;
4. public report-only currently progresses when lower replay reports `artifact_matches=False`.

The tests must use disposable SQLite/artifact fixtures or mocks only. No network/provider/runtime execution.

## Minimum GREEN proof

- four Checkpoint 7 regressions green;
- existing child-terminal/wrapper first-cause tests green;
- existing supervision cleanup/lease idempotency tests green;
- existing unified terminal closure and report persistence/idempotency tests green;
- existing public report-only/full-run acceptance tests green;
- changed-module compilation PASS;
- `git diff --check` PASS.

Use risk-based verification. Do not expand to the full repository suite unless these changes reach beyond the named terminal/report owners.

## Money-usefulness contribution

A terminal result becomes a trustworthy stopping boundary: the operator gets the precise safe reason, canonical report publication means cleanup and lease release were actually proven, and report-only replay requires the exact archived artifact rather than accepting DB-only evidence.

## What improves

- initialized first-cause precision;
- failure terminal cleanup gating;
- report row/artifact publication integrity;
- deterministic recovery/idempotency of artifact-first publication;
- public replay integrity.

## What remains locked

Retrieval, decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, live wallet/signing/funds, paid APIs, scoring/ranking/confidence/weighting, embeddings/vectors, new 1h proof, 4h/12h/24h activation, and Checkpoint 8 remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

1. SQLite + filesystem cannot be one physical transaction; artifact-first plus compensation is the fail-closed protocol.
2. A process crash can leave an artifact-only orphan; it is non-authoritative because no report row exists and is safely completable only by the exact same canonical payload.
3. Safe first-cause extraction must remain deliberately narrow; arbitrary exception text must never become durable terminal cause.
4. Cleanup failure diagnostics must survive even though canonical report persistence is blocked.
5. Existing successful full-run acceptance/replay contracts must not be weakened or duplicated.

## Stop condition

After this design, create the four deterministic RED regressions before production implementation. Do not start Checkpoint 8.