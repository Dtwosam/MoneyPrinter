# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Close / Memory / Terminal-Reconciliation Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CLOSE_MEMORY_TERMINAL_RECONCILIATION_AUDIT_BLOCKED_REPAIR_DESIGN_REQUIRED`

The physical one-token `WINDOW_4H` close and clean-memory quality pipeline are substantially reusable and must not be rebuilt.

The standard two-token campaign is not yet closeout-complete because successful 4h physical outcomes are not bound back to their exact campaign `WINDOW_4H` / token-slot lifecycles, and the existing final 4h validator remains one-token/proof-shaped.

A narrow repair design is required before implementation.

This audit authorizes no code, runtime, source fetching, DB operational mutation, memory generation, real `WINDOW_4H` collection, authorization, or activation.

## Baseline

Audit baseline:

`27d331579c3329fd7bedf8e5d7f36fe9f2c9990f`

This baseline contains the independently proven collection execution/state/accounting repair and its durable PASS closeout.

No production file, test, schema, migration, source row, Scheduler row, memory row, campaign state, or authorization was changed by this audit.

## Reusable physical 4h close path

`src/printer_v1/operator_cli/one_token_4h_runtime.py::close_current_run_4h` already provides the required physical main-window close primitive.

It already enforces:

- exact current-run 1h predecessor resolution;
- exact token/pair/tracking-lane identity;
- real opening long snapshot;
- exact closing snapshot target;
- unique linkage from the current long close step to the closing snapshot;
- fixed policy-derived 4h deadline;
- long-window continuity evaluation;
- cadence evaluation across only run-attached long snapshots;
- fail-closed continuity/cadence blocker handling;
- dirty classification when continuity/cadence is dirty;
- exact `printer_memory_windows` `WINDOW_4H` construction;
- idempotent physical-window replay by exact token/pair/start-anchor identity.

The physical close should be reused, not replaced.

## Reusable shared 4h context path

`one_command_15m_factory.py::_execute_long_4h_step` already:

- forces the long closing snapshot through the shared governed snapshot path;
- gathers the approved closing market/chain, safety and exit-quote context;
- persists that context through existing owners;
- calls `close_current_run_4h`;
- builds `shared_window_4h_context_evidence` from exact current-run ledger identity;
- marks the physical window dirty/do-not-train when shared 4h context is not clean-ready;
- otherwise preserves the shared context on the physical window.

No second context collector is justified.

## Reusable 4h quality / clean-memory path

### E2Q

The current `e2q_memory_window_audit.py` implementation supports `WINDOW_4H` despite stale top-level wording that still describes 4h as disabled.

The actual code includes:

- `WINDOW_4H` in valid main window kinds;
- `E2Q_4H_MIN_ELAPSED_SECONDS = 10800`;
- `_validate_genuine_4h_window`;
- exact start/end snapshot identity checks;
- continuity metadata requirements;
- normal clean/dirty/audit-only classification.

The stale module commentary is documentation debt, not a runtime blocker for this checkpoint.

### Lane Q

`lane_q_15m_window_integrity_guard.py` also supports `WINDOW_4H` in its current implementation:

- `_MIN_ELAPSED_BY_WINDOW['WINDOW_4H'] = 10800`;
- exact window identity and snapshot anchors;
- CLEAN_DATA / do-not-train gate;
- cadence/coverage evaluation through the canonical policy.

Its historical 15m-centric name/header is not permission to fork a new 4h guard.

### E2Z / clean object promotion

`e2z_clean_memory_creation.py` allows `WINDOW_4H` and additionally requires:

- clean-ready `shared_window_4h_context_evidence`;
- E2Q audit evidence;
- explicit passed Lane Q report for long windows;
- clean physical-window status.

`clean_object_promotion.py` creates the episode kind dynamically from the physical window kind:

`f"{window['window_kind']}_CLEAN_MEMORY"`

Therefore a clean 4h promotion becomes `WINDOW_4H_CLEAN_MEMORY`. The fingerprint also preserves the exact physical `window_kind`.

There is no need for a new memory writer or 4h-specific E2Z engine.

## Finding 1 — successful WINDOW_4H campaign binding is absent

The main factory success path contains an explicit successful first-hour binding:

- after a successful `CONTINUATION_CLOSE`, it requires `memory_window_id`;
- `_bind_owned_continuation_memory_window_at_close` resolves the exact owned campaign `WINDOW_1H`;
- it classifies authoritative memory truth;
- it invokes the atomic first-hour terminal reconciler before Scheduler completion.

There is no equivalent success branch for `LONG_CONTINUATION_CLOSE`.

Current successful 4h sequence can therefore be:

