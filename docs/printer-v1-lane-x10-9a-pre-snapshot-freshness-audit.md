# Printer V1 — Lane X10.9a Pre-Snapshot Freshness Audit

**Verdict:** `IMPLEMENTATION_NEEDED`
**Recommended insertion points:** `MULTIPLE_LAYERS` (X6 advisory → X10.6 traceability field → X5 pre-loop hard gate)
**Runtime status:** `NO_RUNTIME_ALLOWED_IN_AUDIT`

---

## 1. Purpose

This audit inspects the current code paths from discovery through X5 first snapshot to determine:

- Whether a freshness/age gate exists at any point for TRACK_FAST tokens before the first snapshot
- Where existing timestamps are available to support a freshness check
- Where the gate should be placed in the pipeline
- What the gate policy should be per tracking lane
- Whether a DB migration is required

No code was modified. No runtime was invoked. No DB was mutated. No source fetching occurred. This document is the result of static code and schema inspection only.

---

## 2. Code Paths Inspected

| # | Path | File | Lines Inspected |
|---|---|---|---|
| 1 | `printer-discover-candidates-once` | `operator_cli/commands.py` | 1447–1630 |
| 2 | `printer-run-lane-x6-discovery-selection-repair` | `operator_cli/lane_x6_discovery_selection_repair.py` | 1–250 |
| 3 | `X10.6 build_selection_batch()` | `operator_cli/lane_x10_6_selection_traceability.py` | 1–100 |
| 4 | X5 token-list validation | `operator_cli/lane_x5_five_token_runner.py` | 249–342 |
| 5 | X5 runner before first snapshot | `operator_cli/lane_x5_five_token_runner.py` | 750–1070 |
| 6 | E2H TRACK_FAST_FIRST_15M handler | `operator_cli/e2h_runtime_handler.py` | 1–280 |
| 7 | Source request/response timestamps | DB schema inspection | `printer_source_requests`, `printer_source_responses` |
| 8 | Tracking queue / discovery timestamps | DB schema inspection | `printer_tracking_queue`, `printer_discovery_candidates` |

---

## 3. Current Behavior Per Code Path

### 3.1 `printer-discover-candidates-once`

- Writes rows to `printer_discovery_candidates` with `created_at = datetime('now')`.
- The `normalized_candidate_payload_json` blob **does** contain a `captured_at` field (confirmed from live DB: `"captured_at": "2026-07-06T21:51:53.458176+00:00"`).
- No staleness assessment is performed at discovery time.
- Candidates are written and forgotten — no TTL, no expiry flag, no age labeling.

### 3.2 `printer-run-lane-x6-discovery-selection-repair`

- Reads `printer_discovery_candidates` rows from DB (or `candidate_list_override`).
- `classify_memory_diet_label()` uses market data fields: `price_change_5m`, `price_change_1h`, `price_change_24h`, `volume_*`, `txns_*`, `liquidity_usd`.
- **No check on `created_at` age of the discovery candidate.** A candidate written 3 hours ago and a candidate written 30 seconds ago receive identical treatment in X6.
- Cooldown-awareness exists (excludes COOLDOWN/ARCHIVED queue entries) but this is a lifecycle state check, not a time-based freshness check.

### 3.3 X10.6 `build_selection_batch()`

- Takes candidates from X6 or `candidate_list_override`.
- Adds event-kind labels, context tags, manual override gating, pair-drift acknowledgment, and a `source_trace` dict (contains `source_request_id`, `source_response_id`).
- The `source_trace` fields CAN be joined to `printer_source_responses.received_at` for age computation, but **this join is never performed**.
- **No `candidate_age_at_selection_seconds` field.** The batch artifact does not record how old the discovery candidate was at selection time.
- **No `batch_produced_at` timestamp** in the artifact, so the X5 runner cannot know when the list was built.

### 3.4 X5 token-list validation (`_load_and_validate_five_token_list`)

Current checks (lines 249–342 of `lane_x5_five_token_runner.py`):
- Exactly 5 tokens
- `tracking_lane == "TRACK_FAST"` per token
- `operator_approved == True` per token
- `chain == "solana"` per token
- Non-empty, non-placeholder `token_mint`
- Non-empty, non-placeholder `pair_address`
- No duplicate mints
- No duplicate pair addresses

