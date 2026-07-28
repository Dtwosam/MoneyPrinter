# Printer V1 V2-9.8B — Operational Selective WINDOW_1H Readiness Audit

## Status

```text
AUDIT_COMPLETE_SAFE_DESIGN_PATH_ESTABLISHED
```

This audit is documentation only. It does not unlock operational 1h execution,
4h collection, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, PnL, live execution, wallets, private keys, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings, or vectors.

Baseline HEAD at audit start: `bb00d897e5b91bc68a7dd32dd15985f3d49fe0ea`  
Branch: `master`  
Tracked/staged/unstaged/untracked: clean

---

## 1. Canonical operational path (traced)

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
  → printer_v1.operator_cli.operational_memory_factory_command
  → run_operational_campaign
  → AuthoritativeLiveOperationalCampaignOwner.run_operational(fifteen_minute_only=True)
  → OriginToLifecycleCampaignDriver
  → run_one_command_15m_factory (continuous_first_hour=False)
  → E2O 15m close → E2Q audit → Lane K / E2Z promotion
  → unified_terminal_closure + report-only replay
```

Owners:

| Layer | Owner module |
|---|---|
| Public command | `operational_memory_factory_command.py` |
| Campaign shell | `campaign_persistence.py`, `campaign_ownership.py` |
| Live activation | `authoritative_live_operational_campaign.py` |
| Slot activation | `discovery/combined_executor.py` |
| Lifecycle | `one_command_15m_factory.py` via `origin_lifecycle_campaign.py` |
| Scheduler jobs | factory steps + `printer_scheduler_jobs` |
| Source requests | Source Governor via factory adapters |
| Terminal report | `unified_terminal_closure.py`, `final_campaign_report.py` |
| Replay | `report_only` / `zero_source_campaign_replay.py` |

Successful campaign evidence (`20260727T235023Z-390455e31060`): two clean
`WINDOW_15M` episodes (54, 55) from windows 157 and 158; zero campaign-window
rows; null `authoritative_run_id`; `reconciliation.windows = {}`.

---

## 2. Finding table (required classifications)

| # | Finding | Classification | Evidence | Implication for selective 1h |
|---:|---|---|---|---|
| 1 | Public operational path locks `WINDOW_1H` | `EXPECTED_OPERATIONAL_CONFIGURATION` | `LOCKED_WINDOWS`, `MAIN_WINDOW=WINDOW_15M`, `TOTAL_DURATION_SECONDS=1200`, `continuous_first_hour=False`, `fifteen_minute_only=True` | Production remains 15m-only until an explicit later operational 1h proof is authorized |
| 2 | Historical X12 / E2H / Lane H 1h runners are proof-only and do not use V2-9.8B campaign ownership | `PROOF_ONLY_COMPONENT_NOT_OPERATIONAL` | `lane_x12_1h_runner.py`, `lane_e2h_*_1h_handler.py`, `lane_h_1h_bounded_memory_factory.py` | Reuse close/cadence contracts; do not promote as operational front door |
| 3 | `token_local_continuation` (4A) and `build_4a_authority_facts` exist as pure policy/adapters | `READY_AS_COMMITTED` | `scheduler/token_local_continuation.py`, `campaign_authority_adapters.py`, 4A/6B tests | Authoritative selective gate for 15m→1h |
| 4 | Natural disposition continues on PARTIAL/CLEAN window labels, not authoritative episodes | `DOCUMENTATION_OR_REPORTING_GAP` + policy divergence | `NaturalEvidenceDispositionOwner` uses `printer_memory_windows.memory_quality_label` | Selective 1h must consume B.1 episode authority, not raw window PARTIAL label |
| 5 | Factory can schedule CONTINUATION_* when `continuous_first_hour=True` | `READY_AS_COMMITTED` (proof path) | `_plan_continuation_jobs`, `_execute_continuation_close` | Reuse for bounded non-live proof; not operationally enabled |
| 6 | No production call to `persist_window` | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | `persist_window` only in tests | Campaign-window graph empty → terminal `windows={}` |
| 7 | Campaign run created before factory UUID; `authoritative_run_id` never bound | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` + `SCHEMA_OR_PERSISTENCE_GAP` | Operational `create_campaign_run` omits id; trigger blocks any UPDATE of `authoritative_run_id` | Requires one-shot NULL→value bind migration + factory init callback |
| 8 | Empty `reconciliation.windows` is honest empty-set reporting | `DOCUMENTATION_OR_REPORTING_GAP` | `unified_terminal_closure.reconcile_campaign_terminal` | Not a report defect; symptom of missing graph writes |
| 9 | E2Q already admits genuine `WINDOW_1H` (≥2700s, anchors, token/pair) | `HISTORICAL_BLOCKER_ALREADY_RESOLVED` | V2-6 closeout + `e2q_memory_window_audit.py` | X14 E2Q 15m-only blocker is retired |
| 10 | E2X is 15m-only | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | `E2X_WINDOW_KIND = WINDOW_15M` | Lane K uses individual promotion for production; 1h promotion can use per-window E2Z gate |
| 11 | E2Y assumes all candidates are `WINDOW_15M` | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | `all_window_15m` summary check | Need period/kind separation so 15m and 1h never mix; distinct 1h periods stay distinct |
| 12 | E2Z allows `WINDOW_15M` and `WINDOW_4H` but not `WINDOW_1H` | `COMMITTED_CODE_DEFECT` | `_ALLOWED_WINDOW_KINDS = {WINDOW_15M, WINDOW_4H}` | Blocks clean 1h promotion after genuine close/audit |
| 13 | Cadence/continuity contracts for 1h exist (2700s continuation, gap rules) | `READY_AS_COMMITTED` | `cadence_policy.py`, `lifecycle_continuity.py`, `lane_e2o_1h_window_close.py` | Timing/gap enforcement reusable |
| 14 | Period-aware 1h identity uses `snapshot_start_id` duplicate guard | `READY_AS_COMMITTED` | E2O 1h close docs | Separate periods remain distinct |
| 15 | Operational budgets are 15m-only ceilings | `EXPECTED_OPERATIONAL_CONFIGURATION` | 65 governed / 21 per token / 1200s duration | Selective 1h proof needs dedicated bounded ceilings when enabled; production stays 15m |
| 16 | Scheduler factory steps own collection work; campaign_scheduler_work table unused operationally | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | Schema 032 helpers; no operational writer | Implementation must keep factory/Scheduler ownership and optionally mirror campaign work rows |
| 17 | Report-only replay is zero-source / zero-write | `READY_AS_COMMITTED` | `report_only`, replay modules | Must remain zero-write with graph fields populated |
| 18 | Token slot states include WINDOW_1H_* but operational slots jump SELECTED→terminal | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | `_TOKEN_TRANSITIONS` vs live residual MANUAL_REVIEW | Selective path must advance slot/window states categorically |
| 19 | 5m cannot satisfy 1h; 4h/12h/24h operationally locked | `EXPECTED_OPERATIONAL_CONFIGURATION` | E2Q support-only 5m; LOCKED_WINDOWS | Preserve |
| 20 | Missing evidence that would force audit-only stop | none material | Schema, E2Q, continuity, 4A, factory continuation all present | Safe design path exists without live run |

