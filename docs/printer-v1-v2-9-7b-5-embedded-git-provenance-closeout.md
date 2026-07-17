# Printer V1 V2-9.7B.5 Embedded Git Provenance Closeout

## Verdict

`V2_9_7B_5_EMBEDDED_GIT_PROVENANCE_PASS`

V2-9.7B.5 passes. Printer now captures one minimal, immutable Git provenance
payload before run execution; rejects unavailable, unverifiable, malformed, or
tracked-dirty Git state; stores the payload in the existing run configuration
JSON; and carries the exact same payload through supervision, launcher
artifacts, final reporting, and report-only replay. No migration or historical
row rewrite was required.

Untracked files are represented only by a boolean and do not make the tracked
tree dirty. Detached HEAD is valid. Git calls use argument arrays, no shell,
fixed five-second ceilings, and no branch dependency. No source payload, file
name, credential, environment secret, or diff is retained.

## Todo / Checklist

- [x] Verify exact HEAD, initial tracked cleanliness, inactive proof lock/runtime,
  persistent DB hash, and preservation of unrelated untracked artifacts.
- [x] Inspect run configuration, migration 028, final reporting, launcher
  artifacts, supervision, report-only replay, and existing helper boundaries.
- [x] Implement bounded launch-time capture, fail-closed validation, and
  migration-free JSON persistence.
- [x] Prove Git-state classification and immutable run/report/replay propagation.
- [x] Run focused and nearest regressions, compilation, PowerShell parsing,
  persistent DB comparison, accidental-unlock scan, scope review, and diff checks.

## Preflight And Scope

- Starting HEAD: exact `62ae4695b04f0bf7cb68eae4075615fb02385a71`.
- Tracked tree: clean before lane edits.
- One-proof lock: absent at preflight and after verification.
- Runtime: no active Python proof process was present.
- Persistent DB: `data/printer_v1.sqlite3`, SHA-256
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
- Unrelated untracked artifacts were not edited, staged, removed, or treated as
  tracked-tree dirtiness.
- No real proof, source request, runtime, or persistent DB operation was started.

## Implementation

### Reusable Capture And Validation

`git_provenance.py` captures and validates exactly:

- `git_head`
- `git_tracked_tree_clean`
- `git_staged_changes_present`
- `git_unstaged_changes_present`
- `git_untracked_present`
- `git_provenance_captured_at`

The helper verifies `HEAD^{commit}`, staged tracked changes, unstaged tracked
changes, and untracked presence with four bounded `subprocess.run()` calls using
`shell=False`. The full 40- or 64-hex commit object ID is accepted, so detached
HEAD works without branch inspection. Staged or unstaged tracked changes,
missing Git, timeout, nonzero or malformed command results, an unverifiable
HEAD, inconsistent fields, or a naive timestamp fail closed.

The payload stores no untracked names and no diff content. Its fixed field set
also prevents callers from adding source data, secrets, or environment content.

### Run, Launcher, And Report Propagation

The one-command factory captures provenance before importing or invoking source
execution and before creating a run-ledger row. Supervised execution receives
the launcher's already-captured payload, validates it, and passes that exact
object into the factory rather than recomputing it in the child.

The existing migration-028 `config_json` field stores launch provenance without
schema change. `_final_report()` validates and exposes the same payload at the
report top level while retaining it inside `config`. `load_report_only()` remains
read-only, loads the stored terminal report, and never calls Git or replaces the
launch value.

The V2-9 PowerShell launcher captures provenance before preparation, proof DB
creation, network preflight, or child start. It records the payload in
`LAUNCHER_START`, sends compact JSON to the supervised child, and includes the
same value in the terminal launcher artifact. Existing B.4 heartbeat, first
cause, cleanup, and no-restart behavior is unchanged.

## Verification Results

Focused V2-9.7B.5 tests:

- 7 passed.
- A clean temporary repository produced its exact full HEAD SHA.
- Staged and unstaged tracked changes failed closed.
- Untracked-only state remained tracked-clean and was recorded separately.
- Detached HEAD succeeded.
- Missing Git, an unverifiable repository HEAD, timeout, and malformed HEAD
  output failed closed.
- Run `config_json`, final report, and report-only replay contained identical
  launch provenance.
- Replay made zero source calls, wrote zero evidence, did not rewrite stored
  configuration or report JSON, and did not recapture Git state.
- The isolated verification DB contained zero source, snapshot, memory-window,
  episode, retrieval, decision, position, trade-event, trade-audit, and paper
  audit-report rows.

Nearest regressions:

- 72 passed, including 12 subtests.
- Coverage included the V2-4 one-command factory, V2-5 two/three-token isolation,
  V2-9.7B.1 authoritative promotion reporting, B.2 timeframe-aware safety
  reporting, B.3 tracking/lifecycle reconciliation, B.4 heartbeat/lease
  reliability, durable supervision/cleanup, launcher bootstrap, and launcher
  logging reliability.