**What is absent:** No `selected_at`, `discovered_at`, `source_response_id`, or any age metadata in the token list format. The token list JSON carries only `token_mint`, `pair_address`, `chain`, `tracking_lane`, `operator_approved`, plus optional `name`/`symbol` fields. There is no mechanism for the X5 validator to check whether the tracking designation is still current.

### 3.5 X5 runner before first snapshot (main cadence loop)

After token list validation passes (line ~879 in `run_five_token_memory_factory_cycle`), the runner immediately initializes token state dicts and enters the cadence loop. The sequence for each token's first iteration:

```
cadence_cycle starts
→ _run_x5_token_step(mint, slot, close_window=False)
    → _create_x5_job()           # scheduler job created
    → _claim_x5_job()            # job claimed (RUNNING)
    → execute_track_fast_first_15m_job()   # E2H handler
        → Gate 1: transport check
        → Gate 2: no running jobs
        → Gate 3: no active locks
        → Gate 4: source governor
        → source call (DexScreener)
    → E2M: persist snapshot
    → E2O: close window if elapsed
    → E2Q: audit window
```

**No freshness check at any of these steps.** The cadence loop has no gate between "token list parsed" and "first source call." A TRACK_FAST token designated 6 hours ago would receive its first snapshot with no warning or block.

Note: The source call itself produces FRESH DexScreener data (the snapshot is current). The staleness problem is not about snapshot data quality — it is about whether the **tracking designation** (TRACK_FAST, based on a memecoin event that was fast-moving at discovery time) is still valid. A memecoin that was pumping at T+0 may be fully dead at T+30 minutes. Snapshotting it as TRACK_FAST at T+30 minutes produces snapshots that will have MISSING_CRITICAL_DATA or DIRTY_MEMORY — not because the source failed, but because the underlying event is over.

### 3.6 E2H TRACK_FAST_FIRST_15M runtime handler

Gate order (lines 244–280 of `e2h_runtime_handler.py`):
1. Real source transport available
2. No OTHER RUNNING jobs (excluding current job)
3. No OTHER active locks (excluding current job)
4. Source Governor budget allows the request
5. Execute source call (DexScreener)
6. Forbidden table delta guard (post-execution)

**No freshness gate.** The handler has no access to — and does not check — any timestamp related to when the token was originally classified as TRACK_FAST. It only validates that the scheduler is clean, the transport is available, and the source governor allows the call.

### 3.7 Source request/response timestamps (DB schema)

```
printer_source_requests:
  id, source_name, request_kind, requested_at, request_key,
  tracking_priority, source_status, data_quality_label, created_at

printer_source_responses:
  id, source_request_id, source_name, received_at, status_code,
  source_status, data_quality_label, response_hash,
  normalized_payload_json, created_at
```

**Available for freshness:** `printer_source_responses.received_at` is the most reliable "when was this data current" timestamp. If a governed source response for a given pair was received within the freshness window, it constitutes a revalidation signal — even without a new X5 discovery pass.

### 3.8 Tracking queue / discovery candidate timestamps (DB schema)

```
printer_tracking_queue:
  id, token_id, pair_id, tracking_lane, tracking_action,
  priority_reason, next_check_at, last_checked_at, queue_status,
  source_status, data_quality_label, created_at, updated_at

printer_discovery_candidates:
  id, source_response_id, token_id, pair_id, source_name,
  discovery_label, discovery_action, source_status, data_quality_label,
  raw_candidate_payload_json, normalized_candidate_payload_json,
  lifecycle_state, tracking_lane, priority_reason, created_at,
  source_channel, source_channel_reason
```

**Available for freshness:**
- `printer_discovery_candidates.created_at` — row creation time (≈ discovery time)
- Within `normalized_candidate_payload_json` → `captured_at` — exact DexScreener data-capture timestamp (confirmed present in live data: ISO-8601 UTC)
- `printer_tracking_queue.created_at` — when token was first enqueued
- `printer_tracking_queue.updated_at` — when queue entry was last touched

---

## 4. Freshness Gaps Found

### Gap 1: No age field in X5 token list format (CRITICAL)
The token list JSON has no `selected_at`, `discovered_at`, or `source_response_id`. The X5 runner cannot determine the age of the tracking designation without a DB lookup against `printer_discovery_candidates.created_at`.

