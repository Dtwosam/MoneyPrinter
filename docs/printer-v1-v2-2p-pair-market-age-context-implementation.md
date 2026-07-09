# Printer V1 V2-2P Pair Market Age Context Implementation

Status: `IMPLEMENTATION`

Final verdict:

`V2-2P Pair Market Age Context Implementation: IMPLEMENTATION_COMPLETE_WITH_BLOCKERS`

V2-2J and V2-3 remain paused. This lane implements the T4-safe pair-age context
layer from the V2-2O design. No DB migration, no live source fetch, no
T1/T2/T3 token-creation evidence, no memory generation, no retrieval, no paper
decisions, no BUY/SELL/HOLD, no positions/trades/audits/PnL, no
scoring/ranking/confidence/weighted logic.

---

## Implementation Anchors

- V2-2O design: `75fa981`
- V2-2P implementation: `d879627`

---

## Files Changed

| File | Change |
|---|---|
| `src/printer_v1/discovery/parser.py` | Added `_derive_pair_age_context_label()`, added `pair_age_context_label` and `token_age_evidence_tier` to `NORMALIZED_FIELDS` and `normalize_candidate()` |
| `src/printer_v1/discovery/selection_batch.py` | Added 5 `PAIR_AGE_CONTEXT_*` constants, `ALLOWED_PAIR_AGE_CONTEXT_LABELS` frozenset, and `build_pair_age_context_report()` |
| `src/printer_v1/operator_cli/commands.py` | Imported `build_pair_age_context_report`, computed `_pair_age_context_report`, added it to payload and added `pair_age_context_label` / `token_age_evidence_tier` to `accepted_candidates` |
| `tests/test_v2_2p_pair_age_context.py` | 67-test focused suite covering all required V2-2P behaviors |

---

## Exact Fields Added

### `src/printer_v1/discovery/parser.py`

**New function:**
```python
def _derive_pair_age_context_label(
    token_age_seconds: float | None,
    pair_age_seconds: float | None,
) -> str:
    if token_age_seconds is not None:
        return "RECENT_LAUNCH" if token_age_seconds < 86400.0 else "OLDER_TOKEN"
    if pair_age_seconds is None:
        return "UNKNOWN_TOKEN_AGE"
    return "RECENT_PAIR_FOR_EXISTING_TOKEN" if pair_age_seconds < 86400.0 else "PAIR_ONLY_AGE_KNOWN"
```

**New `NORMALIZED_FIELDS` entries:**
- `"pair_age_context_label"` — T4-safe context label, never drives age gates
- `"token_age_evidence_tier"` — always `None` until T1/T2/T3 source active

**New `normalize_candidate()` entries:**
```python
"pair_age_context_label": _derive_pair_age_context_label(
    _safe_age_seconds(_token_created_at_raw, _now),
    _safe_age_seconds(_pair_created_at_raw, _now),
),
"token_age_evidence_tier": None,
```

### `src/printer_v1/discovery/selection_batch.py`

**New constants:**
```python
PAIR_AGE_CONTEXT_RECENT_LAUNCH = "RECENT_LAUNCH"
PAIR_AGE_CONTEXT_OLDER_TOKEN = "OLDER_TOKEN"
PAIR_AGE_CONTEXT_RECENT_PAIR_FOR_EXISTING_TOKEN = "RECENT_PAIR_FOR_EXISTING_TOKEN"
PAIR_AGE_CONTEXT_PAIR_ONLY_AGE_KNOWN = "PAIR_ONLY_AGE_KNOWN"
PAIR_AGE_CONTEXT_UNKNOWN_TOKEN_AGE = "UNKNOWN_TOKEN_AGE"
ALLOWED_PAIR_AGE_CONTEXT_LABELS: frozenset[str] = frozenset({...})
```

**New function:** `build_pair_age_context_report(candidates)` returning:
- `pair_age_context_label_counts`: count per label (all ints)
- `token_age_evidence_tier_counts`: `{"T1":0, "T2":0, "T3":0, "T4_PAIR_ONLY":N, "T5_UNKNOWN":M}`
- `tok_age_known_count`: int
- `pair_age_known_count`: int
- `total_candidates`: int

### `src/printer_v1/operator_cli/commands.py`

**New import:** `build_pair_age_context_report`

**New report computation** (alongside `_age_activity_report`):
```python
_pair_age_context_report = build_pair_age_context_report(all_normalized_pairs)
```

**New payload key** (alongside `field_completeness_report`):
```python
"pair_age_context_report": _pair_age_context_report,
```

**Extended `accepted_candidates` per-item:**
```python
"pair_age_context_label": candidate.get("pair_age_context_label"),
"token_age_evidence_tier": candidate.get("token_age_evidence_tier"),
```

---

## Label Logic

