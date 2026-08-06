# Printer V1 V2-9.8B WINDOW_15M Checkpoint 7 — Terminal Closure, Cleanup, Replay, and Residue Audit

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_7_TERMINAL_CLOSURE_AUDIT_CONFIRMED_FOUR_BLOCKERS`

Checkpoint 7 audit/readiness is complete. Design, implementation, bounded proof, and closeout remain pending.

- Baseline: `b6890b7bf8788c6a2b22b4a72acc26352e776248`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-7-terminal-closure-cleanup-replay-residue`
- Linear: `DTW-33`
- Phase: audit/readiness only

No authorization was created or consumed. No provider, RPC, WebSocket, Source Governor runtime, Central Scheduler runtime, public Printer campaign, authoritative database mutation, memory generation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, paper-trade audit, PnL, longer-window activation, or Checkpoint 8 work was performed.

## Audit boundary

Static/read-only inspection traced the current public ordinary `WINDOW_15M` path through:

1. initialized public campaign exception handling;
2. main-coordinator heartbeat failure handling;
3. `cleanup_campaign_supervision()`;
4. `reconcile_campaign_terminal()`;
5. campaign/run/cycle/window/token/Scheduler terminal ownership;
6. campaign acceptance and terminal-safety evidence;
7. canonical terminal report construction/persistence;
8. terminal summary and child terminal propagation;
9. public `report-only` replay;
10. durable cleanup, lease, artifact, Scheduler, and residue reconstruction.

## Confirmed ready contracts

The following current contracts are sound and must be preserved:

- the ordinary public command uses `cleanup_campaign_supervision()` before normal full-run report persistence;
- supervision cleanup preserves the first durable terminal cause on idempotent replay;
- cleanup terminalizes campaign Scheduler ownership work and discovery work, cancels attributable active/locked Scheduler jobs, terminalizes campaign windows/cycles/run/campaign, and requires zero active owned work before marking supervision terminal;
- exact lease release is performed only after cleanup, and durable `cleanup_completed_at` / `lease_released_at` are read back from supervision ownership;
- heartbeat renewal no longer performs independent terminal cleanup; it signals the main coordinator;
- the public full-run acceptance gate requires exact cleanup identity, durable terminal supervision, valid cleanup/release timestamps, absent lease lock, zero active owned work, zero locked work, terminal Scheduler ownership, and no retry/restart/resume/successor;
- normal successful full-run report-only replay independently reconstructs the exact durable supervision row, validates cleanup/release timestamps, requires the lease lock to be absent, reloads campaign window/Scheduler ownership rows, and rejects active/locked Scheduler jobs;
- report-only mode performs zero source work, zero Scheduler runtime work, and zero database writes;
- child-terminal handling remains bounded/source-safe and preserves unknown terminal facts as unknown when reconstruction fails;
- downstream retrieval/decision/trading capabilities remain locked.

`reconcile_campaign_terminal()` performs multiple owner transitions that commit individually through `campaign_ownership.transition_state()`. This is not classified as a standalone blocker in this audit because the public command first invokes supervision cleanup and its outer failure coordinator retries cleanup/reconciliation on exceptions. The reconciliation path is therefore intentionally recoverable rather than transactionally atomic across every owner.

## Confirmed blocker 1 — `INITIALIZED_FAILURE_PRECISE_CAUSE_COLLAPSED_TO_EXCEPTION_CLASS`

### Evidence

`LiveOperationalError` and `LiveTransportError` carry a precise `.code` and `.detail`.

When `_terminalize_initialized_failure()` has no earlier durable first cause and no heartbeat terminal cause, it derives:

`OPERATIONAL_CAMPAIGN_FAILED:<ExceptionClass>`

It does not inspect the existing `.code` field. For example, a `LiveOperationalError("CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH", ...)` can therefore be durably terminalized as only `OPERATIONAL_CAMPAIGN_FAILED:LiveOperationalError` if no earlier owner already persisted the specific code.

The public exception envelope later reconstructs durable state and overlays the durable first cause, so this generic value can propagate through the child terminal even though the original exception carried a more precise bounded code.

### Contract conflict

Checkpoint 1 established exact structured first-cause propagation and made stderr non-authoritative. Checkpoint 7 requires precise first-cause propagation across every initialized failure exit.

### Money-usefulness impact

A precise operational failure can become indistinguishable from other failures of the same Python class. Diagnosis becomes less actionable and may encourage unnecessary repeat authorization/runtime attempts.

