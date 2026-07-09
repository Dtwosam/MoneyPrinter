# Printer V1 — V2-2L WATCH_ONLY / D1 Quota Semantics and Candidate-Pool Handoff Repair Design

**Lane:** V2-2L
**Type:** Design/specification only. No implementation.
**Status:** DESIGN_COMPLETE_WITH_BLOCKERS
**Date:** 2026-07-09
**Anchors:** V2-2K audit `2cd7940` → V2-2H closeout `3f48a63` → V2-2I proof `5165f9c`

---

## Todo / Checklist

- [x] Read AGENTS.md
- [x] Read docs/printer-v1-clean-master-spec.md
- [x] Read docs/printer-v1-post-rc-build-order.md
- [x] Read docs/printer-v1-memory-factory-guide.md
- [x] Read docs/printer-v1-current-state-memory-growth-audit.md
- [x] Read docs/printer-v1-memory-growth-build-order-v2.md
- [x] Read docs/printer-v1-assistant-active-build-order-anchor.md
- [x] Read docs/printer-v1-v2-2-live-discovery-selection-capacity-audit.md
- [x] Read docs/printer-v1-v2-2g-discovery-selection-capacity-repair-design.md
- [x] Read docs/printer-v1-v2-2h-discovery-selection-repair-implementation-closeout.md
- [x] Read docs/printer-v1-v2-2i-discovery-selection-capacity-repair-bounded-proof.md
- [x] Read docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md
- [x] Inspect selection_batch.py quota logic (lines 876–942)
- [x] Inspect discovery.py routing logic
- [x] Inspect commands.py WATCH_ONLY rejection gate (line 1729–1730)
- [x] Write this design document

---

## 1. Lane Boundary

**V2-2L is design-only.** It produces a specification and implementation handoff.
No code is changed, no migrations are created, no discovery is run, and no DB is
mutated in this lane.

**V2-2J remains paused.**

**V2-3 remains paused.**

This lane does not unlock:

- memory generation
- memory-window creation
- retrieval activation
- paper decisions
- BUY / SELL / HOLD
- paper positions
- trades
- paper trade audits
- PnL
- live trading
- wallet / private keys / real funds
- paid APIs
- scoring / ranking / confidence / weighted token logic
- embeddings / vectors
- Source Governor bypass
- Central Scheduler bypass

Allowed in this lane:

- design/specification documentation
- static repo inspection (read-only)
- blocker mapping
- implementation plan for V2-2M
- proof plan for V2-2N

Not allowed in this lane (verbatim from operator spec):

- implementation
- migrations
- live discovery
- source fetching
- runtime execution
- scheduler execution
- DB mutation
- proof DB creation
- memory generation
- memory-window creation
- retrieval activation
- paper decisions
- BUY/SELL/HOLD
- positions
- trades
- paper trade audits
- PnL
- paid APIs
- live wallet/private keys/real funds
- scoring/ranking/confidence/weighted token logic
- embeddings/vectors
- weakening Source Governor or Central Scheduler boundaries

---

## 2. Why V2-2L Is Needed

### 2.1 The V2-2K Numbers

The V2-2K practical coverage audit (`2cd7940`) ran a three-request, two-provider,
three-channel discovery cycle and measured the full pipeline end to end:

| Metric | Result |
|---|---:|
| Source requests planned / attempted | 3 / 3 |
| Source responses received | 3 |
| Source failures | 0 |
| Providers measured | 2 |
| Channels measured | 3 |
| Candidates normalized | 70 |
| Candidates persisted | 20 |
| WATCH_ONLY candidates seen raw | 13 |
| WATCH_ONLY candidates persisted | 0 |
| D1 candidates seen raw | 3 (1 Solana) |
| D1 candidates persisted | 0 |
| Candidates considered by selection | 20 |
| Candidates assembled by selection | 13 |
| Candidates rejected by selection | 7 |
| Final quota result | FAIL |
| Quota violation 1 | `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH` |
| Quota violation 2 | `MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH` |

### 2.2 Why This Blocks Near-Perfect Discovery/Selection

The raw governed candidate universe contained useful protective lessons:

- 13 raw WATCH_ONLY candidates were present but zero reached selection.
- 3 raw D1 (dead/near-dead) candidates were present including one valid Solana D1,
  but zero reached selection.
- The persisted pool of 20 assembled 13 into a batch, but that batch contained zero
  WATCH_ONLY and zero D1 — exactly the two classes V2-2C quota requires for a 6+
  batch.

The result is a system that can discover 70 candidates across 8 asset classes, produce
dead-token raw evidence, see WATCH_ONLY signals, and still generate a quota-invalid
selected batch — not because of missing source data, but because of a structural gap
in how rejected candidates flow into quota logic.

The master spec (Section 4.5) states explicitly: "Discovery must feed full
market-behavior memory, not only bullish memory." Without protective lessons in the
selected batch, Printer cannot build a balanced memory diet. Every quota-invalid batch
is a missed opportunity for avoid/dead-token/wait memory.

---

## 3. Current Contradiction

### 3.1 The Three-Part Contradiction

**Part 1 — The persistence gate:** `_select_discovery_candidates()` in
`commands.py:1729–1730` explicitly rejects WATCH_ONLY candidates before persistence
with reason `"watch_only_not_eligible_for_15m_memory_proof_cycle"`. This is correct
protection: WATCH_ONLY tokens should not consume active tracking/scheduler budget the
same way TRACK_NORMAL and TRACK_FAST tokens do.

**Part 2 — The quota requirement:** `validate_batch_quota()` in `selection_batch.py:930–931`
requires at least one item with `tracking_lane == "WATCH_ONLY"` in any batch of 6+
selected items. This is correct quota design: the memory diet should include tokens
that are not yet active-tracking quality, to teach the system about uncertain/watchful
conditions.

**Part 3 — The structural impossibility:** Because WATCH_ONLY candidates are always
rejected before persistence (Part 1), no WATCH_ONLY candidate can ever enter the
persisted pool, and the persisted-pool-only selection step can never satisfy the quota
(Part 2). The contradiction is not an edge case — it is guaranteed to fire on any
6+ batch.