---

## 3. Answers to the ten audit questions

### 1. Where 1h is currently locked

Public V2-9.8B command: `LOCKED_WINDOWS`, 15m-only duration, `fifteen_minute_only=True`,
`continuous_first_hour=False`. Factory continuation branch is never entered.

### 2. Historical 1h code reusable or proof-only?

| Component | Reuse | Class |
|---|---|---|
| E2O 1h close | Yes | structural |
| E2Q genuine-1h gate | Yes | structural |
| Cadence + lifecycle continuity | Yes | structural |
| Factory CONTINUATION_* steps | Yes under flag | proof/runtime reusable |
| X12 runner / Lane H | Evidence only | proof-only |
| 4A token-local policy | Yes | pure policy |
| Campaign ownership schema | Yes | persistence ready |

### 3. Canonical lineage (required)

```text
campaign_token_slot
  → root_15m_lifecycle_identity
  → printer_memory_windows WINDOW_15M (candidate PARTIAL_MEMORY)
  → printer_episodes WINDOW_15M_CLEAN_MEMORY (authoritative CLEAN)
  → continuation decision (categorical CONTINUE / STOP / BLOCK)
  → campaign_window WINDOW_1H (predecessor = 15m campaign window)
  → printer_memory_windows WINDOW_1H
  → E2Q audit → E2Z WINDOW_1H_CLEAN_MEMORY (if clean)
```

Authoritative predecessor for continuation is the **episode**, not the raw
window PARTIAL label (V2-9.8B first-success closeout §6).

