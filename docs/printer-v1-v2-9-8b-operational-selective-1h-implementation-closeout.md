# Printer V1 V2-9.8B — Operational Selective WINDOW_1H Implementation Closeout

## Final verdict

```text
V2_9_8B_OPERATIONAL_SELECTIVE_1H_IMPLEMENTATION_PASS
```

This package completes audit → design → implementation → bounded non-live proof
→ closeout for operational selective `WINDOW_1H` continuation.

PASS means the implementation and non-live proof are complete. The **next**
step is a separate operator-readiness review and a separately authorized
bounded operational 1h proof. This PASS does **not** authorize that proof, does
not activate production 1h, and does not unlock 4h.

Baseline HEAD at start: `bb00d897e5b91bc68a7dd32dd15985f3d49fe0ea`  
Branch: `master` (clean)

---

## 1. Audit and design findings

### Audit path

`docs/printer-v1-v2-9-8b-operational-selective-1h-readiness-audit.md`

Key findings:

| Finding | Classification |
|---|---|
| Public command is 15m-only by lock | `EXPECTED_OPERATIONAL_CONFIGURATION` |
| Campaign windows not written in production | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` |
| `authoritative_run_id` never bound; trigger blocked post-create UPDATE | `SCHEMA_OR_PERSISTENCE_GAP` |
| E2Q genuine 1h already works | `HISTORICAL_BLOCKER_ALREADY_RESOLVED` |
| E2Z excluded WINDOW_1H (allowed 15m+4h only) | `COMMITTED_CODE_DEFECT` |
| E2Y 15m-centric; needed kind/period separation | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` |
| 4A policy + factory CONTINUATION_* reusable | `READY_AS_COMMITTED` |
| Historical X12/Lane H not V2-9.8B ownership | `PROOF_ONLY_COMPONENT_NOT_OPERATIONAL` |
| Safe design path exists without live run | established |

### Design path

`docs/printer-v1-v2-9-8b-operational-selective-1h-design.md`

Authoritative predecessor = B.1 clean episode (not raw PARTIAL window).  
Selective gate = 4A token-local policy.  
Default-off flag `selective_1h_continuation`.  
One-shot migration for linkage binds.  
4h remains a future boundary only.

---

## 2. Blockers found and resolved

| Blocker | Resolution |
|---|---|
| Immutable `authoritative_run_id` prevented factory bind | Migration 047 one-shot NULL→value bind + `bind_authoritative_run_id` |
| No campaign-window write path | `persist_15m_campaign_window` / selective 1h WINDOW_1H persist |
| No campaign↔factory linkage | `ensure_authoritative_factory_link` from factory init + operational callback |
| E2Z blocked WINDOW_1H | Added WINDOW_1H to `_ALLOWED_WINDOW_KINDS` |
| E2Y period collapse risk | Kind-homogeneous + distinct period identity keys |
| Raw PARTIAL used as clean predecessor risk | Selective path uses B.1 promotion facts only |
| Continuous 1h coupled to 4h in coarse flags | Separate `selective_1h_continuation` flag; 4h stays locked |
| Public command test fixture missing 047 on copy | Fixture applies missing migrations to **copy only** |

---

## 3. Files changed

### Documentation

- `docs/printer-v1-v2-9-8b-operational-selective-1h-readiness-audit.md` (new)
- `docs/printer-v1-v2-9-8b-operational-selective-1h-design.md` (new)
- `docs/printer-v1-v2-9-8b-operational-selective-1h-implementation-closeout.md` (this file)

### Migration

- `migrations/047_campaign_oneshot_linkage_binds.sql` (new; **not** applied to `data/printer_v1.sqlite3`)

### Implementation

- `src/printer_v1/operator_cli/operational_selective_1h.py` (new)
- `src/printer_v1/operator_cli/campaign_ownership.py` — bind helpers
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — authoritative bind + selective schedule branch
- `src/printer_v1/operator_cli/operational_memory_factory_command.py` — production remains 15m-only; bind safety net; `selective_1h_continuation=False`
- `src/printer_v1/operator_cli/e2z_clean_memory_creation.py` — WINDOW_1H allowed
- `src/printer_v1/operator_cli/e2y_15m_candidate_set_gate.py` — kind/period awareness

### Tests

- `tests/test_v2_9_8b_operational_selective_1h.py` (new bounded proof)
- `tests/test_v2_9_8a_public_operational_command.py` — apply missing migrations on fixture copy

---

## 4. Migration status

| Item | Status |
|---|---|
| Migration file | `047_campaign_oneshot_linkage_binds.sql` committed |
| Applied to `data/printer_v1.sqlite3` | **No** (forbidden in this lane) |
| Temp/proof DBs in tests | Applied via full migration runner |
| Operator action later | Apply 047 before any future operational 1h proof against persistent corpus |

---

## 5. Authoritative lineage result

```text
campaign_token_slot
  → root_15m_lifecycle_identity
  → campaign_window WINDOW_15M (memory_window_row_id bound)
  → printer_memory_windows WINDOW_15M (PARTIAL candidate)
  → printer_episodes WINDOW_15M_CLEAN_MEMORY (B.1 authoritative)
  → CONTINUATION_4A object (CONTINUE / STOP / BLOCK)
  → campaign_window WINDOW_1H (predecessor exact)
  → printer_memory_windows WINDOW_1H
  → E2Q → E2Z WINDOW_1H_CLEAN_MEMORY (if clean)
```

