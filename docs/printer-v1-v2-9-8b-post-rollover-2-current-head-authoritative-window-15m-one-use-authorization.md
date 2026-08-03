# Printer V1 V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M One-Use Authorization

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M One-Use Authorization and Independent Review`

Lane type: authorization packaging and static independent review only.

No campaign, discovery run, lifecycle, memory generation, proof, provider
request, Scheduler runtime, database mutation, wrapper application, external
application marker, git-provenance manifest, or push was executed by this lane.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_ONE_USE_AUTHORIZATION_PASS`

This lane issues exactly one fresh one-use `WINDOW_15M` authorization package
bound to the post-audit exact HEAD. It does not run the 15-minute command.

## 2. Exact starting baseline

| Item | Exact value |
| --- | --- |
| Required / observed HEAD | `e07ff977292d79f36a2067319187a0ad1f17f2f7` |
| Commit subject | `Audit current-head authoritative 15m readiness` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked / staged trees | Clean |
| Relevant Printer processes | None |
| Active / locked Scheduler residue | Zero |
| Push | Not performed |
| `/private/tmp/mp-preclaim` | Detached `8fb4256c70d4e81660c177238253322cb37ae947` — untouched |
| Preserved untracked operator evidence | `.DS_Store`; `operator-runs/v2-9-8b-authoritative-mig050/`; `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/` |

## 3. Controlling readiness

Controlling readiness document:

`docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-operational-re-readiness-audit.md`

| Field | Value |
| --- | --- |
| Readiness commit | `e07ff977292d79f36a2067319187a0ad1f17f2f7` |
| Readiness verdict | `V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_OPERATIONAL_RE_READINESS_AUDIT_PASS` |
| Classification | `READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION` |

All mutable bindings were rechecked immediately before package creation.

## 4. New authorization ID

`V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`

Generated once from UTC timestamp. Distinct from every prior authorization,
including:

- `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` (consumed)
- `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` (consumed)
- `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` (consumed)
- `V2_9_8B_EXACT_OFFLINE_PUBLIC_COMPOSITION_AUTH_20260803_01` (consumed offline)

Package path:

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/`

External application directory at issuance: **absent**

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`

## 5. Package contents

| File | Role |
| --- | --- |
| `final_authorization.json` | Canonical authorization document (mode `0444`) |
| `final_authorization.sha256` | Exact SHA-256 of the JSON bytes |
| `binding_inventory.json` | Bound identities inventory |
| `readiness_reference.md` | Controlling readiness reference |
| `authorization_report.md` | Package-local authorization summary |
| `exact_manual_command.md` | Exact manual PowerShell command with real path and hash |
| `consumed_on_start_rule.md` | Permanent consumed-on-start law |
| `stop_conditions.md` | Stop / fail-closed conditions |

Exact `final_authorization.json` SHA-256:

`1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680`

This lane does **not** create the external application marker or git-provenance
manifest. The wrapper must create those on actual execution.

## 6. Bound identities

### 6.1 Git

| Field | Value |
| --- | --- |
| Full HEAD | `e07ff977292d79f36a2067319187a0ad1f17f2f7` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Exact HEAD required | `true` |
| Tracked worktree must be clean | `true` |

### 6.2 Authoritative database

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| SHA-256 | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` |
| Size | `65806336` |
| `mtime_ns` | `1785707543679666859` |
| inode | `1230526` |
| WAL / SHM / journal | absent / absent / absent |
| Migration count | `50` |
| Migration head | `050_campaign_scheduler_ownership_scope.sql` @ `2026-08-01 20:44:32` |

Package hash/stat binding did not open SQLite. Separate read-only residue checks
confirmed zero active or locked Scheduler jobs before packaging.

### 6.3 Migration-050 retained package

| Field | Value |
| --- | --- |
| Execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| File count | `12` |
| Listing digest (sorted `shasum -a 256` output) | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` |
| Re-invoke Migration-050 | **Forbidden** |

### 6.4 Launch chain

