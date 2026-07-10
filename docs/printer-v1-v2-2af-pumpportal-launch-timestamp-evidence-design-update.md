# Printer V1 V2-2AF PumpPortal Launch Timestamp Evidence Design Update

**Lane:** V2-2AF
**Type:** Design only — no implementation, no live source calls, no code changes
**Verdict:** `DESIGN_COMPLETE_WITH_BLOCKERS`
**Date:** 2026-07-10
**Executor:** Claude Sonnet 4.6

V2-3, V2-4, implementation lanes, source activation, runtime/scheduler, memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, and PnL remain paused. This document is design-only.

---

## 1. Source Stack Read

| Document | Role |
|---|---|
| `AGENTS.md` | Highest authority |
| `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md` | T2 evidence contract (Section 4–9 hard invariants) |
| `docs/printer-v1-v2-2ae-pumpportal-live-event-diagnostics.md` | Payload shape evidence from live PumpPortal stream |
| `docs/printer-v1-v2-2ad-bounded-live-pumpportal-smoke-proof.md` | Earlier bounded live smoke proof |
| `docs/printer-v1-v2-2ac-pumpportal-websockets-dependency-gate.md` | Dependency gate proof |
| `docs/printer-v1-memory-growth-build-order-v2.md` | V2 roadmap |

Design anchors confirmed:

| Anchor | Commit | Content |
|---|---|---|
| V2-2AA design | `447e3fc` | Minimal PumpPortal launch-stream transport design |
| V2-2AD smoke proof | `0106417` | Bounded live smoke inconclusive (no events in window) |
| V2-2AE diagnostics | `9f9562c` | 4 mint-bearing events; 0 timestamp fields present |

---

## 2. V2-2AE Finding Summary

V2-2AE ran one bounded diagnostic live PumpPortal `pumpfun_launch_stream` call
through Source Governor against an isolated proof DB. It received 5 raw
WebSocket messages. One was a subscription acknowledgement with no `mint` field.
Four were mint-bearing token launch events that normalized as PumpPortal
candidates.

**Critical finding:** none of the 4 mint-bearing launch events contained any
of the three timestamp fields accepted by the T2 contract:

| Field | Count in 4 events |
|---|---:|
| `tokenCreatedAt` | 0 |
| `createdTimestamp` | 0 |
| `timestamp` | 0 |

Fields that WERE present in launch events:

```
bondingCurveKey, initialBuy, is_mayhem_mode, marketCapSol, mint, name, pool,
signature, solAmount, symbol, traderPublicKey, txType, uri,
vSolInBondingCurve, vTokensInBondingCurve
```

**Consequence:** the current T2 normalization path (V2-2X.1 Section 5.3) leaves
`token_created_at = None`, `token_age_seconds = None`, and
`token_age_evidence_tier = None` for all 4 events. T2 evidence is blocked for
live PumpPortal `subscribeNewToken` events as they arrive today.

This is not a connection failure, not a subscription failure, and not a
normalization failure. The events are valid launch events. The payload shape
does not include an explicit source-provided token creation timestamp.

**Sample count caveat:** V2-2AE observed 4 events across one 30-second window.
This is not a statistically large sample. PumpPortal may add timestamp fields
in a future API version, or some event types might include them. The design in
this document must remain valid regardless of whether PumpPortal adds timestamps
later.

---

## 3. Hard Rule: T2 Preservation

**T2 must remain: explicit source-provided token creation timestamp only.**

PumpPortal live receipt/observation time must not be called T2 unless the
source payload includes an explicit accepted timestamp field
(`tokenCreatedAt`, `createdTimestamp`, or `timestamp` in priority order per
V2-2X.1 Section 5.1).

This rule is not negotiable and is not relaxed by this design.

Consequences:
- `captured_at` from Source Governor must never map to `token_created_at`.
- `captured_at` must never set `token_age_evidence_tier = "T2"`.
- The T2 acceptance criteria (V2-2X.1 Section 7.1, criteria 4–7) are unchanged.
- The 9 hard invariants in V2-2X.1 Section 9 are unchanged.

Rationale (from V2-2X.1 Section 5.2):
- Network latency between on-chain event and Source Governor processing
  introduces bias that cannot be quantified per-event.
- Batch collection delays (processing a queue of events) could make
  `captured_at` minutes after the true creation time.