Static checks:

- Python compilation passed for all changed Python sources and tests.
- Windows PowerShell parse check passed for `Start-V2-9-Proof.ps1`.
- Accidental-unlock scan found no capability unlock or forbidden-write addition.
- Persistent DB post-check hash remained
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
- `git diff --check` passed; Git emitted only existing line-ending normalization
  notices for the two updated factory regression files.

## Money-Usefulness Contribution

Immutable launch provenance makes every bounded memory result traceable to the
exact code revision that produced it. That reduces false comparison between
campaigns, makes regressions attributable, and protects later corpus-quality
reviews from mixing evidence produced by unknown or locally modified code. The
separate untracked indicator preserves operational honesty without discarding a
valid run merely because unrelated operator artifacts exist.

## What This Lane Improves

- Adds exact, reusable launch-time code identity without a migration.
- Distinguishes staged, unstaged, and untracked repository state.
- Prevents tracked-dirty or unverifiable code from starting execution.
- Preserves one provenance payload across launcher, child, run ledger, final
  report, and report-only replay.
- Supports detached HEAD and paths containing spaces.
- Keeps capture bounded, shell-safe, minimal, and free of diffs or secrets.

## What Remains Locked

- The operational campaign command and V2-9.7C/D/E, V2-9.8, and V2-10.
- Real operational memory growth and persistent corpus production.
- Source fetching outside an explicitly approved later command.
- Retrieval activation and dirty-memory use.
- Paper decisions, BUY, SELL, HOLD, positions, trades, audits, and PnL.
- Live execution, wallets, private keys, signing, real funds, and paid APIs.
- Scoring, ranking, confidence percentages, weighted logic, embeddings, and
  vectors.

## Completed Proof Requirements

- Exact full HEAD capture: complete.
- Staged and unstaged tracked-dirty refusal: complete.
- Untracked-only separation: complete.
- Detached HEAD support: complete.
- Git unavailable, repository/HEAD unverifiable, timeout, and malformed-output
  fail-closed behavior: complete.
- Identical run configuration, final report, and report-only provenance:
  complete.
- Replay zero-source and immutable provenance behavior: complete.
- B.1-B.4 and supervision/launcher compatibility: complete.
- Persistent DB isolation and zero forbidden capability mutation: complete.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Provenance deliberately describes tracked cleanliness and only the presence
   of untracked files. It does not preserve untracked names or content, so later
   forensic work must use separately governed artifacts when those details
   matter.
2. Each Git command has a fixed five-second ceiling. A severely degraded Git
   filesystem therefore blocks launch rather than waiting indefinitely.
3. Existing historical run rows are not rewritten and may lack provenance. This
   lane guarantees provenance for newly launched runs only.
4. The proof launcher remains proof-specific. This repair does not make it the
   future operational campaign supervisor or activation command.
5. The Windows restricted-token sandbox denied normal Python temporary-directory
   writes. Verification used PowerShell-created isolated directories without
   changing the test assertions or product paths.
6. The standard patch helper was blocked by the same split writable-root sandbox
   setup, so guarded exact file writes were used for this lane's scoped edits.

## Files Changed

- `src/printer_v1/operator_cli/git_provenance.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/proof_supervision.py`
- `scripts/Start-V2-9-Proof.ps1`
- `tests/test_v2_4_one_command_15m_factory.py`
- `tests/test_v2_5_multi_token_15m_conservative.py`
- `tests/test_v2_9_7b_5_embedded_git_provenance.py`
- `docs/printer-v1-v2-9-7b-5-embedded-git-provenance-closeout.md`

## What Was Built

A minimal, reusable, migration-free launch provenance boundary with fail-closed
Git verification and immutable propagation through run artifacts and reports.

## What Was Not Touched

No migration, schema, persistent database, source adapter, evidence collection,
memory promotion, reporting policy from B.1, safety acceptance from B.2,
tracking/lifecycle behavior from B.3, heartbeat/cleanup behavior from B.4,
continuation policy, 5m support-only behavior, retrieval, financial function, or
operational campaign command was changed.

## Tests / Checks Run

Focused provenance tests; nearest factory, multi-token, B.1-B.4, launcher,
supervision, and cleanup regressions; Python compilation; PowerShell parsing;
persistent DB hash comparison; accidental-unlock scan; scope inspection; and
`git diff --check`.

## Pass / Fail Status

PASS: `V2_9_7B_5_EMBEDDED_GIT_PROVENANCE_PASS`.

## Risks Or Concerns

The bounded Git preflight intentionally favors a safe stop over running with
ambiguous code identity. Historical reports remain untouched and therefore do
not gain retroactive provenance.

## Next Recommended Phase

Stop after this commit. Do not begin V2-9.7B closeout, V2-9.7C, or operational
memory growth automatically.