| Condition | Label |
|---|---|
| `token_age_seconds` known and `< 86400` | `RECENT_LAUNCH` |
| `token_age_seconds` known and `>= 86400` | `OLDER_TOKEN` |
| `token_age_seconds` unknown, `pair_age_seconds` unknown | `UNKNOWN_TOKEN_AGE` |
| `token_age_seconds` unknown, `pair_age_seconds` known and `< 86400` | `RECENT_PAIR_FOR_EXISTING_TOKEN` |
| `token_age_seconds` unknown, `pair_age_seconds` known and `>= 86400` | `PAIR_ONLY_AGE_KNOWN` |

---

## Proof That Pair Age Does Not Replace Token Age

### Separation rules enforced

1. `_derive_pair_age_context_label` is the only function that reads both fields.
   It returns a string label. It writes nothing to `token_age_seconds`.
2. `normalize_candidate()` still computes `pair_age_seconds` from
   `_safe_age_seconds(_pair_created_at_raw, _now)` and `token_age_seconds` from
   `_safe_age_seconds(_token_created_at_raw, _now)` independently. Neither is
   assigned from the other.
3. `derive_age_bucket(candidate)` is unchanged. It reads
   `candidate.get("token_age_seconds")` only and returns `AGE_UNKNOWN` when `None`.
4. `derive_recent_active_tier(age_bucket, activity_bucket)` is unchanged. It
   returns `UNKNOWN_TIER_5` when `age_bucket == AGE_UNKNOWN`.
5. `assign_bucket()` A3 gate: `_tok_age_known = candidate.get("token_age_seconds") is not None`
   is unchanged. When `token_age_seconds` is `None`, A3 does not fire regardless
   of `pair_age_seconds`.

### Tests proving separation

- `TestPairAgeDoesNotReplaceTokenAge.test_token_age_seconds_is_none_when_only_pair_created_at_present`
- `TestPairAgeDoesNotReplaceTokenAge.test_pair_age_seconds_is_not_equal_to_token_age_seconds`
- `TestPairAgeDoesNotReplaceTokenAge.test_derive_age_bucket_ignores_pair_age_seconds`
- `TestPairAgeDoesNotReplaceTokenAge.test_derive_recent_active_tier_unknown_when_only_pair_age_known`
- `TestA3SafetyPairAgeDoesNotUnlockA3.test_a3_does_not_fire_with_only_pair_age`
- `TestA3SafetyPairAgeDoesNotUnlockA3.test_tok_age_known_flag_false_when_token_age_none`
- `TestSTNPSafety.test_unknown_token_new_pair_does_not_unlock_a3`
- `TestSTNPSafety.test_unknown_token_new_pair_does_not_set_recent_active_tier`

---

## Tests and Checks Run

### V2-2P focused suite

| Suite | Result |
|---|---|
| `tests/test_v2_2p_pair_age_context.py` | **67 passed** |

Test coverage by section:
- Section 1 — `_derive_pair_age_context_label` unit tests: 12 tests
- Section 2 — `normalize_candidate` new-field tests: 7 tests
- Section 3 — Pair age vs token age separation: 6 tests
- Section 4 — A3 safety: 4 tests
- Section 5 — STNP safety: 5 tests
- Section 6 — `build_pair_age_context_report` counts: 14 tests
- Section 7 — Payload report integration: 10 tests
- Section 8 — `accepted_candidates` metadata: 5 tests
- Section 9 — Constants export: 4 tests

### Required regressions

| Suite | Result |
|---|---|
| `tests/test_v2_2h3_field_normalization_fast_events.py` | **67 passed, 48 subtests passed** |
| `tests/test_v2_2h2_age_activity_recent_priority.py` | **66 passed, 31 subtests passed** |
| `tests/test_v2_2c_selection_batch.py` | **112 passed** |
| `tests/test_v2_2m_audit_only_handoff.py` | **95 passed** |
| `tests/test_post_rc_controlled_discovery_cycle.py` | **8 passed** |

### Git checks

| Check | Result |
|---|---|
| `git diff --check` | Clean (LF/CRLF warnings only, not errors) |
| `git status --short` | 3 modified source files + 1 new test file staged; all others untracked/unchanged |
| `git diff --stat` | 97 insertions, 0 deletions across 3 source files |
| `git diff --name-only` | `parser.py`, `selection_batch.py`, `commands.py` (source only; test untracked at check time) |

---

## What Improved

1. **Pair-age visibility**: Every normalized candidate now carries
   `pair_age_context_label`. With current GeckoTerminal sources (98.6% pair-age
   coverage), 98.6% of candidates will be labeled `RECENT_PAIR_FOR_EXISTING_TOKEN`
   or `PAIR_ONLY_AGE_KNOWN` rather than `UNKNOWN_TOKEN_AGE`.