- Using `captured_at` as creation time would understate token age, producing
  false "just launched" evidence.

These hazards are not removed by the fact that the PumpPortal stream is
typically low-latency. Per-event latency cannot be guaranteed, so the design
cannot assume it.

---

## 4. Lower-Tier Evidence Decision

**Decision: YES — introduce `OBSERVED_LIVE_LAUNCH` as a new lower-tier label.**

### 4.1 Rationale for adding a lower tier

When Printer receives a mint-bearing `subscribeNewToken` event from PumpPortal:

1. The event fires at token creation time on-chain. PumpPortal rebroadcasts
   it in real-time via WebSocket. Network delivery is typically seconds.
2. `captured_at` (Source Governor receipt time) is therefore a very close
   upper bound on how old the token is at the moment Printer receives it.
3. The token CANNOT be younger than `captured_at` (a token cannot exist before
   it is observed). The token CAN be slightly older than `captured_at`
   indicates by the delivery latency.
4. A token observed in this stream is almost certainly less than 60 seconds old
   at observation time under normal conditions.

This is meaningfully different from pair age:
- Pair age can be days or weeks old for an existing token that migrated or
  relisted. It can never safely proxy token age.
- `OBSERVED_LIVE_LAUNCH` is uniquely available only when Printer directly
  observed the creation event on the stream. It is far more informative than
  pair age or any other indirect signal.

This is also meaningfully different from T2:
- T2 uses the source-provided timestamp to bound token age from above (explicit
  creation time).
- `OBSERVED_LIVE_LAUNCH` uses the observation time to provide an upper bound on
  token age — the token cannot be younger than what was observed, but may be
  slightly older.

The lower tier is useful for:
- Distinguishing "Printer observed this token being created live" from
  "Printer found this token via pair-age discovery with unknown token age."
- Reports and diagnostics: annotating that a candidate came from the live stream
  even when T2 evidence was absent.
- Future implementation lanes that want to use `captured_at` as an
  upper-bound-only age indicator without conflating it with `token_created_at`.

### 4.2 Label name decision

**Label: `OBSERVED_LIVE_LAUNCH`**

Rejected alternatives and reasons:

| Label | Reason rejected |
|---|---|
| `T2_OBSERVED_LIVE` | "T2" prefix implies T2 contract is satisfied. It is not. |
| `T2B` | Same problem. Implies T2 variant. Causes confusion in grep and docs. |
| `T_OBS` | Cryptic. Does not convey what it is. |
| `T4` | Reserved for pair-age diagnostic context only (V2-2X.1 Invariant 7). |

`OBSERVED_LIVE_LAUNCH` was chosen because:
- It contains no "T2" substring — prevents accidental conflation with T2.
- It is self-describing: the token was observed live in a launch event.
- It is distinct in grep/log/search from all existing tier labels.
- It signals intent without implying a numbered tier hierarchy.

---

## 5. Field and Metadata Design

### 5.1 Fields for `OBSERVED_LIVE_LAUNCH` candidates

| Field | Value | Rationale |
|---|---|---|
| `token_created_at` | `None` | MUST NOT be populated from observation time. Never an exception. |
| `token_age_seconds` | `None` | MUST NOT be computed from observation time. |
| `token_age_evidence_tier` | `"OBSERVED_LIVE_LAUNCH"` | New valid value — signals live observation without implying explicit creation timestamp. |
| `captured_at` | Source Governor receipt time (already stored) | Already set by `_normalize_pumpportal_event()`. Serves as the observation timestamp for OBSERVED_LIVE_LAUNCH evidence. No separate field needed — `captured_at` IS the observation record. |
| `pair_age_context_label` | Computed from pair age if pair timestamp available; otherwise existing rules | Unchanged from current logic |

**Why no separate `observed_live_launch_at` field?**

`captured_at` already records when Source Governor processed the event. For
`OBSERVED_LIVE_LAUNCH` evidence, `captured_at` IS the observation timestamp.
Adding a separate `observed_live_launch_at` field would be redundant. Downstream
readers that need the observation time should read `captured_at`.

**Critical invariant:** `token_created_at` must remain `None` for any
`OBSERVED_LIVE_LAUNCH` candidate. Setting `token_created_at = captured_at`
is forbidden by the same rationale as T2 — it would understate token age
and produce false creation-time evidence.

### 5.2 Selection batch persistence

