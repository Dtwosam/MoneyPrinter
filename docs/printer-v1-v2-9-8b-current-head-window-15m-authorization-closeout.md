# V2-9.8B Current-HEAD WINDOW_15M Authorization Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Fresh One-Use WINDOW_15M Authorization Package`

Baseline branch: `grok/v2-9-8b-holder-partial-transport-count-repair`
Baseline HEAD: `7dcadbfb02ef93f2b8e955ab6c23d8a62dc5e14a`

## Verdict

`V2_9_8B_CURRENT_HEAD_WINDOW_15M_AUTHORIZATION_PASS`

One fresh one-use authorization package was created, bound to the exact current
HEAD and the exact current authoritative operational database, and then
independently reviewed as a separate operation. The authorization is **unused**.
No campaign, provider, discovery, Source Governor, Central Scheduler, lifecycle,
memory, retrieval, decision, position, trade, audit, or PnL activity occurred.

## 1. Exact HEAD

| Item | Value |
|---|---|
| Branch (baseline and bound) | `grok/v2-9-8b-holder-partial-transport-count-repair` |
| Full commit SHA | `7dcadbfb02ef93f2b8e955ab6c23d8a62dc5e14a` |
| Subject | `Preserve partial holder transport counts` |
| Tracked tree at creation | clean |
| Untracked operator packages | preserved (mig050, `…160827Z`, `…164530Z`) |
| `/private/tmp/mp-preclaim` | not touched, not read |

## 2. Package

| Item | Value |
|---|---|
| Authorization identity | `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z` |
| One-use nonce | `8d7fea71efeb60619ae1fbc432fa294e` |
| Package root | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z/` |
| Canonical document | `final_authorization.json` |
| Package SHA-256 | `0b3bd62dd912c7292c9dbb159def963f768e3c0e6e30b624ff90cfd3d420316e` |
| Schema | `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` |
| Canonical bytes | `json.dumps(payload, indent=2) + "\n"`, UTF-8 |
| Created at | `2026-08-04T21:49:01.218180Z` |
| Expires at | `2026-08-05T21:49:01.218180Z` (86,400 s) |
| Files in package | 7 |
| Tracked | no — untracked by established operator-package policy |

Package files: `final_authorization.json`, `final_authorization.sha256`,
`binding_inventory.json`, `authorization_report.md`,
`consumed_on_start_rule.md`, `stop_conditions.md`, `exact_manual_command.md`.

The package was written by the existing canonical authorization-package owner
format into the established operator authorization location
(`AUTHORIZATION_PACKAGE_ROOT`). No new launcher, second authorization mechanism,
parallel command path, migration, or production behaviour change was introduced.
No production source file was modified in this lane.

## 3. Repository and database bindings

| Field | Value |
|---|---|
| Repository path | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Authorization package root | `operator-runs/v2-9-8b-window-15m-final-authorization` |
| Migration package root | `operator-runs/v2-9-8b-authoritative-mig050` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Retained migration files | 12, listing digest `67ddde51aa53b9290703bfd3287ab53ce58e9ceaccdc3d3fa67c9624ea35bbbd` |
| Database path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Database SHA-256 | `a9c1472016dd1909df06897cc7e7257347f8af6d3f6927dc5cbc19dba21f6233` |
| Size | 67862528 |
| inode | 1230526 |
| `mtime_ns` | 1785862166532276815 |
| Migration count / head | 51 / `051_permanent_discovery_availability.sql` |
| `quick_check` | `ok` |
| Foreign-key violations | 0 |
| Sidecars (`-journal`, `-wal`, `-shm`) | absent before and after |

The database was hashed as a regular file. The migration ledger and integrity
facts were read through a `mode=ro&immutable=1` SQLite URI, which cannot write
and cannot create a sidecar. Bytes, `mtime_ns`, and inode were identical after
the review. The database identity differs from every previous authorization
package — historical values were not copied.

## 4. Exact approved command chain

```text
scripts/Start-PrinterV1-Window15M-OneShot.ps1
  -> .venv/bin/python -m printer_v1.operator_cli.window_15m_one_shot_wrapper
       --authorization-file … --authorization-sha256 … --operator-approved
  -> .venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command
       run --operator-approved