### 3.2 D1 (Dead-Token) Path

D1 dead-token candidates follow a parallel path. In the V2-2K audit:

- GeckoTerminal produced no raw D1 candidates.
- DexScreener produced 3 raw D1 candidates, including 1 valid Solana D1.
- DexScreener persisted 0 candidates total due to cross-chain noise and STNP
  clusters dominating its pool.

Even if DexScreener's query productivity is later improved, D1 candidates that have
low or dead activity are likely classified as WATCH_ONLY by the classifier
(`discovery_action = DiscoveryOutputAction.WATCH_ONLY`), which means they also hit
the same pre-persistence rejection gate. The structural dead-token path is blocked
by the same contradiction as WATCH_ONLY.

### 3.3 What the Contradiction Means

The V2-2B quota was designed to force balanced memory intake. The current persisted-
pool-only selection architecture cannot honor it without a separate audit-only
candidate handoff or an explicit revision of the quota semantics.

Silently loosening either gate — removing the WATCH_ONLY pre-persistence rejection,
or removing the WATCH_ONLY/D1 quota requirement — would resolve the contradiction
only by defeating its own purpose. The design must preserve both protections while
creating a safe path between them.

---

## 4. Safety Principles

The following must be preserved throughout V2-2L design and any downstream
implementation:

1. **WATCH_ONLY must not be silently promoted to TRACK_NORMAL or TRACK_FAST.**
   `check_watch_only_promotion_gate()` in `selection_batch.py` enforces this. The
   repair must not weaken it.

2. **D1/dead/low-activity tokens must not create active tracking or scheduler load**
   unless an explicit future lane approves it. No new scheduler rows from audit-only
   candidates.

3. **Audit-only candidates must remain audit-only** through the full pipeline. A
   candidate that does not qualify for persistence must not receive a
   `printer_tracking_queue` entry or `printer_scheduler_jobs` entry.

4. **No memory generation.** An audit-only candidate in the selected batch must not
   open a memory window.

5. **No retrieval activation.** Audit-only candidates must not trigger retrieval
   query matching.

6. **No paper decisions.** Audit-only candidates must not create paper decision
   records.

7. **No BUY/SELL/HOLD/positions/trades/audits/PnL** from any path involving audit-
   only candidates.

8. **No scoring/ranking/confidence/weighted logic.**

9. **Source trace must be preserved** for every audit-only candidate so future proofs
   can verify what source and channel the lesson came from.

10. **Rejection reason must be preserved** for every pre-persistence rejected candidate
    that enters the audit-only pool, so the pool is not opaque.

11. **No dirty or unsafe candidate use** for future retrieval, decisions, or memory
    window creation. An audit-only candidate that later gets promoted to active
    tracking must go through a new, fresh discovery classification — not through a
    silent promotion of its audit-only record.

---

## 5. Option Analysis

### Option A — Quota Operates on the Broader Governed Candidate Universe

**How it works:**

An audit-only candidate pool is created at the pre-persistence rejection boundary.
Specifically, immediately before `_select_discovery_candidates()` discards WATCH_ONLY
and D1 candidates, those candidates are captured into an in-memory structure called
the audit-only pool. The pool carries each candidate's full normalized fields, its
rejection reason, its source trace (source_name, source_channel, source_response_id),
and a marker (`audit_only: True`).

The `_select_discovery_candidates()` function receives both the normal persisted
candidates and the audit-only pool as separate inputs. For quota satisfaction, the
function can draw from audit-only candidates to fulfill WATCH_ONLY and D1 quota
requirements — but only after all persisted candidates have been considered first,
and only up to the quota-required minimum.

Audit-only candidates selected for quota satisfaction are marked clearly in the
assembled batch with `candidate_kind: "AUDIT_ONLY"` so reporting can distinguish
them from active-tracking candidates. They do not generate tracking queue entries,
scheduler jobs, or memory windows.

**Pros:**

- Preserves the original quota intent: the memory diet includes protective lessons
  even when the persisted pool cannot supply them.
- WATCH_ONLY and D1 lessons reach the selected batch without active tracking load.
- Source trace and rejection reason are preserved end to end.
- No change required to source adapters, the Source Governor, or the Central
  Scheduler.
- Supports the master spec requirement to learn from dead tokens, traps, and WATCH
  behavior.
- Enables future memory-diet proof to verify that quota-satisfying candidates were
  genuinely observed, not fabricated.

**Cons:**

- Requires a new data structure (the audit-only pool) to flow from the pre-persistence
  rejection boundary through to selection.
- `validate_batch_quota()` must be updated to accept and recognize audit-only
  candidates in the quota check.
- Report fields must be expanded to distinguish active-tracking vs audit-only
  representation.
- Implementation complexity is moderate: two inputs to selection instead of one,
  plus audit-only markers at every downstream reporting step.
- Proof must verify that no audit-only candidate accidentally creates tracking or
  scheduler rows.

**Safety risks:**

- **Fake quota pass:** The strongest risk. If the audit-only candidate pool can be
  filled with any rejected candidate, an adversarial or buggy classifier could flood
  the pool with low-quality candidates and satisfy quota dishonestly. Mitigation:
  strict pool entry rules — only WATCH_ONLY and D1 actions enter the audit-only pool;
  quality/source-status checks must still pass; incomplete/dirty candidates must not
  enter the pool.
- **Accidental active-tracking leak:** An audit-only candidate could accidentally
  receive a tracking queue entry if the candidate_kind marker is not checked at the
  persistence boundary. Mitigation: explicit guard in the tracking queue path that
  rejects any candidate with `audit_only: True`.

**Money-usefulness impact:**

High. The design directly enables memory-diet balance. A selected batch that includes
WATCH_ONLY and D1 lessons will eventually produce memory windows that teach Printer
about avoid, wait, dead-token, and trap behavior — exactly the negative-lesson diet
that prevents over-learning from winners.

