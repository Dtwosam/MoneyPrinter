# Printer V1 V2-2S.1 Cross-Batch Selection Cooldown Verification

## 1. Status

Lane: `V2-2S.1 - Cross-Batch Selection Cooldown Verification`

Task type: independent verification only

Verdict: `VERIFICATION_PARTIAL_WITH_BLOCKER`

V2-2J, V2-3, V2-2T, and discovery persistence gate reform remain paused.

V2-2S correctly added rotation-state storage, selected-item recording,
categorical evidence fingerprints, and callable token/pair cooldown helpers.
The implementation is not ready for V2-2T proof because the approved selection
path does not call the cooldown helpers, and the token-level lookup is not safe
when one mint has rotation rows for multiple pairs.

## 2. Source Stack and Anchors

The following documents were read together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2r-discovery-fair-chance-selection-rotation-design.md`
- `docs/printer-v1-v2-2s-cross-batch-selection-cooldown-implementation.md`

Anchors confirmed:

- V2-2R design: `a1257a0`
- V2-2S implementation: `22d0e51`

## 3. Files Inspected

- `migrations/026_selection_rotation_state.sql`
- `src/printer_v1/discovery/selection_batch.py`
- `tests/test_v2_2s_selection_cooldown.py`
- `tests/test_v2_2c_selection_batch.py`
- `tests/test_v2_2p_pair_age_context.py`
- `tests/test_v2_2m_audit_only_handoff.py`
- `tests/test_post_rc_controlled_discovery_cycle.py`
- the V2-2R and V2-2S documents listed above
- commit scope and diff for `a1257a0..22d0e51`

## 4. Migration Verification

Migration 026 creates `printer_selection_rotation_state` with:

- integer primary key
- required `token_mint`
- required `pair_address`
- last selected batch ID
- last selected batch sequence
- last selected timestamp
- last evidence fingerprint JSON
- non-null `selection_count` with default zero
- created and updated timestamps
- unique constraint on `(token_mint, pair_address)`

Indexes exist for:

- `token_mint`
- `pair_address`

The unique token/pair constraint supplies the upsert identity required by
`record_selection_rotation_state()`. The migration contains no score, rank,
confidence, weight, trading signal, retrieval status, or financial field.

Migration verdict: **PASS**.

## 5. Rotation-State Persistence Verification

`persist_selection_batch()`:

1. persists the selection batch;
2. obtains the inserted batch row ID as a monotonic batch sequence;
3. persists all selection batch items;
4. checks whether the rotation-state table exists;
5. calls `record_selection_rotation_state()` when the table is available.

`record_selection_rotation_state()`:

- filters to `SELECTED` items;
- skips rejected and unclassified items;
- skips items without both mint and pair identity;
- stores the latest batch ID, sequence, and timestamp;
- stores sorted categorical fingerprint JSON;
- starts `selection_count` at one;
- increments `selection_count` on a repeated token/pair upsert;
- preserves one row per `(token_mint, pair_address)`.

The focused tests verify direct recording and recording through
`persist_selection_batch()`, including rejected-item exclusion, timestamp and
batch updates, JSON persistence, and count increments.

Rotation-state persistence verdict: **PASS**.

## 6. Cooldown Helper Verification

### 6.1 Nominal Token Rule

For a token selected at sequence 1 with the default three-batch window:

- sequence 2: blocked
- sequence 3: blocked
- sequence 4: allowed

This matches the requested V2-2R nominal rule.

### 6.2 Nominal Pair Rule

The pair helper applies the same rule and orders matching pair rows by latest
batch sequence.

### 6.3 Multi-Pair Token Blocker

Rotation state is uniquely keyed by `(token_mint, pair_address)`, so one mint
can correctly have multiple rows when it appears on multiple pairs.

The token helper currently executes a token-only query without:

- `ORDER BY last_selected_batch_seq DESC`
- `LIMIT 1`
- a `MAX(last_selected_batch_seq)` aggregate

It then calls `fetchone()`. For a mint with multiple pair rows, SQLite is not
required to return the row with the latest token selection. The helper can
therefore evaluate cooldown against an older pair row and allow a token too
early.

The pair helper does not have this defect because it explicitly orders by
latest sequence.

No existing focused test covers a token mint with multiple rotation-state pair
rows and differing last-selected sequences.

Cooldown helper verdict: **PARTIAL / BLOCKED FOR PROOF**.

## 7. Evidence Fingerprint Verification

`compute_evidence_identity_fingerprint()` returns exactly four categorical
fields:

- `activity_bucket`
- `pair_age_context_label`
- `source_channel`
- `primary_bucket`

It does not include:

- token age
- pair age seconds
- numeric score
- rank
- confidence
- weight
- trade action

`fingerprint_change_is_meaningful()` matches the requested V2-2R behavior:

| Change | Result |
|---|---|
| Activity bucket changes | Meaningful |
| Source channel changes | Meaningful |
| Primary bucket crosses group boundary | Meaningful |
| Pair-age context alone changes | Not meaningful |
| Primary bucket changes within same group | Not meaningful |
| Fingerprint remains identical | Not meaningful |

Evidence fingerprint verdict: **PASS**.

## 8. Live-Gate Wiring Assessment

Classification:

`blocker requiring V2-2S.2 wiring repair`

V2-2R Section 9.1 explicitly requires cooldown checks to be wired into the
discovery selection path after existing STNP, lifecycle cooldown/archive, and
WATCH_ONLY promotion gates, and before final quota validation.

Static search found:

- `check_token_selection_cooldown()` defined only in
  `selection_batch.py`;
- `check_pair_selection_cooldown()` defined only in
  `selection_batch.py`;
- no production caller for either helper;
- tests call the helpers directly;
- `persist_selection_batch()` records state after selection but does not enforce
  eligibility before selection.

The absence of an always-running live selection loop does not make this
acceptable for V2-2T. A bounded proof still needs a callable selection
assembly/gate path that actually rejects token and pair cooldown violations.
Otherwise the proof can only demonstrate helper behavior, not cross-batch
selection behavior.

This conclusion does not authorize scheduler/runtime work. The repair should
remain a bounded selection-path wiring change.

## 9. Required V2-2S.2 Repair

Before V2-2T:

1. Make token cooldown select the latest rotation sequence across every pair
   for the mint.
2. Add a focused multi-pair token test proving the latest selection controls
   token cooldown.
3. Wire token and pair cooldown checks into the existing bounded selection
   assembly path before quota validation.
4. Preserve existing STNP, lifecycle, WATCH_ONLY, and audit-only gates.
5. Add integration tests proving:
   - selected at sequence 1;
   - rejected at sequences 2 and 3;
   - allowed at sequence 4;
   - rejected items do not update rotation state;
   - a new pair does not bypass token cooldown;
   - no memory, retrieval, paper, trading, or financial row is created.

Discovery persistence reform remains paused and must not be folded into this
repair.

## 10. Tests and Checks

Executed:

- `python -m pytest tests/test_v2_2s_selection_cooldown.py -q`
  - 61 passed
- `python -m pytest tests/test_v2_2c_selection_batch.py -q`
  - 120 passed
- `python -m pytest tests/test_v2_2p_pair_age_context.py -q`
  - 67 passed
- `python -m pytest tests/test_v2_2m_audit_only_handoff.py -q`
  - 95 passed
- `python -m pytest tests/test_post_rc_controlled_discovery_cycle.py -q`
  - 8 passed

Total: **351 passed**.

Each pytest invocation emitted one cache warning because the environment could
not create `.pytest_cache/v/cache/nodeids`. The warning did not fail a test.
The environment also printed unrelated local-chain plugin configuration during
pytest startup. No live discovery or external source command was run.

Static checks included:

- V2-2S commit file-scope inspection;
- source and downstream path name scan;
- helper call-site search;
- pair-age-to-token-age assignment search;
- A3, age-bucket, and recent-active call-site inspection;
- score/rank/confidence/weighted term classification.

## 11. Safety Confirmations

The V2-2S commit changed only:

- the implementation closeout document;
- migration 026;
- selection batch/rotation code;
- focused cooldown tests.

Static inspection confirms:

- no source-fetching path changed;
- no discovery persistence reform was added;
- no scheduler/runtime path changed;
- no memory or memory-window path changed;
- no retrieval path changed;
- no paper decision path changed;
- no BUY/SELL/HOLD path changed;
- no position, trade, audit, or PnL path changed;
- no scoring, ranking, confidence, or weighted logic was introduced;
- no embeddings or vectors were introduced;
- no pair age is copied into token age;
- `derive_age_bucket()` still reads token age;
- A3 still requires known token age;
- recent-active classification still consumes the token-derived age bucket.

All downstream capabilities remain locked.

## 12. Remaining Blockers

1. Token cooldown is not latest-row-safe for a mint with multiple pairs.
2. Token and pair cooldown helpers are not wired into the bounded selection
   gate path.
3. Evidence-fingerprint meaningful-change waiver behavior is helper-level and
   is not yet an enforced selection-path policy.
4. Source/category exposure rotation and discovery persistence reform remain
   outside V2-2S and paused.
5. V2-2T cannot prove cross-batch enforcement until items 1 and 2 are repaired.

## 13. Verification Verdict

`VERIFICATION_PARTIAL_WITH_BLOCKER`

Migration, persistence, nominal cooldown behavior, and categorical fingerprint
logic pass verification. The implementation does not yet enforce cooldown in
the selection path, and token cooldown can read an older row for multi-pair
mints.

V2-2S.2 is required before bounded proof.

## 14. Next Recommended Lane

`V2-2S.2 - Cross-Batch Selection Cooldown Wiring and Latest-Token-State Repair`

V2-2T is **not allowed yet**.

V2-2S.2 should stay narrow:

- fix latest token rotation-state lookup;
- wire token and pair checks into bounded selection assembly;
- add focused integration tests;
- preserve every existing V1 lock;
- leave discovery persistence reform paused.
