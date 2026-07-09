# Printer V1 V2-2O Token Age / AGE_UNKNOWN Evidence Repair Design

Status: `DESIGN`

Final verdict:

`V2-2O Token Age / AGE_UNKNOWN Evidence Repair Design: DESIGN_COMPLETE_WITH_BLOCKERS`

V2-2J and V2-3 remain paused. This document is design-only. No implementation,
migration, live source fetch, scheduler execution, memory generation, retrieval,
paper decision, position, trade, audit, or PnL path is activated here.

---

## Todo / Checklist

- [x] Read V2-2K audit: token-age field completeness (Section 9), age-bucket
      breakdown (Section 8), A3 blocking evidence (Section 10)
- [x] Read V2-2N bounded proof: remaining blockers (Section 13)
- [x] Read V2-2N.1 fixture proof: remaining blockers (Section 11)
- [x] Inspect `parser.py`: token_created_at extraction keys, `_safe_age_seconds`,
      `pair_created_at` extraction, `token_age_seconds` derivation
- [x] Inspect `selection_batch.py`: `derive_age_bucket`, `derive_recent_active_tier`,
      A3 gate, `_tok_age_known` flag, `_LATE_BUY_TOKEN_AGE_SECONDS`
- [x] Inspect `classifier.py`: WATCH_ONLY classification paths
- [x] Inspect `geckoterminal.py`: field surface — confirmed `pair_created_at`
      present, `token_created_at` absent
- [x] Review source capability matrix from V2-2K Section 2
- [x] Document evidence-tier hierarchy (5 tiers)
- [x] Document pair-age vs token-age separation rules and STNP risk
- [x] Propose safe age labels
- [x] Map repairs to: recent-active priority, A3, STNP interpretation,
      memory-diet selection
- [x] Write implementation handoff spec
- [x] Write proof requirements
- [x] Write money-usefulness contribution
- [x] Write what this improves / does not unlock
- [x] Write functionality risks / setbacks / efficiency blockers
- [x] Write next recommended lane

---

## 1. Current Blocker Summary

| Blocker | Observed | Evidence |
|---|---|---|
| `token_created_at` absent | 70 / 70 (100%) | V2-2K Section 9; GeckoTerminal + DexScreener |
| `token_age_seconds` None | 70 / 70 (100%) | V2-2K Section 9; parser derives from missing field |
| `age_bucket` always `AGE_UNKNOWN` | 70 / 70 (100%) | V2-2K Section 8 |
| `recent_active_tier` always `UNKNOWN_TIER_5` | 70 / 70 (100%) | V2-2K Section 8 |
| A3 gate never fires | 0 / 70 (0%) | V2-2K Section 10; `_tok_age_known` always False |
| `pair_age_seconds` available | 69 / 70 (98.6%) | V2-2K Section 9; derived from `pool_created_at` |
| Pair age not safe as token-age substitute | Design rule | STNP risk; one token can have many pairs |

### Root cause

Neither GeckoTerminal nor DexScreener exposes a `token_created_at` (or
equivalent) field in their current candidate-level API responses. The parser
searches for keys `("token_created_at", "tokenCreatedAt")`; neither key is
present in any live response observed through V2-2K. `_safe_age_seconds(None,
now)` returns `None` unconditionally. `derive_age_bucket(candidate)` returns
`AGE_UNKNOWN` when `candidate.get("token_age_seconds")` is `None`.
`derive_recent_active_tier(age_bucket, activity_bucket)` returns `UNKNOWN_TIER_5`
whenever `age_bucket == AGE_UNKNOWN`.

Pair age (`pair_age_seconds`) is derived from `pool_created_at`, which
GeckoTerminal does include in pool-level attributes. This field is present for
69 of 70 observed candidates. However, pair age and token age represent
different things: a pair is created when liquidity is deployed for that
token-pair combination. A token can persist across multiple pairs over its
lifecycle (same-token/new-pair, abbreviated STNP). Using pair age as a direct
substitute for token age would silently misclassify older tokens with new pairs
as recent launches, potentially enabling late-buy-trap decisions on established
tokens.

