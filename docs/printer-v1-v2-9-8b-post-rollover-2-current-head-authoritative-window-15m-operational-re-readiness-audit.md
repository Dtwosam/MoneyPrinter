# Printer V1 V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M Operational Re-Readiness Audit

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M Operational Re-Readiness Audit`

Lane type: audit and documentation only.

No campaign, discovery run, lifecycle, memory generation, proof, provider
request, Scheduler runtime, database mutation, authorization, or push was
executed by this lane.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_OPERATIONAL_RE_READINESS_AUDIT_PASS`

Readiness classification:

`READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION`

Current HEAD `939a610591f2d8422dc69053560b1378a6ea4650` is ready for **one newly
authorized, manually started, authoritative `WINDOW_15M` command** after a
separate one-use authorization lane. This audit creates **no** authorization
and does **not** run that command.

Offline exact public-composition PASS at this HEAD closes the post-consumption
repair chain. Offline PASS does **not** replace authoritative operational proof.

## 2. Baseline

| Item | Exact value |
| --- | --- |
| Required / observed HEAD | `939a610591f2d8422dc69053560b1378a6ea4650` |
| Commit subject | `Close exact public composition repair` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked / staged trees | Clean (`git status` shows only untracked operator evidence) |
| Ahead / behind | `15` ahead / `0` behind of configured upstream |
| Relevant Printer processes | None |
| Push | Not performed |
| `/private/tmp/mp-preclaim` | Detached `8fb4256c70d4e81660c177238253322cb37ae947` — untouched |
| Untracked operator evidence (preserved, unchanged) | `.DS_Store`; `operator-runs/v2-9-8b-authoritative-mig050/`; `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/` |

Confirmed before proceeding: exact HEAD and branch match the lane start
requirement; tracked and staged trees clean; no relevant Printer processes;
preserved untracked evidence left unaltered; `mp-preclaim` remains at the
required detached commit.

## 3. Controlling source hierarchy

### 3.1 Active Printer V1 source stack (inspected)

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `d71bdf56518543c9c66bb419c917cf5dc421d61380bb3da8b756c06166af743e` |
| `docs/printer-v1-clean-master-spec.md` | `83d026c2a3ce6d35bd3b4cb67b72ff404a283ded86561597485109204c4cc657` |
| `docs/printer-v1-post-rc-build-order.md` | `c40c1533d1be579c3b07559cbcd58396205da73e674b0b6600beb1bf3cff67e2` |
| `docs/printer-v1-memory-factory-guide.md` | `1325d9bd126e526738e397ec2aee453de77705a15dbc469de048c49cbd4b740d` |
| `docs/printer-v1-current-state-memory-growth-audit.md` | `130d245008d75210f2610e158757b235b33f4737a929b9750e38beaba87edb81` |
| `docs/printer-v1-memory-growth-build-order-v2.md` | `c12f5dcbd8700ec50e0926d3dd14430839575a707c13cf836fc0373e3bc722c1` |
| `docs/printer-v1-python-builder-guide.md` | `1b1487040710d35e7e453254feaaeaca15adf346f9d356fe379c8899efaabe0f` |

### 3.2 Latest committed V2-9.8B control documents (reviewed)

- V2-9.8A / post-RC anchors via the active stack and AGENTS locks.
- Migration-050 and Scheduler ownership (retained package
  `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`).
- Authoritative `WINDOW_15M` readiness and authorization chain:
  post-rollover-2 fresh readiness audit / evidence completion / final
  authorization / independent review.
- One-shot wrapper, Git-provenance manifest, and application-marker design /
  implementation / closeout chain.
- Post-rollover repairs: token-slot projection, discovery claim-at-work-start,
  SHARED_FAILURE evidence capture, origin-driver failure propagation,
  end-to-end pre-lifecycle failure propagation, frozen-secondary contract,
  lifecycle-entry harness.
- Exact offline public-composition Full PASS and closeout at `939a610`
  (`docs/printer-v1-v2-9-8b-post-rollover-2-exact-public-composition-repair-and-harness-closeout.md`).

### 3.3 Just-in-time Solana Builder stack

The exact filenames requested
(`docs/source-governor-evidence-rules.md`, `docs/solana-core-rpc-reference.md`,
`docs/dexscreener-api-contract.md`, `docs/pumpportal-api-contract.md`,
`docs/pumpswap-pool-confirmation-contract.md`,
`docs/token-age-evidence-tier-registry.md`) are **not present** at those paths
in the current repository. Active source law for this audit is taken from:

- `src/printer_v1/sources/operational_source_contracts.py`
  (`CONTRACT_REGISTRY_VERSION = V2_9_8B_SOURCE_COMPATIBILITY_RESET_V1`);
- `src/printer_v1/sources/secondary_discovery.py`
  (`SECONDARY_DISCOVERY_CONTRACT_VERSION = V2-9.7D.7B.4B`);
- committed V2-9.x pump / PumpSwap / token-age / public-RPC docs under `docs/`.

This filename drift is a documentation-location note only. It is **not** a
command, manifest, DB, or product-path blocker for readiness.

## 4. Established state (not reopened)

| Established fact | Status |
| --- | --- |
| Exact offline public-composition repair/harness chain | Closed PASS at `939a610` |
| Production claim-at-work-start, failure propagation, frozen-secondary, accounting repairs | Committed and ancestral to HEAD |
| Final offline exact composition | PASS (`1 passed in 3.75s`) |
| Offline PASS replaces authoritative operational proof | **False** — does not |
| `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` | Consumed; permanently non-reusable |
| `V2_9_8B_EXACT_OFFLINE_PUBLIC_COMPOSITION_AUTH_20260803_01` | Consumed; permanently non-reusable |
| Any live authorization currently usable | **None** |

## 5. Exact command owner

| Role | Owner |
| --- | --- |
| Manual operator entry script | `scripts/Start-PrinterV1-Window15M-OneShot.ps1` |
| One-shot application owner | `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` |
| Git-provenance / marker law | `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` |
| Operational child (wrapper-launched only) | `printer_v1.operator_cli.operational_memory_factory_command` |
| Direct operational-command authorization | **Not authorized** — wrapper required |

The PowerShell entry requires:

- explicit `-AuthorizationFile`;
- exact `-AuthorizationSha256` (`^[0-9a-f]{64}$`);
- explicit `-OperatorApproved` switch (fail-closed without it).

It launches:

```text
.venv/bin/python -m printer_v1.operator_cli.window_15m_one_shot_wrapper
  --authorization-file <path>
  --authorization-sha256 <64-hex>
  --operator-approved
```

Wrapper law (static inspection):

- accepts one explicit operator authorization package;
- creates create-once external Git-provenance manifest and application marker;
- launches exactly one child via single production `subprocess.Popen` with
  `shell=False`;
- hard-false: automatic retry, manual rerun, resume, restart, successor;
- `allowed_invocation_count == 1`;
- main window must be `WINDOW_15M`;
- `selective_1h_continuation` must be `false`;
- lexical repository `.venv` interpreter preservation (no base-interpreter
  substitution);
- safe-stop / fail-closed on HEAD, branch, package, binding, or flag mismatch;
- no Central Scheduler or Source Governor bypass (wrapper owns only launch
  provenance; runtime remains child-owned under those governors).

### 5.1 Current launch-chain identities (fresh at this HEAD)

| File | Bytes | Git blob | SHA-256 |
| --- | ---: | --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `878` | `a7fd77e680fa48dff911982d1491462185b5699a` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `42875` | `64b8a305765bb0967ae1f57301d8bcee70db22a3` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `30802` | `73d5ac306eee0241dcb3d1b97bd353fa950bd470` | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `177721` | `1b47078ad0e619bb589ffc44f6c1d06aaecfe48e` | `92b92d67c7daba913839834a5ef5834b9f902c3b12d4140291c5983c459df510` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `34700` | `e4f1eb046d8ce9c4def2840d9ffb80edd679589a` | `b41678d3b1ff08ae9dccca9639b7f412e104356805683bfcab178f4a72ff47fe` |

Notes:

- wrapper and manifest SHAs match the last live authorization authority;
- `operational_memory_factory_command.py` **changed** after that live auth
  (post-consumption production repairs). Future authorization **must** bind
  the current command SHA `92b92d67…`, not the consumed `16c8bb80…`.

Schema versions:

- wrapper: `PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1`;
- manifest: `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1`;
- application marker: `PRINTER_V1_APPLICATION_MARKER_V1`;
- required main window: `WINDOW_15M`.

External application root (create-once, outside repo):

`~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/<AUTHORIZATION_ID>/`

## 6. Repository and implementation findings

### 6.1 Ancestry from last authoritative readiness baseline

