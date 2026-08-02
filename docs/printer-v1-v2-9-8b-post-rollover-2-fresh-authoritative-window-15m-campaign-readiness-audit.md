# Printer V1 V2-9.8B Post-Rollover-2 Fresh Authoritative WINDOW_15M Campaign Readiness Audit

Date: 2026-08-02

Linear tracking issue: `DTW-13`

Lane:
`V2-9.8B Post-Rollover-2 Fresh Authoritative WINDOW_15M Campaign Readiness Audit`

Lane type: audit/readiness only.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_FRESH_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_PASS`

The exact current macOS repository state at the required HEAD is ready for a
separate fresh exact-HEAD WINDOW_15M final-authorization lane. The second
current-evidence historical-rollover section closed the prior namespace blocker:
the consumed authorization `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` is now
immutable tracked history at its original path, and Migration-050 is again the
only current evidence package with zero current WINDOW_15M authorization
packages.

This PASS authorizes no campaign and no wrapper application. It created no
authorization, manifest, marker, application, memory, or financial artifact. No
Migration-050 rerun occurred. No provider or source was contacted. No Source
Governor or Central Scheduler runtime started. No SQLite mutation occurred. The
authoritative database and the external consumed application are byte-unchanged
before and after this audit.

## 2. Exact baseline

| Item | Exact value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-post-rollover-2-fresh-authoritative-window-15m-campaign-readiness-audit` |
| Starting/inspected HEAD | `5ff71753f60f355d268ecd35a13f5c78116fb414` |
| Starting commit message | `Close second current evidence historical rollover` |
| Rollover-2 closeout verdict | `V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_INDEPENDENT_CLOSEOUT_2_PASS` |
| Consumed authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Consumed authorization content SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Consumed authorization committed blob | `36f11811b76c9a1f7121f08592642ff984384036` |
| Consumed authorization reusable | `false` |
| Retained migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Only untracked root | `operator-runs/v2-9-8b-authoritative-mig050/` |
| Current WINDOW_15M authorization packages | `0` |

Confirmed before proceeding:

- branch and HEAD are exact;
- tracked worktree and index are clean;
- the only untracked root is `operator-runs/v2-9-8b-authoritative-mig050/`;
- no untracked current authorization package exists;
- the retained Migration-050 evidence was not altered.

## 3. Source-stack review

This audit is governed by the active Printer V1 source stack. Current inspected
identities at this HEAD:

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `d71bdf56518543c9c66bb419c917cf5dc421d61380bb3da8b756c06166af743e` |
| `docs/printer-v1-clean-master-spec.md` | `83d026c2a3ce6d35bd3b4cb67b72ff404a283ded86561597485109204c4cc657` |
| `docs/printer-v1-post-rc-build-order.md` | `c40c1533d1be579c3b07559cbcd58396205da73e674b0b6600beb1bf3cff67e2` |
| `docs/printer-v1-memory-factory-guide.md` | `1325d9bd126e526738e397ec2aee453de77705a15dbc469de048c49cbd4b740d` |
| `docs/printer-v1-current-state-memory-growth-audit.md` | `130d245008d75210f2610e158757b235b33f4737a929b9750e38beaba87edb81` |
| `docs/printer-v1-memory-growth-build-order-v2.md` | `c12f5dcbd8700ec50e0926d3dd14430839575a707c13cf836fc0373e3bc722c1` |
| `docs/printer-v1-python-builder-guide.md` | `1b1487040710d35e7e453254feaaeaca15adf346f9d356fe379c8899efaabe0f` |

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active
memory-growth build order inside this stack and is not the sole source of truth.

The just-in-time interpreter-repair chain (failure audit, repair design,
implementation, bounded proof, independent closeout), the post-interpreter-repair
readiness audit (`DTW-7`, which BLOCKED pending rollover), and the second
current-evidence rollover chain (readiness audit 2, design 2, implementation 2,
bounded proof 2, independent closeout 2 — `DTW-12`) were all reviewed. The prior
`printer-v1-v2-9-8b-window-15m-fresh-authoritative-readiness-audit.md` was used
as procedural precedent only. The read-only SQLite technique, placeholder set,
and URL-validation semantics were taken from the current operational source stack
(`src/printer_v1/operator_db/status.py`,
`src/printer_v1/sources/operational_source_contracts.py`) and the
post-migration campaign-readiness audit's established query set.