---

## 2. Evidence Tier Hierarchy

This hierarchy defines the trustworthiness levels of any age signal from highest
to lowest. Only evidence at Tier 1–3 may be mapped to `token_age_seconds` for
use in age-gated logic such as `derive_age_bucket`, `derive_recent_active_tier`,
or A3. Tier 4 signals may inform safe contextual labels only. Tier 5 is the
current universal state.

### Tier 1 — Confirmed token age from source response

Source: a future discovery source or an enrichment path that explicitly returns
the token's original creation timestamp (not the pair/pool creation timestamp).

Concrete paths that could supply T1 evidence:
- Solana RPC `getAccountInfo` for the mint account (`mintTimestamp` or
  `blockTime` of the initialization transaction);
- Helius free-tier enrichment returning a verified token launch time;
- A future PumpPortal or PumpSwap feed that carries the canonical on-chain
  token creation event.

Current availability: 0%. Neither GeckoTerminal nor DexScreener returns this.
GeckoTerminal `pool_created_at` is a pool creation field, not a token creation
field. DexScreener returns `pairCreatedAt` for the pair, not the token.

Mapping rule: when Tier 1 is present, map it to `token_created_at` in the
normalized candidate and let the existing `_safe_age_seconds` / `derive_age_bucket`
pipeline run unchanged. No new gate logic is required at this tier.

### Tier 2 — Source-observed launch age from event timing

Source: a real-time launch-event feed (PumpPortal launch stream) where the
event arrival timestamp is a direct or near-direct proxy for the token's
creation time, because the event is only emitted at token creation.

Current availability: 0%. Both PumpPortal and PumpSwap are `NOT_READY`. This
tier is a future capability, not a current repair.

Mapping rule: when Tier 2 is present and the source is the launch-event feed,
map to `token_created_at` with an annotation `token_age_evidence_tier = T2`.
The age bucket and A3 gate may use this value but reporting must surface the
evidence tier so operators can evaluate confidence.

### Tier 3 — Onchain / mint-derived age (secondary reference path)

Source: Solana RPC or Helius queried out-of-band during discovery or at a
post-discovery enrichment step. The mint account's creation slot / block time
provides a reliable token-origin timestamp for any SPL token.

Current availability: 0% (no current enrichment call wired into discovery).
Solana RPC is registered as a source reference, not a discovery feed.

Mapping rule: when Tier 3 is present from a governed RPC enrichment step, map
to `token_created_at` with `token_age_evidence_tier = T3`. The age bucket and
A3 gate may use this value. The governed enrichment call budget and request
tracking must be defined before implementation.

### Tier 4 — Pair-age-only context (must not drive age-gated logic)

Source: `pool_created_at` (GeckoTerminal) or `pairCreatedAt` (DexScreener),
already surfaced as `pair_age_seconds` in the current normalized candidate.

Current availability: 98.6% (69 of 70 candidates in V2-2K).

Mapping rule: Tier 4 evidence MUST NOT be written to `token_age_seconds`. It
MUST NOT drive `derive_age_bucket`. It MUST NOT be used to evaluate A3. It MAY
be exposed as a separate `pair_age_context_label` field for diagnostic and
reporting purposes, with an explicit STNP caveat. See Section 3 for separation
rules and Section 4 for safe labels.

### Tier 5 — Unknown token age (current universal state)

All fields derived from token creation timestamp are absent. `token_age_seconds`
is `None`. `age_bucket` is `AGE_UNKNOWN`. `recent_active_tier` is
`UNKNOWN_TIER_5`. A3 does not fire.

Current availability: 100% of observed candidates.

No age-gated logic may fire. The candidate remains selectable by activity and
liquidity gates but cannot contribute to A3 or recent-active priority ordering.

---

## 3. Token Age vs Pair Age Separation Rules

### Why pair age must never replace token age

A Solana SPL token has a single creation transaction on-chain. Its token address
(mint) was created at a specific block time. A pair (liquidity pool) is created
separately when an operator or automated market maker deploys liquidity for that
token against a quote asset. One token can have many pairs across its lifecycle:

- initial launch pair (Raydium or Pump.fun AMM, very young);
- migration pair (token moves from Pump.fun to Raydium / PumpSwap);
- new listing pair on a second DEX months later.

If pair age is mapped to `token_age_seconds`, the system would observe a very
young pair and classify a potentially months-old token as a recent launch. A3
(`_LATE_BUY_TOKEN_AGE_SECONDS = 3600.0`) would then fail to fire for an old
token being relisted in a new pair, creating a false "safe window" signal for a
candidate that the system should treat with late-buy caution.

This is the STNP (Same Token New Pair) risk. It is the core reason the current
design explicitly does not map `pair_age_seconds` to `token_age_seconds`.

### Separation rules

1. `token_age_seconds` MUST remain `None` whenever `token_created_at` is absent.
2. `pair_age_seconds` MUST remain in its own normalized field and must never be
   assigned to `token_age_seconds`, even when `token_created_at` is absent.
3. `derive_age_bucket(candidate)` reads `token_age_seconds` only.
4. A3 reads `_tok_age_known = candidate.get("token_age_seconds") is not None`.
   This check MUST NOT be changed to fall back to `pair_age_seconds`.
5. `derive_recent_active_tier` reads the age bucket derived from token age only.
6. Any pair-age-derived context must be labeled with its tier (T4) and must
   carry an explicit STNP caveat in all reporting surfaces.
7. Implementation-level guard: if a future contributor attempts to map
   `pair_age_seconds` to `token_age_seconds` as a "good enough" fallback, the
   test suite must reject it via an STNP fixture proof (see Section 8).

### What pair age IS safe for

- Diagnostic field reporting in discovery reports and audit documents.
- A new `pair_age_context_label` field (see Section 4) surfaced in candidate
  metadata for operator visibility.
- Pool-freshness signals that do not influence age-bucket classification or A3.
- Future STNP-detection heuristics if a multi-pair evidence model is designed
  with explicit STNP handling (a separate future lane, not this design).

---

## 4. Safe Age Labels

These labels are for reporting and context surfaces only. They do not drive
`derive_age_bucket`, `derive_recent_active_tier`, or A3. They are proposed as a
new optional field `pair_age_context_label` in the normalized candidate and in
selection-batch metadata, surfacing in discovery reports and future audit docs.

| Label | Condition | Interpretation |
|---|---|---|
| `RECENT_LAUNCH` | `token_age_seconds` known AND `< 86400` (< 24 h) | Confirmed recent token. T1/T2/T3 evidence required. A3 eligible (age < threshold, safe early-window). |
| `RECENT_PAIR_FOR_EXISTING_TOKEN` | `token_age_seconds` unknown AND `pair_age_seconds` known AND `pair_age_seconds < 86400` | New pair exists; token age unknown. STNP risk present. Operator should not treat this as RECENT_LAUNCH. |
| `OLDER_TOKEN` | `token_age_seconds` known AND `>= 86400` (≥ 24 h) | Confirmed non-recent token. T1/T2/T3 evidence required. A3 potentially eligible (check exact threshold). |
| `UNKNOWN_TOKEN_AGE` | `token_age_seconds` unknown AND `pair_age_seconds` unknown | No age signal at all. Both fields absent. Report as full unknown. |
| `PAIR_ONLY_AGE_KNOWN` | `token_age_seconds` unknown AND `pair_age_seconds` known AND `pair_age_seconds >= 86400` | Pair is not new. Token age unknown. No STNP early-launch false signal; pair age consistent with older or stable deployment. |

At current coverage (V2-2K):
- 69 of 70 candidates would be labeled `RECENT_PAIR_FOR_EXISTING_TOKEN` or
  `PAIR_ONLY_AGE_KNOWN` based on their `pair_age_seconds` values.
- 1 of 70 candidates would be `UNKNOWN_TOKEN_AGE` (pair_age_seconds also absent).
- Zero candidates would be `RECENT_LAUNCH` or `OLDER_TOKEN`.

