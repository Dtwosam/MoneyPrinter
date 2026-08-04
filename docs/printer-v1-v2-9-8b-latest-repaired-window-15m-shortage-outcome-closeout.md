# Printer V1 V2-9.8B Latest Repaired WINDOW_15M Shortage Outcome Closeout

Date: 2026-08-03

Lane:

```text
V2-9.8B Full WINDOW_15M Pre-Lifecycle Readiness and Exact Success-Path Repair
```

Phase:

```text
Phase 0 — Close the consumed attempt (evidence only)
```

Authorization:

```text
V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z
```

Execution:

```text
20260803T233517Z-cf35a4925238
```

Lane type: evidence closeout only. No source/test edit, provider contact,
wrapper execution, authorization creation, campaign, DB mutation, or memory-window
start. No reset, clean, or deletion of evidence.

## 1. Verdict (Phase 0)

```text
V2_9_8B_LATEST_REPAIRED_WINDOW_15M_SHORTAGE_OUTCOME_CLOSEOUT_PASS
```

Honest terminal classification of the consumed attempt:

```text
SOURCE_VISIBILITY_SHORTAGE
```

Lifecycle did not start. Factory run and memory window were not created.
Authorization is consumed exactly once and permanently non-reusable. Six-unit
accounting completed. Cleanup and lease release completed. Active and locked
residue is zero. No retry, restart, resume, or successor exists.

This phase does **not** authorize another live attempt. Remaining repair work
is owned by Phases 1–4 of the same lane.

## 2. Baseline at Phase 0 start

| Item | Value |
| --- | --- |
| Required / start HEAD | `3c426ad546511f759309714c2c3b56d3faf5823e` |
| Start subject | `Rollover consumed repaired 15m authorization` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Detached HEAD | No |
| Tracked / staged trees at start | Clean (only untracked operator evidence) |
| Untracked at start | eight-file auth package `…232743Z`; Migration-050 package |
| `/private/tmp/mp-preclaim` | Detached `8fb4256c70d4e81660c177238253322cb37ae947` — untouched |
| Push | Not performed |

## 3. Required evidence presence