| Commit | Role | Ancestral to HEAD |
| --- | --- | --- |
| `5ff71753f60f355d268ecd35a13f5c78116fb414` | Second current-evidence rollover closeout | Yes |
| `9b1f88ac143db2db690dfd53bc9130017762179a` | Post-rollover-2 fresh readiness audit | Yes |
| `d9714fa56ae0217dcca8a35ad66e27f223e0eba5` | Fresh readiness evidence completion | Yes |
| `be6ead74a260d58c7ccca2042de2fe8f2b584242` | Fresh exact-HEAD WINDOW_15M authorization | Yes |
| `de8108b…` | Independent review of that authorization | Yes |

HEAD descends from the last authoritative readiness and authorization lineage.

### 6.2 Post-readiness production repairs included

| Repair | Commit | In HEAD |
| --- | --- | --- |
| Token-slot projection (`token_slot_id`) | `b0690d5` | Yes |
| Discovery Scheduler claim-at-work-start | `f765b6d` | Yes |
| SHARED_FAILURE evidence capture | `f32336b` | Yes |
| Origin-driver activation failure propagation | `3f1be84` | Yes |
| End-to-end pre-lifecycle failure propagation | `1a95458` | Yes |
| Frozen secondary discovery contract | `ff5f539` | Yes |
| Lifecycle-entry harness (test-only) | `a84b80e` | Yes |
| Exact offline public composition PASS | `4e2de68` | Yes |
| Closeout | `939a610` | Yes (HEAD) |

### 6.3 Authoritative 15m path blockers

| Check | Result |
| --- | --- |
| Unresolved implementation blocker on authoritative 15m path | **None identified** in static inspection |
| Exact manual command owner | Present (wrapper + PS1) |
| One explicit operator authorization | Required; consumed without it |
| Hidden automatic retry / restart / resume / successor | **None** (hard false flags / zero counters) |
| First target | `WINDOW_15M` only |
| `WINDOW_5M_MICRO_EVENT` | Support-only |
| Token capacity | `TOKEN_CAPACITY = 2` (still required) |
| 1h / 4h continuation in same authorization | Forced false / locked |
| Retrieval / BUY / SELL / HOLD / positions / trades / audits / PnL | Still locked |

The previous live application of
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` failed after successful two-slot
selection with `KeyError: 'token_slot_id'` (child exit 1,
`OPERATIONAL_COMMAND_BLOCKED`). That product defect was repaired
(`b0690d5`) and the offline exact public composition later passed two-slot
lifecycle closes. Remaining uncertainty is **live-provider / market-supply /
authoritative-corpus operational proof**, not an open committed code defect in
the repaired path.

## 7. Authoritative database findings

Read-only inspection only (`mode=ro` + `PRAGMA query_only = ON`). No vacuum,
migration, write, or mutation.

### 7.1 Canonical path and identity

| Field | Value |
| --- | --- |
| Canonical path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Regular file | Yes |
| Size | `65806336` |
| SHA-256 | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` |
| `mtime_ns` | `1785707543679666859` |
| inode | `1230526` |
| WAL / SHM / journal | Absent / absent / absent |
| Pre/post open identity | Identical (no mutation) |

This identity matches the offline exact-composition closeout’s measured
authoritative corpus identity. Offline composition did **not** open or mutate
this file. The identity differs from the pre-live-attempt readiness identity
(`56ca1218…`, size `65671168`) because the consumed live authorization
application on 2026-08-02 wrote terminal campaign residue — expected historical
state, not offline-proof contamination.

Authoritative DB has **not** been replaced by offline disposable proof
artifacts. Disposable proof DBs were temporary Migration-050 databases only.

### 7.2 Migration state

| Check | Result |
| --- | --- |
| Migration count | `50` |
| Migration head | `050_campaign_scheduler_ownership_scope.sql` @ `2026-08-01 20:44:32` |
| Migration-050 applied | Yes |
| `__v2_9_8b_050%` / `_mig050_guard_%` residue objects | None |
| Post-050 campaign work columns | Present |
| Required indexes / triggers | Present |

### 7.3 Integrity

| Check | Result |
| --- | --- |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | `0` violations |

### 7.4 Active residue matrix

