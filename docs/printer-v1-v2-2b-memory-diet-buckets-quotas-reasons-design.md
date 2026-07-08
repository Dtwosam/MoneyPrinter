# Printer V1 V2-2B — Memory-Diet Buckets / Quotas / Reasons Design

**Type:** Design documentation only.

**Status:** Design only. This document does not implement code, run discovery, fetch
sources, mutate a DB, create memory, activate retrieval, create paper decisions, unlock
BUY/SELL/HOLD, open paper positions, create trade events, create paper trade audits, or
create PnL.

**Date:** 2026-07-08

**Prerequisite:** `V2-2A — Audit current discovery/selection pipeline`
Commit: `6d493a5 Add V2-2A discovery selection pipeline audit`

**Active build order:** `docs/printer-v1-memory-growth-build-order-v2.md`

---

## Todo / Checklist

- [x] Read AGENTS.md
- [x] Read docs/printer-v1-clean-master-spec.md
- [x] Read docs/printer-v1-post-rc-build-order.md
- [x] Read docs/printer-v1-memory-factory-guide.md
- [x] Read docs/printer-v1-current-state-memory-growth-audit.md
- [x] Read docs/printer-v1-memory-growth-build-order-v2.md
- [x] Read docs/printer-v1-assistant-active-build-order-anchor.md
- [x] Read docs/printer-v1-v2-2a-discovery-selection-pipeline-audit.md
- [x] Write this design document

---

## 1. Lane Boundary Confirmation

**Current lane:** `V2-2B — Design memory-diet buckets/quotas/reasons`

Allowed in this lane:

- Design documentation.
- Bucket taxonomy definition.
- Quota policy.
- Selection reason policy.
- Same-token/new-pair policy design.
- WATCH_ONLY / TRACK_NORMAL / TRACK_FAST selection semantics.
- Cooldown / archive / reopen design.
- Proof/test plan for V2-2C and V2-2D.

Not allowed in this lane:

- Source code edits.
- Test edits.
- Migrations.
- DB mutation.
- Discovery runs.
- Source fetching.
- Scheduler or runtime commands.
- Memory generation.
- Retrieval activation.
- Paper decisions.
- BUY / SELL / HOLD.
- Paper positions.
- Trade events.
- Paper trade audits.
- PnL.
- Scoring / ranking / confidence / weighted logic.
- Embeddings / vectors.
- Live wallet / private keys / real funds / live execution.
- Paid APIs.

---

## 2. Design Inputs From V2-2A

V2-2A found the following gaps that this design must address:

- No durable selection-batch table for X6/X10.6 output. Reasons exist in artifacts only.
- No active memory-diet quota policy.
- WATCH_ONLY, cooldown, archive, and reopen exist as lifecycle tools but have no Memory
  Factory selection semantics.
- Same-token/new-pair behavior is detected in X6/X10.6 but not yet expressed as a
  durable contract.
- TRACK_FAST candidates dominate early proofs; losers, traps, dead tokens, and revivals
  have no quota protection.
- Trending-token bias is structurally possible because no quota caps trending sources.
- X10.6 can emit empty outputs when not fed a candidate list, making the handoff fragile.

V2-2B does not repair these gaps in code. It specifies how the repairs should work so
V2-2C (implementation) and V2-2D (bounded proof) have a clear specification to follow.

---

## 3. Memory-Diet Bucket Taxonomy

### Design Principles

All buckets are categorical. No bucket is a score, rank, or confidence percentage.
A token belongs to exactly one primary bucket per selection batch. Sub-labels are
allowed as supplementary notes but do not override the primary bucket assignment.

Buckets exist to teach Printer what the full range of Solana memecoin outcomes looks like,
not to predict which tokens are good investments. Every bucket — winners and losers alike
— serves the goal of building realistic paper-only comparison memory.

A token that produces DIRTY_MEMORY or PARTIAL_MEMORY in a bounded proof is still a valid
learning example. Failed memories teach realistic boundary behavior. Memory-diet balance
requires intentional sampling of failure cases.

### Bucket Group A — Fast-Event / High-Activity Buckets

Tokens in Group A were classified TRACK_FAST by the discovery classifier. They showed
strong initial activity signals. Group A must not dominate any memory-diet batch because
these tokens represent only one part of the memecoin outcome distribution.

| Bucket ID | Name | Primary Signal | Example Discovery Label | Notes |
|-----------|------|---------------|------------------------|-------|
| A1 | FAST_PUMP_FOLLOW | Fast pump with sustained follow-through beyond discovery time | HOT_PAIR, high volume + price + txn | The "winner" case. Must be quota-capped. |
| A2 | WICK_ONLY_PUMP | Fast spike with immediate reversal; no continuation | TRACK_FAST with rapid stale signal | Price peak visible in payload but no volume follow-through. |
| A3 | LATE_BUY_TRAP | Strong activity at discovery time; momentum already dissipated when tracked | TRACK_FAST with age > ideal entry | Appears as fast mover but entry was too late. |
| A4 | FAILED_PUMP | Pump started but collapsed before any sustainable follow-through | TRACK_FAST then rapid WATCH_ONLY or stale | No recovery after initial move. Classic failed pump profile. |

**Group A quota rule:** No more than 40% of any batch may be Group A tokens.
At least 1 Group A slot in any batch of 5+ must be A2, A3, or A4 (not A1).

### Bucket Group B — Normal-Activity / Slow-Moving Buckets

Tokens in Group B were classified TRACK_NORMAL or WATCH_ONLY. They showed normal or
quiet market behavior. Group B is the anti-bias complement to Group A.

| Bucket ID | Name | Primary Signal | Example Discovery Label | Notes |
|-----------|------|---------------|------------------------|-------|
| B1 | VOLUME_RISING | Sustained volume building without fast-event trigger | TRACK_NORMAL with increasing volume windows | Captures slow appreciation without pump signal. |
| B2 | VOLUME_DECAYING | Previously active token with falling volume | TRACK_NORMAL post-peak | Teaches decay behavior and exit-timing learning. |
| B3 | TRANSACTION_SPIKE | Sudden txn count spike without proportional price action | TRACK_NORMAL or TRACK_FAST with txn spike only | Decoupled txn/price behavior is a distinct learning case. |
| B4 | TRANSACTION_DECAY | Falling transaction count over time | WATCH_ONLY or late TRACK_NORMAL | Token losing trader interest. |
| B5 | CONSOLIDATION | Price / volume in tight range, no clear direction | TRACK_NORMAL with flat payload fields | Baseline neutral behavior. Teaches WAIT and NO_ACTION cases. |

