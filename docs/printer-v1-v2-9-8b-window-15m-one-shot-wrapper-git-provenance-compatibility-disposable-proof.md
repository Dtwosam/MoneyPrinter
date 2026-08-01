# Printer V1 V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Disposable Proof

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Bounded Disposable Proof`

Lane type: proof only. No implementation was repaired or expanded. No campaign,
provider, Source Governor, Central Scheduler, memory, retrieval, decision,
position, trade, audit, or PnL work occurred, and the authoritative database was
never opened.

## Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_DISPOSABLE_PROOF_PASS`

The implemented manifest/marker validator and its narrow `preflight-only`/`run`
operational preflight boundary were proven, fail-closed, against a disposable
temporary Git repository with disposable external fixtures. All seven positive
cases passed, all ten required negative cases (plus one supporting marker-inside
case) blocked at the exact expected blocker, every runtime guard held, and both
real untracked `operator-runs/` evidence packages plus the authoritative
database were byte-for-byte unchanged.

## Baseline

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-window-15m-provenance-compatibility-disposable-proof` |
| Starting / ending HEAD | `9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c` |
| Tracked worktree | clean before and after (no tracked file changed) |
| Preserved untracked package A | `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/` (11 files) |
| Preserved untracked package B | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/` (8 files) |
| Implementation lane | `V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_IMPLEMENTATION_PASS` (commit `9a22d0d`) |

The remote branch was fetched to the exact required ref and tracked; its HEAD was
`9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c`. The two untracked evidence packages
were neither modified, deleted, moved, nor ignored. Their pre/post SHA-256
digests are identical (see integrity results).

### Source-file Git blob hashes (proven at baseline)

| File | Blob |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance.py` | `4f3fa4a78028bab149a613c148b6cfc65c3e310d` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `1ec951301da185d56a67f8e7d8bb8165d279395d` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `2901dae139cc4a4f996dd3a2768ebe499790e716` |
| `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` | `17a50fe138f694b729aabc5e75e85eb85096d3aa` |

## Exact disposable proof method

A single self-contained proof harness (disposable; never committed) built
disposable temporary Git repositories under a unique external proof directory and
exercised the production validator, resolver, and capture helper directly. It
imported and called only:

* `git_provenance_authorization_manifest.validate_git_provenance_authorization()`
  and `compute_allowed_file_set_sha256()`;
* `git_provenance.capture_git_provenance()`;
* `operational_memory_factory_command._resolve_git_provenance_authorization()`
  and `_capture_operational_git_provenance()`.

Each temporary repository reproduced the approved package shapes:

* `operator-runs/v2-9-8b-authoritative-mig050/<disposable_migration_execution_id>/…`
  (migration evidence, including a nested `verified-backup/…sqlite3` file);
* `operator-runs/v2-9-8b-window-15m-final-authorization/<disposable_authorization_id>/…`
  (`final_authorization.json`, `pre_run_evidence.json`, `application_started.json`).

A disposable authorization ID, a disposable external manifest, and a disposable
external application marker were created outside the temporary repository. The
disposable authorization was bound to the temporary repository's **real** branch
and HEAD (temp repo `master` @ `f4550a816ab955b99de001af14f6dd6e91b0fbb9` for the
positive fixture; each negative case used a fresh temporary repository with its
own real branch/HEAD). No authoritative database, no real authorization, no
provider credentials, no network, and no campaign invocation were used.

External proof directory (unique per execution):

```
$HOME/PrinterOperations/v2-9-8/provenance-compatibility-disposable-proof/
  V2_9_8B_WINDOW_15M_GITPROV_DISPOSABLE_PROOF_20260801T221154Z_73a65c89/