| Surface | Count / state | Active? |
| --- | --- | --- |
| Campaigns | 20 total: `TERMINAL_COMPLETED` 12 / `TERMINAL_FAILED` 8 | No active |
| Campaign runs | 20: same 12 / 8 terminal split | No active |
| Campaign cycles | 20: 12 / 8 terminal | No active |
| Campaign supervision | 20 `TERMINAL`; lease released 0 null; cleanup completed 0 null | No active |
| Campaign scheduler work | 10: `SUCCEEDED` 8 / `CANCELLED` 2 | No active |
| Discovery work | 80: `SUCCEEDED` 78 / `FAILED` 2 | No active |
| Factory run steps | 72: `SUCCEEDED` 60 / `CANCELLED` 12 | No active |
| Factory runs | 7: `COMPLETED` 3 / `SAFE_STOPPED` 4 | No active |
| Proof-run supervision | 0 | None |
| Candidate acquisition leases | 19 `TERMINAL`; released_at null = 0 | No active |
| Scheduler jobs | 1375: `SUCCEEDED` 1316 / `CANCELLED` 45 / `FAILED` 14 | Running/locked = **0** |
| Campaign windows | 2 historical `CANCELLED` only | No active |
| Paper positions / trade events / decision audits / trade audits / retrieval matches | All `0` | Locked empty |

Latest failed live campaign (consumed auth path):

| Field | Value |
| --- | --- |
| Campaign | `20260802T215214Z-50fece784718-campaign` |
| State | `TERMINAL_FAILED` |
| Cause | `OPERATIONAL_CAMPAIGN_FAILED:KeyError` (`token_slot_id`) |
| Discovery | 8 `SUCCEEDED` stages through selection/handoff |
| Scheduler work | 8 `SUCCEEDED` + 2 `CANCELLED` (`FIRST_15M_HANDOFF`) |
| Windows created | 0 |

Historical `SELECTED` token-slot labels (2 rows from
`20260727T001520Z-d513e21260b5-campaign`) belong to a **terminal** parent
campaign (`TERMINAL_FAILED`, leases released). They are preserved history, not
live locks or active Scheduler work.

### 7.5 Backup / rollback readiness