**Implementation complexity:** Moderate (3–4 targeted changes to existing functions;
no schema change required; no new tables required initially).

**Proof requirements:**

- Audit-only pool is populated from pre-persistence rejections.
- Audit-only candidates satisfy WATCH_ONLY/D1 quota in a 6+ batch.
- No audit-only candidate appears in `printer_tracking_queue` or
  `printer_scheduler_jobs`.
- No audit-only candidate triggers memory window creation.
- Source trace and rejection reason are present for all audit-only items in the batch.
- Quota report distinguishes active-tracking vs audit-only representation.

**Does this support near-perfect discovery/selection better?** Yes. This is the
design that most closely matches the master spec intent: full market-behavior memory
including deaths and watch-only conditions, without active tracking load.

---

### Option B — Quota Operates Only on Persisted Candidates With Revised Semantics

**How it works:**

The quota rule is revised to make WATCH_ONLY and D1 requirements conditional:

- If 6+ items AND at least 1 WATCH_ONLY candidate exists in the persisted pool:
  require at least 1 WATCH_ONLY in the selected batch.
- If 6+ items AND no WATCH_ONLY candidate exists in the persisted pool: skip the
  WATCH_ONLY quota requirement (or downgrade to QUOTA_WARNING instead of
  QUOTA_VIOLATION).
- Same conditional logic for D1.

The existing pre-persistence rejection gate for WATCH_ONLY remains unchanged.

**Pros:**

- Minimal implementation: only `validate_batch_quota()` needs updating.
- No new data structures required.
- No risk of audit-only candidates accidentally leaking into tracking.
- Simple to test: quota still validates against the persisted pool only.

**Cons:**

- The quota can now be satisfied with zero WATCH_ONLY and zero D1 whenever the
  persisted pool happens not to contain them — which is the normal case given the
  current architecture. This effectively removes the WATCH_ONLY and D1 quota
  protections in practice.
- Does not improve memory diet balance. A batch of 13 active-tracking candidates
  is still all active-tracking, all TRACK_NORMAL, all from one channel. Quota passes
  but the diet is not balanced.
- Defeats the intent of V2-2B Section 5: the quota was designed to force inclusion of
  protective lessons, not to measure what happened to be available.
- Future proof of memory-diet quality will still show bias toward active-tracking
  winners, but quota will no longer flag it.
- The "conditional quota" logic is subtle and easy to misread: "quota passed" would
  no longer mean "balanced batch" — it could mean "persisted pool had no protective
  lessons available."

**Safety risks:**

- **Memory diet becoming homogeneous:** The strongest risk. Without a hard WATCH_ONLY/D1
  requirement, Printer's selected batch defaults to all-active-tracking candidates. The
  resulting memory will be biased toward tokens that survived active tracking gates,
  missing the vocabulary of dead tokens, traps, and watch-only conditions.

**Money-usefulness impact:**

Low in the medium term. Quota passes, but the diet taught to Printer is unbalanced.
A money machine that only learns from winners will not learn when to wait, avoid, or
recognize dead-token traps.

**Implementation complexity:** Very low (1 targeted change to `validate_batch_quota()`).

**Proof requirements:**

- Quota passes when WATCH_ONLY/D1 are absent from persisted pool.
- Batch report clearly labels that quota was conditionally satisfied.
- No memory-diet balance improvement is claimed.

**Does this support near-perfect discovery/selection better?** No. It makes quota
easier to satisfy at the cost of removing the protective lesson requirement.

---

## 6. Recommended Design

**Recommended: Option A — Audit-Only Candidate-Pool Handoff.**

Option B is technically simpler but defeats the quota's purpose. The master spec
Section 4.5 states Printer must learn from "pumps, dumps, consolidation, stable
ranges, dead movement, revival, fake pumps, micro-pumps, liquidity increase/decrease,
volume increase/decrease, transaction changes, holder changes where available, and
failed breakouts." A quota that silently exempts itself when protective lessons are
absent does not enforce this requirement — it merely reports an honest deficit without
correcting it.

Option A preserves the protective intent while providing a safe, auditable, non-
tracking path for WATCH_ONLY and D1 candidates to participate in memory-diet quota.

### 6.1 What Counts as an Audit-Only Candidate

A candidate qualifies for the audit-only pool if all of the following are true:

1. It is a Solana candidate (chain == "solana").
2. It passed source-status validation (source_status == COMPLETE or PARTIAL, not
   FAILED or STALE).
3. It passed data-quality validation (data_quality_label == CLEAN_DATA or
   ACCEPTABLE_PARTIAL_DATA, not DIRTY_DATA or DO_NOT_TRAIN).
4. It was classified with `discovery_action == WATCH_ONLY` or its primary bucket
   resolves to `D1` (DEAD_TOKEN).
5. It was not classified `INSTANT_REJECT_MEMORY_ONLY` — those remain pure reject
   memory with no audit-pool eligibility.
6. It is not a duplicate of a candidate already in the audit-only pool for this run
   (dedup by token_mint within the run).

Non-Solana candidates, FAILED/STALE/DIRTY source results, and INSTANT_REJECT
candidates do not enter the audit-only pool.

### 6.2 How WATCH_ONLY Enters the Handoff

Current rejection point in `commands.py:1729–1730`:
```
elif classification.discovery_action == DiscoveryOutputAction.WATCH_ONLY:
    reject_reason = "watch_only_not_eligible_for_15m_memory_proof_cycle"
```

In V2-2M, before this rejection fires, WATCH_ONLY candidates that pass the quality
and chain checks above are captured into the run's `audit_only_pool` list. The
rejection still fires — they still do not enter the `accepted` list or the
`printer_tracking_queue`. They are captured into a separate in-memory structure
that is passed alongside the rejected list.

The audit-only pool is transient: it exists only during the discovery run. Nothing
from the audit-only pool is committed to `printer_tracking_queue`,
`printer_scheduler_jobs`, or any active tracking table.

### 6.3 How D1 Enters the Handoff

