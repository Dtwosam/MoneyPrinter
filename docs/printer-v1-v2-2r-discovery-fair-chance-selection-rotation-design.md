# Printer V1 V2-2R Discovery Fair-Chance / Selection Rotation Design

## 1. Status

**Lane:** V2-2R - Discovery Fair-Chance / Selection Rotation Design
**Task type:** Design-only
**Verdict:** `DESIGN_COMPLETE_WITH_BLOCKERS`

V2-2J and V2-3 remain paused. V2-2Q remains paused.

This lane produces a design specification only. It does not implement any
rotation gate, mutate any database, fetch any source, generate memory, activate
retrieval, create paper decisions, authorize BUY/SELL/HOLD, open positions,
create trades, create paper trade audits, or create PnL.

No scoring, ranking, confidence percentage, or weighted logic is introduced.

## 2. Source Stack and Anchors

Documents read as source of truth:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2q-discovery-fair-chance-selection-rotation-audit.md`
- `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md`

Source files inspected:

- `src/printer_v1/discovery/selection_batch.py`
- `src/printer_v1/operator_cli/commands.py`

Anchors confirmed:

- V2-2P.3 verification: `be70309`
- V2-2Q audit: `b460ce1`

## 3. Current Blocker Summary

V2-2Q identified a central contradiction in the current system:

**Discovery is too restrictive**: the normal persistence gate rejects any
candidate whose `token_mint` or `pair_address` already exists in
`printer_discovery_candidates`. This blocks legitimate migration, revival, and
distinct-evidence resurfacing permanently, not just temporarily.

**Selection is too permissive**: no current gate queries recent selection-batch
history to prevent the same token or pair from being selected again in the
immediately following batch. The selection quota rules prevent duplicates within
one batch, but cross-batch repetition is not prevented.

These two controls contradict each other:

- Discovery excludes too much (prevents useful re-entry).
- Selection excludes too little (permits repeated re-selection).

Neither side provides a complete, evidence-aware, time-aware rotation policy.

Additional structural blockers from V2-2Q:

- `printer_selection_batches` and `printer_selection_batch_items` are absent
  from the live persistent database. Cross-batch rotation cannot query history
  until these tables are present.
- All 15 persistent tracking rows are `QUEUED`. No cooldown, archive, or reopen
  population has been operationally exercised. Lifecycle rotation controls exist
  as code but are not proven in production.
- Source/channel concentration: 60% DexScreener, 40% GeckoTerminal. 53.3% of
  historical rows lack an explicit source channel. Fixed page-one endpoints can
  repeatedly return the same provider-defined token set.

## 4. Duplicate and Resurfacing Taxonomy

Seven categories govern how a returning candidate should be treated. The
taxonomy resolves the ambiguity in the current "block all existing mints" rule.

### 4.1 EXACT_DUPLICATE

**Definition**: The same `pair_address` appears more than once within a single
source response.

**Current handling**: safely rejected by `filter_within_response_duplicates()`
with reason `REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE`.

**V2-2R action**: preserve current behavior. No change needed.

### 4.2 DUPLICATE_RECYCLE

**Definition**: A candidate whose `token_mint` and `pair_address` both already
exist in persistent discovery with no meaningful change in evidence since the
last record.

**Current handling**: blocked at the normal discovery persistence gate
(existing mint or pair found → reject).

**V2-2R action**: preserve blocking. A DUPLICATE_RECYCLE with identical or
trivially changed evidence must not re-enter discovery. The evidence-freshness
gate in Section 6 determines whether a returning candidate qualifies as
DUPLICATE_RECYCLE or DISTINCT_NEW_EVIDENCE.

### 4.3 STNP_UNRESOLVED

**Definition**: Same `token_mint`, different `pair_address`, but the source
channel does not provide enough information to classify the reason.

**Current handling**: rejected with `REJECTION_STNP_UNRESOLVED` by
`classify_same_token_new_pair()`.

**V2-2R action**: preserve blocking. Unresolved STNP is unsafe by definition.

### 4.4 MIGRATION

**Definition**: Same `token_mint`, different `pair_address`, source channel is
in the confirmed migration set (`PUMPFUN_MIGRATION`, `PUMPSWAP_GRADUATED`,
`PUMPSWAP_MIGRATION_POOL_REFERENCE`).

**Current handling**: `classify_same_token_new_pair(STNP_MIGRATION)` returns
`ok=True`. However, V2-2Q found that the normal discovery persistence gate can
block the existing mint before the STNP classification runs. This means
migration candidates may be blocked before they reach the classification helper.

**V2-2R action**: the implementation lane must add a lifecycle-aware pre-check
before the existing-mint rejection. When the source channel is in the migration
set and the pair address is new, the candidate must reach STNP classification
rather than being blocked by the generic existing-mint gate. The new pair
address must never have been seen before (not in `printer_pairs` for this mint).

### 4.5 REVIVAL

**Definition**: Same `token_mint`, same or different `pair_address`, token is
in `COOLDOWN` or `ARCHIVED` state in the tracking queue, and current data shows
renewed activity (`derive_activity_bucket()` returns `ACTIVITY_REVIVING` when
called with `prior_lifecycle_state` set to `ARCHIVED` or `COOLDOWN`).

**Current handling**: lifecycle helpers exist for cooldown, archive, and
explicit reopen. The Lane X6 repair path excludes candidates whose latest state
is COOLDOWN or ARCHIVED unless an explicit reopen is present. However, the
normal discovery persistence gate rejects existing mints before a
lifecycle-aware path can operate.

**V2-2R action**: the implementation lane must insert a lifecycle-state check
before the existing-mint rejection. A token in COOLDOWN or ARCHIVED with a
verified `ACTIVITY_REVIVING` activity bucket is a REVIVAL candidate, not a
DUPLICATE_RECYCLE. It must reach the evidence-freshness gate before a
re-admission decision is made.

### 4.6 DISTINCT_NEW_EVIDENCE

**Definition**: Same `token_mint` and `pair_address`, but the evidence identity
fingerprint (see Section 6.2) differs meaningfully from the last time this
token was selected or persisted. For example: a token previously dead
(`ACTIVITY_DEAD`) is now showing `ACTIVITY_HIGH` on the same pair.

**Current handling**: blocked at the existing-mint or existing-pair discovery
gate. No evidence comparison exists.

**V2-2R action**: a returning candidate whose evidence identity fingerprint
differs from the last persisted fingerprint for that mint/pair is
DISTINCT_NEW_EVIDENCE, not DUPLICATE_RECYCLE. The evidence-freshness gate
(Section 6.2) must be applied to determine whether the change is meaningful
enough to allow re-admission.

### 4.7 PAIR_DRIFT

**Definition**: Same `token_mint`, different `pair_address`, where the
difference is a provider routing quirk or liquidity pool alias rather than a
genuine migration or new trading venue.

**Current handling**: classified as `STNP_PAIR_DRIFT` and rejected with
`REJECTION_PAIR_DRIFT_UNRESOLVED` by `classify_same_token_new_pair()`.

**V2-2R action**: preserve blocking. Pair drift is not a legitimate resurfacing
event.

### 4.8 Taxonomy Decision Table

| Category | Same mint | Same pair | Action |
|---|---|---|---|
| EXACT_DUPLICATE | — | Yes (within response) | Block (existing gate) |
| DUPLICATE_RECYCLE | Yes | Yes | Block (no evidence change) |
| STNP_UNRESOLVED | Yes | No | Block (existing gate) |
| MIGRATION | Yes | No (migration channel) | Conditional allow |
| REVIVAL | Yes | Same or new | Conditional allow |
| DISTINCT_NEW_EVIDENCE | Yes | Yes | Conditional allow |
| PAIR_DRIFT | Yes | No (drift) | Block (existing gate) |

## 5. Fair-Chance Discovery Rules

### 5.1 Two-Tier Discovery Persistence Policy

The current discovery persistence gate is a single flat check: if mint or pair
exists in the DB, reject. V2-2R replaces this with a two-tier policy.

**Tier 1: Unconditional blocking (unchanged)**

Apply unconditional blocking for:
- Exact pair duplicate within the same source response.
- STNP unresolved (no source-channel migration evidence).
- Pair drift.
- Duplicate recycle (same mint, same pair, no evidence change).

These cases require no new implementation; existing gates already handle them.

**Tier 2: Lifecycle-aware conditional allowance (new)**

Before applying the existing-mint rejection, check:

1. Is the returning mint's lifecycle state `COOLDOWN` or `ARCHIVED` in the
   tracking queue?
   - If yes → evaluate REVIVAL path (Section 4.5).
   - If the revival criteria pass → allow candidate to reach the
     evidence-freshness gate.

2. Is the returning candidate's source channel a confirmed migration channel,
   and is the pair address new (not in `printer_pairs` for this mint)?
   - If yes → evaluate MIGRATION path (Section 4.4).
   - If the migration criteria pass → allow candidate to reach the STNP
     classification gate, which already handles it.

3. Is the returning candidate the same mint and same pair, but evidence identity
   fingerprint meaningfully different from the last persisted record?
   - If yes → evaluate DISTINCT_NEW_EVIDENCE path (Section 4.6).
   - If the evidence-freshness gate passes → allow re-admission.

If none of the Tier 2 checks applies, fall through to the existing-mint or
existing-pair rejection (Tier 1 behavior preserved).

### 5.2 Evidence Identity Fingerprint

An evidence identity fingerprint is a lightweight categorical description of
the token's state at discovery time. It is not a score.

Fingerprint fields (all categorical, no floats):

| Field | Derivation |
|---|---|
| `activity_bucket` | `derive_activity_bucket(candidate)` — HIGH/MEDIUM/LOW/DEAD/REVIVING/UNKNOWN |
| `pair_age_context_label` | Already computed in `normalize_candidate()` by V2-2P |
| `source_channel` | `candidate.get("source_channel")` — the discovery channel |
| `primary_bucket` | `assign_bucket(candidate)` result — the categorical bucket |

A fingerprint change is meaningful when at least one of the following differs
from the last persisted fingerprint for this mint/pair:

- `activity_bucket` changed (e.g., DEAD → REVIVING or REVIVING → HIGH).
- `primary_bucket` changed across group boundaries (e.g., D1 → B1, not A1 → A2).
- `source_channel` changed (different narrative context from a different provider).

A fingerprint change is not meaningful (still DUPLICATE_RECYCLE) when:

- Only `pair_age_context_label` changed (pair age grows over time naturally;
  this is not evidence of a new event).
- `primary_bucket` changed within the same group (e.g., A1 → A2 within Group A).

The evidence identity fingerprint is stored alongside selection batch items
to support future freshness comparison without re-computing from scratch.

### 5.3 Source/Query Coverage Improvement (Future Scope)

This note is forward-looking only. No implementation is permitted in V2-2R.

The current discovery endpoints use fixed page-one GeckoTerminal requests and a
stable default DexScreener search query. A future source-expansion lane (after
an explicit operator approval) could rotate query terms or endpoints to improve
candidate universe breadth without increasing API request count. Any such lane
must route all requests through the Source Governor. Paid APIs and unrestricted
endpoint scraping remain forbidden.

## 6. Selection Rotation Rules

Six categorical rotation rules govern which candidates may enter a new
selection batch.

### Rule 1: Token-Level Cooldown (Cross-Batch)

A `token_mint` that appears in any recent selection batch as `SELECTED` cannot
be re-selected within the immediately preceding **3 batches**.

Cooldown window is expressed in batch count, not calendar time. Batch
frequency is operator-controlled and may be irregular. Batch count is a stable,
auditable unit.

**Gate check**: query `printer_selection_batch_items` for the most recent 3
batch IDs containing this `token_mint` with `item_status = SELECTED`. If found,
reject with reason `REJECTION_TOKEN_SELECTION_COOLDOWN` (new rejection constant).

**Waiver condition**: token-level cooldown may be waived when:
- The returning candidate is classified as MIGRATION (new pair address, valid
  migration channel), **and** an explicit migration reason is provided, **and**
  the evidence identity fingerprint on the new pair differs from the last
  selected evidence fingerprint for this mint.
- The returning candidate is classified as REVIVAL with `ACTIVITY_REVIVING`
  activity bucket and `cooldown_reopened=True` with explicit reopen reason.

Cooldown waiver does not bypass the pair-level cooldown (Rule 2).

### Rule 2: Pair-Level Cooldown (Cross-Batch)

Same as Rule 1, but keyed by `pair_address` rather than `token_mint`.

Token cooldown and pair cooldown are independent gates:
- A token returning on a new pair address (MIGRATION) is subject to
  token-level cooldown (Rule 1) but not pair-level cooldown (the new pair has
  no history).
- A token selected on the same pair is subject to both token and pair cooldown.

Pair-level cooldown window: same 3-batch window as Rule 1.

New rejection constant: `REJECTION_PAIR_SELECTION_COOLDOWN`.

### Rule 3: Source/Channel Exposure Cap (Cross-Batch)

No single `source_name` should contribute more than **60%** of selected tokens
across the most recent **3 batches**.

This is a **soft warning**, not a hard block. Hard blocking is unsafe with only
two READY sources (DexScreener and GeckoTerminal); hard blocking could starve
selection entirely if one source temporarily produces no qualifying candidates.

Implementation: query `printer_selection_batch_items` for the 3 most recent
batches, count `source_name` distribution among SELECTED items, and emit a
warning into the payload's `rotation_exposure_warnings` field if any source
exceeds 60%. The warning is observable by the operator but does not prevent the
batch from assembling.

### Rule 4: Category Exposure Cap (Cross-Batch)

No single `primary_bucket` should occupy more than **50%** of selected slots
across the most recent **3 batches**.

Also a **soft warning** (same reason as Rule 3: hard blocking could conflict
with quota gates that require specific bucket coverage).

Implementation: same query as Rule 3, count bucket distribution, emit into
`rotation_exposure_warnings`.

### Rule 5: Evidence Freshness Gate (Per-Token at Selection Time)

Before including a token in a new selection batch:

1. Compute the evidence identity fingerprint for the current candidate
   (Section 5.2).
2. Look up the last selected evidence identity fingerprint for this mint in
   `printer_selection_rotation_state` (new table, Section 8).
3. If the fingerprints are identical → token is not fresh. The token is
   eligible for reselection only after the cooldown window (Rule 1) has fully
   elapsed. If cooldown has elapsed but fingerprint is unchanged, the token may
   be reselected (dead or slow tokens are still useful for negative-learning
   coverage) with an added note `STALE_EVIDENCE_RESELECT` in the batch item's
   `lane_rationale` field.
4. If the fingerprints differ meaningfully (per Section 5.2 criteria) → token
   qualifies for cooldown waiver consideration (Rule 1 waiver conditions still
   apply).

This rule prevents zero-change recycling of identical stale evidence even after
the cooldown window has technically elapsed.

### Rule 6: Fair-Aging for Eligible Candidates

**Problem**: newest-first ordering in the Lane X6 repair path can starve
eligible candidates that consistently appear below the per-batch selection cap.

**Rule**: among all candidates that pass cooldown gates (Rules 1 and 2) and
evidence-freshness gate (Rule 5), candidates not selected in any of the
**most recent 6 batches** receive priority consideration for at least 1
slot per batch.

This is a categorical ordering gate, not a score. The rule asks: "Has this
candidate been given a fair chance recently?" If not in 6 batches → eligible
for the fair-aging slot.

**Constraints**:
- Maximum **1 fair-aging slot per batch** (prevents the mechanism from
  distorting the overall batch composition).
- Fair-aging slot candidates still pass all other categorical gates
  (cooldown, evidence freshness, quota).
- If multiple candidates are fair-aging eligible, tie-break by
  discovery_candidate_id ascending (stable, deterministic, no scores).
- Fair-aging slot does not waive Group F corpus requirement or the
  A1 winner cap.

## 7. Lifecycle Integration

### 7.1 Cooldown State

- COOLDOWN in the tracking queue blocks normal selection (existing gate
  via `check_cooldown_archive_gate()`, preserved).
- A reopened COOLDOWN token (`cooldown_reopened=True`) clears the lifecycle
  gate but must still pass the cross-batch selection cooldown (Rule 1/2) and
  evidence-freshness gate (Rule 5).
- Lifecycle reopen and cross-batch selection cooldown are independent gates.
  Passing one does not waive the other.

### 7.2 Archive State

- ARCHIVED in the tracking queue blocks normal selection (existing gate
  via `check_cooldown_archive_gate()`, preserved).
- Revival evidence (`ACTIVITY_REVIVING` when prior state was ARCHIVED) can
  trigger an explicit operator-approved reopen request.
- An ARCHIVED + reopened token with revival evidence passes the lifecycle gate
  and is then evaluated for evidence-freshness. If the revival itself
  constitutes a meaningful fingerprint change, the token-level cooldown may be
  waived (Rule 1 waiver conditions).

### 7.3 Revival Path

1. Token is in ARCHIVED or COOLDOWN lifecycle state.
2. New discovery data shows renewed activity: `derive_activity_bucket()` with
   `prior_lifecycle_state=ARCHIVED` or `COOLDOWN` returns `ACTIVITY_REVIVING`.
3. Operator or automated path sets `cooldown_reopened=True` with a reopen
   reason.
4. Lifecycle gate passes.
5. Evidence freshness gate evaluates: `activity_bucket` changed (DEAD → REVIVING)
   → meaningful change → cooldown waiver applies.
6. Token enters selection pool as a REVIVAL candidate (assigns `BUCKET_D2` in
   `assign_bucket()` when caller provides `cooldown_reopened=True`).

### 7.4 Migration Path

1. Token already exists in `printer_discovery_candidates`.
2. New source response carries a migration-channel source channel.
3. New `pair_address` has not been seen before for this mint.
4. Pre-check before existing-mint rejection: source channel is migration
   channel → route to STNP classification.
5. `classify_same_token_new_pair(STNP_MIGRATION)` returns `ok=True`.
6. New pair enters discovery as a MIGRATION candidate (`BUCKET_D3`).
7. Token-level cooldown (Rule 1) is waived because:
   - Migration is the evidence identity change itself.
   - Explicit `same_token_new_pair_classification=STNP_MIGRATION` reason is
     on the batch item.
8. Pair-level cooldown (Rule 2) does not apply because the new pair address
   has no selection history.

### 7.5 WATCH_ONLY in Rotation

- WATCH_ONLY tokens can be selected for audit-only representation (existing
  quota rule: 6+ item batches require at least 1 WATCH_ONLY).
- All six rotation rules apply to WATCH_ONLY tokens.
- WATCH_ONLY tokens are never silently promoted to TRACK_FAST or TRACK_NORMAL
  (existing gate via `check_watch_only_promotion_gate()`, preserved).
- A WATCH_ONLY token that is also revival-eligible may be promoted through the
  normal promotion criteria (new discovery classification sets
  `discovery_action` accordingly); the WATCH_ONLY silent-promotion gate checks
  `discovery_action`, not the lifecycle path.

### 7.6 D1 Dead Tokens in Rotation

- D1 dead tokens are selected for negative-learning coverage (existing
  quota rule: 6+ item batches require at least 1 D1).
- All six rotation rules apply to D1 tokens.
- A dead token that remains dead has minimal evidence-identity change. After
  the cooldown window (Rule 1), it may be reselected. Rule 5 will flag the
  fingerprint as unchanged and add `STALE_EVIDENCE_RESELECT` to the batch
  item, which is correct and useful: the dead-token state is itself the
  negative-learning signal and remains valid.
- Maximum D1 reselection is still constrained by Rule 1 (3-batch cooldown).
  A token that died and stays dead does not flood the batch with repeated
  dead-token evidence.

## 8. Storage and Readiness

### 8.1 Current Storage State

| Table | Present in live DB | Present in proof/test DB |
|---|---|---|
| `printer_discovery_candidates` | Yes | Yes |
| `printer_tracking_queue` | Yes | Yes |
| `printer_tokens` / `printer_pairs` | Yes | Yes |
| `printer_selection_batches` | **No** | Yes (migration 025) |
| `printer_selection_batch_items` | **No** | Yes (migration 025) |
| `printer_selection_rotation_state` | **No** | No |

### 8.2 What the Current Schema Provides Without New Migrations

- Evidence-freshness check between the current candidate and the last discovery
  record for the same mint/pair can be done by reading
  `printer_discovery_candidates` (existing table). This covers the
  DISTINCT_NEW_EVIDENCE discovery gate.
- Lifecycle state for the REVIVAL and MIGRATION gates comes from
  `printer_tracking_queue` (existing table).
- STNP classification helpers are already in `selection_batch.py` (existing
  code).

No new migration is needed for the discovery-side gates.

### 8.3 New Table Required: printer_selection_rotation_state

The cross-batch selection cooldown (Rules 1, 2, 5, 6) requires querying recent
selection history keyed by `token_mint` and `pair_address`. While this could be
queried from `printer_selection_batch_items`, a dedicated rotation-state table
provides a faster lookup path and avoids a full-batch scan on every selection
cycle.

**Proposed schema** (for the implementation lane to formalize in a migration):

```sql
CREATE TABLE printer_selection_rotation_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    pair_address TEXT NOT NULL,
    last_selected_batch_id TEXT,
    last_selected_batch_seq INTEGER,
    last_selected_at TEXT,
    last_evidence_fingerprint_json TEXT,
    selection_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(token_mint, pair_address)
);
```

This table is updated atomically with each batch assembly. It never replaces
`printer_selection_batch_items`; it is an auxiliary lookup table only.

### 8.4 Readiness Gate for Implementation

Before any rotation implementation runs against the live database:

1. `printer_selection_batches` must exist (apply migration 025_selection_batch.sql).
2. `printer_selection_batch_items` must exist (same migration).
3. `printer_selection_rotation_state` must exist (new migration, to be written
   in the implementation lane).
4. `check_selection_batch_schema_ready()` must pass on the live database.

If any of these tables are absent, the rotation logic must fail-fast with a
clear error rather than silently skipping rotation checks.

## 9. Implementation Handoff

This section describes the ordered work for a future implementation lane.
This design does not authorize beginning that work.

### 9.1 Step Order

1. **Apply migration 025** to the live database if not already applied. This
   creates `printer_selection_batches` and `printer_selection_batch_items`.

2. **Write migration for `printer_selection_rotation_state`** (new file:
   `migrations/026_selection_rotation_state.sql`). Include `UNIQUE` constraint
   on `(token_mint, pair_address)` for upsert safety.

3. **Add `compute_evidence_identity_fingerprint(candidate) -> dict` to
   `selection_batch.py`**. Pure function. Reads `activity_bucket` (computed by
   calling `derive_activity_bucket(candidate)`), `pair_age_context_label`,
   `source_channel`, and `primary_bucket`. Returns a dict with these four
   categorical fields. No DB reads. No scores.

4. **Add `fingerprint_change_is_meaningful(old_fp, new_fp) -> bool` to
   `selection_batch.py`**. Pure function. Implements the meaningful-change
   criteria from Section 5.2. Returns True when at least one meaningful field
   differs per the defined rules.

5. **Add `check_token_selection_cooldown(db_or_connection, token_mint,
   current_batch_seq, *, cooldown_window=3) -> tuple[bool, str]` to
   `selection_batch.py`**. Queries `printer_selection_rotation_state` for this
   mint. Returns `(ok, reason)`. Cooldown window defaults to 3 batches.

6. **Add `check_pair_selection_cooldown(db_or_connection, pair_address,
   current_batch_seq, *, cooldown_window=3) -> tuple[bool, str]` to
   `selection_batch.py`**. Same structure as Step 5, keyed by `pair_address`.

7. **Add `record_selection_rotation_state(db_or_connection, items, batch_id,
   batch_seq)` to `selection_batch.py`**. Upserts one row per SELECTED item
   into `printer_selection_rotation_state`. Called inside `persist_selection_batch()`
   after the batch is written.

8. **Wire cooldown checks into `commands.py` discovery selection path** after
   existing gates (STNP gate, cooldown/archive gate, WATCH_ONLY promotion gate)
   and before final quota validation.

9. **Add evidence-aware discovery gate to the normal discovery persistence
   path in `commands.py`**: insert the Tier 2 lifecycle check (Section 5.1)
   before the existing-mint rejection to allow MIGRATION, REVIVAL, and
   DISTINCT_NEW_EVIDENCE candidates to pass through to the appropriate
   classification helpers.

10. **Add `rotation_exposure_warnings` to the discovery payload** (Step 3/4
    of the operator payload in `commands.py`): source concentration warning
    (Rule 3) and category concentration warning (Rule 4) computed from
    recent batch history.

### 9.2 What Does Not Require New Implementation

- **Source/channel cap (Rule 3)**: computed from existing `printer_selection_batch_items`
  records once the schema is present. No new write path at selection time.
- **Category cap (Rule 4)**: same: computed from existing batch-item records.
- **STNP classification (migration gate)**: already implemented in
  `classify_same_token_new_pair()`. Only the discovery pre-check (Step 9) is new.
- **WATCH_ONLY silent-promotion guard**: already implemented in
  `check_watch_only_promotion_gate()`. Preserved without change.
- **Quota rules**: already implemented in `validate_batch_quota()`. Preserved
  without change.

### 9.3 New Rejection Constants

Add to `selection_batch.py`:

```python
REJECTION_TOKEN_SELECTION_COOLDOWN = "TOKEN_SELECTION_COOLDOWN"
REJECTION_PAIR_SELECTION_COOLDOWN = "PAIR_SELECTION_COOLDOWN"
```

These join the existing rejection constant set. They are categorical labels
only — not scores or rankings.

## 10. Proof and Test Plan

Six proof types for a future implementation lane.

### Proof 1 — Token-Level Cooldown

Build an in-memory test that simulates 4 successive selection batches:

- Batch 1: token_mint X is SELECTED. Update rotation state.
- Batch 2: token_mint X is a candidate. Assert rejected with
  `TOKEN_SELECTION_COOLDOWN`.
- Batch 3: token_mint X is a candidate. Assert rejected.
- Batch 4: token_mint X is a candidate. Assert allowed (cooldown window of 3
  batches has elapsed).

Test file: add to `tests/test_v2_2c_selection_batch.py` or create
`tests/test_v2_2r_selection_rotation.py`.

### Proof 2 — Pair-Level Cooldown

Same structure as Proof 1, keyed by `pair_address`.

Also test: same token_mint returning on a new pair_address. Assert:
- Pair-level cooldown does not trigger (new pair address has no history).
- Token-level cooldown still triggers.
- Migration waiver path clears token-level cooldown when migration criteria
  are met.

### Proof 3 — Evidence Freshness Gate

Three sub-tests:

3a. Token in cooldown window, fingerprint unchanged → no waiver → still blocked
    for remaining cooldown batches.

3b. Token in cooldown window, fingerprint changed meaningfully (DEAD → REVIVING
    activity bucket) → waiver eligible → passes Rule 5 → token-level cooldown
    waiver applied if migration/revival reason provided.

3c. Token beyond cooldown window, fingerprint unchanged → allowed with
    `STALE_EVIDENCE_RESELECT` note in `lane_rationale`.

### Proof 4 — Fair-Aging Slot

Build a pool of 8 candidates. Simulate 6 batches where 2 candidates are
consistently excluded (their `primary_bucket` or cooldown status prevents
normal selection). In batch 7:

- Assert: at least 1 fair-aging slot is allocated to one of the 2
  stale-eligible candidates.
- Assert: no more than 1 fair-aging slot is allocated.
- Assert: fair-aging candidate still passes all categorical gates.

### Proof 5 — Discovery Migration Gate

5a. Token already in `printer_discovery_candidates`. New response has the
    same mint, a new pair address, `source_channel=PUMPFUN_MIGRATION`.
    Assert: the Tier 2 lifecycle check routes the candidate to STNP
    classification before the existing-mint rejection fires.
    Assert: STNP classification returns `ok=True` for `STNP_MIGRATION`.
    Assert: candidate is admitted with `same_token_new_pair_classification=MIGRATION`.

5b. Same token, same pair address (not new), same migration channel.
    Assert: blocked as EXACT_DUPLICATE or DUPLICATE_RECYCLE (pair already
    in persistence, pair address not new → migration gate does not apply).

### Proof 6 — Source/Channel Exposure Cap Warning

Build 3 test batches where DexScreener contributes 5 of 6 selected items in
each batch (83%):

- Assert: `rotation_exposure_warnings` in payload batch 4 contains a
  DexScreener source-concentration entry.
- Assert: no hard block occurs (batch still assembles).
- Assert: when source distribution is 60/40, no warning fires.

## 11. Money-Usefulness Contribution

This design is upstream evidence-quality work, not a trading signal, ranking,
or BUY probability.

When implemented, the rotation rules will improve Printer's memory diet by:

- Reducing repeated exposure to the same popular tokens from fixed
  provider endpoints.
- Allowing revival, migration, and distinct-evidence tokens to re-enter
  discovery rather than being permanently suppressed.
- Retaining losers, traps, failed pumps, dead tokens, and archived tokens
  for negative-learning coverage, rotated in at bounded frequency.
- Reducing source and category concentration across successive batches.
- Separating DUPLICATE_RECYCLE from legitimate market evolution events.
- Making later clean-memory comparisons less biased toward whichever provider
  or page dominated recent discovery.

Without this design, Printer's memory corpus accumulates tokens from a narrow,
provider-biased selection universe, and the same tokens can dominate successive
batches without cooldown.

## 12. What V2-2R Improves

- Converts V2-2Q's 10 "missing" findings into concrete design rules.
- Defines the 7-category duplicate/resurfacing taxonomy that replaces the
  flat "block all existing mints" rule.
- Defines 6 categorical selection rotation rules (cooldown, source cap,
  category cap, evidence freshness, fair-aging).
- Provides the lifecycle integration map (COOLDOWN, ARCHIVED, revival,
  migration, WATCH_ONLY, D1) for each rotation path.
- Identifies the new `printer_selection_rotation_state` table as the minimal
  new schema addition needed.
- Provides a 6-proof test plan and step-ordered implementation handoff.
- Enables a future implementation lane to close the V2-2Q gaps.

## 13. What V2-2R Does Not Unlock

- Implementation.
- Source fetching.
- Scheduler or runtime execution.
- Database mutation.
- Snapshots or memory windows.
- Clean-memory creation.
- Retrieval.
- Paper decisions.
- BUY, SELL, or HOLD.
- Paper positions.
- Trades.
- Paper trade audits.
- PnL.
- Wallet, private-key, signing, or live-execution logic.
- Paid APIs.
- Scoring, ranking, confidence, or weighted logic.
- Embeddings or vectors.

V2-2J and V2-3 remain paused. V2-2Q remains paused.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk or blocker | Effect |
|---|---|
| Selection batch tables absent from live DB | Cross-batch rotation cannot query history; migration 025 must be applied to live DB before implementation starts |
| Two-tier discovery gate changes the normal persistence path | Risk of inadvertently allowing unsafe resurfacing if the Tier 2 pre-check is mis-implemented; evidence-freshness gate is the safety net |
| 3-batch token cooldown window is a design assumption | Too short: repeated exposure; too long: starves active tokens. Requires empirical validation after first implementation proof run |
| Evidence identity fingerprint has low entropy (4 categorical fields) | Minor evidence changes may not trigger the meaningful-change threshold, allowing quasi-recycling to pass as fresh |
| Fair-aging single-slot rule limits impact | Only 1 stale candidate per batch gets priority; heavily starved candidates may still wait many cycles |
| Source exposure cap is soft warning (not hard block) | Concentration can persist if only 2 READY sources remain and both happen to produce the same tokens |
| WATCH_ONLY promotion guard must be verified after lifecycle reopen | A revival path that sets `cooldown_reopened=True` without updating `discovery_action` could accidentally enable silent WATCH_ONLY promotion |
| D1 dead-token evidence identity rarely changes | STALE_EVIDENCE_RESELECT notes will accumulate on dead tokens after every cooldown cycle; this is correct behavior but requires operator awareness |
| `printer_selection_rotation_state` upsert concurrency | If two discovery cycles run simultaneously (not currently possible under Central Scheduler, but must be verified), rotation state could have a race condition on the UNIQUE constraint |
| No proof DB for cross-batch behavior yet | The 6-proof test plan requires a test DB with selection history; end-to-end proof of rotation requires multiple batches to run against a populated rotation-state table |

## 15. Next Recommended Lane

**V2-2S — Cross-Batch Selection Cooldown Implementation**

V2-2S should implement the selection-rotation side first (Rules 1, 2, and 5)
because:

- These rules are purely additive to `selection_batch.py` and `commands.py`
  (new functions, new rejection constants, new table).
- They do not change the discovery persistence gate.
- They have the most direct, measurable impact on V2-2Q's cross-batch
  repetition blocker.
- Proof types 1, 2, and 3 from Section 10 are sufficient to verify them in
  isolation.

The discovery gate reform (Tier 2 conditional allowance for MIGRATION,
REVIVAL, DISTINCT_NEW_EVIDENCE from Section 5.1) is higher risk because it
changes the normal discovery persistence path. It should be a separate
subsequent lane (V2-2T or a designated discovery reform lane) after V2-2S
proves the selection cooldown side.

V2-2J and V2-3 remain paused. V2-2Q remains paused. WINDOW_ONLY must not be
silently promoted to TRACK_NORMAL or TRACK_FAST.

## 16. Design Verdict

`DESIGN_COMPLETE_WITH_BLOCKERS`

The V2-2R design converts the V2-2Q audit's central mismatch — discovery
over-blocks legitimate resurfacing while selection under-controls cross-batch
repetition — into a concrete, categorical, implementable specification.

The blockers are not design gaps. The blockers are implementation prerequisites:

1. Migration 025 must be applied to the live database before cross-batch
   rotation can query selection history.
2. The `printer_selection_rotation_state` table does not yet exist and must be
   created in the implementation lane.
3. The discovery persistence gate must be modified carefully in a separate
   lane (after the selection cooldown side is proven) to avoid inadvertent
   resurfacing of unsafe candidates.

No scoring, ranking, confidence percentage, or weighted logic is required or
introduced by any rule in this design. All rules are categorical gates,
categorical labels, and count-based exposure checks.
