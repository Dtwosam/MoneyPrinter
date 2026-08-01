# Printer V1 V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Independent Closeout

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Independent Closeout`

Lane type: independent read-only verification and closeout documentation only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_INDEPENDENT_CLOSEOUT_PASS`

The ignored-evidence visibility repair is independently closed PASS at the implementation-and-disposable-proof level.

The production validator matches the approved three-set reconciliation design. The implementation commit remained within its approved source/test/document scope. The bounded proof commit added documentation only. The uploaded external proof record independently reconciles to the exact implementation commit and proves the committed focused suites passed without authoritative-state mutation or protected-capability activation.

This closeout does not establish final authoritative readiness by itself. A repeated post-repair authoritative readiness audit remains mandatory before any wrapper construction or fresh authorization may be considered.

No wrapper was built, no authorization was issued, no provider or source was contacted, no Source Governor or Central Scheduler runtime ran, no campaign executed, no authoritative database was opened or mutated, and no memory, retrieval, decision, position, trade, audit, or PnL capability was activated.

## 2. Controlling source stack

This closeout follows the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of this stack and is not treated as the sole source of truth.

The required V2 progression remains:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout report`

## 3. Exact lane chain

| Stage | Commit | Verdict |
| --- | --- | --- |
| Blocking authoritative audit | `57a8ba600cfa008209fda1e9ec4efbef7dcfa005` | `V2_9_8B_WINDOW_15M_POST_REPAIR_AUTHORITATIVE_READINESS_BLOCKED_IGNORED_EVIDENCE_VISIBILITY` |
| Repair design | `cce78eae42a4e711439c0623fdadc1dde857cf2a` | `V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_DESIGN_PASS` |
| Repair implementation | `32ec6467d08165637015d5775d5ba6e2180a74af` | `V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_IMPLEMENTATION_PASS` |
| Bounded disposable proof closeout | `21ea24d5e2ae53b7d689c2acd97a94688f58d9c0` | `V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_DISPOSABLE_PROOF_PASS` |

The independent-closeout branch started exactly from proof commit:

`21ea24d5e2ae53b7d689c2acd97a94688f58d9c0`

## 4. Independent scope verification

### 4.1 Design to implementation

Comparison from design commit `cce78eae42a4e711439c0623fdadc1dde857cf2a` to implementation commit `32ec6467d08165637015d5775d5ba6e2180a74af` showed exactly one commit and three changed files:

1. modified:
   `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
2. added:
   `tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py`
3. added:
   `docs/printer-v1-v2-9-8b-window-15m-authoritative-ignored-evidence-visibility-repair-implementation.md`

No other source, test, ignore, launcher, scheduler, campaign, migration, database, memory, retrieval, or paper-trading file changed.

This exactly matches the approved implementation scope.

### 4.2 Implementation to proof closeout

Comparison from implementation commit `32ec6467d08165637015d5775d5ba6e2180a74af` to proof commit `21ea24d5e2ae53b7d689c2acd97a94688f58d9c0` showed exactly one commit and one added file:

`docs/printer-v1-v2-9-8b-window-15m-authoritative-ignored-evidence-visibility-repair-disposable-proof.md`

No production source, test, evidence, ignore, database, wrapper, authorization, or runtime file changed during proof closeout.

## 5. Independent production-code review

The production validator was inspected directly at proof commit `21ea24d5e2ae53b7d689c2acd97a94688f58d9c0`.

### 5.1 Existing direct validation remains mandatory

Every manifest file continues to require:

- exact approved package kind;
- exact authorization or migration package identity;
- normalized repository-relative POSIX path;
- no absolute path, traversal, empty segment, trailing slash, glob, or backslash;
- no symlink file or parent component;
- regular-file status;
- exact size;
- exact SHA-256;
- unique manifest path.

The repair did not replace direct hash, size, package, or path validation with set membership alone.

### 5.2 Git-visible set remains whole-repository and fail-closed

The validator still obtains Git-visible untracked files with:

`git ls-files --others --exclude-standard -z`