`token_age_evidence_tier` is already in `_METADATA_FIELDS` (V2-2P.3 confirmed).
The value `"OBSERVED_LIVE_LAUNCH"` will flow into `candidate_metadata_json`
via the existing selection batch path without schema changes.

No new columns, no migrations, no schema changes.

### 5.3 Precedence rule: T2 beats OBSERVED_LIVE_LAUNCH

If a future PumpPortal payload includes an explicit timestamp (`tokenCreatedAt`,
`createdTimestamp`, or `timestamp`), T2 evidence takes precedence:

- Set `token_created_at` from the event timestamp.
- Set `token_age_evidence_tier = "T2"`.
- Do NOT set `OBSERVED_LIVE_LAUNCH`.

The precedence rule in the implementation must check for T2 fields FIRST. Only
if all three T2 fields are absent from the launch event should the normalizer
fall through to stamping `OBSERVED_LIVE_LAUNCH`.

### 5.4 Qualifier conditions for OBSERVED_LIVE_LAUNCH

`OBSERVED_LIVE_LAUNCH` must only be set when ALL of the following are true:

1. `source_name == "pumpportal"` — source trace confirmed
2. `request_kind == "pumpfun_launch_stream"` — not a migration event
3. `token_mint` is non-empty — event represents an identifiable token
4. None of `tokenCreatedAt`, `createdTimestamp`, `timestamp` was present in
   the event (i.e., T2 evidence was absent — if any T2 field is present, use T2)
5. `source_status == COMPLETE` — Source Governor accepted the result
6. `data_quality_label` is not `MISSING_CRITICAL_DATA`, `STALE_DATA`, or
   `DIRTY_DATA` — response quality was acceptable

If any of these conditions fails, `token_age_evidence_tier` remains `None`.

### 5.5 OBSERVED_LIVE_LAUNCH is not set for migration events

A `pumpfun_migration_stream` event MUST NOT produce `OBSERVED_LIVE_LAUNCH`.
The observation time for a migration event does not bound the token's age —
it bounds only the migration time. The token could be days old at the migration
event. This distinction is critical.

The implementation check `request_kind == "pumpfun_launch_stream"` (condition 2
above) enforces this.

---

## 6. A3 Impact

**A3 is NOT unlocked by `OBSERVED_LIVE_LAUNCH` evidence.**

A3 (late-buy-trap signal) requires:

```python
_tok_age_known = candidate.get("token_age_seconds") is not None
```

`OBSERVED_LIVE_LAUNCH` evidence leaves `token_age_seconds = None`. Therefore
`_tok_age_known` remains `False` for all `OBSERVED_LIVE_LAUNCH` candidates.
A3 cannot fire.

This is correct behavior:
- A3 fires for old tokens (age ≥ 3600 seconds) with falling price. It is a
  late-buy-trap warning.
- A token observed live in the `subscribeNewToken` stream is almost certainly
  seconds old. A3 for a freshly launched token would be a false positive, not
  a meaningful signal.
- Even if we wanted A3 to fire on `OBSERVED_LIVE_LAUNCH` tokens based on
  re-evaluation time (i.e., checking the token again hours later), that design
  requires a separate implementation lane that explicitly defines how to track
  `observed_launch_at` vs. current re-evaluation time. This is not in scope.

**V2-2X.1 Invariant 3 is unchanged:**

```
_tok_age_known = candidate.get("token_age_seconds") is not None
```

must remain the A3 gate. It must not be changed to check
`token_age_evidence_tier == "OBSERVED_LIVE_LAUNCH"`. A3 may only fire after a
T1/T2/T3 source has populated `token_age_seconds`.

**V2-2X.1 Invariant 4 is unchanged:**

No pair-age-derived field and no observation-tier field may cause
`_tok_age_known` to become `True`.

---

## 7. Safety Confirmations

### 7.1 T2 contract safety

- V2-2X.1 Invariants 1–9 are all preserved.
- `token_created_at` can only be set from explicit source-provided event
  timestamps in the T2 priority order. `captured_at` never maps to it.
- `OBSERVED_LIVE_LAUNCH` is a distinct label value; it does not alias `"T2"`.
- `derive_age_bucket()` reads `token_age_seconds` only. Since `token_age_seconds`
  remains `None` for `OBSERVED_LIVE_LAUNCH` candidates, `derive_age_bucket`
  returns `AGE_UNKNOWN`. Unchanged.

