# Printer V1 V2-9.8B WINDOW_15M Git-Provenance Compatibility Independent Repair Closeout

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Git-Provenance Compatibility Independent Repair Closeout`

Lane type: independent read-only audit and closeout. The only repository change in
this lane is this closeout document.

## 1. Verdict

`V2_9_8B_WINDOW_15M_GIT_PROVENANCE_COMPATIBILITY_INDEPENDENT_REPAIR_CLOSEOUT_PASS`

The narrow Git-provenance compatibility repair is independently closed.

The approved implementation remains fail-closed and exact-file-only. The bounded
disposable proof record was independently re-read, re-hashed, and reconciled with
the repository, implementation blobs, real evidence packages, and authoritative
database identity. All required positive proof cases passed, every required
negative case blocked, no capability boundary moved, and no evidence or database
drift was found.

This PASS does not authorize a wrapper, a fresh campaign authorization, provider
access, source fetching, discovery, Scheduler runtime, a campaign, memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
or PnL.

## 2. Controlling baseline and ancestry

| Item | Independently verified value |
| --- | --- |
| Closeout branch | `agent/v2-9-8b-window-15m-provenance-compatibility-independent-closeout` |
| Closeout starting HEAD | `ada3376a09abcd6fe291d309889c1fb91d5d73ec` |
| Corrected design commit | `d4166010472d1e6504d2a9805e9d5e047116212b` |
| Implementation commit | `9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c` |
| Disposable proof commit | `ada3376a09abcd6fe291d309889c1fb91d5d73ec` |
| Tracked tree before closeout document | clean |

Ancestry checks passed:

- `d4166010472d1e6504d2a9805e9d5e047116212b` is an ancestor of
  `9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c`;
- `9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c` is an ancestor of
  `ada3376a09abcd6fe291d309889c1fb91d5d73ec`;
- GitHub comparison shows implementation is exactly one commit ahead of design;
- GitHub comparison shows disposable proof is exactly one commit ahead of
  implementation.

## 3. Implementation-scope review

The implementation commit changed only four approved files:

1. `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
2. `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
3. `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`;
4. `docs/printer-v1-v2-9-8b-window-15m-one-shot-wrapper-git-provenance-compatibility-implementation.md`.

The disposable proof commit added only:

- `docs/printer-v1-v2-9-8b-window-15m-one-shot-wrapper-git-provenance-compatibility-disposable-proof.md`.

No disposable harness, temporary repository, proof fixture, external manifest,
external marker, provider secret, database copy, or runtime artifact was
committed.

Independent source review confirmed:

- the new validator reads explicit external manifest and marker paths and hashes;
- manifest, marker, authorization, command, path, size, and digest validation is
  fail-closed;
- exact schemas reject missing, extra, and duplicate keys;
- repository evidence paths remain exact normalized repository-relative POSIX
  files under the two approved package identities;
- absolute paths, traversal, globs, directory forms, duplicates, symlinks,
  missing files, size drift, hash drift, and out-of-root paths block;
- live branch, HEAD, staged state, unstaged state, and observed untracked state
  are checked using read-only Git plumbing;
- final authorization must be PASS, ordinary `run`, operator-approved, exactly
  one invocation, `WINDOW_15M`, selective-1h false, and all retry/rerun/resume/
  restart/successor flags false;
- the external marker binds authorization SHA-256, manifest SHA-256,
  allowed-file-set SHA-256, branch, HEAD, command, one invocation, and all false
  retry/restart flags;
- the immutable validated result returns only the exact allowed path tuple,
  authorization ID, manifest SHA-256, marker SHA-256, allowed-file-set SHA-256,
  and file count;
- its bounded summary exposes no file names or fixture contents;
- the operational integration accepts all four environment variables together or
  none and only for `preflight-only` and ordinary `run`;
- exact validated paths are combined only with the existing fixed SQLite sidecar
  tuple at the existing capture boundary;
- any residual untracked path still blocks;
- the canonical six-field Git-provenance object remains unchanged;
- `git_provenance.py` was not changed or weakened;
- no PowerShell public parameter or command shape changed;
- no migration, schema, Source Governor, Central Scheduler, memory, retrieval,
  paper-decision, position, trade, audit, or PnL ownership changed.

## 4. Source and test blob reconciliation

The disposable proof record's source blobs were independently resolved from Git
at implementation commit `9a22d0d` and compared with proof commit `ada3376`.
All remained unchanged:

| File | Git blob at implementation and proof |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance.py` | `4f3fa4a78028bab149a613c148b6cfc65c3e310d` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `1ec951301da185d56a67f8e7d8bb8165d279395d` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `2901dae139cc4a4f996dd3a2768ebe499790e716` |
| `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` | `17a50fe138f694b729aabc5e75e85eb85096d3aa` |

The recorded focused verification remains:

- 48 dedicated manifest/marker tests passed;
- 22 direct boundary-regression tests passed in implementation;
- the combined proof verification recorded 70 passed in 4.37 seconds;
- `py_compile` and import checks passed.

The closeout did not rerun the test suite, because this lane is independent
read-only review and no source blob changed after the proof.

## 5. External proof-record identity

