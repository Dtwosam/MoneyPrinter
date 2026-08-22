# V2-9.8B Design Lane 1 — Cadence Authority Provenance Design Amendment

**Document status:** `DESIGN_AMENDMENT_ONLY`  
**Date:** 2026-08-21  
**Starting implementation commit:** `cc36f1e18dd4c184be4137bd2e067df1e6b54d2c`  
**Migration head at design time:** `059_pair_ready_parent_terminal_cancellation_transition.sql`  
**Scope:** Close ONLY the later-cycle frozen-lane provenance gap.  
**Out of scope:** Design Lane 2 scheduling; live Printer; authorization; financial/retrieval unlocks; historical backfill; heuristic lane invention.

---

## 1. Proven gap (confirmed)

Printer already has a legitimate categorical TRACK_FAST / TRACK_NORMAL decision owner:

| Piece | Exact owner |
| --- | --- |
| Classifier | `printer_v1.discovery.classifier.classify_discovery_candidate` |
| Lane projection | `printer_v1.discovery.classifier.choose_tracking_lane` |
| Ordinary discovery writer | `printer_v1.discovery.discovery` (records `printer_discovery_candidates.tracking_lane` / `discovery_action`) |

Later-cycle frozen pre-admission does **not** preserve that decision:

| Artifact | Lane field? |
| --- | --- |
| `printer_pre_admission_discovery_attempt_items` (migration 055) | **No** `tracking_lane` |
| `PreAdmissionAttemptItem` | **No** lane field |
| Later-cycle handoff assessment | Hardcodes `TokenLifecycleState.TRACK_NORMAL` |
| `persist_cycle_rooted_selected_item` | Hardcodes `'TRACK_NORMAL'` into selection items |

Therefore admission currently has **no lawful exact lane input** for later cycles.

---

## 2. Required architecture (binding)

```text
current exact candidate evidence (selected mint/pool)
  → classify_discovery_candidate(candidate_mapping)
  → choose_tracking_lane(...) ∈ {TRACK_FAST, TRACK_NORMAL} else FAIL CLOSED
  → freeze lane + provenance onto printer_pre_admission_discovery_attempt_items
  → admit_two_token_cycle_from_attempt reads frozen lane
  → claim_tracking_item(exact frozen lane)
  → slot.tracking_queue_id bound at INSERT
  → printer_tracking_queue.tracking_lane = canonical runtime cadence authority
  → Lane Q resolves queue lane (not the frozen field directly)
```

Forbidden lane sources (unchanged):

- latest token history / latest discovery row / previous cycle
- snapshots / supporting_context
- policy table order / cycle ordinal / always NORMAL or always FAST

---

## 3. Exact named design elements

### 3.1 Categorical lane decision owner

- **Owner/functions:**  
  `classify_discovery_candidate` → `choose_tracking_lane`  
  (`src/printer_v1/discovery/classifier.py`)
- **Do not invent** a second classifier or later-cycle-specific FAST/NORMAL heuristic.

### 3.2 Input evidence

Classifier expects a candidate mapping with at least the fields used by:

- identity/chain gates (`token_mint`, `pair_address`, `chain`)
- market basics (`price_usd`, `liquidity_usd`)
- activity pulse / FAST gates (`volume_5m`, `txns_5m`, `volume_1h`, `txns_1h`, `volume_24h`, `txns_24h` as consumed today)
- optional `source_channel` for graduation liquidity floor

**Later-cycle evidence adapter (not a new classifier):**

Exact selected token/pair current evidence must be projected into that mapping at freeze time from:

1. the selected candidate’s `canonical_evidence_json` / reserve candidate payload for that mint/pool; and  
2. when needed, the attempt’s already-linked governed source responses (`printer_pre_admission_discovery_attempt_source_links` → `printer_source_responses`) for that exact mint/pool.

Use existing discovery normalize/parser helpers where they already decode those payloads. Do not invent thresholds.

**If projection cannot produce classifier-sufficient current evidence for that exact mint/pool:** fail closed — that candidate cannot freeze a cadence lane and cannot be admitted.

### 3.3 Path reachability

| Later-cycle path | Reaches classifier today? | After amendment |
| --- | --- | --- |
| Pre-admission PAIR_READY freeze (`persist_pre_admission_pair` writer path in `authoritative_live_operational_campaign`) | **No** | **Must** call classifier before freeze |
| `admit_two_token_cycle_from_attempt` | N/A (consumer) | Reads frozen lane only |
| Hardcoded TRACK_NORMAL assessment sites | Fabricated | Must use frozen lane / stop fabricating |

Any later-cycle candidate class that cannot obtain a TRACK_FAST/TRACK_NORMAL result from the classifier on current evidence is **stopped** (not defaulted).

### 3.4 Frozen pre-admission fields (additive)