**Group B quota rule:** Group B must represent at least 30% of any batch of 6+ tokens.
At least 1 Group B slot must be B2 or B4 (decay behavior).

### Bucket Group C — Liquidity-State Buckets

Liquidity fields are normalized in all discovery payloads. Group C buckets isolate
liquidity as the primary behavioral signal.

| Bucket ID | Name | Primary Signal | Example Source Fields | Notes |
|-----------|------|---------------|-----------------------|-------|
| C1 | LIQUIDITY_RISING | Measurable liquidity increase observed in source payloads | `liquidity_usd` increasing across sequential payloads | Low-risk early tracking candidate for baseline memory. |
| C2 | LIQUIDITY_FALLING | Measurable liquidity decline during tracking window | `liquidity_usd` decreasing across payloads | Critical teaching example for capital-protection memory. |
| C3 | LIQUIDITY_REMOVED | Sharp liquidity drop; potential rug or abandon signal | `liquidity_usd` near zero in payload | High-risk event. Must be tracked with WATCH_ONLY or fail-fast TRACK_NORMAL. |

**Group C quota rule:** Any batch of 8+ tokens should include at least 1 Group C token.
C3 (LIQUIDITY_REMOVED) requires explicit operator note in the selection reason because
it is a safety-sensitive event and must not be selected to test BUY timing.

### Bucket Group D — Lifecycle / State-Change Buckets

Group D captures tokens whose identity or state is changing. These require special
handling in the same-token/new-pair policy (see Section 7).

| Bucket ID | Name | Primary Signal | Example Source / Lifecycle Context | Notes |
|-----------|------|---------------|-------------------------------------|-------|
| D1 | DEAD_TOKEN | Effectively zero volume and liquidity; stale or failed | WATCH_ONLY, stale payload, zero txn count | Core protection memory. Teaches what dead looks like. |
| D2 | REVIVAL | Previously archived/cooldown token showing new activity | Lifecycle REOPEN event with new pair or new volume | Teach that dead tokens can re-emerge. Distinct from MIGRATION. |
| D3 | MIGRATION_EVENT | Same token mint, new pair address (pool migration) | `MIGRATION_EVENT` in source channel; pair drift detected | Must be treated as new evidence cycle (see Section 7). |
| D4 | SUSPICIOUS_SAFETY | Abnormal authority flags, blacklist signal, or safety-risk pattern | X10.6 safety-risk context tag | Evidence only; no BUY/paper decisions from suspicious tokens. |

**Group D quota rule:** Any batch of 6+ tokens must include at least 1 D1 (DEAD_TOKEN).
D4 (SUSPICIOUS_SAFETY) may be included at most 1 per batch; selection reason must explain
the safety signal and confirm it is included for protection-memory learning, not entry-timing.

### Bucket Group E — Exit-Evidence Buckets

Group E tokens are not selected primarily for entry behavior. They are selected to build
memory about what exit conditions looked like at window close.

| Bucket ID | Name | Primary Signal | Notes |
|-----------|------|---------------|-------|
| E1 | REALISTIC_EXIT | Price / liquidity at 15m window end was plausibly exitable; no extreme slippage implied | Selected from tokens where volume remained nonzero through window close. |
| E2 | UNREALISTIC_EXIT | Chart shows profit at peak but realistic exit was impossible due to liquidity or slippage | Selected specifically when peak was visible in payload but later payloads show liquidity collapse. |

**Group E quota rule:** At most 2 Group E tokens per batch. Group E is supplementary
to Group A-D, not a replacement. Group E tokens may overlap with another primary bucket
(e.g., A2 with E2) — in that case the primary bucket assignment wins; E is an annotation.

### Bucket Group F — Correct/Wrong Avoidance and Wait Buckets

Group F captures counterfactual learning cases. These are tokens the system classified
as high-risk or low-priority and where the outcome either vindicated or contradicted
that classification.

| Bucket ID | Name | Primary Signal | Notes |
|-----------|------|---------------|-------|
| F1 | CORRECT_AVOID | Token was avoided; later evidence shows token died, was a trap, or had no follow-through | Validates avoidance classification. |
| F2 | WRONG_AVOID | Token was avoided; later evidence shows it continued meaningfully upward | Teaches where AVOID over-fired. |
| F3 | CORRECT_WAIT | A wait decision (no entry) was vindicated by the outcome | Teaches patience value and WAIT as a valid state. |
| F4 | WRONG_WAIT | A wait cost a genuine opportunity (token continued without a second entry) | Teaches the cost of over-cautious inaction. |

**Group F quota rule:** Group F tokens are optional in early batches. They require
prior memory windows to be meaningful (can only classify F1/F2/F3/F4 if a prior run
produced evidence for the same token). V2-2C may treat Group F as a future bucket that
activates only once the corpus has at least 10 clean memory windows.

---

## 4. Consolidated Bucket Reference Table

