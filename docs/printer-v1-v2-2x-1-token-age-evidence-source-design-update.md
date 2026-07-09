# Printer V1 V2-2X.1 Token-Age Evidence Source Design Update

**Lane:** V2-2X.1 — Token-Age Evidence Source Design Update
**Type:** Design/specification only
**Verdict:** `DESIGN_COMPLETE_WITH_BLOCKERS`
**Date:** 2026-07-09
**Executor:** Claude Sonnet 4.6

V2-3, V2-4, token-age implementation, source activation, runtime/scheduler,
memory generation, retrieval, paper decisions, and all financial paths remain
paused. This document is design-only.

---

## 1. Source Stack Read

| Document | Role |
|---|---|
| `AGENTS.md` | Highest authority |
| `docs/printer-v1-clean-master-spec.md` | Master specification |
| `docs/printer-v1-post-rc-build-order.md` | Post-RC lane order |
| `docs/printer-v1-memory-factory-guide.md` | Memory factory rules |
| `docs/printer-v1-current-state-memory-growth-audit.md` | Baseline state |
| `docs/printer-v1-memory-growth-build-order-v2.md` | V2 roadmap |

Blocker docs read:

| Document | Purpose |
|---|---|
| `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md` | V2-2 closeout; carry-forward blockers including token age |
| `docs/printer-v1-v2-2o-token-age-evidence-repair-design.md` | Tier hierarchy, pair/token separation, first implementation handoff |
| `docs/printer-v1-v2-2x-token-age-evidence-source-readiness-review.md` | Source capability matrix; T2 as recommended first path |
| `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md` | Pair-age metadata boundary confirmation |
| `docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md` | Live audit: token age 100% absent, pair age 98.6% present |

Anchors verified:

| Anchor | Commit | Content |
|---|---|---|
| V2-2J closeout | `c6f002a` | V2-2 foundation closeout; token age designated as separate future lane |
| V2-2X readiness review | `5b9f93b` | T2 = governed PumpPortal launch timing as first path |
| V2-2P.3 pair-age verification | `be70309` | Both metadata fields present in parser and selection batch |

Files inspected statically:

- `src/printer_v1/sources/pumpportal.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`

---

## 2. Current Readiness Summary

From V2-2X and V2-2J:

| Item | Current state |
|---|---|
| `token_created_at` in parser NORMALIZED_FIELDS | YES — field exists, always None in live responses |
| `token_age_seconds` derivation in parser | YES — reads from `token_created_at` only |
| `token_age_evidence_tier` in parser NORMALIZED_FIELDS | YES — always None until T1/T2/T3 source active |
| `pair_age_context_label` in parser NORMALIZED_FIELDS | YES — implemented by V2-2P |
| Both fields in selection-batch `_METADATA_FIELDS` | YES — verified by V2-2P.3 |
| GeckoTerminal / DexScreener: provides `token_created_at` | NO — pair creation fields only |
| PumpPortal adapter: fixture-transport shell exists | YES — `pumpportal.py`, disabled by default |
| PumpPortal: `pumpfun_launch_stream` in registry | YES — `stale_after_seconds=60`, `rate_limit=30/min` |
| PumpPortal: live HTTP transport wired | NO — `fixture_transport_only=True` |
| PumpPortal: `token_created_at` extracted in normalization | NO — current `_normalize_pumpportal_event` does not extract event timestamp as token creation time |
| `derive_age_bucket` reads token age only | YES — UNCHANGED, confirmed by V2-2P.3 |
| A3 reads `_tok_age_known` from token age only | YES — UNCHANGED |
| Pair age fallback to token age | NO — correctly absent, confirmed by V2-2P.3 |

The parser infrastructure is ready. The PumpPortal adapter shell exists. The
normalization path does not yet extract token creation time from launch events.

---

## 3. Chosen First Source Path

`T2 — governed PumpPortal launch-event timing`

Specifically:

- **Source name:** `pumpportal`
- **Source channel:** `pumpfun_launch_stream`
- **Request kind:** `pumpfun_launch_stream`
- **Event type:** `subscribeNewToken` (Pump.fun new token creation event)
- **Rationale:** PumpPortal's `subscribeNewToken` stream emits a new event for
  every Pump.fun token the moment it is created on-chain. The event emission
  timestamp is therefore a direct real-time proxy for token creation time — not
  delayed by days or weeks as pair age can be. This is the narrowest and safest
  T2 path because it is free/public, already registered in the Source Registry,
  already has a fixture-transport adapter shell, and maps naturally to
  `token_created_at` without requiring RPC enrichment or a paid API.

T3 (Solana RPC / Helius mint-derived enrichment) remains the recommended
secondary path if PumpPortal launch timing is unavailable for a token. T3 is
a larger design scope (governed enrichment contract, budget controls, per-call
rate limits) and is explicitly deferred to a later design lane.

---

## 4. T2 Evidence Contract

This section defines the complete contract for valid T2 token-age evidence from
a PumpPortal `subscribeNewToken` launch event. An implementation must satisfy
all fields in this contract before mapping to `token_created_at`.

### 4.1 Required event fields

| Field | Source in PumpPortal payload | Notes |
|---|---|---|
| `source_name` | Hard-coded `"pumpportal"` | Set by adapter |
| `source_channel` | Hard-coded `"pumpfun_launch_stream"` | Set by adapter |
| `request_kind` | `context.request.request_kind` | Must equal `"pumpfun_launch_stream"` |
| `event_type` | Implicit: the event is a `subscribeNewToken` output | Migration events (`pumpfun_migration_stream`) are never valid T2 for `token_created_at` |
| `token_mint` | `event["mint"]` or `event["tokenMint"]` or `event["token_mint"]` | Must be non-empty Solana address |
| `pair_address` | `event["bondingCurveKey"]` or `event["pairAddress"]` or `event["pair_address"]` | Optional; bonding curve is the initial pair for Pump.fun |
| `event_timestamp` | `event["tokenCreatedAt"]` or `event["createdTimestamp"]` or `event["timestamp"]` (in this priority order) | Primary clock for T2 evidence; see Section 5 |
| `captured_at` | UTC datetime at Source Governor execution time | Must be recorded independently of event timestamp |
| `source_status` | From `NormalizedSourceResult.source_status` | Must be `COMPLETE` for T2 evidence to be accepted |
| `data_quality_label` | From `NormalizedSourceResult.data_quality_label` | Must not be `MISSING_CRITICAL_DATA`, `STALE_DATA`, or `DIRTY_DATA` |
| `source_trace` | `source_name` + `request_kind` + `source_status` present in normalized candidate | Complete source trace must survive to `printer_discovery_candidates` |