New migration **`060_pre_admission_frozen_tracking_lane_provenance.sql`** (do not edit 055).

Add to `printer_pre_admission_discovery_attempt_items` (NOT NULL for new rows; historical rows remain NULL and non-reusable — see §3.10):

| Field | Rule |
| --- | --- |
| `frozen_tracking_lane` | `TRACK_FAST` \| `TRACK_NORMAL` only |
| `frozen_discovery_action` | matching `DiscoveryOutputAction` (`TRACK_FAST` / `TRACK_NORMAL`) |
| `frozen_discovery_label` | matching classifier label |
| `frozen_classification_reason` | classifier `reason` string |
| `frozen_lane_evidence_hash` | SHA-256 of exact classifier input mapping (canonical JSON) |
| `frozen_lane_decided_at` | timezone-aware UTC timestamp |
| `frozen_lane_decision_owner` | fixed literal e.g. `classify_discovery_candidate+choose_tracking_lane` |

Immutability: extend item immutability so these fields cannot be updated after INSERT (same class as existing item immutability).

### 3.5 Provenance fields / validation

On freeze and again on admit readback, require:

- `frozen_tracking_lane ∈ {TRACK_FAST, TRACK_NORMAL}`
- `frozen_discovery_action` consistent with lane
- `frozen_lane_evidence_hash` non-empty 64-hex
- item `token_row_id` / `pair_row_id` / mint / pool match the exact selected identities
- recomputed hash of admitted classifier input (if re-derived for audit) must match freeze hash **or** admit trusts immutable frozen row only without reclassification — prefer **immutable frozen row as admission input**, with hash retained as proof of which evidence produced it

Mismatch / NULL / UNKNOWN → block before admission.

### 3.6 Writer

**Writer:** later-cycle PAIR_READY freeze path that currently builds `PreAdmissionAttemptItem` and calls `persist_pre_admission_pair`  
(`authoritative_live_operational_campaign` later-cycle callback / persist pair site).

Sequence inside the existing PAIR_READY transaction/savepoint:

1. Build classifier input for exact selected mint/pool from current evidence.  
2. `classification = classify_discovery_candidate(input)`  
3. `lane = choose_tracking_lane(input, classification)`  
4. If `lane` not in `{TRACK_FAST, TRACK_NORMAL}` → do not persist PAIR_READY pair; fail closed.  
5. Persist item with frozen lane + provenance fields.

### 3.7 Reader

**Reader:** `admit_two_token_cycle_from_attempt` via `load_pre_admission_pair`.

- Read `frozen_tracking_lane` from each item.  
- Pass that exact lane into `claim_tracking_authority_for_slot_insert` / `claim_tracking_item`.  
- Remove all `tracking_lane="TRACK_NORMAL"` defaults from later-cycle admission/factory callers.

### 3.8 Transaction boundary

- Freeze write: same transaction/savepoint as `persist_pre_admission_pair` (atomic with PAIR_READY).  
- Admit: keep existing `BEGIN IMMEDIATE` covering claim + `token_status` projection + cycle/slot INSERT (`tracking_queue_id`) + attempt consumption; rollback on failure.

### 3.9 NULL / UNKNOWN / conflict behavior

| Case | Behavior |
| --- | --- |
| Missing frozen lane on admit | Block admission |
| Missing provenance hash/owner/reason | Block freeze / block admit |
| Classifier yields WATCH_ONLY / IGNORE / REJECT / None | Block freeze (no PAIR_READY for that pair) |
| Token/pair provenance mismatch | Block |
| Stale older discovery row / previous-cycle lane | Must not be consulted |
| After admit: `token_status` opposite valid lane vs queue | `CADENCE_AUTHORITY_CONFLICT`; no UPDATE; no opening |
| `token_status` NULL vs valid queue | Queue remains canonical; may proceed |

### 3.10 Historical-row behavior

- No backfill of guessed lanes onto historical pre-admission rows.  
- Rows with NULL frozen lane are **non-reusable** for new admission.  
- Migration 060 may leave existing rows NULL; only newly frozen PAIR_READY items after implementation are admissible.

### 3.11 Migration requirement and rationale

| Question | Answer |
| --- | --- |
| Can current schema hold frozen lane/provenance? | **No** (055 items lack columns) |
| Edit applied migration 055? | **Forbidden** |
| Required migration | **One minimal additive `060_...sql`** adding the frozen lane/provenance columns + immutability/check constraints |
| Rationale | Durable, immutable, per-item exact lane is required for lawful later-cycle claim input without inventing defaults |

### 3.12 Runtime authority after admit

- Canonical cadence authority remains:  
  `campaign window → slot → tracking_queue_id → printer_tracking_queue.tracking_lane`  
- Frozen lane is **activation provenance only**, not a second Lane Q authority.