| Bucket ID | Name | Group | Min per batch (6+ tokens) | Max % of batch | Lane affinity |
|-----------|------|-------|--------------------------|----------------|---------------|
| A1 | FAST_PUMP_FOLLOW | Fast-event | 0 | 25% | TRACK_FAST |
| A2 | WICK_ONLY_PUMP | Fast-event | 0 | 20% | TRACK_FAST |
| A3 | LATE_BUY_TRAP | Fast-event | 0 | 20% | TRACK_FAST |
| A4 | FAILED_PUMP | Fast-event | 0 | 20% | TRACK_FAST |
| B1 | VOLUME_RISING | Normal-activity | 0 | 25% | TRACK_NORMAL |
| B2 | VOLUME_DECAYING | Normal-activity | 1 | 25% | TRACK_NORMAL |
| B3 | TRANSACTION_SPIKE | Normal-activity | 0 | 20% | TRACK_NORMAL or TRACK_FAST |
| B4 | TRANSACTION_DECAY | Normal-activity | 0 | 20% | TRACK_NORMAL or WATCH_ONLY |
| B5 | CONSOLIDATION | Normal-activity | 0 | 20% | TRACK_NORMAL |
| C1 | LIQUIDITY_RISING | Liquidity | 0 | 20% | TRACK_NORMAL or TRACK_FAST |
| C2 | LIQUIDITY_FALLING | Liquidity | 0 | 20% | TRACK_NORMAL |
| C3 | LIQUIDITY_REMOVED | Liquidity | 0 | 1 per batch cap | WATCH_ONLY |
| D1 | DEAD_TOKEN | Lifecycle | 1 | 20% | WATCH_ONLY |
| D2 | REVIVAL | Lifecycle | 0 | 1 per batch cap | TRACK_NORMAL or TRACK_FAST |
| D3 | MIGRATION_EVENT | Lifecycle | 0 | 1 per batch cap | New tracking session only |
| D4 | SUSPICIOUS_SAFETY | Lifecycle | 0 | 1 per batch cap | WATCH_ONLY only |
| E1 | REALISTIC_EXIT | Exit-evidence | 0 | 2 per batch cap | annotation only |
| E2 | UNREALISTIC_EXIT | Exit-evidence | 0 | 2 per batch cap | annotation only |
| F1-F4 | AVOID/WAIT variants | Counterfactual | 0 | 2 per batch cap | future activation |

---

## 5. Quota Policy

### Design Principles for Quotas

- All quotas are categorical counts, not scores or percentages of a quality metric.
- Quotas enforce diversity, not ranking.
- A token is selected because it fills a needed learning bucket, not because it scores
  highest on any axis.
- Quotas are defined for a **conservative first-pass bounded `WINDOW_15M` only batch**.
- These quotas are advisory for V2-2B design; they become enforced requirements in V2-2C
  implementation.

### First-Pass Conservative Batch Quotas

Target batch size: **6 to 10 tokens** (within WINDOW_15M bounded capacity).

This matches the combined max of X12 FAST (5 tokens) + X10.10B NORMAL (7 tokens) less
overlap and safety margin. First-pass batches should not exceed 10 tokens until balanced
multi-lane proofs are tested.

| Slot category | Min | Max | Notes |
|---------------|-----|-----|-------|
| Group A (fast-event) total | 1 | 4 | At least 1 A token for fast-event coverage. |
| — A1 (FAST_PUMP_FOLLOW) | 0 | 2 | Winner cap: no more than 2 pure winners per batch. |
| — A2 / A3 / A4 (trap/failed/wick) | 1 | 3 | At least 1 trap/failure/wick example per batch if any Group A is present. |
| Group B (normal-activity) total | 1 | 4 | At least 1 normal-activity token. |
| — B2 / B4 (decay) | 1 | 2 | At least 1 decay example. |
| Group C (liquidity) total | 0 | 2 | Optional; prioritize C2/C3 over C1 for diversity. |
| Group D (lifecycle) total | 1 | 3 | At least 1 lifecycle token. |
| — D1 (DEAD_TOKEN) | 1 | 2 | Required: at least 1 dead token per batch of 6+. |
| — D3 (MIGRATION) | 0 | 1 | Per-batch cap: 1 migration at most. Requires new tracking session. |
| — D4 (SUSPICIOUS_SAFETY) | 0 | 1 | Per-batch cap: WATCH_ONLY only; requires explicit reason. |
| WATCH_ONLY tokens | 1 | 3 | At least 1 WATCH_ONLY in any batch of 6+. |
| TRACK_FAST tokens | 1 | 5 | Must use the X12 FAST runner constraints. |
| TRACK_NORMAL tokens | 1 | 7 | Must use the X10.10B or X12 NORMAL runner constraints. |

**Hard rejection rules for quota violations:**

| Violation | Action |
|-----------|--------|
| All tokens in batch are Group A (all fast-event) | Reject batch; require at least 1 Group B or D token |
| Zero Group D (no dead/lifecycle/revival token) in batch of 6+ | Reject batch or downgrade 1 A token to WATCH_ONLY |
| All TRACK_FAST tokens with the same event_kind | Reject batch; require event_kind diversity |
| Same token mint appears more than once | Reject batch; mint dedup required |
| Batch has 0 WATCH_ONLY tokens in 6+ token batch | Advisory warning; require explicit operator override reason |

### Why These Quotas Avoid Winner-Only and Trending-Token Bias

- The A1 cap (max 2) ensures fast-pump winners cannot dominate.
- The mandatory D1 (dead token) forces the operator to consider the worst case.
- The Group B minimum ensures at least one slow/decaying token is tracked.
- WATCH_ONLY minimum forces protection-memory inclusion.
- No quota is based on the token's price performance or trend ranking —
  all quotas are categorical.

---

## 6. Selection Reason Policy

### Design Principles

Every selected and rejected token must have a persisted, auditable reason. Reasons are
categorical fields, not scores. The reason chain must be traceable from the discovery
source response to the final batch selection decision.

Reason fields must be durable: they must survive to the post-run report and, in V2-2C,
to a persisted selection-batch row in the DB.

### Required Reason Fields Per Token

The following fields must be present in any V2-2C selection-batch record:

| Field | Type | Description |
|-------|------|-------------|
| `token_mint` | string | Solana mint address. 44-char base58. |
| `pair_address` | string | Specific pair address used for this selection. |
| `chain` | string | Must be `"solana"`. |
| `token_id` | int | FK to `printer_tokens.id`. |
| `pair_id` | int | FK to `printer_pairs.id`. |
| `primary_bucket` | string | One of the bucket IDs from Section 3 (e.g., `"A4"`, `"D1"`). |
| `bucket_name` | string | Human-readable bucket name (e.g., `"FAILED_PUMP"`, `"DEAD_TOKEN"`). |
| `selection_reason` | string | One or more categorical labels from the reason vocabulary below. |
| `rejection_reason` | string or null | If token was considered but rejected, the rejection reason. Null if selected. |
| `tracking_lane` | string | `"TRACK_FAST"`, `"TRACK_NORMAL"`, or `"WATCH_ONLY"`. |
| `lane_rationale` | string | Why this lane was chosen for this token (see Section 8). |
| `source_name` | string | Discovery source (e.g., `"dexscreener"`, `"geckoterminal"`). |
| `source_channel` | string or null | Discovery channel (e.g., `"GECKOTERMINAL_NEW_POOL"`). |
| `source_request_id` | int or null | FK to `printer_source_requests.id` for discovery call. |
| `source_response_id` | int or null | FK to `printer_source_responses.id` for discovery response. |
| `discovery_candidate_id` | int or null | FK to `printer_discovery_candidates.id`. |
| `same_token_new_pair` | boolean | True if this selection uses a new pair for an already-tracked mint. |
| `same_token_new_pair_classification` | string or null | See Section 7. One of: `"MIGRATION"`, `"REVIVAL"`, `"PAIR_DRIFT"`, `"DUPLICATE_RECYCLE"`, `"DISTINCT_EVIDENCE"`. |
| `operator_approved` | boolean | Operator must set True before token enters any bounded runner. |
| `manual_override_reason` | string or null | Required if lane was manually overridden from discovery classification. |
| `selected_at` | ISO timestamp | When this token was added to the selection batch. |
| `cooldown_reopened` | boolean | True if this token was previously in COOLDOWN or ARCHIVED and is being reopened. |
| `cooldown_reopen_reason` | string or null | Required if `cooldown_reopened = True`. |
| `batch_id` | string | Identifier linking all tokens selected in the same bounded proof batch. |

