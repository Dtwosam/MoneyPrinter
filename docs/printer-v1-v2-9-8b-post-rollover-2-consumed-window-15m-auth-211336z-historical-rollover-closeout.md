# Printer V1 V2-9.8B Post-Rollover-2 Consumed WINDOW_15M Authorization `…211336Z` Historical Rollover Closeout

Date: 2026-08-03

Lane:

```text
V2-9.8B Post-Rollover-2 Consumed WINDOW_15M Authorization Historical Rollover
```

Authorization:

```text
V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z
```

Lane type: bounded design/readiness, historical-evidence rollover, exact-set
proof, and closeout. No source/test edit, provider contact, wrapper execution,
authorization creation, campaign, DB mutation, or memory-window start.

## 1. Verdict

```text
V2_9_8B_POST_ROLLOVER_2_CONSUMED_WINDOW_15M_AUTH_211336Z_HISTORICAL_ROLLOVER_PASS
```

Readiness classification (after successful proof):

```text
READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION
```

The consumed eight-file repository package is now immutable tracked historical
evidence at its existing path. Migration-050 is the only remaining Git-visible
current evidence package. External application and campaign artifacts are
preserved unmodified. Authoritative DB identity and launch-chain hashes are
unchanged. No new authorization was created.

## 2. Baseline

| Item | Value |
| --- | --- |
| Required / start HEAD | `d6ffe22723de7524d1ddca5d788e452fe8758f56` |
| Start subject | `Audit repaired authoritative 15m readiness` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked / staged trees at start | Clean (only untracked operator evidence) |
| Relevant Printer processes | None |
| `/private/tmp/mp-preclaim` | Detached `8fb4256c70d4e81660c177238253322cb37ae947` — untouched |
| Push | Not performed |

Controlling readiness source for this rollover:

`docs/printer-v1-v2-9-8b-post-rollover-2-repaired-authoritative-window-15m-current-head-readiness-audit.md`

That audit classified:

```text
READY_FOR_CONSUMED_AUTHORIZATION_HISTORICAL_ROLLOVER
```

and named this lane as the exact next permitted preparation step.

## 3. Bounded design / readiness

### 3.1 Intent

Convert the consumed authorization package from Git-visible untracked current
evidence into tracked historical evidence **without** rewriting bytes, renaming
paths, regenerating content, or touching external application/campaign/DB
surfaces.

### 3.2 Scope (allowed)

| Action | Allowed |
| --- | --- |
| `git add` the exact eight existing package files at their current paths | Yes |
| Record closeout proof documenting hashes and exact-set equality | Yes |
| Preserve Migration-050 as the only remaining current untracked evidence | Yes |

### 3.3 Scope (forbidden)

| Action | Forbidden |
| --- | --- |
| Rewrite / regenerate / rename / move package files | Yes (not done) |
| Modify source, tests, wrapper, authorization law, runtime data | Yes (not done) |
| Create authorization, marker, staging directory, campaign | Yes (not done) |
| Contact providers / run wrapper / start memory window | Yes (not done) |
| Mutate authoritative DB or Migration-050 package | Yes (not done) |

### 3.4 Design readiness gates (pre-implementation)

| Gate | Result |
| --- | --- |
| Package present at established path | PASS |
| Exactly eight files | PASS |
| All eight SHA-256 match readiness-audit recorded hashes | PASS |
| Consumed + permanently non-reusable (marker/wrapper evidence) | PASS |
| External application directory present and immutable | PASS |
| Campaign artifacts present; lease lock absent | PASS |
| Authoritative DB identity matches readiness audit | PASS |
| Zero active/locked runtime residue | PASS |
| Launch-chain hashes match repair HEAD | PASS |
| No Printer process; `mp-preclaim` untouched | PASS |

Design readiness: **PASS** — proceed to historical rollover.

## 4. Historical rollover action

Method:

```text
git add <exact eight existing files at established path>
```

No file content was rewritten, regenerated, renamed, or moved. Transition is
classification-only: untracked current evidence → tracked historical evidence
at the same path.

Root path (unchanged):

```text
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/
```