### Gap 2: X6 selection ignores discovery candidate age (MEDIUM)
X6 reads `printer_discovery_candidates` but uses only market data fields for classification. A 4-hour-old TRACK_FAST candidate and a 30-second-old TRACK_FAST candidate receive identical selection treatment.

### Gap 3: X10.6 batch has no staleness field (MEDIUM)
The selection batch artifact carries a `source_trace` with `source_request_id` and `source_response_id` per candidate, but never computes or records the age of the candidate at selection time. The batch artifact also has no `batch_produced_at` field.

### Gap 4: X5 pre-loop has no freshness gate (CRITICAL)
After token list validation passes, the runner proceeds directly to the cadence loop with no check on how old the tracking designation is. For TRACK_FAST tokens (where the spec requires 1-3 minute snapshot frequency and the event is inherently fast-moving), this means a stale designation can produce misleading WINDOW_15M memory.

### Gap 5: E2H handler has no freshness advisory (LOW)
The E2H handler is the last gate before a source call. Even though a freshness gate cannot block at E2H without a DB lookup (which is expensive per-snapshot), it could emit a `freshness_advisory` field in the handler result for the first snapshot of a new window.

### Gap 6: Discovery candidates have no TTL or expiry flag (LOW)
Discovery candidates persist indefinitely. There is no `expires_at` field, no `staleness_label`, and no automatic mechanism to downgrade a TRACK_FAST candidate to TRACK_NORMAL or WATCH_ONLY as time passes.

---

## 5. Answers to the 10 Audit Questions

### Q1: Earliest safe place to block stale TRACK_FAST before X5

**X6 selection** is the earliest place where candidate age can be assessed. X6 already reads `printer_discovery_candidates` with `created_at`. However, X6 should add an **advisory flag** only, not a hard block, because:

- At X6 time, the operator has not yet begun X10.6 or X5 prep
- Some candidates may take time to process (BONK pair drift requires manual override)
- Hard blocking at X6 would reject candidates that are still within freshness limits by the time X5 starts

**Earliest advisory**: X6 — adds `discovery_age_seconds` and `freshness_status` to each candidate's output.

### Q2: Latest mandatory place to block stale TRACK_FAST before first snapshot

**X5 runner, pre-cadence-loop** (inside `run_five_token_memory_factory_cycle`, after `_load_and_validate_five_token_list` passes and before the cadence loop starts) is the last mandatory gate.

This requires:
1. Adding `selected_at` to the X5 token list format (JSON field — no DB migration)
2. Or, performing a DB lookup against `printer_discovery_candidates.created_at` for each mint at X5 startup

The DB lookup approach works without changing the token list format but adds a startup-time read. The `selected_at` field approach is cleaner and verifiable without a DB call.

Both approaches can coexist: check `selected_at` if present, fall back to DB lookup, warn if neither is available.

**Latest mandatory gate**: X5 `run_five_token_memory_factory_cycle()` after token list validation, before cadence loop.

### Q3: DB fields/timestamps currently available for candidate age

| Field | Table | Type | Meaning |
|---|---|---|---|
| `created_at` | `printer_discovery_candidates` | ISO TEXT | When the discovery row was written (≈ discovery time) |
| `normalized_candidate_payload_json → captured_at` | `printer_discovery_candidates` | ISO TEXT (JSON) | DexScreener data-capture time at discovery |
| `created_at` | `printer_tracking_queue` | ISO TEXT | When token was first enqueued |
| `updated_at` | `printer_tracking_queue` | ISO TEXT | Last queue status change |
| `requested_at` | `printer_source_requests` | ISO TEXT | When source request was made |
| `received_at` | `printer_source_responses` | ISO TEXT | When source response was received |

