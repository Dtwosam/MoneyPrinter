# V2-9.8B.22 — Governed Discovery-Only Qualification Command Surface Closeout

**Lane:** V2-9.8B.22 — Governed Discovery-Only Qualification Command Surface  
**Baseline HEAD:** `a13231a`  
**Implementation commit:** `3b08ac4` — `Build V2-9.8B discovery-only qualification command`  
**Closeout commit:** (this document)  
**Final verdict:**

```text
V2_9_8B_22_DISCOVERY_ONLY_COMMAND_SURFACE_PASS
READY_FOR_OPERATOR_REVIEW_BEFORE_ONE_BOUNDED_DISCOVERY_ONLY_LIVE_QUALIFICATION
```

---

## 1. What was built

### Audit

`docs/printer-v1-v2-9-8b-discovery-only-command-audit.md`

Proved the public command surface had only:

```text
preflight-only | run | status | cooperative-stop | recover-orphan | report-only
```

Production `run` was the only path that exercised V2-9.8B.21 Eligible Token
Supply, and it always created campaign/supervision/lifecycle risk. No
discovery-only public mode existed.

### Design

`docs/printer-v1-v2-9-8b-discovery-only-command-design.md`

Normative public mode `discovery-only`, qualification identity, mutation
allowlist, protected zero-delta tables, terminal statuses, status/report-only
inspection, and disposable proof matrix.

### Implementation

| Artifact | Role |
|---|---|
| `scripts/Start-PrinterV1-MemoryFactory.ps1` | `discovery-only` in ValidateSet |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Public mode + runner + status/report integration |
| `tests/test_v2_9_8b_22_discovery_only_command.py` | Disposable proof matrix (20 tests) |

### Public command (not executed live in this lane)

```bash
pwsh -NoProfile -File scripts/Start-PrinterV1-MemoryFactory.ps1 \
  -Mode discovery-only \
  -OperatorApproved
```

---

## 2. Command ownership

| Layer | Owner |
|---|---|
| PowerShell front door | `scripts/Start-PrinterV1-MemoryFactory.ps1` |
| Python public command | `operational_memory_factory_command.main` |
| Mode entry | `run_discovery_only_qualification` |
| Preflight | `build_activation_preflight` (shared with production) |
| Supply completeness loop | `eligible_token_supply.run_persistent_eligible_token_supply` |
| Market / migration sources | existing adapters via Source Governor |
| Central Scheduler runtime | **not called** |

---

## 3. Exact mutation allowlist

Discovery-only may write only discovery-owned evidence:

* `printer_source_requests` / `printer_source_responses` / `printer_source_failures`
* `printer_source_health` / `printer_source_rate_limits`
* `printer_external_source_operations`
* `printer_pumpswap_graduated_candidate_registry`
* `printer_discovery_batches` / `printer_discovery_work` /
  `printer_discovery_work_source_links` / `printer_discovery_candidates` /
  `printer_discovery_merged_candidates` /
  `printer_discovery_candidate_contributions` /
  `printer_discovery_provider_observations` /
  `printer_discovery_provider_report_links` /
  `printer_discovery_origin_verifications` /
  `printer_discovery_pumpswap_confirmations` /
  `printer_discovery_selection_links` /
  `printer_discovery_selected_item_links`
* `printer_graduated_market_floor_state`
* `printer_eligible_token_reserve` (migration 046)
* `printer_discovery_exhaustion_certificates` (migration 046)
* `printer_pumpfun_finalized_origin_registry` / `printer_pumpfun_origin_cursor`
* `printer_tokens` / `printer_pairs` (intake materialization when used)

Artifact filesystem writes under
`~/PrinterOperations/v2-9-8/<execution_id>/` (qualification report + terminal
summary) are allowed.

Any positive non-allowlisted table delta fails the qualification as
`DISCOVERY_ONLY_FAILED`.

---

## 4. Protected-table zero-delta proof

Protected surfaces (campaign ownership, supervision, factory runs/steps, slots,
windows, Scheduler jobs, tracking queue, memory windows/episodes, retrieval,
paper decisions/positions/trades/audits, proof supervision, snapshot/micro-event/
holder/selection-batch handoff tables) must show **exact zero row-count delta**.

Disposable suite proof:
`test_integrity_fk_locked_deltas_and_no_successor` and
`test_two_eligible_outside_first_six_and_stop_at_two` assert:

* `protected_table_deltas == {}`
* zero campaigns / scheduler jobs / factory steps created
* locked retrieval/financial tables unchanged
* `scheduler_runtime_calls == 0`
* `restart_created == False` / `successor_created == False`

---

## 5. Source and duration ceilings

| Ceiling | Value |
|---|---:|
| Lifecycle admission operation ceiling | 45 |
| Discovery-only operation budget | 30 |
| Evaluation batch size | 6 |
| Required token capacity | 2 |
| Discovery-only duration | 900 seconds |
| Automatic retries / restart / successor | 0 / forbidden |

Stop immediately when two distinct freshly eligible tokens are reserved.

---

## 6. Terminal statuses

| Status | Meaning |
|---|---|
| `DISCOVERY_ONLY_CAPACITY_READY` | Two eligible tokens reserved |
| `DISCOVERY_ONLY_HONEST_EXHAUSTION` | Certificate + true market/visibility shortage |
| `DISCOVERY_ONLY_SOURCE_UNAVAILABLE` | Provider/channel failure |
| `DISCOVERY_ONLY_BUDGET_EXHAUSTED` | Discovery budget exhausted |
| `DISCOVERY_ONLY_DURATION_EXHAUSTED` | Mode duration deadline reached |
| `DISCOVERY_ONLY_FAILED` | Mutation boundary, integrity, residue, or unclassified fault |