---

## 4. Corrective blockers incorporated (post-amendment implementation checklist)

After this amendment is approved, corrective implementation must also close:

1. **token_status conflicts** — opposite valid lane vs queue → conflict, zero mutation by validators.  
2. **Existing-slot activation hole** — no FIRST_15M / no `WINDOW_15M_ACTIVE` without valid immutable slot-bound queue authority (identity + non-NULL pair + lawful lifecycle state via existing tracking_queue owner).  
3. **NULL `queue.pair_id`** — explicit authority failure.  
4. **Tracking-queue lifecycle eligibility** — use existing tracking_queue lifecycle owner; no parallel state machine in `cadence_authority.py`.  
5. **Post-admit materialization failure** — use canonical tracking lifecycle owner to terminalize/cancel misleading active/queued claim + status projection; no raw audit-history deletes.  
6. **Scheduler `target_id`** — if not strictly required for cadence authority, revert Lane-1 leakage; no Design Lane 2 scheduling work.

Owner-level invariant:

```text
valid exact slot-bound tracking authority
BEFORE
SELECTED → WINDOW_15M_ACTIVE
and BEFORE durable FIRST_15M enqueue
```

---

## 5. Exact production files implementation would touch

| File | Role |
| --- | --- |
| `migrations/060_pre_admission_frozen_tracking_lane_provenance.sql` | Additive schema |
| `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py` | Item dataclass, persist/load, validation |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | Freeze-time classify + write frozen fields; stop hardcoded NORMAL assessment where it fabricates admission lane |
| `src/printer_v1/operator_cli/multi_cycle_campaign_coordinator.py` | Admit reads frozen lane; no NORMAL default |
| `src/printer_v1/operator_cli/cadence_authority.py` | Claim requires explicit lane; conflict/no-mutation; NULL pair reject; lifecycle eligibility via existing owner |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Remove fabricated NORMAL; materialization-failure tracking cleanup via lifecycle owner; scheduler target_id review/revert if unrelated |
| `src/printer_v1/discovery/combined_executor.py` | Existing-slot hole: fail closed without valid bound queue before FIRST_15M |
| `src/printer_v1/operator_cli/campaign_ownership.py` | `SELECTED → WINDOW_15M_ACTIVE` must require valid slot-bound tracking authority |
| `src/printer_v1/discovery/classifier.py` | **Reuse only** (no new heuristic) |
| Focused tests under `tests/` | Provenance + corrective cases |

Optional small helper (same ownership stack, not a new classifier): project later-cycle evidence → classifier input mapping; live next to later-cycle / pre-admission writer.

---

## 6. Proof design (required cases)

1. Later-cycle truthful NORMAL survives freeze → claim → queue lane NORMAL.  
2. Later-cycle truthful FAST survives freeze → claim → queue lane FAST.  
3. Missing lane blocks before admission.  
4. Missing provenance blocks.  
5. Token/pair provenance mismatch blocks.  
6. Stale older discovery lane cannot leak.  
7. Previous-cycle lane cannot leak.  
8. Frozen lane cannot be silently mutated after selection.  
9. Queue lane exactly equals frozen admission lane.  
10. Lane Q resolves queue lane, not frozen field directly.  
11. No invented NORMAL/FAST fallback.  
12. No Source Governor / Central Scheduler bypass.  
13. Financial/retrieval locks unchanged.  
14. token_status opposite lane → conflict, zero mutation.  
15. Existing slot + NULL `tracking_queue_id` → no FIRST_15M, no ACTIVE.  
16. NULL queue pair / mismatches / invalid lane / stale-terminal queue → blocked.  
17. Direct `SELECTED → WINDOW_15M_ACTIVE` without authority → rejected at ownership owner.  
18. Materialization failure after committed claim → truthful terminal tracking state.  
19. Pre-commit admit failure rolls back queue/status/slot.  
20. Forensic gaps under NORMAL pass; under genuine FAST retain existing FAST contract.  
21. Cross-cycle historical queues cannot authorize another cycle’s slot.  
22. `get_policy("WINDOW_15M", None) → None`.

---

## 7. Explicit non-goals

- Design Lane 2 scheduling / sibling-close concurrency  
- Changing FAST/NORMAL cadence thresholds  
- Rewriting historical pre-admission or consumed campaign rows  
- Making frozen lane a second runtime cadence authority  
- New scoring/ranking/confidence systems  

---

## 8. Verdict

**`V2_9_8B_CADENCE_AUTHORITY_PROVENANCE_DESIGN_AMENDMENT_PASS_READY_FOR_CORRECTIVE_IMPLEMENTATION`**

Ready for operator review/adoption. Implementation must not start until this amendment is explicitly accepted. No production code changes and no commits were made in this design task.