Only the existing fixed authoritative SQLite runtime sidecars are subtracted.

Any other visible untracked file outside the exact manifest continues to block.

### 5.3 Ignored set is correctly bounded

The ignored query is exactly scoped to:

`operator-runs/`

using:

`git ls-files --others --ignored --exclude-standard -z -- operator-runs/`

It does not enumerate or authorize `.venv`, caches, local databases, or ignored development content elsewhere in the repository.

Returned ignored paths are normalized and explicitly rejected if they fall outside `operator-runs/`.

### 5.4 Filesystem inventory is complete and no-follow

The validator inventories the entire repository-local `operator-runs/` namespace.

The walk:

- rejects a symlinked `operator-runs` root;
- never follows symlink directories;
- rejects every symlink file or directory;
- rejects FIFO, socket, device, and other non-regular entries;
- records regular files as normalized repository-relative POSIX paths;
- includes files under unexpected package identities so they block;
- does not hash or inventory unrelated ignored content outside `operator-runs/`.

### 5.5 Required set invariants are implemented

The production reconciliation requires:

1. visible and ignored untracked classifications are disjoint;
2. no Git-visible untracked path exists outside the manifest after fixed-sidecar subtraction;
3. no scoped ignored path exists outside the manifest;
4. every manifest file exists in the complete `operator-runs/` inventory;
5. no complete-inventory file exists outside the manifest;
6. every ignored path exists in the filesystem inventory;
7. every manifest path is classified as exactly Git-visible untracked or scoped Git-ignored untracked;
8. complete inventory equals the manifest file set.

These checks implement the approved `M`, `V`, `I`, and `F` trust boundary without introducing a general ignored-file bypass.

### 5.6 Validation sequence remains correct

The production order remains:

1. validate external manifest identity and digest;
2. parse exact manifest schema with duplicate-key rejection;
3. validate live branch, HEAD, staged state, and unstaged state;
4. validate the referenced final authorization;
5. directly validate every manifest file;
6. enumerate visible untracked paths;
7. enumerate scoped ignored paths;
8. inventory complete `operator-runs/` filesystem paths;
9. reconcile all sets;
10. compute the unchanged allowed-file-set digest;
11. validate the external application marker and bindings;
12. return the immutable exact allowlist and bounded summary.

### 5.7 Compatibility preserved

Independent review confirmed no change to:

- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1`;
- `PRINTER_V1_APPLICATION_MARKER_V1`;
- public validator parameters;
- immutable validator result fields;
- allowed-file-set digest algorithm;
- bounded summary fields;
- `git_provenance.py` canonical six-field payload;
- `operational_memory_factory_command.py` integration;
- PowerShell public command shape;
- Source Governor or Central Scheduler ownership.

## 6. Independent test review

The added focused test module uses temporary Git repositories and external disposable fixtures.

It directly covers:

1. real `*.sqlite3` ignore semantics;
2. exactly 17 Git-visible files plus 2 ignored SQLite files;
3. complete 19-file manifest PASS;
4. deterministic digest including ignored files;
5. extra ignored SQLite file inside the approved migration package blocks;
6. extra ignored file under another `operator-runs/` package blocks;
7. ignored manifest file missing from the filesystem blocks;
8. ignored filesystem file omitted from the manifest blocks;
9. tracked file beneath `operator-runs/` blocks;
10. visible extra outside `operator-runs/` blocks;
11. visible extra inside `operator-runs/` blocks;
12. symlink file blocks;
13. symlink directory blocks without traversal;
14. non-regular FIFO blocks where supported;
15. manifest path classified by neither Git set blocks;
16. visible/ignored classification overlap blocks;
17. unrelated ignored SQLite content outside `operator-runs/` is not authorized;
18. validation performs no network access;
19. existing authorization and marker failure laws remain fail-closed;
20. marker digest mismatch blocks;
21. exact manifest schema remains enforced;
22. duplicate manifest path blocks;
23. direct size/hash validation remains enforced;
24. staged and unstaged tracked changes remain blocked;
25. external manifest/marker requirement remains enforced;
26. bounded summary remains filename-free.

The existing validator/integration, embedded Git-provenance, and public operational command tests were also included in the bounded proof.

## 7. Independent external proof-record verification

The operator-uploaded proof record was independently read, parsed, and rehashed during this closeout.

### 7.1 Identity

| Field | Verified value |
| --- | --- |
| Execution ID | `V2_9_8B_WINDOW_15M_IGNORED_EVIDENCE_DISPOSABLE_PROOF_20260801T231732Z` |
| Schema | `PRINTER_V1_V2_9_8B_IGNORED_EVIDENCE_DISPOSABLE_PROOF_V1` |
| File size | `172156` bytes |
| SHA-256 | `33d2e42b640fd8cbef77af215491efc653bbf0c0ef6d6daf885770da8cf36705` |
| Recorded branch | `agent/v2-9-8b-window-15m-ignored-evidence-visibility-repair-disposable-proof` |
| Recorded HEAD | `32ec6467d08165637015d5775d5ba6e2180a74af` |

The independently calculated SHA-256 matched the prior recorded digest exactly.

### 7.2 Compilation and tests

- in-memory compile return code: `0`;
- compile errors: none;
- pytest return code: `0`;
- passed tests: `94`;
- blockers: none.

### 7.3 Exact committed blob identity

All seven proofed working files matched their committed Git blobs:

- production authorization-manifest validator;
- canonical Git-provenance helper;
- public operational Memory Factory command;
- original validator/integration tests;
- new ignored-evidence tests;
- embedded Git-provenance tests;
- public operational command tests.

Blob matches: `7 of 7`.

### 7.4 Accepted evidence invariance

- expected evidence count: `19`;
- before count: `19`;
- after count: `19`;
- before and after inventories: exactly equal;
- every path retained the same size, `mtime_ns`, and SHA-256;
- both ignored SQLite backups remained present and unchanged.

### 7.5 Authoritative database invariance

The authoritative database was not opened through SQLite.

Before and after matched exactly:

- size: `65671168` bytes;
- `mtime_ns`: `1785617072867102156`;
- no `-wal`, `-shm`, or `-journal` sidecar;
- authoritative SQLite connection attempts: `0`;
- unknown SQLite target attempts: `0`.

The 22 recorded SQLite connections were disposable temporary test databases only.

### 7.6 Runtime guards and capability locks

- network attempts: `0`;
- forbidden launcher/campaign subprocess attempts: `0`;
- provider calls: `0`;
- Source Governor calls: `0`;
- Scheduler calls: `0`;
- campaign calls and real campaign invocations: `0`;
- memory calls: `0`;
- retrieval calls: `0`;
- decision calls: `0`;
- position calls: `0`;
- trade calls: `0`;
- paper audit calls: `0`;
- PnL calls: `0`.

Tracked status was clean before and after. The ignored source/test inventory was exactly equal before and after. Bytecode and pytest cache writes were disabled.

## 8. Earlier proof-harness failures

Three earlier local invocations failed because of proof-runner defects:

1. missing `textwrap` import;
2. an over-broad socket monkeypatch that broke Python SSL imports;
3. an over-broad SQLite guard that rejected disposable test databases.

They stopped fail-closed and did not establish a Printer implementation failure.

The final path-aware proof runner corrected those harness defects without changing Printer source, tests, accepted evidence, the authoritative database, or operational state.

The successful immutable proof record supersedes the failed harness attempts for the PASS conclusion. The failed records should remain preserved as historical proof-harness evidence.

## 9. Money-usefulness contribution

The closeout confirms that the prior deterministic 19-manifest-versus-17-visible mismatch has a narrow, fail-closed repair.

Printer can retain the full audit package, including the two ignored SQLite backups, without allowing extra visible or ignored evidence to pass silently. This reduces the risk of consuming another scarce one-shot authorization on the same pre-runtime provenance blocker.

This is operational-readiness support only. It does not create a market signal, clean memory, retrieval result, paper decision, position, trade, or profit claim.

## 10. What this closeout improves

- independently confirms design-to-code fidelity;
- independently confirms implementation scope discipline;
- independently confirms proof scope discipline;
- confirms real `*.sqlite3` ignore semantics are covered;
- confirms all 19 authoritative-shaped evidence files can be represented;
- confirms extra visible and ignored evidence remains fail-closed;
- confirms accepted evidence and authoritative database invariance;
- confirms no operational or financial capability activation occurred;
- clears the repair sequence to proceed to repeated authoritative readiness audit.

## 11. What remains locked

This closeout does not unlock:

- production one-shot wrapper construction;
- any fresh authorization;
- providers, RPC, WebSockets, or source fetching;
- discovery or Scheduler runtime;
- a real `WINDOW_15M` campaign;
- memory generation or promotion;
- retrieval;
- dirty-memory decision use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallet, private key, signing, real funds, live execution, or paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently unlock retrieval, decisions, positions, trades, audits, or PnL.

Solana-only, Solana memecoin-only, and paper-only V1 restrictions remain unchanged.

## 12. Proof still required before authorization

The next required step is a repeated authoritative readiness audit against the preserved real repository state and all 19 accepted evidence files.

That audit must independently confirm:

1. 19-file recursive evidence inventory remains exact;
2. Git-visible count remains 17 and scoped ignored count remains 2;
3. both ignored SQLite files remain exact by size and SHA-256;
4. the repaired production validator's set model is compatible with the real repository state;
5. no extra visible or ignored evidence exists;
6. tracked tree remains clean;
7. authoritative database remains unchanged;
8. no wrapper, marker, authorization, provider, Scheduler, campaign, memory, retrieval, or financial activity occurs.

Only after that audit returns PASS may a separate wrapper-construction or final-authorization readiness lane be considered under the active build order.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Independent closeout disposition |
| --- | --- |
| Repair becomes a generic ignored-file bypass | Closed by scoped ignored query plus complete `operator-runs/` equality |
| Extra ignored file under approved package | Closed by ignored-set and filesystem-inventory negative tests |
| Extra ignored file under another package | Closed by complete namespace inventory and negative test |
| Visible untracked drift | Existing whole-repository visible query remains fail-closed |
| Tracked evidence accepted as untracked | Classification and inventory reconciliation block it |
| Symlink or non-regular entry | No-follow inventory blocks it |
| Manifest/marker schema drift | Existing schemas and exact-key validation preserved |
| Six-field provenance payload drift | Canonical helper remained unchanged and proofed |
| Evidence mutation during proof | 19-file exact before/after equality passed |
| Authoritative DB mutation | No authoritative connection and exact stat equality passed |
| Harness defects create false implementation failures | Historical failures identified; final corrected proof passed |
| Closeout overclaims authoritative readiness | Prevented; repeated authoritative audit remains mandatory |
| Runtime race between validation and future marker creation | Remains a future wrapper/readiness concern; no wrapper exists in this lane |
| Full repository regression suite not run | Acceptable under risk-based verification; focused boundary plus integration contracts produced 94 PASS tests |

## 14. Closeout decision

No implementation blocker, proof blocker, scope violation, safety weakening, or roadmap violation was found.

The repair is independently accepted for progression to authoritative readiness re-audit.

It is not accepted as authorization to run the real campaign.

## 15. Exact next lane

`V2-9.8B WINDOW_15M Repeated Post-Repair Authoritative Readiness Audit`

Type: audit-only, read-only, documentation-only.

Allowed:

- static source and test inspection;
- recursive read-only evidence inventory;
- scoped read-only Git-visible and Git-ignored inspection;
- read-only file size and SHA-256 verification;
- authoritative database file-stat verification without SQLite open;
- readiness audit documentation.

Not allowed:

- wrapper construction;
- marker creation;
- fresh authorization;
- provider or source fetching;
- discovery;
- Scheduler runtime;
- campaign execution;
- database mutation;
- memory generation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.