### 4.2 Evidence identity / target matching

T2 evidence maps to one specific token mint. Valid T2 evidence requires:

- `token_mint` from the launch event matches the `token_mint` in the downstream
  normalized candidate for that discovery cycle entry;
- no cross-mint substitution (a launch event for mint A must not populate
  `token_created_at` for mint B);
- source trace confirms the evidence came from `pumpfun_launch_stream`, not
  from GeckoTerminal, DexScreener, or any other source.

When PumpPortal launch evidence is joined with a GeckoTerminal or DexScreener
candidate (future enrichment design), the match must be on `token_mint`
(canonical Solana address) before `token_created_at` is assigned.

---

## 5. Timestamp Semantics

This section answers each required question about which timestamp is used and
how edge cases are handled.

### 5.1 Which timestamp becomes `token_created_at`?

Priority order for T2 evidence from a `pumpfun_launch_stream` event:

1. **`event["tokenCreatedAt"]`** — if PumpPortal includes an explicit token
   creation timestamp in the event payload, this is the highest-quality T2
   field. It represents when PumpPortal's indexer observed the on-chain creation
   transaction.

2. **`event["createdTimestamp"]`** — alternative PumpPortal field name for
   the same concept.

3. **`event["timestamp"]`** — the event emission timestamp from PumpPortal.
   For `subscribeNewToken` events, this is very close to creation time because
   the stream is triggered by the on-chain creation transaction. This is the
   minimal acceptable T2 field.

If none of these three fields is present, `token_created_at` remains `None`
and `token_age_evidence_tier` remains `None`. The implementation must not fall
through to `captured_at` in this case.

### 5.2 When is `captured_at` allowed only as observation time, not creation time?

`captured_at` is always observation-only. It records when the Source Governor
processed and stamped the event. It must never be mapped to `token_created_at`
for T2 evidence because:

- Network latency between on-chain event and Source Governor processing
  introduces bias;
- Batch collection delays (processing a queue of events) could make
  `captured_at` minutes or hours after the true creation time;
- Using `captured_at` as creation time would silently understate token age,
  turning old events into false "just launched" evidence.

`captured_at` must remain in the normalized candidate as the source observation
timestamp only, separately from `token_created_at`.

### 5.3 How should missing event time behave?

If all three priority fields (`tokenCreatedAt`, `createdTimestamp`, `timestamp`)
are absent from the launch event:

- `token_created_at` remains `None`.
- `token_age_seconds` remains `None`.
- `token_age_evidence_tier` remains `None`.
- `age_bucket` remains `AGE_UNKNOWN`.
- The candidate is still valid if it meets other selection criteria, but
  it contributes no age evidence.

This is the same behavior as for GeckoTerminal and DexScreener candidates today.

### 5.4 How should stale event time behave?

**Staleness definition:** a launch event timestamp is stale if:

```
captured_at - event_timestamp > PUMPPORTAL_LAUNCH_EVENT_STALENESS_THRESHOLD
```

Recommended threshold: `3600 seconds` (1 hour). If the Source Governor
receives a launch event more than 1 hour after the event's own timestamp, the
event was delayed in transit (network queue, replay, batch gap). In this case:

- Set `source_status = STALE` in the normalized result.
- Set `data_quality_label = STALE_DATA`.
- Do not populate `token_created_at` from a stale event's timestamp.
- The candidate may still carry pair and market data from subsequent READY
  sources (GeckoTerminal/DexScreener), but token age from this stale event
  must not be used.

**Rationale:** a 2-hour-old launch event claiming the token was created 2 hours
ago is correct, but using `captured_at` as a staleness guard ensures Printer
only maps T2 evidence when the event was received promptly after creation.

### 5.5 How should future timestamps / invalid timestamps behave?

**Future timestamp** (event_timestamp > captured_at):

- Reject as invalid. A launch event cannot pre-date its own observation.
- `token_created_at` remains `None`.
- Log the anomaly in source trace as a `data_quality_label` issue.

**Zero or negative timestamp:**

- Reject as invalid. A Unix epoch of 0 or negative indicates a missing or
  malformed timestamp field.
- `token_created_at` remains `None`.

**Non-numeric / unparseable timestamp:**

- Reject as invalid.
- `token_created_at` remains `None`.

In all invalid timestamp cases, the candidate may still be processed for other
fields, but age evidence is absent.

### 5.6 How should duplicate launch events behave?

PumpPortal may occasionally emit duplicate `subscribeNewToken` events for the
same mint (e.g., due to redelivery or stream reconnection).

Design rule: the discovery pipeline already deduplicates by `(token_mint,
pair_address)` via `filter_within_response_duplicates()` and the existing-mint
gate. If two launch events for the same mint are seen in one collection batch:

- Use the earliest valid `event_timestamp` as `token_created_at` (most likely
  to represent the actual creation time).
- Do not average timestamps.
- If timestamps differ by more than 60 seconds, log a data quality note but
  still use the earliest valid one.

### 5.7 How should launch events differ from migration events?