These labels require no schema migration. They are computed at normalization or
selection-reporting time and stored in `candidate_metadata_json` or emitted in
the discovery report. No new DB column is needed in the initial implementation.

---

## 5. How This Repairs Downstream Capabilities

### 5.1 Recent-active priority

Current state: all candidates are `UNKNOWN_TIER_5` because `age_bucket` is
always `AGE_UNKNOWN`. The system cannot prefer recently launched or recently
revived tokens over older ones.

Repair path (requires T1, T2, or T3 evidence):
- Once `token_created_at` is available, `derive_age_bucket` produces
  `AGE_0_24H` / `AGE_1_7D` / etc. for qualifying candidates.
- `derive_recent_active_tier` then produces `RECENT_ACTIVE_TIER_1`,
  `RECENT_ACTIVE_TIER_2`, or `OLDER_ACTIVE_TIER_3` for those candidates.
- Selection ordering can rank Tier 1/2 candidates above Tier 3/4/5.

What pair-age context alone unlocks (Tier 4, no T1/T2/T3 evidence):
- Pair-age labels (`PAIR_ONLY_AGE_KNOWN`, `RECENT_PAIR_FOR_EXISTING_TOKEN`)
  are surfaced in reports for operator review.
- These labels MUST NOT drive selection priority ordering because they do not
  distinguish new pairs from old tokens-with-new-pairs.
- The age bucket remains `AGE_UNKNOWN` for all Tier 4 cases.

### 5.2 A3 eligibility

Current state: A3 never fires because `_tok_age_known` is always `False`.
A3 is the late-buy-trap gate: tokens older than `_LATE_BUY_TOKEN_AGE_SECONDS`
(3600.0 s = 1 hour) with a declining 1h price change should be rejected as
`LATE_BUY_TRAP`. Without token age, no candidate is assessed for this risk.

Repair path (requires T1, T2, or T3 evidence only):
- Once `token_age_seconds` is available, `_tok_age_known` becomes `True` for
  those candidates.
- A3 can fire against candidates where age >= 3600.0 s AND price_change_1h < 0.
- Candidates with confirmed recent age (< 3600 s) are correctly passed through
  without A3 penalty.

CRITICAL: Pair age (Tier 4) MUST NOT be used to unlock A3. An old token with a
new pair would appear young by pair age, causing A3 to fail to fire exactly when
it should. This is the highest-stakes STNP consequence.

`price_change_1h` is also required for A3. V2-2K found `price_change_1h`
missing for 17 of 70 candidates (24.3%). A3 requires BOTH fields populated.

### 5.3 STNP interpretation

Current state: the system has no mechanism to detect or flag STNP candidates.
All candidates are treated uniformly with no age context.

Repair path (Tier 4, available now with pair age):
- The `RECENT_PAIR_FOR_EXISTING_TOKEN` label flags the case where a young pair
  exists but token age is unknown, prompting operator awareness.
- `PAIR_ONLY_AGE_KNOWN` flags candidates whose pair is not new.
- Neither label causes any gate to fire; they are diagnostic only.

Full STNP detection (future, beyond this lane):
- Comparing `pair_age_seconds` to a multi-pair history for the same mint would
  allow the system to identify repeated pair-creation events.
- This requires either persistent per-mint pair history or an external RPC query.
- Out of scope for V2-2O.

### 5.4 Memory-diet selection balance

Current state: `UNKNOWN_TIER_5` candidates fill the entire selected batch.
Recent and revival-tier candidates cannot be distinguished from stale ones.
The memory diet receives no age signal, so memory growth is not biased toward
more-valuable recently active token profiles.

Repair path (requires T1/T2/T3):
- Once age buckets are real, selection can balance recent vs. older active
  candidates as designed in the spec.
- `RECENT_ACTIVE_TIER_1` (recent + HIGH/MEDIUM activity) would rank above
  `OLDER_ACTIVE_TIER_3` in selection preference.

Pair-age context alone (Tier 4) does not unlock this balance because
`UNKNOWN_TIER_5` remains the assigned tier for all Tier 4 candidates.

---

## 6. Implementation Handoff Specification