### Selection Reason Vocabulary

The `selection_reason` field must use one or more of the following categorical labels:

**Activity reasons:**
- `FAST_ACTIVITY_CONFIRMED` — discovery payload confirms high volume/txn/price at discovery time.
- `NORMAL_ACTIVITY_BASELINE` — normal volume/txn pattern; no extreme signal.
- `TRANSACTION_SPIKE_DETECTED` — txn count spike observed in discovery payload.
- `VOLUME_RISING_TREND` — volume field shows rising pattern.
- `VOLUME_DECAY_PATTERN` — volume field shows declining pattern.
- `CONSOLIDATION_PATTERN` — price/volume flat; no clear direction.

**Liquidity reasons:**
- `LIQUIDITY_ABOVE_THRESHOLD` — liquidity meets or exceeds discovery threshold.
- `LIQUIDITY_BELOW_THRESHOLD` — liquidity below normal threshold; tracked for decay observation.
- `LIQUIDITY_NEAR_ZERO` — liquidity effectively zero; dead or abandoned.
- `LIQUIDITY_REMOVED_SIGNAL` — abrupt liquidity drop detected.

**Lifecycle reasons:**
- `DEAD_TOKEN_PROTECTION_SAMPLE` — token selected explicitly for dead-token memory.
- `REVIVAL_DETECTED` — new activity after prior ARCHIVED or COOLDOWN status.
- `MIGRATION_DETECTED` — new pair address for a known mint; prior pair is stale.
- `SUSPICIOUS_SAFETY_SIGNAL` — authority/blacklist flag detected; tracked for safety memory.

**Trap / failure reasons:**
- `WICK_ONLY_EVIDENCE` — payload shows price spike with no sustained volume follow-through.
- `LATE_ENTRY_RISK` — token age or momentum suggests the entry window has passed.
- `FAILED_PUMP_EVIDENCE` — prior tracking evidence shows pump that did not follow through.
- `TRAP_MEMORY_REQUIRED` — selected explicitly to teach trap patterns.

**Avoidance / wait counterfactual reasons:**
- `CORRECT_AVOID_CANDIDATE` — token matches a prior AVOID decision; included to validate it.
- `WRONG_AVOID_CANDIDATE` — token continued after a prior AVOID; included for miss-analysis.
- `CORRECT_WAIT_CANDIDATE` — token outcome confirmed a wait decision was correct.
- `WRONG_WAIT_CANDIDATE` — token outcome showed a missed opportunity from over-waiting.

**Exit-evidence reasons:**
- `EXIT_REALISM_SAMPLE` — token selected to build realistic exit-timing memory.
- `UNREALISTIC_EXIT_EVIDENCE` — peak profit visible in payload but liquidity/volume does not
  support realistic exit.

### Rejection Reason Vocabulary

The `rejection_reason` field must use one of the following when a token is not selected:

- `MINT_DUPLICATE` — same `token_mint` already present in the batch.
- `PAIR_DUPLICATE` — same `pair_address` already present in the batch.
- `ACTIVE_COOLDOWN` — token is in COOLDOWN status without approved reopen.
- `ARCHIVED_NO_REOPEN` — token is ARCHIVED and operator has not approved reopen.
- `BATCH_QUOTA_EXCEEDED` — bucket quota for this token's group is already full.
- `WINNER_CAP_EXCEEDED` — A1 (FAST_PUMP_FOLLOW) quota already filled.
- `STALE_SOURCE_DATA` — discovery payload is stale; token cannot be confirmed fresh.
- `CHAIN_NOT_SOLANA` — token is not on Solana chain.
- `INSTANT_REJECT_CLASSIFICATION` — discovery classifier returned INSTANT_REJECT.
- `IGNORE_CLASSIFICATION` — discovery classifier returned IGNORE.
- `NO_SOURCE_TRACE` — discovery candidate is missing `source_response_id`.
- `PAIR_DRIFT_UNRESOLVED` — token has an unresolved pair drift and cannot enter a new batch.
- `SAFETY_RISK_OPERATOR_OVERRIDE` — suspicious safety signal; operator chose to exclude.
- `MANUAL_EXCLUSION` — operator explicitly excluded this token with a stated reason.

---

## 7. Same-Token / New-Pair Policy

A "same-token/new-pair" situation occurs when a token mint already has one or more rows
in `printer_tokens` and `printer_pairs`, but a new discovery response shows a different
pair address for the same mint. This is common in Solana memecoins due to migration events
(e.g., PumpFun → Raydium pool migration) and is detected by X6 and X10.6.

The V2-2B policy requires every same-token/new-pair case to be classified as exactly one
of the five categories below before a token enters a bounded batch.

### Classification Rules

