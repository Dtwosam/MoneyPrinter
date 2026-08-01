# Printer V1 V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Implementation

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Implementation`

Lane type: narrow implementation and focused disposable verification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_IMPLEMENTATION_PASS`

The approved three-set ignored-evidence reconciliation design is implemented in the production manifest validator.

The implementation preserves the existing all-file manifest, marker schema, authorization binding, immutable result, bounded summary, ordinary `WINDOW_15M` mode boundary, existing capture helper, and canonical six-field Git-provenance payload.

No wrapper was created, no authorization was issued, no provider or source was contacted, no Scheduler or campaign ran, no database was opened or mutated, and no memory, retrieval, decision, position, trade, audit, or PnL capability changed.

## 2. Controlling baseline

| Item | Value |
| --- | --- |
| Implementation branch | `agent/v2-9-8b-window-15m-ignored-evidence-visibility-repair-implementation` |
| Starting HEAD | `cce78eae42a4e711439c0623fdadc1dde857cf2a` |
| Approved design verdict | `V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_DESIGN_PASS` |
| Blocked readiness audit | `V2_9_8B_WINDOW_15M_POST_REPAIR_AUTHORITATIVE_READINESS_BLOCKED_IGNORED_EVIDENCE_VISIBILITY` |
| Authoritative evidence shape | 19 files: 17 Git-visible and 2 Git-ignored `.sqlite3` backups |

The active Printer V1 source stack remains unchanged:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## 3. Exact files changed