```

Mode: `run`. Operator approval: required. Direct invocation of the operational
command is not authorized. Alternate launchers are not authorized.

| Launch-chain file | SHA-256 |
|---|---|
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `58b65975bf16f745250e7ec3491815d3f878dc984b693eec9d6cec20d9e73df1` |

These were read from the current production chain, not copied from a historical
package; `operational_memory_factory_command.py` and
`window_15m_one_shot_wrapper.py` both differ from the values in earlier
authorizations.

### Approved environment-variable names (names only)

Wrapper-supplied bindings (created by the wrapper, never by this lane):

* `PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH`
* `PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256`
* `PRINTER_V1_APPLICATION_MARKER_PATH`
* `PRINTER_V1_APPLICATION_MARKER_SHA256`

Operator-supplied source bindings:

* `PRINTER_SOLANA_RPC_URL`
* `PRINTER_HELIUS_API_KEY`

No value, fragment, length, or digest of any secret is recorded in the package
or in this closeout.

## 5. Authorization scope and one-use restrictions

The package authorizes exactly:

```text
one manual authoritative WINDOW_15M campaign attempt
```

Policy bound: 1 campaign, 1 cycle, token capacity 2, main window `WINDOW_15M`
(900 s), total duration 1,200 s, `WINDOW_5M_MICRO_EVENT` support-only, zero
automatic retries, Source Governor as source owner, Central Scheduler as
scheduler owner, Solana-only, Solana-memecoin-only, paper-only.

Consumed when wrapper execution begins, permanently non-reusable afterwards,
regardless of PASS, block, safe stop, interruption, or failure.

Explicitly prohibited (all recorded as hard `false` / locked in the package):

reuse; retry; rerun; resume; restart; automatic successor; concurrent or second
execution; discovery-only substitutes; `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`,
`WINDOW_24H`; live wallet or private keys; real funds or live execution;
retrieval; paper decisions; BUY/SELL/HOLD; paper positions; trade events; paper
trade audits; PnL; paid API dependency; embeddings, vectors, scoring, ranking,
confidence, or weighted decisions; Source Governor or Central Scheduler bypass.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently unlock
memory outcomes, retrieval, decisions, positions, or PnL — recorded as five
separate `false` fields.

## 6. Independent review result

`V2_9_8B_CURRENT_HEAD_WINDOW_15M_AUTHORIZATION_REVIEW_PASS` — **14 checks, 14
passed, 0 failed.**

Creation and review were separate operations. The reviewer re-derived every
binding independently from the filesystem, the live Git state, and a read-only
database open, and drove the production package resolver
(`window_15m_one_shot_wrapper._resolve_authorization`) against the exact
generated bytes. It never built a manifest or marker, never called
`apply_authorization_once`, and never consumed the authorization.

| # | Check | Result |
|---|---|---|
| 1 | package schema and canonical bytes | PASS — schema `…_V2`; re-serialised bytes byte-identical; verdict `_PASS`; ID path-safe and equal to directory name |
| 1.1 | sidecar digest agreement | PASS — `final_authorization.sha256` equals the on-disk digest |
| 1.2 | production resolver accepts package | PASS — production `_resolve_authorization` returns the exact ID and path |
| 2 | exact HEAD binding | PASS — bound head = live head = `7dcadbfb…`; branch matches; `exact_head_required` and `tracked_worktree_must_be_clean` true |
| 3 | repository and database identity | PASS — path, SHA-256, size, inode, `mtime_ns`, 51 migrations, head `051_…`, no sidecars |
| 4 | launcher → wrapper → operational command binding | PASS — all four SHA-256 values recomputed and matched; launcher text invokes the wrapper module; child argv `run --operator-approved`; direct invocation false |
| 4.1 | wrapper child module matches bound operational command | PASS — production wrapper launches the bound module |
| 5 | one-use and expiry restrictions | PASS — invocation count 1; `expires_at` > `authorized_at`; 86,400 s validity; 32-hex nonce |
| 6 | manual-start requirement | PASS — operator approval, manual-terminal-only, manually-started-only; automatic and scheduled start false |
| 7 | retry and successor prohibition | PASS — 15 prohibition flags all `false`; `automatic_retries` = 0 |
| 8 | capability-lock preservation | PASS — all 24 required locks present; `WINDOW_15M` main; selective 1h false; longer windows locked; 5m unlocks nothing; no Governor/Scheduler bypass |
| 9 | absence of secret values | PASS — names only; no live secret value present in the bytes; no key/secret/token value pair; no URL literal |
| 10 | no authorization consumption | PASS — external application directory absent; no marker, manifest, `application_started.json`, campaign exit, or terminal evidence; 7 package files; bytes unchanged |
| 11 | no campaign, provider, Scheduler, lifecycle, or memory activity | PASS — database bytes/`mtime_ns`/inode unchanged, no sidecars, no wrapper or operational process, tracked tree clean |

## 7. Tests and counts

| Suite / check | Result |
|---|---|
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` + `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` | **92 passed** |
| Independent package review (14 checks) | **14 passed** |
| `compileall` — `window_15m_one_shot_wrapper.py`, `git_provenance_authorization_manifest.py` | OK |
| `git diff --check` | OK |
| Tracked-tree status at creation and after review | clean |