## 5. Exact files and hashes

| Path (under package root) | Bytes | Mode | SHA-256 | Match readiness audit |
| --- | ---: | --- | --- | --- |
| `authorization_report.md` | 1439 | `0644` | `e024c1fe67a7013226d5221d76fea2995f0e0d9f8f024a619d5492b26b73b335` | Yes |
| `binding_inventory.json` | 4063 | `0644` | `71897068ba17c730938371b13c7b0a158ce0c32c9236dd923a107f44fa0fa010` | Yes |
| `consumed_on_start_rule.md` | 956 | `0644` | `869c46a0908e23e203d93c82ca8a59e442e761b1d40d3671bbd7041d9627e311` | Yes |
| `exact_manual_command.md` | 2500 | `0644` | `f923f2b0c31d20999e965ab1beea4799a6c1351c79aa74aea394658d7606effe` | Yes |
| `final_authorization.json` | 13843 | `0444` | `5524ada42b3da1a56516ccbb5cfe821b3414ee0653d516453fd4212cb3439c03` | Yes |
| `final_authorization.sha256` | 91 | `0644` | `5ea3b345f87addc5d5712a988c4fa95fb0c873800a1bfb5c8158a541e7ddfa1e` | Yes |
| `readiness_reference.md` | 950 | `0644` | `2ceeb5d9b3d5396d737b0e8aae430df1073f158a9398f4e7afcacc21ea2803e9` | Yes |
| `stop_conditions.md` | 1518 | `0644` | `85eae383abc7191b050b67e9f70667d20f803383d3ad9b23a4d9fbad01bf8e23` | Yes |

All eight files match their recorded hashes. `final_authorization.json` remains
immutable (`0444`).

### 5.1 Consumed-state table (post-rollover)

| Authorization ID | Prior state | Post-rollover state | Reusable |
| --- | --- | --- | --- |
| `…20260801T205700Z` | tracked historical | tracked historical | no |
| `…20260802T112358Z` | tracked historical | tracked historical | no |
| `…20260802T210122Z` | tracked historical | tracked historical | no |
| `…20260803T204800Z` | tracked historical | tracked historical | no |
| `…20260803T211336Z` | consumed; Git-visible untracked; external application preserved | **tracked historical** + external application preserved | **no** |
| Live reusable WINDOW_15M authorization | none | **none** | n/a |

Explicit historical marking for `…211336Z`:

- consumed (wrapper execution began; one-shot law);
- permanently non-reusable;
- child exited nonzero (`CHILD_EXITED_NONZERO`, exit code 1) under execution
  HEAD `6bb73ca…` with first operational cause
  `OperationalMemoryFactoryError: initialized factory-run identity changed`
  (since repaired at `7aaa58e…`);
- historical evidence only after this rollover.

No new authorization ID was created.

## 6. Before / after untracked inventories

### 6.1 Before (at start HEAD `d6ffe22`)

Visible untracked (18 paths):

```text
operator-runs/v2-9-8b-authoritative-mig050/… (10 visible Migration-050 files)
operator-runs/…/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/ (8 package files)
```

Ignored `operator-runs` (2 paths):

```text
…/disposable-restore/printer_v1-rehearsal.sqlite3
…/verified-backup/printer_v1-pre050.sqlite3
```

### 6.2 After rollover (post-stage / pre-commit proof)

Visible untracked files equal **exactly** the ten Migration-050 files:

```text
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json
```

Count: **10**. No WINDOW_15M authorization package paths. No `.DS_Store`.

Ignored `operator-runs` files equal **exactly** the two approved Migration-050
SQLite files (both SHA-256
`e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`):

```text
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3
```

`.DS_Store` remains ignored (`.gitignore:22:.DS_Store`) and is not Git-visible
untracked.

## 7. External evidence preservation

### 7.1 Canonical external application directory