| Classification | When to use | Memory handling |
|---------------|-------------|-----------------|
| `MIGRATION` | New pair was created because the token migrated to a new pool or DEX (e.g., PumpFun pump → Raydium). Old pair is stale or has near-zero liquidity. | Treat as a new tracking session. Require a new WINDOW_15M evidence cycle. Do not continue old-pair memory windows into the new pair. Record `migration_detected = True` in the selection reason. |
| `REVIVAL` | Token was previously archived or in COOLDOWN with the same pair (or a different pair), and new activity is now detected. Old pair may still be active or may have changed. | Treat as a lifecycle reopen. The old tracking context is archived. Start fresh WINDOW_15M for the revived pair. Record `revival_detected = True` and `cooldown_reopened = True`. |
| `PAIR_DRIFT` | Same-token/new-pair occurred during an active tracking window (mid-window pair address change). Old and new pair evidence cannot be mixed in one WINDOW_15M record. | Immediately mark open windows for the old pair as DIRTY_MEMORY. Do not open a new window on the new pair in the same batch. Require a separate operator-approved batch for the new pair. |
| `DUPLICATE_RECYCLE` | New pair was discovered but appears to be a duplicate or near-identical to an existing active pair (same pool, same liquidity, same price, different address format). | Reject the new pair from the batch. Mark as `rejection_reason = PAIR_DUPLICATE`. Do not consume source budget on indistinguishable duplicates. |
| `DISTINCT_EVIDENCE` | Same mint has multiple genuinely distinct active pairs with meaningfully different liquidity, volume, or price. Each pair is a separate market for this token. | Each pair may have its own selection reason and its own memory windows. They are distinct evidence candidates. Track each pair as a separate token-pair row. |

### Same-Token/New-Pair in the DB (Current State)

From V2-2A, three tokens currently have multiple pair rows:
- token_id 7 (BONK / `DezXAZ8z...`): 3 pairs — classify each new pair entry as
  DISTINCT_EVIDENCE or MIGRATION based on source payload timestamps and liquidity.
- token_id 12 (`yMJPZbn...`): 2 pairs — check whether the second pair was created by
  a migration event or is a concurrent alternate pool.
- token_id 13 (ANSEM / `9cRCn9r...`): 2 pairs — UNRESOLVED from X11 R8. Require explicit
  operator classification before this mint enters any batch.

### Same-Token/New-Pair Operator Actions Required Before V2-2C

Before V2-2C implements the selection batch table, the operator must document the
classification for each of the three multi-pair tokens above. No token with an
UNRESOLVED pair classification may enter a bounded batch.

---

## 8. WATCH_ONLY / TRACK_NORMAL / TRACK_FAST Selection Semantics

### Design Principles

Each tracking lane feeds a different kind of memory. Lane assignment must be based on
the discovery classifier output and bucket assignment, not on operator intuition about
which tokens are more profitable.

Tracking lane semantics are not about trade priority. They are about data-collection
cadence and evidence quality. A WATCH_ONLY token tracked carefully produces equally
valid protection memory as a TRACK_FAST token.

### TRACK_FAST Semantics for Memory Factory

- **Who it is for:** Tokens with confirmed high activity at discovery time that need
  frequent snapshots to capture fast event behavior.
- **Primary learning targets:** A1 (FAST_PUMP_FOLLOW), A2 (WICK_ONLY_PUMP),
  A3 (LATE_BUY_TRAP), A4 (FAILED_PUMP), C1 (LIQUIDITY_RISING), B3 (TRANSACTION_SPIKE).
- **Cadence:** 15m window — snapshot every 120s (first 15m phase), then 240s (1h phase).
- **Freshness gate:** Hard freshness gate (X10.9 rules). If stale at batch start, block.
- **Max tokens per batch:** 5 (X12 FAST runner limit).
- **Balance constraint:** At least 1 of the 5 TRACK_FAST slots must be a trap/failure
  bucket (A2, A3, or A4). A TRACK_FAST batch that is all A1 (FAST_PUMP_FOLLOW) tokens
  is not a balanced memory diet — it is a winner-only sample.
- **Not for:** prediction, alpha hunting, BUY signal detection, or lead indicator use.
- **Safety:** TRACK_FAST memory does not unlock BUY, does not inform paper positions,
  does not produce confidence percentages, and does not feed retrieval until an explicitly
  approved retrieval lane is reached.

### TRACK_NORMAL Semantics for Memory Factory

- **Who it is for:** Tokens with moderate or declining activity where snapshot density
  should be lower to avoid wasting source budget on low-change windows.
- **Primary learning targets:** B1 (VOLUME_RISING), B2 (VOLUME_DECAYING),
  B4 (TRANSACTION_DECAY), B5 (CONSOLIDATION), C2 (LIQUIDITY_FALLING), D2 (REVIVAL).
- **Cadence:** 15m window — snapshot every 420s (first 15m phase), then 720s (1h phase).
- **Freshness gate:** Advisory only. Stale at batch start logs a warning but does not block.
- **Max tokens per batch:** 7 (X10.10B NORMAL runner limit, confirmed by X12).
- **Balance constraint:** At least 1 of the 7 TRACK_NORMAL slots must be a decay bucket
  (B2, B4, or C2). TRACK_NORMAL batches must not be filled exclusively with rising/positive
  signals.
- **Not for:** alpha hunting or entry-timing signals.
- **Note:** TRACK_NORMAL 15m has not yet run against the live DB (X11 R2, X12 design).
  X10.10C (first TRACK_NORMAL live 15m proof) must complete before TRACK_NORMAL 1h proofs.
  V2-2D should include at least one TRACK_NORMAL 15m example in its bounded proof.

### WATCH_ONLY Semantics for Memory Factory

- **Who it is for:** Tokens that the discovery classifier could not confirm for active
  tracking (low activity, safety risk, incomplete source data, dead tokens, or candidates
  under observation before lane decision).
- **Primary learning targets:** D1 (DEAD_TOKEN), D4 (SUSPICIOUS_SAFETY),
  C3 (LIQUIDITY_REMOVED), B4 (TRANSACTION_DECAY), F1-F4 (avoidance/wait counterfactuals).
- **Cadence:** No regular snapshots. DISCOVERY_REFRESH job only. No source budget
  consumed for active tracking.
- **No WINDOW_15M memory:** WATCH_ONLY tokens do not enter WINDOW_15M or WINDOW_1H
  memory windows. They remain in discovery/tracking queue as observation candidates.
- **Memory value:** WATCH_ONLY tokens teach what the system correctly ignored,
  incorrectly avoided, or should monitor without committing source budget. Their memory
  value is in the selection-reason record and the tracking-queue event log, not in
  snapshot-based WINDOW_15M evidence.
