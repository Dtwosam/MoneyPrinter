# Printer V1 V2-2P.1 Pair Market-Age Context Verification

Status: `INDEPENDENT VERIFICATION`

Verification verdict:

`V2-2P.1 Pair Market Age Context Verification: VERIFICATION_PARTIAL_WITH_BLOCKER`

V2-2J and V2-3 remain paused. The core pair-age versus token-age safety
boundary passed. One required selection-batch metadata handoff is missing.

## 1. Source Stack and Anchors

The verification used these documents together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2o-token-age-evidence-repair-design.md`
- `docs/printer-v1-v2-2p-pair-market-age-context-implementation.md`

Anchors:

- V2-2O design: `75fa981`
- V2-2P implementation: `d879627`
- V2-2P implementation document: `ff8251d`

## 2. Files Inspected

Implementation commit `d879627` changed only:

- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`
- `src/printer_v1/operator_cli/commands.py`
- `tests/test_v2_2p_pair_age_context.py`

No migration, memory, retrieval, paper-decision, position, trade, audit, or PnL
file changed in the implementation commit.

## 3. Static Safety Findings

### 3.1 Pair age never replaces token age

Result: `PASS`.

`normalize_candidate()` derives:

- `pair_age_seconds` only from `_pair_created_at_raw`;
- `token_age_seconds` only from `_token_created_at_raw`.

Repository searches found no assignment from `pair_age_seconds` to
`token_age_seconds` and no age-gate fallback that substitutes pair age for
token age.

### 3.2 Age buckets remain token-age-only

Result: `PASS`.

`derive_age_bucket()` reads only:

```text
candidate.get("token_age_seconds")
```

When that value is absent, invalid, or negative, it returns `AGE_UNKNOWN`.
The function does not read `pair_age_seconds` or `pair_age_context_label`.

### 3.3 A3 remains token-age-gated

Result: `PASS`.

`assign_bucket()` still defines:

```text
_tok_age_known = candidate.get("token_age_seconds") is not None
```

A3 requires `_tok_age_known`, the token-age threshold, and known negative
one-hour price change. Pair age and pair-age context do not participate.

### 3.4 Recent-active tier remains token-age-gated

Result: `PASS`.

`derive_recent_active_tier()` receives the result of `derive_age_bucket()`.
Because the age bucket remains `AGE_UNKNOWN` when token age is missing, a young
pair alone remains `UNKNOWN_TIER_5`.

No direct pair-age fallback exists.

### 3.5 Pair-age context appears in normalized candidates

Result: `PASS`.

`NORMALIZED_FIELDS` includes:

- `pair_age_context_label`;
- `token_age_evidence_tier`.

The parser emits one of:

- `RECENT_LAUNCH` only when real token age is known and below 24 hours;
- `OLDER_TOKEN` when real token age is known and at least 24 hours;
- `RECENT_PAIR_FOR_EXISTING_TOKEN` when token age is unknown and pair age is
  below 24 hours;
- `PAIR_ONLY_AGE_KNOWN` when only an older pair age is known;
- `UNKNOWN_TOKEN_AGE` when neither age is known.

### 3.6 Token-age evidence tier remains inactive

Result: `PASS`.

The normalizer sets `token_age_evidence_tier` to `None`. No T1/T2/T3 source
stamping path was activated. The report may derive the categorical
`T4_PAIR_ONLY` or `T5_UNKNOWN` count for observability, but this does not
populate token age or unlock an age gate.

### 3.7 Pair-age context report appears in discovery output

Result: `PASS`.

`build_discover_candidates_once_payload()` calls
`build_pair_age_context_report()` and returns `pair_age_context_report`.
The report contains:

- counts for all five pair-age context labels;
- counts for T1, T2, T3, T4 pair-only, and T5 unknown;
- known token-age count;
- known pair-age count;
- total candidate count.

All report counts are integers.

## 4. Selection-Batch Metadata Blocker

Required result: selection-batch metadata carries:

- `pair_age_context_label`;
- `token_age_evidence_tier`.

Actual result: `FAIL`.

`build_batch_item()` serializes only fields listed in `_METADATA_FIELDS`.
That tuple includes `token_age_seconds` and `pair_age_seconds`, but it does not
include either V2-2P context field.

A direct read-only function check supplied both fields to `build_batch_item()`
and decoded `candidate_metadata_json`. Results:

| Field | Present in selection metadata |
|---|---|
| `pair_age_context_label` | No |
| `token_age_evidence_tier` | No |

The V2-2P focused tests verify that `accepted_candidates` in discovery output
carry the fields. They do not verify V2-2C `build_batch_item()` metadata.
`tests/test_v2_2c_selection_batch.py` contains no assertions for either field.

This is a narrow handoff omission. It does not weaken age safety, but it means
the implementation does not satisfy every stated V2-2P output contract.

## 5. STNP Safety Verification

Result: `PASS`.

Verified behaviors:

- an old token with a new pair is labeled `OLDER_TOKEN`, not
  `RECENT_LAUNCH`, when token age is known;
- a young pair with unknown token age becomes
  `RECENT_PAIR_FOR_EXISTING_TOKEN`, not `RECENT_LAUNCH`;
- young pair age alone leaves `derive_age_bucket()` at `AGE_UNKNOWN`;
- young pair age alone cannot satisfy the A3 `_tok_age_known` gate;
- young pair age alone leaves recent-active priority at `UNKNOWN_TIER_5`.

The implementation improves STNP observability without treating pair creation
as token creation.

## 6. Downstream Lock Verification

Static diff inspection found no new or modified path for:

- memory generation or memory-window creation;
- retrieval queries or matches;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events or paper audits;
- PnL;
- wallet, private-key, signing, or live execution;
- paid APIs;
- scores, rankings, confidence, or weighted logic;
- embeddings or vectors.

The changed production code only normalizes context fields, aggregates a
report, and exposes accepted-candidate metadata.

## 7. Tests and Checks Run

| Test suite | Result |
|---|---|
| `tests/test_v2_2p_pair_age_context.py` | 67 passed |
| `tests/test_v2_2h3_field_normalization_fast_events.py` | 67 passed, 48 subtests passed |
| `tests/test_v2_2h2_age_activity_recent_priority.py` | 66 passed, 31 subtests passed |
| `tests/test_v2_2c_selection_batch.py` | 112 passed |
| `tests/test_v2_2m_audit_only_handoff.py` | 95 passed |
| `tests/test_post_rc_controlled_discovery_cycle.py` | 8 passed |

Total: 415 tests passed and 79 subtests passed.

Pytest emitted non-failing cache warnings because `.pytest_cache` was not
writable. No test failure occurred.

Static checks included:

- implementation commit scope and diff inspection;
- all repository references to token and pair age;
- assignment/fallback searches;
- A3 and recent-active call-site inspection;
- forbidden downstream capability scan;
- direct `build_batch_item()` metadata decoding.

## 8. Optional Bounded Proof

No live or isolated-DB discovery proof was run.

Reason: static inspection and the focused fixture suites conclusively prove the
token/pair age separation, output report, A3 gate, recent-active gate, and STNP
behavior. The remaining blocker is a deterministic in-memory metadata
extraction omission; a source call or DB copy would add mutation without
clarifying it.

Row-delta proof: not applicable. No database was opened or mutated for this
verification.

## 9. Remaining Blockers

1. Add `pair_age_context_label` and `token_age_evidence_tier` to V2-2C
   selection-batch metadata extraction.
2. Add focused V2-2C tests proving both values survive `build_batch_item()` and
   selection-batch persistence.
3. Real token age remains unavailable until a separately approved governed
   T1/T2/T3 source is implemented.
4. A3 and recent-active tiers correctly remain blocked while token age is
   unknown.
5. Pair age remains context only and must not become a token-age fallback.

## 10. Verification Verdict

`V2-2P.1 Pair Market Age Context Verification: VERIFICATION_PARTIAL_WITH_BLOCKER`

Safety verification passed:

- pair age never replaces token age;
- token-age bucketing remains strict;
- A3 remains strict;
- recent-active priority remains strict;
- STNP behavior remains conservative;
- normalized candidates and discovery reports expose honest pair-age context;
- token-age evidence tiers remain inactive;
- downstream V1 locks remain unchanged.

Completeness verification did not fully pass because V2-2C selection-batch
metadata drops both new context fields.

## 11. Next Recommended Lane

Keep V2-2J and V2-3 paused.

Run a narrow V2-2P.2 selection-metadata handoff repair that adds only the two
context fields to `_METADATA_FIELDS`, adds focused build/persistence regression
tests, and re-runs this verification. It must not change token-age derivation,
A3, recent-active logic, source collection, memory, retrieval, or paper paths.