### 7.2 STNP / migration safety

Migration events are never qualified as `OBSERVED_LIVE_LAUNCH`. The
`request_kind == "pumpfun_launch_stream"` gate is the enforcement mechanism.
A migration event's `captured_at` can never indicate token creation time and is
not used as such.

### 7.3 Cross-mint safety

`OBSERVED_LIVE_LAUNCH` evidence is per-candidate, derived from the
mint-bearing launch event for a specific `token_mint`. No cross-mint
substitution is possible because each candidate is normalized independently
from its own event.

### 7.4 No new schema dependencies

The value `"OBSERVED_LIVE_LAUNCH"` is a string stored in the existing
`token_age_evidence_tier` field. No new columns, no DB migrations, no new
registry entries, no new source kinds.

### 7.5 No financial path impact

- No BUY/SELL/HOLD unlocked.
- No paper decision unlocked.
- No position, trade, or PnL impact.
- No memory generation or retrieval change.
- No scheduler change.

### 7.6 `enabled_by_default` unchanged

PumpPortal adapter `enabled_by_default = False` is unchanged. The
`OBSERVED_LIVE_LAUNCH` label is irrelevant until the adapter is operator-enabled
with a transport.

---

## 8. Implementation Handoff

This section defines what must change in a future approved implementation lane.
Nothing here is implemented now.

### 8.1 Files to change

| File | Change |
|---|---|
| `src/printer_v1/sources/pumpportal.py` | In `_normalize_pumpportal_event()`: after checking T2 fields (and finding all absent), set `"live_observed_launch": True` on the normalized event for mint-bearing `pumpfun_launch_stream` events. This flag is read by the parser to stamp the tier. |
| `src/printer_v1/discovery/parser.py` | In `normalize_candidate()` or the PumpPortal-specific branch: if `source_name == "pumpportal"` and `request_kind == "pumpfun_launch_stream"` and `token_created_at is None` (no T2 evidence) and `event.get("live_observed_launch")` is True and `token_mint` is non-empty → set `token_age_evidence_tier = "OBSERVED_LIVE_LAUNCH"`. T2 must be checked first; `OBSERVED_LIVE_LAUNCH` is the fallback. |

### 8.2 Files NOT to change

- `src/printer_v1/discovery/selection_batch.py` — `token_age_evidence_tier` already in `_METADATA_FIELDS`; no change
- `src/printer_v1/discovery/classifier.py` — A3 gate unchanged
- `src/printer_v1/operator_cli/commands.py` — no change
- Any memory, retrieval, paper decision, financial, scheduler, or runtime path
- DB schema — no new columns

### 8.3 Tests required in the implementation lane

| Test | Assertion |
|---|---|
| `test_observed_live_launch_tier_set_for_mint_bearing_event` | mint-bearing `pumpfun_launch_stream` event with no timestamp fields → `token_age_evidence_tier == "OBSERVED_LIVE_LAUNCH"`, `token_created_at is None`, `token_age_seconds is None` |
| `test_t2_takes_precedence_over_observed_live_launch` | mint-bearing event WITH a `timestamp` field → `token_age_evidence_tier == "T2"`, `OBSERVED_LIVE_LAUNCH` not set |
| `test_observed_live_launch_not_set_for_migration_event` | `request_kind == "pumpfun_migration_stream"` event → `token_age_evidence_tier is None`, even if mint is present |
| `test_observed_live_launch_not_set_for_ack_message` | subscription acknowledgement with no `mint` → does not produce a token candidate at all |
| `test_observed_live_launch_not_set_for_missing_mint` | event with no `mint` field → `token_age_evidence_tier is None` |
| `test_token_created_at_not_populated_from_captured_at` | confirmed: `token_created_at` remains `None` even when `OBSERVED_LIVE_LAUNCH` is set |
| `test_a3_does_not_fire_for_observed_live_launch_candidate` | A3 gate check: `_tok_age_known` is `False` when `token_age_evidence_tier == "OBSERVED_LIVE_LAUNCH"` |
| `test_observed_live_launch_tier_survives_to_metadata` | `OBSERVED_LIVE_LAUNCH` string appears in `candidate_metadata_json` via selection batch |

### 8.4 Live proof requirement after implementation

After the implementation lane completes, another bounded live PumpPortal
diagnostic run is required to confirm:
- `token_age_evidence_tier = "OBSERVED_LIVE_LAUNCH"` is set on real received
  events (not just fixture events).
