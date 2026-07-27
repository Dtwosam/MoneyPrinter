# V2-9.8B.22 — Governed Discovery-Only Qualification Command Design

**Lane:** V2-9.8B.22  
**Authority inputs:**

* `docs/printer-v1-v2-9-8b-discovery-only-command-audit.md`
* `docs/printer-v1-v2-9-8b-eligible-token-supply-architecture-design.md`
* `docs/printer-v1-v2-9-8b-eligible-token-supply-architecture-closeout.md`
* `AGENTS.md` / Clean Master Spec / Python Builder Guide / active V2 memory-growth build order

**Design verdict:** `V2_9_8B_22_DISCOVERY_ONLY_COMMAND_SURFACE_DESIGN_PASS`

---

## 1. Goal

Add one explicit operator-approved public command mode:

```text
discovery-only
```

that runs the canonical V2-9.8B.21 Eligible Token Supply service against the
authoritative operational database through Source Governor, continues bounded
discovery batches until two freshly eligible distinct tokens are confirmed **or**
a valid exhaustion certificate is produced, then stops — with **zero** Central
Scheduler runtime calls and **no** production campaign / tracking / factory /
memory / retrieval / financial activation.

Intended later operator command (not executed in this lane):

```bash
pwsh -NoProfile -File scripts/Start-PrinterV1-MemoryFactory.ps1 \
  -Mode discovery-only \
  -OperatorApproved
```

---

## 2. Public command ownership

| Layer | Owner |
|---|---|
| PowerShell front door | `scripts/Start-PrinterV1-MemoryFactory.ps1` |
| Python public command | `printer_v1.operator_cli.operational_memory_factory_command` |
| Mode entry | `run_discovery_only_qualification(...)` |
| Supply completeness loop | `printer_v1.discovery.eligible_token_supply.run_persistent_eligible_token_supply` |
| Exact-pool market checks | `graduated_liquidity_front_door` via Source Governor |
| Migration intake | `direct_migration_discovery` via Source Governor |
| Preflight | `build_activation_preflight` (shared with production) |

No second public launcher. No internal-only Python entry promoted as the operator
surface. Disposable tests may inject fixture transports into the public function;
live transport defaults remain free/public and governed.

---

## 3. Mode surface

PowerShell `ValidateSet` and Python argparse choices become:

```text
preflight-only
run
status
cooperative-stop
recover-orphan
report-only
discovery-only
```

Authorization:

| Mode | `--operator-approved` / `-OperatorApproved` |
|---|---|
| `discovery-only` | **Required** |
| `run` | Required (unchanged) |
| others | Unchanged |

---

## 4. Execution contract

```text
1. Require explicit operator approval.
2. Run build_activation_preflight (identical gates to production).
3. Create unique execution_id + qualification_id + artifact tree.
4. Snapshot protected-table row counts.
5. Invoke run_persistent_eligible_token_supply with:
   - authoritative DB
   - cycle_seed = execution_id
   - required_token_capacity = 2
   - front_door_max_candidates = 6 (one evaluation batch)
   - discovery_operation_budget = 30 (holder headroom under ceiling 45)
   - deadline_at = now + DISCOVERY_ONLY_DURATION_SECONDS
   - campaign_id = qualification_id (reserve tag only; no campaign row)
   - execution_id / run_id / cycle_id for certificate identity
   - live free transports by default (injectable in tests)
6. Continue multi-round discovery until capacity 2 or proven exhaustion.
7. Stop immediately when eligible_reserve_count reaches 2.
8. Persist reserve / exhaustion certificate per migration 046.
9. Map outcome to discovery-only terminal status.
10. Write durable qualification report JSON under artifact root.
11. Prove protected-table zero deltas + zero active residue.
12. Return public result; never create retry/restart/successor.
```

### 4.1 Duration and ceilings

| Ceiling | Value | Ownership |
|---|---:|---|
| Lifecycle source operation ceiling | 45 | Unchanged admission law |
| Discovery-only operation budget | 30 | Leaves holder/handoff headroom; not used for handoff here |
| Evaluation batch size | 6 | One market-enrichment batch |
| Required token capacity | 2 | Unchanged |
| Discovery-only duration | 900 seconds | Mode-local deadline for `DURATION_EXHAUSTION` |
| Automatic retries | 0 | Locked |
| Restart / successor | Forbidden | Locked |

### 4.2 Live sources (defaults)

| Channel | Transport owner | Governor |
|---|---|---|
| PumpPortal migration stream | `build_pumpportal_migration_transport` | Yes |
| Solana RPC graduation verify | existing verifier factory / OneShot RPC | Yes |
| DexScreener exact-pool market | default pair snapshot transport | Yes |
| Optional fresh-profile locator | operational supply kwargs when enabled | Yes |

No paid APIs. No Source Governor bypass. No improvised raw HTTP outside adapters.

---

## 5. Qualification identity and report

```text
execution_id   = YYYYMMDDTHHMMSSZ-<12 hex>
qualification_id = <execution_id>-discovery-only
artifact_root  = ~/PrinterOperations/v2-9-8/<execution_id>/
report_path    = <artifact_root>/discovery-only-qualification-report.json
summary_path   = <artifact_root>/terminal-summary.json
```