This section defines exactly what must be built in a future implementation lane.
It is a contract, not a task. Nothing here should be coded until an operator
approves an implementation lane that explicitly references V2-2O.

### 6.1 New normalized fields

Add the following to `NORMALIZED_FIELDS` in `parser.py`:

| Field | Type | Derivation | Notes |
|---|---|---|---|
| `token_age_evidence_tier` | `str \| None` | Set to `"T1"`, `"T2"`, or `"T3"` when `token_created_at` is populated from a tier-qualified source; `None` otherwise | Stored per-candidate in normalized output |
| `pair_age_context_label` | `str \| None` | Compute from `token_age_seconds`, `pair_age_seconds` using the label table in Section 4 | Never drives age gates |

The existing fields `token_age_seconds`, `pair_age_seconds`, `token_created_at`,
and `pair_created_at` remain unchanged. No field is renamed or removed.

`token_age_evidence_tier` must be stamped in the plan loop in `commands.py`
using the same H.6 per-candidate pattern as `source_status` and
`data_quality_label`, once a T1/T2/T3 source path is wired.

### 6.2 Report fields

The `build_discover_candidates_once_payload` report section should include:

- `token_age_evidence_tier_counts`: `{"T1": int, "T2": int, "T3": int, "T4": int, "T5_UNKNOWN": int}`
- `pair_age_context_label_counts`: `{"RECENT_LAUNCH": int, "RECENT_PAIR_FOR_EXISTING_TOKEN": int, ...}`
- `tok_age_known_count`: count of candidates where `token_age_seconds is not None`
- `pair_age_known_count`: count of candidates where `pair_age_seconds is not None`

### 6.3 Selection-batch metadata

In `candidate_metadata_json` for each selection-batch item, add:

- `token_age_evidence_tier`: the tier string or `null`
- `pair_age_context_label`: the label string or `null`
- `age_bucket`: existing derived field, already intended for metadata

These fields are observation-only. They must not trigger any new selection gate.

### 6.4 Field-completeness reporting

Extend the field-completeness section of discovery reports to include:

| Field | Missing | Missing % | Target |
|---|---|---|---|
| `token_created_at` | ? | ? | 0% when T1/T2/T3 source active |
| `token_age_seconds` | ? | ? | Mirrors `token_created_at` |
| `pair_created_at` | ? | ? | Should remain ≤ 1.4% |
| `pair_age_seconds` | ? | ? | Should remain ≤ 1.4% |
| `token_age_evidence_tier` | ? | ? | `null` acceptable until T1/T2/T3 active |

### 6.5 Parser changes

In `normalize_candidate()` (`parser.py`):

1. After computing `token_age_seconds`, compute `pair_age_context_label` by
   calling a new `_derive_pair_age_context_label(token_age_seconds, pair_age_seconds)`.
2. Accept an optional `token_age_evidence_tier` kwarg (or candidate-dict field)
   from the stamping loop. Default to `None`.
3. Return both new fields in the normalized dict alongside existing fields.
4. No existing logic changes. No existing field renamed.

`_derive_pair_age_context_label(token_age_seconds, pair_age_seconds)`:
```
if token_age_seconds is not None and token_age_seconds < 86400:
    return "RECENT_LAUNCH"
if token_age_seconds is not None:
    return "OLDER_TOKEN"
if pair_age_seconds is None:
    return "UNKNOWN_TOKEN_AGE"
if pair_age_seconds < 86400:
    return "RECENT_PAIR_FOR_EXISTING_TOKEN"
return "PAIR_ONLY_AGE_KNOWN"
```

This function is pure and side-effect-free. It is independently testable
without touching any gate or selection logic.

### 6.6 No migration required

All new fields are stored in `candidate_metadata_json` or emitted in report
JSON. No new DB columns, no new tables, no schema migration. The persistent DB
hash must remain unchanged throughout implementation.

### 6.7 No gate changes for Tier 4

