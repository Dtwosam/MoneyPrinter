# Printer V1 V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M Wrapper Provenance Blocker Capture

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M Wrapper Provenance Blocker Capture`

Lane type: read-only inspection and documentation only.

No source changes, package changes, authorization creation, repository cleanup,
provider contact, Scheduler runtime, campaign execution, database mutation,
wrapper rerun, or push was performed by this lane.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_WRAPPER_PROVENANCE_BLOCKER_ROOT_CAUSE_CAPTURED`

Primary classification:

`MULTI_BOUNDARY_AUTHORIZATION_DEFECT`

The one authorized wrapper invocation for
`V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` was blocked by a correct
Git-provenance safe-stop before create-once marker publication and before any
operational child launch. No campaign, discovery, factory, Scheduler, or memory
runtime work was created. The authoritative database identity is unchanged.

The safe-stop itself is **not** a production wrapper defect. The unusable
application state was allowed by incomplete authorization-package allowlist
coverage relative to the preserved untracked worktree, incomplete
independent-review / package-procedure enforcement of untracked-set equality,
and operator-preparation preservation of residual files that the wrapper
manifest law cannot accept outside the allowlist.

## 2. Immutable wrapper result

```text
WINDOW_15M_ONE_SHOT_WRAPPER_BLOCKED
GitProvenanceAuthorizationError
unexpected untracked repository file not covered by manifest:
.DS_Store,
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json
```

Counters recorded by the wrapper terminal JSON (all zero):

| Counter | Value |
| --- | ---: |
| automatic retries | 0 |
| manual reruns | 0 |
| restarts | 0 |
| resumes | 0 |
| successors | 0 |

Error type: `GitProvenanceAuthorizationError`  
Error class meaning: visible Git-untracked repository paths exist that are not
in the authorization-derived provenance manifest allowlist.

This lane does **not** re-invoke the wrapper.

## 3. Invocation command and timestamp

### 3.1 Authorized command (package-bound)

From the authorization package
`exact_manual_command.md` / `final_authorization.json`:

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json `
  -AuthorizationSha256 1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680 `
  -OperatorApproved
```

Equivalent Python entry (same one-shot law):

```bash
./.venv/bin/python -m printer_v1.operator_cli.window_15m_one_shot_wrapper \
  --authorization-file operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json \
  --authorization-sha256 1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680 \
  --operator-approved
```

### 3.2 Observed invocation timing

| Field | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` |
| Package `authorized_at` | `2026-08-03T20:48:00.842758+00:00` |
| Staging manifest `created_at` | `2026-08-03T20:54:00.620958+00:00` |
| Staging path mtime (local) | 2026-08-03 13:54:00 |
| Operator event label | one authorized wrapper invocation; counters all zero |

The residual staging manifest is the durable application-side timestamp of
wrapper progress past child-interpreter selection and into manifest staging /
pre-marker provenance validation.

## 4. Baseline preservation (recorded, not altered)

| Item | Observed at capture |
| --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| HEAD | `e07ff977292d79f36a2067319187a0ad1f17f2f7` |
| Tracked worktree | clean |
| Index / staged | clean (`git diff --cached` empty) |
| Ahead of configured upstream | 16 commits (unchanged by this lane before the report commit) |
| Reset performed | **No** |
| `.DS_Store` relocated/removed | **No** |
| Prior auth package relocated/removed | **No** |

### 4.1 Complete Git-visible untracked inventory (`git ls-files --others --exclude-standard`)

```text
.DS_Store
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
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/authorization_report.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/binding_inventory.json
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/consumed_on_start_rule.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/exact_manual_command.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.sha256
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/readiness_reference.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/stop_conditions.md
```

Git-ignored current Migration-050 SQLite evidence (present on disk; covered by
manifest package enumeration, not by visible untracked listing):

```text
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3
```

### 4.2 Authorization package bytes and SHA-256 (unchanged)