| Evidence surface | Path | Present |
| --- | --- | --- |
| External application directory | `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/` | Yes |
| Wrapper terminal | `…/wrapper-terminal.json` | Yes |
| Child stdout | `…/child-stdout.txt` (120383 bytes, sha256 `425db20b…`) | Yes |
| Child stderr | `…/child-stderr.txt` (0 bytes, empty) | Yes |
| Application marker | `…/application-marker.json` | Yes |
| Git provenance manifest | `…/git-provenance-manifest.json` | Yes |
| Execution directory | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T233517Z-cf35a4925238/` | Yes |
| Campaign report | `…/reports/20260803T233517Z-cf35a4925238-report.campaign-report.json` | Yes |
| Terminal summary | `…/terminal-summary.json` | Yes |
| Pre-campaign backup | `…/printer_v1.pre-campaign.backup.sqlite3` | Yes |
| Authoritative DB | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` | Yes |
| Exact eight-file authorization package (repo) | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/` | Yes |
| Auth restore copy (tmp) | `/private/tmp/mp-auth-restore-V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/` | Yes (byte-equal) |

No required evidence surface is missing. Evidence was not reset, cleaned, or deleted.

## 4. Consumed-attempt verification matrix

| Check | Result | Evidence |
| --- | --- | --- |
| Authorization consumed exactly once | **PASS** | Marker: `allowed_invocation_count=1`, `authorization_consumed_at=2026-08-03T23:35:16.710482+00:00`; single application directory for this auth id; wrapper `automatic_retries=0`, `manual_reruns=0`, `restarts=0`, `resumes=0`, `successors=0` |
| Child exited `0` | **PASS** | Wrapper: `child_exit_code=0`, `terminal_classification=CHILD_EXITED_ZERO` |
| First terminal cause `SOURCE_VISIBILITY_SHORTAGE` | **PASS** | Terminal summary + campaign report + cleanup: `first_terminal_cause=SOURCE_VISIBILITY_SHORTAGE` |
| Lifecycle did not start | **PASS** | `lifecycle_started=false`; `run_status=NOT_STARTED`; `status=OPERATIONAL_CAMPAIGN_PRE_LIFECYCLE_TERMINAL` |
| No factory run created | **PASS** | Reconciliation: `factory_run=not_found`; `scope.factory_run_id=null`; `factory_run_step_jobs=0` |
| No memory window created | **PASS** | Reconciliation: `windows={}`; cleanup `cancelled_windows=0` |
| Six-unit accounting completed | **PASS** | `accounting_status=SIX_UNIT_ACCOUNTING_COMPLETE`; `accounting_error=null`; report `six_unit_evidence_match=true` |
| Cleanup completed | **PASS** | `cleanup.cleanup_completed=true` at `2026-08-03T23:35:48.427089+00:00` |
| Lease released | **PASS** | `cleanup.lease_released=true` at same timestamp |
| No retry / restart / resume / successor | **PASS** | Marker forbids all; wrapper counters all zero; cleanup/reconciliation: `restart_created=false`, `resume_created=false`, `successor_created=false`, `automatic_retries=0`; `new_child_work_allowed=false` |
| Active residue zero | **PASS** | `active_owned_work_after=0`; `active_jobs=0`; `active_work_rows=0`; `pending_or_running_run_steps=0`; `clean_terminal=true` |
| Locked residue zero | **PASS** | `locked_job_ids=[]`; `terminal_work_with_active_job=0` |
| Campaign acceptance honest block | **PASS** | `campaign_acceptance_verdict=HONEST_BLOCKED`; `campaign_pass=false` |
| Eligible capacity shortfall | **PASS** | Exhaustion certificate: `eligible_count=0`, `required_eligible_capacity=2`; liquidity outcomes: 10 below floor, 18 malformed/partial DexScreener; `shortage_classification=SOURCE_VISIBILITY_SHORTAGE` |

### 4.1 Wrapper / marker facts

| Field | Value |
| --- | --- |
| Wrapper schema | `PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1` |
| Wrapper execution id | `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z` |
| Started / ended (UTC) | `2026-08-03T23:35:16.710516+00:00` → `2026-08-03T23:35:48.452779+00:00` |
| Repository HEAD | `3c426ad546511f759309714c2c3b56d3faf5823e` |
| Child command | `.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved` |
| Marker schema | `PRINTER_V1_APPLICATION_MARKER_V1` |
| Authorization sha256 | `2b0bf37ca642f201dba91f31266b29e0c9374347def5a0383a8c0fadcc9cc74a` |
| Automatic retry / manual rerun / restart / resume / successor allowed | All `false` |

### 4.2 Six-unit totals (terminal summary report)

| Unit | Value |
| --- | --- |
| `SOURCE_TRANSPORT_OPERATION` | 13 |
| `SOURCE_RESPONSE_BYTES` | 80759 |
| `NORMALIZED_SOURCE_ROWS` | 56 |
| `LOCAL_VALIDATION_STEP` | 0 |
| `SCHEDULER_WORK_ITEM` | 0 |
| `LIFECYCLE_RESERVED_TRANSPORT_OPERATION` | 0 |

Campaign scheduler calls: `0`. Campaign source calls: `30` (discovery/admission path; lifecycle reserved transport remains 0).

### 4.3 Supply exhaustion summary

| Metric | Value |
| --- | --- |
| Unique tokens observed | 35 |
| Eligible count | 0 |
| Required eligible capacity | 2 |
| Fresh market checks | 28 |
| Source operations used / remaining | 30 / 0 |
| Liquidity outcome `LIQUIDITY_EXACT_BELOW_FLOOR` | 10 |
| Liquidity outcome `LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL` | 18 |
| Rejection `DUPLICATE_ACTIVE_TRACKING` | 2 |
| Rejection `TERMINAL_TRACKING_STATE` | 5 |
| Last reason discovery could not continue | `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` |
| Unexplored work prevented by hard ceiling | `true` |
| Channels unavailable | `dexscreener_exact_pool_market` (as reported under exhaustion certificate) |

Honest block: market/source visibility did not yield two simultaneously eligible candidates under the frozen ceilings and floors. This is not a crash, lease leak, or wrapper-law failure.

## 5. Exact eight-file authorization package (byte-for-byte)

Root (repository):

```text
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/
```

| File | Size | SHA-256 |
| --- | --- | --- |
| `final_authorization.json` | 13976 | `2b0bf37ca642f201dba91f31266b29e0c9374347def5a0383a8c0fadcc9cc74a` |
| `final_authorization.sha256` | 91 | `3a35ca075fcdd8d208775058dc256e400d5965a5d29e71ce6a10dbb993a8a2f1` |
| `binding_inventory.json` | 4060 | `96bbe59996fbdcf707825adfa8f4654bf4281336445a77da4d22f81705a1bdca` |
| `authorization_report.md` | 999 | `8d183075b8917ad23f96abe1d3375c7ac879432064ab1cdceccb1456e1ef36c3` |
| `exact_manual_command.md` | 2497 | `557779a6afc3003bd97e751ddea33be96e2041355cb01c4b80943456120459cd` |
| `consumed_on_start_rule.md` | 389 | `4ebcac028331dccd931e930c312bb134406a77ca88c50c9f1fd5cb4f69410b18` |
| `readiness_reference.md` | 657 | `4828d609f677a9afd607163fa27743e7557f3b25d5a6c981ce23f41c984220b3` |
| `stop_conditions.md` | 1292 | `7c8aadd6c5430278327bdcb7234c544a25d49158e18787fe2c8782b82cad98b4` |

Byte equality:

- Repository package ↔ `/private/tmp/mp-auth-restore-V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/` — **all eight files identical**
- `final_authorization.sha256` content matches SHA-256 of `final_authorization.json` — **PASS**

At Phase 0 start these eight files were untracked. Migration-050 current-evidence package and ignored SQLite files are **not** added.

## 6. Authoritative DB identity (post-attempt)

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | 66113536 |
| SHA-256 | `248bab8a70141c3c429c2823b2eee5669cdbc5d72f689f9a515ce0db60efaad2` |
| Pre-campaign backup path | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T233517Z-cf35a4925238/printer_v1.pre-campaign.backup.sqlite3` |
| Pre-campaign backup SHA-256 | `a4a36867f563d3c900c3b5efffe27b0c8eb7191a8a066ab5e944886a50077b7c` |
| Pre-campaign backup size | 65896448 |

