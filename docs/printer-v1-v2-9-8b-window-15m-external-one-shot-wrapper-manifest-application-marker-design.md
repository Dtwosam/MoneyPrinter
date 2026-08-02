# Printer V1 V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Design

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Design`

Lane type: design/specification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_EXTERNAL_ONE_SHOT_WRAPPER_MANIFEST_APPLICATION_MARKER_DESIGN_PASS`

A narrow implementation is approved for the missing production launch boundary between a fresh final authorization and the existing ordinary `WINDOW_15M` operational command.

The approved design does not replace the production validator or Memory Factory command. It adds one external one-shot owner that:

1. builds the exact current-evidence manifest;
2. completes all reusable pre-marker validation;
3. publishes the manifest outside the repository;
4. creates one create-once application marker as the authorization-consumption event;
5. revalidates the complete manifest/marker pair;
6. injects the four exact bindings into one child process only;
7. launches the existing ordinary `run` command once;
8. records one truthful external terminal result;
9. never retries, resumes, restarts, or creates a successor.

No implementation was performed in this lane. No manifest, marker, wrapper artifact, authorization, provider call, Scheduler action, campaign, database connection, memory, retrieval, decision, position, trade, audit, or PnL action occurred.

## 2. Controlling source stack

This design follows the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-9-8b-window-15m-post-authoritative-readiness-roadmap-review.md`
- `docs/printer-v1-v2-9-8b-window-15m-current-vs-historical-operator-runs-trust-boundary-repair-design.md`

The active memory-growth build order remains part of this stack and is not the sole source of truth.

The required progression remains:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout report`

## 3. Exact design baseline

| Item | Value |
| --- | --- |
| Design branch | `agent/v2-9-8b-window-15m-external-one-shot-wrapper-manifest-marker-design` |
| Starting HEAD | `3d809ed457b5dcaa47a836daa2344707981496a7` |
| Roadmap-review verdict | `V2_9_8B_WINDOW_15M_POST_AUTHORITATIVE_READINESS_ROADMAP_REVIEW_PASS` |
| Readiness-audit verdict | `V2_9_8B_WINDOW_15M_REPEATED_POST_TRUST_BOUNDARY_REPAIR_AUTHORITATIVE_READINESS_AUDIT_PASS` |
| Current namespace | 11 tracked historical + 19 current untracked = 30 |
| Current untracked split | 17 visible + 2 ignored SQLite |
| Prior authorization | consumed, historical-only, not reusable |

Static inspection confirms:

- `git_provenance_authorization_manifest.py` validates the approved manifest and marker schemas;
- `operational_memory_factory_command.py` consumes the four exact environment bindings;
- the public PowerShell launcher does not construct or supply those bindings;
- production has no manifest builder, marker builder, or atomic one-shot launcher;
- manifest and marker constructors exist only in disposable tests;
- the existing operational integration treats the bindings as optional, so a direct ordinary `run` is not yet technically forced through the wrapper.

## 4. Design goal

Provide one auditable, fail-closed production owner for applying one fresh exact-HEAD authorization to one ordinary `WINDOW_15M` child invocation.

The wrapper is not:

- a second Memory Factory;
- a Scheduler;
- a Source Governor;
- a campaign recovery owner;
- a provider selector;
- a retry supervisor;
- an artifact repair tool;
- a database preflight replacement;
- a memory or trading feature.

It owns only the pre-process authorization application boundary.

## 5. Approved architecture

### 5.1 Canonical Python owner

Add one production module:

`src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`

Python is the canonical owner because the required work is deterministic JSON construction, SHA-256 calculation, no-follow filesystem inspection, atomic file publication, exact subprocess environment construction, and disposable unit testing.

The module must not import provider, discovery, Scheduler-runtime, campaign-owner, memory, retrieval, or paper-trading modules.

### 5.2 Thin PowerShell entrypoint

Add one thin launcher:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

It may accept only:

- the exact final-authorization JSON path;
- its expected SHA-256;
- explicit `-OperatorApproved`.

It must resolve the repository interpreter and invoke the canonical Python wrapper. It must not construct JSON, enumerate evidence, calculate digests, set the four child variables itself, select providers, alter duration, or invoke the Memory Factory directly.

### 5.3 Existing operational command

The existing operational module remains the only Memory Factory runtime owner:

`printer_v1.operator_cli.operational_memory_factory_command`

The wrapper launches exactly:

```text
python -m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved
```

No other mode is allowed.

### 5.4 Direct-run bypass prevention

The implementation must change the ordinary Python `run` boundary so that `run --operator-approved` fails closed unless the complete external manifest/marker authorization resolves successfully.

`preflight-only`, `status`, `cooperative-stop`, `report-only`, and other existing non-run modes retain their existing contracts unless a focused test proves an unavoidable conflict.

Blocking direct `run` in Python is required. Blocking only in PowerShell is insufficient because direct module invocation would remain a bypass.

## 6. Wrapper input contract

The wrapper accepts exactly:

1. `authorization_file`
   - repository-relative or absolute path resolving beneath:
     `operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/final_authorization.json`;
2. `authorization_sha256`
   - lowercase 64-character SHA-256 supplied by the fresh authorization lane;
3. `operator_approved`
   - explicit true switch.

The wrapper accepts no:

- arbitrary repository path;
- database path;
- artifact root override;
- manifest path;
- marker path;
- file list;
- mode override;
- token or pair;
- provider or endpoint;
- duration;
- request ceiling;
- retry flag;
- resume flag;
- recovery flag.

The final authorization JSON must contain, at minimum:

- `authorization_id`;
- PASS verdict;
- exact authorized branch and 40-character HEAD;
- `migration_execution_id`;
- ordinary command mode `run`;
- `operator_approved: true`;
- `allowed_invocation_count: 1`;
- all retry/rerun/resume/restart/successor flags false;
- campaign main window `WINDOW_15M`;
- selective 1h continuation false.

Existing validator-required fields remain unchanged. Wrapper-specific required fields may be additional authorization-document fields; the approved manifest and marker schemas must not change.

## 7. Fixed external artifact location

Use the fixed operator-controlled root:

`~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/<authorization_id>/`

The operator cannot override this root.

Canonical files:

- `git-provenance-manifest.json`
- `application-marker.json`
- `child-stdout.txt`
- `child-stderr.txt`
- `wrapper-terminal.json`

Optional pre-marker diagnostic staging may exist only beneath:

`~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/`

The canonical authorization directory must be created exclusively. A pre-existing canonical directory, final manifest, marker, or terminal record blocks.

Directory permissions should be owner-only where the platform supports them. Artifact files should be read-only after successful publication.

No secret, API key, bearer token, full endpoint credential, private key, wallet, or environment dump may be written.

## 8. Deterministic manifest construction

The wrapper builds `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` without changing its schema.

### 8.1 Exact identities

- authorization root comes from the validated authorization ID;
- migration root comes from the authorization's exact `migration_execution_id`;
- branch and HEAD come from the authorization and must equal live Git state;
- authorization-file path and SHA-256 come from the explicit wrapper inputs.

### 8.2 File enumeration

The wrapper enumerates regular files without following symlinks beneath exactly:

1. `operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/`
2. `operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/`

For every file it records:

- normalized repository-relative POSIX path;
- exact SHA-256;
- exact size;
- exact approved package kind.

Records are sorted by path before canonical JSON serialization.

No filename allowlist, glob, directory count, or historical lane-name heuristic is allowed.

### 8.3 Canonical serialization

Use:

- UTF-8;
- sorted keys;
- deterministic indentation or compact separators chosen once;
- trailing newline;
- no NaN;
- no duplicate keys;
- timezone-aware UTC creation time.