Preserved governance boundaries: Source Governor owns external-source access;
Central Scheduler owns runtime; source fetching, RPC calls, transaction parsing,
token-age evaluation, and protocol classification remain forbidden in this lane.
No additional protocol/API module was required or loaded.

Required completion pattern remains:

```text
audit/readiness -> design/specification -> implementation -> bounded proof/test -> independent closeout
```

## 4. Git and evidence inventory

| Set | Count |
| --- | ---: |
| Tracked historical `T` | `19` |
| Visible current | `10` |
| Ignored current | `2` |
| Current evidence `M` | `12` |
| Complete inventory `F` | `31` |
| Current WINDOW_15M authorization packages | `0` |

Invariants (all hold):

```text
F == T union M            -> 31 == 19 + 12
T intersect M == empty    -> no path in both sets
M == visible union ignored -> 12 == 10 + 2
```

- The consumed authorization is tracked history at
  `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`;
- its committed blob is `36f11811b76c9a1f7121f08592642ff984384036` (confirmed via
  `git ls-tree HEAD`);
- it remains consumed and permanently non-reusable (external create-once marker
  plus tracked history);
- only Migration-050 remains current evidence;
- the single `final_authorization.json` inside the current namespace is the
  Migration-050 migration-authorization evidence file (a member of `M = 12`), not
  a WINDOW_15M authorization package. Zero untracked
  `window-15m-final-authorization/` current packages exist.

No unexpected current authorization, additional evidence root, collision, or
inventory mismatch was found.

## 5. Migration-050 identity

Read-only hash/stat inspection only. The two retained `.sqlite3` evidence files
were **not opened**; their content SHA-256 values were taken from the accepted
prior evidence record and folded into the identity listing.

- execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`;
- file count: `12`;
- symlink count: `0`;
- non-regular entry count: `0`;
- both `.sqlite3` evidence files remain ignored and untracked;
- no Migration-050 rerun.

Ten non-SQLite files were freshly re-hashed and are byte-identical to the accepted
record. The sorted `shasum -a 256` identity listing (12 repo-relative paths,
path-sorted, two-space separator, trailing newline) reconstructs to:

`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`

This equals the accepted identity digest, proving the package is unchanged
without opening the migration SQLite files.

## 6. Lexical venv / bootstrap proof

Repository entrypoint: `<repo>/.venv/bin/python`.

One harmless finite-timeout `-c` subprocess was launched via a Python parent
using `subprocess.run([...], timeout=60, shell=False)`:

- exit code: `0`;
- `shell=False`;
- `sys.prefix` = `/Users/Dtwo1/Developer/MoneyPrinter/.venv`;
- `sys.base_prefix` = `/opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12`;
- `sys.prefix != sys.base_prefix`: `True`;
- active prefix is the repository `.venv`: `True`;
- `find_spec("printer_v1")` non-null: `True`;
- `find_spec("printer_v1.operator_cli.operational_memory_factory_command")` non-null: `True`;
- the operational command was not imported or executed (spec discovery only).

Repaired wrapper inspection
(`src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`, 819 lines):

- the lexical venv path is preserved — the resolver returns the lexical absolute
  `.venv/bin/python` entrypoint and never places the dereferenced target in the
  child command;
- the resolved Homebrew base interpreter is validation evidence only (the
  entrypoint is followed only to validate that it reaches an existing regular,
  executable target);
- direct base-interpreter substitution blocks before staging/marker creation —
  the child interpreter is selected and validated before any staging directory,
  manifest, or marker artifact is created; interpreters outside `<repo>/.venv` or
  whose parent is not the venv `bin` directory are rejected;
- exactly one production `subprocess.Popen` remains (line 392);
- production launch uses `shell=False` (line 398);
- no retry, rerun, resume, restart, or successor path was introduced — those
  tokens appear only as explicit `False` marker flags and zero counters.

### Current launch-chain hashes (computed fresh at this HEAD)

| File | Git blob | SHA-256 | Bytes |
| --- | --- | --- | ---: |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `73d5ac306eee0241dcb3d1b97bd353fa950bd470` | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` | 30802 |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `64b8a305765bb0967ae1f57301d8bcee70db22a3` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` | 42875 |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `70b87bef1add0f203c5d497213ad2c6d8ef52470` | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` | 169566 |