- `token_created_at` remains `None` in all live candidates.
- `captured_at` is correctly recorded as the observation timestamp.

This live proof is deferred to a future lane, not this design.

### 8.5 Approved label values for `token_age_evidence_tier`

After this design, the complete vocabulary is:

| Value | Meaning |
|---|---|
| `None` | No token-age evidence; could be GeckoTerminal/DexScreener candidate with pair age only |
| `"T2"` | Explicit source-provided token creation timestamp from PumpPortal launch event |
| `"OBSERVED_LIVE_LAUNCH"` | Mint-bearing `subscribeNewToken` event observed live; no explicit creation timestamp; `captured_at` is observation time |

`"T1"` (Solana on-chain creation slot) and `"T3"` (RPC enrichment) remain
deferred and are not introduced by this design.

---

## 9. Remaining Blockers

| Blocker | Status |
|---|---|
| T2 unavailable — live PumpPortal events contain no accepted timestamp fields | CONFIRMED (V2-2AE) |
| `OBSERVED_LIVE_LAUNCH` implementation not yet built | DEFERRED — needs approved implementation lane |
| `OBSERVED_LIVE_LAUNCH` live proof not yet run | DEFERRED — runs after implementation |
| A3 remains blocked for PumpPortal candidates until T2 is available | INTENTIONAL |
| `pumpfun_migration_stream` remains `NOT_READY` | INTENTIONAL |
| V2-3 remains paused | INTENTIONAL |

---

## 10. Exact Next Recommended Lane

**V2-2AG — OBSERVED_LIVE_LAUNCH Tier Implementation**

Scope:
1. Change `_normalize_pumpportal_event()` in `pumpportal.py` to set
   `live_observed_launch = True` on mint-bearing `pumpfun_launch_stream` events
   when no T2 timestamp fields are present.
2. Change `normalize_candidate()` in `parser.py` to stamp
   `token_age_evidence_tier = "OBSERVED_LIVE_LAUNCH"` when
   `live_observed_launch` is True and T2 evidence is absent.
3. Write all 8 tests listed in Section 8.3.
4. Run focused test suites:
   - `tests/test_v2_2ab_pumpportal_live_transport.py`
   - `tests/test_post_rc_pumpportal_discovery_adapter.py`
   - `tests/test_v2_2x2_t2_token_age_evidence.py`
5. Run git diff/status checks.
6. Commit only changed files.
7. Proof report: `docs/printer-v1-v2-2ag-observed-live-launch-tier-implementation.md`
8. Commit message: `Add V2-2AG OBSERVED_LIVE_LAUNCH tier implementation`

Pre-conditions:
- V2-2AF committed (this document).
- No live source calls in the implementation lane.
- No A3 unlocking.
- No migration events touched.

---

## 11. V2-3 Status

**V2-3 remains PAUSED.**

No retrieval, no memory generation, no scheduling, no scoring, no paper
decisions, no BUY/SELL/HOLD were introduced or enabled in this design.

`OBSERVED_LIVE_LAUNCH` is a tier label only. It does not open any path to V2-3
work. V2-3 resumes only when the operator explicitly approves V2-3 scope with
full build-order context.

---

## 12. Final Verdict

`DESIGN_COMPLETE_WITH_BLOCKERS`

V2-2AF establishes:

1. T2 is confirmed blocked for live PumpPortal events — no explicit timestamp
   fields observed in V2-2AE sample.
2. T2 remains exactly as defined in V2-2X.1 — explicit source-provided
   timestamp only. This rule is not weakened or relaxed.
3. A new lower-tier label `OBSERVED_LIVE_LAUNCH` is approved for mint-bearing
   `subscribeNewToken` events where T2 evidence is absent.
4. `OBSERVED_LIVE_LAUNCH` does NOT populate `token_created_at` or
   `token_age_seconds`. Both remain `None`.
5. `captured_at` is the observation record for `OBSERVED_LIVE_LAUNCH` evidence.
   No new field is needed — `captured_at` already carries this information.
6. A3 is not unlocked. `_tok_age_known` requires `token_age_seconds is not None`.
7. Migration events are categorically excluded from `OBSERVED_LIVE_LAUNCH`.
8. Implementation is deferred to V2-2AG.

V2-3 remains paused.