D1 candidates that were classified with `discovery_action == WATCH_ONLY` (the common
case for dead-activity tokens) enter the audit-only pool via the same WATCH_ONLY path
above. Their bucket assignment (D1) is preserved from the normalized candidate.

If a D1 candidate was classified with `discovery_action == TRACK_NORMAL` and then
rejected by another gate (for example, a dead-activity filter), it must be evaluated
separately. The implementation plan must address this edge case explicitly. For V2-2M,
the safe initial scope is: D1 candidates that were classified WATCH_ONLY enter the
audit-only pool. D1 candidates that were classified TRACK_NORMAL but later rejected
are in-scope only if the reason was specifically a dead-activity/D1 filter.

### 6.4 How Source Trace Is Preserved

Each audit-only candidate carries:

- `source_name`: the governed source that produced it
- `source_channel`: the channel label (e.g., `GECKOTERMINAL_NEW_POOL`)
- `source_response_id`: the UUID of the source response it came from
- `source_channel_reason`: why that channel was assigned

These fields are already present on normalized candidates (set in the plan loop by
H.6). The audit-only pool must not strip or overwrite them.

### 6.5 How Rejection Reason Is Preserved

Each audit-only candidate carries the `reject_reason` string that was assigned at the
pre-persistence boundary (e.g.,
`"watch_only_not_eligible_for_15m_memory_proof_cycle"`). This reason is included in
the audit-only pool entry as `pre_persistence_reject_reason`.

The batch report exposes this reason per audit-only candidate in
`reasons_by_audit_only_candidate`.

### 6.6 How candidate_stage_report Changes

New keys to add to `candidate_stage_report` or its parallel `audit_only_report`:

- `candidates_audit_only_total`: count of candidates in the audit-only pool for this
  run.
- `candidates_audit_only_watch_only`: count classified as WATCH_ONLY action.
- `candidates_audit_only_d1`: count with primary bucket D1.
- `candidates_audit_only_selected_for_quota`: count of audit-only candidates used to
  satisfy quota in the selected batch.

The existing H.1 invariant remains: all values in `candidate_stage_report` must be
`int` or `"NOT_MEASURED"`.

### 6.7 How V2-2C Selection Gets Access to Audit-Only Candidates

`_select_discovery_candidates()` currently takes a single list of accepted
(persisted) candidates. In V2-2M, it receives a second optional parameter:
`audit_only_pool: list[dict] | None = None`.

Selection behavior:

1. Proceed as before for the persisted (active-tracking) candidate pool.
2. If the assembled batch of 6+ items fails quota on WATCH_ONLY or D1:
   a. Search the audit-only pool for WATCH_ONLY candidates to fill the WATCH_ONLY
      quota minimum (1 candidate).
   b. Search the audit-only pool for D1 candidates to fill the D1 quota minimum
      (1 candidate).
   c. Add matched audit-only candidates to the assembled batch, marked
      `candidate_kind: "AUDIT_ONLY"`.
   d. Re-run `validate_batch_quota()` on the augmented batch.
3. If the audit-only pool cannot supply the required WATCH_ONLY or D1 candidates,
   the quota still fails and is reported honestly as
   `MISSING_D1_OR_WATCH_ONLY_UNAVAILABLE_IN_AUDIT_POOL`.
4. Audit-only candidates selected for quota are not passed to
   `process_discovery_payload()` and do not enter `printer_discovery_candidates` or
   `printer_tracking_queue`.

This keeps the persisted-pool-first priority intact while using the audit-only pool
as a quota supplement of last resort.

### 6.8 How Selected Audit-Only Items Are Marked

Each selected audit-only candidate in the batch carries:

- `candidate_kind: "AUDIT_ONLY"` (as opposed to `"ACTIVE_TRACKING"` for persisted
  candidates)
- `audit_only: True`
- `pre_persistence_reject_reason`: the string from the pre-persistence rejection
- `source_name`, `source_channel`, `source_response_id`, `source_channel_reason`:
  full source trace
- All normalized fields that were present at the time of rejection

These fields are stored in `printer_selection_batch_items` if the schema is extended,
or in a parallel JSON column if the schema is not extended in V2-2M.

### 6.9 Why This Does Not Create Active Tracking

The audit-only pool entry point is strictly before the `accepted` list. The
`accepted` list is the only path into `process_discovery_payload()`, which is the
only path into `printer_discovery_candidates` and `printer_tracking_queue`. Audit-
only pool candidates bypass `process_discovery_payload()` entirely and are never
passed to it. Therefore no `printer_tracking_queue` entry is created, no
`printer_scheduler_jobs` entry is created, and no active tracking budget is consumed.

The existing `check_watch_only_promotion_gate()` gate in `selection_batch.py` remains
unchanged. Future promotion of a WATCH_ONLY token to TRACK_NORMAL must come from a
new, fresh discovery classification — not from an audit-only batch record.

### 6.10 Why This Does Not Generate Memory by Itself

Audit-only candidates in the selected batch have `candidate_kind: "AUDIT_ONLY"` and
no `printer_tracking_queue` row. The memory factory (Lane U / Lane K pipeline) only
opens memory windows for tokens in the tracking queue that have sufficient snapshot
coverage. An audit-only candidate has no tracking queue entry, so no memory window
can be opened for it. The memory factory loop will not encounter it.

### 6.11 Why This Does Not Unlock Retrieval or Paper Decisions

Retrieval matches are found against memory fingerprints that were created from
completed, clean memory windows. An audit-only candidate never enters the tracking
queue and never produces a snapshot series, so it never produces a memory window or
fingerprint. Retrieval cannot match against a non-existent fingerprint. Paper
decisions require a retrieval match. Therefore audit-only candidates cannot cause
paper decisions.

### 6.12 How Future Memory-Diet Proof Can Use It Safely

V2-2N proof will verify:

- Audit-only candidates appear in the batch report but not in `printer_tracking_queue`.
- Quota passes because WATCH_ONLY/D1 are represented in the batch (via audit-only).
- No audit-only candidate triggers any downstream memory, retrieval, or paper path.
- Batch report shows `active_tracking_selected_count` and `selected_audit_only_count`
  separately so the proof can confirm the distinction is not lost.