| Attribute | `pumpfun_launch_stream` (launch) | `pumpfun_migration_stream` (migration) |
|---|---|---|
| Event type | `subscribeNewToken` — token created for the first time | `subscribeMigration` — existing token moves from Pump.fun to Raydium |
| Token age | Event timestamp ≈ token creation time | Event timestamp = migration time, NOT creation time |
| `token_created_at` | Map from event timestamp (T2 evidence) | DO NOT map. Token was created before the migration event. |
| `token_age_evidence_tier` | `"T2"` | `None` (no valid T2 age from migration events) |
| `pair_address` | `bondingCurveKey` (initial bonding curve pool) | `newRaydiumPool` (new post-migration pool) |
| STNP status | New token, new pair | Existing token, new pair (same-token/new-pair = STNP) |

**Critical invariant:** a migration event timestamp MUST NOT become
`token_created_at` even if the timestamp field is present. A PumpPortal
migration event tells Printer when the token moved to Raydium, which is always
after the token was created. Using migration time as creation time would
understate token age — exactly the STNP late-buy-trap risk described in V2-2O.

Migration events remain useful for pair address discovery (which new Raydium
pool the token landed in) and STNP/Tier 2 gate context (V2-2V.1/V2-2W), but
they are not a source of T2 token-age evidence.

---

## 6. Normalized Output Fields

When a valid PumpPortal `pumpfun_launch_stream` event provides acceptable T2
evidence, the downstream normalized candidate must carry the following fields.

### 6.1 Primary age fields

| Field | Value | Notes |
|---|---|---|
| `token_created_at` | ISO-8601 UTC string from event timestamp | Derived from `tokenCreatedAt` / `createdTimestamp` / `timestamp` in priority order |
| `token_age_seconds` | `(captured_at - token_created_at).total_seconds()` | Must be ≥ 0; derived by existing `_safe_age_seconds(token_created_at, captured_at)` |
| `token_age_evidence_tier` | `"T2"` | Set explicitly by the PumpPortal normalization path for launch events |

### 6.2 Pair fields (if available from the launch event)

| Field | Value | Notes |
|---|---|---|
| `pair_created_at` | Same as `token_created_at` for initial bonding-curve pair | The bonding curve is created simultaneously with the token on Pump.fun |
| `pair_age_seconds` | `(captured_at - pair_created_at).total_seconds()` | Will equal `token_age_seconds` for the initial pair |
| `pair_age_context_label` | `"RECENT_LAUNCH"` when `token_age_seconds < 86400`; `"OLDER_TOKEN"` otherwise | Computed by existing `_derive_pair_age_context_label()` |

**Note on pair/token age equality at launch:** for a Pump.fun initial launch,
the bonding curve is created in the same transaction as the token. Therefore
`pair_created_at ≈ token_created_at` and the two age fields will be nearly
equal. This is NOT a STNP false signal — it is the correct state for a genuine
new token on its first pair. STNP risk arises only when a pair is young but the
token is old; this case cannot occur for a valid `pumpfun_launch_stream` event.

### 6.3 Source trace fields

| Field | Value |
|---|---|
| `source_name` | `"pumpportal"` |
| `source_channel` (in metadata) | `"pumpfun_launch_stream"` |
| `pool_source` | `"pumpportal"` |
| `dex` | `"pumpfun"` |
| `source_status` | `"COMPLETE"` for valid non-stale events |
| `data_quality_label` | `"CLEAN_DATA"` for valid non-stale events |

### 6.4 Downstream metadata in selection batch

Both of the following fields already exist in `_METADATA_FIELDS` (confirmed
by V2-2P.3) and will carry the T2 evidence into selection-batch persistence:

| Field | Value when T2 evidence present | Value when absent |
|---|---|---|
| `token_age_evidence_tier` | `"T2"` | `None` |
| `pair_age_context_label` | `"RECENT_LAUNCH"` or `"OLDER_TOKEN"` (computed from real token age) | `"RECENT_PAIR_FOR_EXISTING_TOKEN"` or other label (pair-age only) |

---

## 7. Acceptance and Rejection Rules

### 7.1 Acceptance criteria (all must be true)

For T2 evidence from a PumpPortal launch event to populate `token_created_at`:

1. `source_name == "pumpportal"`
2. `request_kind == "pumpfun_launch_stream"` (not migration)
3. `token_mint` is non-empty and represents a valid Solana address
4. At least one of `tokenCreatedAt`, `createdTimestamp`, or `timestamp` is
   present in the event and parses to a valid numeric or ISO-8601 timestamp
5. Parsed `event_timestamp` is not in the future relative to `captured_at`
6. Parsed `event_timestamp` > 0 (not zero or negative)
7. `captured_at - event_timestamp <= 3600 seconds` (not stale)
8. `source_status == COMPLETE` in the normalized result
9. `data_quality_label` is not `MISSING_CRITICAL_DATA`, `STALE_DATA`, or
   `DIRTY_DATA`
10. `token_mint` in the discovery candidate matches the `mint` field in the
    launch event (no cross-mint substitution)
11. Candidate chain is `"solana"` (Solana-only rule)

### 7.2 Rejection rules (any one triggers age-unknown)

Leave `token_created_at = None` and `token_age_evidence_tier = None` when:

| Condition | Reason |
|---|---|
| All three timestamp fields absent from event | Missing evidence — no T2 clock |
| Event timestamp is invalid (zero, negative, non-numeric, unparseable) | Invalid evidence |
| Event timestamp is in the future (`event_timestamp > captured_at`) | Logically impossible; malformed event |
| Staleness exceeded (`captured_at - event_timestamp > 3600 s`) | Stale event; cannot be trusted as recent creation time |
| `request_kind == "pumpfun_migration_stream"` | Migration time ≠ creation time; STNP risk |
| `source_status != COMPLETE` | Source failed or stale |
| `data_quality_label in (MISSING_CRITICAL_DATA, STALE_DATA, DIRTY_DATA)` | Data quality insufficient |
| `token_mint` mismatch between event and candidate | Cross-mint substitution; target mismatch |
| Missing or empty `token_mint` in event | Cannot target the evidence |
| Non-Solana candidate | Chain rule — Solana only |
| Pair-only evidence without launch event | Pair creation time is not token creation time |

