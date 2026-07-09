# Printer V1 V2-2P.3 Pair Market-Age Metadata Verification

Status: `INDEPENDENT POST-REPAIR VERIFICATION`

Verification verdict:

`V2-2P.3 Pair Market Age Metadata Handoff Verification: VERIFICATION_PASS`

V2-2J and V2-3 remained paused. V2-2Q was not started during this
verification.

## 1. Source Stack and Anchors

The verification used:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2o-token-age-evidence-repair-design.md`
- `docs/printer-v1-v2-2p-pair-market-age-context-implementation.md`
- `docs/printer-v1-v2-2p-1-pair-market-age-context-verification.md`

Anchors:

- V2-2P implementation: `d879627`
- V2-2P implementation document: `ff8251d`
- V2-2P.1 verification: `165bf6e`
- V2-2P.2 repair: `09d4ea0`

## 2. Files Inspected

The V2-2P.2 repair changed only:

- `src/printer_v1/discovery/selection_batch.py`
- `tests/test_v2_2c_selection_batch.py`

Production change size: two metadata fields plus one explanatory comment.

No parser, source, operator command, migration, memory, retrieval, paper,
position, trade, audit, or PnL file changed.

## 3. Metadata Handoff Result

### 3.1 Metadata field declaration

Result: `PASS`.

`_METADATA_FIELDS` now includes:

- `pair_age_context_label`;
- `token_age_evidence_tier`.

### 3.2 In-memory batch item

Result: `PASS`.

`build_batch_item()` calls `extract_candidate_metadata()`, then serializes the
result into `candidate_metadata_json`. Both fields therefore survive:

- direct metadata extraction;
- batch-item construction;
- JSON serialization and decoding.

The focused tests cover all five pair-age context labels:

- `RECENT_LAUNCH`;
- `OLDER_TOKEN`;
- `RECENT_PAIR_FOR_EXISTING_TOKEN`;
- `PAIR_ONLY_AGE_KNOWN`;
- `UNKNOWN_TOKEN_AGE`.

They also confirm that a missing or inactive `token_age_evidence_tier` remains
present with the honest value `None`.

### 3.3 Selection-batch persistence

Result: `PASS`.

The V2-2C regression suite:

1. builds a selected batch item containing
   `pair_age_context_label = RECENT_PAIR_FOR_EXISTING_TOKEN`;
2. keeps `token_age_evidence_tier = None`;
3. persists the item through `persist_selection_batch()`;
4. reads `candidate_metadata_json` from
   `printer_selection_batch_items`;
5. confirms both values survived unchanged.

No schema migration was needed because the existing metadata JSON column is
the intended storage boundary.

## 4. Safety Confirmations

### Token and pair age derivation

Result: `UNCHANGED`.

The repair did not modify `parser.py`. Pair age remains derived only from pair
creation time, and token age remains derived only from token creation time.
There is no pair-age-to-token-age assignment.

### Age bucket

Result: `UNCHANGED`.

`derive_age_bucket()` still reads only `token_age_seconds`. Pair age and
pair-age context remain excluded.

### A3

Result: `UNCHANGED`.

A3 still requires:

- known `token_age_seconds`;
- the real token-age threshold;
- known negative one-hour price change.

No pair-age fallback was introduced.

### Recent-active tier

Result: `UNCHANGED`.

Recent-active tier still consumes the token-age-derived age bucket. A young
pair with unknown token age remains `AGE_UNKNOWN` and `UNKNOWN_TIER_5`.

### Source and downstream locks

Result: `UNCHANGED`.

Static commit inspection found no modification to:

- source fetching or Source Governor;
- scheduler/runtime;
- memory generation or windows;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- positions, trades, paper audits, or PnL;
- wallet, private-key, signing, or live execution;
- paid APIs;
- scoring, ranking, confidence, or weighted logic;
- embeddings or vectors.

The new fields remain categorical audit/context metadata only.

## 5. Tests and Checks Run

| Test suite | Result |
|---|---|
| `tests/test_v2_2c_selection_batch.py` | 120 passed |
| `tests/test_v2_2p_pair_age_context.py` | 67 passed |
| `tests/test_v2_2h3_field_normalization_fast_events.py` | 67 passed, 48 subtests passed |
| `tests/test_v2_2h2_age_activity_recent_priority.py` | 66 passed, 31 subtests passed |
| `tests/test_v2_2m_audit_only_handoff.py` | 95 passed |
| `tests/test_post_rc_controlled_discovery_cycle.py` | 8 passed |

Total: 423 tests passed and 79 subtests passed.

Pytest emitted non-failing cache warnings because `.pytest_cache` was not
writable. No test failed.

Static checks included:

- V2-2P.2 commit scope and complete diff inspection;
- direct inspection of `_METADATA_FIELDS`;
- metadata extraction and persistence test inspection;
- pair-age/token-age fallback searches;
- A3 and recent-active boundary review;
- downstream forbidden-capability diff scan.

## 6. Remaining Blockers

The V2-2P.1 metadata blocker is resolved.

Broader age-evidence constraints remain intentionally unchanged:

- real token creation age still requires a separately approved governed
  T1/T2/T3 source;
- `token_age_evidence_tier` remains `None` until that source exists;
- A3 and recent-active tiers remain blocked when token age is unknown;
- pair age remains context only and cannot substitute for token age.

These are roadmap constraints, not failures of the V2-2P.2 repair.

## 7. V2-2Q Gate

From the V2-2P metadata-handoff perspective, V2-2Q is now allowed.

This statement does not start V2-2Q and does not override operator approval or
the active build order. V2-2J and V2-3 remain paused.

V2-2Q must preserve:

- pair age as context only;
- real token-age requirements for age buckets, A3, and recent-active tiers;
- all Source Governor and Central Scheduler boundaries;
- all memory, retrieval, paper, trading, and financial locks.

## 8. Final Verdict

`V2-2P.3 Pair Market Age Metadata Handoff Verification: VERIFICATION_PASS`

The repair fully closes the V2-2P.1 blocker:

- both fields are declared in metadata extraction;
- both survive `build_batch_item()`;
- both survive selection-batch DB persistence;
- all age/STNP safety boundaries remain unchanged;
- no downstream capability was touched.

## 9. Next Recommended Lane

V2-2Q may proceed only after explicit operator approval and according to its
defined roadmap scope. Keep V2-2J and V2-3 paused.