- **Promotion rules:** A WATCH_ONLY token may be promoted to TRACK_NORMAL or TRACK_FAST
  only through a new discovery classification with a valid fresh source response. Silent
  promotion (without a new discovery classification) is not allowed.
- **Not for:** Direct BUY signal, entry timing, or memory comparison until promoted.

### How Each Lane Feeds a Balanced Memory Factory

| Lane | Memory type produced | Balanced diet role | BUY/SELL/HOLD risk |
|------|---------------------|-------------------|--------------------|
| TRACK_FAST | High-density WINDOW_15M fast-event evidence | Fast pump wins, traps, wick-only | Must be capped to prevent winner-only dominance |
| TRACK_NORMAL | Lower-density WINDOW_15M slow-event evidence | Decay, consolidation, revival | Lower bias risk; slower to produce clean episodes |
| WATCH_ONLY | No snapshot-based memory; tracking queue + reason record only | Dead token, suspicious safety, protection baseline | Zero BUY risk; pure observation |

No lane assignment in any bucket is a recommendation to enter a paper trade. Lane
assignment is a data-collection strategy, not a trade strategy.

---

## 9. Cooldown / Archive / Reopen Policy

### Definitions

| Status | Meaning | Source Governor | Scheduler |
|--------|---------|-----------------|-----------|
| `QUEUED` | Ready for tracking; not yet started | Budget requested at start | Job to be created |
| `ACTIVE` | Currently being tracked; snapshots in flight | Budget actively consumed | Jobs running |
| `PAUSED` | Temporarily stopped; may resume | Budget not consumed | Jobs paused |
| `COOLDOWN` | Temporarily excluded from new batches | No budget | No new jobs |
| `ARCHIVED` | Permanently excluded unless operator reopens | No budget | No jobs |
| `SKIPPED` | Excluded without explanation; same as terminal | No budget | No jobs |

### Cooldown Entry Rules

A token enters COOLDOWN when:

1. **Active tracking ended without clean evidence** — fewer than the minimum required
   snapshots in a WINDOW_15M close, or pair drift detected mid-window. Token is too
   unreliable for immediate re-selection.
2. **Discovery classifier produced IGNORE** — token is not interesting enough to track
   but is not permanently excluded.
3. **Source budget failure during tracking** — consecutive source failures exceeded the
   budget limit. Token may recover if source stabilizes.
4. **Batch quota exceeded at selection time** — token was valid but its bucket was
   already filled. Place in COOLDOWN for next batch consideration.

Cooldown duration: minimum 6 hours for fast-moving tokens (Group A); minimum 24 hours
for Group B-D tokens. No automatic expiry: operator must explicitly reopen or the token
must trigger a new discovery event that overrides the cooldown.

### Archive Entry Rules

A token is ARCHIVED when:

1. **INSTANT_REJECT classification** — source data shows safety, fraud, or blacklist
   signals that make the token permanently unsuitable.
2. **DEAD_TOKEN confirmed for long duration** — token has zero liquidity and zero volume
   across multiple refresh cycles with no revival signal.
3. **Pair drift permanently unresolved** — operator has not provided a new pair address
   and the token's old pair is no longer trackable.
4. **Operator manual archive** — operator explicitly archives a token with a stated reason.

ARCHIVED tokens are not deleted. They remain in `printer_discovery_candidates` and
`printer_tracking_queue` with ARCHIVED status so they can be audited and reopened if evidence
warrants reconsideration.

### Reopen Rules

A COOLDOWN or ARCHIVED token may be reopened when:

1. **New discovery response for the same mint with a different pair address** — this is
   classified as MIGRATION or REVIVAL (see Section 7) and requires explicit bucket assignment.
2. **Time-based natural reopen** — operator confirms token is fresh and the original
   cooldown reason no longer applies (e.g., source stabilized, budget recovered).
3. **Explicit operator reopen with reason** — `cooldown_reopened = True` and
   `cooldown_reopen_reason` is filled in the selection batch record.

When reopening:
- Assign a bucket to the reopened token as if it were a new selection.
- Record `cooldown_reopened = True` and `cooldown_reopen_reason` in the selection-batch row.
- Do not carry over the old selection reason from before cooldown — the reopen event
  creates a new selection reason record.

### Stale Candidate Avoidance

A candidate is considered stale for selection purposes if:

- The `source_response_id` associated with the discovery candidate is older than
  **24 hours** at batch-assembly time.
- The token's last tracking-queue activity shows `COOLDOWN` or `ARCHIVED`.
- The normalized source payload shows `liquidity_usd < $500` and `volume_24h < $1000`
  (effectively dead regardless of classification label).

Stale candidates must be rejected with `rejection_reason = STALE_SOURCE_DATA` or
the appropriate lifecycle status rejection. They may be revisited in the next batch
if a fresh discovery response replaces the stale one.

---

## 10. Proof / Test Plan for V2-2C and V2-2D

This section defines what future lanes must prove. V2-2B does not implement any of this.

### V2-2C Proof / Test Requirements

V2-2C (Implement discovery/selection repairs) must prove, via unit tests with fixtures:

1. **Bucket assignment tests:**
   - Given a fixture discovery payload with high volume/price/txn, the bucket assigned
     is A1 (FAST_PUMP_FOLLOW) or A2/A3/A4 as appropriate.
   - Given a fixture payload with zero liquidity, the bucket assigned is D1 (DEAD_TOKEN).
   - Given a fixture payload with declining volume over sequential normalized payloads,
     the bucket assigned is B2 (VOLUME_DECAYING).
   - Bucket assignment never returns a numeric score; always returns a categorical string.

2. **Quota enforcement tests:**
   - A batch of 6+ tokens with zero D1 (DEAD_TOKEN) tokens is rejected at batch-assembly.
   - A batch where all Group A tokens are A1 (FAST_PUMP_FOLLOW) is rejected.
   - A batch with 3+ A1 tokens (exceeding winner cap) is rejected.
   - A batch with a single dead token and one fast-pump token passes quota validation.

3. **Selection reason persistence tests:**
   - Every selected token has a non-null `selection_reason` with at least one reason label.
   - Every rejected token has a non-null `rejection_reason`.
   - The `source_response_id` and `discovery_candidate_id` fields are non-null for every
     selected token.
   - `operator_approved = False` blocks selection even if all other fields are valid.