### 7.3 Migration events: explicit block

If the Source Governor processes a `pumpfun_migration_stream` event, the
normalization path must:

- NOT populate `token_created_at` from the migration timestamp.
- NOT set `token_age_evidence_tier = "T2"` for migration events.
- May still populate `pair_address` (the new Raydium pool) and other pair
  fields from the migration event.
- May carry the migration event as STNP context (for the Tier 2 discovery
  gate: `PUMPFUN_MIGRATION` is a recognized migration channel in V2-2V).
- Set a `migration_event = True` flag or equivalent in candidate metadata to
  distinguish this from a launch event at the selection-gate level.

---

## 8. Source Governor and Scheduler Boundaries

### 8.1 Source Governor compatibility

The PumpPortal adapter already requires Source Governor approval
(`governor_approved == True` and `execution_path == GOVERNOR_ONLY_EXECUTION_PATH`).
This must remain unchanged. T2 token-age evidence does not relax the Source
Governor boundary.

New source governor expectations:

- All PumpPortal launch calls must go through the existing `PumpPortalAdapter.execute()`
  path with a valid `SourceAdapterContext`.
- Source trace must be recorded via `printer_source_requests`,
  `printer_source_responses`, and `printer_source_failures` exactly as for
  GeckoTerminal and DexScreener calls.
- The `NormalizedSourceResult` with `source_status`, `data_quality_label`,
  and `normalized_payload` must be returned before any candidate normalization
  occurs. Source failures must be surfaced in the failure table, not silently
  dropped.

### 8.2 Bounded collection — no unbounded stream

PumpPortal's `subscribeNewToken` stream is designed as a continuous WebSocket
stream in its full form. For Printer V1, the adapter is `fixture_transport_only`
and the T2 design must preserve this bounded posture.

The implementation design for bounded T2 collection:

- **Mode 1: Fixture-based (proof stage)** — inject a fixed list of pre-collected
  launch events as a fixture transport. No live network calls. Proves the
  normalization contract is correct.

- **Mode 2: Bounded operator-approved one-shot (future public proof)** — a
  Source Governor call that connects to the PumpPortal stream, collects events
  for a bounded time window (e.g., 30 seconds), disconnects, and returns the
  batch. This is operator-triggered only. It must not run continuously.

For both modes, the bounded collection contract is:

| Parameter | Constraint |
|---|---|
| Max events per collection | `max_candidates` as passed by the discovery caller |
| Max collection window | Defined by `stale_after_seconds=60` in registry |
| Connection timeout | 10 seconds to establish connection |
| Event collection timeout | 30 seconds active collection |
| Reconnect on failure | NO — one attempt only; failure returns `FAILED` result |
| Concurrent streams | 0 — only one bounded call at a time |

The transport function that implements Mode 2 must be injected by the caller,
not hard-coded into the adapter. This keeps the adapter shell clean and ensures
no implicit network calls occur when the adapter is instantiated with
`enabled=False` (the default).

### 8.3 Central Scheduler compatibility

The T2 design does not change the Central Scheduler. PumpPortal launch evidence
is collected during the discovery phase, which is governed by the Source Governor
and triggered by the operator command (or bounded discovery loop). No new
scheduler job types are required for T2 evidence.

Central Scheduler boundary rules for this design:

- No new scheduler job kinds.
- No background collection loop for PumpPortal.
- No recurring job that watches the PumpPortal stream between discovery calls.
- Token-level snapshot jobs and memory window close jobs remain higher priority
  than discovery (per AGENTS.md Resource Priority Order, discovery is item 7).

### 8.4 Request budget limits

From `SOURCE_REGISTRY["pumpportal"]`:

| Parameter | Value |
|---|---|
| `default_rate_limit_per_minute` | 30 |
| `stale_after_seconds` | 60 |
| `retry_after_seconds` | 30 |
| `max_retries` | 3 |

For the first T2 implementation (fixture-transport proof only), no live calls
are made. Request budget enforcement becomes relevant only when a bounded live
transport is designed in a subsequent proof lane.

### 8.5 No paid API dependency