Package root:

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/`

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `authorization_report.md` | 1320 | `eb057678aeace13a67da5c980e8b5fba07cb4f2d1d955829c201907b5ac60cd5` |
| `binding_inventory.json` | 4059 | `1e87c2e88030d006ab09a2c7f907a678e22867771dd54e19b090f4e47c23c153` |
| `consumed_on_start_rule.md` | 817 | `f3fba9f7c5a1115e4f776fee967167a4e366d074f9f9725d2fc8e7b24be45f18` |
| `exact_manual_command.md` | 1998 | `6bf6c2e63cc20f98c9ad187b17aaa4eea7bdd7400d32f7656f8a0f1e61c13b23` |
| `final_authorization.json` | 12670 | `1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680` |
| `final_authorization.sha256` | 91 | `5fb6588fcdbf0c19383b582b042c41ded715e1f3c75bc7bfaf2fc568870a57c3` |
| `readiness_reference.md` | 684 | `a1a23001387942dec556df07d92edfb577aa4e5557c122e5a0a7d40189767967` |
| `stop_conditions.md` | 1333 | `4dc60556c4666d4ebb5aa1dd01fc6f6ab888f97058e385d29a10b2cdd0205317` |

`final_authorization.sha256` contents match the JSON hash above.

Prior consumed untracked package retained in place:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `…/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json` | 8129 | `1191277816c97589ed05aa0aee8ec4a5af1feb777728c356a51eba40c1595626` |

`.DS_Store` retained in place:

| File | Bytes | SHA-256 | mtime |
| --- | ---: | --- | --- |
| `.DS_Store` | 8196 | `015b5bf17d3735a713e984ef642fa540dbbcc62d2ee1167bb8f4bd35f81391b1` | 2026-08-03 07:26:23 local |

### 4.3 Authoritative DB identity and sidecars

Path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

| Field | Bound in package | Observed now | Result |
| --- | --- | --- | --- |
| SHA-256 | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` | identical | matched |
| size | `65806336` | `65806336` | matched |
| `mtime_ns` | `1785707543679666859` | `1785707543679666859` | matched |
| inode | `1230526` | `1230526` | matched |
| WAL / SHM / journal | absent | absent | matched |

Authoritative DB identity **did not change** as a result of this invocation.

### 4.4 Process state

No relevant Printer / wrapper / operational_memory_factory processes were
observed at capture time.

### 4.5 `/private/tmp/mp-preclaim` state

| Field | Observed |
| --- | --- |
| Path | `/private/tmp/mp-preclaim` |
| Git worktree pointer | `gitdir: /Users/Dtwo1/Developer/MoneyPrinter/.git/worktrees/mp-preclaim` |
| Detached HEAD | `8fb4256c70d4e81660c177238253322cb37ae947` |
| Mutation by this lane | none |

### 4.6 Prior external applications (historical; not this ID)

Existing completed application directories remain:

- `…/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/`
- `…/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/`

They were not modified by this lane.

## 5. Required inspection findings

### 5.1 External application directory for this authorization

Expected canonical path:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z
```

**Result: does not exist.**

No `application-marker.json`, published `git-provenance-manifest.json`,
`wrapper-terminal.json`, `child-stdout.txt`, or `child-stderr.txt` exists under
a canonical application directory for this authorization ID.

### 5.2 Application marker / Git-provenance manifest

| Artifact | Result |
| --- | --- |
| Canonical application marker (`PRINTER_V1_APPLICATION_MARKER_V1`) | **not created** |
| Canonical published git-provenance manifest | **not created** |
| Staging residue | **created** |

Staging path:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd/
```

Staging contents: only

| File | Bytes | SHA-256 | `created_at` |
| --- | ---: | --- | --- |
| `git-provenance-manifest.json` | 6958 | `d1705ced3a8629ad87a2745a78ec0940b77494e0a6177b0e8192fe7659e098b1` | `2026-08-03T20:54:00.620958+00:00` |

This matches wrapper control flow in
`apply_authorization_once()`:

1. select/validate lexical venv child interpreter (no consumption side effects);
2. create unique staging directory and write exclusive staging manifest;
3. run `validate_git_provenance_manifest_pre_marker` on the staging manifest;
4. **only if that passes**, promote to canonical application directory, write
   create-once marker, full-validate, then launch child.

The failure occurred at step 3. Staging was not promoted; the marker write never
ran. Residual staging is documented in production comments as a benign
efficiency residue that does not itself create a second application or overwrite
a first terminal cause.

### 5.3 Recorded `consumed_at`, terminal state, error type/message

| Field | Observed |
| --- | --- |
| Marker `authorization_consumed_at` | **absent** (no marker) |
| Wrapper stderr/status | `WINDOW_15M_ONE_SHOT_WRAPPER_BLOCKED` |
| Error type | `GitProvenanceAuthorizationError` |
| Error message | `unexpected untracked repository file not covered by manifest: .DS_Store, operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json` |
| Child start attempted | **false** (no marker, no launcher call) |
| Child PID / exit | none |

### 5.4 Operational child process

**Never started.**

Pre-marker provenance validation failed before marker creation and before
`process_launcher` / `subprocess` child launch. No child stdout/stderr artifacts
exist for this authorization ID.

### 5.5 Campaign / run / cycle / discovery / factory / Scheduler / memory window

Read-only SQLite inspection of the authoritative DB shows **no new rows**
attributable to this invocation:

| Table | Count | Max time column | Latest max |
| --- | ---: | --- | --- |
| `printer_memory_factory_campaigns` | 20 | `created_at` | `2026-08-02T21:52:15.193999+00:00` |
| `printer_memory_factory_campaign_runs` | 20 | `created_at` | `2026-08-02T21:52:15.193796+00:00` |
| `printer_memory_factory_campaign_cycles` | 20 | `created_at` | `2026-08-02T21:52:15.193796+00:00` |
| `printer_memory_factory_runs` | 7 | `created_at` | `2026-07-31T14:52:48.376170+00:00` |
| `printer_memory_windows` | 162 | `opened_at` | `2026-07-31T14:52:49.813210+00:00` |
| `printer_scheduler_jobs` | 1375 | `created_at` | `2026-08-02 21:52:23` |

Latest campaign remains the prior historical
`20260802T215214Z-50fece784718-campaign` (`TERMINAL_FAILED`,
`KeyError`/`token_slot_id` lineage from the previous authorized application). No
`20260803T204800Z` string hits were found in relevant tables.

### 5.6 Authoritative DB identity change

**No.** Exact equality with the package binding (section 4.3).

### 5.7 Authorization package expected untracked-file allowlist

The wrapper builds the provenance manifest by enumerating **exactly two**
current package roots (`build_manifest_bytes`):

1. Migration-050 evidence root bound by `migration_execution_id`
2. Current WINDOW_15M authorization root bound by `authorization_id`

Staging manifest file count: **20**

- 12 × `MIGRATION_050_EVIDENCE` under
  `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/`
- 8 × `WINDOW_15M_AUTHORIZATION_EVIDENCE` under
  `…/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/`

The expected allowlist therefore **includes only** those twenty paths. It does
**not** include:

- `.DS_Store`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json`

Independent recomputation at capture time:

| Set | Count |
| --- | ---: |
| Manifest paths | 20 |
| Visible untracked paths | 20 |
| `visible - manifest` (unexpected) | 2 (exactly the wrapper error set) |
| Manifest SQLite paths that are Git-ignored rather than visible | 2 (Migration-050 evidence DBs; handled by ignored-inventory law, not the unexpected-visible gate) |

### 5.8 Why `.DS_Store` and the prior consumed authorization JSON were excluded despite readiness/review preservation

#### Readiness preservation (current-head operational re-readiness)

`docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-operational-re-readiness-audit.md`
explicitly recorded and preserved:

```text
.DS_Store
operator-runs/v2-9-8b-authoritative-mig050/
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/
```

It also classified `…210122Z` as consumed and permanently non-reusable, while
instructing later operators to “preserve untracked operator evidence.”

#### Historical rollover precedent

Earlier consumed package `…112358Z` was rolled into **tracked immutable
history** so that only Migration-050 remained current untracked evidence before
the next authorization. That rollover pattern was **not** repeated for
`…210122Z` before creating `…204800Z`.

#### Manifest builder law

`build_manifest_bytes()` only walks the Migration-050 package root and the
**current** authorization ID package root. It has no path to absorb:

- Finder metadata such as `.DS_Store`;
- a prior consumed authorization package that remains untracked.

#### Independent-review / formal report gap for `…204800Z`

- No committed independent-review document for
  `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` is present in the repository.
- The package field
  `authorized_git.authorization_report` names
  `docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-one-use-authorization.md`,
  but that path is **absent** from the worktree and from `HEAD`.
- Prior independent review for `…210122Z` correctly required “exactly two
  untracked roots” (Migration-050 + that then-current authorization). The same
  equality discipline was not enforced against the later worktree that still
  held residual untracked evidence plus `.DS_Store`.

Therefore the files were “preserved” by readiness/operator practice, but never
entered the only allowlist the wrapper will accept. Preservation without either
(a) historical rollover into tracked history, or (b) explicit inclusion in a
manifest-compatible current-evidence set, is an authorization/procedure defect,
not a wrapper false positive.

### 5.9 Mismatch origin boundaries

| Boundary | Contribution |
| --- | --- |
| Authorization-package generation | **Yes** — package / derived allowlist covers only mig050 + `…204800Z`; ignores known residual untracked files that readiness had already declared present |
| Independent review | **Yes (procedure gap)** — no repository-resident independent review for `…204800Z` proving untracked-set equality to future manifest allowlist; hard gate text claims independent review PASS without durable review artifact at the named formal report path |
| Operator preparation | **Yes** — application attempted while worktree still contained preserved residual untracked files outside the two current package roots |
| Wrapper manifest law / implementation | **No production defect** — exact untracked-equality fail-closed behavior operated as designed |
| More than one boundary | **Yes** |

## 6. Root-cause classification and distinctions

### 6.1 Primary classification

`MULTI_BOUNDARY_AUTHORIZATION_DEFECT`

Not selected as primary (with reasons):

| Alternative | Why not primary |
| --- | --- |
| `AUTHORIZATION_PACKAGE_MANIFEST_COVERAGE_DEFECT` | Real, but incomplete alone — review and operator precondition also failed |
| `AUTHORIZATION_INDEPENDENT_REVIEW_DEFECT` | Real procedure gap, but package generation and operator worktree also contribute |
| `OPERATOR_WORKTREE_PRECONDITION_MISMATCH` | Real at application time, but the package/review chain already allowed that unusable state to be authorized |
| `WRAPPER_PROVENANCE_IMPLEMENTATION_DEFECT` | Rejected — block matches designed exact-equality law |
| `EXPECTED_PROVENANCE_SAFE_STOP` | The stop was expected given the allowlist/worktree pair, but does not name the upstream defect that made the package unusable |
| `INSUFFICIENT_EVIDENCE` | Rejected — staging manifest, error text, DB identity, and process state are sufficient |

### 6.2 Why the safe-stop itself was correct

Wrapper provenance law requires exact reconciliation between:

- manifest paths derived from the two current evidence packages;
- Git-visible untracked paths (after fixed SQLite sidecar subtraction);
- ignored operator-runs inventory coverage for package SQLite evidence.

Any residual visible untracked path outside the allowlist must fail closed before
marker publication and before child launch. That is the intended money-safety
and provenance-safety behavior. Observing the block is evidence the gate worked.

### 6.3 Why the authorization/review package nevertheless allowed an unusable application state

1. Readiness preserved residual untracked files that are incompatible with the
   two-root allowlist builder unless historically rolled over or otherwise
   dispositioned.
2. The new package was generated as an additional untracked root without first
   removing those residual visible untracked paths from the current-evidence
   namespace.
3. No durable independent review artifact for `…204800Z` is present to prove
   `git ls-files --others --exclude-standard` equality to the exact future
   manifest allowlist before operator application.
4. Operator application therefore started from a worktree the wrapper could not
   accept, burning the scarce one-shot attempt at the pre-marker gate.

### 6.4 Production wrapper repair justified?

**No.**

Do not treat this blocker as justification to loosen exact untracked equality,
auto-ignore `.DS_Store`, or silently absorb prior authorization packages into
the allowlist. Those would weaken provenance law.

Optional future efficiency hygiene (not required to classify this incident, and
**not** authorized by this lane): clearer pre-marker operator diagnostics that
print the full unexpected set and the expected two-root allowlist before exit.
That would be an operator-UX improvement only, not a correctness repair for this
root cause.

### 6.5 What must be corrected before a replacement authorization

Only the next authorization package and surrounding readiness/review/operator
procedure require correction. Exact corrections:

1. **Disposition residual current untracked evidence outside the two allowed
   roots**, using the established historical-rollover pattern for consumed
   authorization packages where appropriate:
   - `…/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json`
     should leave the *current* untracked evidence namespace (tracked history
     at the same path, consistent with prior rollover closeouts), **or** be
     otherwise removed from Git-visible untracked status under a dedicated
     authorized evidence lane — never by silent deletion in a runtime lane.
2. **Disposition `.DS_Store`** so it is not Git-visible untracked at application
   time (ignore/remove under an explicit operator hygiene decision). Do not
   invent wrapper allowlist coverage for Finder metadata.
3. **Create a new distinct authorization ID** only after the visible untracked
   set is exactly the intended current packages (Migration-050 + new package).
4. **Independent review must recompute** and PASS only if:
   - `git status` tracked/staged clean;
   - `set(git ls-files --others --exclude-standard) == set(manifest allowlist visible files)`;
   - ignored Migration-050 SQLite evidence remains byte-identical and
     inventory-covered;
   - no pre-existing external application directory/marker/staging for the new
     ID;
   - formal authorization report path exists and is bound.
5. **Do not reuse** `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`.

## 7. Authorization consumption state

Authorization ID:

`V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`

| Question | Finding |
| --- | --- |
| One authorized wrapper invocation made? | **Yes** (operator event + staging residue) |
| Canonical create-once marker written? | **No** |
| Package-law consumption (`consumed_when = wrapper_execution_begins`, regardless of block/safe-stop)? | **Treat as consumed / permanently non-reusable** for operator law |
| Mechanically re-appliable under create-once marker gate? | Canonical application directory still absent, so the marker gate alone would not yet reject; residual staging and package one-shot law still forbid reuse |
| This capture lane replacement authorization? | **Forbidden** — none created |

**Lane recording decision:** record
`V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` as **consumed and permanently
non-reusable**. Wrapper start is confirmed by application-side staging evidence
and the immutable blocked wrapper result. Formal marker `authorization_consumed_at`
is absent only because the pre-marker gate failed before marker write; that
absence does **not** restore reusability under package consumption law or this
lane’s authorization-state instruction.

No replacement authorization was created in this lane.

## 8. Money-usefulness contribution

This capture prevents a false diagnosis that production provenance code “broke”
and therefore needs a risky loosen-the-gate repair. It preserves the scarce
remaining path to money-useful 15-minute operation by:

- keeping the fail-closed untracked equality law intact;
- proving the child never ran and the DB was not mutated;
- naming the exact residual files that must be dispositioned before the next
  one-use authorization is minted;
- preventing silent reuse of `…204800Z`.

The cost of the defect was one wasted authorized attempt and continued delay of
live WINDOW_15M proof. The value of the capture is avoiding a second waste on
the same precondition mismatch and avoiding an incorrect production code change.

## 9. What remains locked

Still locked / not authorized by this lane:

- any second invocation, retry, rerun, resume, restart, or successor under
  `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`;
- any new live WINDOW_15M authorization ID;
- wrapper re-run;
- direct `operational_memory_factory_command` invocation;
- provider / Source Governor / Central Scheduler runtime;
- campaign execution;
- memory retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  PnL;
- WINDOW_1H / 4H / 12H / 24H;
- wallets, private keys, real funds, live execution, paid APIs;
- deletion/relocation of `.DS_Store` or prior authorization packages in this
  lane (already forbidden and not done);
- production source/test edits for “repair” of this blocker.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality Risks

- Re-minting a package without first clearing residual visible untracked files
  will deterministically reproduce this block.
- Loosening wrapper equality to “fix” residual files would reintroduce
  provenance ambiguity and is a money-safety regression risk.
- Treating the missing marker as “unconsumed and reusable” would violate package
  one-shot law and risk double application attempts under one ID.

### Setbacks

- One authorized current-head attempt is spent without child launch or campaign
  proof.
- Live post-repair WINDOW_15M operational proof remains unearned at this HEAD.
- Residual staging directory remains as non-canonical efficiency residue under
  `.staging/` for this ID.

### Efficiency Blockers

- Consumed prior authorization `…210122Z` still occupies the current untracked
  evidence namespace (no historical rollover yet).
- `.DS_Store` remains Git-visible untracked.
- Formal authorization report path named by the package is missing from the
  repository, weakening audit lineage for the spent package.
- No repository-resident independent review artifact exists for `…204800Z`.

## 11. Exact next permitted lane

**Exact next permitted lane:**

`V2-9.8B Post-Rollover-2 Current-Evidence Historical Rollover of Consumed WINDOW_15M AUTH_20260802T210122Z and Application-Time Untracked Precondition Correction`

Scope of that next lane (guidance only; not executed here):

- historical rollover / Git classification of the consumed
  `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` package out of the *current*
  untracked evidence namespace, following the established rollover closeout
  pattern used for `…112358Z`;
- explicit operator disposition of `.DS_Store` so it is not Git-visible
  untracked at future application time;
- preserve Migration-050 package byte identity;
- do **not** create a replacement authorization in that rollover lane;
- do **not** re-run the 15-minute command;
- after rollover/precondition correction and a fresh readiness/review chain,
  only then mint a **new** one-use authorization ID.

Forbidden until those preconditions are restored and a new authorization is
independently reviewed:

- wrapper application;
- any use of `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`.

## 12. Capture method and boundaries

Allowed methods used:

- read-only filesystem inspection of repository and
  `~/PrinterOperations/...` application/staging trees;
- Git status / history / `ls-files` inventories;
- read-only SQLite inspection (`mode=ro`) for counts and max timestamps;
- hash/stat of authorization package, staging manifest, DB, and `.DS_Store`;
- process listing;
- `git diff --check` (clean).

Forbidden methods **not** used:

- wrapper rerun;
- pytest;
- provider contact;
- DB writes;
- file deletion or relocation;
- manifest/package regeneration;
- new authorization;
- source or test edits;
- push.

## 13. Summary table

| Question | Answer |
| --- | --- |
| Wrapper terminal | `WINDOW_15M_ONE_SHOT_WRAPPER_BLOCKED` |
| Error | `GitProvenanceAuthorizationError` unexpected untracked: `.DS_Store` + prior `…210122Z/final_authorization.json` |
| Canonical app dir | absent |
| Marker / `consumed_at` | absent / N/A |
| Staging manifest | present; `created_at=2026-08-03T20:54:00.620958+00:00` |
| Child launched | no |
| DB delta | none; identity exact |
| Runtime objects created | none |
| Auth ID reuse | permanently non-reusable |
| Production code repair justified | no |
| Primary classification | `MULTI_BOUNDARY_AUTHORIZATION_DEFECT` |
| Capture verdict | `V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_WRAPPER_PROVENANCE_BLOCKER_ROOT_CAUSE_CAPTURED` |

## 14. Stop condition

This lane stops after committing only this blocker report.

No repair, worktree cleanup, replacement authorization, or 15-minute command is
authorized here.