| Asset | State |
| --- | --- |
| Migration-050 verified backup | `operator-runs/.../verified-backup/printer_v1-pre050.sqlite3` present (size `65654784`) |
| Disposable restore rehearsal | Present under same package |
| Package listing identity digest | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` (12 files, unchanged) |
| Historical pre-campaign backups under PrinterOperations | Present (older runs) |

Migration-050 must **not** be re-invoked. Rollback for a future failed
authoritative run remains operator-controlled restore from verified backup /
pre-campaign snapshot practice; this audit does not rehearse restore.

## 8. Wrapper / manifest / marker findings

| Check | Result |
| --- | --- |
| Exact one-shot wrapper to run manually | `scripts/Start-PrinterV1-Window15M-OneShot.ps1` → `window_15m_one_shot_wrapper` |
| Required manifest version | `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` |
| Required application marker version | `PRINTER_V1_APPLICATION_MARKER_V1` |
| Exact HEAD binding | Authorization `authorized_git.head` must equal live HEAD at apply time |
| Exact DB identity binding | Future auth must bind current SHA `d85442e6…` / size `65806336` |
| Authorization identity / consumed-state checks | Create-once external marker; re-application blocked by existing path |
| Safe-stop on wrong binding | Fail-closed wrapper / manifest validation |
| Bypass Central Scheduler / Source Governor | None in wrapper launch path |

Consumed external applications (immutable `0444`):

| Auth ID | Marker consumed_at | Child exit | Terminal |
| --- | --- | --- | --- |
| `…112358Z` | `2026-08-02T11:34:17Z` | 1 | Interpreter bootstrap failure (later repaired) |
| `…210122Z` | `2026-08-02T21:52:14Z` | 1 | `KeyError: token_slot_id` after selection |

Both remain permanently non-reusable. No current unused WINDOW_15M authorization
package exists.

## 9. Environment-shape findings

Secrets inspected for **presence and shape only**. No secret values printed,
hashed, or logged.

| Item | Result |
| --- | --- |
| Local secrets file | `/Users/Dtwo1/.config/printer-v1/secrets.env` |
| Permissions | `0600` (owner read/write only; not group/world readable) |
| `PRINTER_SOLANA_RPC_URL` | Present, non-empty, non-placeholder; `https`; hostname length 28; no userinfo; no fragment |
| `PRINTER_HELIUS_API_KEY` | Present, non-empty, length 36, non-placeholder, no whitespace |
| `SOLANA_TRACKER_API_KEY` | Present, non-empty, length 36, non-placeholder, no whitespace |
| Placeholder markers | None detected |
| Paid-API dependency | Not required by ordinary active contracts (`paid_dependency=False`) |
| Live wallet / private key / signing / funds env vars | Absent |
| Provider contact during this audit | **None** |

Operator prerequisite: the future run terminal must load the secrets file (or
equivalent env) before the one-shot wrapper; this audit does not start that
process.

## 10. Provider / source readiness (static contracts only)

Registry: `V2_9_8B_SOURCE_COMPATIBILITY_RESET_V1`.

| Surface | Classification | Contract version | Notes |
| --- | --- | --- | --- |
| Governed Pump origin / migrate locator | MANDATORY | `PUMP_IDL_PINNED_EXACT_MIGRATE_V1` | Keyless or operator endpoint; rate 30/min |
| PumpSwap exact join / confirmation | MANDATORY | `PUMPSWAP_IDL_PINNED_POOL_JOIN_V1` | Rate 30/min |
| DexScreener profiles / token batch / exact pair | MANDATORY | public API V1 variants | Rate 60/min |
| GeckoTerminal secondary (exact pair + 15m) | CONDITIONAL | `GECKOTERMINAL_API_V2_20230203` | Rate 10/min; lawful secondary |
| Frozen secondary transport contract | Product pin | `V2-9.7D.7B.4B` | Offline-pinned; live uses governed path |
| Helius holder backup | CONDITIONAL | `HELIUS_STANDARD_RPC_HOLDER_V1` | Only when selected; free conditional key |
| PumpPortal ordinary runtime | DEFERRED / inactive | Historical only | Prohibited in ordinary run |
| Paid dependency / wallet / signing endpoints | — | — | All ordinary active profiles false |

Known rate-limit / resource risks for one bounded 15m run (not blockers for
authorization readiness):

- GeckoTerminal 10/min ceiling under multi-token evidence fill;
- public DexScreener / CoinGecko ceilings under burst discovery;
- Solana RPC 30/min class ceilings for origin/PumpSwap/holder fallback;
- natural market supply may still yield zero eligible two-token sets (honest
  market block, not code defect).

No provider bypass or unauthorized endpoint introduced by the repair chain.

## 11. Operational boundaries for the future run

If newly authorized and manually started, the future run must remain:

- one manually started authoritative `WINDOW_15M` campaign;
- Solana memecoin-only;
- paper-only;
- two-token capacity only (`TOKEN_CAPACITY = 2`);
- no automatic second run;
- no 1h or 4h continuation under the same authorization;
- no retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- no authorization reuse after start / permanent consumption on command start;
- Source Governor owns external-source access; Central Scheduler owns runtime.

## 12. Authorization state

| Authorization | State |
| --- | --- |
| `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` | Consumed (historical; tracked) |
| `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` | Consumed (untracked package + external marker); permanently non-reusable |
| `V2_9_8B_EXACT_OFFLINE_PUBLIC_COMPOSITION_AUTH_20260803_01` | Consumed offline; permanently non-reusable |
| Current reusable live WINDOW_15M authorization | **None** |

This audit creates **no** authorization.

## 13. Exact operator prerequisites

Before any wrapper application after a future authorization:

1. Create a **new** one-use authorization ID (next lane), distinct from all
   consumed IDs.
2. Bind that authorization to:
   - post-audit exact HEAD (this audit commit changes HEAD — do **not** bind
     only `939a610` after the audit lands);
   - current branch;
   - current launch-chain SHAs (especially command `92b92d67…`);
   - current authoritative DB identity `d85442e6…` / `65806336`;
   - Migration-050 package identity digest `08e6f40b…` (do not re-run 050);
   - exact one-shot command owner and single invocation law.
3. Complete independent authorization review PASS.
4. Confirm tracked worktree clean at application time; preserve untracked
   operator evidence.
5. Confirm no pre-existing external application directory / marker / staged
   manifest for the new authorization ID.
6. Source `/Users/Dtwo1/.config/printer-v1/secrets.env` (mode `0600`) into the
   operator shell without printing secrets.
7. Confirm still zero active Scheduler locks and no Printer process.
8. Run the one-shot PowerShell command **exactly once** with operator approval.
9. Do not retry, resume, restart, or issue a successor under the same
   authorization — even on safe-stop or failure.

## 14. Readiness classification

**Chosen classification:**

`READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION`

| Classification | Disposition |
| --- | --- |
| `READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION` | **Selected** |
| `READY_WITH_OPERATOR_PREREQUISITES` | Not selected — prerequisites are for the *authorization/application* lanes, not open blockers to readiness |
| `BLOCKED_BY_REPOSITORY_STATE` | No — clean tracked trees, correct HEAD/branch |
| `BLOCKED_BY_DATABASE_STATE` | No — integrity/FK ok; zero active runtime residue |
| `BLOCKED_BY_ENVIRONMENT_OR_CREDENTIAL_SHAPE` | No — required vars present/shaped; no wallet keys |
| `BLOCKED_BY_COMMAND_OR_MANIFEST_DRIFT` | No — wrapper/manifest/PS1 stable; command SHA updated intentionally by repairs and must be rebound |
| `BLOCKED_BY_UNRESOLVED_PRODUCT_DEFECT` | No — prior live `token_slot_id` defect repaired; offline composition PASS |
| `INSUFFICIENT_EVIDENCE` | No — static + read-only DB evidence sufficient for readiness |

## 15. Proposed future authorization scope

Recommend (do **not** create in this lane):

`V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M One-Use Authorization`

Must bind:

| Binding | Requirement |
| --- | --- |
| Exact HEAD | Post-audit commit on this branch (after this report commits) |
| Exact canonical DB identity | Path + SHA-256 `d85442e6…` + size `65806336` |
| Exact command | PS1 → one-shot wrapper → one operational child |
| Invocation count | Exactly one |
| Campaign / cycle | Exactly one campaign / one cycle |
| Retry / rerun / restart / resume / successor | All false; permanent consumption on command start |
| 1h / 4h continuation | Forbidden under this authorization |
| Execution mode | Manual terminal execution only |
| Main window | `WINDOW_15M` only |
| Token capacity | 2 |
| Paper / Solana memecoin | Enforced |

## 16. Exact manual command template (secrets redacted)

After a future authorization package exists and independent review PASSes:

```powershell
# From a clean operator shell with secrets already loaded (values never printed):
#   source /Users/Dtwo1/.config/printer-v1/secrets.env

cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/<NEW_AUTH_ID>/final_authorization.json `
  -AuthorizationSha256 <64_HEX_SHA256_OF_THAT_FILE> `
  -OperatorApproved
```

Equivalent Python form (still requires explicit approval flags and hashes):

```bash
cd /Users/Dtwo1/Developer/MoneyPrinter
./.venv/bin/python -m printer_v1.operator_cli.window_15m_one_shot_wrapper \
  --authorization-file operator-runs/v2-9-8b-window-15m-final-authorization/<NEW_AUTH_ID>/final_authorization.json \
  --authorization-sha256 <64_HEX_SHA256_OF_THAT_FILE> \
  --operator-approved
```

Do **not** invoke `operational_memory_factory_command` directly for the
authoritative path.

## 17. Rollback and stop conditions

Stop / do not apply if any of:

- HEAD or branch differs from the authorization binding;
- tracked tree dirty with unexpected product changes;
- authorization package missing, modified, or already consumed;
- external application directory or marker already exists for the ID;
- authoritative DB SHA/size/mtime/sidecars differ from bound identity;
- Migration-050 package identity digest drifts;
- launch-chain file SHAs differ from bound set;
- active Scheduler locks / non-terminal campaign residue / Printer processes
  present;
- required env vars missing, empty, or placeholder-shaped;
- operator tries automatic retry / second invocation under the same auth.

Rollback posture:

- do not re-run Migration-050;
- do not reuse consumed authorization IDs;
- preserve verified pre-050 backup and any pre-campaign snapshot taken by the
  operator before a future run;
- failed/safe-stopped attempts permanently consume the one-use authorization
  (honest terminal law).

## 18. Money-usefulness contribution

This re-readiness audit protects the next scarce one-use authorization from
being spent on a HEAD that still carries known composition defects or an
unclean runtime corpus. By proving that:

- all post-consumption production repairs and the offline exact public
  composition PASS are on HEAD;
- the authoritative DB is integrity-clean with zero active residue;
- the one-shot launch chain remains fail-closed and single-invocation;
- credentials are shaped without paid-API or wallet requirements;

it raises the chance that the next authorized 15-minute run can spend its only
shot collecting clean Solana memecoin memory rather than rediscovering fixed
product defects. It creates no memory, market signal, decision, trade, or
profit claim.

## 19. What this audit improves

- re-validates readiness at the **post-repair, post-offline-PASS** HEAD rather
  than at the pre-consumption readiness HEAD;
- records the **new** operational command SHA that future auth must bind;
- refreshes authoritative DB identity after the consumed live attempt;
- confirms zero active Scheduler / campaign / discovery residue after that
  failed attempt;
- restates that offline PASS is composition confidence, not live operational
  proof;
- names the exact next authorization scope without creating it.

## 20. What remains locked

- live campaign execution until a new authorization is issued and reviewed;
- wrapper application / manifest / marker creation until that review;
- provider contact and Source Governor / Central Scheduler runtime;
- retrieval, ranking, scoring, confidence, weights, embeddings, vectors;
- BUY / SELL / HOLD, positions, trades, audits, PnL;
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`;
- wallets, private keys, signing, real funds, live execution, paid APIs;
- reuse of any consumed authorization;
- re-run of Migration-050.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana-memecoin-only, paper-only.