The closeout independently inspected:

`$HOME/PrinterOperations/v2-9-8/provenance-compatibility-disposable-proof/V2_9_8B_WINDOW_15M_GITPROV_DISPOSABLE_PROOF_20260801T221154Z_73a65c89/disposable_proof_record.json`

Verified identity:

| Property | Result |
| --- | --- |
| Exists outside repository | PASS |
| Regular file | PASS |
| Symlink | no |
| Mode | `0444` |
| Size | `18479` bytes |
| SHA-256 | `ae4cd39fdb8dea3654e638740e042240741718b09a46496984adb718cf607092` |
| Duplicate-key-safe JSON parse | PASS |
| Execution ID | `V2_9_8B_WINDOW_15M_GITPROV_DISPOSABLE_PROOF_20260801T221154Z_73a65c89` |
| Verdict | `V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_DISPOSABLE_PROOF_PASS` |

Disposable positive-fixture identity reconciled exactly:

- authorization ID:
  `V2_9_8B_WINDOW_15M_DISPOSABLE_POSITIVE`;
- manifest SHA-256:
  `701dd0137d831a07be1eeb44e6186a0c16ba07b12a71d3cf555fcdef3f41607f`;
- marker SHA-256:
  `2576314416a9b174f165dbcbe8a08af48d68176462c41d1ce0bdde913333110d`;
- allowed-file-set SHA-256:
  `c8bfd971074c5b6c071ee78208a1dfe0594bf54972cb8d7caaec236267d7d0de`;
- temporary repository branch/HEAD:
  `master` at `f4550a816ab955b99de001af14f6dd6e91b0fbb9`.

## 6. Positive proof reconciliation

All seven required positive claims are present and PASS:

1. complete manifest validation;
2. external marker binding to manifest and authorization;
3. deterministic allowed-file-set digest;
4. all four environment variables accepted for `preflight-only`;
5. capture helper passes with only exact validated paths plus fixed SQLite
   sidecars;
6. canonical Git-provenance object remains exactly six fields;
7. bounded summary contains no path or fixture-content leak.

The six canonical fields recorded are:

- `git_head`;
- `git_provenance_captured_at`;
- `git_staged_changes_present`;
- `git_tracked_tree_clean`;
- `git_unstaged_changes_present`;
- `git_untracked_present`.

## 7. Negative proof reconciliation

All ten required negative cases and the supporting marker-inside case record a
clean disposable baseline first and then block as expected:

1. no manifest allowlist with untracked evidence;
2. unrelated extra untracked file;
3. evidence SHA-256 mismatch;
4. evidence size mismatch;
5. missing manifest-listed file;
6. staged tracked change;
7. unstaged tracked change;
8. partial four-variable environment;
9. unsupported `discovery-only` mode;
10. manifest inside repository;
11. supporting marker-inside-repository case.

Every case records both the expected blocker and observed blocking message.
`all_blocked_as_expected` is true. No negative case unexpectedly passed.

The marker-inside supporting case was caught by the earlier exact-untracked-set
gate because the marker itself became an unrelated repository-local untracked
file. This remains fail-closed and does not weaken the outside-repository marker
contract.

## 8. Runtime and capability reconciliation

The proof record and closeout collectors show:

| Guarded activity | Count/result |
| --- | --- |
| Network calls | 0 |
| SQLite connection attempts | 0 |
| Provider calls | 0 |
| Source Governor calls | 0 |
| Scheduler calls | 0 |
| Campaign calls | 0 |
| Real campaign invocations | 0 |
| Memory calls | 0 |
| Retrieval calls | 0 |
| Decision calls | 0 |
| Position calls | 0 |
| Trade calls | 0 |
| Audit calls | 0 |
| PnL calls | 0 |
| Forbidden launcher/campaign subprocess | 0 |
| Proof guard triggered | false |

The proof used 195 read-only Git process invocations through its guarded
subprocess choke point. No public PowerShell launcher or operational campaign
command ran.

## 9. Real evidence-package integrity

The initial closeout collector used `git ls-files --others --exclude-standard`
and therefore enumerated 17 visible untracked files. It omitted two nested
`.sqlite3` evidence files hidden by Git exclude behavior. This was a collector
coverage gap, not an implementation or evidence failure.

A supplemental read-only collector recursively walked only the two approved
package roots, including ignored files, and reconciled all 19 files against both
the proof record's pre and post maps.

Supplemental result:

`V2_9_8B_INDEPENDENT_CLOSEOUT_EVIDENCE_REHASH_PASS`

Verified:

- file count: 19 of 19;
- proof pre map equals proof post map;
- all current SHA-256 and size values match both maps;
- missing paths: 0;
- unexpected paths: 0;
- hash or size mismatches: 0;
- symlinks: 0;
- non-regular paths: 0;
- tracked tree remained clean;
- branch and HEAD remained exact;
- network requests: 0;
- SQLite connections: 0;
- repository writes: 0;
- campaign invocations: 0.

The two previously omitted files are present and match:

- `disposable-restore/printer_v1-rehearsal.sqlite3` — size `65654784`, SHA-256
  `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`;