4. **Same-token/new-pair tests:**
   - A token with `same_token_new_pair = True` and `same_token_new_pair_classification = None`
     is rejected at batch-assembly.
   - A MIGRATION classification creates a new tracking session without inheriting old windows.
   - A PAIR_DRIFT during an active window produces DIRTY_MEMORY for the old pair window.
   - A DUPLICATE_RECYCLE case rejects the new pair with `rejection_reason = PAIR_DUPLICATE`.

5. **WATCH_ONLY gate tests:**
   - A WATCH_ONLY token never creates a WINDOW_15M memory window.
   - A WATCH_ONLY token never enters the TRACK_FAST or TRACK_NORMAL runner.
   - Silent promotion (WATCH_ONLY to TRACK_FAST without a new discovery classification)
     is blocked.

6. **Cooldown/archive tests:**
   - A COOLDOWN token without `cooldown_reopened = True` is rejected from a new batch.
   - An ARCHIVED token without explicit operator reopen is rejected.
   - `cooldown_reopened = True` without `cooldown_reopen_reason` is rejected.

7. **Risky-language / score-detection tests:**
   - No bucket assignment function returns a float, int ranking, or confidence percentage.
   - No selection reason field contains numeric ranking language.
   - No quota logic uses a weighted sum or score accumulation.

### V2-2D Proof / Test Requirements

V2-2D (Bounded discovery/selection proof) must prove with a real operator-approved run:

1. **Full batch assembly:** A bounded proof assembles a batch of 4-8 tokens meeting the
   quota rules above, with at least 1 dead/WATCH_ONLY token and at least 1 trap/failure
   bucket token.

2. **Selection-batch report:** The proof emits a JSON or text report that includes
   every token's primary bucket, selection reason, tracking lane, source trace reference,
   and same-token/new-pair classification (if applicable).

3. **Rejection-batch report:** Every candidate considered but rejected is listed with
   a non-null rejection reason.

4. **No financial rows:** The proof does not create paper decisions, positions, trade
   events, paper trade audits, or PnL rows.

5. **No retrieval activation:** The proof does not create retrieval match rows.

6. **Source-governed discovery:** All discovery calls in the proof use the Source
   Governor path. No direct API calls without `can_request_source()`.

7. **Tracking queue handoff:** Every selected token in the proof batch has a corresponding
   row in `printer_tracking_queue` with the correct `tracking_lane` and `priority_reason`.

8. **Balanced outcome report:** The post-proof report shows which buckets were filled,
   which were empty, and why. Empty bucket audit is required: if D1 (DEAD_TOKEN) was
   required but not filled, the report explains why.

---

## 11. Lock Preservation

This design document does not unlock:

| Capability | Status after V2-2B |
|-----------|-------------------|
| Discovery automation | Locked. V2-2C requires operator-approved bounded proof. |
| Source fetching | Locked. Still governed; V2-2D proof uses Source Governor path. |
| Memory generation | Locked. Bucket design feeds selection, not memory window creation. |
| Clean-memory creation | Locked. Memory creation requires a V2-3 one-command Memory Factory. |
| Retrieval activation | Locked. No retrieval design in this document. |
| Paper decisions | Locked. No decision logic in this document. |
| BUY / SELL / HOLD | Locked. No financial action design. |
| Paper positions | Locked. |
| Trade events | Locked. |
| Paper trade audits | Locked. |
| PnL | Locked. |
| 5m as main memory window | Locked. WINDOW_5M_MICRO_EVENT remains support-only. |
| 1h / 4h / 12h / 24h activation | Locked. V2-2B is WINDOW_15M only design. |
| Live trading, wallet, private keys, real funds | Out of scope for V1. |
| Scoring / ranking / confidence / weighted logic | Locked. All buckets are categorical. |
| Embeddings / vectors | Locked. |
| Paid APIs | Locked. |
| Source Governor bypass | Locked. |
| Central Scheduler bypass | Locked. |

Bucket taxonomy, quota policy, and selection reason fields are design artifacts only.
They describe how a future implementation should behave. They do not constitute
an implementation, do not run any code, and do not unlock any capability listed above.

---

## 12. Money-Usefulness Contribution

The V2-2B memory-diet design improves Printer's long-term money-usefulness by solving
the learning-diet imbalance that was identified in V2-2A:

**Without V2-2B:** Discovery/selection naturally over-samples fast movers and trending
tokens because those are the easiest candidates to classify. A corpus built entirely
from fast pumps will teach Printer that memecoins go up after being discovered, which
is selection bias, not reality. Paper decisions based on a winner-only corpus would
not be realistic.

**With V2-2B:** A bounded batch that must include at least one dead token, at least
one decay example, and at least one trap/failure example teaches Printer what the full
distribution of Solana memecoin outcomes looks like. A paper-only decision model trained
on this corpus can produce realistic AVOID, WAIT, and NO_ACTION decisions, not just BUY
predictions.

The bucket taxonomy also defines the **exit-evidence** group (E1/E2), which captures
whether the projected exit at a token's price peak was actually achievable. This is
essential for any future realistic paper-exit decision, not just entry-detection.

V2-2B does not unlock retrieval or paper decisions. It creates the design spec for a
selection pipeline that, once implemented and proven, will produce a corpus worth querying.

---

## 13. What V2-2B Improves

V2-2B converts the gap list from V2-2A into a formal specification:

| V2-2A gap | V2-2B resolution |
|-----------|-----------------|
| No durable selection-batch table | Defines required fields and reason vocabulary for V2-2C implementation |
| No quota policy | Defines conservative first-pass quotas; enforces diversity without scores |
| WATCH_ONLY has no Memory Factory semantics | Defines WATCH_ONLY role: protection memory and observation, no snapshot windows |
| Same-token/new-pair unclassified | Defines 5 formal classifications; 3 existing multi-pair tokens require operator action |
| Winner-only and trending-token bias unaddressed | A1 cap, D1 minimum, and mandatory decay example prevent bias |
| Cooldown/archive unclear for selection | Defines cooldown entry, archive entry, and reopen rules explicitly |
| X10.6 can produce empty batches | Quota validation at batch-assembly blocks empty-bucket batches |
| Dead-token under-sampling | D1 (DEAD_TOKEN) is a required slot in any batch of 6+ |
| Revival under-sampling | D2 (REVIVAL) is a named bucket with a required cooldown-reopen reason |