A future memory-quality audit can verify that the eventual memory corpus includes
episodes from both active-tracking and audit-only origin pools, the latter via tokens
that were later legitimately promoted to active tracking through a fresh discovery
cycle.

---

## 7. Candidate-Pool Layers

The following layers define the full candidate-pool architecture after V2-2L repair:

| Layer | Name | Description |
|---|---|---|
| L0 | Raw normalized source candidates | All candidates returned by the governed source response and run through normalize_candidates(). All tokens regardless of action. |
| L1 | Pre-persistence rejected candidates | L0 candidates rejected by _select_discovery_candidates() for any reason. Includes WATCH_ONLY, D1, insufficient_activity, INSTANT_REJECT, non-Solana, cap-overflow, etc. |
| L2 | Audit-only pool | Subset of L1: only WATCH_ONLY and D1 candidates that pass quality/chain checks and are not INSTANT_REJECT. Captured before the L1 rejection is finalized. |
| L3 | Persisted tracking candidates | L0 candidates that passed all gates and were accepted into printer_discovery_candidates + printer_tracking_queue. |
| L4 | Selection-considered candidates | L3 + L2 (audit-only pool, for quota supplement only). Passed to _select_discovery_candidates(). |
| L5 | Selected memory-diet candidates | Subset of L4: items assembled into the batch by V2-2C selection. Includes both ACTIVE_TRACKING and AUDIT_ONLY items. |
| L6 | Active tracking queue candidates | Subset of L3 only: candidates with a printer_tracking_queue entry and printer_scheduler_jobs. L2/AUDIT_ONLY candidates never reach this layer. |

### Layer Membership Rules

| Property | L0 | L1 | L2 (audit-only) | L3 | L4 | L5 | L6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| May contain WATCH_ONLY | YES | YES | YES | NO | YES | YES | NO |
| May contain D1 | YES | YES | YES | NO | YES | YES | NO |
| Creates printer_tracking_queue row | NO | NO | NO | YES | — | NO* | YES |
| Creates printer_scheduler_jobs row | NO | NO | NO | NO | — | NO* | YES |
| May later feed memory-window generation | NO | NO | NO | YES | — | NO* | YES |
| Carries source trace | YES | YES | YES | YES | YES | YES | YES |
| Carries rejection reason | NO | YES | YES | NO | — | YES† | — |

\* Active-tracking (L3) items in L5 do not create new queue rows during selection;
their queue rows were created at the L3 persistence step. Audit-only (L2) items in
L5 create no queue rows at any step.

† Audit-only items in L5 carry `pre_persistence_reject_reason`.

---

## 8. WATCH_ONLY Semantics

After V2-2L repair, WATCH_ONLY behavior is:

- **Discoverable:** A WATCH_ONLY candidate is correctly classified by the classifier
  and normalized by the source adapter.
- **Reportable:** WATCH_ONLY candidates are visible in `candidate_stage_report` under
  `candidates_audit_only_watch_only` and `raw_watch_only_count`.
- **Eligible for audit-only memory-diet quota consideration:** A WATCH_ONLY candidate
  that passes quality/chain checks can enter L2 and be drawn into L5 to satisfy the
  quota WATCH_ONLY requirement.
- **Not active tracking by default:** No `printer_tracking_queue` entry. No scheduler
  follow-up. No snapshot schedule. No memory window.
- **No scheduler follow-up unless explicitly later approved:** A future lane may
  approve a light WATCH_ONLY refresh cycle (as described in master spec Section 4.11,
  every 20–30 minutes). That approval requires a separate implementation lane; it is
  not granted by V2-2L or V2-2M.
- **Cannot unlock retrieval or paper decisions:** WATCH_ONLY candidates in L5 have no
  memory fingerprint and therefore cannot be retrieval targets.
- **Cannot become BUY/SELL/HOLD:** WATCH_ONLY candidates in L5 are quota
  contributors, not decision inputs.
- **Must retain reason and source trace:** Every WATCH_ONLY candidate in the audit-
  only pool and in the selected batch carries `pre_persistence_reject_reason`,
  `source_name`, `source_channel`, `source_response_id`, and `source_channel_reason`.
- **Promotion path:** A WATCH_ONLY token may only become TRACK_NORMAL or TRACK_FAST
  through a new discovery classification that sets `discovery_action` accordingly.
  The existing `check_watch_only_promotion_gate()` gate enforces this. An audit-only
  batch record is not a promotion vehicle.

---

## 9. D1 / Dead-Token Semantics

After V2-2L repair, D1 (DEAD_TOKEN) behavior is:

- **Discoverable:** D1 candidates are correctly classified by `assign_bucket()` and
  visible in raw normalized output.
- **Reportable:** D1 candidates are visible in `candidate_stage_report` under
  `candidates_audit_only_d1` and `raw_d1_count`.
- **Eligible for audit-only memory-diet quota consideration:** A D1 candidate that is
  WATCH_ONLY-classified (the common case for dead-activity tokens) and passes
  quality/chain checks can enter L2 and be drawn into L5 to satisfy the quota D1
  requirement.
- **Should teach negative/dead-token/avoid lessons:** D1 tokens represent tokens with
  dead or near-dead activity. Their primary memory value is negative: they teach
  Printer what a dead or dying token looks like at discovery time. This lesson is
  valuable for future avoid decisions even if the token never produces a memory window.
- **Should not create active tracking load unless future lane explicitly approves:**
  D1 tokens at discovery time have by definition dead or minimal activity. Tracking
  them at any meaningful frequency wastes source budget on tokens that have no
  predictive value for live positions. A future lane may approve a one-shot D1
  confirmation pass, but this is not part of V2-2L or V2-2M scope.
- **Must not be hidden just because not attractive:** D1 is reported in raw counts,
  audit-only pool counts, and selected-batch representation. The system must not
  silently discard dead-token evidence; it must surface it in the report so the
  operator can verify dead-token coverage.
- **Must preserve source trace and reason:** Same as WATCH_ONLY above.