The two suites are the existing minimum tests covering authorization-package
generation and validation, exact-HEAD and database binding, one-use enforcement,
launcher → wrapper → operational-command binding, and forbidden capability
locks. No provider, discovery, Scheduler runtime, `WINDOW_15M`, or unrelated
full suite was run. No tracked test needed a lane-specific correction.

## 8. Authorization remains unused

* External application directory
  `~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z`
  does not exist.
* No `git-provenance-manifest.json` and no `application-marker.json` were
  created anywhere by this lane.
* No `application_started.json`, campaign exit, or terminal evidence exists in
  the package.
* The package bytes hash to `0b3bd62d…` before and after review.

The two most recent prior authorizations (`…160827Z`, `…164530Z`) are already
consumed — both have external application directories — and must not be reused.

## 9. Confirmation that no campaign or source execution occurred

No provider, RPC, discovery, Source Governor, Central Scheduler, lifecycle,
snapshot, memory, retrieval, decision, position, trade, audit, or PnL code path
was executed. The authoritative database was never opened writable and is
byte-identical to its state at package creation. `/private/tmp/mp-preclaim` was
neither read nor modified.

## 10. What remains locked

Retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
trade audits, PnL, live wallets, private keys, real funds, live execution, paid
API dependency, embeddings, vectors, scoring, ranking, confidence, weighted
decisions, Source Governor bypass, Central Scheduler bypass, `WINDOW_1H`,
`WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`, selective-1h continuation, automatic
retry/rerun/resume/restart/successor, concurrent or second execution, and
discovery-only substitutes.

Freeze depth `4`, surplus target `8`, liquidity floor `$3,000`, ceiling `30`,
and reservations `3/2/6/7/8/4` are unchanged.

## 11. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition |
|---|---|
| **Any new commit on the baseline branch invalidates the package.** The validator compares `authorized_git.head` to live `git rev-parse HEAD`, and rejects detached HEAD because `rev-parse --abbrev-ref HEAD` returns `HEAD`. | This closeout is therefore committed on the sibling lane branch `agent/v2-9-8b-current-head-window-15m-authorization`, leaving `grok/v2-9-8b-holder-partial-transport-count-repair` pinned at `7dcadbf`. The operator must check out that branch — not the lane branch — before invoking the command. Any further commit to the baseline branch requires a fresh authorization. |
| **Expiry is not machine-enforced.** The production wrapper never reads `expires_at`; it is recorded as `expiry_enforcement: OPERATOR_ENFORCED_ONLY`. | The operator must not invoke the command after `2026-08-05T21:49:01Z`. Making expiry machine-enforced would be a production behaviour change, which this lane may not make. |
| The database is a mutable binding and can drift before application. | Bound by exact SHA-256, size, inode, and `mtime_ns`; the wrapper and the campaign preflight recheck identity at application time, and a drifted database fails closed. |
| The authorization is consumed by a blocked or safe-stop attempt. | Explicit one-attempt semantics. A block consumes it; no retry, rerun, or successor is authorized. |
| The attempt guarantees no outcome. | `honest_terminal_law` records that clean memory, eligible two-token supply, and provider success are not guaranteed, and that exit code zero is not a memory PASS. |
| Package creation could have succeeded while review failed. | Creation and review are separate operations; review PASS is a precondition for the operator step below. |
| The 16 pre-existing test failures recorded in the holder-partial-transport-count-repair closeout remain open. | Outside this lane; none are in the authorization, wrapper, or provenance suites, both of which are fully green. |

## 12. Exact next operator step

Manually, from an operator terminal, with the working tree on branch
`grok/v2-9-8b-holder-partial-transport-count-repair` at exact HEAD
`7dcadbfb02ef93f2b8e955ab6c23d8a62dc5e14a` and a clean tracked tree, run exactly
once:

```powershell
./scripts/Start-PrinterV1-Window15M-OneShot.ps1 -AuthorizationFile 'operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z/final_authorization.json' -AuthorizationSha256 '0b3bd62dd912c7292c9dbb159def963f768e3c0e6e30b624ff90cfd3d420316e' -OperatorApproved
```

Then capture terminal evidence immediately and open a separate independent
campaign closeout lane. Do not issue a second command. Do not push.

## Commit subject

`Authorize current-head WINDOW_15M attempt`
