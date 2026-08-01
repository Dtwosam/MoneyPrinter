# Printer V1 V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Implementation

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Implementation`

Lane type: narrowly scoped implementation and focused static/unit verification only.

## Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_IMPLEMENTATION_PASS`

The approved corrected design was implemented exactly. A new fail-closed
manifest/marker validator converts an authorization-bound, out-of-repository
manifest and one-attempt marker into an exact repository-relative untracked-file
allowlist. That allowlist is combined only with the existing fixed SQLite sidecar
tuple and handed unchanged to `capture_git_provenance()`. No launch-time Git
safety rule was weakened, and the canonical six-field Git-provenance payload is
untouched.

This lane implements only code and focused tests. It does not run the bounded
disposable proof, authorize a campaign, contact providers, mutate the
authoritative database, generate memory, or unlock any retrieval or financial
capability.

## Controlling baseline

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-window-15m-provenance-compatibility-implementation` |
| Starting HEAD | `d4166010472d1e6504d2a9805e9d5e047116212b` |
| Approved design | `docs/printer-v1-v2-9-8b-window-15m-one-shot-wrapper-git-provenance-compatibility-design.md` |
| Design verdict | `V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_DESIGN_PASS` |
| Provenance-block audit | `V2_9_8B_WINDOW_15M_PRE_LIFECYCLE_GIT_PROVENANCE_BLOCK_AUDIT_PASS` |
| Consumed authorization (not reused) | `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Accepted post-050 DB SHA-256 (unchanged, not read) | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |

The tracked worktree was clean before editing. The two untracked
`operator-runs/` evidence packages were preserved exactly and were neither
moved, modified, deleted, nor ignored.

## Exact files changed