---

## 14. What V2-2B Still Does Not Unlock

V2-2B is design-only. The same capabilities locked in V2-2A remain locked after V2-2B:

- Discovery automation.
- Source fetching without operator approval.
- Memory generation.
- Clean-memory creation.
- Retrieval.
- Paper decisions.
- BUY / SELL / HOLD.
- Paper positions, trade events, paper trade audits, PnL.
- 5m as main window.
- 1h / 4h / 12h / 24h windows.
- Live trading, wallet, private keys.
- Scoring, ranking, confidence, weighted logic.

V2-2B produces no code, no test changes, no migrations, no DB writes, and no runtime
changes. It is complete when this document is committed and reviewed by the operator.

---

## 15. Proof / Test Needed Before V2-2B Completion

V2-2B is considered complete when this document is committed. No code proof is required
for V2-2B itself because V2-2B is design-only.

However, the following verification should be done before V2-2C begins:

1. **Risky-language scan:** Confirm this document contains no scoring, ranking,
   confidence-percentage, or numeric-ranking language that violates V1 restrictions.
   `git diff --check` and `rg` scan for terms like `score`, `rank`, `confidence`,
   `weight`, `probability`, `alpha`, `signal` used in a predictive sense.

2. **Operator review:** The operator should confirm the bucket taxonomy, quota rules,
   same-token/new-pair classifications, and WATCH_ONLY semantics match the intended
   Memory Factory diet before V2-2C implementation begins.

3. **Three multi-pair token classification:** The operator must document the
   same-token/new-pair classification for token_id 7, 12, and 13 (from V2-2A DB
   observations) before V2-2D can include any of these tokens.

---

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Stop condition |
|---------|---------------|------------------------------------------------------|--------------|--------------------|----|
| Buckets drift toward hidden scoring | Violates V1; creates false BUY signal | Corpus becomes biased toward winners | Numeric rank appears in reason field | Categorical-only vocabulary; risky-language scan | Any float or rank in bucket/reason fields |
| D1 (DEAD_TOKEN) slot goes unfilled in practice | Dead-token protection memory stays weak | Corpus overstates opportunity | Operator selects 6+ tokens with no dead example | Quota enforcement at batch-assembly; hard block | Dead-token batch audit always empty |
| Same-token/new-pair left UNRESOLVED at ANSEM | Pair drift can corrupt evidence | Dirty memory from mixed-pair windows | ANSEM enters batch with wrong pair | Explicit classification required before batch entry | Any batch includes `token_id = 13` without resolved pair classification |
| WATCH_ONLY silently promoted to TRACK_FAST | Wrong cadence; wrong freshness gate | WATCH_ONLY evidence treated as fast-event memory | Manual override without new discovery call | Explicit classification gate; no silent promotion | WATCH_ONLY in TRACK_FAST runner without new discovery |
| Cooldown tokens re-enter without fresh source | Stale data corrupts new batch | Repeated bad evidence from same token | Reopen without source freshness check | `source_response_id` must be fresh at reopen time | Stale `source_response_id` accepted at reopen |
| Exit-evidence bucket (E1/E2) confused with BUY signal | E1 tokens could be misread as entry recommendations | Paper decisions built on fake exit-realism | E1 label repurposed as "safe to enter" | E1/E2 annotation-only; no operator BUY promotion from E label | E1/E2 triggers paper decision logic |
| V2-2C implements buckets without tests | Silent selection drift | Unauditable batch output | No unit test coverage | Full V2-2C test plan (Section 10) required before V2-2D | V2-2C merged without tests |
| Batch size grows too large | Exceeds source budget; too many simultaneous tracker slots | Memory growth becomes expensive and fragile | 15+ tokens in one batch | First-pass max: 10 tokens; quota hard cap | Batch exceeds X12 FAST + X10.10B NORMAL combined limit |
| Revival and migration over-sampled | Same token dominates multiple batches | Low bucket diversity | Multiple D2/D3 entries without new fast/normal coverage | 1 per batch cap on D2 (REVIVAL) and D3 (MIGRATION) | D2/D3 > 1 in any single batch |
| Group F (counterfactual) activates without corpus | No prior memory to compare against | Empty or misleading counterfactual batch | F1-F4 used in early batches before 10 clean windows exist | Defer Group F until corpus has ≥ 10 clean WINDOW_15M episodes | F buckets in batch with < 10 clean episodes |

---

## 17. Next Recommended Lane

Next recommended lane: `V2-2C — Implement discovery/selection repairs`

V2-2C should:

1. Implement the selection-batch persistence layer (new DB table or extended
   `printer_discovery_candidates` fields to store all required reason fields from Section 6).
2. Implement bucket assignment logic as a module that takes a normalized discovery payload
   and returns a categorical bucket ID with no numeric scoring.
3. Implement quota validation at batch-assembly time (blocking batches that violate the
   rules from Section 5).
4. Implement same-token/new-pair classification gates (blocking unresolved classifications).
5. Implement cooldown/archive/reopen status gates at batch-assembly time.
6. Wire X6/X10.6 output into the durable selection-batch layer so post-run reports can
   reference the batch record rather than re-reading artifacts.
7. Write a complete unit test suite proving all requirements from Section 10.

V2-2C must not:
- Run a live discovery proof (that belongs to V2-2D).
- Create memory windows.
- Unlock retrieval, paper decisions, BUY, or any financial capability.
- Introduce any scoring, ranking, confidence, or weighted logic.
- Run the real-DB selection proof (that belongs to V2-2D).

V2-2C completes when the unit test suite passes and the operator approves the implementation
for V2-2D bounded proof.

---

## End-of-Lane Summary

**Files changed:** `docs/printer-v1-v2-2b-memory-diet-buckets-quotas-reasons-design.md` (created).

**Code touched:** None.

**Runtime touched:** None.

**Source fetching touched:** None.

**DB touched:** None.

**Checks to run:** `git diff --check`, `git status --short`, `git diff --stat`,
`git diff --name-only`.

**Locks preserved:** All V1 locks. No implementation, no discovery automation, no source
fetching, no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions, no trades, no audits, no PnL.

**Next recommended lane:** `V2-2C — Implement discovery/selection repairs`