The following must NOT be modified during V2-2O implementation:
- `derive_age_bucket` — continues to read `token_age_seconds` only
- `derive_recent_active_tier` — continues to read age bucket from token age only
- A3 gate (`_tok_age_known`) — continues to check `token_age_seconds is not None`
- `_LATE_BUY_TOKEN_AGE_SECONDS` — unchanged at `3600.0`

---

## 7. Proof Requirements

Any future implementation lane implementing V2-2O must pass four proofs before
operator acceptance.

### Proof A — Deterministic fixture proof: age gates and labels

Purpose: demonstrate that token age gates (`derive_age_bucket`, A3, recent-active
tier) work correctly when T1 evidence is present.

Requirements:
- Fixture candidate with `token_age_seconds = 1800` (30 min, below A3 threshold):
  - `age_bucket = AGE_0_24H`
  - `recent_active_tier != UNKNOWN_TIER_5`
  - A3 does not fire (age < threshold)
  - `pair_age_context_label = RECENT_LAUNCH`
- Fixture candidate with `token_age_seconds = 7200` (2 h, above A3 threshold) and
  `price_change_1h < 0`:
  - `age_bucket = AGE_0_24H`
  - A3 fires: candidate rejected as `LATE_BUY_TRAP`
- Fixture candidate with `token_age_seconds = None` and `pair_age_seconds = 1800`:
  - `age_bucket = AGE_UNKNOWN`
  - A3 does not fire (`_tok_age_known = False`)
  - `pair_age_context_label = RECENT_PAIR_FOR_EXISTING_TOKEN`
  - `recent_active_tier = UNKNOWN_TIER_5`

### Proof B — Bounded governed source proof: pair-age coverage

Purpose: confirm that `pair_age_seconds` continues to be available for ≥ 95%
of GeckoTerminal candidates after implementation changes (regression check).

Requirements:
- Live governed call to GeckoTerminal (new-pool or trending).
- Count `pair_age_seconds is not None` vs. total candidates.
- Assert coverage ≥ 95%.
- Persistent DB hash unchanged.

### Proof C — STNP safety proof

Purpose: prove that a fixture token with an old creation date but a new pair
does not produce a false `RECENT_LAUNCH` label or enable A3 to fail to fire.

Requirements:
- Fixture candidate: `token_age_seconds = 2_592_000` (30 days), `pair_age_seconds = 3600` (1 h).
  - `age_bucket = AGE_14_28D`
  - `pair_age_context_label = PAIR_ONLY_AGE_KNOWN` (pair is not new; token known as old)
  - Wait: this fixture has token_age_seconds known, so label is `OLDER_TOKEN`. Correct.
  - `recent_active_tier = OLDER_ACTIVE_TIER_3` (if activity qualifies)
- Fixture candidate: `token_age_seconds = None`, `pair_age_seconds = 3600` (1 h).
  - `age_bucket = AGE_UNKNOWN`
  - `pair_age_context_label = RECENT_PAIR_FOR_EXISTING_TOKEN` (pair is fresh, token unknown)
  - A3: does NOT fire (`_tok_age_known = False`)
  - `recent_active_tier = UNKNOWN_TIER_5`
  - Explicit assertion: `pair_age_seconds` is NOT assigned to `token_age_seconds`
  - Explicit assertion: `pair_age_context_label != "RECENT_LAUNCH"`

### Proof D — Row-delta lock proof

Purpose: confirm V2-2O implementation creates no downstream rows.

Requirements:
- Counts for all active and downstream tables must remain unchanged or match
  expected active-candidate-only deltas.
- Specifically: `printer_memory_windows`, `printer_paper_decisions`,
  `printer_paper_positions`, and all PnL-adjacent tables: all zero delta.
- `pair_age_context_label` and `token_age_evidence_tier` fields stored only in
  `candidate_metadata_json` or report JSON — no new columns.
- Persistent DB SHA-256 must match the before-hash exactly.

---

## 8. Money-Usefulness Contribution

The Printer V1 system earns its usefulness by identifying memecoins with
memory-worthy behavior early enough that the memory diet remains fresh and
actionable. Token age is a primary signal in this calculus:

1. **Late-buy-trap prevention**: A3 blocks candidates where the token is already
   old and the price is declining. Without token age, A3 never fires, meaning
   potentially stale late-movers may enter the batch unchallenged.

2. **Diet balance**: A memory diet of only `UNKNOWN_TIER_5` candidates cannot
   prioritize genuinely recent launches or reviving tokens. Recent-active priority
   (Tiers 1 and 2) is the primary mechanism for ensuring the memory factory grows
   windows on high-value, time-sensitive profiles.

3. **Quota integrity**: The `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET` quota
   violation (observed in V2-2K and V2-2N) occurs partly because A3 never fires
   to create the trap-failure bucket. Resolving token age is a precondition for
   producing quotas that pass without forcing.

4. **STNP risk surface**: By labeling `RECENT_PAIR_FOR_EXISTING_TOKEN` candidates,
   the system surfaces a risk class that currently passes silently. Operators
   monitoring the diet can see when new-pair candidates might be older tokens
   seeking new liquidity, rather than genuine new launches.

---

## 9. What This Improves and Does Not Unlock

### What V2-2O implementation would improve

- Parser: adds `pair_age_context_label` and `token_age_evidence_tier` fields;
  labels are always computable from existing normalized data.
- Reports: token-age coverage summary visible per discovery run.
- Audit docs: future audits can report actual label distribution, not just
  `AGE_UNKNOWN` uniformly.
- STNP visibility: `RECENT_PAIR_FOR_EXISTING_TOKEN` flags high-risk candidates
  that previously had no label.
- Test coverage: STNP fixture proof closes the gap where pair-age silently
  substituted for token age would go undetected.

### What V2-2O does NOT unlock

| Capability | Reason not unlocked |
|---|---|
| Real `AGE_0_24H` / `AGE_1_7D` buckets in live batches | Requires T1/T2/T3 source evidence; GeckoTerminal/DexScreener do not provide it |
| Real `RECENT_ACTIVE_TIER_1` / `TIER_2` candidates | Derived from token age buckets; blocked until T1/T2/T3 present |
| A3 firing in live batches | Blocked until T1/T2/T3 token age present; pair age cannot unlock A3 |
| Quota violation `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET` resolved | A3 must fire to produce the trap-failure bucket |
| STNP detection (multi-pair history) | Separate future lane; requires per-mint pair history |
| PumpPortal / PumpSwap token age (T2 evidence) | Both sources remain NOT_READY |
| Solana RPC / Helius enrichment (T3 evidence) | Not a current discovery path; requires governed enrichment design |

---

## 10. Functionality Risks / Setbacks / Efficiency Blockers

### Risk 1 — T1/T2/T3 source evidence remains absent after implementation

V2-2O implementation adds labels and report fields but does not activate any new
evidence source. The tier labels will all resolve to `null` (`T5`) unless a
T1/T2/T3 source is activated in a subsequent lane. This means `AGE_UNKNOWN` and
`UNKNOWN_TIER_5` remain the live batch reality even after V2-2O is implemented.
The repair's value is forward-looking (when evidence arrives, the pipeline is
ready) and diagnostic (labels surface STNP risk today with pair age).

### Risk 2 — STNP label misread as age-gate signal

If a future contributor reads `RECENT_PAIR_FOR_EXISTING_TOKEN` and treats it as
equivalent to `RECENT_LAUNCH`, they may attempt to enable A3 or recent-active
priority based on pair age. The test suite must include an explicit assertion that
pair age does not modify `_tok_age_known` (Proof C, assertion 3 above). This risk
is mitigated by naming the label to emphasize its STNP context, not the age class.

### Risk 3 — `pair_age_context_label = RECENT_LAUNCH` computed incorrectly

The `_derive_pair_age_context_label` function produces `RECENT_LAUNCH` when
`token_age_seconds is not None and token_age_seconds < 86400`. If a future
source returns an invalid or zero `token_age_seconds`, the label could misfire.
The Proof A fixture must include an edge case with `token_age_seconds = 0` to
confirm the label and age bucket behavior.

### Risk 4 — Parser normalization not called for all candidates in the audit-only path