- `verified-backup/printer_v1-pre050.sqlite3` — size `65654784`, SHA-256
  `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`.

The independently computed current 19-file inventory digest is:

`92a80fa80c6c1f7bd07a9e304f514c6815d711c6b8357a7a72d04629a118430e`

This inventory digest is a closeout reconciliation digest over path, SHA-256,
and size. It is separate from the disposable manifest's five-file
`allowed_file_set_sha256` and does not replace that production contract.

## 10. Authoritative database integrity

The authoritative database was hashed as a file and was never opened through
SQLite.

| Property | Independently verified value |
| --- | --- |
| Path | `data/printer_v1.sqlite3` |
| Regular, non-symlink file | yes |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `-wal` sidecar | absent |
| `-shm` sidecar | absent |
| `-journal` sidecar | absent |
| SQLite opens | 0 |
| SQLite writes | 0 |

The accepted post-migration database identity is unchanged.

## 11. Money-usefulness contribution

The closeout establishes that the repair is ready to move to authoritative
readiness review without consuming another scarce campaign authorization. A
future legitimate one-shot `WINDOW_15M` wrapper can present exact immutable
evidence without deterministically self-blocking at the Git gate, while stale,
tampered, partial, wrong-mode, or unrelated repository state still blocks.

This contributes to money usefulness only by improving the reliability and
auditability of future paper-only memory collection. It does not create a market
signal, clean memory, decision, position, trade, or profit claim.

## 12. What the repair improves

- removes the deterministic wrapper/provenance incompatibility proven by the
  earlier pre-lifecycle block;
- preserves strict tracked-tree cleanliness and exact untracked-file control;
- binds every exception to authorization identity, branch, HEAD, exact path,
  size, and SHA-256;
- binds the irreversible external marker to authorization, manifest, file set,
  branch, HEAD, command, invocation count, and no-retry law;
- preserves the canonical Git-provenance payload and existing capture helper;
- prevents directory, glob, free-form, or ignore-based provenance bypasses;
- restricts compatibility to ordinary `preflight-only` and `run`;
- leaves selective-1h, discovery-only, status, stop, recovery, and report-only
  outside the exception;
- has focused unit/boundary verification and a guarded disposable end-to-end
  proof;
- preserves the accepted database and evidence chain.

## 13. What remains locked

- external production one-shot wrapper construction/adoption;
- repeated authoritative readiness review;
- any fresh campaign authorization;
- providers, RPC, WebSockets, source fetching, discovery, and Scheduler runtime;
- campaign execution;
- memory generation, promotion, or retrieval;
- dirty-memory use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` activation;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, signing, real funds, live execution, and paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot unlock retrieval,
decisions, positions, trades, or PnL. Solana-only, Solana memecoin-only, and
paper-only V1 restrictions remain binding.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Closeout disposition | Required control |
| --- | --- | --- |
| Exact manifest becomes a generic bypass | Not observed | Continue exact files, exact package roots, exact hashes, no globs/directories |
| External marker created before complete validation | Not implemented yet | Future wrapper must validate manifest and observed set before exclusive marker creation |
| Consumed authorization reused | Prohibited | Future authoritative readiness must require a new authorization identity |
| Additional unrelated untracked file | Proven to block | Preserve exact observed-set equality and existing capture helper |
| Staged or unstaged drift | Proven to block | Readiness must recheck live tracked state immediately before wrapper preparation |
| Ignore rules hide evidence from a generic closeout collector | Observed collector limitation | Authoritative readiness must use production capture semantics for launch and recursive approved-root reconciliation for complete evidence inventory |
| Nested backup evidence changes after proof | Not observed | Re-hash all 19 accepted files during readiness and final authorization review |
| Manifest/marker or file digest drifts | Proven to block | Rebuild only under a new readiness/authorization identity; never patch consumed evidence |
| Large evidence files make repeated hashing slower | Accepted bounded cost | Use streamed SHA-256 and minimum necessary re-hash points |
| Unit proof mistaken for campaign readiness | Prevented | Separate authoritative readiness audit remains mandatory |
| Repair interpreted as retrieval or trading unlock | Rejected | All memory/retrieval/financial locks remain explicit |

## 15. Proof still required before any campaign

The repair implementation and disposable proof are closed. The following steps
remain mandatory and ordered:

1. `V2-9.8B WINDOW_15M Post-Repair Authoritative Readiness Audit`;
2. external production wrapper construction/adoption only if that readiness lane
   explicitly approves it;
3. repeated final authoritative readiness with exact current evidence and DB
   identity;
4. a new one-attempt final authorization;
5. one future ordinary `WINDOW_15M` campaign attempt.

No step may be skipped. The consumed authorization
`V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` remains consumed and invalid for reuse.

## 16. Exact next lane

`V2-9.8B WINDOW_15M Post-Repair Authoritative Readiness Audit`

Type: audit-only, read-only except for its audit document.

It must inspect current authoritative readiness after this repair, including the
complete 19-file evidence inventory, authoritative DB identity, branch/HEAD,
tracked state, manifest/marker integration readiness, wrapper ownership and
ordering, and all capability locks. It does not itself authorize or execute a
campaign.