```

Disposable identities (positive fixture):

| Item | Value |
| --- | --- |
| Execution ID | `V2_9_8B_WINDOW_15M_GITPROV_DISPOSABLE_PROOF_20260801T221154Z_73a65c89` |
| Disposable authorization ID | `V2_9_8B_WINDOW_15M_DISPOSABLE_POSITIVE` |
| Manifest SHA-256 | `701dd0137d831a07be1eeb44e6186a0c16ba07b12a71d3cf555fcdef3f41607f` |
| Marker SHA-256 | `2576314416a9b174f165dbcbe8a08af48d68176462c41d1ce0bdde913333110d` |
| Allowed-file-set SHA-256 | `c8bfd971074c5b6c071ee78208a1dfe0594bf54972cb8d7caaec236267d7d0de` |

### Runtime guards (installed before any proof logic)

* **Sockets** — `socket.socket` and `socket.create_connection` replaced with
  raising guards; recorded network calls: **0**.
* **SQLite** — `sqlite3.connect` replaced with a raising guard; recorded connect
  attempts: **0**.
* **Subprocess** — `subprocess.Popen` replaced with a single guarded choke point
  that permits only read-only `git` plumbing and blocks anything matching the
  public PowerShell launcher or the operational campaign command (`.ps1`,
  `powershell`, `pwsh`, `operational_memory_factory_command`,
  `run_operational_campaign`). Because `subprocess.run` resolves `Popen` through
  the module global, this choke point observed **every** git spawn, including the
  validator's own read-only plumbing. Recorded read-only git spawns: **195**;
  forbidden subprocess blocked: **none**; guard triggered: **false**.
* **Authoritative DB** — never referenced; `data/printer_v1.sqlite3` size and
  `mtime_ns` were captured before and after and were identical (opens 0,
  writes 0).
* **Real evidence** — the 19 real untracked evidence files were SHA-256 hashed
  (read-only) before and after; identical.

Each negative case ran on a **fresh** disposable fixture and first proved the
fixture was at the exact clean baseline (a clean `validate()` succeeded) before
applying its single mutation or bad invocation. No mutated fixture was reused
across cases.

## Positive proof results

| # | Claim | Result |
| --- | --- | --- |
| 1 | the complete manifest validates | **PASS** (`ValidatedGitProvenanceAuthorization`, authorization_id + file_count + manifest SHA-256 confirmed) |
| 2 | the external marker validates and binds to the manifest | **PASS** (marker's `manifest_sha256`, `allowed_file_set_sha256`, `authorization_sha256` all bind) |
| 3 | the allowed-file-set digest is deterministic | **PASS** (identical under reversed input order; equals result digest) |
| 4 | `_resolve_git_provenance_authorization()` accepts all four env vars for `preflight-only` | **PASS** (also accepts `run`) |
| 5 | `_capture_operational_git_provenance()` passes with only the validated exact paths plus fixed SQLite sidecars | **PASS** (`git_untracked_present=false`, `git_tracked_tree_clean=true`) |
| 6 | the canonical Git-provenance object retains exactly its six fields | **PASS** (`set(provenance) == GIT_PROVENANCE_FIELDS`, len 6) |
| 7 | the bounded summary contains no file names or fixture contents | **PASS** (five bounded keys only; no path or fixture-content leak) |

## Negative proof results (fail-closed, each with the exact expected blocker)

| # | Case | Exact blocker observed | Blocked as expected |
| --- | --- | --- | --- |
| 1 | no manifest allowlist while evidence files are untracked | `launch Git tree contains an arbitrary untracked file` (`GitProvenanceError`) | ✅ |
| 2 | one unrelated extra untracked file | `unexpected untracked repository file not covered by manifest: unrelated_stray.txt` | ✅ |
| 3 | one evidence-file SHA-256 mismatch | `manifest file SHA-256 mismatch: operator-runs/v2-9-8b-authoritative-mig050/…` | ✅ |
| 4 | one evidence-file size mismatch | `manifest file size mismatch: operator-runs/v2-9-8b-authoritative-mig050/…` | ✅ |
| 5 | one missing manifest-listed file | `manifest file is missing or not a regular file: operator-runs/v2-9-8b-authoritative-mig050/…` | ✅ |
| 6 | staged tracked change | `launch Git tree has staged changes` | ✅ |
| 7 | unstaged tracked change | `launch Git tree has unstaged changes` | ✅ |
| 8 | partial four-variable environment configuration | `git provenance manifest environment variables must all be set together or all be unset: missing=…` (`OperationalMemoryFactoryError`) | ✅ |
| 9 | unsupported mode `discovery-only` | `git provenance manifest integration is not accepted for mode='discovery-only'` (`OperationalMemoryFactoryError`) | ✅ |
| 10 | manifest placed inside the temporary repository | `manifest must live outside the repository` | ✅ |
| 10b (supporting) | marker placed inside the temporary repository | `unexpected untracked repository file not covered by manifest: inside-marker.json` (untracked-equality gate runs before marker resolution; shares the marker outside-repository code path) | ✅ |

No positive case failed and no negative case unexpectedly passed.

## Focused test results

Syntax/import checks:

* `py_compile` of `git_provenance.py` and
  `git_provenance_authorization_manifest.py` — **OK**.
* Import of both modules with `capture_git_provenance` and
  `validate_git_provenance_authorization` present — **OK**.

Focused suite:

```
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py \
  tests/test_v2_9_7b_5_embedded_git_provenance.py \
  tests/test_v2_9_8a_public_operational_command.py \
  -q