Path (unchanged):

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/`

| Artifact | Bytes | SHA-256 | Mode |
| --- | ---: | --- | --- |
| `application-marker.json` | 905 | `49d91b61bcc1a6310b18fe266a8f5dcdf725048031d19640b61d7dd9096f7c00` | `0444` |
| `git-provenance-manifest.json` | 6958 | `c6331641ea1fe1789312a42a64f2f1a02a44f6c71b4de0442e0112f846036da6` | `0444` |
| `wrapper-terminal.json` | 1750 | `5e04cf20543384a520890db583fe19343f30362112b19aa6a0087284ca9e7297` | `0444` |
| `child-stderr.txt` | 383 | `4828f080e4d1142b8d467adc4e0d1e79d30ca1b3d6dcd3fd27ea7f1349ffe821` | `0444` |
| `child-stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0444` |

Not modified by this lane. Marker still records
`authorization_consumed_at=2026-08-03T21:28:01.121959+00:00` and bound execution
HEAD `6bb73ca…`.

### 7.2 Campaign artifacts

Path (unchanged):

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T212801Z-4f7377e702c7/`

Preserved: pre-campaign backup, restore rehearsal, terminal-summary, reports.
`campaign.lease.lock` remains absent. Not modified by this lane.

### 7.3 Migration-050 current evidence

Package
`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/`
remains untracked current evidence (ten visible files + two ignored SQLite
backups). Not modified by this lane. Listing identity digest remains
`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` when
recomputed from the twelve-file package.

## 8. Authoritative DB and residue state

Read-only inspection only. Pre/post open identity identical.

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | `65896448` |
| SHA-256 | `a4a36867f563d3c900c3b5efffe27b0c8eb7191a8a066ab5e944886a50077b7c` |
| inode | `1230526` |
| `mtime_ns` | `1785792510343843917` |
| WAL / SHM / journal | Absent / absent / absent |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | empty (clean) |
| Migration count / head | `50` / `050_campaign_scheduler_ownership_scope.sql` |

Runtime residue:

| Surface | Active/locked residue |
| --- | --- |
| Campaigns non-terminal | 0 |
| Campaign runs non-terminal | 0 |
| Supervision non-terminal | 0 |
| Unreleased leases / missing cleanup | 0 |
| Scheduler lock owners | 0 |
| Scheduler non-terminal jobs | 0 |
| Acquisition non-terminal leases | 0 |
| Relevant Printer processes | none |

## 9. Launch-chain hashes (unchanged from repair HEAD)

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | 878 | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | 42875 | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | 30802 | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | 180667 | `58b65975bf16f745250e7ec3491815d3f878dc984b693eec9d6cec20d9e73df1` |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | 117957 | `6fa736c05cf57de819c2e0f501b9e7e8ef9bbefcb6773ff4268343faf81e9c26` |

All match the post-repair readiness-audit bindings. No source file was modified
by this lane.

Repair HEAD ancestry remains:

```text
7aaa58e615b2d07509f050611df541bc7abc2a38  Repair pre-lifecycle factory identity contract
```

Future fresh authorization must bind the **post-rollover HEAD** (this closeout
commit), the repaired operational-command SHA `58b65975…`, and the current DB
identity `a4a36867…` / size `65896448` / inode `1230526`.

## 10. Exact-set proof

| # | Obligation | Result |
| --- | --- | --- |
| 1 | All eight package files match recorded SHA-256 hashes | **PASS** |
| 2 | Consumed authorization is staged/tracked historical evidence at existing path | **PASS** |
| 3 | Package no longer Git-visible untracked | **PASS** |
| 4 | Visible untracked files equal exactly the ten Migration-050 files | **PASS** |
| 5 | Ignored `operator-runs` files equal exactly the two approved Migration-050 SQLite files | **PASS** |
| 6 | `.DS_Store` remains ignored; not visible untracked | **PASS** |
| 7 | No other authorization package is untracked | **PASS** |
| 8 | Authoritative DB SHA-256 `a4a36867…`, size `65896448`, inode `1230526`, no WAL/SHM/journal | **PASS** |
| 9 | Integrity ok; FK clean | **PASS** |
| 10 | Zero active or locked runtime residue | **PASS** |
| 11 | Launch-chain hashes unchanged from repair HEAD | **PASS** |
| 12 | No new authorization, marker, staging directory, campaign, or provider call | **PASS** |
| 13 | External application + campaign artifacts unmodified | **PASS** |
| 14 | Migration-050 package unmodified and remains sole current evidence | **PASS** |
| 15 | Commit scope limited to eight package files + this closeout | **PASS** (enforced at commit) |