Provider, budget, and duration failures are **not** reported as true market shortage.

---

## 7. Proof matrix

Suite: `tests/test_v2_9_8b_22_discovery_only_command.py`  
Result: **20 passed**

| # | Proof | Result |
|---:|---|---|
| 1 | Operator approval required (Python + main + PS1) | PASS |
| 2 | Dirty Git / migration / active work / dependency gates | PASS |
| 3 | Two eligible outside first six | PASS |
| 4 | Round-1 eligible preserved across rounds | PASS |
| 5 | Stop at two | PASS |
| 6 | Zero tracking/Scheduler/factory/window/memory work | PASS |
| 7 | One-token honest exhaustion certificate | PASS |
| 8 | Provider / budget / duration distinct | PASS |
| 9 | Source budget enforced | PASS |
| 10 | Source Governor path (B.21 + fixture governed ledger) | PASS (via supply service) |
| 11 | Deterministic non-ranked selection | PASS |
| 12 | Status + report-only zero source/write inspection | PASS |
| 13 | Failure zero active residue | PASS |
| 14 | Integrity ok / FK clean | PASS |
| 15 | Retrieval/financial zero deltas | PASS |
| 16 | No retry/restart/successor | PASS |
| 17 | PowerShell macOS disposable mode acceptance | PASS |

---

## 8. Regression results

| Suite group | Result |
|---|---|
| V2-9.8B.22 discovery-only command | 20 passed |
| V2-9.8B.21 eligible supply + B.22 + B.19 + B.5/7 productivity + B.4 blocked supply | 75 passed |
| V2-9.8B.10 lifecycle integrity + B.16 batch persistence | 15 passed |
| V2-9.7E.43 front door + B.2 holder budget | 9 passed |

No unrelated product suites run. No live discovery-only or production campaign
executed.

---

## 9. Authoritative readiness review (read-only)

Run only after implementation commit `3b08ac4`:

```text
preflight-only
status
report-only
```

| Gate | Result |
|---|---|
| Clean Git provenance | PASS (`3b08ac4`, tracked tree clean) |
| Migrations | PASS (46; latest `046_eligible_token_supply.sql`) |
| Integrity | PASS (`ok`) |
| FK violations | PASS (`0`) |
| Active operational counts | PASS (all zero) |
| Preflight | PASS `V2_9_8_OPERATIONAL_PREFLIGHT_READY` |
| Status | PASS (source/sched/writes = 0; no discovery-only report yet) |
| Report-only | PASS (campaign report_kind; source/sched/writes/replay = 0; DB bytes unchanged) |
| SQLite sidecars | PASS (none) |
| discovery-only / production executed | **No** |

---

## 10. Money-usefulness contribution

Printer’s money path depends on honest graduated supply before any paper decision
lane. False single-shot shortages and production campaigns that burn operator
attention without multi-round completeness waste the Memory Factory.

This lane gives the operator one **governed, discovery-only** public command to
qualify the B.21 completeness loop against live free sources later — without
opening tracking, Scheduler lifecycle, or financial surfaces. That is the
minimum truthful step between architecture repair and another production attempt.

---

## 11. Remaining limitations

* Completeness remains bounded by free sources and the 30/45/900 ceilings.
* Live market may still be truly thin; that is certified honestly, not invented.
* Status/report-only inspect discovery-only only after a qualification report
  exists under `~/PrinterOperations/v2-9-8/`.
* This lane does **not** authorize or execute the live qualification.
* Historical residual `QUEUED` tracking rows remain in the corpus; preflight
  active counts remain the readiness authority.

---

## 12. What remains locked

* Retrieval activation  
* Paper decisions / BUY / SELL / HOLD  
* Paper positions, trades, audits, PnL  
* Live trading, wallets, private keys, signing, real funds  
* Paid APIs  
* Scoring / ranking / confidence / weighted selection  
* Embeddings / vectors  
* Automatic retry / restart / successor qualifications  
* Lower liquidity floor or one-token two-token campaigns  
* Production Memory Factory `run` authorization from this closeout  
* Automatic operator authorization of discovery-only live qualification  

---

## 13. Next operator action (separate)

```text
One bounded discovery-only live qualification
```

* Requires explicit operator approval at launch time  
* Uses the public command only  
* Must not unlock financial capabilities  
* Must not start a production memory campaign  

Do **not** treat this closeout as automatic authorization.

---

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Detail | Mitigation / status |
|---|---|---|
| Live qualification multi-round Dex spend | More market calls when inventory deep | Budget 30 + stop-at-two |
| True thin market after honest work | Still possible | Exhaustion certificate + distinct statuses |
| Operator confuses discovery-only with production `run` | Mode misuse | Distinct mode, statuses, no campaign rows |
| Status without campaign supervision | Historical assumption | Fallback to discovery-only report |
| Artifact-root report dependency for inspection | File-based identity (no new migration) | Durable JSON under PrinterOperations |
| Residual historical queue rows | Corpus noise | Preflight active counts authoritative |

---

## Final verdict

```text
V2_9_8B_22_DISCOVERY_ONLY_COMMAND_SURFACE_PASS
READY_FOR_OPERATOR_REVIEW_BEFORE_ONE_BOUNDED_DISCOVERY_ONLY_LIVE_QUALIFICATION
```