Campaign run `authoritative_run_id` one-shot binds to factory `run_id`.

---

## 6. Continuation policy

- Token-local categorical evaluation via `evaluate_token_local_continuations`.
- Predecessor clean quality from **B.1 episode**, not raw window PARTIAL.
- Learning need: TRANSITION / COVERAGE from governed outcomes; ordinary
  CONSOLIDATION/NO_PUMP → STOP; dirty/missing → BLOCK.
- Zero / one / two CONTINUE tokens supported.
- No scoring, ranking, confidence, weighted logic, profitability, or BUY readiness.

---

## 7. Timing and budget

| Item | Value |
|---|---|
| 15m main | 900s |
| 1h continuation phase | 2700s from 15m close |
| Genuine 1h min elapsed | 2700s (E2Q/E2O) |
| Production duration | still 1200s (15m-only) |
| Production 1h flag | `selective_1h_continuation=False` |
| 4h/12h/24h | remain locked |

---

## 8. Scheduler and Source Governor ownership

- Continuation collection reuses factory CONTINUATION_SNAPSHOT / CONTINUATION_CLOSE
  under Central Scheduler claim path.
- Selective path only enqueues jobs for CONTINUE tokens.
- Source requests remain Source-Governed factory adapters.
- No parallel runner, no independent API loop, no automatic retry/restart/successor.
- Production public command does not enable selective 1h.

---

## 9. E2Q / E2Y / E2Z result

| Gate | Result |
|---|---|
| E2Q | Unchanged genuine WINDOW_1H support (already PASS historically) |
| E2Y | Kind-homogeneous + distinct period identities; 15m set gate preserved |
| E2Z | WINDOW_1H admitted; clean promotes once; dirty/5m blocked |

---

## 10. Reporting / replay result

- `summarize_selective_1h_reporting` surfaces authoritative_run_id, windows, CONTINUATION_4A objects.
- Production remains 15m-only; when graph is written, terminal reconciliation can populate windows.
- Report-only path unchanged zero-source/zero-write contract.
- Locked downstream flags remain false in selective payloads.

---

## 11. Proof results

Focused suite `tests/test_v2_9_8b_operational_selective_1h.py`: **16 passed**.

Proved:

- zero / one / two token selective continuation
- dirty/ineligible predecessor blocked
- authoritative episode over raw PARTIAL
- missing lineage fails closed
- duplicate continuation idempotent
- distinct 1h period identities
- clean 1h promote once; dirty/5m unpromoted
- reporting linkage; production locks; no retry/restart/successor fields

Nearest + broader relevant suite (cross-cutting checkpoint):

- selective 1h, 4A, ownership schema, promotion/safety, final report, zero-source replay,
  E2Q, E2Y, E2Z, Lane K, public operational command
- **All green** after fixture-copy migration apply fix
- No unrelated baseline failures expanded into this lane

Temporary DBs / fixtures / mocks only. No real source calls. No authoritative DB mutation.

---

## 12. Rollback

1. Revert this commit.
2. Do not apply 047 to the live corpus if not yet applied.
3. If 047 was applied later by operator: restore from pre-migration backup; do not
   half-apply selective 1h production flags.

Production default remains 15m-only without this package’s flag.

---

## 13. Money-usefulness contribution

Selective 1h continuation is the controlled path to longer-horizon clean/dirty
lessons (survival, collapse, transition) **without** tracking every token for
every timeframe and without spending budget on ineligible predecessors. Clean
1h memory remains non-financial; it does not imply BUY readiness or profit.

---

## 14. What remains locked

- Operational production 1h activation (requires separate readiness + authorized proof)
- WINDOW_4H / 12H / 24H operational work
- Retrieval, paper decisions, BUY/SELL/HOLD
- Positions, trades, audits, PnL
- Live wallet / private keys / real funds / paid APIs
- Scoring / ranking / confidence / weighted logic
- Embeddings / vectors
- Dirty-memory decision use
- Automatic retry / restart / successor

---

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Mitigation / residual |
|---|---|
| Operator applies 047 but enables selective 1h without readiness review | Public command keeps flag false; LOCKED_WINDOWS unchanged |
| Safety composite missing → all CONTINUE blocked | Fail closed; correct until B.2 evidence present |
| Host sleep / lease expiry during future 1h proof | Existing lease fail-closed; caffeinate operator policy |
| Natural disposition vs 4A policy divergence if both enabled | Selective branch takes priority when flag true |
| Live corpus without 047 fails preflight | Expected until operator applies 047 |

---

## 16. Exact next permitted lane

```text
Separate operator-readiness review for bounded operational selective WINDOW_1H proof
```

Only after that review may a **separately authorized** bounded operational 1h
proof be considered. Do not start V2-10, 4h production, retrieval, or any
financial lane from this PASS.

---

## 17. Confirmation of hard boundaries

This lane did **not** perform:

- real source fetching
- discovery or campaign runtime against live corpus
- authoritative database mutation (`data/printer_v1.sqlite3` untouched)
- real 15m / 1h / 4h collection
- operational 1h activation
- any 4h implementation
- retrieval / paper / BUY-SELL-HOLD / positions / trades / audits / PnL
- wallet / private-key / signing / real-fund work
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- Source Governor or Scheduler bypass
- dirty-memory decision use
- automatic retry / restart / successor
