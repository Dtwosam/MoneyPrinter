# Printer V1 V2-2V.1 Discovery Persistence Gate Reform Verification

## 1. Status

**Lane:** V2-2V.1 - Discovery Persistence Gate Reform Verification
**Task type:** Independent verification only
**Verdict:** `VERIFICATION_PASS_WITH_BLOCKERS`
**Date:** 2026-07-09

V2-2W proof, V2-2J, V2-3, token-age evidence work, and source expansion remain paused.

This lane verifies the V2-2V implementation. It does not implement repairs, mutate
the persistent database, run live discovery, fetch sources, run scheduler/runtime,
generate memory, activate retrieval, create paper decisions, authorize BUY/SELL/HOLD,
open positions, create trades, create paper trade audits, or create PnL.

No scoring, ranking, confidence percentage, weighted logic, embeddings, vectors,
wallet, private-key, real-fund, or live-execution behavior is introduced.

## 2. Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2u-discovery-persistence-gate-reform-design.md`
- `docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md`

Current anchors checked:

- V2-2U design: `fe60ba6`
- V2-2V implementation: `147d4b7`

## 3. Files Inspected

- `src/printer_v1/operator_cli/commands.py`
- `src/printer_v1/discovery/selection_batch.py`
- `tests/test_v2_2v_discovery_persistence_gate_reform.py`
- `tests/test_post_rc_controlled_discovery_cycle.py`
- `tests/test_v2_2s_selection_cooldown.py`
- `tests/test_v2_2c_selection_batch.py`
- `tests/test_v2_2p_pair_age_context.py`
- `tests/test_v2_2m_audit_only_handoff.py`
- `docs/printer-v1-v2-2u-discovery-persistence-gate-reform-design.md`
- `docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md`

V2-2V changed only:

- `src/printer_v1/operator_cli/commands.py`
- `tests/test_v2_2v_discovery_persistence_gate_reform.py`
- `docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md`

No V2-2V diff touched source adapters, scheduler/runtime execution, memory
generation, retrieval, paper decision, paper position, trade, audit, PnL,
wallet/private-key/signing, scoring/ranking/confidence/weighted, embedding, or
vector paths.

## 4. Tier 2 Insertion-Point Verification

Result: `PASS`

Verified implementation:

- `_select_discovery_candidates()` now accepts `db_path_or_conn`.
- It opens or reuses a caller-provided SQLite connection only for read-side
  lifecycle/fingerprint context.
- It batch-loads lifecycle statuses for returning mints before the candidate loop.
- It pre-computes `primary_bucket` with `assign_bucket(candidate)` before the
  Tier 2 DISTINCT_NEW_EVIDENCE fingerprint comparison.
- `_classify_returning_candidate()` is called inside the duplicate gate only when
  `token_mint in existing_token_mints`.
- Pair-only collisions (`new mint + existing pair`) do not run the resurfacing
  allowance path and still fall through to `duplicate_pair_address`.
- If Tier 2 does not return `ALLOWED`, the original flat rejection reasons remain:
  `duplicate_existing_token_or_pair`, `duplicate_existing_token_mint`, or
  `duplicate_pair_address`.

This satisfies the V2-2U insertion-point requirement: returning existing mints
can be examined before flat existing-mint rejection, while pair-only collisions
remain blocked.

## 5. MIGRATION Verification

Result: `PASS`

Verified behavior:

- Existing mint + migration channel + genuinely new pair is allowed.
- Migration channels recognized:
  - `PUMPFUN_MIGRATION`
  - `PUMPSWAP_GRADUATED`
  - `PUMPSWAP_MIGRATION_POOL_REFERENCE`
- Migration channel + existing pair is blocked.
- Same mint + new pair + non-migration channel is blocked.
- Migration allowance calls `classify_same_token_new_pair(STNP_MIGRATION, same_token_new_pair=True)`.
- No duplicate recycle path is accidentally allowed through migration when the
  pair already exists.

Safety note: MIGRATION is stateless in V2-2V. It can be allowed without
`db_path_or_conn` because the migration channel plus new pair is the evidence
shape designed in V2-2U. It still does not create memory, retrieval, paper, or
financial rows.

## 6. REVIVAL Verification

Result: `PASS`

Verified behavior:

- Only `COOLDOWN` or `ARCHIVED` lifecycle states can trigger the REVIVAL path.
- Lifecycle statuses are batch-loaded by `_load_returning_mint_lifecycle_statuses()`
  before the main loop.
- `ARCHIVED` + `ACTIVITY_REVIVING` is allowed.
- `COOLDOWN` + `ACTIVITY_REVIVING` is allowed.
- `QUEUED` / non-archived lifecycle is blocked.
- Archived/cooldown candidate with dead/no reviving activity is blocked.
- REVIVAL reports `prior_lifecycle_state`.