### 4. Missing campaign-window rows and null authoritative_run_id

**Blockers for selective 1h authority path: yes.**  
`campaign_authority_adapters` fail closed without both.  
**Blockers for 15m yield truth: no** — episodes remain authoritative for 15m.

### 5. E2Q / E2Y / E2Z for period-aware WINDOW_1H

| Gate | Support | Gap |
|---|---|---|
| E2Q | Genuine 1h clean/dirty/blocked | Ready |
| E2Y | 15m set gate only | Must separate kinds/periods |
| E2Z | 15m + 4h only | Must admit WINDOW_1H |

### 6. Categorical token-local continuation gates (4A)

Requires: exact identities; closed predecessor; **CLEAN_MEMORY** predecessor;
CLEAN_DATA; not do_not_train; evidence eligible/complete/fresh; governed
provenance; safety context acceptable; continuity continuous; eligible token
state; learning need in {COVERAGE, TRANSITION} for 15m→1h; token budget;
campaign running with shared health.

No scoring, ranking, confidence, or weighted logic.

### 7. Timing / cadence / elapsed / lease / host-awake

| Rule | Value |
|---|---|
| 15m main | 900s |
| 1h continuation phase | 2700s (close anchored to 15m close) |
| 1h min elapsed for genuine close/audit | 2700s |
| Cadence | TRACK_FAST ~120s / TRACK_NORMAL ~240s (policy table) |
| Operational lease | 90s renew / 30s heartbeat |
| Host-awake | Operator caffeinate awareness (prior LEASE_EXPIRED incident) |
| Gap / pair drift | Continuity + E2O fail closed |

### 8. Source Governor budget (0 / 1 / 2 continued tokens)

15m operational ceilings remain the production default. Selective 1h, when
explicitly enabled for proof, must reserve closeout budget so ordinary
collection cannot starve close work; zero continued tokens spend zero 1h
budget; one or two tokens spend only their planned CONTINUATION_* requests
under factory ceilings. Fairness: two-token barrier already exists for natural
mode; selective path must not let one token monopolize close budget.

### 9. Scheduler ownership / fairness / cancellation / zero residue

Factory steps claim scheduler jobs; cancellation_probe + supervision cleanup
must leave zero PENDING/RUNNING/COOLDOWN residue. Campaign window terminal
cancel path already exists in `reconcile_campaign_terminal` once rows exist.
No automatic retry/restart/successor.

### 10. Schema / idempotency / reporting / replay gaps

| Gap | Resolution class |
|---|---|
| Immutable `authoritative_run_id` blocks post-create bind | forward-only migration (one-shot NULL→value) |
| No campaign window writes | implementation boundary |
| E2Z missing WINDOW_1H | code defect fix |
| E2Y kind mixing | period/kind separation |
| Reporting empty windows | filled when graph written |
| Replay | keep zero-write; report includes linkage when present |

---

## 4. Safe design determination

A safe design **can** be established without missing evidence, weakened gates,
or a live run because:

1. Schema for campaign windows and 1h states already exists (032).
2. E2Q genuine-1h and E2O 1h close already exist.
3. 4A selective policy and B.1/B.2 adapters already exist.
4. Factory CONTINUATION_* machinery already exists under proof flags.
5. The only hard schema friction is one-shot bind of `authoritative_run_id`
   (and optional late binds) under the current immutability trigger.

**Stop-before-implementation condition: not triggered.**

---

## 5. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Setback if ignored | Mitigation |
|---|---|---|
| Using raw PARTIAL window as clean predecessor | False 1h continuation | Require B.1 CLEAN episode |
| Enabling continuous_first_hour also enabling 4h | Scope creep / unlocked 4h | Separate `selective_1h_continuation` flag; 4h stays locked |
| Parallel X12 operational runner | Dual ownership | Extend factory + campaign graph only |
| Blind E2Z accept of any 1h | Dirty promotion | Keep PARTIAL + e2q_audited + CLEAN_DATA + closed gates |
| Production 1h on by default | Unauthorized long collection | Default false; production command stays 15m-only |
| Budget starvation of close | Incomplete 1h | Reserve closeout budget; earliest-deadline close first |
| One-shot bind abused | Identity mutation | Migration allows only NULL→non-null once |

---

## 6. Next step

Proceed to design and implementation in the same consolidated package:

`docs/printer-v1-v2-9-8b-operational-selective-1h-design.md`

then implementation, bounded non-live proof, and closeout.