## 21. Proof required after authorization

After the future one-use authorization is applied exactly once:

1. immutable external application package (marker, manifest, stdout/stderr,
   wrapper terminal) with create-once `0444` artifacts;
2. honest terminal classification (pass, blocked, safe-stop, or failed) without
   retry;
3. campaign / run / cycle terminal states and first terminal cause;
4. Scheduler claim transition evidence for discovery work where work occurred;
5. residue matrix (active locks = 0 post-terminal);
6. authoritative DB integrity / FK post-run;
7. before/after DB identity (or documented expected write set);
8. confirmation of zero retrieval / paper-trade / PnL activation;
9. no second invocation under the same authorization.

## 22. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition |
| --- | --- |
| This audit commit changes HEAD | Future authorization must bind the **post-audit** HEAD, not only `939a610` |
| Reusing consumed `…210122Z` or offline composition auth | Impossible / forbidden; permanent consumption proven by markers |
| Binding stale operational-command SHA `16c8bb80…` | Reject; bind current `92b92d67…` |
| Offline PASS mistaken for live proof | Explicitly separated; live proof still required |
| Natural two-token market supply shortage | Honest terminal risk; not a readiness code blocker |
| GeckoTerminal / public API rate ceilings | Bounded-run resource risk; monitor; no paid-API dependency |
| Historical `SELECTED` token-slot labels | Parent campaigns terminal; not active locks |
| JIT docs missing at exact uploaded filenames | Location drift only; code contracts govern |
| Build-order docs lag post-closeout naming | Does not block one-use WINDOW_15M authorization readiness under this operator lane |
| Secrets not loaded in a new shell | Operator prerequisite before apply |
| Second command under same auth | Forbidden by wrapper and authorization law |

None of the above reclassifies this audit to BLOCKED.

## 23. Exact next lane

On this READY classification:

```text
V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M One-Use Authorization
```

That lane may create exactly one new authorization package bound to the
post-audit HEAD and the identities recorded here. It must be independently
reviewed before any wrapper application. This audit authorizes neither
authorization issuance nor the 15-minute command.

## 24. Verification performed

| Allowed check | Performed |
| --- | --- |
| Static source / document inspection | Yes |
| Git ancestry / history | Yes |
| Read-only database queries | Yes |
| Environment variable presence / shape | Yes |
| File permission and path checks | Yes |
| Process / worktree status | Yes |
| `git diff --check` | Yes (clean; no tracked diff) |
| Exact documentation-scope review | Yes |

Not performed (forbidden by lane):

- pytest;
- provider / RPC / WebSocket contact;
- manual one-shot command;
- campaign / discovery / lifecycle / Scheduler runtime;
- database mutation / vacuum / migration;
- authorization creation;
- push.

## 25. Final statement

Current HEAD `939a610` includes the complete post-rollover-2 repair chain and
the closed offline exact public-composition PASS. The authoritative database is
Migration-050 complete, integrity-clean, foreign-key clean, and free of active
campaign, Scheduler, discovery, factory, or lease residue. The one-shot wrapper
/ manifest / marker path remains the sole manual entry for a single authorized
`WINDOW_15M` run. Environment credentials are present and correctly shaped
without wallet or paid-API dependency. No reusable live authorization exists.

Readiness classification:

`READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION`

Lane verdict:

`V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_OPERATIONAL_RE_READINESS_AUDIT_PASS`
