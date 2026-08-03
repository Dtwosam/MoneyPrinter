# Printer V1 V2-9.8B Post-Rollover-2 Consumed WINDOW_15M Authorization Historical Rollover Design

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Consumed WINDOW_15M Authorization Historical Rollover and Untracked-Set Precondition Correction`

Lane type: design / specification for a same-session bounded implementation and
closeout. This document does not by itself mutate Git classification, create an
authorization, run the wrapper, or contact providers.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_CONSUMED_WINDOW_15M_AUTHORIZATION_HISTORICAL_ROLLOVER_DESIGN_PASS`

The minimum safe correction is approved:

1. commit exact surviving consumed authorization evidence for
   `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` and
   `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` as immutable tracked history at
   their established repository paths;
2. restore and commit the formal authorization report and independent-review
   documents from verified commit `69ce7275065c87ae03dd68a0b47837703af1a120`
   after byte/hash verification against that object and the on-disk package;
3. add a narrow standard `.DS_Store` ignore rule so Finder metadata leaves the
   Git-visible untracked set without entering any authorization manifest;
4. preserve external staging evidence for `…204800Z` untouched;
5. leave Migration-050 as the sole current untracked evidence package.

No wrapper provenance law change is authorized. Production safe-stop remains
correct and unrepaired.

## 2. Baseline (design start)

| Item | Exact value |
| --- | --- |
| Required start SHA | `466f9aac72294c8194a7a75f5b080272ca68fea1` |
| Commit subject | `Record authoritative 15m provenance blocker` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked / staged | clean |
| Relevant Printer processes | none |
| Authoritative DB SHA-256 | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` |
| DB size / mtime_ns / inode | `65806336` / `1785707543679666859` / `1230526` |
| Sidecars | absent |
| `/private/tmp/mp-preclaim` | detached `8fb4256c70d4e81660c177238253322cb37ae947` |
| Wrapper execution in this lane | forbidden / none |

## 3. Controlling sources

- Active Printer V1 source stack (`AGENTS.md` and controlling docs).
- Current readiness audit:
  `docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-operational-re-readiness-audit.md`.
- Wrapper-provenance blocker capture at `466f9aa`:
  `docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-wrapper-provenance-blocker.md`.
- Authorization and independent-review objects available from
  `69ce7275065c87ae03dd68a0b47837703af1a120` (sibling of `466f9aa` on parent
  `e07ff977292d79f36a2067319187a0ad1f17f2f7`; not currently on HEAD).
- Prior historical-rollover precedent for `…112358Z`
  (`docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-*-2.md`).
- Wrapper manifest / untracked equality law in
  `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
  (`build_manifest_bytes` two-root enumeration) and
  `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
  (`unexpected untracked repository file not covered by manifest`).

## 4. Established facts (not reopened)

| Fact | Status |
| --- | --- |
| Wrapper safe-stop for `…204800Z` was correct | established |
| Production wrapper repair not justified | established |
| `…210122Z` consumed / non-reusable | established |
| `…204800Z` consumed / non-reusable | established |
| Operational child never started for `…204800Z` | established |
| Authoritative DB and runtime unchanged by that invocation | established |
| External staging for `…204800Z` must remain preserved | established |

## 5. Audit of current residual state

### 5.1 Git-visible untracked (before correction)

```text
.DS_Store
operator-runs/v2-9-8b-authoritative-mig050/… (10 visible files)
operator-runs/…/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json
operator-runs/…/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/ (8 package files)
```

### 5.2 Ignored Migration-050 SQLite evidence

```text
…/disposable-restore/printer_v1-rehearsal.sqlite3
…/verified-backup/printer_v1-pre050.sqlite3
```

Both SHA-256 `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`.

### 5.3 `.gitignore`

Current ignore law covers Python caches, venvs, env files, and `*.sqlite3` /
data DB patterns. It does **not** currently ignore `.DS_Store`.

### 5.4 Consumed package identities (must not rewrite)

| Package | Path | Key identity |
| --- | --- | --- |
| `…210122Z` | `…/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json` | size `8129`; SHA-256 `1191277816c97589ed05aa0aee8ec4a5af1feb777728c356a51eba40c1595626` |
| `…204800Z` | `…/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/` (8 files) | `final_authorization.json` SHA-256 `1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680` |

All eight `…204800Z` on-disk files byte-match blobs in `69ce727`.

### 5.5 Formal docs in `69ce727` (absent from HEAD)

| Path | SHA-256 of blob content |
| --- | --- |
| `docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-one-use-authorization.md` | `36b65783dc2d52f7bb62afadd2edce4ac58c060c884eefdd7413136257e65457` |
| `docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-one-use-authorization-independent-review.md` | `0729b67fbefce55ece908bc131e4bbe68c74cc42b31fc53ecb2a0d290f06f545` |

### 5.6 External staging (must preserve)

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd/git-provenance-manifest.json
```

