# Printer V1 V2-2U Discovery Persistence Gate Reform Design

## 1. Status

**Lane:** V2-2U - Discovery Persistence Gate Reform Design
**Task type:** Design-only
**Verdict:** `DESIGN_COMPLETE_WITH_BLOCKERS`

V2-2J, V2-3, token-age evidence work, and any implementation remain paused.

This lane produces a design specification only. It does not implement any
gate, mutate any database, fetch any source, generate memory, activate
retrieval, create paper decisions, authorize BUY/SELL/HOLD, open positions,
create trades, create paper trade audits, or create PnL.

No scoring, ranking, confidence percentage, or weighted logic is introduced.

## 2. Source Stack and Anchors

Documents read as source of truth:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2q-discovery-fair-chance-selection-rotation-audit.md`
- `docs/printer-v1-v2-2r-discovery-fair-chance-selection-rotation-design.md`
- `docs/printer-v1-v2-2t-cross-batch-selection-rotation-proof.md`

Source files inspected:

- `src/printer_v1/operator_cli/commands.py` — flat gate location
- `src/printer_v1/discovery/discovery.py` — storage layer (no gate)
- `src/printer_v1/discovery/classifier.py` — stateless classification
- `src/printer_v1/discovery/contracts.py` — enums and labels
- `src/printer_v1/discovery/selection_batch.py` — STNP/lifecycle/fingerprint helpers
- `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py` — lifecycle load helper

Anchors confirmed:

- V2-2Q audit: `b460ce1`
- V2-2R design: `a1257a0`
- V2-2T proof: `6d616cf`

## 3. Current Flat Gate — Location and Behavior

### 3.1 Where the gate lives

The existing-mint rejection is in `_select_discovery_candidates()` in
`src/printer_v1/operator_cli/commands.py` at line 1743:

```python
elif token_mint in existing_token_mints or pair_address in existing_pair_addresses:
    if token_mint in existing_token_mints and pair_address in existing_pair_addresses:
        reject_reason = "duplicate_existing_token_or_pair"
    elif token_mint in existing_token_mints:
        reject_reason = "duplicate_existing_token_mint"
    else:
        reject_reason = "duplicate_pair_address"