2. **STNP surface**: `RECENT_PAIR_FOR_EXISTING_TOKEN` flags the specific case
   where a young pair exists but token age is unknown — the highest-risk STNP
   scenario. This was previously invisible; now it is labeled in every report.

3. **Report completeness**: `pair_age_context_report` appears in the
   `build_discover_candidates_once_payload` output with correct integer counts for
   all 5 labels and all 5 evidence tiers, plus `tok_age_known_count`,
   `pair_age_known_count`, and `total_candidates`.

4. **T1/T2/T3 pipeline readiness**: `token_age_evidence_tier` is wired into the
   normalized output and report. When a future T1/T2/T3 source is activated, the
   stamping and counting plumbing already exists. No additional parser/report
   changes are needed at that point.

5. **No gate drift**: All existing age gates (`derive_age_bucket`, A3,
   `derive_recent_active_tier`) are provably unchanged. The regression suites
   confirm this across 348 tests.

---

## What Still Does Not Unlock

| Capability | Reason |
|---|---|
| Real `AGE_0_24H` / `AGE_1_7D` buckets in live batches | Requires T1/T2/T3 token-creation source; not activated in V2-2P |
| `RECENT_ACTIVE_TIER_1` / `TIER_2` in live batches | Derived from token age; blocked until T1/T2/T3 present |
| A3 firing in live batches | `_tok_age_known` always False; T1/T2/T3 needed |
| Quota violation `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET` resolved | A3 must fire; pair age cannot substitute |
| STNP multi-pair detection | Separate future lane; requires per-mint pair history |
| PumpPortal / PumpSwap token age | Both sources remain NOT_READY |
| Solana RPC / Helius enrichment | Not a current discovery path; separate design needed |

---

## Remaining Blockers

1. `token_created_at` absent 100% from GeckoTerminal and DexScreener. V2-2P
   implements T4 context labels; live token age requires T1/T2/T3 evidence.
2. `token_age_evidence_tier` is always `None` in current production. It will
   remain `None` until a governed T1/T2/T3 source path is wired.
3. A3 gate remains blocked. `_tok_age_known` is always `False` in live batches.
4. `AGE_UNKNOWN` and `UNKNOWN_TIER_5` remain the universal live state for all
   candidates.
5. `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET` quota violation remains unresolved.
6. PumpPortal and PumpSwap feeds remain NOT_READY.

---

## Functionality Risks / Setbacks / Efficiency Blockers

### Risk 1 — T4 label misread as age classification

`RECENT_PAIR_FOR_EXISTING_TOKEN` could be misread as meaning the token is
recent. The label name is chosen to make the distinction explicit, and the test
suite explicitly asserts that this label does not unlock A3 or
`derive_recent_active_tier`. Any future contributor adding a gate based on
`pair_age_context_label` directly would need to add new proof tests.

### Risk 2 — token_age_evidence_tier stamping in plan loop not yet wired

When a T1/T2/T3 source is activated in a future lane, the per-candidate
stamping of `token_age_evidence_tier` must follow the H.6 pattern (stamped in
the plan loop inside `commands.py`, like `source_status` and
`data_quality_label`). The field is present in `NORMALIZED_FIELDS` and in the
normalize output as `None`, but the plan-loop stamping override is not yet
implemented. This is intentional (T1/T2/T3 not active) but must not be
forgotten in that future lane.

### Efficiency note — `_safe_age_seconds` called twice for label

`_derive_pair_age_context_label` in `normalize_candidate` calls
`_safe_age_seconds(_token_created_at_raw, _now)` and
`_safe_age_seconds(_pair_created_at_raw, _now)` a second time (they are also
called for `token_age_seconds` and `pair_age_seconds` fields). The function is
pure and cheap; the double call is intentional for readability. If the parser
is ever profiled as a bottleneck, the computed values can be hoisted to locals.

---

## Next Recommended Lane

V2-2J and V2-3 remain paused.

V2-2P implementation is complete. The natural next safe step is V2-2J closeout.
V2-2J should consolidate V2-2K, V2-2N, V2-2N.1, V2-2O design, and V2-2P
implementation findings and decide whether the token-age T1/T2/T3 evidence lane
(V2-2O implementation proper) is opened inside V2-2 or carried to a later
approved lane.

---

## Implementation Verdict

`V2-2P Pair Market Age Context Implementation: IMPLEMENTATION_COMPLETE_WITH_BLOCKERS`

The T4-safe pair-age context layer is implemented, tested, and committed. Pair
age never replaces token age. All age gates, A3, and recent-active tier
derivation remain unchanged and proven by 348 passing regression tests. The
implementation delivers pair-age visibility and STNP surface today, and leaves
the T1/T2/T3 pipeline ready for a future source lane.