No `printer_memory_factory_campaigns` row is created. The qualification identity is
file-durable and embedded in:

* report JSON
* `printer_discovery_exhaustion_certificates.execution_id` (when issued)
* `printer_eligible_token_reserve.last_campaign_id` tag (`qualification_id`) for
  audit linkage only

---

## 6. Public result schema

Required fields:

```text
mode
execution_id
qualification_id
status
discovery_rounds
candidates_observed
unique_candidates_observed
duplicate_candidates_removed
candidates_validated
eligible_reserve_count
required_token_capacity
selected_candidate_mints
source_operations_used
source_operations_remaining
scheduler_runtime_calls
database_writes
shortage_classification
exhaustion_certificate
report_path
restart_created
successor_created
```

Also recorded for operator clarity:

```text
protected_table_deltas
mutation_allowlist
active_residue
integrity
foreign_key_violations
git_provenance
source_accounting
```

### 6.1 Terminal statuses

| Status | Meaning |
|---|---|
| `DISCOVERY_ONLY_CAPACITY_READY` | ≥2 distinct freshly eligible tokens reserved; stopped at capacity |
| `DISCOVERY_ONLY_HONEST_EXHAUSTION` | Valid exhaustion certificate; true market or visibility shortage |
| `DISCOVERY_ONLY_SOURCE_UNAVAILABLE` | Provider/channel unavailability (not market shortage) |
| `DISCOVERY_ONLY_BUDGET_EXHAUSTED` | Discovery operation budget exhausted with lawful work remaining or stop-reason budget |
| `DISCOVERY_ONLY_DURATION_EXHAUSTED` | Mode duration deadline reached |
| `DISCOVERY_ONLY_FAILED` | Pre/post condition fault, integrity fault, unexpected residue, or unclassified failure |

Provider, budget, and duration failures **must not** be reported as true market
shortage. Classification remains in `shortage_classification` from B.21 when a
certificate is issued.

---

## 7. Mutation boundary

### 7.1 Allowlist (discovery-owned evidence only)

| Table / surface | Why allowed |
|---|---|
| `printer_source_requests` | Governed request ledger |
| `printer_source_responses` | Governed response ledger |
| `printer_source_failures` | Governed failure ledger |
| `printer_source_health` | Governor health |
| `printer_source_rate_limits` | Governor rate limits |
| `printer_external_source_operations` | Operation accounting |
| `printer_pumpswap_graduated_candidate_registry` | Graduated inventory |
| `printer_discovery_batches` | Discovery batch evidence |
| `printer_discovery_work` | Discovery work evidence |
| `printer_discovery_work_source_links` | Work↔source links |
| `printer_discovery_candidates` | Candidate inventory (legacy path) |
| `printer_discovery_merged_candidates` | Merged candidates |
| `printer_discovery_candidate_contributions` | Contributions |
| `printer_discovery_provider_observations` | Provider observations |
| `printer_discovery_provider_report_links` | Provider report links |
| `printer_discovery_origin_verifications` | Origin verify evidence |
| `printer_discovery_pumpswap_confirmations` | PumpSwap confirmations |
| `printer_discovery_selection_links` | Selection links (evidence only; no tracking handoff) |
| `printer_discovery_selected_item_links` | Selected item links (evidence only) |
| `printer_graduated_market_floor_state` | Floor/cooldown evidence |
| `printer_eligible_token_reserve` | Durable eligible reserve (046) |
| `printer_discovery_exhaustion_certificates` | Exhaustion certificates (046) |
| `printer_pumpfun_finalized_origin_registry` | Origin registry support |
| `printer_pumpfun_origin_cursor` | Origin cursor support |
| `printer_tokens` / `printer_pairs` | Intake rows discovery may materialize |

Artifact filesystem writes under `~/PrinterOperations/v2-9-8/<execution_id>/` are
allowed (reports only).

### 7.2 Protected zero-delta tables

Must show **exact zero row-count delta** across the qualification:

* all `printer_memory_factory_campaign*` tables (campaigns, runs, cycles, slots,
  supervision, configurations, reports, objects, scheduler_work, windows, …)
* `printer_memory_factory_runs` / `printer_memory_factory_run_steps`
* `printer_scheduler_jobs`
* `printer_tracking_queue`
* `printer_memory_windows` / `printer_episodes` / `printer_episode_*` /
  `printer_memory_fingerprints` / `printer_memory_audit_reports`
* `printer_memory_retrieval_queries` / `printer_memory_retrieval_matches`
* `printer_paper_decisions` / `printer_paper_decision_audits` /
  `printer_paper_positions` / `printer_paper_trade_events` /
  `printer_paper_trade_audits` / `printer_paper_audit_reports` /
  `printer_paper_quote_evidence`
* `printer_proof_run_supervision`
* `printer_token_snapshots` / `printer_snapshot_*` / micro-event / trading-flow /
  safety / liquidity / market-regime / chain-heat snapshot tables
