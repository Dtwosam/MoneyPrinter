# Printer V1 V2-9.8B — Operational Selective WINDOW_1H Design

## Status

```text
DESIGN_COMPLETE_IMPLEMENTATION_AUTHORIZED_IN_PACKAGE
```

Authority stack: AGENTS.md, clean master spec, post-RC build order, memory
factory guide, memory-growth V2 build order, first-successful 15m closeout,
V2-9.7C campaign design, 4A continuation closeout, this readiness audit.

Does not authorize operational 1h production activation, 4h implementation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
live wallets, paid APIs, scoring, ranking, confidence, weighted logic,
embeddings, or vectors.

---

## 1. Design goal

Extend the existing V2-9.8B operational architecture so selective
`WINDOW_15M → WINDOW_1H` continuation is:

- campaign-owned and lineage-exact;
- categorical and token-local (zero, one, or two tokens);
- Scheduler-owned and Source-Governed;
- E2Q/E2Y/E2Z period-aware for genuine 1h;
- default-off in the public production command;
- fully proveable with temporary DBs and mocked sources.

Do **not** create a parallel production runner.

---

## 2. Authoritative predecessor and campaign/factory linkage

### 2.1 Authoritative predecessor

| Role | Row | Rule |
|---|---|---|
| Candidate evidence | `printer_memory_windows` WINDOW_15M | May remain PARTIAL_MEMORY |
| Authoritative clean yield | `printer_episodes` COMPLETE + CLEAN_MEMORY | Required for CONTINUE |
| Authority adapter | B.1 `load_authoritative_promotion_outcome` | Maps promotion → CLEAN_MEMORY facts |
| Safety | B.2 checkpoint safety | Required present + ACCEPTABLE for CONTINUE |

Raw window PARTIAL labels alone **never** authorize continuation.

### 2.2 Campaign ↔ factory linkage

1. Campaign run is created before the factory UUID exists.
2. Factory run insert emits UUID via `factory_run_initialized`.
3. One-shot bind: `campaign_runs.authoritative_run_id = factory_run_id`
   only when previous value is NULL.
4. Migration 047 replaces the absolute immutability trigger with a one-shot
   NULL→value rule for `authoritative_run_id` (and matching late binds for
   `memory_window_row_id` / `scheduler_job_id` when OLD is NULL).

---

## 3. Campaign-window graph persistence

On each main window lifecycle event, when campaign identities are present:

| Event | Graph action |
|---|---|
| 15m window closed and linked | `persist_window` WINDOW_15M with `memory_window_row_id`, state → COLLECTING→…→AUDITING→CLEAN_PROMOTED/DIRTY/BLOCKED |
| Selective CONTINUE | `persist_window` WINDOW_1H with predecessor_window_id = 15m campaign window id, root_15m_lifecycle_identity exact |
| 1h close promoted | window_state CLEAN_PROMOTED; slot WINDOW_1H_CLOSED |
| 1h dirty/blocked | DIRTY/BLOCKED preserved; no clean episode |
| Cancel / lease expiry | CANCELLED; zero active residue |

Window identity:

```text
campaign_id + run_id + cycle_id + token_slot_id
+ window_kind + root_15m_lifecycle_identity
+ predecessor_window_id (required for WINDOW_1H)
+ memory_window_row_id (exact printer_memory_windows.id)
```

---

## 4. Categorical continuation decision

Owner module: `operational_selective_1h.py` (extends operational architecture).

Inputs per token (from B.1/B.2 + continuity + lifecycle):

- exact slot/token/mint/pair/lifecycle/predecessor identities;
- predecessor closed;
- B.1 promotion success → predecessor_memory_quality CLEAN_MEMORY;
- continuity CONTINUOUS;
- safety ACCEPTABLE;
- learning need categorical:
  - CONTINUE path needs COVERAGE or TRANSITION for 15m→1h;
  - derived from governed outcome labels without scores:
    - meaningful transition outcomes → TRANSITION;
    - coverage gaps after clean close → COVERAGE;
    - ordinary consolidation / no pump → no learning need → STOP;
  - dirty/missing/ineligible → BLOCK;
- token and campaign budgets.

Output: immutable CONTINUATION_4A campaign object:

```text
verdict ∈ {CONTINUE_TO_WINDOW_1H, STOP_AFTER_WINDOW_15M, BLOCK_CONTINUATION}
reasons: tuple[str, ...]
authoritative_episode_id | null
predecessor_memory_window_id
```

Zero eligible → zero continuation jobs.  
One eligible → exactly one.  
Two eligible → both, with two-token fairness / close-priority ordering.

No profitability prediction, ranking, confidence, or BUY readiness.

---

## 5. Period-aware identity and duplicate guard

| Layer | Rule |
|---|---|
| E2O 1h | unique by pair_id + WINDOW_1H + snapshot_start_id |
| Campaign window | predecessor must be same-root WINDOW_15M (schema trigger) |
| E2Y | candidate set may not mix window_kinds; 1h periods grouped by snapshot_start/opened period |
| E2Z | promote once per memory_window_id (existing idempotency) |
| Factory | CONTINUATION steps keyed by run + token + step_key |

5m support windows never satisfy 1h identity.

---

## 6. Timing, cadence, coverage, gaps

| Rule | Value |
|---|---|
| Continuation phase | 2700s from exact 15m close |
| Cadence | existing WINDOW_1H TRACK_FAST/NORMAL policy |
| Min genuine 1h elapsed | 2700s (E2O report + E2Q gate) |
| Gap / delayed restart | continuity blocked |
| Pair drift | E2O fail closed |
| Lease | existing 90s / heartbeat 30s |
| Host-awake | operator responsibility; lease expiry fails closed, no auto restart |