| Field | Value |
| --- | --- |
| Bytes | `6958` |
| SHA-256 | `d1705ced3a8629ad87a2745a78ec0940b77494e0a6177b0e8192fe7659e098b1` |
| `created_at` | `2026-08-03T20:54:00.620958+00:00` |
| Canonical application directory for `…204800Z` | absent |

## 6. Target post-correction state

### 6.1 Visible untracked set after this lane

Exactly the **visible** Migration-050 current-evidence files (10 paths). The two
Migration-050 SQLite files remain ignored and inventory-covered.

No consumed WINDOW_15M authorization package may remain Git-visible untracked.

`.DS_Store` must not appear in `git ls-files --others --exclude-standard`.

### 6.2 Future application-time equality (after a later new package)

```text
Migration-050 current evidence
+
new current WINDOW_15M authorization package
```

This design restores only the pre-package half of that equality.

## 7. Smallest correction (approved mechanics)

### 7.1 Historical rollover of `…210122Z`

- Track in place:
  `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/final_authorization.json`
- Same path, same bytes, no rewrite/regenerate/chmod/move.
- Record SHA-256 `1191277816…` after add.
- Classification change only: untracked current evidence → tracked historical
  evidence (precedent: `…112358Z` rollover 2).

### 7.2 Historical rollover of `…204800Z`

- Track in place all eight package files currently on disk under
  `…/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/`.
- Verify each against the previously recorded package hashes and against
  `69ce727` blobs.
- Do **not** alter `final_authorization.json`.
- Restore and commit formal docs from `69ce727` only after hash verification.
- Closeout must mark the package as: consumed; permanently non-reusable;
  blocked before child launch; historical evidence only.

### 7.3 `.DS_Store` disposition

- Preferred: add a narrow standard `.DS_Store` rule to `.gitignore` if absent.
- Verify `.DS_Store` no longer appears in
  `git ls-files --others --exclude-standard`.
- Do **not** add `.DS_Store` to any authorization manifest.
- Do **not** modify wrapper provenance logic.

### 7.4 External staging

- Do not delete, rename, or promote the `…204800Z-*` staging directory.
- Record path and manifest hash as preserved historical application evidence.

### 7.5 Explicit non-goals

- No replacement authorization ID.
- No wrapper execution.
- No pytest.
- No provider contact.
- No DB mutation.
- No Migration-050 reclassification or re-run.
- No production code repair of provenance gates.

## 8. Commit scope (single PASS commit)

On PASS, one commit may contain only:

1. exact historical authorization evidence (`…210122Z`, `…204800Z` package);
2. restored authorization and independent-review documentation from verified
   `69ce727` objects;
3. `.gitignore` only if the `.DS_Store` rule is required;
4. this design document and the lane closeout document.

Commit message:

`Rollover consumed 15m authorization evidence`

Do not push.

## 9. Static exact-set proof obligations

Implementation/closeout must prove:

1. tracked/staged changes limited to historical evidence, required docs,
   `.gitignore` if needed, and lane reports;
2. neither consumed authorization remains Git-visible untracked;
3. `.DS_Store` is not Git-visible untracked;
4. visible untracked paths equal exactly the visible Migration-050
   current-evidence files;
5. ignored Migration-050 SQLite artifacts remain byte-identical and
   inventory-covered;
6. no other ignored `operator-runs` artifact exists outside the approved
   Migration-050 package;
7. authoritative DB identity unchanged;
8. no active/locked Scheduler residue or Printer process;
9. no external application directory or marker created for a new ID;
10. no authorization created.

## 10. Next lane (after PASS closeout only)

`V2-9.8B Post-Rollover-2 Replacement Authoritative WINDOW_15M Current-HEAD Readiness and One-Use Authorization Preparation`

That later lane must bind the new post-rollover HEAD, create a completely new
authorization ID, prove exact visible-untracked equality against the generated
manifest before review PASS, and require a separate operator application.

## 11. Stop condition for this design

Design alone does not implement. Implementation and closeout follow in the same
lane under this approved plan.