## Confirmed blocker 2 — `FAILURE_TERMINAL_REPORT_CAN_PERSIST_WITH_UNPROVEN_CLEANUP_OR_LEASE_RELEASE`

### Evidence

`_terminalize_initialized_failure()` attempts cleanup under bounded SQLite-busy retry. If cleanup still raises, it records the cleanup exception in `closure_errors` and continues to reconciliation, accounting, report construction, and report persistence.

`build_campaign_terminal_report()` / `write_campaign_terminal_report()` require valid six-unit evidence when requested, but they do not require:

- `cleanup_completed is True`;
- `lease_released is True`;
- durable terminal supervision;
- valid durable cleanup/release timestamps;
- absent lease lock;
- zero active owned work.

Therefore a failure-path immutable terminal report may be persisted while cleanup or lease release remains unresolved.

Normal successful full-run acceptance is stricter and is not affected by this finding.

### Contract conflict

A canonical terminal report must not imply completed terminal closure when the cleanup owner has not proven closure. Cleanup/lease truth must either gate canonical report persistence or be represented by an explicitly non-clean diagnostic artifact that cannot masquerade as the terminal report.

### Money-usefulness impact

Printer could retain a durable terminal report for a campaign that still needs operator cleanup/recovery, weakening trust in terminal evidence and potentially obscuring residue that matters before the next bounded run.

## Confirmed blocker 3 — `TERMINAL_REPORT_ROW_AND_ARTIFACT_PERSISTENCE_NOT_ATOMIC`

### Evidence

`write_campaign_terminal_report()` persists the canonical report row first through `persist_terminal_report()`, then writes the filesystem artifact.

If artifact creation/write fails after the SQLite commit:

- the immutable `REPORT_TERMINAL` row survives;
- the matching artifact may be missing or incomplete;
- the caller raises only after the database-side terminal report already exists.

The report row and artifact therefore do not close as one fail-closed publication unit.

### Contract conflict

Checkpoint 7 owns report generation and replay integrity. The canonical row/artifact pair must not be able to settle into a half-published terminal state without an explicit blocked/recovery classification.

### Money-usefulness impact

Later audits can see a canonical report row without the exact durable artifact that operators expect to archive and compare, weakening reproducibility and immutable evidence handling.

## Confirmed blocker 4 — `PUBLIC_REPORT_ONLY_IGNORES_ARTIFACT_MISMATCH`

### Evidence

`replay_campaign_terminal_report()` calculates and returns `artifact_matches`.

The public `report_only()` entry point validates exact campaign/run/config/report identity and performs strong full-run durable reconstruction, but it never requires `replay["artifact_matches"] is True` before returning `status="REPLAYED"`.

Consequently, when the report directory exists but the expected report artifact is missing or differs from the canonical database report bytes, the lower-level replay can return `artifact_matches=False` while the public full-run replay continues through durable validation and may still report success.

This is directly reachable from blocker 3 if the DB row committed and the artifact write failed.

### Contract conflict

Public report-only replay must prove both canonical database report identity and exact artifact parity. A mismatch must be a categorical replay blocker, not merely an informational boolean.

### Money-usefulness impact

Printer/operator audit could accept a replay whose durable filesystem evidence does not match the authoritative report row, reducing confidence in reproducible terminal evidence.

## Residue/replay findings that are not blockers

- Normal full-run acceptance already gates on zero active owned work, zero locked work, exact cleanup/lease evidence, and terminal Scheduler ownership.
- Public full-run replay independently reloads campaign windows and stage-scoped Scheduler ownership and requires zero active/locked Scheduler jobs.
- Historical lower-level replay helpers are not the controlling public report-only acceptance surface when the full-run evidence exists.
- The recoverable multi-commit nature of `reconcile_campaign_terminal()` is not by itself a completion blocker because the public coordinator has supervision cleanup first and a fallback terminalization coordinator on raised exceptions. Any repair must preserve this first-cause/idempotent recovery behavior rather than replacing it casually.

## Required design before implementation

One narrow Checkpoint 7 design must cover these four seams together:

1. precise initialized-failure cause extraction with an explicit allowlisted owner rule (prefer an existing safe categorical error code where present; do not persist arbitrary provider/body/detail text as terminal cause);
2. a canonical failure-report publication gate that requires durable cleanup/lease/residue truth before a canonical terminal report row is published, while still preserving bounded diagnostic evidence when cleanup itself fails;
3. an exact fail-closed publication protocol for the report row + artifact pair that prevents or explicitly repairs a half-published state without creating duplicate reports;
4. public report-only enforcement of exact artifact parity, with a precise categorical block reason;
5. preservation of idempotent replay, immutable first cause, Source Governor/Central Scheduler ownership, no retries/restarts/successors, and zero-source/zero-write report-only behavior.