1. Modified:
   `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
2. Added:
   `tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py`
3. Added:
   `docs/printer-v1-v2-9-8b-window-15m-authoritative-ignored-evidence-visibility-repair-implementation.md`

No other file is changed.

In particular, the lane does not modify:

- `.gitignore`
- `.git/info/exclude`
- global Git configuration
- `git_provenance.py`
- `operational_memory_factory_command.py`
- PowerShell parameters or public command shape
- migrations or schema
- Source Governor
- Central Scheduler
- campaign, memory, retrieval, decision, position, trade, audit, or PnL ownership

## 4. Implemented reconciliation contract

The validator now derives and reconciles three exact evidence sets.

### 4.1 Manifest set

`M = all normalized manifest file paths`

Every member continues to pass the existing direct validation:

- exact approved package identity
- normalized repository-relative POSIX path
- no absolute path, traversal, empty segment, trailing slash, glob, or backslash
- no symlink file or parent component
- regular file
- exact byte size
- exact SHA-256
- unique path
- correct package kind and authorization or migration identity

### 4.2 Git-visible set

`V = git ls-files --others --exclude-standard -z`

The existing fixed authoritative SQLite runtime sidecars are subtracted exactly as before. Any remaining visible untracked path outside the manifest blocks.

### 4.3 Scoped Git-ignored set

`I = git ls-files --others --ignored --exclude-standard -z -- operator-runs/`

The query is scoped only to `operator-runs/`. It does not enumerate or authorize ignored content elsewhere in the repository.

### 4.4 Complete filesystem inventory

`F = every regular file beneath operator-runs/`

The validator performs a no-follow recursive inventory limited to `<repository_root>/operator-runs`.

It blocks on:

- a symlinked `operator-runs` root
- any symlink file
- any symlink directory
- sockets, devices, FIFOs, or another non-regular entry
- malformed or duplicate repository-relative paths
- unreadable inventory state

The walk never follows symlink directories and does not hash unrelated ignored content outside `operator-runs/`.

## 5. Required set invariants implemented

The validator now requires:

1. `F == M`
2. `V_effective - M == empty`
3. `I - M == empty`
4. `V_effective intersect I == empty`
5. every manifest path is classified as exactly visible-untracked or scoped ignored-untracked
6. every ignored path exists in the complete filesystem inventory

Consequences:

- the two accepted ignored SQLite backups can be present in the complete manifest and pass;
- an extra ignored SQLite file inside an authorized package blocks;
- an ignored file under another `operator-runs/` package blocks;
- a visible extra file inside or outside `operator-runs/` blocks;
- a tracked file beneath `operator-runs/` blocks through complete-inventory/classification reconciliation;
- a manifest-listed file classified by neither Git set blocks;
- visible/ignored overlap blocks;
- unrelated ignored files outside `operator-runs/` are not added to the trust boundary.

## 6. Compatibility preserved

No manifest schema change was made.

`PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` remains unchanged.

No marker schema change was made.

`PRINTER_V1_APPLICATION_MARKER_V1` remains unchanged.

The existing allowed-file-set SHA-256 remains deterministic over every manifest record, including ignored files.

The public validator signature remains unchanged:

- repository root
- manifest path and SHA-256
- marker path and SHA-256
- Git executable
- timeout ceiling
- injectable runner
- fixed sidecar paths

The immutable `ValidatedGitProvenanceAuthorization` fields remain unchanged.

The bounded summary remains file-name-free and exposes only:

- authorization ID
- manifest SHA-256
- marker SHA-256
- allowed-file-set SHA-256
- allowed file count

The existing operational command integration therefore requires no modification.

## 7. Deterministic failure messages

The implementation adds bounded operator-facing blockers for:

- visible/ignored classification overlap
- unexpected ignored `operator-runs/` file
- manifest file absent from complete inventory
- unexpected complete-inventory file
- ignored path absent from inventory
- manifest path classified by neither visible nor ignored Git state
- symlink or non-regular inventory entry
- malformed or duplicate Git path output

Existing blocker wording used by the original validator contract remains available for visible extras, staged/unstaged changes, schema errors, path errors, hash/size mismatch, authorization mismatch, marker mismatch, and mode violations.

## 8. Focused validation

The exact replacement module and exact new test module were syntax-compiled before publication.

A disposable isolated package executed the new focused suite against the exact implementation bytes.

Result:

`24 passed in 3.454s`

The focused suite proves:

1. real `*.sqlite3` ignore semantics;
2. 17 Git-visible evidence files;
3. 2 Git-ignored SQLite evidence files;
4. complete 19-file manifest PASS;
5. digest determinism and ignored-file inclusion;
6. extra ignored file inside the authorized migration package blocks;
7. extra ignored file under an unauthorized `operator-runs/` package blocks;
8. missing ignored file blocks;
9. ignored filesystem file omitted from the manifest blocks;
10. tracked `operator-runs/` file blocks;
11. visible extra outside `operator-runs/` blocks;
12. visible extra inside `operator-runs/` blocks;
13. symlink file blocks;
14. symlink directory blocks without traversal;
15. non-regular FIFO blocks where supported;
16. manifest path classified by neither Git set blocks;
17. visible/ignored overlap blocks;
18. unrelated ignored content outside `operator-runs/` remains outside the trust boundary;
19. zero network dependency;
20. authorization PASS law remains fail-closed;
21. marker digest mismatch remains fail-closed;
22. exact manifest schema and duplicate path law remain fail-closed;
23. direct hash/size and tracked-tree checks remain fail-closed;
24. external-file and bounded-summary contracts remain unchanged.

The source SHA-256 used for isolated validation was:

`94ae4103e2f1b797d1d8ca3516f601115511c05bcdc776d7fcc658b9c13589ca`

The focused test source SHA-256 used for isolated validation was:

`3d2c86248bf1f4d3fbf579025cec0832a73636f1ff2d832a41579ba63de59656`

The existing committed validator/integration test module was not modified. A broad repository suite was not run because this lane changed only the isolated validator boundary and no focused result indicated broader architectural impact. The next bounded disposable proof must execute the committed focused modules in the repository environment before closeout.

## 9. Money-usefulness contribution

The implementation removes the deterministic mismatch that would reject the two accepted SQLite evidence backups before a useful paper-only `WINDOW_15M` lifecycle begins.

It improves future collection reliability while preserving complete audit evidence and strict failure behavior. It creates no market signal, memory, retrieval result, decision, position, trade, or profit claim.

## 10. What improved

- all 19 accepted authoritative-shaped evidence files can participate in one exact manifest;
- ignored SQLite evidence is explicitly classified rather than silently omitted;
- every file under `operator-runs/` is reconciled against the manifest;
- extra ignored evidence becomes visible to the fail-closed trust boundary;
- unrelated ignored development content remains outside the authorization namespace;
- no ignore rule or operational command was weakened.

## 11. What remains locked

- the bounded disposable proof of this repair;
- independent repair closeout;
- repeated authoritative readiness audit;
- external one-shot wrapper construction;
- any fresh final authorization;
- providers, RPC, WebSockets, and source fetching;
- discovery and Scheduler runtime;
- campaign execution;
- memory generation or promotion;
- retrieval and dirty-memory use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, signing, real funds, live execution, and paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Solana-only, Solana memecoin-only, and paper-only V1 restrictions remain unchanged.

## 12. Proof required before readiness

The next proof lane must:

1. run the committed existing validator/integration tests plus the new focused test module;
2. reproduce the real `*.sqlite3` ignore semantics;
3. prove a 19-file manifest with 17 visible and 2 ignored files passes;
4. prove extra ignored evidence inside an authorized package blocks;
5. prove ignored evidence elsewhere under `operator-runs/` blocks;
6. prove a visible extra outside `operator-runs/` blocks;
7. prove visible and ignored classifications are disjoint and complete;
8. prove unrelated ignored content outside `operator-runs/` is not authorized;
9. use temporary repositories and disposable fixtures only;
10. record zero network, SQLite, provider, Scheduler, campaign, memory, retrieval, decision, position, trade, audit, and PnL activity.

After proof PASS, the roadmap still requires independent closeout and another authoritative readiness audit. No fresh authorization may be considered before those steps pass.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Control |
| --- | --- |
| General ignored-file bypass | Rejected; ignored Git query is scoped to `operator-runs/` only |
| Extra ignored file under an approved package | Blocks through `I - M` and `F - M` |
| Extra ignored file under another `operator-runs/` package | Blocks through complete inventory and ignored-set reconciliation |
| Unrelated ignored content elsewhere | Not enumerated and not authorized |
| Visible untracked drift | Existing whole-repository visible query still blocks |
| Tracked evidence under `operator-runs/` | Complete inventory cannot satisfy untracked classification |
| Symlink traversal | No-follow walk; any symlink blocks |
| Non-regular filesystem object | Blocks |
| Git output ambiguity or duplicates | Blocks |
| Schema or digest drift | Existing manifest/marker law preserved |
| Operational ownership drift | None; operational command unchanged |
| Full repository suite not executed in connector environment | Deferred to the mandatory bounded disposable proof; isolated exact-source suite passed |

## 14. Exact next lane

`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Bounded Disposable Proof`

Type: disposable proof only.

It may not build the real wrapper, issue authorization, contact providers, run Scheduler, execute a campaign, open or mutate the authoritative database, generate memory, activate retrieval, or unlock paper trading.
