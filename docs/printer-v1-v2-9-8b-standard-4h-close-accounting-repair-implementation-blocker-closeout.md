# Printer V1 V2-9.8B Standard-4h Close/Accounting Repair — Implementation Execution Blocker Closeout

## Baseline and lane

- Root-cause audit baseline: `300010e2ea6b3edff777c7dfb43c55ef23b4871e`.
- Repair design commit: `0c0087f769985d00e8b5238e563582614bde9f04`.
- Test-first RED contract commit: `034b34ac176e094ee08dfdfba81c21f46bd57d95`.
- Branch: `agent/v2-9-8b-standard-4h-close-accounting-repair`.
- Fifth standard-4h authorization remains permanently consumed.

## Verdict

`V2_9_8B_STANDARD_4H_CLOSE_ACCOUNTING_REPAIR_IMPLEMENTATION_BLOCKED_TOOLING_NO_FALSE_GREEN`

The design is complete and focused RED tests are durably present, but production implementation and a real RED->GREEN repository test execution are not complete in this session.

## Failure classification

This is **not** a Printer runtime/source/memory blocker and is **not** evidence that either proposed repair is invalid.

It is an implementation-environment/tooling blocker:

1. the connected GitHub surface permits repository reads, branch/commit creation, file creation and whole-file replacement;
2. it does not expose a safe in-place source patch action;
3. the active session has no checked-out MoneyPrinter worktree and no authenticated repository-native shell/test runner;
4. the repository branch does not expose a GitHub Actions workflow that can be dispatched to execute the focused tests; and
5. direct unauthenticated/network materialization of the repository is unavailable from the execution container.

Using wrapper modules or replacing safety-critical owners solely to work around the connector would introduce unnecessary architectural indirection and was rejected.

## Work completed

### Design

The approved design keeps the two defect families separate:

- Defect A: propagate explicit `FourHourExecutionAuthority` into final `LONG_CONTINUATION_CLOSE`, with the existing resolver remaining fail-closed globally.
- Defect B: keep 15m source/six-unit accounting intact while adding standard-campaign-aware exact Scheduler correspondence for authorized 15m->1h->4h work.

The design also preserves campaign automatic-retry truth separately from Scheduler retry bookkeeping and keeps wrapper command completion separate from campaign/proof success.

### Test-first contract

Focused tests were added before production changes for:

- explicit STANDARD_CAMPAIGN close authority reaching enabled-successor resolution;
- missing close authority failing before resolution;
- exact standard 15m->1h->4h Scheduler correspondence;
- unexplained extra work failing closed;
- ordinary 15m correspondence remaining narrow;
- standard lifecycle attribution using an exact expected count rather than hard-coded 18;
- ordinary 15m retaining the historical 18-job contract; and
- Scheduler retry history not being misreported as a campaign automatic retry.

The RED commit is structurally RED because it imports the planned repair helpers/signature that do not exist in the preceding production baseline. No claim is made that pytest was executed for that commit.

## Production code changed

None.

This is intentional. No safety-critical core file was rewritten through a workaround merely to claim implementation progress.

## Verification performed

Read-only/static verification confirmed:

- standard 4h planning already validates `FourHourExecutionAuthority.STANDARD_CAMPAIGN` and explicitly allows enabled successor planning during plan composition;
- `close_current_run_4h()` does not currently receive or carry that authority and therefore reaches the resolver with its fail-closed default;
- full-run accounting currently forms `lifecycle_steps` from only `SNAPSHOT`/`WINDOW_CLOSE` but compares that set to all campaign-owned `WINDOW_LIFECYCLE` Scheduler ownership;
- terminal acceptance also contains a 15m-specific `lifecycle == 18` attribution assumption; and
- Scheduler `retry_count` is currently included in `no_retry_restart_resume_successor` even when campaign automatic retry count is zero.

No source fetching, runtime, memory generation, database mutation, campaign execution, or authorization preparation was performed.

## Required production implementation once a repository-native patch/test surface is available

### Defect A

1. Add explicit `execution_authority` to `close_current_run_4h()` with fail-closed parsing.
2. Permit enabled WINDOW_4H successor resolution only for an explicit valid 4h authority.
3. Carry the correct existing authority through the exact standard/proof execution caller; do not infer an unrestricted boolean.
4. Update existing proof tests to supply `PROOF` explicitly where appropriate.
5. Keep the global resolver default unchanged and keep 12h/24h locked.

### Defect B

1. Add a separate terminal Scheduler-correspondence loader that preserves existing 15m source/sealing accounting.
2. For standard campaigns, include only exact joined 1h/4h campaign-window/Scheduler lineage; continue comparing against all owned lifecycle work so unexplained rows remain extra.
3. Make lifecycle Scheduler attribution compare to the exact expected standard lineage count, retaining the historical 18 fallback for ordinary 15m.
4. Keep Scheduler retry count observable but remove it from the campaign-level automatic-retry/restart/resume/successor predicate.
5. Preserve runtime-terminal completion as an independent requirement so child exit 0 cannot fabricate success.

## Minimum proof still required

A real repository-native focused RED->GREEN run must cover the new repair test file plus only directly affected existing tests. No broad regression suite is justified yet.

Until that focused run is green, implementation closeout cannot PASS.

## Money-usefulness contribution

The design and test contract reduce the risk of wasting another four-hour evidence collection on the same deterministic close/accounting defects. They do not yet deliver the operational benefit because production implementation is not complete.

## What this improves

- Durable, reviewable repair specification.
- Test-first safety contract before code changes.
- Clear distinction between code defects and tooling limitations.
- Prevents a false-green branch from advancing to authorization.

## What this still does not unlock

No fresh standard-4h authorization, no standard-4h rerun, no 12h/24h, no retrieval, no paper decisions, no BUY/SELL/HOLD, no positions/trade events/audits/PnL, no live wallet, no private keys, no real funds, no live execution, no paid APIs, no scoring/ranking/confidence/weighted systems, and no embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Primary blocker:** no repository-native safe patch + focused test execution surface in this session.
- **Risk avoided:** architectural wrapper/monkey-patch indirection around safety-critical owners.
- **Risk remaining:** the defects remain in production code until the approved implementation is applied and tested.
- **Efficiency rule:** do not spend another four-hour authorization attempting to prove code that has not passed the focused repair tests.

## Stop condition

Stop here. Do not prepare a sixth authorization and do not run another standard-4h campaign. Resume only from production implementation of the approved design on a repository-native worktree/test surface, then perform focused proof, implementation closeout, and a fresh post-repair rereadiness review.