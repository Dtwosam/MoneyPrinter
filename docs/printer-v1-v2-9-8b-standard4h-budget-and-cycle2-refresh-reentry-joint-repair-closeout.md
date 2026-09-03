# Printer V1 — Standard-4H Budget + Cycle-2 Refresh Re-entry Joint Repair Closeout

Status: **CLOSED PASS as implementation + bounded proof only**

Lane:

`STANDARD-4H BUDGET + CYCLE-2 REFRESH-REENTRY JOINT REPAIR — IMPLEMENTATION + BOUNDED PROOF`

Final verdict:

`V2_9_8B_STANDARD4H_BUDGET_AND_CYCLE2_REFRESH_REENTRY_JOINT_REPAIR_IMPLEMENTATION_BOUNDED_PROOF_PASS`

Component results:

```text
BUDGET_REPAIR_PASS
CYCLE2_REFRESH_REENTRY_REPAIR_PASS
JOINT_SEAM_PASS
```

This closeout does not run Printer, prepare or apply an authorization, contact
providers/RPC/WebSockets, run Central Scheduler, or mutate the authoritative
DB. Focused tests alone do not establish live 4/2/2 readiness.

---

## 1. Baseline and identities

| Item | Value |
|---|---|
| Branch | `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` |
| Implementation baseline HEAD | `1a505ac1234d94f584d9001ece796bb06373d234` |
| Live implementation HEAD | this closeout commit (`git rev-parse HEAD` after it exists) |
| Authoritative DB | `data/printer_v1.sqlite3` |
| DB SHA-256 before | `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e` |
| DB SHA-256 after | `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e` |
| Consumed authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` permanently non-reusable |
| Future prior-non-reuse root | 60 IDs |

Governing design:

`docs/printer-v1-v2-9-8b-standard4h-budget-and-cycle2-refresh-reentry-joint-repair-design.md`

Design verdicts remain:

- `V2_9_8B_STANDARD4H_BUDGET_AND_CYCLE2_REFRESH_REENTRY_JOINT_REPAIR_DESIGN_PASS`
- `V2_9_8B_FOUR_TOKEN_STANDARD4H_PER_TOKEN_REQUEST_CEILING_WIRING_REPAIR_DESIGN_PASS`
- `V2_9_8B_SEP3_CYCLE2_DUPLICATE_TRANSPORT_ACQUISITION_REPAIR_DESIGN_PASS`

No production-code drift existed at the implementation baseline. Tracked tree
was clean except historical untracked `operator-runs/` residue.

---

## 2. Exact production files changed

```text
src/printer_v1/operator_cli/one_command_15m_factory.py
src/printer_v1/discovery/pre_lifecycle_refresh_composition.py
```

Unchanged, as designed:

- `direct_migration_discovery.py`
- Source Governor core
- Central Scheduler
- `CampaignSixUnitOwner`
- `canonical_transport_identity_key`
- authorization/wrapper code
- schema/migrations
- `load_completed_cooperative_mint_market_batch_mints`

---

## 3. Exact tests changed/added

Added/extended:

```text
tests/test_v2_9_8b_standard4h_pre4h_request_ceiling_wiring.py
tests/test_v2_9_8b_cycle2_pump_live_tail_refresh_reentry_repair.py
tests/test_v2_9_8b_standard4h_budget_and_cycle2_refresh_reentry_joint_seam.py
```

Historical mint-batch tests run, not modified:

```text
tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py
```

Nearest existing refresh-composition tests run because that file changed:

```text
tests/test_v2_9_8b_persistent_multisource_refresh.py
tests/test_v2_9_8b_4_2_2_followup_repairs.py
tests/test_v2_9_8b_refresh_internal_failure_truth.py
```

---

## 4. Budget helper / wiring

Added `_token_ceiling_for_run_config(config)` beside the existing run and
Scheduler selectors. Four-token reads
`scaled_standard_four_hour_capacity_contract(4)["lifecycle_requests_per_token"]`
(`118`). Continuous/selective-1h remains `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN`
(`50`). 15m-only remains `_MAX_GOVERNED_REQUESTS_PER_TOKEN` (`22`).

`_enforce_budgets_before_step` pre-4h branch now uses that helper. Comparison
remains `current + projected > ceiling`. Genuine overshoot still raises
`_GlobalStop` with `SAFE_STOP_BUDGET_CEILING_EXCEEDED` /
`CUMULATIVE_LIFECYCLE`.

Unchanged:

- `_request_ceiling_for_run_config` four-token `476`
- `_scheduler_ceiling_for_run_config` four-token `444`
- `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = 50`
- `_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN = 50`
- `_MAX_GOVERNED_REQUESTS_PER_TOKEN = 22`
- retries `0`
- endpoint rotation `false`
- two-token Standard-4H `102 / 50` residual
- `_run_budgets` reporting

Admission-health continues to call `_enforce_budgets_before_step` and therefore
inherits four-token `118`.

---

## 5. Cycle-2 completed-HEAD skip

Added `cycle_pump_live_tail_head_already_completed` in
`pre_lifecycle_refresh_composition.py`. It rehydrates Source Governor
`COMPLETE` + `CLEAN_DATA` Pump signature-page rows under the cycle-scoped
request-key root, then compares `canonical_transport_identity_key` against the
existing HEAD identity from `direct_migration_signature_page_target_identity`.

SQL `LIKE` is not trusted alone; `request_key_belongs_to_root` is required.
Missing source tables do not skip (no completed evidence). Failures, PARTIAL,
non-CLEAN_DATA, foreign roots, different cursors, and malformed identities do
not skip.

Pump branch of `refresh_stage` checks the helper after existing
transport-configured / worst-case-budget checks and **before**
`channels_attempted.append` or `run_direct_migration_discovery`. Skip records
`CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED` /
`CANONICAL_TRANSPORT_ALREADY_COMPLETED` with `source_requests = 0`, then uses
existing `continue`.

Cooperative 4/2/2 ordinal 1 remains Pump-first. Completed HEAD completes that
ordinal with 0 new operations. Ordinal 2 still selects DexScreener first.
Non-cooperative full-stage skip continues peer channels. Timing
`+600 / +1200 / +1800 / +2400` is unchanged.

---

## 6. Duplicate-guard / identity preservation

No change to:

- `canonical_transport_identity_key`
- `CampaignSixUnitOwner`
- `MeasuredTransportLedger`
- `DUPLICATE_TRANSPORT_IDENTITY`

Direct injection of a genuine duplicate canonical Pump HEAD identity into
`CampaignSixUnitOwner` still raises `DUPLICATE_TRANSPORT_IDENTITY`.

---

## 7. Focused test counts / results

All PASS. No live providers. Disposable SQLite only.

| File | Collected | Result |
|---|---|---|
| `tests/test_v2_9_8b_standard4h_pre4h_request_ceiling_wiring.py` | 18 | PASS |
| `tests/test_v2_9_8b_cycle2_pump_live_tail_refresh_reentry_repair.py` | 7 | PASS |
| `tests/test_v2_9_8b_standard4h_budget_and_cycle2_refresh_reentry_joint_seam.py` | 1 | PASS |
| `tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py` | 6 | PASS |
| `tests/test_v2_9_8b_persistent_multisource_refresh.py` | 9 | PASS |
| `tests/test_v2_9_8b_4_2_2_followup_repairs.py` | 5 | PASS |
| `tests/test_v2_9_8b_refresh_internal_failure_truth.py` | 15 | PASS |
| **Total this lane** | **61** | **PASS** |

Also: `py_compile` on touched production Python; `git diff --check` clean.

Budget proofs include four-token `50+1`, Sep-3 `51+0`, `117+1`, `118+0` allow;
`118+1` and `119+0` `_GlobalStop`; selective-1h `49+1` allow / `50+1` stop;
15m `22+1` stop; two-token residual still `50`.

Cycle-2 proofs include exact empty HEAD replay, re-entry idempotence, cursor
distinction, cycle/campaign isolation, cooperative ordinal-2 DexScreener-first,
non-cooperative peer continuation, and strict duplicate-guard regression.

Joint seam proves four-token `51` is lawful under `118` while Cycle-2 refresh
ordinal 1 skips completed HEAD and ordinal 2 still has DexScreener work.

---

## 8. Known out-of-scope debts

Unchanged and not repaired:

- two-token Standard-4H factory pre-4h `102 / 50` residual
- selective-1h catalog mismatch (`92 / 45` vs factory `102 / 50`)
- `_run_budgets` non-4h reporting inline `50`
- failed / non-CLEAN Pump evidence collision behavior
- Cycle-2 timing / provider availability
- Source Governor core, Scheduler core, direct-migration architecture

---

## 9. Locks and non-authority

No live Printer run. No authorization preparation or application. Consumed
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` remains permanently
non-reusable. Source Governor remains sole source-request owner. Central
Scheduler remains sole scheduling owner. Permanent V1 locks unchanged.
`WINDOW_12H` / `WINDOW_24H`, retrieval, and BUY/SELL/HOLD remain locked.

Focused tests do **not** claim live 4/2/2 readiness.

---

## 10. Exact next lane

```text
INDEPENDENT CODE / PROOF REVIEW — STANDARD-4H BUDGET + CYCLE-2 REFRESH-REENTRY JOINT REPAIR
```

Do not prepare another authorization. Do not run Printer. A later fresh
readiness lane is required after independent review.

STOP.