1. campaign 4h close job claimed -> campaign window becomes `CLOSE_PENDING`;
2. physical `WINDOW_4H` row closes;
3. shared context / E2Q / Lane Q / E2Z run;
4. run step becomes `SUCCEEDED`;
5. Scheduler job completes and campaign Scheduler-work projection reaches terminal truth;
6. campaign `WINDOW_4H` remains `CLOSE_PENDING` and token slot remains `WINDOW_4H_CONTINUING`.

That is a campaign-truth blocker even when the physical memory result is valid.

## Finding 2 — 4h terminal owner supports failure/cancel only

The collection/state/accounting repair added `_terminalize_owned_long_window`, but intentionally limited it to collection-stage terminal outcomes:

- `BLOCKED -> token slot FAILED`;
- `CANCELLED -> token slot MANUAL_REVIEW`.

It does not support successful outcome states:

- `CLEAN_PROMOTED`;
- `DIRTY`;
- `NO_PROMOTION`;
- `ALREADY_EXISTS_IDEMPOTENT`.

That limitation was correct for the previous checkpoint and must not be treated as a defect in that closeout.

The next design needs an exact successful 4h memory-binding/terminal owner analogous to the proven first-hour reconciliation contract, with `WINDOW_4H_CLOSED` as the successful token state.

## Finding 3 — authoritative 4h terminal classification must be stage-correct

The existing first-hour classifier is explicitly hard-coded to:

- physical `window_kind='WINDOW_1H'`;
- episode kind `WINDOW_1H_CLEAN_MEMORY`.

It cannot be reused unchanged for 4h.

For 4h, authoritative clean promotion must be proven from an exact clean episode/fingerprint pair attached to the same physical `WINDOW_4H` row. The current clean-object promotion owner already creates `WINDOW_4H_CLEAN_MEMORY` dynamically.

Required categorical terminal interpretation should remain consistent with existing product semantics:

- exact complete clean object -> `CLEAN_PROMOTED`;
- dirty / audit-only / do-not-train physical result -> `DIRTY`;
- clean physical candidate without successful promotion -> `NO_PROMOTION`;
- exact idempotent clean-object replay may use `ALREADY_EXISTS_IDEMPOTENT` only when the authoritative clean object already exists and identity is exact.

The design must verify the exact authoritative source for each classification rather than rely only on a nested report label.

## Finding 4 — existing final 4h validator is one-token/proof-shaped

`one_command_15m_factory.py::_four_hour_terminal_validation` remains built around the older one-token 4h proof shape.

When the 4h phase starts it currently:

- derives one tracking lane from the first long step;
- derives one expected snapshot count from that one lane;
- counts all long snapshots against that one expected value;
- requires `len(close_steps) == 1`;
- validates one physical 4h successor.

A standard campaign has exactly two owned `WINDOW_4H` lifecycles and may contain mixed `TRACK_FAST` / `TRACK_NORMAL` lanes. Such a campaign can lawfully have two forced long closes with different policy-derived snapshot counts.

Therefore the old validator cannot be made authoritative for the standard two-token campaign without a narrow campaign-aware composition.

The historical one-token validator must remain available for its proven callers; do not rewrite it globally merely to satisfy the standard campaign.

## Finding 5 — old compressed-two-token proof validator is not the new standard campaign contract

`_two_token_continuous_proof_validation` represents an older proof where exactly one selected token continues through 1h/4h and the other stops after 15m.

It explicitly expects:

- two 15m closes;
- one 1h close;
- one 4h close;
- exactly one authoritative clean promotion in that proof shape.

That is useful historical proof logic but is not the standard two-token 4h campaign contract implemented by B1/B2, where two exact 4h campaign windows and their Scheduler ownership are created.

Do not broaden or reinterpret the old proof validator as the standard campaign validator.

## Finding 6 — physical lifecycle completion and money-memory acceptance remain separate

The current 4h terminal validator correctly contains an important product rule: lifecycle completion is not the same as clean-memory acceptance.

A lawful physical 4h close may complete while its evidence is dirty/audit-only or while clean promotion is unavailable. That must not be rewritten into fake clean memory or a generic runtime failure.

The campaign terminal states already provide the correct categorical distinction:

- `CLEAN_PROMOTED`;
- `DIRTY`;
- `NO_PROMOTION`;
- `ALREADY_EXISTS_IDEMPOTENT`;
- `BLOCKED` / `CANCELLED` for failure/stop paths.

The next design must preserve that separation per token.

## Finding 7 — ordering boundary for successful reconciliation is already demonstrated by 1h

The first-hour factory path performs successful campaign binding after the physical memory pipeline result is available but before canonical Scheduler completion/synchronization is committed.

That ordering is the safest reuse precedent for 4h:

- physical close / quality result must exist first;
- exact campaign window must still be `CLOSE_PENDING`;
- bind the exact physical memory row and reconcile campaign window + token slot;
- then complete the canonical Scheduler job and synchronize Scheduler-work truth;
- commit the success transaction.

A 4h campaign-binding fault must not be hidden by completing the Scheduler job first.