The manifest SHA-256 is calculated over the exact published bytes.

The existing allowed-file-set digest function remains the only file-set digest owner.

## 9. Reusable pre-marker validation

The prior trust-boundary design requires all manifest, Git, file, and namespace checks to pass before marker creation. The current public validator performs those checks and then expects a marker in one call.

The implementation must refactor, not duplicate, that logic.

Add one immutable preparation result, for example:

`PreparedGitProvenanceAuthorization`

It should contain only the values required to construct and later validate the marker:

- current allowed untracked paths;
- authorization ID;
- authorization-document SHA-256;
- manifest SHA-256;
- allowed-file-set SHA-256;
- exact branch;
- exact HEAD;
- file count.

Add one reusable function, for example:

`validate_git_provenance_manifest_pre_marker(...)`

It must perform all existing work through allowed-file-set digest calculation, including:

- external manifest path and hash;
- exact schema and duplicate-key rejection;
- live branch/HEAD;
- staged and unstaged cleanliness;
- final authorization validation;
- direct file path/size/hash validation;
- visible, ignored, tracked, current-root, and complete inventory reconciliation;
- `F == T union M`;
- `C == M`;
- symlink and non-regular rejection;
- current allowlist containing only `M`.

The existing `validate_git_provenance_authorization(...)` must call this preparation function and then apply the existing marker validation. Its public parameters, return type, schemas, and behavior remain compatible.

The wrapper must not independently recreate the five-set reconciliation.

## 10. Manifest publication

The wrapper may build candidate bytes in memory and write them to a unique staging directory.

After pre-marker validation passes:

1. create the canonical authorization directory with create-new semantics;
2. atomically publish the validated manifest from the same filesystem;
3. fsync the manifest and containing directory where supported;
4. calculate and recheck the final published hash;
5. make the manifest read-only.

A partial final manifest must never be treated as valid.

If publication fails before any marker file exists:

- authorization is not consumed;
- no child starts;
- no automatic cleanup or retry occurs;
- preserve enough external diagnostic identity for an operator review;
- a later application requires an explicit new operator action.

## 11. Marker and authorization-consumption boundary

The existing `PRINTER_V1_APPLICATION_MARKER_V1` schema remains unchanged.

The marker payload is constructed entirely from:

- the pre-marker preparation result;
- exact command `{mode: run, operator_approved: true}`;
- `allowed_invocation_count: 1`;
- all retry/rerun/resume/restart/successor flags false;
- one timezone-aware UTC `authorization_consumed_at`.

### 11.1 Exact consumption event

Authorization becomes consumed when creation of the canonical marker path succeeds with create-new semantics.

Use an exclusive create operation. Any marker-path existence blocks.

The marker's existence is fail-closed consumption even if:

- its write is interrupted;
- later parsing fails;
- full validation fails;
- the child cannot start;
- the child exits immediately;
- the host disappears.

This avoids an ambiguous "marker exists but authorization is not consumed" state.

### 11.2 After marker creation

Immediately:

1. hash the marker bytes;
2. call the existing complete validator against the published manifest and marker;
3. compare the returned preparation identities with the pre-marker preparation;
4. recheck live exact branch/HEAD and clean tracked state;
5. launch at most one child.

Any mismatch consumes the authorization and blocks without a child.

No marker deletion, replacement, rewrite, repair, or second marker is allowed.

## 12. Child-process contract

The wrapper creates a fresh child environment dictionary.

It must:

1. copy the parent environment without mutating `os.environ`;
2. remove all four provenance binding variables first;
3. insert exactly:
   - `PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH`
   - `PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256`
   - `PRINTER_V1_APPLICATION_MARKER_PATH`
   - `PRINTER_V1_APPLICATION_MARKER_SHA256`;
4. pass the dictionary only to one direct subprocess;
5. use `shell=False`;
6. use the exact repository interpreter;
7. use repository root as working directory;
8. redirect stdout/stderr to the canonical external files;
9. wait for the one child to terminate;
10. never call the child command again.