No schema migration should be introduced unless the design proves an existing table cannot represent the required state safely.

## Required RED proof before implementation

Minimum sufficient fail-first regressions:

### RED A — precise initialized first cause

Inject a disposable initialized failure using an existing safe coded operational exception before any durable first cause exists. Current code must demonstrate that the durable terminal cause collapses to the exception class instead of preserving the safe code.

After repair, the exact allowlisted safe code must be durable and propagated; arbitrary detail/body text must not become the terminal cause.

### RED B — cleanup failure cannot publish canonical terminal report

Inject a deterministic cleanup failure after initialization while leaving valid accounting evidence available. Current code must demonstrate that canonical report persistence is still attempted/reachable despite unproven cleanup/lease release.

After repair, canonical terminal report persistence must be blocked; bounded diagnostic/child evidence may still record the cleanup failure and original first cause.

### RED C — half-publication row/artifact

Inject artifact-write failure after a would-be terminal report publication in a disposable DB/artifact root. Current code must demonstrate the committed report-row / missing-artifact half-state.

After repair, the protocol must either leave neither canonical publication or deterministically complete/recover the exact pair without a duplicate/differing report.

### RED D — public report-only artifact parity

Create a valid disposable full-run report row and then remove or alter only its artifact. Current public `report_only()` must demonstrate that it can progress despite `artifact_matches=False`.

After repair, public replay must fail closed with an exact artifact mismatch/missing classification, zero source calls, zero Scheduler runtime calls, and zero database writes.

## Minimum bounded GREEN proof

After an approved implementation:

- all four Checkpoint 7 RED regressions pass;
- existing child-terminal/wrapper first-cause regressions remain green;
- existing supervision cleanup/lease idempotency regressions remain green;
- existing unified terminal closure/current full-run acceptance regressions remain green;
- existing report persistence/idempotency and public report-only regressions remain green;
- exact zero-source/zero-write report-only behavior is re-proven;
- changed-module Python compilation and `git diff --check` pass;
- no broad repository suite is required unless the implementation expands beyond these terminal/report owners.

## Money-usefulness contribution

Checkpoint 7 makes a terminal campaign trustworthy as a stopping boundary. Printer and the operator can know why the campaign stopped, that Scheduler/work/lease ownership is actually closed, that the canonical report is fully published, and that report-only replay reconstructs the same durable truth without new source work.

## What this checkpoint improves

If the four blockers are repaired and proven, Checkpoint 7 will improve:

- precise first-cause diagnosis after initialized failures;
- strict separation between terminal diagnostics and a fully closed canonical terminal report;
- exact report-row/artifact publication integrity;
- public report-only artifact parity;
- confidence that a replayed terminal means cleanup, lease release, Scheduler/work closure, and report evidence are all consistent.

## What this checkpoint still does not unlock

Checkpoint 7 does not unlock:

- a new public live proof by itself;
- Checkpoint 8;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- live wallet, private keys, signing, execution, or real funds;
- paid APIs;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- `WINDOW_1H` proof rerun or `WINDOW_4H`/`WINDOW_12H`/`WINDOW_24H` activation.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Terminal report row/artifact publication spans SQLite and filesystem boundaries, so true cross-resource atomicity is impossible. The design must use an explicit fail-closed publication/recovery protocol rather than pretending one transaction can cover both resources.
2. Failure diagnostics are still needed when cleanup itself fails. Blocking the canonical report must not erase the original first cause or the cleanup failure evidence.
3. Precise cause extraction must remain source-safe. Only existing bounded categorical codes should be eligible; arbitrary exception detail, provider bodies, URLs, headers, secrets, or unbounded text must never become durable terminal cause.
4. Existing successful full-run acceptance/replay already has strong cleanup gates. Repairs must not replace or weaken those gates.
5. Existing reconciliation is deliberately recoverable/idempotent across owner commits. A redesign toward broad transactionality could conflict with owner-level commit semantics and should not be attempted unless a RED proves it necessary.
6. No authorization or live campaign is needed to prove these repairs; disposable SQLite/artifact fixtures are sufficient and preferred.

## Audit completion boundary

Checkpoint 7 audit closes with exactly four confirmed reachable deterministic blockers.

The next allowed phase is Checkpoint 7 design/specification for these four blockers only, followed by deterministic RED regressions before implementation. Checkpoint 8 remains unstarted.
