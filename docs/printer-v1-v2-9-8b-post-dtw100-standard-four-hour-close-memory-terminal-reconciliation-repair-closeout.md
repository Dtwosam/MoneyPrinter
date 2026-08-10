# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Close / Memory / Terminal-Reconciliation Repair Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CLOSE_MEMORY_TERMINAL_RECONCILIATION_REPAIR_PASS`

The standard two-token `WINDOW_4H` close/memory/campaign-terminal composition is implemented and independently re-proven on the exact durable production commit.

The repair reuses the existing physical 4h close, shared context, E2Q, Lane Q, E2Z and clean-object owners. It adds the missing full-path 4h outcome boundary, successful campaign memory binding/terminal reconciliation, and standard two-window campaign terminal validation without enabling real 4h collection.

This PASS is offline/proof-bounded only. It does not authorize operational `WINDOW_4H` collection, source fetching, fresh authorization, 12h/24h, retrieval, decisions, positions, PnL, wallets, signing, execution or real funds.

## Durable anchors

Final corrected RED baseline:

`0fc4121e972c568845b6c66975c015d96aa4985b` — `Align one-token four-hour replay with outcome boundary`

Production implementation:

`51a9cf3649420577503bcc7678e94f666733eb25` — `Repair standard four-hour close memory terminal reconciliation`

Production diff from final RED:

- exactly one commit ahead;
- exactly two approved production files changed;
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — 495 additions / 1 deletion;
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` — 171 additions;
- no schema/migration change;
- no source/provider change;
- no cadence activation or budget expansion;
- no workflow/test/doc file in the production commit.

## Audit / design sequence

Controlling records:

- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-close-memory-terminal-reconciliation-audit.md`;
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-close-memory-terminal-reconciliation-repair-design.md`;
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-outcome-promotion-supplemental-audit.md`;
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-close-memory-terminal-reconciliation-repair-design-amendment.md`.

The initial audit proved that the physical one-token 4h close, shared 4h context, E2Q, Lane Q and E2Z were already reusable. The missing boundary was campaign composition after a successful physical 4h close plus a standard two-token terminal validator.

Focused RED then exposed an additional same-lane prerequisite: the physical 4h row reached E2Z without a persisted outcome label. The clean-object owner correctly refused to create clean memory when outcome was missing/unknown. That gate was preserved rather than weakened.

The design was therefore amended to derive the full current-run `WINDOW_4H` outcome from exact main-lifecycle run-step evidence before E2Q/Lane Q/E2Z.

## RED evidence

Final RED workflow:

- PR #148, closed unmerged;
- run `31389388959`;
- job `93457216438`;
- exact head `0fc4121e972c568845b6c66975c015d96aa4985b`;
- exact-head compile PASS;
- 48 focused/directly affected tests executed;
- exactly 10 failures;
- all 10 reduced to the intentionally missing amended production behavior;
- prior B2 planning, 4h state/accounting/fairness, first-hour close/memory and other one-token 4h contracts remained healthy.

The accepted RED covered:

- missing exact full-path 4h outcome owner;
- missing successful 4h campaign binder;
- missing successful 4h terminal reconciler;
- missing standard two-window terminal validator;
- formerly historical one-token clean 4h creation/replay, now intentionally in scope because the amended path requires outcome-before-E2Z.

## Test-fixture corrections before GREEN

Two test-only corrections were made before production implementation and were re-RED-proven.

### Exact identity mismatch fixture

The focused mismatch test initially placed binder lookup inside a broad `assertRaises`, so the intentionally absent binder itself could satisfy the assertion. The fixture was corrected so binder existence is asserted first.

### Historical one-token 4h replay fixture

The old V2-8.1 test called the low-level physical close and quality gates directly, bypassing the now-explicit canonical outcome composition boundary. The V2-8.1 closeout was reviewed and confirmed its product contract was the composed one-command path, not a promise that raw E2Z derives outcomes itself.

Commit `0fc4121e972c568845b6c66975c015d96aa4985b` therefore aligned that regression with the canonical architecture: derive/persist exact full-path 4h outcome before quality/promotion, while preserving the original expected behavior — first clean promotion succeeds and exact replay is idempotent.

No production behavior was changed by those test corrections.

## Implementation completed

### Full current-run 4h outcome boundary

`_derive_and_persist_four_hour_outcome` now:

- requires the exact physical `WINDOW_4H` token/pair identity;
- derives inclusion from current-run main-lifecycle run-step ownership, not a broad timestamp query;
- includes successful `SNAPSHOT`, `WINDOW_CLOSE`, `CONTINUATION_SNAPSHOT`, `CONTINUATION_CLOSE`, `LONG_CONTINUATION_SNAPSHOT`, plus the current long-close snapshot;
- de-duplicates exact snapshot IDs;
- loads them chronologically by `captured_at,id`;
- fails closed on missing/foreign token/pair/current-close identity;
- uses the existing categorical `classify_episode_outcome('WINDOW_4H', ...)` owner;
- persists the exact outcome, including truthful `OUTCOME_UNKNOWN` when applicable;
- persists full-path snapshot/provenance metadata.

No new outcome vocabulary, scoring, ranking, confidence or weighting was introduced.

### Outcome-before-E2Z ordering

After physical 4h close and shared-context persistence, `_execute_long_4h_step` now derives/persists the full-path 4h outcome and commits those prerequisite facts before the separately connected E2Q/Lane-Q/E2Z owners run.

The existing clean-object outcome gate remains unchanged. `OUTCOME_UNKNOWN` therefore remains non-promotable rather than being coerced into clean memory.

### Authoritative 4h clean-object classification

The factory now validates one exact complete `WINDOW_4H_CLEAN_MEMORY` episode/fingerprint pair against the physical memory row, token, pair and window kind.

Campaign success classification is categorical:

- exact complete clean object + `E2Z_MEMORY_CREATED` -> `CLEAN_PROMOTED`;
- exact complete clean object + `E2Z_ALREADY_EXISTS` -> `ALREADY_EXISTS_IDEMPOTENT`;
- dirty/audit/do-not-train/non-clean physical result without a clean object -> `DIRTY`;
- clean physical candidate without a complete clean object -> `NO_PROMOTION`.

A complete clean object with missing/conflicting E2Z event identity fails closed.

### Successful 4h campaign reconciliation

`reconcile_4h_terminal_lifecycle` now handles successful campaign outcomes while preserving caller transaction ownership.

Fresh success requires:

- exact campaign `WINDOW_4H`;
- exact campaign slot/token/pair identity;
- exact physical `WINDOW_4H` memory identity;
- campaign window `CLOSE_PENDING`;
- token slot `WINDOW_4H_CONTINUING`;
- no conflicting first terminal cause;
- no conflicting memory binding.

Under a SAVEPOINT/caller-owned transaction it:

1. binds the physical memory row;
2. moves `CLOSE_PENDING -> AUDITING`;
3. moves `AUDITING ->` the exact successful terminal state;
4. moves the token slot `WINDOW_4H_CONTINUING -> WINDOW_4H_CLOSED`;
5. read-backs exact identity/state/cause.

Exact replay is idempotent. Conflicting state, cause or memory identity fails closed. The reconciler never commits the caller's outer transaction.

### Scheduler-success ordering

For `LONG_CONTINUATION_CLOSE`, the main factory now binds and reconciles the exact campaign 4h lifecycle before canonical Scheduler success is committed.

A campaign binding/reconciliation failure therefore cannot be hidden behind a Scheduler `SUCCEEDED` state.

### Standard two-window terminal validator

The new standard campaign validator activates only for the exact B2 `WINDOW_4H` campaign set. Historical one-token terminal validation remains unchanged when standard ownership is absent.

For each standard token independently it validates:

- exact stage-scoped Scheduler ownership;
- exact token/pair/window identity;
- one tracking lane;
- that lane's own policy-derived expected 4h snapshot count;
- exactly one owned long close;
- run-step, Scheduler and campaign-work success;
- exact bound physical 4h memory;
- campaign terminal-state/physical-memory consistency;
- token slot `WINDOW_4H_CLOSED`.

At campaign level it requires:

- exactly two standard 4h windows;
- distinct slots/tokens;
- zero active owned 4h Scheduler work;
- zero nonterminal campaign 4h windows.

Mixed FAST/NORMAL campaigns therefore use different per-token cadence expectations correctly. No aggregate score is created.

## GREEN apply proof

Production apply workflow:

- PR #149, closed unmerged;
- run `31389648700`;
- job `93458049837`;
- exact final RED parent verified;
- exact two-file production scope verified;
- `git diff --check` PASS;
- compile PASS;
- 48/48 focused/directly affected tests PASS;
- first-hour outcome/memory regressions PASS;
- historical one-token 4h clean create/replay PASS;
- real 4h/12h/24h capability locks PASS;
- production commit/push PASS.

## Independent exact-head proof

Read-only proof:

- PR #150, closed unmerged;
- run `31389998534`;
- job `93459196241`;
- checkout explicitly bound to `51a9cf3649420577503bcc7678e94f666733eb25`;
- Python 3.12.13;
- compile PASS;
- 48/48 tests PASS in 36.216 seconds;
- `git diff --check` PASS;
- real `WINDOW_4H` collection remains disabled for FAST and NORMAL;
- `WINDOW_12H` and `WINDOW_24H` remain disabled.

The exact-head suite included:

- amended standard 4h close/memory/terminal tests;
- B2 standard 4h planning/handoff;
- previous 4h collection state/accounting/fairness;
- first-hour Checkpoint-4 close boundary;
- first-hour Checkpoint-5 full-path outcome/memory construction;
- historical one-token 4h runtime/create/replay.

## Money-usefulness contribution

Printer can now carry each standard 4h token from exact physical evidence to truthful campaign terminal state without confusing lifecycle completion with clean-memory acceptance.

A clean 4h memory is counted only when its complete clean object and known observed outcome exist. Dirty evidence remains negative/audit evidence rather than fake clean memory. Clean-but-unpromoted/unknown outcomes remain explicitly no-promotion. Mixed FAST/NORMAL tokens are independently reconciled and validated.

This improves future long-horizon corpus accuracy for delayed collapse, survival, revival, distribution, round trips and liquidity deterioration. It proves no profitability and creates no decision or trading authority.

## What this checkpoint improves

- closes the successful 4h campaign binding gap;
- makes first clean 4h promotion and exact replay reachable under current clean-object law;
- preserves full-path outcome provenance rather than classifying only the long suffix;
- prevents foreign/historical snapshots entering 4h outcome derivation;
- prevents Scheduler success from outrunning campaign truth;
- makes mixed-lane two-token 4h terminal validation exact;
- preserves historical one-token and first-hour owners.

## What remains locked / incomplete

Still locked:

- real `WINDOW_4H` collection;
- operational standard-4h rereadiness;
- activation repair/proof;
- fresh exact-HEAD one-use operational authorization;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, audits, PnL;
- wallets, private keys, signing, live execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

No 12h successor is created by this repair.

## Functionality Risks / Setbacks / Efficiency Blockers

- The canonical factory remains large; do not use this PASS as justification for unrelated refactoring.
- Full-path outcome derivation depends on exact run-step identity. Any later run-ledger redesign must preserve that inclusion authority or redesign this contract explicitly.
- E2Q/Lane-Q/E2Z use separate committed DB operations. Campaign reconciliation cannot roll back already-durable physical memory facts and must continue to report them honestly on later campaign failure.
- `OUTCOME_UNKNOWN` can legitimately prevent clean promotion; this is a money-usefulness safeguard, not a test failure to bypass.
- The standard validator is intentionally separate from the historical one-token validator. Partial/ambiguous B2 ownership must fail closed rather than silently fall back.
- Two simultaneous 4h lifecycles remain materially more expensive than the historical one-continuer proof; operational ceilings and safe-stop behavior still require later rereadiness.
- GitHub Actions emitted Node runtime deprecation warnings for action internals. They did not affect Printer code/tests and are not a production blocker.

## Next permitted step

Do **not** activate or run real 4h collection from this closeout alone.

Reconcile the full adopted Standard Four-Hour Campaign Integration Implementation contract across the already-passed sub-slices and determine whether any integration/proof obligation remains before the required overall implementation/proof closeout.

Only after the full implementation/proof closeout passes may a separate **operational standard-four-hour rereadiness** review begin. Real collection remains locked until the later separately approved activation repair/proof and fresh exact-HEAD one-use authorization/review sequence.