---

## 10. Quota Semantics After Repair

### 10.1 What Quota Validates Against

After V2-2L repair, quota validation receives the full L4/L5 candidate set:
persisted active-tracking candidates plus audit-only candidates drawn from the
audit-only pool. `validate_batch_quota()` is extended to accept an
`audit_only_items` parameter.

**Quota validates against the selected memory-diet candidates (L5), not just active
tracking candidates (L3/L6).**

### 10.2 Can Audit-Only Candidates Satisfy D1/WATCH_ONLY Quota?

Yes — this is the core mechanism of Option A. An audit-only candidate with
`tracking_lane = "WATCH_ONLY"` can satisfy the `MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH`
violation. An audit-only candidate with `primary_bucket = "D1"` can satisfy the
`MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH` violation.

Satisfaction is honest: the candidate was genuinely observed in the governed source
response. Its source trace and rejection reason prove it was a real discovery event,
not a fabricated placeholder.

### 10.3 How Quota Reports Audit-Only vs Active-Tracking Representation

The quota result carries two new summary fields:

- `quota_satisfied_by_audit_only_count`: number of quota requirements satisfied by
  audit-only candidates.
- `quota_satisfied_by_active_tracking_count`: number satisfied by persisted active-
  tracking candidates.

The batch report also carries:

- `active_tracking_selected_count`: count of L3/active-tracking items in L5.
- `selected_audit_only_count`: count of L2/audit-only items in L5.

### 10.4 How Quota Avoids Fake Quota Passes

Fake quota pass risk is controlled by the audit-only pool entry rules (Section 6.1):

- Only Solana candidates enter the pool.
- Only COMPLETE or PARTIAL source-status candidates enter the pool.
- Only CLEAN_DATA or ACCEPTABLE_PARTIAL_DATA quality candidates enter the pool.
- Only WATCH_ONLY-classified or D1-bucketed candidates enter the pool.
- INSTANT_REJECT candidates never enter the pool.
- Run-level deduplication by token_mint prevents a single token from occupying both
  an active-tracking slot and an audit-only slot.

A quota pass from audit-only candidates means: "this run observed valid Solana
WATCH_ONLY or D1 candidates from a governed source, and they passed quality checks,
but they did not qualify for active tracking." That is an honest quota pass.

### 10.5 What Happens If WATCH_ONLY/D1 Are Absent From the Governed Universe

If no WATCH_ONLY or D1 candidates are present in the governed candidate universe for
a given run, the audit-only pool is empty, and the quota cannot be satisfied by
audit-only candidates. The quota result remains `QUOTA_FAIL` with the original
violations. This is honest: the run did not observe the required lesson types.

### 10.6 Should Quota Become Conditional on Candidate Availability?

**No.** Making the quota conditional on candidate availability is Option B and has
been rejected for the reasons in Section 5. The quota should remain a hard requirement
for 6+ batches. A failing quota is a signal to the operator that the source mix or
candidate quality is insufficient for a balanced memory diet.

### 10.7 Should Quota Fail, Warn, or Downgrade If No Safe WATCH_ONLY/D1 Exists?

**Fail.** The quota must fail honestly if the required lesson types are absent. A
`QUOTA_WARNING` mode could be introduced as a future operator parameter, but the
default behavior must be `QUOTA_FAIL`. This forces the system to surface the
imbalance rather than silently producing a quota-passing but diet-weak batch.

The batch is still assembled and reported even when quota fails. The operator can
inspect the batch and decide whether to accept it for audit purposes. A failed quota
does not prevent the discovery run from completing; it only marks the batch as
`QUOTA_NOT_MET`.

---

## 11. Reporting Requirements

The following new fields must be present in the discovery run payload after V2-2M
implementation:

### 11.1 Audit-Only Pool Report (top-level key: `audit_only_report`)

| Field | Type | Description |
|---|---|---|
| `raw_watch_only_count` | int | WATCH_ONLY candidates in L0 (all normalized). |
| `audit_only_watch_only_count` | int | WATCH_ONLY candidates that entered L2. |
| `persisted_watch_only_count` | int | WATCH_ONLY candidates in L3 (expect 0 until further design). |
| `selected_watch_only_count` | int | WATCH_ONLY items in L5 (active-tracking + audit-only). |
| `raw_d1_count` | int | D1 candidates in L0. |
| `audit_only_d1_count` | int | D1 candidates that entered L2. |
| `persisted_d1_count` | int | D1 candidates in L3 (expect 0 until further design). |
| `selected_d1_count` | int | D1 items in L5. |
| `audit_only_candidate_count` | int | Total candidates in L2. |
| `selected_audit_only_count` | int | Total L2 candidates drawn into L5. |
| `active_tracking_selected_count` | int | Total L3 candidates in L5. |
| `quota_satisfied_by_audit_only_count` | int | Quota requirements met by L2 candidates. |
| `quota_satisfied_by_active_tracking_count` | int | Quota requirements met by L3 candidates. |
| `candidates_excluded_from_tracking_but_used_for_quota` | int | Alias for selected_audit_only_count; explicit label for clarity. |
| `reasons_by_audit_only_candidate` | dict[token_mint, reason] | Maps each audit-only pool candidate's mint to its pre_persistence_reject_reason. |
| `source_trace_by_audit_only_candidate` | dict[token_mint, trace] | Maps each audit-only pool candidate's mint to its source_name, source_channel, source_response_id. |

### 11.2 Additions to candidate_stage_report

| Field | Type | Description |
|---|---|---|
| `candidates_audit_only_total` | int | Total in audit-only pool. |
| `candidates_audit_only_watch_only` | int | WATCH_ONLY in audit-only pool. |
| `candidates_audit_only_d1` | int | D1 in audit-only pool. |
| `candidates_audit_only_selected_for_quota` | int | Drawn from audit-only pool into L5. |

All new fields in `candidate_stage_report` must satisfy the H.1 invariant: `int` or
`"NOT_MEASURED"`.

---

## 12. Implementation Handoff (V2-2M)