These are the current authorization authority for the next lane. The old consumed
authorization's wrapper hash (`77e35c14...` recorded before the interpreter
repair) is **not** reused as current authority; the current wrapper SHA-256 is
`cb3eb498...`.

## 7. Environment shape (no values exposed)

The approved local secrets environment was already loaded into the session. Only
presence/shape was inspected; no secret value was printed, hashed, partially
printed, or included. Required names were derived from the current operational
source path (`operational_source_contracts.py`, `helius_holder.py`, `commands.py`,
`live_candidate_acquisition_transport.py`) and prior accepted readiness audits.

| Variable | Present | Non-empty | Length | Placeholder | Structural |
| --- | --- | --- | ---: | --- | --- |
| `PRINTER_HELIUS_API_KEY` | yes | yes | 36 | none | valid |
| `SOLANA_TRACKER_API_KEY` | yes | yes | 36 | none | valid |
| `PRINTER_SOLANA_RPC_URL` | yes | yes | 61 | none | valid |

Placeholder detection used the operational marker set
(`your_`, `changeme`, `placeholder`, `<`, `>`, `example.com`).

RPC URL structural validity (value never printed):

- URL parse: OK;
- scheme: `https`;
- hostname: non-empty (hostname length 28);
- userinfo (credentials) present: no;
- fragment present: no;
- port valid: yes (no explicit port);
- placeholder: none.

No endpoint was contacted. All required variables are present, non-placeholder,
and structurally valid — no BLOCKED environment condition.

## 8. Authoritative database reconciliation

Path: `data/printer_v1.sqlite3`.

### 8.1 Pre-open identity

| Field | Value |
| --- | --- |
| Regular file | true |
| Size | `65671168` |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL / SHM / journal | absent / absent / absent |

All match the expected starting identity.

### 8.2 Strict read-only readiness

Connection used the approved technique: SQLite URI `mode=ro` (from
`status.connect_read_only`) plus `PRAGMA query_only = ON`. `journal_mode` is
`delete` for the authoritative DB, so no WAL/SHM was created. No schema or data
mutation, migration execution, or persistent temporary artifact occurred.

Findings:

- `PRAGMA integrity_check`: `ok`;
- `PRAGMA foreign_key_check`: `0` violations;
- migration ledger (`printer_schema_migrations`): count `50`, tip
  `050_campaign_scheduler_ownership_scope.sql`;
- Migration-050 residue: no `__v2_9_8b_050%` replacement-table objects, no
  `_mig050_guard_%` objects;
- schema: `printer_memory_factory_campaign_scheduler_work` has all post-050
  columns (`ownership_contract_version`, `stage_id`, `work_scope`,
  `target_category`, `target_identity`, `factory_run_id`); required indexes
  (`idx_campaign_work_owner`, `idx_campaign_work_scheduler_job_unique`,
  `idx_campaign_work_scope_stage`) present; required triggers
  (`printer_campaign_work_identity_immutable`,
  `printer_campaign_work_provenance_insert`) present; table holds `0` rows —
  correct pre-campaign state.

Runtime residue / active work:

| Surface | State |
| --- | --- |
| Scheduler-owned campaign work | `0` rows |
| Active scheduler jobs (`RUNNING` or locked) | `0` |
| Running scheduler jobs | `0` |
| Campaigns | 19 rows, all terminal (`TERMINAL_COMPLETED` 12 / `TERMINAL_FAILED` 7) |
| Campaign runs | 19 rows, all terminal (12 / 7) |
| Campaign supervision | 19 rows, all `TERMINAL`; unreleased leases `0`; uncleaned `0` |
| Discovery work | 72 rows, all terminal (`SUCCEEDED` 70 / `FAILED` 2) |
| Factory run steps | 72 rows, all terminal (`SUCCEEDED` 60 / `CANCELLED` 12) |
| Proof run supervision | `0` rows |
| Candidate acquisition leases | 19 rows, all `TERMINAL`; unreleased `0`; cancellation-pending `0` |

No active campaign, no active lifecycle/window, no active Scheduler-owned work,
no live lease/lock requiring recovery, no orphaned authoritative work, and no
runtime residue that would conflict with a future `WINDOW_15M` attempt.

Protected capability counters (all `0`, unchanged): `printer_paper_positions`,
`printer_paper_trade_events`, `printer_paper_decision_audits`,
`printer_paper_trade_audits`, `printer_memory_retrieval_matches`.

Protected preserved records (unchanged from the migration-application closeout
baseline): `printer_memory_windows` 162, `printer_episodes` 59,
`printer_memory_retrieval_queries` 10, `printer_paper_decisions` 2,
`printer_paper_audit_reports` 1, `printer_paper_quote_evidence` 32,
`printer_scheduler_jobs` 1365, `printer_source_requests` 1748,
`printer_source_responses` 1609, `printer_source_failures` 139. Their presence is
preserved history, not retrieval or paper-trading activation.

### 8.3 Post-close identity

After closing the connection, DB identity and sidecars were recomputed:

| Field | Before | After | Equal |
| --- | --- | --- | --- |
| Size | `65671168` | `65671168` | yes |
| SHA-256 | `56ca1218…d4c8eed5` | `56ca1218…d4c8eed5` | yes |
| `mtime_ns` | `1785617072867102156` | `1785617072867102156` | yes |
| WAL / SHM / journal | absent | absent | yes |

Exact before/after equality holds. No mutation, sidecar creation, integrity
issue, FK issue, unexpected migration state, or runtime residue.

## 9. External consumed-application preservation

Read-only hash/stat inspection only, at:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

- five immutable application files (`application-marker.json`, `child-stderr.txt`,
  `child-stdout.txt`, `git-provenance-manifest.json`, `wrapper-terminal.json`),
  all mode `0444`, `0` symlinks;
- the preserved historical empty staging directory
  `.staging/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d`
  remains under the application parent;
- complete application-parent digest reproduced exactly:
  `f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`
  (sorted `shasum -a 256` listing over the five files as absolute paths, then
  hashed);
- the application marker still proves consumption: `authorization_consumed_at`
  `2026-08-02T11:34:17.389120+00:00`, `allowed_invocation_count` `1`,
  `authorization_sha256` `af63b05423c4…d55c60`, and
  `automatic_retry_allowed` / `manual_rerun_allowed` / `resume_allowed` /
  `restart_allowed` / `successor_allowed` all `false`.

No attempt was made to reuse, remove, repair, or alter it.

## 10. Capability locks

Statically confirmed:

- the only possible future main window is `WINDOW_15M`
  (`REQUIRED_MAIN_WINDOW = "WINDOW_15M"`, enforced in the manifest validator);
