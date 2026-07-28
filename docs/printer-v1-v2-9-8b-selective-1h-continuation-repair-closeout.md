# Printer V1 V2-9.8B Selective-1h Continuation Repair Closeout

Verdict: `V2_9_8B_SELECTIVE_1H_CONTINUATION_REPAIR_PASS`

## Starting baseline

- Branch: `master`
- Required and observed starting HEAD: `cfbae1f8075b6bc0674f9cf728a15a5f7b6103ad`
- Starting worktree: clean
- Authoritative database: `data/printer_v1.sqlite3`
- Authoritative database SHA-256 before: `d4f22680fa9358ab3a61dff4968839a7ae3bf0acdccd44d27850bcb71263ea56`

The design was completed and statically validated before Python or test changes. No live source, discovery, Scheduler, campaign, lifecycle, memory-generation, or selective-1h proof command ran.

## Changed files

- `docs/printer-v1-v2-9-8b-selective-1h-continuation-repair-design.md`
- `src/printer_v1/operator_cli/campaign_authority_adapters.py`
- `src/printer_v1/operator_cli/operational_selective_1h.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_8b_operational_selective_1h.py`
- `docs/printer-v1-v2-9-8b-selective-1h-continuation-repair-closeout.md`

## Root causes repaired

### Exact safety linkage

The evaluator no longer performs a latest-composite query by `memory_window_id`. One canonical read-only resolver now starts from the exact `safety_composite_id` retained in the authoritative memory window's `memory_build_evidence_overlays` context.

The resolver loads only that composite and validates exact token, mint, pair, closing snapshot, target, optional non-null window lineage, checkpoint freshness, contribution request/response/failure trace, provenance completeness, blockers, conflicts, and the unchanged safety predicate. Missing, stale, mismatched, invalid, blocked, conflicted, or untraceable evidence fails closed. A real-producer composite with `memory_window_id=NULL` is accepted only through the exact window-retained ID and all other checks.

The raw `SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY` label and optional unknown fields remain unchanged. It supports continuation only when the existing effective projection is `SAFETY_CONTEXT_ACCEPTABLE`; no unknown field is relabelled safe.

### Evaluation order and owner

Selective evaluation and scheduling were removed from the current token's still-`RUNNING` close body. The one-command bounded factory remains the canonical campaign-wide barrier owner, but it now admits only `SUCCEEDED` starting-token `WINDOW_CLOSE` steps with exact memory-window linkage.

The successful close step and Scheduler job are committed first. The post-success barrier then checks the complete activated close set, requires every B.1 outcome to resolve, evaluates the whole campaign once, and schedules the resulting token-local plans. The first close defers without polling or work. The final authoritative close releases the barrier. Close arrival order no longer changes eligibility.

An episode existing while its current close step remains `RUNNING` is explicitly insufficient. No still-running close reaches selective evaluation.

### Immutable continuation idempotency

The evaluator computes the candidate decision set before continuation side effects and inspects the campaign's existing `CONTINUATION_4A` set.

- An exact complete persisted set is returned unchanged.
- A partial or foreign set fails closed.
- Any candidate/persisted payload conflict fails closed.
- BLOCK cannot become CONTINUE and CONTINUE cannot become BLOCK.
- Repeated invocation creates no campaign window and triggers no scheduling.
- First authoritative evaluation ownership is preserved.
- Deterministic window, step, and Scheduler identities remain additional duplicate defenses.

No ad hoc second evaluation was added to repair the earlier ordering defect.

### Campaign-window states

Authoritative predecessor outcomes are now terminally reconciled from `AUDITING`:

- `CLEAN_PROMOTED` -> `CLEAN_PROMOTED`
- `ALREADY_EXISTS_IDEMPOTENT` -> `CLEAN_PROMOTED`
- closed dirty/do-not-train evidence -> `DIRTY`
- `DIRTY_OR_BLOCKED` without dirty memory, or an authority/evidence blocker -> `BLOCKED`
- resolved clean close with no promotion -> `NO_PROMOTION`
- genuine cancellation remains `CANCELLED`

A completed 15m predecessor is therefore not cancelled because 1h continuation stops or blocks. The continuation verdict remains in `CONTINUATION_4A` and reporting.

### Terminal reporting

Canonical campaign report construction now accepts a read-only selective-1h projection. The operational terminal owner supplies it for authorized or reached selective campaigns, and report-only replay returns the same persisted canonical payload without source or Scheduler work.

The projection includes token plans, per-token verdicts/reasons, continue/block/stop counts, window counts by kind and state, actual persisted `WINDOW_1H` count, explicit zero-continuation truth, locked downstream capabilities, and false restart/successor flags.

The secondary categorical field is `selective_1h_outcome` and emits exactly one of:

- `ZERO_ELIGIBLE_CONTINUATIONS`
- `ONE_CONTINUATION`
- `TWO_CONTINUATIONS`
- `EVALUATION_BLOCKED_SYSTEM_DEFECT`
- `EVALUATION_NOT_REACHED`

An incomplete decision set or mismatch between CONTINUE count and actual persisted 1h windows is a system defect. The primary campaign terminal cause remains unchanged, so normal completion and selective continuation truth are both represented without claiming that zero continuation is a successful 1h proof.

## Scheduler and lifecycle behavior

The repaired barrier delegates each new token plan to the existing selective continuation scheduler adapter. STOP/BLOCK plans enqueue nothing; CONTINUE plans retain exact predecessor, token, pair, campaign, and run linkage and use Central Scheduler ownership. Offline proof covers zero, one, and two continuation decisions plus repeated barrier entry with no second scheduling call.

No 4h, 12h, 24h, retrieval, paper-decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, or funds path was added or enabled.

## Focused offline proof

All proof used temporary migrated SQLite databases, fixtures, and mocks.

- Focused selective-1h repair suite: 31 tests passed.
- Combined focused plus nearest affected adapter/reporting regressions: 56 tests passed.
- Python compilation passed for all changed Python/test files.
- `git diff --check` passed.
- Static invariant scan found no migration or unrelated discovery/retrieval change; locked-window mentions are reporting-only and restart remains explicitly false.

Coverage includes:

- accepted producer composite with null window linkage and exact context ID;
- wrong ID/token/pair/snapshot/window, stale, incomplete-provenance, blocked, conflicted, and untraceable evidence;
- unchanged effective safety acceptance with raw unknown labels preserved;
- token 1 then token 2 and token 2 then token 1 close arrival;
- delayed close with both episodes already present;
- no evaluation before all required closes are `SUCCEEDED`;
- zero, one, and two eligible continuations;
- exact immutable replay, partial object set, and conflicting recomputation;
- no duplicate 1h windows or repeated scheduling;
- clean, already-existing, dirty, blocked, no-promotion, and genuine cancellation states;
- truthful canonical zero-continuation report and zero-source replay;
- no retry, restart, successor, 4h+, retrieval, or paper/financial delta.

One separately attempted historical integration suite produced 9 passes and one unrelated pre-existing failure. `test_completed_slice_6_components_work_together` hard-codes migration `035_insufficient_pool_cycle_terminal_trigger.sql` as the latest migration, while the required baseline already contains committed migration `047_campaign_oneshot_linkage_binds.sql`. The assertion is unchanged at baseline HEAD, this repair adds no migration, and the failure does not affect the repaired owners.

## Migration and authoritative data status

- Migration added: no
- Migration applied: no
- Historical authoritative rows rewritten: no
- Failed-proof artifacts changed: no
- Authoritative database SHA-256 after: `d4f22680fa9358ab3a61dff4968839a7ae3bf0acdccd44d27850bcb71263ea56`
- Before/after equality: yes

## Money-usefulness contribution

This repair makes the selective clean-memory growth funnel evidence-faithful. Valid exact safety evidence is no longer discarded because of producer timing, tokens are compared only after authoritative predecessor completion, immutable decisions cannot drift, predecessor completion is represented honestly, and operators can distinguish campaign completion from actual 1h continuation. It creates no trade, position, financial action, or profit claim.

## What remains locked

- another live selective-1h proof;
- normal-production 1h activation;
- 4h/12h/24h activation;
- retrieval;
- paper decisions and BUY/SELL/HOLD;
- positions, trades, paper audits, and PnL;
- wallets, keys, signing, execution, and real funds;
- retries, restarts, resumes, or successor campaigns;
- stale fallback or relaxed safety admission;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

## Rollback

Revert the single repair commit. No database, migration, or historical-artifact rollback is required.

## Proof required before later operational action

This PASS authorizes only a fresh read-only selective-1h operator-readiness review. That review must confirm the committed hash, clean worktree, authoritative database hash, exact command/configuration, evidence freshness requirements, Scheduler/source ceilings, report destinations, and all capability locks. Any later live proof still requires separate explicit operator approval; this closeout does not authorize it.

## Functionality Risks / Setbacks / Efficiency Blockers

- Older memory windows without an exact retained composite ID intentionally fail closed.
- Immutable partial persistence or conflicting recomputation intentionally requires a separately approved recovery/repair lane; it is never silently re-evaluated.
- Scheduler failure after immutable CONTINUE ownership remains a terminal operational defect rather than a retry trigger.
- The barrier relies on exact activated close-step enumeration; order and delayed-arrival behavior are offline-proven, but a later separately approved live proof is still needed for operational composition evidence.
- The historical migration-sentinel test remains stale and should be repaired in a separate test-maintenance lane only if requested.

## Exact next permitted lane

Fresh read-only selective-1h operator-readiness review. No live proof is authorized.