V2-2M implementation must build the following, in the stated order:

### Step 1 — Audit-Only Pool Capture

In `commands.py`, inside `_select_discovery_candidates()`, add a pre-capture step:

- Before the WATCH_ONLY rejection fires, check the quality/chain eligibility rules
  from Section 6.1.
- If eligible, append the candidate (with source trace, rejection reason, and
  `audit_only: True`) to a new `audit_only_pool` list.
- The rejection logic is unchanged: the candidate is still added to `rejected`.
- Return `audit_only_pool` as a third return value from `_select_discovery_candidates()`.

### Step 2 — Audit-Only Pool Signature

Update `_select_discovery_candidates()` to return
`(accepted, rejected, inspected, audit_only_pool)`.

Update the call site in `build_discover_candidates_once_payload()` to unpack the
fourth return value.

### Step 3 — Quota-Supplement Logic

After the normal selection loop, if the assembled batch of 6+ items fails the
WATCH_ONLY or D1 quota:

- Iterate `audit_only_pool` for WATCH_ONLY candidates; take the first eligible one
  not already in the batch (by token_mint dedup).
- Iterate `audit_only_pool` for D1 candidates; take the first eligible one.
- Append matched items to the assembled batch with `candidate_kind: "AUDIT_ONLY"`.
- Re-validate quota.

This supplement step must run only once (not in a loop) to prevent quota-inflation.

### Step 4 — Active-Tracking Guard

In `process_discovery_payload()` or at the call site, add a guard:

```
if candidate.get("audit_only"):
    raise ValueError("audit_only candidate must not enter process_discovery_payload")
```

This ensures audit-only candidates cannot accidentally be persisted.

### Step 5 — Reporting Updates

Update `build_discover_candidates_once_payload()` to:

- Build and attach `audit_only_report` (Section 11.1).
- Add new `candidate_stage_report` fields (Section 11.2).

### Step 6 — Validate Schema or JSON Column

Determine whether `printer_selection_batch_items` needs a new column for
`candidate_kind` and `audit_only` fields, or whether this metadata is stored
entirely in `pool_summary_json` and `selection_reason` for now. For V2-2M, storing
in JSON columns avoids a migration if the schema is not extended.

### Step 7 — Tests

Write `tests/test_v2_2m_audit_only_handoff.py` covering:

- WATCH_ONLY candidates enter audit-only pool, not accepted list.
- D1 candidates enter audit-only pool.
- Non-Solana candidates do not enter audit-only pool.
- INSTANT_REJECT candidates do not enter audit-only pool.
- FAILED source-status candidates do not enter audit-only pool.
- Audit-only candidates satisfy WATCH_ONLY quota in 6+ batch.
- Audit-only candidates satisfy D1 quota in 6+ batch.
- No audit-only candidate appears in printer_tracking_queue.
- No audit-only candidate appears in printer_scheduler_jobs.
- Quota fails honestly if audit-only pool is empty.
- Source trace and rejection reason are present for all audit-only items in batch.
- H.1 invariant holds for all new candidate_stage_report fields.
- Backward compat: single-request, single-channel run still works with no audit-only
  pool (empty pool, no crash, no fake quota pass).

---

## 13. Proof Handoff (V2-2N)

V2-2N must demonstrate on an isolated proof DB:

1. **Raw WATCH_ONLY/D1 candidates are visible** in `raw_watch_only_count` and
   `raw_d1_count` in a live run that produces both.
2. **WATCH_ONLY/D1 can enter the audit-only candidate pool:** `audit_only_candidate_count`
   > 0 in at least one run.
3. **Active tracking/scheduler rows do not increase from audit-only candidates:**
   `printer_tracking_queue` delta from audit-only candidates = 0;
   `printer_scheduler_jobs` delta from audit-only candidates = 0.
4. **Quota can be satisfied honestly if safe WATCH_ONLY/D1 candidates exist:** A run
   that would have failed quota pre-V2-2M now returns `quota_ok = True` when the
   audit-only pool supplies the missing types.
5. **Quota fails or reports blocked if they do not exist:** A run where the governed
   universe contains no WATCH_ONLY or D1 candidates returns `quota_ok = False` with
   `MISSING_D1_OR_WATCH_ONLY_UNAVAILABLE_IN_AUDIT_POOL` (or the existing violations).
6. **Selected batch distinguishes active-tracking vs audit-only candidates:**
   `active_tracking_selected_count` and `selected_audit_only_count` are both non-zero
   in a proof run that used audit-only candidates for quota.
7. **Downstream locked deltas remain zero:**
   - `printer_memory_windows`: delta = 0
   - `printer_memory_retrieval_queries`: delta = 0
   - `printer_memory_retrieval_matches`: delta = 0
   - `printer_paper_decisions`: delta = 0
   - `printer_paper_positions`: delta = 0
   - `printer_paper_trade_events`: delta = 0
   - `printer_paper_trade_audits`: delta = 0

---

## 14. Money-Usefulness Contribution

V2-2L does not unlock trading or live execution. It improves the quality and balance
of what Printer learns over time.

**Preserves negative/dead-token learning.** A memory machine that only learns from
tokens that survived active tracking gates will have a survivor-bias corpus. Dead
tokens, dying tokens, and low-activity tokens teach Printer what to avoid and when to
wait. The audit-only handoff ensures these lessons are not silently discarded at the
pre-persistence gate.

**Avoids all-active/all-attractive bias.** Without the repair, every 6+ selected
batch fails quota and is implicitly biased toward medium-activity TRACK_NORMAL
candidates from GeckoTerminal's new-pool channel. With the repair, the batch
explicitly includes one WATCH_ONLY and one D1 lesson minimum per 6+ batch, providing
a deliberate contrast with the active-tracking majority.

**Makes memory diet more balanced.** The V2-2B quota was designed precisely to prevent
homogeneous memory intake. Restoring functional quota compliance ensures the eventual
memory corpus reflects the full distribution of what Printer observes: pumps,
consolidations, dead tokens, and watchful conditions.