```

`existing_token_mints` and `existing_pair_addresses` are loaded at line 1826
via `_existing_token_pair_sets(connection)` — a read across `printer_tokens`
and `printer_pairs` before the source request loop runs.

This function is called from `build_discover_candidates_once_payload()` at
line 1906, which is the controlled discovery cycle command. The rejection
fires before any lifecycle, evidence-freshness, or STNP classification check
can run on the returning candidate.

### 3.2 The storage layer does not gate

`discovery.py`'s `upsert_discovered_token()` and `upsert_discovered_pair()`
use `SELECT id ... WHERE token_mint = ?` / `WHERE pair_address = ?` and
branch to `UPDATE` or `INSERT` — no rejection. `record_discovery_candidate()`
always inserts a new row. The discovery storage layer is gate-free; all
rejection happens in `_select_discovery_candidates()`.

### 3.3 Effect on STNP and lifecycle classification

`classify_same_token_new_pair()` (line 869 in `selection_batch.py`) only runs
inside `filter_within_response_duplicates()` (line 779), which fires on
within-response duplicates only. A candidate that hits the flat gate at
`_select_discovery_candidates()` never reaches `classify_same_token_new_pair()`
or `check_cooldown_archive_gate()`.

This is the design defect V2-2Q documented: migration, revival, and
distinct-evidence candidates are blocked before lifecycle-aware logic can
run on them.

## 4. Existing Helpers Available to the Reform

### 4.1 STNP classification

`classify_same_token_new_pair(classification, same_token_new_pair)` in
`selection_batch.py:869` returns `(ok, reason)`.

- `STNP_MIGRATION` → `ok=True` (allowed)
- `STNP_REVIVAL` → `ok=True` (allowed)
- `STNP_DISTINCT_EVIDENCE` → `ok=True` (allowed)
- `STNP_PAIR_DRIFT` → `ok=False, REJECTION_PAIR_DRIFT_UNRESOLVED`
- `STNP_DUPLICATE_RECYCLE` → `ok=False, REJECTION_PAIR_DUPLICATE`
- `None` or unrecognized → `ok=False, REJECTION_STNP_UNRESOLVED`

### 4.2 Migration channel set

`_migration_channel(source_channel)` in `selection_batch.py:336` returns
True when `source_channel` is one of:

```python
{"PUMPFUN_MIGRATION", "PUMPSWAP_GRADUATED", "PUMPSWAP_MIGRATION_POOL_REFERENCE"}
```

### 4.3 Lifecycle status load

`_load_mint_lifecycle_statuses(db_path, mints)` in
`lane_x6_discovery_selection_repair.py:344` queries
`printer_tracking_queue JOIN printer_tokens` and returns
`{mint → most_recent_queue_status}`.

`check_cooldown_archive_gate(lifecycle_state, cooldown_reopened, reopen_reason)`
in `selection_batch.py:896` returns `(ok, reason)`. States `COOLDOWN` and
`ARCHIVED` without explicit reopen → block.

`_ACTIVITY_REVIVING_LIFECYCLE_STATES = frozenset({"ARCHIVED", "COOLDOWN", "DEAD"})`
is defined in `selection_batch.py:319`. When the prior state is in this set
and the candidate shows any short-window activity, `derive_activity_bucket()`
returns `ACTIVITY_REVIVING`.

### 4.4 Evidence fingerprint helpers

`compute_evidence_identity_fingerprint(candidate)` in `selection_batch.py:1514`
returns:

```python
{
    "activity_bucket": derive_activity_bucket(candidate),
    "pair_age_context_label": candidate.get("pair_age_context_label"),
    "source_channel": candidate.get("source_channel"),
    "primary_bucket": candidate.get("primary_bucket"),
}
```

All four fields are categorical. No floats, no scores.

`fingerprint_change_is_meaningful(old_fp, new_fp)` in `selection_batch.py:1534`
returns True when:
- `activity_bucket` changed (any change), OR
- `source_channel` changed, OR
- `primary_bucket` crossed a group boundary (e.g., D1 → B1, not A1 → A2).

Returns False when only `pair_age_context_label` changed, or `primary_bucket`
changed within the same group.

### 4.5 What is already blocked and must stay blocked

The following rejections must be preserved unconditionally (Tier 1):

| Block | Existing mechanism |
|---|---|
| EXACT_DUPLICATE (same pair, same response) | `filter_within_response_duplicates()` |
| DUPLICATE_RECYCLE (same mint+pair, no evidence change) | Flat gate + fingerprint check to be added |
| STNP_UNRESOLVED | `classify_same_token_new_pair()` already returns `ok=False` |
| PAIR_DRIFT | `classify_same_token_new_pair(STNP_PAIR_DRIFT)` returns `ok=False` |
| `dirty` / `stale` / `unsafe` discovery classifications | `classify_discovery_candidate()` INSTANT_REJECT / IGNORE paths |

## 5. Tier 2 Pre-Check Design

### 5.1 Insertion point

The Tier 2 pre-check intercepts the flat gate in `_select_discovery_candidates()`
before line 1743. The implementation lane must add a new helper function,
called `_classify_returning_candidate()` (design placeholder name), that runs
only when `token_mint in existing_token_mints`.

Proposed call site (pseudocode, not implementation):

```
if token_mint in existing_token_mints:
    tier2 = _classify_returning_candidate(
        candidate, connection, token_mint, pair_address, existing_pair_addresses
    )
    if tier2.allows:
        # candidate proceeds to normal gates (STNP classification, etc.)
        pass
    else:
        reject_reason = tier2.rejection_reason
        # fall through to existing rejection path