---

## 7. E2Q / E2Y / E2Z 1h behavior

| Gate | Behavior |
|---|---|
| E2Q | Unchanged genuine-1h structural gate; clean/dirty/blocked preserved |
| E2Y | Kind-homogeneous sets; distinct 1h periods not collapsed; 15m set rules unchanged |
| E2Z | Add WINDOW_1H to allowed kinds; same PARTIAL→episode CLEAN contract; episode_kind `WINDOW_1H_CLEAN_MEMORY` |

Dirty/gapped 1h remains unpromoted with do_not_train where applicable.

---

## 8. Scheduler jobs and priorities

Reuse factory CONTINUATION_SNAPSHOT / CONTINUATION_CLOSE via
`_plan_continuation_jobs` for tokens with CONTINUE verdict only.

Priority order (existing two-token fairness):

1. imminent close / CONTINUATION_CLOSE;
2. overdue gap / safe-stop;
3. lower service token;
4. older work id;
5. stable slot order.

Optional mirror rows in `printer_memory_factory_campaign_scheduler_work`
for report completeness; factory steps remain the execution owner.

---

## 9. Source Governor ceilings and reserved closeout budget

When selective 1h is **disabled** (production default): unchanged 15m ceilings.

When selective 1h is **enabled** (proof/tests only):

| Ceiling class | Rule |
|---|---|
| Zero continued tokens | zero 1h source spend |
| One / two tokens | only planned CONTINUATION_* steps |
| Close reserved | close step always claimable before ordinary snapshot if deadline imminent |
| 4h / 12h / 24h | still disabled |

No Source Governor bypass. No independent API loop.

---

## 10. Supervision, cancellation, host-awake

- Existing campaign supervision lease and cancellation_probe.
- On cancel / lease expiry: cancel active factory steps and campaign work;
  terminalize windows CANCELLED; no retry/restart/successor.
- Host sleep remains operator-managed; expired lease is terminal fail-closed.

---

## 11. Schema / migration

**Migration 047 — one-shot campaign linkage binds**

- Replace `printer_campaign_run_identity_immutable` so:
  - `run_id`, `campaign_id`, `run_ordinal`, `proof_supervision_id` remain immutable;
  - `authoritative_run_id` may change only when OLD is NULL and NEW is non-null.
- Replace window identity trigger so `memory_window_row_id` may bind only when OLD is NULL.
- Replace work identity trigger so `scheduler_job_id` / source ids may bind only when OLD is NULL.

Do not apply to `data/printer_v1.sqlite3` in this lane.

No new parallel ownership tables.

---

## 12. Terminal reporting and zero-write replay

Terminal report must include when graph present:

- `authoritative_run_id` / factory run id;
- campaign windows by kind and state;
- continuation decisions (CONTINUATION_4A objects);
- clean/dirty/blocked 1h outcomes;
- forbidden deltas remain zero for retrieval/paper/financial tables.

Report-only replay: zero source calls, zero Scheduler runtime, zero writes.

---

## 13. Flag surface (default off)

| Flag | Default | Production public command |
|---|---|---|
| `selective_1h_continuation` | `False` | remains False |
| `continuous_first_hour` | False | remains False |
| `continuous_four_hour` | False | remains False / locked |
| `LOCKED_WINDOWS` includes WINDOW_1H for production policy | Yes | Yes |

Selective 1h proof path enables `selective_1h_continuation=True` only under
operator-approved test/proof invocation with temp DBs. The normal production
command does not pass the flag.

---

## 14. Future 4h extension boundary (not implemented)

Token states and predecessor triggers already model WINDOW_1H→WINDOW_4H.
This design does **not** implement 4h collection, 4h budgets, or 4h unlock.
Any 4h work requires a separate authorized lane.

---

## 15. Implementation modules

| Module | Responsibility |
|---|---|
| `migrations/047_campaign_oneshot_linkage_binds.sql` | one-shot binds |
| `campaign_ownership.py` | `bind_authoritative_run_id`, optional late binds |
| `operational_selective_1h.py` | evaluate, persist decisions, bind graph, plan selective continuation |
| `one_command_15m_factory.py` | wire bind + selective branch |
| `operational_memory_factory_command.py` | bind factory run on init; keep production 15m-only |
| `e2z_clean_memory_creation.py` | allow WINDOW_1H |
| `e2y_15m_candidate_set_gate.py` | kind/period separation honesty |
| tests | bounded non-live proofs |

---

## 16. Proof matrix (non-live)

Prove with temp DB + fixtures + mocked sources:

1. no eligible token → zero continuation  
2. one eligible → exactly one  
3. two eligible → fair bounded continuation  
4. dirty/ineligible predecessor rejected  
5. authoritative episode used (not raw PARTIAL)  
6. missing lineage fails closed  
7. duplicate continuation idempotent  
8. separate 1h periods distinct  
9. clean 1h closes and promotes once  
10. dirty/gapped 1h unpromoted  
11. pair drift fails safely  
12. closeout budget not starved  
13. Scheduler-owned + Source-Governed  
14. cancel/lease → zero active residue  
15. no retry/restart/successor  
16. reporting has linkage + windows  
17. report-only replay zero calls/writes  
18. 5m cannot satisfy 1h  
19. 4h/12h/24h remain disabled  
20. retrieval/paper/financial deltas zero  

---

## 17. Locks preserved

All V1 locks remain. Operational 1h production activation remains a **later
operator-readiness + separately authorized bounded proof** after this package
PASS. This design's PASS does not authorize that proof.