Audit-only candidates are captured before persistence but after normalization.
The V2-2M.2 stamping of `source_status` and `data_quality_label` proved that
per-candidate stamping must happen inside the plan loop. `pair_age_context_label`
and `token_age_evidence_tier` should be computed during normalization (not
post-normalization stamping) to ensure consistent coverage across active and
audit-only paths.

### Efficiency blocker — Pair-age context label requires `pair_age_seconds` to be accurate

`pair_age_seconds` is derived from `pool_created_at` via `_safe_age_seconds`.
The current GeckoTerminal adapter returns `pool_created_at` from pool attributes.
If GeckoTerminal changes its response shape, `pool_created_at` could go missing.
The existing field-completeness check currently shows 1.4% missing; a future
regression could increase this. The Proof B bounded check (≥ 95% coverage) is
designed to detect this.

---

## 11. Implementation Anchors and Source Stack

| Item | Value |
|---|---|
| V2-2K audit | `2cd7940` |
| V2-2N bounded proof | `04cb35f` |
| V2-2N.1 fixture proof | `2ef9ed2` |
| Parser inspection path | `src/printer_v1/discovery/parser.py` |
| Selection-batch inspection path | `src/printer_v1/discovery/selection_batch.py` |
| Classifier inspection path | `src/printer_v1/discovery/classifier.py` |
| GeckoTerminal adapter path | `src/printer_v1/sources/geckoterminal.py` |

Source documents consulted for this design:
- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md`
- `docs/printer-v1-v2-2l-watch-only-d1-quota-handoff-design.md`
- `docs/printer-v1-v2-2n-watch-only-d1-handoff-bounded-proof.md`
- `docs/printer-v1-v2-2n-1-d1-selection-batch-audit-only-proof.md`

---

## 12. Next Recommended Lane

V2-2J and V2-3 remain paused.

The immediate next safe step is V2-2J closeout. V2-2J should consolidate V2-2K,
V2-2N, and V2-2N.1 findings and explicitly preserve the broader token-age,
native-15m, A3/A4, and source-coverage blockers. V2-2J must record this V2-2O
design as the approved repair design for the token-age blocker, and decide
whether token-age implementation is inside V2-2 or carries into a later approved
lane.

After V2-2J:
- A V2-2O implementation lane could be opened once an operator approves the
  implementation handoff spec in Section 6. That lane implements the parser
  changes, contextual labels, and report fields, but does NOT activate any new
  T1/T2/T3 evidence source.
- A separate T1/T2/T3 evidence source lane would wire in an actual token-age
  data path: PumpPortal launch stream (T2) or Solana RPC / Helius enrichment (T3)
  would be the first practical choices. This lane cannot run until the
  NOT_READY feeds are unblocked or an enrichment budget is designed.

V2-2N proof of a persisted selection batch containing A3-fired candidates cannot
be created until T1/T2/T3 evidence is available in the discovery pipeline.

---

## 13. Final Verdict

`V2-2O Token Age / AGE_UNKNOWN Evidence Repair Design: DESIGN_COMPLETE_WITH_BLOCKERS`

The design is complete. All structural blockers are documented. The evidence-tier
hierarchy, pair-age vs token-age separation rules, safe age labels, downstream
repair paths, implementation handoff spec, and proof requirements are defined and
ready for a future implementation lane.

Blockers that remain after this design:

1. `token_created_at` is absent from all current GeckoTerminal and DexScreener
   responses. V2-2O implementation delivers the plumbing and labels; it does not
   deliver live token-age evidence.
2. A3 remains blocked until T1/T2/T3 evidence is live in the pipeline. Pair age
   (T4) must never be used to unblock A3.
3. `RECENT_ACTIVE_TIER_1` and `RECENT_ACTIVE_TIER_2` candidates cannot appear in
   live batches until T1/T2/T3 evidence is live.
4. The `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET` quota violation cannot be
   resolved by this design alone.
5. STNP multi-pair detection is out of scope for V2-2O.
6. PumpPortal and PumpSwap feeds remain NOT_READY.