* `printer_holder_*` campaign ledgers (no holder funnel in discovery-only)
* `printer_selection_batches` / `printer_selection_batch_items` /
  `printer_selection_rotation_state` (no production selection batch handoff)

If any protected delta is non-zero, status becomes `DISCOVERY_ONLY_FAILED`.

### 7.3 Explicit non-mutations

Discovery-only **must not**:

* call Central Scheduler runtime admission/execution;
* acquire production campaign supervision / heartbeat lease;
* create production campaign ownership rows;
* activate tracking queue items or token slots;
* start factory runs / lifecycle windows / memory creation;
* create retrieval queries or paper decisions/positions/trades/audits/PnL;
* create retry, restart, or successor qualifications;
* lower eligibility floor or required capacity.

---

## 8. Status and report-only integration

### 8.1 `status`

Remains zero-source and zero-write. Extended payload:

```text
mode: STATUS
status: <latest campaign supervision inspect result when present, else null>
discovery_only_qualification: <latest discovery-only report summary or null>
source_calls: 0
scheduler_runtime_calls: 0
database_writes: 0
```

If no campaign supervision exists but a discovery-only report exists, status still
succeeds and returns the qualification summary.

### 8.2 `report-only`

Remains zero-source and zero-write. When the latest durable public report is a
discovery-only qualification, report-only returns that report (with
`mode: REPORT_ONLY`, `report_kind: discovery-only`, and zero new source/scheduler
calls). Otherwise existing campaign terminal report replay is unchanged.

---

## 9. Failure and cancellation residue

On preflight failure: no artifact qualification report required beyond blocked
command JSON on stderr; zero DB writes from discovery-only itself.

On mid-run failure after discovery work began:

* do not leave production campaign/supervision active (none created);
* do not create restart/successor;
* write best-effort terminal report with `DISCOVERY_ONLY_FAILED` when possible;
* active residue counts for campaign/supervision/scheduler locks/factory steps
  must remain zero.

---

## 10. Disposable proof matrix (normative)

| # | Proof |
|---:|---|
| 1 | PowerShell + Python require operator approval for discovery-only |
| 2 | Rejected on dirty Git, migration mismatch, integrity failure, FK failure, active work, missing dependencies |
| 3 | Two eligible tokens outside first six observations found |
| 4 | One eligible token preserved across later rounds |
| 5 | Stops immediately after two fresh eligible tokens |
| 6 | Exactly zero tracking handoff, Scheduler, factory, window, memory work |
| 7 | One-token universe → complete honest exhaustion certificate |
| 8 | Provider / budget / duration failures remain distinct from market shortage |
| 9 | Source ceiling and discovery budget enforced |
| 10 | Source Governor cannot be bypassed |
| 11 | Selection deterministic and non-ranked |
| 12 | Status + report-only inspect qualification with zero source calls and zero writes |
| 13 | Cancellation/failure leaves zero active residue |
| 14 | Integrity `ok`, FKs clean |
| 15 | Retrieval and financial table deltas remain zero |
| 16 | No retry / restart / successor created |
| 17 | PowerShell wrapper accepts `discovery-only` on macOS disposable path |

---

## 11. Authoritative readiness (this lane)

After implementation commits, run **only**:

```text
preflight-only
status
report-only
```

Require clean provenance, migrations through 046, integrity ok, zero FK, zero
active operational state, zero source calls, zero Scheduler calls, zero database
writes.

**Do not** execute discovery-only or production against live sources in this lane.

---

## 12. Locks preserved

All V1 / V2 locks remain in force: Solana memecoin paper-only, no live wallet /
private keys / real funds / live execution, no paid APIs, no scoring/ranking/
confidence/weights, no retrieval/decision/position/trade/audit/PnL unlock, no
embeddings/vectors, Source Governor + Central Scheduler ownership preserved,
BUY/SELL/HOLD remain locked, 15m main / 5m support-only, exact PumpSwap +
`$3,000` floor, capacity 2, operation ceiling 45.

---

## 13. Implementation file plan

| File | Change |
|---|---|
| `scripts/Start-PrinterV1-MemoryFactory.ps1` | Add `discovery-only` to ValidateSet |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Mode + runner + status/report integration |
| `tests/test_v2_9_8b_22_discovery_only_command.py` | Disposable proof matrix |
| `docs/printer-v1-v2-9-8b-discovery-only-command-audit.md` | Audit |
| `docs/printer-v1-v2-9-8b-discovery-only-command-design.md` | This design |
| `docs/printer-v1-v2-9-8b-discovery-only-command-closeout.md` | Closeout after proof |

No new migration. Migration 046 remains the durable discovery evidence schema.

---

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Risk | Mitigation |
|---|---|---|
| Live qualification still thin market | True shortage remains possible | Honest certificate; do not auto-retry |
| Multi-round Dex spend | Budget pressure | Budget 30 + stop-at-two |
| Status without campaign supervision | Historical status assumed campaign | Fallback to discovery-only report |
| Confusing qualification with production | Operator misuse | Distinct mode + statuses + no campaign rows |
| Residual historical QUEUED queue rows | Noise in corpus | Preflight active counts remain authoritative; protected deltas use counts |

**Design complete. Implementation may proceed.**