The wrapper must not set these variables globally or leave them in the parent process.

The child receives no wrapper-only authorization hash argument or arbitrary file list.

## 13. Terminal record

After the one child attempt, create one immutable `wrapper-terminal.json` containing only safe operational identity:

- wrapper schema/version;
- authorization ID;
- manifest and marker paths/hashes;
- authorized branch/HEAD;
- wrapper execution ID;
- child command identity;
- child-start attempted true/false;
- child PID when available;
- start/end timestamps;
- exit code or process-start error;
- stdout/stderr file hashes and sizes;
- retry/rerun/resume/restart/successor counts, all zero;
- parent environment-clean confirmation;
- terminal classification.

It must not reinterpret campaign success. The Memory Factory's own terminal evidence remains authoritative for campaign outcome.

A zero child exit is not by itself a clean-memory or campaign PASS.

## 14. Failure law

### 14.1 Before marker creation

- no authorization consumption;
- no child;
- no source, Scheduler, campaign, or DB work;
- no automatic retry;
- preserve diagnostic state;
- require explicit operator review before another application.

### 14.2 After marker creation but before child start

- authorization consumed;
- no second child;
- no retry or replacement marker;
- terminal classification records `CONSUMED_CHILD_NOT_STARTED`;
- proceed only to independent closeout.

### 14.3 Child nonzero exit

- authorization consumed;
- exactly one child attempt;
- no automatic or manual rerun under the authorization;
- preserve output and terminal identity;
- proceed to independent closeout or separately authorized recovery audit.

### 14.4 Host disappearance

Marker existence remains the durable consumption fact.

No wrapper relaunch may infer permission from a missing terminal record. A later read-only audit must classify the state.

## 15. Current-evidence rollover prerequisite

The wrapper implementation does not solve historical evidence rollover.

The future authoritative launch shape must still satisfy:

`F == T union M`

Before a fresh authorization package can become current:

- the consumed authorization package must no longer remain unexplained untracked evidence;
- it must be preserved through a separately approved historical-evidence rollover method, normally exact Git tracking at the next authorized HEAD;
- it must not be deleted, silently relocated, inserted into the fresh manifest, or treated as reusable authority.

The accepted migration-050 evidence package may remain current across a later authorization only when the fresh authorization explicitly binds the same migration execution ID and a fresh readiness audit proves every file identity unchanged. Otherwise it also requires approved rollover.

This prerequisite must be resolved before fresh authoritative readiness and authorization. It does not block disposable wrapper implementation and proof.

## 16. Approved implementation scope

The implementation lane may change only:

1. new:
   `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`;
2. narrow refactor:
   `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
3. narrow run-required guard:
   `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
4. new thin launcher:
   `scripts/Start-PrinterV1-Window15M-OneShot.ps1`;
5. focused disposable tests;
6. one implementation report.

The existing generic PowerShell launcher should remain otherwise unchanged.

No migration, DB code, Source Governor, Scheduler, provider, discovery, campaign, memory, retrieval, decision, position, trade, audit, or PnL code is in scope.

Any unavoidable need to change manifest or marker schemas, final-authorization semantics, campaign runtime, or evidence rollover must stop implementation for a separate design review.

## 17. Minimum sufficient implementation tests

Use temporary Git repositories, temporary external artifact roots, fake authorization documents, and fake child executables only.

Required positive tests:

1. exact historical/current shape prepares successfully;
2. deterministic manifest records and SHA-256;
3. pre-marker result equals full-validator result;
4. marker is created once and binds exact values;
5. exactly one child receives the four variables;
6. parent environment remains unchanged;
7. exact child command/cwd/shell contract;
8. stdout/stderr and terminal record are immutable;
9. ordinary direct `run` without bindings blocks.

Required negative tests:

10. wrong authorization path or SHA blocks before marker;
11. wrong branch/HEAD or dirty tracked tree blocks before marker;
12. extra visible or ignored file blocks before marker;
13. tracked file in current root blocks;
14. historical mutation blocks;
15. symlink or non-regular entry blocks;
16. partial environment set blocks;
17. pre-existing canonical directory/manifest/marker blocks;
18. manifest publication failure creates no marker or child;
19. marker creation failure creates no child;
20. malformed/partial marker consumes and creates no child;
21. post-marker full-validation mismatch creates no child and no retry;
22. child start failure consumes and creates no successor;
23. child nonzero exit creates no retry;
24. wrapper cannot launch a second child;
25. unsupported mode, DB path, artifact root, duration, provider, or file-list override is unavailable;
26. zero network and zero authoritative SQLite connections during wrapper tests.

Run only focused validator, wrapper, operational-command integration, and launcher-shape checks. Broad suites are reserved for later closeout or pre-live readiness.

## 18. Bounded disposable proof

After implementation, one bounded proof must establish:

- exact committed implementation identities;
- positive 11 tracked + current-manifest shape;
- exact deterministic manifest and marker bytes;
- pre-marker validation before consumption;
- marker create-once consumption;
- one child maximum;
- environment isolation;
- all negative cases in Section 17;
- zero authoritative evidence mutation;
- zero authoritative DB access;
- zero network/provider/Source Governor/Scheduler/campaign/memory/retrieval/decision/position/trade/audit/PnL activity.

The proof must not create a real authorization or run the operational Memory Factory.

## 19. Money-usefulness contribution

This design protects the next scarce one-shot authorization from being consumed by manual artifact assembly, environment leakage, a direct-run bypass, or an ambiguous marker boundary.

It increases the probability that a later approved ordinary `WINDOW_15M` attempt reaches useful paper-only collection.

It creates no market signal, memory, retrieval result, paper decision, position, trade, or profit claim.

## 20. What this design improves

- assigns one canonical launch owner;
- separates construction from existing validation;
- reuses the production trust-boundary logic before marker creation;
- makes marker creation the exact durable consumption event;
- prevents direct ordinary-run bypass;
- isolates child environment bindings;
- proves one child and zero retries;
- preserves truthful failures before and after consumption;
- identifies the current-evidence rollover prerequisite before real authorization.

## 21. What remains locked

- implementation before the approved implementation lane;
- real manifest or marker creation;
- current-evidence rollover;
- fresh readiness or authorization;
- providers, RPC, WebSockets, or source fetching;
- Source Governor or Scheduler runtime;
- campaign execution;
- authoritative database access or mutation;
- memory generation or promotion;
- retrieval;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 22. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Design control |
| --- | --- |
| Wrapper duplicates validator logic | Add reusable pre-marker validator preparation |
| Direct Python run bypasses wrapper | Require complete authorization for ordinary `run` |
| Marker created before full pre-marker checks | Preparation must pass first |
| Marker created after child launch | Prohibited; marker precedes validation and child |
| Partial marker creates ambiguity | Any marker existence consumes |
| Parent leaks bindings | Child-only copied environment |
| Wrapper launches twice | One subprocess call and create-once marker |
| Test builder becomes production authority | New production builder follows approved contract |
| Child exit is called campaign PASS | Wrapper records process truth only |
| Consumed authorization package remains untracked beside fresh package | Separate historical-evidence rollover prerequisite |
| Migration evidence is reused without fresh proof | Fresh authorization and readiness must bind exact identity |
| Implementation expands into campaign/runtime | Stop and redesign |
| Broad tests waste time | Focused tests now; broader verification at closeout/readiness |

## 23. Exact next lane

`V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Implementation`

Type: narrow implementation and focused disposable tests only.

It may not create authoritative artifacts, issue authorization, contact providers, run Source Governor or Central Scheduler, execute a campaign, open or mutate the authoritative database, generate memory, activate retrieval, or unlock paper trading.
