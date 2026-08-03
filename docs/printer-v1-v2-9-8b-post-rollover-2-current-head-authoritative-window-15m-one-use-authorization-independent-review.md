# Printer V1 V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M One-Use Authorization Independent Review

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Current-HEAD Authoritative WINDOW_15M One-Use Authorization and Independent Review`

Lane type: fresh static independent review of the final authorization package
bytes. No package rewrite, no wrapper application, no provider contact, no
database mutation, and no push.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_CURRENT_HEAD_AUTHORITATIVE_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS`

## 2. Package under review

| Item | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` |
| Package root | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/` |
| Canonical document | `final_authorization.json` |
| Exact SHA-256 | `1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680` |
| Mode | `0444` |
| Canonical JSON | `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"` byte-identical |
| Authorization report | `docs/printer-v1-v2-9-8b-post-rollover-2-current-head-authoritative-window-15m-one-use-authorization.md` |

## 3. Required checklist

| # | Check | Result |
| --- | --- | --- |
| 1 | Authorization ID is new | **PASS** — distinct from all prior WINDOW_15M and offline composition auth IDs; package directory created once |
| 2 | Exact HEAD is the post-audit commit | **PASS** — `authorized_git.head` = live HEAD = `e07ff977292d79f36a2067319187a0ad1f17f2f7` |
| 3 | DB identity still matches | **PASS** — path/sha256/size/mtime_ns/inode; WAL/SHM/journal absent; matches readiness `d85442e6…` / `65806336` |
| 4 | Launch-chain identities still match | **PASS** — PS1, wrapper, manifest module, operational command `92b92d67…`, and wrapper tests all match bound SHA-256 values |
| 5 | Package hash matches exact bytes | **PASS** — on-disk bytes hash to `1c32c9ee…`; `final_authorization.sha256` agrees; canonical re-serialization identical |
| 6 | No prior external application directory for the ID | **PASS** — `~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` absent |
| 7 | Allowed invocation count is one | **PASS** — `allowed_invocation_count == 1` |
| 8 | Retry/rerun/resume/restart/successor flags are false | **PASS** — all five hard-false |
| 9 | 1h and 4h continuation forbidden | **PASS** — `selective_1h_continuation=false`, `continuous_4h=false`; longer windows locked |
| 10 | Wrapper is the only authorized entry | **PASS** — PS1 → wrapper required; `wrapper_required=true` |
| 11 | Direct operational-command invocation forbidden | **PASS** — `direct_operational_command_authorized=false` |
| 12 | Consumed authorizations not referenced as reusable | **PASS** — prior IDs treated as consumed/non-reusable; this ID permanent consumption on wrapper start |
| 13 | No wallet/signing/funds/retrieval/decision/position/trade/audit/PnL path authorized | **PASS** — capabilities remain locked; paper-only / Solana-memecoin-only; no financial capability |

## 4. Additional binding confirmations

| Binding | Observed | Result |
| --- | --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` | matched |
| Operator approved | `true` | matched |
| Main window | `WINDOW_15M` | matched |
| Token capacity | `2` | matched |
| Campaign / cycle counts | `1` / `1` | matched |
| Manifest schema | `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` | matched |
| Application marker schema | `PRINTER_V1_APPLICATION_MARKER_V1` | matched |
| Authorization schema | `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` | matched |
| Migration count / head | `50` / `050_campaign_scheduler_ownership_scope.sql` | matched |
| Migration-050 listing digest | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` | matched |
| Scheduler active/locked residue | `0` | matched |
| Relevant Printer processes | none | matched |
| `mp-preclaim` HEAD | `8fb4256c70d4e81660c177238253322cb37ae947` | matched / untouched |
| Tracked/staged trees | clean | matched |
| Secrets file mode | `0600` | matched |
| Env shape (`PRINTER_SOLANA_RPC_URL`, `PRINTER_HELIUS_API_KEY`, `SOLANA_TRACKER_API_KEY`) | present non-empty | matched (values not exposed) |

## 5. Mutable-binding post-package recheck

Immediately after package creation and again during this review, mutable
bindings were rechecked. No drift was observed in:

- live HEAD / branch
- authoritative DB identity
- launch-chain file hashes
- package bytes / SHA-256
- external application pre-existence
- Scheduler residue / process presence

Therefore the package is **not** invalidated.

## 6. Application-marker pre-existence result

| Path | Result |
| --- | --- |
| `~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` | **Does not exist** |

No external application marker or git-provenance manifest was created by this
lane.

## 7. Consumption law (reviewed)

Permanent consumption begins when wrapper execution starts, regardless of PASS,
block, safe-stop, interruption, or failure. No reuse, retry, rerun, resume,
restart, or successor is authorized under this ID.

## 8. Exact manual command (reviewed)

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json `
  -AuthorizationSha256 1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680 `
  -OperatorApproved
```

## 9. What this review did not do

- did not run the wrapper or 15-minute command
- did not contact providers
- did not mutate the authoritative database
- did not create external marker/manifest
- did not push
- did not silently regenerate the package

## 10. Final review disposition

All thirteen required independent-review checks PASS. Mutable bindings remain
stable. Authorization package is accepted for a future single manual wrapper
application only after operator prerequisites are satisfied.