| File | Bytes | Git blob | SHA-256 |
| --- | ---: | --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `878` | `a7fd77e680fa48dff911982d1491462185b5699a` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `42875` | `64b8a305765bb0967ae1f57301d8bcee70db22a3` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `30802` | `73d5ac306eee0241dcb3d1b97bd353fa950bd470` | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `177721` | `1b47078ad0e619bb589ffc44f6c1d06aaecfe48e` | `92b92d67c7daba913839834a5ef5834b9f902c3b12d4140291c5983c459df510` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `34700` | `e4f1eb046d8ce9c4def2840d9ffb80edd679589a` | `b41678d3b1ff08ae9dccca9639b7f412e104356805683bfcab178f4a72ff47fe` |

Schema / marker bindings:

- manifest: `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1`
- application marker: `PRINTER_V1_APPLICATION_MARKER_V1`
- wrapper: `PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1`
- authorization schema: `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`

## 7. Authorized command law

| Field | Value |
| --- | --- |
| Mode | `run` |
| Operator approved | `true` |
| Allowed invocation count | `1` |
| Automatic retry | `false` |
| Manual rerun | `false` |
| Resume | `false` |
| Restart | `false` |
| Successor | `false` |
| Manual Terminal execution only | `true` |
| Wrapper required | `true` |
| Direct operational-command invocation | **Forbidden** |

Entry:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

→ `printer_v1.operator_cli.window_15m_one_shot_wrapper`

→ one child `printer_v1.operator_cli.operational_memory_factory_command` only

## 8. Campaign policy

| Field | Value |
| --- | --- |
| Main window | `WINDOW_15M` (`900` s) |
| Total duration | `1200` s |
| Token capacity | `2` |
| Campaign count | `1` |
| Cycle count | `1` |
| Selective 1h continuation | `false` |
| Continuous 4h | `false` |
| Locked longer windows | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| Solana-only | `true` |
| Solana memecoin-only | `true` |
| Paper-only | `true` |
| Retrieval / financial capability | **Not authorized** |
| Source owner | `SOURCE_GOVERNOR` |
| Scheduler owner | `CENTRAL_SCHEDULER` |

## 9. Consumption law

Authorization is **permanently consumed when wrapper execution begins**,
regardless of PASS, block, safe-stop, interruption, or failure.

Consumed authorizations are permanently non-reusable. No retry, rerun, resume,
restart, or successor is authorized under this ID.

## 10. Environment-shape result

Presence and shape only. No secret values printed, hashed, or exposed. No
provider contacted.

| Item | Result |
| --- | --- |
| `/Users/Dtwo1/.config/printer-v1/secrets.env` permissions | `0600` |
| `PRINTER_SOLANA_RPC_URL` | Present, non-empty |
| `PRINTER_HELIUS_API_KEY` | Present, non-empty |
| `SOLANA_TRACKER_API_KEY` | Present, non-empty |

## 11. Exact manual PowerShell command

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json `
  -AuthorizationSha256 1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680 `
  -OperatorApproved
```

Application-time note: live HEAD must equal authorized HEAD
`e07ff977292d79f36a2067319187a0ad1f17f2f7`, tracked trees must be clean, and
current evidence packages (this authorization package and Migration-050) must be
present as **untracked** evidence for wrapper Git-provenance reconciliation.

## 12. Stop conditions

Stop / do not apply if any of:

- HEAD or branch differs from the authorization binding
- tracked tree dirty with unexpected product changes
- authorization package missing, modified, or already consumed
- external application directory or marker already exists for this ID
- authoritative DB identity drift
- launch-chain identity drift
- Migration-050 package identity drift or re-invocation attempt
- any active or locked Scheduler residue
- any relevant Printer process present
- any retry / rerun / resume / restart / successor under this authorization
- any 1h or 4h continuation under this authorization
- direct operational-command invocation
- any wallet, signing, funds, retrieval, decision, position, trade, audit, or PnL path
- any mutable binding change after package creation (invalidate; do not silently regenerate in this lane)

## 13. What remains locked

- wrapper application and operational-command execution until operator applies this package after independent review PASS
- provider/source contact and paid APIs until authorized child runtime
- memory retrieval, paper decisions, BUY/SELL/HOLD
- positions, trades, audits, and PnL
- longer windows and continuous 4h
- wallets, private keys, real funds, live execution
- scoring, ranking, confidence, weighting, embeddings, and vectors

## 14. What this lane did not run

- the 15-minute command
- the one-shot wrapper
- external marker or manifest creation
- provider contact
- authoritative database mutation
- push

## 15. Independent review

Independent static review is performed in the same combined lane and recorded in:

`docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-one-use-authorization-independent-review.md`