This satisfies the V2-2U revival boundary. The gate does not make dead archived
tokens eligible merely because the mint is old or resurfaced.

## 7. DISTINCT_NEW_EVIDENCE Verification

Result: `PASS_WITH_NON_BLOCKING_REPORTING_NOTE`

Verified behavior:

- Same mint + same pair + meaningful activity-bucket change is allowed.
- Same mint + same pair + meaningful source-channel change is allowed.
- No historical discovery payload is blocked.
- Unparseable historical payload is blocked.
- Same fingerprint / no meaningful change is blocked.
- Pair-age-only change remains blocked by `fingerprint_change_is_meaningful()`.
- Same-group primary-bucket-only change remains blocked by
  `fingerprint_change_is_meaningful()`.
- `primary_bucket` is populated before computing the current fingerprint.
- Historical payloads are re-bucketed with `assign_bucket()` before historical
  fingerprint calculation.
- `pair_age_seconds` is not copied into `token_age_seconds`.

Non-blocking reporting note:

- `_fingerprint_change_type()` reports `primary_bucket_group_crossing` whenever
  `old_bucket != new_bucket`.
- The allowance gate still calls `fingerprint_change_is_meaningful()` first, so
  same-group primary-bucket-only changes do not become eligible.
- This means the safety gate is correct, but a selected DISTINCT_NEW_EVIDENCE
  candidate that is already allowed by activity or source-channel change could
  carry an over-broad `fingerprint_change_type` label if primary bucket also
  changed within the same group.
- This is a categorical reporting precision issue only. It does not create a
  score, ranking, trade signal, memory row, retrieval row, paper decision, or
  financial row. It should be watched in V2-2W proof output but does not block
  proof from running.

## 8. Tier 1 Hard-Block Verification

Result: `PASS`

Verified hard blocks:

- Exact duplicate / duplicate recycle remains blocked when no meaningful
  fingerprint change exists.
- STNP unresolved (`same mint + new pair + non-migration channel`) remains blocked.
- Pair-only collision remains blocked.
- Non-Solana candidate remains blocked before Tier 2.
- Dirty/stale/unsafe candidates remain controlled by existing discovery
  classification and data-quality gates.
- Missing historical source/evidence trace for DISTINCT_NEW_EVIDENCE blocks
  safely through `no_historical_fingerprint_null_safe_block`.

V2-2V does not weaken within-response STNP filtering in
`filter_within_response_duplicates()`.

## 9. Reporting Fields Verification

Result: `PASS`

Accepted Tier 2 candidates can carry the requested categorical reporting fields:

- `resurfacing_category`
- `resurfacing_reason`
- `tier2_gate_outcome`
- `prior_lifecycle_state`
- `fingerprint_change_type`

These fields are descriptive. They are not scores, rankings, confidence values,
weighted decisions, BUY/SELL/HOLD signals, memory-cleanliness gates, retrieval
signals, or paper-trading signals.

## 10. B-PERSIST-1 Assessment

Classification: `documentation wording issue`

The V2-2V implementation report says:

```text
printer_selection_rotation_state.last_evidence_fingerprint_json not written
```

That statement is too broad in context.

Verified:

- V2-2S already writes `last_evidence_fingerprint_json` to
  `printer_selection_rotation_state` for persisted selected batch items through
  `record_selection_rotation_state()`.
- V2-2V does not write to `printer_selection_rotation_state`; that is correct
  for this lane because V2-2V is a discovery persistence gate reform, not a
  selection-rotation write-path lane.
- V2-2V correctly reads from `printer_discovery_candidates` for
  DISTINCT_NEW_EVIDENCE because the discovery gate must not depend on a
  selection batch having already run.

Conclusion:

- No functional blocker.
- No schema blocker.
- No V2-2W blocker.
- The implementation report wording should be interpreted narrowly as
  "V2-2V itself does not write the rotation-state fingerprint column."

## 11. Tests and Checks Run

Targeted tests:

```text
python -m pytest tests/test_v2_2v_discovery_persistence_gate_reform.py -q
45 passed, 42 subtests passed, 1 pytest cache warning

python -m pytest tests/test_post_rc_controlled_discovery_cycle.py -q
8 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2s_selection_cooldown.py -q
80 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2c_selection_batch.py -q
120 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2p_pair_age_context.py -q
67 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2m_audit_only_handoff.py -q
95 passed, 1 pytest cache warning
```

Total targeted result:

```text
415 passed
42 subtests passed
0 failed
```

Static inspections run:

```text
git status --short
git show --stat --oneline 147d4b7
git show --name-only --format= 147d4b7
rg -n "_classify_returning_candidate|_load_returning_mint_lifecycle_statuses|_load_last_discovery_fingerprint|_fingerprint_change_type|resurfacing_category|tier2_gate_outcome|prior_lifecycle_state|fingerprint_change_type|duplicate_existing_token|db_path_or_conn|assign_bucket\(" src/printer_v1/operator_cli/commands.py tests/test_v2_2v_discovery_persistence_gate_reform.py
rg -n "last_evidence_fingerprint_json|record_selection_rotation_state|compute_evidence_identity_fingerprint|fingerprint_change_is_meaningful|check_token_selection_cooldown|pair_age_seconds|token_age_seconds" src/printer_v1/discovery/selection_batch.py src/printer_v1/operator_cli/commands.py tests/test_v2_2v_discovery_persistence_gate_reform.py
git diff fe60ba6..147d4b7 --stat
git diff fe60ba6..147d4b7 --name-only
rg -n "source_fetch|http|requests\.|urllib|scheduler|memory_window|retrieval|paper_decision|paper_position|trade_event|paper_trade|PnL|pnl|BUY|SELL|HOLD|score|rank|confidence|weighted|embedding|vector|token_age_seconds.*pair_age|pair_age_seconds.*token_age|Source Governor|Central Scheduler" src/printer_v1/operator_cli/commands.py tests/test_v2_2v_discovery_persistence_gate_reform.py docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md
rg -n "_classify_returning_candidate|_select_discovery_candidates|filter_within_response_duplicates|classify_same_token_new_pair|record_discovery_candidate|printer_selection_rotation_state|last_evidence_fingerprint_json" src tests docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md
```

The broad risky-term scans found many pre-existing matches in
`operator_cli/commands.py` because that file contains many operator commands and
lock/report sections. The V2-2V diff itself was limited to the discovery
selection helper path, the V2-2V tests, and the V2-2V implementation doc.

## 12. Safety Confirmations

Confirmed:

- No source-fetching path changed by V2-2V.
- No runtime/scheduler execution path changed by V2-2V.
- No memory generation path changed by V2-2V.
- No retrieval path changed by V2-2V.
- No paper decision path changed by V2-2V.
- No BUY/SELL/HOLD path changed by V2-2V.
- No paper position, trade, audit, or PnL path changed by V2-2V.
- No scoring, ranking, confidence, or weighted logic was added.
- No embeddings or vectors were added.
- No `token_age_seconds` synthesis from pair age was found.
- No Source Governor bypass was added.
- No Central Scheduler bypass was added.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- V2-2J, V2-3, token-age evidence work, and source expansion remain paused.

## 13. Remaining Blockers

V2-2V.1 found no safety blocker that requires V2-2V.2 before proof.

Remaining non-blocking proof considerations:

1. V2-2W must prove the gate under bounded isolated proof conditions, not only
   unit tests.
2. The `_fingerprint_change_type()` reporting nuance should be watched in proof
   output; it is not an allowance-gate issue.
3. Token-age evidence work remains paused, so A3 and token-age-based discovery
   paths remain outside this lane.
4. Source expansion remains paused; PumpPortal/PumpSwap and broader provider
   coverage are not activated by this verification.

## 14. V2-2W Proof Decision

V2-2W proof is allowed.

V2-2V.2 repair is not required before V2-2W, because:

- The Tier 2 insertion point is correct.
- MIGRATION, REVIVAL, and DISTINCT_NEW_EVIDENCE behaviors are covered by tests.
- Tier 1 hard blocks remain intact.
- B-PERSIST-1 is a documentation wording issue, not a functional blocker.
- The requested regression suite passed.
- No downstream retrieval, paper, BUY/SELL/HOLD, position, trade, audit, PnL,
  source-fetching, runtime, scoring, embedding, or vector path was changed.

V2-2W must remain a bounded proof lane. It must not start V2-2J, V2-3,
token-age evidence work, source expansion, memory generation, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## 15. Final Verdict

```text
VERIFICATION_PASS_WITH_BLOCKERS
V2_2W_ALLOWED: YES
V2_2V_2_REPAIR_REQUIRED: NO
LIVE_DB_MUTATED: NO
LIVE_DISCOVERY_RUN: NO
SOURCE_FETCHING_RUN: NO
SCHEDULER_RUNTIME_RUN: NO
MEMORY_GENERATION_RUN: NO
RETRIEVAL_ACTIVATED: NO
PAPER_DECISIONS_CREATED: NO
BUY_SELL_HOLD_UNLOCKED: NO
POSITIONS_TRADES_AUDITS_PNL_CREATED: NO
NEXT_RECOMMENDED_LANE: V2-2W - Discovery Persistence Gate Reform Bounded Proof
```