**Improves avoid/wait/trap learning.** WATCH_ONLY and D1 tokens represent scenarios
where the correct paper action is AVOID, WAIT, or NO_ACTION. Without these lessons,
Printer's memory diet teaches it primarily when to track — not when to step back.

**Protects against only learning from tokens that survive active tracking gates.** The
current gate architecture selects for TRACK_NORMAL/TRACK_FAST quality by design. That
selection is correct for active tracking. But memory learning requires more than what
active tracking quality teaches. The audit-only handoff maintains the active tracking
gate while opening a safe secondary path for the remaining lesson types.

---

## 15. What This Still Does Not Unlock

V2-2L and the downstream V2-2M/V2-2N lanes change only the discovery candidate-pool
handoff and quota semantics. The following remain completely locked:

- Memory generation
- Memory-window creation
- Retrieval activation
- Paper decisions
- BUY / SELL / HOLD
- Paper positions
- Trades
- Paper trade audits
- PnL
- Live trading
- Wallet / private keys / real funds
- Paid APIs
- Source Governor bypass
- Central Scheduler bypass
- Scoring / ranking / confidence / weighted token logic
- Embeddings / vectors
- WATCH_ONLY silent promotion to TRACK_NORMAL or TRACK_FAST
- D1 active tracking (unless a future lane explicitly approves)
- Audit-only candidates creating scheduler jobs or tracking queue entries

---

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Severity | Mitigation |
|---|---|---|
| Fake quota pass via low-quality audit-only candidates | High | Strict pool entry rules: Solana only; COMPLETE/PARTIAL source status; CLEAN_DATA/ACCEPTABLE_PARTIAL data quality; no INSTANT_REJECT; WATCH_ONLY or D1 only. |
| Audit-only candidate accidentally entering printer_tracking_queue | High (if unguarded) | Explicit `audit_only` flag on candidates; guard in process_discovery_payload call path that raises ValueError on `audit_only: True`. |
| Scheduler row growth from audit-only candidates | High (if unguarded) | Audit-only candidates never reach printer_tracking_queue; scheduler rows derive only from tracking queue entries; zero risk if guard is in place. |
| Source trace loss | Medium | Source trace (source_name, source_channel, source_response_id) must be carried through the audit-only pool and batch report; test must verify. |
| Rejection reason loss | Medium | `pre_persistence_reject_reason` must be preserved in audit-only pool entry; test must verify it is present in batch report. |
| WATCH_ONLY over-representation in batch | Low | Quota requires minimum 1, not unlimited; audit-only supplement draws only the minimum needed. |
| D1 over-representation in batch | Low | Same minimum-1 logic; audit-only supplement is capped at quota-required minimum. |
| Memory diet too negative from D1/WATCH_ONLY quota | Low | 1 WATCH_ONLY and 1 D1 in a 13-item batch is 15% audit-only — still majority active-tracking. Active-tracking remains primary. |
| Quota semantics becoming confusing | Medium | `active_tracking_selected_count` and `selected_audit_only_count` separate the two types clearly; operator can read both; documentation must be clear. |
| Audit-only candidate leakage into retrieval/decisions | Medium (if memory factory is modified unsafely) | Memory factory only processes tokens with tracking queue rows; audit-only candidates have none; leakage is structurally blocked. |
| Operator misunderstanding (quota passes but batch is "weaker") | Low | Batch report must clearly label each item's `candidate_kind`; `AUDIT_ONLY` items are visually distinguishable in the report. |
| Future automation using audit-only candidates incorrectly | Medium | `audit_only: True` flag must be respected by any future automation that reads batch items; documentation must note this contract. |
| D1 candidates not entering audit-only pool (classified TRACK_NORMAL, not WATCH_ONLY) | Medium | V2-2M implementation plan must explicitly handle the edge case where D1-bucketed candidates are TRACK_NORMAL-classified but rejected by a dead-activity filter. |
| Audit-only pool not populated on all runs (governed universe has no WATCH_ONLY/D1) | Low | Honest behavior; quota fails; audit-only count is zero; no fake pass. |
| Implementation introduces a regression in backward-compat single-request path | Low | `audit_only_pool` defaults to empty list if not populated; quota behavior unchanged for runs that produce no audit-only candidates. |

---

## 17. Readiness Verdict

**V2-2L WATCH_ONLY / D1 Quota Semantics and Candidate-Pool Handoff Design: DESIGN_COMPLETE_WITH_BLOCKERS**

The design is complete. The recommended architecture (Option A, audit-only candidate-
pool handoff) is defined in sufficient detail to proceed to V2-2M implementation.

Blockers before V2-3 can resume:

- V2-2M implementation must build the audit-only pool capture, quota-supplement
  logic, guard, and reporting updates, and must pass all specified tests.
- V2-2N bounded proof must demonstrate the handoff works end to end on an isolated
  proof DB and that all downstream locked deltas remain zero.
- Operator must accept V2-2N proof results.

Additional secondary blockers (documented but not in V2-2L scope):

- Token age / 15m evidence gap (all 70 candidates AGE_UNKNOWN in V2-2K).
- A3 / A4 gates blocked by token age.
- DexScreener generic-query productivity gap.
- PumpPortal / PumpSwap NOT_READY.

These remain in separate future lanes.

---

## 18. Next Recommended Lane

**V2-2M — WATCH_ONLY / D1 Candidate-Pool Handoff Implementation**

Only after operator accepts this V2-2L design.

V2-2M implements the audit-only pool capture, WATCH_ONLY/D1 handoff, quota-
supplement logic, active-tracking guard, and reporting updates described in Section 12.
It writes `tests/test_v2_2m_audit_only_handoff.py` and verifies all specified
invariants pass. It does not run a live proof.

After V2-2M, the next lane is:

**V2-2N — WATCH_ONLY / D1 Candidate-Pool Handoff Bounded Proof**

V2-2N runs the V2-2M implementation against a real source response on an isolated
proof DB, audits all report fields, and verifies that all downstream locked table
deltas remain zero. V2-2N does not commit proof DB artifacts to the repository.