1. New: `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
   - `GitProvenanceAuthorizationError` (fail-closed error).
   - `ValidatedGitProvenanceAuthorization` (frozen immutable result with exact
     allowed-path tuple, authorization ID, manifest SHA-256, marker SHA-256,
     allowed-file-set SHA-256, file count, and a bounded `summary()`).
   - `compute_allowed_file_set_sha256()` (deterministic, order-independent
     canonical digest: records sorted by path, `sort_keys=True`,
     separators `(',', ':')`, ASCII-safe, no NaN).
   - `validate_git_provenance_authorization()` (the whole validation contract).
   - No network request, no database read or write, no file creation. Only reads
     the named files and runs read-only `git` plumbing (`rev-parse`,
     `diff --quiet`, `ls-files --others --exclude-standard -z`).

2. Modified: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
   (112 insertions, 8 deletions — preflight boundary only)
   - Imports the new validator module.
   - `GIT_PROVENANCE_MANIFEST_ENV_VARS` and
     `GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES` constants.
   - `_capture_operational_git_provenance()` now accepts
     `additional_allowed_untracked_paths` and combines them only with the fixed
     `AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS` tuple. Its fail-closed behavior and
     the canonical six-field payload are unchanged.
   - `_resolve_git_provenance_authorization(mode, environ, repository_root)`
     reads the four environment variables all-or-none, rejects partial
     configuration, rejects any unsupported mode, and validates via the new
     module (wrapping its error as a fail-closed operational error).
   - `build_activation_preflight()` gained an optional
     `git_provenance_authorization` parameter; when present it supplies the exact
     validated allowlist to the capture helper and exposes only the bounded
     `git_provenance_authorization` summary in preflight evidence (a separate key
     from the unchanged `git_provenance` object).
   - `_run_operational_campaign()` and `run_operational_campaign()` thread the
     authorization only into the ordinary-run preflight. Selective-1h never
     receives it.
   - `main()` resolves the authorization once, before dispatch, and passes it to
     `preflight-only` and `run` only.

3. New: `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`
   (48 focused tests, temp repositories and disposable fixtures only).

4. New (this document):
   `docs/printer-v1-v2-9-8b-window-15m-one-shot-wrapper-git-provenance-compatibility-implementation.md`

No other files were changed. `git_provenance.py` is semantically unchanged. No
`.gitignore`, `.git/info/exclude`, or global Git configuration was touched. No
migration, database, Source Governor, Central Scheduler, campaign, memory,
retrieval, or financial code was altered. No PowerShell parameter was added and
the public command shape is unchanged.

## Validation contract implemented

The validator enforces, fail-closed:

- external manifest path is absolute, outside the repository, a regular
  non-symlink file, with actual SHA-256 equal to the expected value;
- external application-marker path is absolute, outside the repository, a regular
  non-symlink file, with actual SHA-256 equal to the expected value;
- exact manifest and marker schemas with no extra keys and no duplicate JSON
  keys;
- referenced repository-local `final_authorization.json`: SHA-256 match,
  authorization ID match, PASS verdict, branch and HEAD equal to live Git state,
  ordinary `run` command, operator approval, allowed invocation count exactly 1,
  and all retry/rerun/resume/restart/successor flags false, plus `WINDOW_15M`
  main window and selective-1h continuation false;
- every manifest file under exactly one approved package root
  (`operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/…` or
  `operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/…`);
- repository-relative POSIX paths only — no absolute path, traversal, empty or
  `.` segment, trailing slash, glob character, backslash, duplicate, symlink
  component, or out-of-root entry;
- each file exists as a regular file with exact size and exact SHA-256;
- exact equality between the observed repository untracked set (fixed SQLite
  sidecars excluded, since they are separately controlled) and the manifest file
  set — a missing manifest file blocks and an extra observed file blocks;
- marker binding: manifest SHA-256, allowed-file-set SHA-256, authorization
  SHA-256, authorization ID, branch, HEAD, command, invocation count 1, and all
  false flags;
- tracked-tree cleanliness (staged and unstaged changes both block).

The returned immutable result exposes the exact allowed path tuple, authorization
ID, manifest SHA-256, marker SHA-256, allowed-file-set SHA-256, and file count.

## Focused tests and results

Command:
`.venv/bin/python -m pytest tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py -q`

Result: **48 passed**.

Regression check on the directly-touched boundary:
`.venv/bin/python -m pytest tests/test_v2_9_7b_5_embedded_git_provenance.py tests/test_v2_9_8a_public_operational_command.py -q`

Result: **22 passed**.

Coverage maps to the required focused items:

1. valid exact manifest and marker pass — `test_valid_manifest_and_marker_pass`;
2. no allowlist still detects repository evidence —
   `test_no_allowlist_detects_repository_evidence`;
3. unrelated untracked file blocks — `test_unrelated_untracked_file_blocks`,
   `test_extra_observed_file_blocks`;
4. missing / changed / size-mismatched / extra file blocks —
   `test_missing_manifest_file_blocks`,
   `test_manifest_listed_file_absent_from_observed_blocks`,
   `test_hash_mismatched_file_blocks`, `test_size_mismatched_file_blocks`;
5. duplicate or malformed paths block — `test_duplicate_path_blocks`,
   `test_malformed_paths_block`, `test_out_of_root_path_blocks`,
   `test_symlink_component_blocks`;
6. wrong package root or package kind blocks — `test_wrong_package_kind_blocks`,
   `test_wrong_migration_execution_id_blocks`;
7. wrong authorization ID / branch / HEAD / verdict / command blocks —
   `test_wrong_authorization_id_blocks`, `test_wrong_branch_blocks`,
   `test_wrong_head_blocks`, `test_non_pass_verdict_blocks`,
   `test_wrong_command_mode_blocks`, `test_authorization_invocation_count_blocks`,
   `test_authorization_flag_true_blocks`;
8. selective-1h authorization blocks — `test_selective_1h_authorization_blocks`;
9. manifest or marker inside the repository blocks —
   `test_manifest_inside_repository_blocks`,
   `test_marker_inside_repository_blocks`;
10. manifest or marker hash mismatch blocks —
    `test_manifest_hash_mismatch_blocks`, `test_marker_hash_mismatch_blocks`,
    `test_marker_file_set_digest_mismatch_blocks`,
    `test_marker_manifest_sha_mismatch_blocks`,
    `test_authorization_file_sha_mismatch_blocks`, `test_marker_flag_true_blocks`;
11. malformed or extra schema keys block — `test_extra_manifest_key_blocks`,
    `test_extra_file_entry_key_blocks`, `test_extra_marker_key_blocks`,
    `test_duplicate_json_keys_block`;
12. staged or unstaged tracked changes block — `test_staged_changes_block`,
    `test_unstaged_changes_block`;
13. exact-file-set digest is deterministic — `test_file_set_digest_is_deterministic`;
14. canonical six-field Git-provenance object remains unchanged —
    `test_canonical_six_field_payload_unchanged`, plus `test_summary_is_bounded`;
15. environment variables are all-or-none — `test_env_absent_returns_none`,
    `test_partial_env_blocks`, `test_full_env_valid_resolves`,
    `test_preflight_only_mode_supported`;
16. unsupported modes reject the variables — `test_unsupported_modes_reject_env`;
17. no provider / source / Scheduler / campaign / DB call occurs —
    `test_validation_performs_no_network` (sockets disabled during a successful
    validation), plus the whole module operates on temp repos and disposable
    files and never opens the authoritative database.

Only focused tests plus syntax/import checks were run. No broad regression suite
was run; no focused failure demonstrated a broader architectural effect. The two
initial focused failures were test-expectation errors (a same-size byte change
and the marker-inside case being caught first by the untracked-equality gate),
corrected in the test file; no module defect was involved.

## Money-usefulness contribution

This implementation makes the approved compatibility repair executable in code.
It prevents another scarce one-shot WINDOW_15M authorization from being consumed
by a wrapper that would deterministically self-block before useful collection,
while preserving the stronger Git launch boundary. It raises the chance that a
future authorized paper-only campaign reaches its real bounded source and memory
path without hiding unrelated repository state. It creates no market signal,
memory, decision, position, trade, or profit claim.

## What improved

- the exact manifest/marker trust boundary is now enforced in production code;
- every allowed untracked exception is bound to authorization identity, branch,
  HEAD, path, size, and SHA-256, plus manifest and file-set digests;
- the fixed SQLite sidecar tuple and the manifest allowlist are combined only at
  the capture boundary, and any residual untracked path still fails closed;
- the canonical six-field Git-provenance payload is preserved, with only a
  bounded, file-name-free manifest/marker summary added to preflight evidence;
- the integration is restricted to ordinary `preflight-only` and `run`; every
  other public mode fails closed if any of the four variables is supplied.

## What remains locked

- the bounded disposable proof (next lane);
- the external one-shot wrapper artifact and any fresh campaign authorization;
- providers, RPC, WebSockets, source fetching, discovery, and Scheduler runtime;
- memory generation or promotion; retrieval or dirty-memory use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL;
- wallets, private keys, signing, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Solana-only, memecoin-only, and
paper-only V1 restrictions are preserved.

## Proof still required

1. one bounded disposable proof (temporary Git repository, copied evidence
   fixtures, disposable authorization/marker, disposable or no DB, no provider
   keys, no network, no authoritative DB mutation, no Scheduler runtime, no
   campaign, no memory/retrieval/decision/position/trade/audit/PnL);
2. independent repair closeout with exact hashes and negative results;
3. repeated authoritative readiness audit;
4. a new final authorization;
5. one future campaign attempt.

No step may be skipped.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition | Control in this implementation |
| --- | --- | --- |
| Manifest becomes a generic bypass | Rejected | Exact schema, authorization binding, exact roots, sizes, and hashes |
| Marker created or consumed before validation | Out of scope here | The production validator only reads the marker; the wrapper (future) owns exclusive creation |
| Missing manifest-listed file passes helper | Handled | Exact observed-set equality plus per-file existence |
| Extra unrelated untracked file | Blocks | Equality plus the unchanged capture helper |
| Symlink or path normalization ambiguity | Blocks | Symlink-component rejection before resolve; normalization equality |
| Broad `operator-runs/` exemption | Rejected | Exact files only; no directory or glob support added |
| Selective-1h / discovery inherits exception | Rejected | Ordinary `preflight-only`/`run` only; all other modes fail closed |
| Existing helper payload omits filenames | Preserved | Separate bounded summary and file-set digest; six-field payload unchanged |
| Large migration package rehash cost | Accepted bounded cost | Streamed SHA-256; no content copying |
| Interpreter mismatch (system Python 3.9) | Efficiency note | Tests run under `.venv` Python 3.12; repo requires >= 3.11 |

## Exact next lane

`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Bounded Disposable Proof`

Type: disposable, non-campaign, zero-provider, zero-authoritative-DB-mutation
proof of the implemented validator and preflight boundary, followed by
independent repair closeout. It may not run providers, source fetching,
discovery, Scheduler runtime, a campaign, memory generation, retrieval, paper
decisions, positions, trades, audits, or PnL, and it may not issue a fresh
campaign authorization.