```

Result: **70 passed in 4.37s**. No broad suite was run; no focused failure
demonstrated a broader architectural issue.

## Proof JSON record

An immutable (`0444`, read-only) JSON proof record was written to the external
proof directory:

| Item | Value |
| --- | --- |
| Path | `$HOME/PrinterOperations/v2-9-8/provenance-compatibility-disposable-proof/V2_9_8B_WINDOW_15M_GITPROV_DISPOSABLE_PROOF_20260801T221154Z_73a65c89/disposable_proof_record.json` |
| Byte size | `18479` |
| SHA-256 | `ae4cd39fdb8dea3654e638740e042240741718b09a46496984adb718cf607092` |

It records: execution ID and timestamps; real branch and exact HEAD;
source-file Git blob hashes; temporary-repository identity; disposable
authorization ID; manifest, marker, and allowed-file-set SHA-256 values; the
positive result; each negative case with its exact expected blocker and observed
message; the test commands and results; network calls `0`; authoritative DB
opens/writes `0`; provider/source/Scheduler/campaign/memory/retrieval/decision/
position/trade/audit/PnL calls `0`; real campaign invocations `0`;
protected-capability activity `0`; real evidence-package pre/post hashes; and the
proof verdict.

### Integrity results

| Guarded quantity | Value |
| --- | --- |
| Network calls | 0 |
| `sqlite3.connect` attempts | 0 |
| Forbidden subprocess (launcher / campaign command) | 0 (none) |
| Read-only `git` spawns (through the guarded choke point) | 195 |
| Authoritative DB opens / writes | 0 / 0 (size + `mtime_ns` identical) |
| Real evidence packages | unchanged (pre == post, 19 files) |
| Real repository tracked files changed | 0 |
| Guard triggered | false |

## Money-usefulness contribution

This proof independently confirms — with runtime guards, not just assertions —
that the approved compatibility repair behaves exactly as designed and fails
closed everywhere it must. It protects the scarce one-shot WINDOW_15M
authorization: a future authorized paper-only campaign that legitimately carries
the two approved evidence packages will no longer self-block at the launch-time
Git gate, while any tampering, drift, partial configuration, wrong mode, or stray
file still blocks. It moves the lane one required step closer to a real bounded
collection run without creating any market signal, memory, decision, position,
trade, or profit claim.

## What the lane improves

* the implemented manifest/marker trust boundary is now proven end-to-end against
  reproduced package shapes, not only unit-mocked;
* every fail-closed path required by the design was demonstrated with its exact
  operator-facing blocker message;
* the canonical six-field Git-provenance payload is proven unchanged, and the
  bounded summary is proven to leak no file name or fixture content;
* the `preflight-only`/`run`-only integration boundary is proven, with
  `discovery-only` and partial environments rejected;
* the proof is fully disposable and left the real repository, its tracked files,
  its two evidence packages, and the authoritative database untouched.

## What remains locked

* the external one-shot wrapper artifact and any fresh campaign authorization;
* providers, RPC, WebSockets, source fetching, discovery, and Scheduler runtime;
* memory generation or promotion; retrieval or dirty-memory use;
* `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
* paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL;
* wallets, private keys, signing, real funds, live execution, paid APIs;
* scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Solana-only, memecoin-only, and
paper-only V1 restrictions are preserved.

## Proof still required before any campaign

1. independent repair closeout with exact hashes and negative results (next lane);
2. repeated authoritative readiness audit;
3. a new final authorization;
4. one future campaign attempt.

No step may be skipped.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition | Control in this proof |
| --- | --- | --- |
| Proof accidentally touches the real DB | Prevented | `sqlite3.connect` guard (0 attempts); DB size + `mtime_ns` identical pre/post |
| Proof reaches the network | Prevented | socket guards (0 calls); no provider secret read |
| Proof spawns the launcher / campaign command | Prevented | guarded `Popen` choke point blocked all non-git spawns (0 forbidden), permitting only read-only git |
| Mutated fixture leaks across negative cases | Prevented | fresh fixture per case, clean-baseline re-verified before each mutation |
| Real evidence packages altered | Prevented | read-only hashing pre/post, identical (19 files) |
| A negative case silently passes | Not observed | every negative case asserted both the exact exception type and the exact blocker substring |
| Interpreter mismatch (system Python 3.9) | Efficiency note | harness and tests run under `.venv` Python 3.12; repo requires >= 3.11 |
| Marker-inside-repo caught by an earlier gate than its own outside-repo check | Accepted | still fail-closed; documented as case 10b, sharing the marker outside-repository code path |

## Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_DISPOSABLE_PROOF_PASS`

## Exact next lane

`V2-9.8B WINDOW_15M Git-Provenance Compatibility Independent Repair Closeout`