```

### 5.2 MIGRATION pre-check

**Trigger condition**: `token_mint` is in `existing_token_mints` AND source
channel is a confirmed migration channel (`_migration_channel(source_channel)`
returns True) AND `pair_address` is NOT in `existing_pair_addresses`.

**What the check does**:

1. Confirms that `pair_address` is genuinely new — not in `printer_pairs`
   for any token. (Using the already-loaded `existing_pair_addresses` set.)
2. Labels the candidate `resurfacing_category = "MIGRATION"`.
3. Allows the candidate to proceed past the flat gate.
4. The candidate then reaches `classify_same_token_new_pair(STNP_MIGRATION, same_token_new_pair=True)`,
   which already returns `ok=True`.

**What blocks**: If `pair_address` IS in `existing_pair_addresses` even for
a migration-channel candidate, fall through to the flat-gate rejection. A
migration that re-uses an existing pair address is a DUPLICATE_RECYCLE, not a
new migration event.

**Evidence quality required**: source channel membership in the migration set
is sufficient. The migration channel itself is the evidence — it encodes that
a confirmed on-chain event (graduation, pool creation) occurred.

### 5.3 REVIVAL pre-check

**Trigger condition**: `token_mint` is in `existing_token_mints` AND the
token's most recent `queue_status` in `printer_tracking_queue` is `COOLDOWN`
or `ARCHIVED` AND `derive_activity_bucket(candidate, prior_lifecycle_state=queue_status)`
returns `ACTIVITY_REVIVING`.

**What the check does**:

1. Loads lifecycle status for `token_mint` from `printer_tracking_queue`
   (one read per returning mint, using `_load_mint_lifecycle_statuses()`-style query).
2. If status not in `{"COOLDOWN", "ARCHIVED"}` → not a REVIVAL candidate,
   fall through to flat gate.
3. Calls `derive_activity_bucket(candidate, prior_lifecycle_state=queue_status)`.
4. If result is `ACTIVITY_REVIVING` → labels the candidate
   `resurfacing_category = "REVIVAL"` and allows it past the flat gate.
5. The candidate must then pass the evidence-freshness gate (Section 5.5).

**What blocks**: If queue status is `COOLDOWN`/`ARCHIVED` but activity is
NOT `ACTIVITY_REVIVING` (still `ACTIVITY_DEAD` or `ACTIVITY_LOW` without
short-window signal) → flat gate rejection preserved. A dead token in archive
that remains dead is a DUPLICATE_RECYCLE, not a REVIVAL.

**Evidence quality required**: any non-zero short-window activity
(`vol5m > 0` or `txns5m > 0` or `vol1h > 0` or `txns1h > 0`) when prior
lifecycle state is ARCHIVED or COOLDOWN. This is the existing `derive_activity_bucket()`
criterion for `ACTIVITY_REVIVING`.

### 5.4 DISTINCT_NEW_EVIDENCE pre-check

**Trigger condition**: `token_mint` is in `existing_token_mints` AND
`pair_address` is in `existing_pair_addresses` (same mint, same pair) AND
neither MIGRATION nor REVIVAL conditions apply.

**What the check does**:

1. Queries `printer_discovery_candidates` for the most recent row with
   matching `token_id` and `pair_id` to retrieve `normalized_candidate_payload_json`.
2. Parses the historical candidate and calls
   `compute_evidence_identity_fingerprint(historical_candidate)`.
3. Calls `compute_evidence_identity_fingerprint(current_candidate)`.
4. Calls `fingerprint_change_is_meaningful(old_fp, new_fp)`.
5. If True → labels the candidate `resurfacing_category = "DISTINCT_NEW_EVIDENCE"`
   and allows it past the flat gate.
6. If False → flat gate rejection preserved (`duplicate_existing_token_or_pair`).

**Evidence quality required**: the fingerprint-change rule must satisfy
`fingerprint_change_is_meaningful()`. Specifically, one of:
- `activity_bucket` changed (e.g., DEAD → ACTIVITY_HIGH or ACTIVITY_MEDIUM).
- `source_channel` changed (new provider narrative).
- `primary_bucket` crossed a group boundary (e.g., D1 → B1).

A token whose only change is `pair_age_context_label` aging naturally is NOT
DISTINCT_NEW_EVIDENCE. A token where only the primary bucket changed within
the same group (A1 → A2) is NOT DISTINCT_NEW_EVIDENCE.

**Null-safety**: if the most recent `normalized_candidate_payload_json` is
absent or unparseable, the check must fail safe → reject (same behavior as
flat gate). Missing historical data is not grounds for allowance.

**Note on `assign_bucket()` dependency**: `compute_evidence_identity_fingerprint()`
reads `candidate.get("primary_bucket")`, which must be pre-assigned by the
caller. In the current `_select_discovery_candidates()` flow, `assign_bucket()`
is called after the gate check. The implementation lane must call `assign_bucket(candidate)`
before the DISTINCT_NEW_EVIDENCE check, or derive `primary_bucket` inline.

### 5.5 Evidence-Freshness Gate (after Tier 2 allowance)

For REVIVAL and DISTINCT_NEW_EVIDENCE candidates that pass the Tier 2
pre-check, the implementation lane must also apply the evidence-freshness
gate before final admission:

1. Compute the new candidate's fingerprint.
2. Compare with the most recent fingerprint for this mint/pair from
   `printer_discovery_candidates`.
3. If not meaningfully different → reject with
   `resurfacing_category = "DUPLICATE_RECYCLE"` (the Tier 2 check was
   insufficient to confirm distinct evidence).
4. If meaningfully different → allow.

For MIGRATION candidates this gate is optional at discovery time: the new
pair address itself is the evidence of a distinct event. The evidence-freshness
gate is nonetheless available for the implementation lane to apply as a
defense-in-depth check on migration candidates.

## 6. Hard Blocks Preserved (Tier 1 Unchanged)

The following blocks are unconditional and must not be relaxed by the
Tier 2 reform:

| Block | Reason |
|---|---|
| EXACT_DUPLICATE | Same pair in same response — not a resurfacing event |
| DUPLICATE_RECYCLE | Same mint+pair, no evidence change — filter in Tier 2 Section 5.4 |
| STNP_UNRESOLVED | Missing migration classification — unsafe ambiguity |
| PAIR_DRIFT | Routing artifact, not a real new event |
| `dirty` candidates | INSTANT_REJECT_MEMORY_ONLY classification |
| `stale` source data | `source_status` gate upstream of the discovery gate |
| `unsafe` classification | IGNORE classification, missing token_mint or pair_address |

## 7. Selection-Cooldown Interaction

The Tier 2 pre-check is a **discovery persistence gate** only. It does not
waive or bypass the cross-batch selection cooldown (V2-2R Rules 1 and 2,
implemented in V2-2S).

A candidate allowed past the flat gate by Tier 2 is still subject to:

- `check_token_selection_cooldown()` — 3-batch token cooldown
- `check_pair_selection_cooldown()` — 3-batch pair cooldown
- `apply_selection_cooldown_gates()` — token check first, pair check second

**MIGRATION exception**: V2-2R Rule 1 specifies a token-level cooldown waiver
for MIGRATION candidates (new pair address, confirmed migration channel, and
fingerprint differs from last selected evidence). The implementation lane must
wire this waiver into the cooldown check when `resurfacing_category = "MIGRATION"`.
The pair-level cooldown (Rule 2) is not waived: for a genuine migration the
pair address is new and has no cooldown history — pair cooldown will naturally
return `ok=True`.

**REVIVAL exception**: V2-2R Rule 1 specifies a token-level cooldown waiver
for REVIVAL candidates when `ACTIVITY_REVIVING` is confirmed AND
`cooldown_reopened=True` with explicit reopen reason. The implementation lane
must wire this waiver as well.

Tier 2 allowance alone does NOT constitute a cooldown waiver. The waiver
requires the additional conditions specified in V2-2R Rule 1 (explicit
migration classification or revival evidence on the batch item).

## 8. Storage and Schema Needs

### 8.1 Discovery-side — no new migration needed

The Tier 2 pre-check reads from existing tables:

| Query | Table | Purpose |
|---|---|---|
| Latest lifecycle status | `printer_tracking_queue JOIN printer_tokens` | REVIVAL check |
| Last historical fingerprint | `printer_discovery_candidates` (most recent row for mint+pair) | DISTINCT_NEW_EVIDENCE check |
| Existing pair addresses per mint | `printer_pairs JOIN printer_tokens` | MIGRATION new-pair check |

These are all reads on existing tables (V2-2R Section 8.2 confirmed this).

The implementation lane must add DB reads inside `_select_discovery_candidates()`
or a refactored pre-check helper. These reads add latency to the discovery
cycle. The implementation design should batch-load lifecycle statuses for all
returning mints before the main loop, rather than per-candidate round-trips.

### 8.2 Selection-side — existing rotation state table sufficient

`printer_selection_rotation_state` (migration `026_selection_rotation_state.sql`,
V2-2S) stores `last_evidence_fingerprint_json` per `(token_mint, pair_address)`.
For the DISTINCT_NEW_EVIDENCE check this column is a useful secondary source
(last fingerprint at selection time, not at discovery time). However, the
discovery gate must not depend on this table being populated — the table may be
empty if no selection batches have run. The primary source for DISTINCT_NEW_EVIDENCE
is `printer_discovery_candidates`.

### 8.3 Reporting fields — new per-candidate annotations

The implementation lane must add the following fields to the rejected/accepted
candidate dicts returned by `_select_discovery_candidates()`:

| Field | Type | Values |
|---|---|---|
| `resurfacing_category` | `str \| None` | `"MIGRATION"`, `"REVIVAL"`, `"DISTINCT_NEW_EVIDENCE"`, or `None` |
| `resurfacing_reason` | `str \| None` | human-readable reason for Tier 2 decision |
| `tier2_gate_outcome` | `str` | `"ALLOWED"`, `"BLOCKED"`, `"NOT_APPLICABLE"` |
| `prior_lifecycle_state` | `str \| None` | tracking-queue status at discovery time (for REVIVAL) |
| `fingerprint_change_type` | `str \| None` | which fingerprint field changed (for DISTINCT_NEW_EVIDENCE) |

These fields are informational for operator reporting. They must never become
scoring inputs, selection criteria, or paper-decision triggers.

## 9. Proof and Test Plan

The implementation lane (a future V2-2V or equivalent) must run the following
proofs before declaring IMPL_COMPLETE:

### 9.1 MIGRATION proof

**Setup**: seed `printer_tokens` with MINT_A, seed `printer_pairs` with
PAIR_OLD for MINT_A, seed `printer_tracking_queue` with MINT_A = QUEUED.
Present MINT_A + PAIR_NEW (not in `printer_pairs`) with
`source_channel = "PUMPFUN_MIGRATION"`.

**Required proof checks**:
1. MINT_A/PAIR_NEW is NOT rejected by the flat gate.
2. `resurfacing_category = "MIGRATION"` is set on the accepted candidate.
3. `classify_same_token_new_pair(STNP_MIGRATION, same_token_new_pair=True)`
   runs and returns `ok=True`.
4. MINT_A/PAIR_OLD presented with same migration channel IS rejected (pair exists).
5. MINT_A/PAIR_NEW with a non-migration channel (`"DEXSCREENER_SEARCH"`) is
   rejected by the flat gate (no Tier 2 allowance without migration channel).

### 9.2 REVIVAL proof

**Setup**: seed MINT_B in `printer_tracking_queue` with `queue_status = "ARCHIVED"`.
Present MINT_B + PAIR_B with `vol5m = 500, txns5m = 15` (non-zero activity).

**Required proof checks**:
1. MINT_B/PAIR_B is NOT rejected by the flat gate.
2. `resurfacing_category = "REVIVAL"` is set.
3. `prior_lifecycle_state = "ARCHIVED"` is recorded.
4. MINT_B presented with `vol5m = 0, txns5m = 0, vol1h = 0, txns1h = 0`
   (dead activity) IS rejected by the flat gate.
5. MINT_B with `queue_status = "QUEUED"` (not archived) IS rejected by the
   flat gate (REVIVAL requires COOLDOWN/ARCHIVED state).

### 9.3 DISTINCT_NEW_EVIDENCE proof

**Setup**: seed MINT_C/PAIR_C in `printer_discovery_candidates` with historical
fingerprint `{activity_bucket: "ACTIVITY_DEAD", primary_bucket: "D1", ...}`.
Present MINT_C + PAIR_C with current data showing
`activity_bucket = "ACTIVITY_HIGH"` (meaningful change).

**Required proof checks**:
1. MINT_C/PAIR_C is NOT rejected by the flat gate.
2. `resurfacing_category = "DISTINCT_NEW_EVIDENCE"` is set.
3. MINT_C/PAIR_C with only `pair_age_context_label` changed IS rejected
   (not meaningful).
4. MINT_C/PAIR_C with primary bucket changing within Group A (A1 → A2) IS
   rejected (same group, not meaningful).
5. MINT_C/PAIR_C with missing or unparseable historical candidate IS rejected
   (null-safety).

### 9.4 Tier 1 preservation proof

**Required proof checks**:
1. A mint+pair with no evidence change is rejected as DUPLICATE_RECYCLE.
2. An STNP_UNRESOLVED case (same mint, different pair, non-migration channel)
   is rejected with REJECTION_STNP_UNRESOLVED.
3. A PAIR_DRIFT case remains rejected.
4. An INSTANT_REJECT classification candidate is rejected before Tier 2 runs.

### 9.5 Cooldown-interaction proof

**Required proof checks**:
1. A MIGRATION candidate that passes Tier 2 is still subject to token-level
   cooldown (Rules 1/2) when no cooldown waiver conditions are met.
2. A MIGRATION candidate with confirmed waiver conditions (new pair + migration
   channel + fingerprint differs from last selected) is NOT blocked by
   token-level cooldown.
3. Row-delta lock: no `printer_paper_decisions`, `printer_paper_positions`,
   `printer_paper_trade_events`, `printer_memory_windows`, or
   `printer_episodes` rows are created during the proof.

### 9.6 Required test suites after implementation

| Suite | Reason |
|---|---|
| `tests/test_post_rc_controlled_discovery_cycle.py` | Core discovery cycle |
| `tests/test_v2_2s_selection_cooldown.py` | Cooldown interaction unchanged |
| `tests/test_v2_2c_selection_batch.py` | Selection batch paths |
| `tests/test_v2_2p_pair_age_context.py` | Pair-age metadata unchanged |
| `tests/test_v2_2m_audit_only_handoff.py` | Audit-only pool unchanged |
| New proof test file | All 9.1–9.5 checks above |

All 370 (+ new test count) must pass.

## 10. Design Blockers

The following must be resolved before the implementation lane can begin:

### B1: `assign_bucket()` must precede DISTINCT_NEW_EVIDENCE check

`compute_evidence_identity_fingerprint()` reads `candidate.get("primary_bucket")`.
In the current `_select_discovery_candidates()` flow, `assign_bucket()` is
called in the audit-only capture path after the gate check fires. The
implementation lane must ensure `primary_bucket` is populated before the
DISTINCT_NEW_EVIDENCE fingerprint comparison. This requires either:
- Calling `assign_bucket()` before the Tier 2 check, OR
- Passing a pre-computed fingerprint that derives `primary_bucket` inline.

Either approach is valid. The implementation lane must choose and document
the approach without introducing a second `assign_bucket()` call on the
happy path.

### B2: Batch-level lifecycle pre-load required

Loading lifecycle status per-candidate inside the main loop would issue one
DB round-trip per returning mint. The implementation lane must batch-load
lifecycle statuses for all returning mints before the loop, using a
`_load_mint_lifecycle_statuses()`-style pre-aggregation. This is the existing
pattern in `lane_x6_discovery_selection_repair.py`.

### B3: `token_age_seconds` remains unavailable

`derive_activity_bucket()` does not require `token_age_seconds`. The REVIVAL
and MIGRATION paths in this design are not blocked by the token-age gap.
However, `assign_bucket()` has an A3 gate (`_tok_age_known`) that remains
inactive. The DISTINCT_NEW_EVIDENCE proof candidates that rely on bucket
group changes (e.g., A3 → B1) cannot be fully exercised until a T1/T2/T3
source is approved. Proof items 9.3.3 and 9.3.4 must use group-crossing
changes that do not require A3 (e.g., D1 → B1, using only activity/volume
fields).

### B4: `cooldown_reopened` wire-up out of scope for discovery gate

V2-2R Rule 1 waiver for REVIVAL requires `cooldown_reopened=True` on the
batch item. The discovery gate reform (Tier 2) only controls whether the
candidate reaches the tracking queue. The `cooldown_reopened` flag lives in
the selection batch assembly path. The implementation lane for the discovery
gate reform must document the handoff point: the Tier 2 REVIVAL pre-check
allows discovery; the selection batch must separately set `cooldown_reopened`
for the cooldown waiver to apply. These are distinct operations in distinct
lanes.

### B5: No live runtime

`apply_selection_cooldown_gates()` is a callable helper; no live runtime or
scheduler calls it in the current paper-trading-only scope. Tier 2 allowance
affects the discovery path only. The selection gate (Rules 1/2) has no live
caller today. The implementation lane must document this gap.

## 11. What the Reform Does Not Change

- No source-fetching path.
- No memory generation, retrieval, paper decision, BUY/SELL/HOLD.
- No position, trade, audit, or PnL path.
- No scoring, ranking, confidence, or weighted logic.
- No embeddings or vectors.
- `pair_age_seconds` not written to `token_age_seconds`.
- `assign_bucket()` A3 gate (`_tok_age_known`) unchanged.
- `filter_within_response_duplicates()` within-response safety unchanged.
- `classify_same_token_new_pair()` gate logic unchanged.
- `check_cooldown_archive_gate()` logic unchanged.
- All Tier 1 hard blocks preserved.
- V2-2J, V2-3, and source-expansion work remain paused.

## 12. Git Checks

- `git diff --check`: no tracked file changes (design doc only).
- `git status --short`: 1 new untracked file (this doc in `docs/`).
- `git diff --stat`: no modified tracked files.
- `git diff --name-only`: no modified tracked files.

## 13. Safety Confirmations

- No source-fetching path called.
- No implementation of Tier 2 gate created.
- No database mutations performed.
- No migration file created.
- No scheduler or runtime path changed.
- No memory or memory-window path changed.
- No retrieval path changed.
- No paper-decision path changed.
- No BUY/SELL/HOLD path changed.
- No position, trade, audit, or PnL path changed.
- No scoring, ranking, confidence, or weighted logic introduced.
- No embeddings or vectors introduced.
- V2-2J, V2-3, token-age evidence work remain paused.
- Live DB untouched.

## 14. Design Verdict

`DESIGN_COMPLETE_WITH_BLOCKERS`

The two-tier design is fully specified. All three Tier 2 resurfacing categories
(MIGRATION, REVIVAL, DISTINCT_NEW_EVIDENCE) have defined trigger conditions,
evidence-quality requirements, rejection fall-throughs, and proof plans.

Five design blockers (B1–B5) must be resolved by the implementation lane
before work begins. None of the blockers prevent the design from being fully
specified; they are pre-conditions for safe implementation.

The reform preserves all Tier 1 hard blocks and does not waive or bypass the
cross-batch selection cooldown. Tier 2 allowance at the discovery gate is
decoupled from cooldown waiver at the selection gate.

## 15. Next Recommended Lane

The V2-2U design specifies the Tier 2 pre-check for discovery persistence
gate reform. The active V2 roadmap continuation is:

- **V2-2V** — implementation of the Tier 2 pre-check in
  `_select_discovery_candidates()` in `commands.py`, with proof tests for all
  five proof groups (Sections 9.1–9.5) and all six required test suites passing.

V2-2J, V2-3, token-age evidence work, and source-expansion work remain paused
and must not be started without explicit operator instruction.