## 11. Readiness classification

```text
READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION
```

Rationale: the only prior blocker for fresh authorization was the consumed
`…211336Z` package remaining Git-visible untracked. That package is now tracked
historical evidence. DB integrity, residue, environment readiness from the
prior audit, launch-chain repair bindings, and Migration-050 sole-current-
evidence precondition are satisfied for the next authorization lane.

This classification does **not** create authorization and does **not** authorize
wrapper execution.

## 12. Money-usefulness contribution

Historical rollover restores a clean exact-set surface so a future one-use
authorization can bind honest current evidence without:

1. reusing a consumed authorization package as if it were current;
2. polluting the untracked exact-set with permanently non-reusable live failure
   residue;
3. forcing another readiness cycle solely for evidence hygiene.

It does not create clean memory, retrieval value, paper decisions, trades, or
PnL. It protects authorization economics after the repaired identity contract.

## 13. What improved

- `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` is immutable tracked historical
  evidence at its established path with byte-identical hashes.
- Git-visible untracked current evidence is reduced to Migration-050 only
  (exact ten-file visible set).
- Fresh one-use authorization is now the lawful next preparation lane under the
  repaired HEAD lineage.
- External terminal artifacts and campaign evidence remain available for audit
  without being reclassified as current authorization authority.

## 14. What remains locked

- retrieval activation
- paper decisions / BUY / SELL / HOLD
- paper positions, trade events, paper audits, PnL
- live wallet / private keys / real funds / live execution
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- reuse of `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` or any prior consumed ID
- wrapper execution, campaign start, and 15m/1h/4h/12h/24h windows until a
  **new** one-use authorization is separately issued and operator-approved
- Migration-050 re-run or authoritative DB rewrite
- source/test/wrapper/authorization-law changes under this closeout

## 15. Functionality Risks / Setbacks / Efficiency Blockers

1. **Fresh authorization still required.** Classification readiness is not
   execution authority. A separate one-use authorization + independent review
   lane must bind post-rollover HEAD, repaired command SHA, and current DB
   identity.
2. **Thin market supply risk remains.** A later authorized attempt may still
   terminalize honestly on `SOURCE_VISIBILITY_SHORTAGE` without 15m collection.
3. **Authoritative DB differs from pre-attempt backup.** Size/hash moved during
   the failed live attempt; future auth must bind current identity, not the
   pre-campaign backup hash, unless a separate restore is explicitly authorized.
4. **Historical tracking-queue noise** may still reduce eligible supply under
   live selection (`DUPLICATE_ACTIVE_TRACKING` / terminal tracking states).
5. **No push.** Remote operators do not yet see this historical package until a
   later operator-approved push.
6. **Offline repair PASS still ≠ live operational proof.** Live proof waits for
   fresh authorization and operator run.

## 16. Exact next lane

```text
V2-9.8B Post-Rollover-2 Repaired Authoritative WINDOW_15M Fresh One-Use Authorization and Independent Review
```

That lane must:

1. bind the **post-rollover HEAD** (this closeout commit);
2. bind the repaired operational-command SHA `58b65975…` and current launch-chain
   set;
3. bind current authoritative DB identity
   (`a4a36867…` / `65896448` / inode `1230526`);
4. prove exact untracked-set equality (Migration-050 ten visible files only)
   before independent review PASS;
5. create at most one new one-use authorization package;
6. create **no** application marker (wrapper-owned), run **no** campaign, and
   start **no** memory window inside the authorization lane itself unless that
   lane’s explicit scope says otherwise — default remains authorization + review
   only until operator-approved execution.

## 17. Stop condition

This lane stops after the rollover commit containing:

1. the exact eight-file historical package;
2. this closeout report.

No authorization creation, wrapper execution, provider contact, or memory-window
start is authorized by this PASS.