DB was not reset or cleaned by this phase. SQLite files remain gitignored and are not staged.

## 7. Historical evidence action (this commit)

Method:

```text
git add <exact eight existing authorization package files at established path>
git add docs/printer-v1-v2-9-8b-latest-repaired-window-15m-shortage-outcome-closeout.md
```

Commit message:

```text
Close latest repaired 15m shortage evidence
```

Scope:

| Included | Excluded |
| --- | --- |
| Eight auth package files at existing paths | Migration-050 ten current-evidence files |
| This closeout document | Both ignored SQLite DBs |
| | Source/tests |
| | External PrinterOperations surfaces (left in place, not git-added) |

No file content was rewritten. Transition is classification-only: untracked current evidence → tracked historical evidence.

## 8. Hard locks preserved

- Solana-only / Solana memecoin-only / paper-only
- No wallet, private keys, signing, real funds, live execution
- No paid API / no scores / ranks / confidence / weights / embeddings
- No Source Governor or Central Scheduler bypass
- No dirty memory / retrieval / BUY/SELL/HOLD / positions / trades / PnL
- No 1h/4h/12h/24h work
- No new live source call, authorization, wrapper execution, or consumed-auth reuse
- `/private/tmp/mp-preclaim` untouched

## 9. What this phase does **not** claim

- Does not claim the five repair findings are true or false (Phase 1)
- Does not implement repairs (Phase 3)
- Does not prove live provider success-path composition
- Does not create a readiness artifact or new authorization
- Does not reclassify `SOURCE_VISIBILITY_SHORTAGE` as a code crash

## 10. Next lane ownership

Phases 1–4 of:

```text
V2-9.8B Full WINDOW_15M Pre-Lifecycle Readiness and Exact Success-Path Repair
```

Order remains:

```text
evidence closeout (this document)
→ verify audit findings
→ design
→ implementation
→ bounded offline proof
→ closeout
```

Stop after the evidence-only commit for this phase before source work begins.