- `WINDOW_5M_MICRO_EVENT` remains support-only (`cadence_policy`: "support-only;
  never a main clean-memory window");
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` remain locked
  (`selective_1h_continuation` forced `false`; no longer-window main path);
- Source Governor owns external-source access;
- Central Scheduler owns runtime;
- no direct operational-command bypass (single wrapper launch site, `shell=False`);
- no provider rotation, no paid API dependency, no retrieval activation, no paper
  decisions, no BUY/SELL/HOLD, no positions/trades/audits/PnL, no wallets/private
  keys/real funds/live execution;
- no scoring, ranking, confidence, weighting, embeddings, or vectors introduced.

Printer remains Solana-only, Solana-memecoin-only, and paper-only.

## 11. Money-usefulness contribution

This readiness audit protects scarce one-shot authorization capacity. By
confirming — at the exact current HEAD — that the consumed authorization is now
immutable tracked history, that the current namespace holds only the retained
Migration-050 package, that the repaired lexical-venv bootstrap resolves, that the
approved secrets are shaped correctly, and that the authoritative DB is clean with
zero active runtime residue, it reduces the risk of losing another scarce
authorization to namespace collision, stale Git identity, bootstrap failure,
malformed configuration, or runtime-residue conflict before useful market
collection begins.

It creates no memory, market signal, paper decision, trade, or profit claim.

## 12. What this audit improves

- confirms the second rollover closed the prior namespace blocker at the exact
  HEAD;
- proves current WINDOW_15M authorization package count is zero;
- freshly re-verifies Migration-050 identity without opening SQLite evidence;
- freshly verifies the repaired lexical-venv bootstrap and records **current**
  launch-chain hashes as the authorization authority;
- adds environment-shape and read-only DB integrity/FK/migration/residue evidence
  that the previous procedural precedent deferred;
- preserves DB and external application evidence with exact before/after identity.

## 13. What remains locked

This PASS does not unlock a fresh authorization, manifest or marker creation,
wrapper application, provider/source access, Source Governor or Central Scheduler
runtime, campaign execution, authoritative SQLite mutation, memory generation or
retrieval, paper decisions or BUY/SELL/HOLD, positions/trades/audits/PnL,
`WINDOW_1H`/`WINDOW_4H`/`WINDOW_12H`/`WINDOW_24H`, or wallets/private keys/real
funds/live execution/paid APIs.

## 14. Proof required before any future application

Before a wrapper application:

1. a fresh exact-HEAD final authorization must be created binding this
   readiness-audit commit and branch, with a new authorization ID distinct from
   `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`;
2. it must bind migration execution ID
   `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` and the exact twelve
   retained migration file identities;
3. it must authorize exactly one ordinary `run` invocation with explicit operator
   approval, with automatic retry, manual rerun, resume, restart, and successor
   all `false`, main window `WINDOW_15M`, selective 1h continuation `false`;
4. the authorization package must receive an independent exact-scope review;
5. the namespace must reconcile as tracked history plus both current packages, and
   no manifest or marker may exist before the wrapper creates them;
6. the DB and external application identities must be revalidated unchanged;
7. the wrapper command must be issued exactly once by the operator.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Audit disposition |
| --- | --- |
| This audit commit changes HEAD | Fresh authorization must bind the post-audit exact HEAD, not `5ff71753` |
| Reusing the consumed authorization | Impossible; tracked history plus external create-once marker prove permanent consumption |
| Migration-050 or DB drift after PASS | Any drift must re-block authorization or application |
| Old wrapper hashes mistaken for current authority | Prevented; current launch-chain hashes recomputed at this HEAD (`cb3eb498…`) |
| Secrets exposed during shape check | Prevented; only presence/length/validity booleans recorded |
| Read-only DB check leaving residue | None; `mode=ro` + `query_only`, exact before/after identity, no sidecars |
| Natural source availability / clean-memory yield | Still unproven; belongs to later authorized runtime, not this lane |
| Windows symlink-test portability | Separate residual interpreter-test limitation; unrelated to this readiness PASS |

## 16. Roadmap decision

- second rollover section closed: `true`;
- fresh campaign readiness passed: `true`;
- current-evidence namespace blocker present: `false`;
- fresh exact-HEAD final-authorization lane authorized: `true`;
- fresh authorization created by this audit: `false`;
- wrapper application authorized: `false`;
- campaign authorized: `false`;
- real `WINDOW_15M` command authorized: `false`.

## 17. Exact next lane

`V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization`

That next lane may create exactly one new current authorization package bound to
the post-readiness commit and branch. It must be independently reviewed before any
separately approved one-shot wrapper application. A readiness PASS authorizes no
campaign and no wrapper application.