The most reliable freshness timestamp for "how old is this discovery event" is `printer_discovery_candidates.created_at` (when the discovery pipeline wrote the row). The `captured_at` inside the JSON payload is even more precise (DexScreener's own data timestamp) but requires JSON extraction.

The most reliable freshness timestamp for "was there a recent governed revalidation" is `printer_source_responses.received_at` filtered by the pair's `source_request_id`.

### Q4: Source request/response fields available for fresh revalidation proof

A token can be considered "freshly revalidated" (even without a new discovery pass) if:

```sql
SELECT sr.received_at
FROM printer_source_requests srq
JOIN printer_source_responses sr ON sr.source_request_id = srq.id
WHERE srq.request_key LIKE '%<pair_address>%'
  AND sr.source_status = 'COMPLETE'
  AND sr.data_quality_label = 'CLEAN_DATA'
  AND sr.received_at > datetime('now', '-180 seconds')
LIMIT 1
```

Fields that prove fresh revalidation:
- `printer_source_responses.received_at` — timestamp of the governed response
- `printer_source_responses.source_status` — must be COMPLETE
- `printer_source_responses.data_quality_label` — must be CLEAN_DATA
- `printer_source_requests.request_key` — used to match to the specific pair

This approach requires one read-only DB join at X5 startup per token. It is lightweight and adds no source calls.

### Q5: Can this be implemented without a migration?

**YES — no DB migration required.**

All needed timestamp fields already exist in the DB:
- `printer_discovery_candidates.created_at` ✓
- `printer_source_responses.received_at` ✓
- `printer_tracking_queue.created_at` ✓

The only format change needed is:
- **X5 token list JSON**: add optional `selected_at` field (ISO-8601 UTC) to each token entry, or at the batch level. This is a non-breaking JSON format extension — existing token lists without `selected_at` work as before (gate falls back to DB lookup).
- **X10.6 batch artifact JSON**: add `batch_produced_at` field and `candidate_age_at_selection_seconds` per candidate. Non-breaking extension.

No `ALTER TABLE` statements required.

### Q6: Which layer(s) should the gate live in?

**Recommended: Three-layer defense in depth**

| Layer | Component | Type | Policy |
|---|---|---|---|
| Layer 1 (earliest) | X6 selection | Advisory | Add `discovery_age_seconds` to each candidate output. Emit `FRESHNESS_WARNING` if > 120s. No blocking. |
| Layer 2 | X10.6 batch | Traceability field | Add `candidate_age_at_selection_seconds` per candidate. Add `batch_produced_at`. No blocking. |
| Layer 3 (mandatory) | X5 pre-loop gate | Hard gate | Block if `selected_at` or DB-derived age > `TRACK_FAST_HARD_MAX_AGE_SECONDS`. Warn if > `TRACK_FAST_PREFERRED_MAX_AGE_SECONDS`. |

**Do not put a hard gate in E2H.** The handler is called per-snapshot (every 90 seconds during the run). Blocking an in-progress run mid-snapshot because 181 seconds have elapsed since discovery would produce partial windows and dirty memory. The gate must run before the first cadence cycle begins.

### Q7: How TRACK_FAST, TRACK_NORMAL, WATCH_ONLY, IGNORE, INSTANT_REJECT should differ

| Lane | Hard Max Age | Preferred Max Age | On Stale |
|---|---|---|---|
| TRACK_FAST | 180 seconds | 60–120 seconds | Hard block at X5 pre-loop (operator must re-discover or explicitly revalidate) |
| TRACK_NORMAL | 600 seconds (10 min) | 300 seconds (5 min) | Advisory warning only; do not block in X5 (TRACK_NORMAL is not in X5 currently) |
| WATCH_ONLY | Cannot enter X5 | — | Already blocked by X5 `tracking_lane` check (no change needed) |
| IGNORE | Cannot enter X5 | — | Already blocked by X5 `tracking_lane` check (no change needed) |
| INSTANT_REJECT | Cannot enter X5 | — | Already blocked by X5 `tracking_lane` check (no change needed) |

Note: The current X5 runner only accepts `TRACK_FAST` tokens, so TRACK_NORMAL, WATCH_ONLY, IGNORE, and INSTANT_REJECT are already blocked by the existing `tracking_lane` check. The freshness gate is only relevant to TRACK_FAST in the current X5 context.

### Q8: Pair drift / same-token-new-pair interaction with freshness

When `pair_drift_acknowledged=True` is set in X10.6:
- The relevant discovery timestamp is from the **new pair's** discovery candidate, not the old pair's
- The new pair's `printer_discovery_candidates.created_at` is the basis for freshness computation
- X10.6 already requires explicit `pair_drift_acknowledged=True` + `manual_override=True` — so the operator has already consciously accepted the drift
- The freshness gate should use the most recent discovery candidate `created_at` for the token's active pair

Implementation: when performing the DB lookup, query `printer_discovery_candidates WHERE token_id = ? ORDER BY created_at DESC LIMIT 1` to pick the most recent discovery event, which will be the new-pair event if pair drift occurred.

### Q9: Tests to add

```
test_freshness_gate_track_fast_within_preferred_max_passes
    candidate created 90s ago → age < 120s → FRESH_WITHIN_PREFERRED_LIMIT

test_freshness_gate_track_fast_within_hard_max_passes
    candidate created 170s ago → age < 180s → FRESH_WITHIN_HARD_LIMIT (warning)

test_freshness_gate_track_fast_at_hard_max_passes
    candidate created 180s ago → age == 180s → FRESH_AT_HARD_LIMIT (warning)

test_freshness_gate_track_fast_exceeded_hard_max_blocks
    candidate created 181s ago → age > 180s → STALE_TRACK_FAST_BLOCKED

test_freshness_gate_track_fast_selected_at_field_respected
    token list has selected_at=now-190s → STALE_TRACK_FAST_BLOCKED without DB lookup

test_freshness_gate_no_selected_at_falls_back_to_db_lookup
    token list has no selected_at → gate queries printer_discovery_candidates.created_at

test_freshness_gate_no_discovery_candidate_emits_warning_only
    mint not in printer_discovery_candidates → FRESHNESS_UNKNOWN advisory, no hard block

test_freshness_gate_pair_drift_uses_new_pair_timestamp
    token has old pair (3 hours ago) and new pair (60s ago) → uses new pair's created_at → FRESH

test_freshness_gate_pair_drift_stale_new_pair_blocks
    token has new pair but created_at > 180s → STALE_TRACK_FAST_BLOCKED

test_freshness_gate_recent_source_response_counts_as_revalidation
    discovery is 200s old but a governed source response for same pair exists within 60s → REVALIDATED_FRESH

test_freshness_gate_track_normal_not_blocked_only_advisory
    TRACK_NORMAL candidate created 8 minutes ago → advisory only, no block in X5 context

test_x10_6_batch_includes_candidate_age_at_selection_seconds
    build_selection_batch() output includes candidate_age_at_selection_seconds per candidate

test_x10_6_batch_includes_batch_produced_at
    build_selection_batch() output includes batch_produced_at timestamp

test_x6_selection_includes_discovery_age_seconds
    run_x6_selection() output includes discovery_age_seconds per candidate

test_x5_token_list_format_accepts_selected_at_field
    token list JSON with selected_at field parsed without error
```

### Q10: What must remain locked

All existing V1 locks remain unchanged. The freshness gate must not:

- Issue any source calls or network requests (no DexScreener check at gate time — read-only DB only)
- Write any new rows to any table (gate is read-only)
- Bypass Source Governor or Central Scheduler
- Create paper decisions, positions, PnL, trade events, or retrieval matches
- Unlock BUY/SELL/HOLD
- Downgrade a TRACK_FAST token to TRACK_NORMAL automatically (gate can BLOCK but not mutate lifecycle state — that requires a separate lifecycle event with operator authorization)
- Introduce scoring, ranking, confidence, or weighted logic (age comparison is a binary threshold check, not a score)

If a TRACK_FAST token is blocked by the freshness gate:
- The X5 run returns `LANE_X5_BLOCKED` (or the token is excluded from the run with a clearly reported reason)
- The operator must re-run discovery (or explicitly acknowledge the staleness as an operator-approved override) before retrying
- Zero clean memories remains a valid outcome

---

## 6. Recommended Implementation Plan

### Phase A: No-code changes — add `selected_at` to X5 token list format

Update the X5 token list JSON schema documentation and `_load_and_validate_five_token_list` to accept (but not require) a `selected_at` field per token or at the top level. When present, record it in the per-token state dict.

**Scope**: `lane_x5_five_token_runner.py` — `_load_and_validate_five_token_list()` and token entry processing. No other files.

### Phase B: X10.6 batch artifact — add age fields

In `build_selection_batch()`:
- Add `batch_produced_at = datetime.now(timezone.utc).isoformat()` to the batch output
- Add `candidate_age_at_selection_seconds` per candidate (from `candidate["created_at"]` or `source_trace["source_response_id"]` lookup)
- Add `freshness_status` per candidate: `FRESH_WITHIN_PREFERRED`, `FRESH_WITHIN_HARD_LIMIT`, `STALE_AT_SELECTION_TIME`

**Scope**: `lane_x10_6_selection_traceability.py` — `build_selection_batch()` only. No DB changes.

### Phase C: X6 advisory flag

In `run_x6_selection_repair()` (or equivalent candidate output):
- Add `discovery_age_seconds` per candidate using `created_at` vs. `datetime.now(timezone.utc)`
- Add `freshness_warning: bool` if age > `TRACK_FAST_PREFERRED_MAX_AGE_SECONDS = 120` and `tracking_lane == TRACK_FAST`

**Scope**: `lane_x6_discovery_selection_repair.py` — candidate output fields only. No blocking logic.

### Phase D: X10.9 freshness gate module (new file)

New file: `src/printer_v1/operator_cli/lane_x10_9_freshness_gate.py`

```python
TRACK_FAST_PREFERRED_MAX_AGE_SECONDS: int = 120
TRACK_FAST_HARD_MAX_AGE_SECONDS: int = 180
TRACK_NORMAL_STALE_THRESHOLD_SECONDS: int = 600

FRESHNESS_STATUS_FRESH_PREFERRED: str = "FRESH_WITHIN_PREFERRED_LIMIT"
FRESHNESS_STATUS_FRESH_HARD: str = "FRESH_WITHIN_HARD_LIMIT"
FRESHNESS_STATUS_STALE_BLOCKED: str = "STALE_TRACK_FAST_BLOCKED"
FRESHNESS_STATUS_UNKNOWN: str = "FRESHNESS_UNKNOWN"
FRESHNESS_STATUS_REVALIDATED: str = "REVALIDATED_FRESH"

def check_track_fast_freshness(
    mint: str,
    db_path: str | Path,
    *,
    selected_at: str | None = None,
    now: datetime | None = None,
) -> FreshnessResult:
    """Read-only. No source calls. No DB writes."""
    ...

def check_token_list_freshness(
    mints_and_selected_at: list[tuple[str, str | None]],
    db_path: str | Path,
) -> list[FreshnessResult]:
    ...
```

All functions: read-only, no source calls, no DB mutations.

### Phase E: X5 pre-loop hard gate

In `run_five_token_memory_factory_cycle()`, after `_load_and_validate_five_token_list()` passes and before the cadence loop:

```python
# Freshness gate — TRACK_FAST staleness check (read-only DB lookup)
freshness_results = check_token_list_freshness(
    [(mint_a, token_a_entry.get("selected_at")),
     (mint_b, token_b_entry.get("selected_at")),
     ...],
    db_path
)
for fr in freshness_results:
    if fr.status == FRESHNESS_STATUS_STALE_BLOCKED:
        blocked_reasons.append(
            f"TRACK_FAST freshness gate: slot {fr.slot} mint {fr.mint}"
            f" is stale (age {fr.age_seconds}s > {TRACK_FAST_HARD_MAX_AGE_SECONDS}s);"
            " re-run discovery or provide explicit operator revalidation"
        )
```

**Scope**: `lane_x5_five_token_runner.py` — `run_five_token_memory_factory_cycle()`, 10-15 new lines after line ~896.

---

## 7. Files Inspected (No Changes Made)

| File | Purpose | Freshness gap found |
|---|---|---|
| `operator_cli/commands.py` | `printer-discover-candidates-once` entry | No age annotation on discovery rows |
| `operator_cli/lane_x6_discovery_selection_repair.py` | X6 selection | No age check in candidate selection |
| `operator_cli/lane_x10_6_selection_traceability.py` | X10.6 batch | No age field in batch artifact |
| `operator_cli/lane_x5_five_token_runner.py` | X5 runner | No freshness gate pre-loop or in validator |
| `operator_cli/e2h_runtime_handler.py` | E2H handler | No freshness advisory |
| `operator_cli/e2m_snapshot_persistence.py` | Snapshot persistence | No freshness check (correct — E2M is post-source) |
| DB schema: `printer_discovery_candidates` | Discovery candidate timestamps | `created_at` present; `captured_at` in JSON blob |
| DB schema: `printer_source_responses` | Source response timestamps | `received_at` present — usable for revalidation proof |
| DB schema: `printer_tracking_queue` | Queue timestamps | `created_at` / `updated_at` present |

---

## 8. Risks and Blockers

### Risk 1: TRACK_FAST blocking may leave X5 with fewer than 5 tokens

If 2 of 5 tokens fail the freshness gate, the operator must either re-discover and rebuild the token list, or provide an explicit `revalidation_acknowledged` override per blocked token. The gate should not silently drop tokens and run with 3/5 — it should block the whole run and require a fresh list.

**Mitigation**: X5 blocks the run entirely if any token fails the gate (consistent with existing pattern: any validation failure blocks the whole run, not per-token).

### Risk 2: Clock drift between DB server and local clock

`created_at` in SQLite uses the local process clock. If the operator runs discovery on a machine with clock drift, the age computation may be wrong.

**Mitigation**: Use `received_at` from `printer_source_responses` (which reflects actual network round-trip time) as a cross-check. Report age from both sources when available.

### Risk 3: Manual operator runs may exceed 180s legitimately

In X10.7 and X10.8, the operator had to: run discovery, run X6, build X10.6 batch, fix stale locks, build X5 token list. This pipeline routinely takes 5-30+ minutes. A hard 180s gate would always block the first attempt.

**Mitigation**: The gate should check the age of the **discovery designation** against the `selected_at` timestamp in the X5 token list, not the age of discovery relative to when X5 starts. The `selected_at` is set when the operator finalizes the token list (e.g., from X10.6 `batch_produced_at`). This measures "how stale is the token list" not "how long since discovery." This approach is more accurate and appropriate for manual operator workflows.

Alternative: the operator explicitly sets `selected_at` when building the token list, and the gate checks whether the selection is still fresh relative to the start of the X5 run — not relative to original discovery time.

### Risk 4: `printer_discovery_candidates` may not exist for all X5 tokens

In X10.8, BONK (DezXAZ8z7Pnrn...) was in the X5 list from X6 selection but its original discovery candidate may have been from an earlier session. If the discovery candidate row is missing or very old, the DB lookup will find no match.

**Mitigation**: If no `discovery_candidate` row is found for a mint, emit `FRESHNESS_UNKNOWN` advisory (not a hard block). Hard blocks should only occur when a known age can be measured and exceeds the limit.

### Risk 5: Revalidation via source response may not always be available

The "recent source response for same pair" revalidation check requires that the `request_key` in `printer_source_requests` includes the pair address. If the request key format changes, this join breaks.

**Mitigation**: Make the revalidation check optional. If no recent source response is found, fall back to discovery candidate age. Document the request_key format dependency.

---

## 9. Tests Needed

See Section 5, Q9 for the full list of 13 test cases. Tests must be in a new file:

```
tests/operator_cli/test_lane_x10_9_freshness_gate.py
```

Tests must not:
- Make real network calls
- Mutate the live DB
- Import from production source adapters without mocking

---

## 10. Final Verdicts

```
implementation_verdict:     IMPLEMENTATION_NEEDED
insertion_points:           MULTIPLE_LAYERS (X6 advisory, X10.6 traceability, X5 hard gate)
migration_required:         NO
new_module_needed:          YES (lane_x10_9_freshness_gate.py)
files_to_modify:            lane_x5_five_token_runner.py
                            lane_x10_6_selection_traceability.py
                            lane_x6_discovery_selection_repair.py
                            (lane_x10_9_freshness_gate.py — new)
runtime_allowed_in_audit:   NO_RUNTIME_ALLOWED_IN_AUDIT

track_fast_hard_max_age_s:  180
track_fast_preferred_max_s: 60–120
track_normal_advisory_s:    300–600
watch_only_in_x5:           ALREADY_BLOCKED (existing tracking_lane check)
ignore_in_x5:               ALREADY_BLOCKED (existing tracking_lane check)
instant_reject_in_x5:       ALREADY_BLOCKED (existing tracking_lane check)

pair_drift_interaction:      USE_NEWEST_DISCOVERY_CANDIDATE_CREATED_AT
revalidation_path:           RECENT_SOURCE_RESPONSE_COUNTS_AS_REVALIDATION
no_discovery_candidate:      FRESHNESS_UNKNOWN_ADVISORY_NOT_HARD_BLOCK

all_v1_locks_preserved:     YES
no_buy_sell_hold:            YES
no_paper_decisions:          YES
no_source_governor_bypass:   YES
no_db_mutations_in_gate:     YES (gate is read-only)
```
