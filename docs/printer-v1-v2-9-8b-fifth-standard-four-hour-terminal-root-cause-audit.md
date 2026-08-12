# Printer V1 V2-9.8B — Fifth Standard-Four-Hour Terminal Root-Cause Audit

## Verdict

`V2_9_8B_FIFTH_STANDARD_4H_TERMINAL_ROOT_CAUSE_AUDIT_PASS_WITH_COMMITTED_CODE_DEFECTS`

The fifth one-use standard-four-hour attempt is permanently consumed and must not be retried, resumed, restarted, or reused.

The run reached the intended four-hour close boundary, but both authorized `WINDOW_4H` close jobs failed deterministically. The direct blocker is a committed runtime authority-propagation defect. The same attempt also exposed a separate standard-four-hour terminal-report/acceptance contract drift that must be designed and repaired before another authorization is considered.

This lane is audit-only. It performs no source fetch, Scheduler/runtime execution, DB mutation, memory generation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, PnL, authorization creation, or successor run.

## Authority and lineage

Use inside the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order, not the sole source of truth.

Launch provenance:

- frozen launch branch: `agent/v2-9-8b-fifth-standard-4h-authorization-preparation`
- launch HEAD: `f826c3653b79715bedecaca6dc337a992efd41e6`
- independent authorization-review closeout: `0e916e1132983588e422b91cf537aac23d0d7d07`
- authorization: `V2_9_8B_STANDARD_4H_AUTH_20260811T232811Z`
- authorization SHA-256: `edc117ab0e82cc17efc47c72f72e23d5e0497cd7c41614bf66dc015101b7dfda`

Attempt identities:

- execution: `20260811T234855Z-2367205e0a1c`
- campaign: `20260811T234855Z-2367205e0a1c-campaign`
- campaign run: `20260811T234855Z-2367205e0a1c-campaign-run`
- factory run: `f52beaea-c62c-4193-be89-063a41247755`

## Durable terminal truth

The wrapper completed with child exit `0`, but this is controlled-command completion only, not a standard-four-hour PASS.

Durable child terminal:

- `status = OPERATIONAL_CAMPAIGN_TERMINAL`
- `terminal_category = OPERATIONAL_COMMAND_COMPLETE`
- `terminal_truth_status = NOT_APPLICABLE_SUCCESS`
- `first_terminal_cause = SAFE_STOP_4H_TERMINAL_INCOMPLETE`
- authorization marker consumed: true
- wrapper automatic retries/reruns/resumes/restarts/successors: zero

The runtime remained active from approximately `2026-08-11T23:48:55Z` through `2026-08-12T03:49:38Z`, reaching the intended four-hour close boundary.

All authoritative active counts were zero after cleanup. Lease release and cleanup completed. Locked downstream capability counts remained at their historical baseline; no positions, trade events, trade audits, or PnL were activated.

## Defect A — direct runtime blocker

Classification:

`COMMITTED_CODE_DEFECT__STANDARD_4H_CLOSE_DROPS_ENABLED_SUCCESSOR_PLANNING_AUTHORITY`

Observed evidence:

- both token slots produced successful `WINDOW_4H` snapshot work through the final cadence point;
- slot 1 final Scheduler job `1806`, `LONG_CONTINUATION_CLOSE`, failed with `successor_enabled_without_explicit_planning_authority`;
- slot 2 final Scheduler job `1837`, `LONG_CONTINUATION_CLOSE`, failed with the same cause;
- both campaign `WINDOW_4H` rows therefore ended `BLOCKED` with no `memory_window_row_id`;
- campaign terminal reconciliation then safe-stopped as `SAFE_STOP_4H_TERMINAL_INCOMPLETE`.

Static code cause at launch HEAD:

1. `lifecycle_continuity.build_long_window_continuation_plan(...)` intentionally blocks an enabled real-collection successor unless `allow_enabled_successor_planning=True`.
2. Standard-four-hour planning explicitly supplies that authority through `_plan_token_4h_phase(...)`, so the two `WINDOW_4H` streams are lawfully planned and run.
3. `close_current_run_4h(...)` later calls `resolve_current_run_long_predecessor(...)` without forwarding the same authority.
4. The resolver therefore falls back to `allow_enabled_successor_planning=False` and rejects the already-authorized enabled `WINDOW_4H` at its final close.

This is not a provider failure, rate-limit blocker, budget exhaustion, Scheduler-capacity failure, authorization failure, or expected operational stop. It is a deterministic mismatch between standard-four-hour planning authority and standard-four-hour close authority.

The repair must not simply weaken the global long-window guard. Design must preserve the default fail-closed behavior for unauthorized/historical callers and propagate or separate explicit standard-campaign close authority only at the approved boundary.

## Defect B — standard-four-hour terminal acceptance/reporting drift

Classification:

`CONTRACT_DRIFT__STANDARD_4H_RUNTIME_REUSES_WINDOW_15M_ONLY_TERMINAL_ACCEPTANCE_MODEL`

The attempt's final acceptance report independently failed multiple checks even beyond the direct close failure:

- `exactly_two_terminal_window_15m_lifecycles = false`
- `both_windows_campaign_owned = false`
- `scheduler_ownership_correspondence_exact = false`
- `complete_scheduler_family_attribution = false`
- `canonical_report_complete = false`
- `persisted_slot_dispositions_exact = false`
- `no_retry_restart_resume_successor = false`

Static inspection shows `campaign_full_run_accounting.py` still identifies itself as the full-run `WINDOW_15M` accounting/terminal-evidence contract and hardcodes mandatory lifecycle stages as:

- `DISCOVERY_SELECTION_SCHEDULER`
- `WINDOW_15M_SLOT_1`
- `WINDOW_15M_SLOT_2`
- `CAMPAIGN_TERMINAL_RECONCILIATION`

The fifth attempt lawfully owned additional `WINDOW_1H` and `WINDOW_4H` Scheduler work. The report's Scheduler correspondence treated jobs `1750` through `1837` as extra ownership while those jobs were attributable campaign continuation work. Therefore the reporting/acceptance model is not yet a truthful standard-four-hour model.

The `no_retry_restart_resume_successor` check also reported false because `scheduler_retry_count = 2` even though durable cleanup truth showed:

- automatic retry count `0`
- restart count `0`
- resume count `0`
- successor count `0`
- `restart_created = false`
- `resume_created = false`
- `successor_created = false`

This discrepancy must be audited in the design lane rather than normalized away. A Scheduler terminal-failure accounting field must not be silently equated with an operational retry if no retry occurred.

## Memory/corpus result

The fifth attempt did not produce a valid clean `WINDOW_4H` memory closeout.

The two prior `WINDOW_15M` and `WINDOW_1H` paths remained represented by durable memory rows, but both campaign `WINDOW_4H` rows ended `BLOCKED` with `memory_window_row_id = null` because the final closes failed.

`clean_memory_outcome_pass = false` must therefore remain honest. No retrieval or paper-decision eligibility is unlocked by this run.

## Money-usefulness contribution

This audit protects future money-useful memory growth by distinguishing a successful four-hour collection stream from a failed four-hour close and by identifying the exact code/contract boundaries that prevented durable 4h memory. Repairing these boundaries is necessary before longer-horizon memory can be trusted for any later approved retrieval or paper-decision work. It makes no profitability claim and unlocks no trading capability.

## What this lane improves

- establishes the exact fifth-attempt root cause instead of treating exit `0` as success;
- proves both 4h streams reached their final close before the deterministic blocker;
- separates runtime close-authority failure from terminal-report/acceptance drift;
- preserves the fifth authorization as permanently consumed;
- confirms cleanup, lease release, and downstream locks remained intact;
- prevents another scarce authorization from being consumed before deterministic repair/proof.

## What this lane still does not unlock

- no sixth authorization;
- no standard-four-hour rerun;
- no source fetching or runtime;
- no `WINDOW_12H` or `WINDOW_24H`;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL;
- no wallet/private key/signing/real funds/live execution;
- no paid APIs;
- no scoring/ranking/confidence/weighted systems;
- no embeddings/vectors.

## Required next lane

`V2-9.8B Fifth Standard-Four-Hour Close Authority and Terminal Acceptance Repair Design`

Design only. No implementation yet.

The design must separately specify:

1. how standard-campaign `WINDOW_4H` close obtains the same explicit enabled-successor authority that planning already lawfully uses, without weakening default long-window safety;
2. how terminal accounting/acceptance becomes standard-four-hour-aware for owned 15m -> 1h -> 4h Scheduler/window families;
3. how retry/restart/resume/successor truth distinguishes actual operational retries from terminal failure accounting;
4. which acceptance failures are direct derivatives of the failed 4h close versus independent report-contract defects;
5. minimum focused TDD proof and nearest regressions;
6. proof that `WINDOW_12H`/`WINDOW_24H`, retrieval, decisions, and trading remain locked.

After design approval, the normal sequence remains implementation -> bounded offline proof -> closeout -> rereadiness -> only then consideration of any fresh authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- Fifth authorization is permanently consumed and cannot be reused.
- A four-hour live run was spent discovering a deterministic final-close defect; do not spend another authorization before offline proof closes.
- Simply passing `allow_enabled_successor_planning=True` everywhere would weaken long-window safety and is not approved.
- Repairing only the close defect may still leave standard-four-hour terminal acceptance falsely blocked by the 15m-only reporting contract.
- Broad regression is unnecessary during narrow implementation; use focused affected tests plus nearest standard-4h/terminal-accounting regressions. Reserve broad/full proof for the repair closeout/pre-live boundary.
- Existing attempt evidence must remain preserved and read-only.