The design must account for the fact that the physical 4h quality path already uses committed DB state / separate DB connections. It must not pretend the entire physical close + E2Q + E2Z pipeline is one SQLite transaction when it is not.

## Existing owners that should be reused

Do not rebuild:

- `close_current_run_4h` physical close;
- `build_window_4h_context_evidence`;
- E2Q genuine 4h validation;
- Lane Q 4h integrity/cadence guard;
- E2Z / `promote_clean_object` clean episode + fingerprint owner;
- B2 stage-scoped Scheduler ownership;
- collection-state `PLANNED -> COLLECTING -> CLOSE_PENDING` transitions;
- Scheduler complete/fail/cancel owners;
- campaign Scheduler-work synchronization;
- token-local/shared failure cleanup.

The repair should compose these owners rather than fork them.

## Money-usefulness contribution

The physical 4h pipeline already creates the type of long-horizon evidence Printer needs to learn whether a Solana memecoin continued, survived, collapsed, revived, distributed, or lost liquidity after the first hour.

What is missing is trustworthy campaign truth around those outcomes. Without exact binding/reconciliation, a real clean or dirty 4h result can exist while the campaign still says the token is continuing.

Closing this gap makes later corpus accounting and memory-yield reporting trustworthy without inflating clean-memory counts or treating dirty evidence as profit-relevant learning.

This audit creates no new market evidence and proves no profitability.

## What this audit improves

- proves the physical 4h close does not need replacement;
- proves E2Q, Lane Q and E2Z already contain 4h-capable logic;
- identifies successful campaign memory binding as a missing composition boundary;
- identifies the old terminal validator as one-token/proof-specific;
- preserves lifecycle-completion vs clean-memory-acceptance separation;
- prevents an unnecessary new memory engine or quality pipeline.

## What remains locked

Still locked:

- repair design/implementation until separately approved by build order;
- real `WINDOW_4H` collection;
- operational 4h rereadiness/authorization;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, audits, PnL;
- wallet, signing, live execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

## Minimum proof required after a later approved implementation

A later focused offline proof must establish at least:

1. clean token A physical 4h close binds only A's exact campaign `WINDOW_4H`, terminalizes it `CLEAN_PROMOTED`, and advances only A's slot to `WINDOW_4H_CLOSED`;
2. dirty/audit-only token B terminalizes `DIRTY` with no clean episode counted;
3. clean-but-not-promoted outcome terminalizes `NO_PROMOTION` rather than fabricating clean memory;
4. exact pre-existing complete clean object replays idempotently without duplicate episode/fingerprint rows or conflicting campaign cause;
5. physical 4h memory token/pair/window-kind mismatch fails closed before campaign terminalization;
6. successful binding requires campaign state `CLOSE_PENDING` and token state `WINDOW_4H_CONTINUING`;
7. Scheduler completion/synchronization occurs only after exact successful campaign reconciliation;
8. two standard 4h windows can close independently in either arrival order;
9. mixed FAST/NORMAL lanes use each token's own policy-derived expected snapshot count;
10. standard campaign terminal validation accepts two exact terminal 4h closes and rejects missing/foreign/duplicate close identity;
11. one token's dirty/no-promotion outcome does not force the peer into failure;
12. zero active owned Scheduler work and zero nonterminal owned 4h campaign windows remain at standard campaign closeout;
13. historical one-token 4h proof behavior remains healthy;
14. first-hour Checkpoints 4–6 remain healthy;
15. real 4h collection and 12h/24h remain disabled throughout offline proof.

Use risk-based verification. A broad suite is unnecessary unless the implementation becomes cross-cutting beyond this design boundary.

## Functionality Risks / Setbacks / Efficiency Blockers

- Reusing the first-hour classifier unchanged would search the wrong window/episode kind.
- Treating `lane_k_status` alone as authoritative could misclassify an incomplete or identity-mismatched clean object.
- Completing the Scheduler job before campaign binding could leave a terminal Scheduler projection beside an active `CLOSE_PENDING` campaign window.
- Replacing the old one-token validator globally could regress previously proven 4h feasibility/proof paths.
- A single aggregate expected-snapshot count is wrong for mixed FAST/NORMAL standard campaigns.
- Forcing dirty/audit-only memory to clean would violate the money-usefulness and dirty-memory locks.
- The physical quality path spans committed DB operations; the next design must define truthful transaction boundaries rather than claim impossible whole-pipeline atomicity.
- Stale 15m-centric E2Q/Lane-Q module wording may confuse future maintainers, but documentation cleanup must not expand the implementation lane unless necessary.

## Next permitted task

A separate **standard four-hour close / memory / terminal-reconciliation repair design** may begin.

The design must be campaign-aware, preserve the proven one-token physical close and historical proof validators, and specify the exact successful binding/classification/terminal-validation boundary before any production edit.