PumpPortal's free public streams (`subscribeNewToken`, `subscribeMigration`) are
explicitly listed as allowed free-first sources in `AGENTS.md` (Section "Source
Rules") and `docs/printer-v1-clean-master-spec.md` (Section 0.4). The T2 design
does not depend on any paid PumpPortal API, paid subscription, or paid data tier.

---

## 9. No-Pair-Age-Fallback Invariants

These invariants are hard rules. They must survive any implementation of this
design. Test failure against any of these invariants is a stop condition.

### Invariant 1 — Pair age is never assigned to token age

```python
# FORBIDDEN: any form of this
candidate["token_age_seconds"] = candidate.get("pair_age_seconds")
candidate["token_created_at"] = candidate.get("pair_created_at")
```

There is no exception to this rule, including when `token_age_seconds` is `None`.

### Invariant 2 — `derive_age_bucket` reads token age only

`derive_age_bucket(candidate)` must continue to read
`candidate.get("token_age_seconds")` only. It must not read `pair_age_seconds`,
`pair_created_at`, or any pair-derived field. This function is NOT modified by
the T2 implementation.

### Invariant 3 — A3 requires real token-age evidence

`_tok_age_known = candidate.get("token_age_seconds") is not None` must remain
the A3 gate. It must not be changed to read pair age, pair age context label,
or any fallback. A3 may only fire after a T1/T2/T3 source has populated
`token_age_seconds`.

### Invariant 4 — Pair age cannot unlock A3

No pair-age-derived field (`pair_age_seconds`, `pair_age_context_label`,
`pair_created_at`) may cause `_tok_age_known` to become `True`.

### Invariant 5 — Pair age cannot unlock recent-active tiers

`derive_recent_active_tier(age_bucket, activity_bucket)` reads the age bucket
derived from token age only. An age bucket of `AGE_UNKNOWN` (from unknown token
age) must continue to produce `UNKNOWN_TIER_5` regardless of pair age.

### Invariant 6 — Pair age remains T4 diagnostic only

`pair_age_context_label` must continue to be stored in `candidate_metadata_json`
and reports only. It must never appear in a gate expression that controls
selection, memory creation, retrieval, or paper decisions.

### Invariant 7 — Token age is T5 Unknown if no T1/T2/T3 evidence exists

If no PumpPortal launch event provides a valid timestamp for a given candidate,
`token_age_evidence_tier` must remain `None`, not `"T4"` or any fallback string.
`"T4"` is reserved for pair-age diagnostic context only, and is not a valid
value for `token_age_evidence_tier`.

### Invariant 8 — Migration event timestamp is not token creation time

A migration event from `pumpfun_migration_stream` must never produce a
`token_created_at` mapping. Migration timing represents the migration event,
not the token's birth. Violating this would cause STNP candidates to falsely
appear as new tokens and suppress A3 for old tokens.

---

## 10. Implementation Handoff

This section is a precise contract for the next implementation lane. Nothing
here should be coded before the operator approves an explicit implementation
lane that references V2-2X.1.

### 10.1 Files to change

| File | Change required |
|---|---|
| `src/printer_v1/sources/pumpportal.py` | Extend `_normalize_pumpportal_event` to extract event timestamp as `token_created_at` for launch events only; add staleness check; add invalid-timestamp guard; do not extract `token_created_at` for migration events |
| `src/printer_v1/discovery/parser.py` | Extend the `normalize_candidate()` extraction to accept `token_created_at` from PumpPortal-format candidates (currently reads from `token_created_at` or `tokenCreatedAt` keys — this may already work if PumpPortal normalization writes to `token_created_at`); stamp `token_age_evidence_tier = "T2"` when `source_name == "pumpportal"` and `request_kind == "pumpfun_launch_stream"` and `token_created_at` is present |

### 10.2 Files NOT to change

- `src/printer_v1/discovery/selection_batch.py` — already handles `token_age_evidence_tier` and `pair_age_context_label` via `_METADATA_FIELDS`; no change needed
- `src/printer_v1/discovery/classifier.py` — no A3 change; no age gate change
- `src/printer_v1/operator_cli/commands.py` — no change to `_select_discovery_candidates` or `_classify_returning_candidate`
- Any memory, retrieval, paper decision, or financial path
- Any scheduler or runtime path
- Any DB migration (no new columns needed; `token_created_at` and `token_age_evidence_tier` are already in `NORMALIZED_FIELDS`)

### 10.3 Whether parser update is enough or a PumpPortal adapter change is needed

Both changes are required and are independent:

**PumpPortal adapter change (`pumpportal.py`):**
The current `_normalize_pumpportal_event` function maps a raw PumpPortal event
to a simplified candidate dict. It currently captures `captured_at` or
`timestamp` as a single `captured_at` field. The change must:
1. Check `request_kind == "pumpfun_launch_stream"` before extracting token age.
2. Extract the event timestamp from `tokenCreatedAt` → `createdTimestamp` →
   `timestamp` (priority order).
3. Validate the timestamp (non-null, positive, not in the future, not stale).
4. If valid: include `token_created_at` as the validated event timestamp in
   the returned candidate dict.
5. If invalid or migration event: omit `token_created_at` (or set to `None`).

The returned dict from `_normalize_pumpportal_event` should include:
```python
{
    "chain": "solana",
    "mint": token_mint,
    "pairAddress": pair_address,
    "symbol": ...,
    "name": ...,
    "dex": ...,
    "poolSource": ...,
    "price_usd": ...,
    "liquidity_usd": ...,
    "captured_at": captured_at_iso,
    "token_created_at": event_timestamp_iso,  # NEW — launch events only
    # Note: token_age_evidence_tier is stamped by parser, not by adapter
}
```

**Parser change (`parser.py`):**
The parser's `normalize_candidate()` already reads `token_created_at` from the
candidate dict. The additional change required is to stamp
`token_age_evidence_tier = "T2"` when:
1. `token_created_at` is successfully derived (non-None after `_safe_age_seconds`)
2. `source_name == "pumpportal"` in the candidate
3. `request_kind == "pumpfun_launch_stream"` in the candidate (or inferred
   from `pool_source == "pumpportal"` and `dex == "pumpfun"`)

When these conditions are not all met, `token_age_evidence_tier` remains `None`.

### 10.4 Whether a migration is needed

No DB migration is required. The fields `token_created_at`, `token_age_seconds`,
`token_age_evidence_tier`, and `pair_age_context_label` are all already in
`NORMALIZED_FIELDS` in `parser.py` and in `_METADATA_FIELDS` in
`selection_batch.py`. They are stored in `candidate_metadata_json` (existing
JSON column). No schema change is needed for the first implementation.

### 10.5 Helper names (suggested)

| Helper | Location | Purpose |
|---|---|---|
| `_extract_launch_event_timestamp(event, captured_at)` | `pumpportal.py` | Extract and validate event timestamp; return ISO string or None |
| `_is_stale_launch_event(event_timestamp, captured_at, threshold_seconds)` | `pumpportal.py` | Returns True if event is too old to trust as creation time |
| `_derive_token_age_evidence_tier(source_name, request_kind, token_created_at)` | `parser.py` | Returns "T2" or None based on source path and presence of token creation time |

### 10.6 Tests to add

See Section 11 (Proof/Test Plan).

---

## 11. Proof and Test Plan

All tests must be fixture-first (deterministic; no live source calls) at the
initial implementation stage. A later bounded public proof lane may add a live
PumpPortal connection exercise.

### 11.1 Core T2 evidence mapping tests

| Test | Assertion |
|---|---|
| `test_valid_launch_event_maps_token_created_at` | Valid `pumpfun_launch_stream` event with `tokenCreatedAt` → `token_created_at` populated, `token_age_seconds` computed, `token_age_evidence_tier = "T2"` |
| `test_valid_launch_event_uses_timestamp_fallback` | Event has `timestamp` but not `tokenCreatedAt` → same result |
| `test_migration_event_does_not_populate_token_created_at` | `pumpfun_migration_stream` event with valid timestamp → `token_created_at = None`, `token_age_evidence_tier = None` |
| `test_migration_event_may_populate_pair_address` | `pumpfun_migration_stream` event → `pair_address` from `newRaydiumPool` is present, but no token age |

### 11.2 Timestamp validation tests

| Test | Assertion |
|---|---|
| `test_missing_timestamp_leaves_token_age_unknown` | Launch event with no timestamp fields → `token_created_at = None`, `token_age_evidence_tier = None` |
| `test_zero_timestamp_leaves_token_age_unknown` | Launch event with `timestamp = 0` → `token_created_at = None` |
| `test_negative_timestamp_leaves_token_age_unknown` | Launch event with `timestamp = -1` → `token_created_at = None` |
| `test_future_timestamp_leaves_token_age_unknown` | Launch event with `timestamp` 60 seconds in the future → `token_created_at = None` |
| `test_stale_event_leaves_token_age_unknown` | Launch event with `timestamp` 7200 seconds before `captured_at` → `token_created_at = None`, `source_status = STALE` |
| `test_fresh_event_just_at_staleness_boundary_accepted` | Event within 3600 seconds → accepted |

### 11.3 Pair-age isolation tests

| Test | Assertion |
|---|---|
| `test_pair_age_never_assigned_to_token_age` | Candidate with `pair_age_seconds = 1800` and no `token_age_seconds` → `token_age_seconds = None` explicitly |
| `test_pair_age_does_not_unlock_a3` | Fixture candidate with `pair_age_seconds = 7200`, no `token_age_seconds`, `price_change_1h = -0.3` → A3 does not fire |
| `test_pair_age_does_not_unlock_recent_active_tier` | Candidate with `pair_age_seconds = 300` and `token_age_seconds = None` → `recent_active_tier = UNKNOWN_TIER_5` |
| `test_derive_age_bucket_reads_token_age_only` | `derive_age_bucket({"pair_age_seconds": 300, "token_age_seconds": None})` → `AGE_UNKNOWN` |

### 11.4 A3 gate tests (requires real T2 evidence to fire)

| Test | Assertion |
|---|---|
| `test_a3_fires_only_with_real_token_age` | Candidate with T2 `token_age_seconds = 7200` and `price_change_1h = -0.2` → A3 fires (LATE_BUY_TRAP) |
| `test_a3_does_not_fire_without_token_age` | Same price_change_1h but `token_age_seconds = None` → A3 does not fire |
| `test_a3_does_not_fire_for_recent_token` | `token_age_seconds = 1800` (30 min, below threshold) → A3 does not fire even with negative price change |
| `test_a3_requires_both_token_age_and_price_change` | `token_age_seconds = 7200` but `price_change_1h = None` → A3 does not fire |

### 11.5 Metadata and source trace tests

| Test | Assertion |
|---|---|
| `test_t2_evidence_tier_survives_selection_batch` | Candidate with `token_age_evidence_tier = "T2"` → tier present in `candidate_metadata_json` after `persist_selection_batch()` |
| `test_pair_age_context_label_with_real_token_age` | T2 `token_age_seconds = 1800` → `pair_age_context_label = "RECENT_LAUNCH"` |
| `test_source_trace_complete_for_t2_candidate` | Accepted T2 candidate → `source_name`, `source_status`, `data_quality_label` all present and correct |
| `test_token_mint_mismatch_rejected` | Fixture where event mint ≠ candidate mint → `token_created_at = None` |

### 11.6 Row-delta lock tests

| Test | Assertion |
|---|---|
| `test_t2_evidence_mapping_creates_no_memory_rows` | After full fixture proof cycle: `printer_memory_windows` delta = 0 |
| `test_t2_evidence_mapping_creates_no_retrieval_rows` | `printer_memory_retrieval_queries` delta = 0, `printer_memory_retrieval_matches` delta = 0 |
| `test_t2_evidence_mapping_creates_no_paper_rows` | All paper decision, position, trade event, audit, PnL tables delta = 0 |
| `test_t2_evidence_mapping_creates_no_source_rows_in_fixture_mode` | In fixture mode: `printer_source_requests` delta = 0 (fixture transport does not call live source) |
| `test_persistent_db_hash_unchanged` | Before-hash == after-hash for `data/printer_v1.sqlite3` |

### 11.7 No-source-call proof for fixture stage

All tests in Sections 11.1–11.6 must run without any live HTTP connection.
The PumpPortal adapter uses a `fixture_transport` (injected callable) throughout
the test suite. No `requests`, `websocket`, or `aiohttp` calls should be made.

### 11.8 Later bounded public proof plan (future lane)

After the fixture-first implementation lane passes all tests, a bounded public
proof lane may:

1. Wire a real 30-second bounded WebSocket collection into the PumpPortal
   adapter transport (Mode 2, Section 8.2).
2. Run a Source Governor call to `pumpfun_launch_stream` with `max_candidates=5`.
3. Verify that: at least one T2 candidate has `token_age_seconds` set; no
   migration event populates `token_created_at`; row-delta locks are zero for
   all forbidden tables; `printer_source_requests` records the call.
4. Persistent DB must remain unchanged (proof DB only).

This public proof is NOT part of the current design lane and must not be
attempted until the fixture-first implementation passes.

---

## 12. A3 and Recent-Active Tier Lock Until Proof

A3 and recent-active tiers are already locked at `_tok_age_known = False`
for all live candidates because `token_age_seconds` is universally `None` today
(V2-2K: 0/70 = 0% have token age). This design does not change that reality
for the current production path.

After T2 implementation:

- A3 may fire only for candidates where:
  1. `token_age_seconds is not None` (real evidence: T1, T2, or T3)
  2. `token_age_seconds >= _LATE_BUY_TOKEN_AGE_SECONDS` (currently 3600.0 s)
  3. `price_change_1h < 0` (known negative 1h price change)
  
- Recent-active tiers may produce non-UNKNOWN values only for candidates where
  `token_age_seconds is not None`.

- T2 evidence alone does not create clean memory. A token entering the
  discovery/selection path with T2 age evidence is still subject to all
  existing quality gates (STNP, data quality, source status, tracking queue).

- T2 evidence does not create trading decisions. Discovery/selection is
  intake-only. Memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
  positions, and PnL remain locked.

---

## 13. Safety Confirmations

| Safety gate | Status under this design |
|---|---|
| Solana-only (non-Solana candidates rejected) | INTACT — chain check unchanged |
| Paper-trading-only | INTACT — no financial path changed |
| No live wallet/private keys/real funds | INTACT |
| No paid API dependency | INTACT — PumpPortal free stream only |
| No retrieval activation | INTACT — locked |
| No paper decisions | INTACT — locked |
| No BUY/SELL/HOLD | INTACT — locked |
| No positions, trades, audits, PnL | INTACT — locked |
| Source Governor required for all PumpPortal calls | INTACT — adapter enforces this |
| Central Scheduler not activated | INTACT — no new job types |
| No scoring/ranking/confidence/weighted logic | INTACT — T2 is a categorical tier label |
| No embeddings or vectors | INTACT |
| `WINDOW_5M_MICRO_EVENT` support-only | INTACT |
| `pair_age_seconds` not assigned to `token_age_seconds` | HARD INVARIANT — see Section 9 |
| Migration event timestamp not used as `token_created_at` | HARD INVARIANT — see Section 5.7 |
| `derive_age_bucket` reads token age only | HARD INVARIANT — not modified |
| A3 requires real `token_age_seconds` only | HARD INVARIANT — not modified |
| No DB migration required | CONFIRMED — existing schema sufficient |
| No live source call in fixture stage | CONFIRMED — fixture transport only |
| Memory windows, retrieval, paper rows: zero delta | REQUIRED by test plan |

---

## 14. Money-Usefulness Contribution

Token-age evidence from the T2 PumpPortal path improves Printer's money-
usefulness without creating trading decisions:

### 14.1 Honest age buckets

Today every candidate is `AGE_UNKNOWN`. After T2 implementation, tokens
discovered via PumpPortal launch events will have real `AGE_0_24H` or similar
buckets. This means the memory factory learns which candidate profiles are
genuinely fresh versus unknown-age.

### 14.2 A3 late-buy-trap classification

A3 is currently silent (never fires). When T2 evidence is present and a token
is older than the A3 threshold (1 hour) with a declining 1h price, A3 fires
and classifies the candidate as `LATE_BUY_TRAP`. This adds the most important
capital-protection signal back into discovery selection:

> A token that launched 2 hours ago and is now declining is a late-buy setup.
> Without token age, Printer cannot distinguish this from a new launch.

### 14.3 Recent-active priority

After T2 evidence, selection can prefer `RECENT_ACTIVE_TIER_1` candidates
(recently launched + active) over `UNKNOWN_TIER_5` candidates. This means the
memory diet starts to grow toward genuinely fresh token profiles rather than
a random sample with unknown age.

### 14.4 Separating new launches from old-token/new-pair resurfacing

Tokens resurfacing via PumpPortal migration events are STNP candidates (old
token, new pair). With T2 evidence for launch events, Printer can identify:

- `RECENT_LAUNCH` candidates: real new tokens born today
- Candidates with no T2 evidence: age unknown (may include STNP candidates
  from GeckoTerminal/DexScreener)
- STNP context from Tier 2 gate (V2-2V.1/V2-2W): migration-channel candidates
  are already handled by the discovery persistence gate

### 14.5 Negative learning from late-buy traps

A3's first live firings will produce `LATE_BUY_TRAP` candidates that enter the
memory factory as explicitly labeled trap profiles. This is the most valuable
negative-learning input: not "random old token" but "specifically identified
late-buy-trap setup." Clean trap memory later supports AVOID decisions.

### 14.6 What this does not create

T2 evidence does not create:
- Trading decisions
- Memory windows (memory generation requires separate approved lanes)
- BUY/SELL/HOLD decisions
- Paper positions
- PnL
- Any ranked or scored signal

---

## 15. Remaining Blockers

| Blocker | Status | Impact |
|---|---|---|
| PumpPortal adapter is `fixture_transport_only` | INTENTIONAL DESIGN — live transport not yet wired | T2 fixture proof is possible; bounded public proof requires a new transport lane |
| `pumpfun_launch_stream` events not collected in current discovery runs | CONFIRMED — discovery uses GeckoTerminal and DexScreener today | T2 evidence only enters pipeline when PumpPortal source is activated in a governed bounded call |
| A3 still requires `price_change_1h` which is missing for ~24% of candidates | CARRY-FORWARD from V2-2K | A3 requires BOTH `token_age_seconds` and `price_change_1h`; missing price change still blocks A3 for those candidates |
| No Pump.fun tokens appear from GeckoTerminal/DexScreener with T2 age | CONFIRMED — those sources don't carry launch timestamps | T2 evidence only flows from PumpPortal launch events specifically |
| T3 Solana RPC / Helius enrichment not designed | DEFERRED — separate future lane | Non-PumpPortal tokens still have unknown age after T2 |
| V2-2R Rules 3/4/5/6 unimplemented (carry-forward from V2-2J) | CONFIRMED | Source concentration, evidence freshness gate, fair-aging remain future work |
| V2-3, V2-4, source expansion, memory generation, retrieval, paper decisions remain paused | CONFIRMED | This design does not unlock any of those |

---

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk or blocker | Effect | Mitigation |
|---|---|---|
| PumpPortal stream timing not reliable enough as T2 | If PumpPortal delays event delivery significantly, captured T2 age is biased | Staleness threshold (3600 s) blocks old events; log discrepancy for audit |
| Migration event mistakenly treated as launch event | Old token gets false RECENT_LAUNCH label; A3 suppressed | Hard invariant: `request_kind == "pumpfun_migration_stream"` → never maps to `token_created_at`; migration test required |
| `captured_at` mistakenly mapped to `token_created_at` | Understates age by network latency | Design explicitly blocks this; separate fields required |
| Stale event batch (reconnection replay) provides old launch events | Stale launch event mapped as current → age inflated | Staleness check gates on `captured_at - event_timestamp > 3600 s` |
| Token appears on GeckoTerminal before PumpPortal event arrives | No T2 evidence for the first GeckoTerminal discovery of that token | Acceptable: token gets `AGE_UNKNOWN`, no T2 mapped. A later discovery cycle with PumpPortal evidence can provide T2. |
| Only PumpPortal-launched tokens get T2 evidence | Non-Pump.fun Solana tokens remain AGE_UNKNOWN | T3 Solana RPC is the fallback for non-Pump.fun tokens; T3 is a separate future lane |
| PumpPortal launch stream not available every run | Discovery runs using only GeckoTerminal/DexScreener still produce all-AGE_UNKNOWN batches | Acceptable; T2 evidence is additive, not required for every run |
| Test suite does not exercise real PumpPortal format | Fixtures may not match real event schema | Fixture events must reflect documented PumpPortal API fields; bounded public proof required before any real-data claims |
| `price_change_1h` still missing for many candidates | A3 cannot fire even with T2 age if 1h price is unknown | Carry-forward; A3 requires both fields and already correctly returns no result when either is absent |
| `_fingerprint_change_type()` reporting nuance (carry-forward from V2-2W) | Over-broad `primary_bucket_group_crossing` label | Non-blocking; safety gate is correct |

---

## 17. Next Recommended Lane

**Recommended: V2-2X.2 — T2 Token-Age Evidence Implementation and Fixture Proof**

### Reasoning

This design (V2-2X.1) defines the complete contract for T2 evidence from
PumpPortal launch events. The next step is implementation and fixture proof,
which is a narrow and well-bounded task:

1. Extend `_normalize_pumpportal_event` in `pumpportal.py` to extract and
   validate the launch event timestamp, mapping it to `token_created_at` for
   launch events only.
2. Extend `normalize_candidate` in `parser.py` to stamp `token_age_evidence_tier
   = "T2"` when PumpPortal launch evidence is present.
3. Write the fixture-first test suite (Section 11).
4. Pass all existing test suites (regression).
5. Confirm row-delta locks.
6. Write a bounded proof/closeout doc.
7. Commit only the implementation files, test file, and proof doc.

This is NOT an activation of the live PumpPortal stream. It is a parser/adapter
extension that can be exercised entirely with fixture transports.

### Conservative conditions on V2-2X.2

1. Implementation only: `pumpportal.py` and `parser.py` only. No memory,
   retrieval, paper, or financial paths.
2. Fixture-transport test only: no live network calls.
3. No DB migration: existing schema is sufficient.
4. All existing test suites must still pass (regression check).
5. No activation of PumpPortal as a default READY source (still disabled by
   default in the adapter).
6. Row-delta locks must be confirmed: zero delta for all memory, retrieval,
   paper, financial, source, and scheduler tables in tests.

### Why not a bounded public proof first?

A bounded public proof requires wiring a live WebSocket transport, which is a
larger scope change than the parser/normalization fix. The fixture implementation
proves the normalization contract is correct before any live network dependency
is introduced. Fixture-first is the safer sequence.

---

## 18. Git Checks

Run immediately before committing this doc:

```
git diff --check      → CLEAN (LF→CRLF warning only, no whitespace errors)
git status --short    → design doc only; all other changes untracked/not staged
git diff --stat       → no modified tracked files
git diff --name-only  → no modified tracked files
```

Committed files: `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md` only.

Not committed: `data/`, `operator-runs/`, proof DBs, temp files, unrelated
lane output `.txt` files.

---

## 19. Final Design Verdict

```
DESIGN_VERDICT: DESIGN_COMPLETE_WITH_BLOCKERS
CHOSEN_FIRST_SOURCE_PATH: T2 — governed PumpPortal launch-event timing
SOURCE_NAME: pumpportal
REQUEST_KIND: pumpfun_launch_stream
T2_EVIDENCE_FIELD_PRIORITY: tokenCreatedAt → createdTimestamp → timestamp
MIGRATION_EVENTS: BLOCKED from populating token_created_at
STALENESS_THRESHOLD: 3600 seconds
PAIR_AGE_FALLBACK: HARD BLOCKED — no exception
A3_UNLOCK_REQUIREMENT: real token_age_seconds from T1/T2/T3 only
DB_MIGRATION_REQUIRED: NO
LIVE_TRANSPORT_REQUIRED: NO (fixture-first implementation only)
IMPLEMENTATION_SCOPE: pumpportal.py + parser.py only
NEXT_RECOMMENDED_LANE: V2-2X.2 — T2 Token-Age Evidence Implementation and Fixture Proof
V2_3_STATUS: PAUSED
MEMORY_GENERATION: LOCKED
RETRIEVAL: LOCKED
PAPER_DECISIONS: LOCKED
BUY_SELL_HOLD: LOCKED
POSITIONS_TRADES_AUDITS_PNL: LOCKED
```
