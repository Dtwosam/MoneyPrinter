# V2-9.7E.4B Direct Pump Create-Capture Productivity Design

**Status:** PASS (internal design review)
**Lane:** V2-9.7E.4B — Direct Pump Create-Capture Productivity Design
**Boundary:** design only until 4C implements exactly this freeze
**Date:** 2026-07-21
**Baseline HEAD:** `f3e8c37567982aaafa5ba53a5e5cce2cc97b18a9`
**Authority:** 4A audit, 7B.2 design, 7B.3A contract, 7B.4A adapter, Source Governor registry, Central Scheduler work types

## Design Verdict

`V2_9_7E_4B_DIRECT_PUMP_CREATE_CAPTURE_PRODUCTIVITY_DESIGN_PASS`

This design fits adopted contracts and ceilings, preserves Governor/Scheduler
ownership, requires **no migration**, and does **not** weaken origin authority,
eligibility gates, two-or-none, freshness, cooldown, Tracker, or financial locks.

Implementation is authorized only as **V2-9.7E.4C** executing this document.

---

## 1. Problem Recap (from 4A)

Both V2-9.7E pilots produced **zero** finalized Pump `create` observations because:

1. operational harness under-sampled (`limit=4` vs adopted 2×16 / 16);
2. program-level latest traffic is create-poor (failed + non-create rows);
3. failed rows still competed with successful rows under a pre-filter decode ceiling;
4. secondary origin matched only same-cycle creates — no mint-scoped historical lookup despite adopted origin request kinds.

Finalized origin authority remained correct. This design improves **productivity** without substituting provider labels for origin.

---

## 2. Frozen Scope

### In scope

- Direct program-level create capture productivity inside `pumpfun_direct` fixture owner.
- Continuity classification refinement (failed / non-create / genuine gaps).
- Bounded mint-scoped secondary origin lookup using **already adopted** request kinds:
  - `pumpfun_origin_signature_reference`
  - `pumpfun_origin_transaction_reference`
- Compact redacted decode-class evidence on cycle/lookup results.
- Combined executor fixture wiring for mint-origin operations (no schema change).
- Synthetic fixture proofs only.

### Out of scope

- Live network, pilot, V2-9.7F, V2-9.8
- `create_v2` adoption
- Eligibility gate order/content changes
- Two-or-none, freshness, cooldown, Tracker changes
- Migrations / public commands / retrieval / decisions / positions / PnL
- Retries, endpoint rotation, background reconnects
- Weakening finalized origin authority

---

## 3. Ownership and Request Map

| Activity | Source | Request kind | Scheduler job_kind | work_type | Max / cycle |
|---|---|---|---|---|---:|
| Live session envelope | `solana_rpc` | `pumpfun_create_event_subscription` | `DISCOVERY_REFRESH` | `DISCOVERY_PUMPFUN_LATEST` | 1 |
| Program signature page | `solana_rpc` | `pumpfun_create_signature_backfill` | `DISCOVERY_REFRESH` | `DISCOVERY_PUMPFUN_LATEST` | 2 |
| Program create decode | `solana_rpc` | `pumpfun_create_transaction_reference` | `DISCOVERY_REFRESH` | `DISCOVERY_PUMPFUN_LATEST` | 16 |
| Mint origin signature page | `solana_rpc` | `pumpfun_origin_signature_reference` | `DISCOVERY_REFRESH` | `DISCOVERY_ORIGIN_VERIFICATION` | 8 |
| Mint origin transaction | `solana_rpc` | `pumpfun_origin_transaction_reference` | `DISCOVERY_REFRESH` | `DISCOVERY_ORIGIN_VERIFICATION` | 8 |

Registry already admits all five Pump kinds. No new request kinds. No new tables.

Bypass rules unchanged: wrong source/request → `SOURCE_GOVERNOR_BYPASS`; wrong
scheduler identity → `CENTRAL_SCHEDULER_BYPASS`.

---

## 4. Direct Capture Freeze

### 4.1 Immutable finalized cutoff

1. Resolve cutoff **once** via governed `getSlot` with `commitment=finalized` semantics in the fixture envelope **before** backfill and before any `getTransaction`.
2. Cutoff is immutable for the cycle.
3. Signatures with `slot > cutoff` → `POST_CUTOFF` (no admission, no decode).
4. No bind-to-page cutoff (that pilot harness pattern is not production continuity).

### 4.2 Cold start and persisted cursor

| Prior cursor | Cycle outcome if interval otherwise healthy |
|---|---|
| `boundary=None` or continuity ≠ `CONTIGUOUS` | Cycle continuity **`UNKNOWN`**; boundary retained (usually `None`); observations still retained if exact |
| Trusted `CONTIGUOUS` + complete interval + no genuine continuity fault | Cycle **`CONTIGUOUS`**; boundary advances to largest admitted `(slot, signature)` in the interval |
| Genuine continuity fault (see §5) | **`GAPPED`**; prior contiguous boundary retained |

Cursor never advances on `GAPPED` or `UNKNOWN`.

### 4.3 Enumeration ceilings

| Ceiling | Value |
|---|---:|
| Signature pages | **2** |
| Rows per page | **16** |
| Max enumerated signatures | **32** |
| Transaction decode attempts (`getTransaction`) | **16** |
| Early-create stop | **8** successful supported creates |

Early-create stop: after **8** successful `create` observations in deterministic
decode order, remaining decode-eligible signatures are classified
`EARLY_CREATE_STOP` **without** `getTransaction` and **without** continuity
fault. Rationale: 8 matches `ORIGIN_VERIFY_ADMISSIONS` scale and is inside the
16 decode ceiling; surplus creates beyond dual activation are not required for
eligibility.

Zero ordinary retries. No endpoint rotation. No in-cycle reconnect after
disconnect (`live_disconnected` remains a genuine gap).

### 4.4 Failed-signature filtering (productivity)

For each deterministically ordered admitted signature:

1. If `err is not None` → classify `FAILED_TRANSACTION`, **do not** call `getTransaction`, **do not** consume decode budget, **do not** set continuity fault.
2. If `confirmationStatus != finalized` → classify `MISSING_FINALITY`, **do not** call `getTransaction`, **do** set continuity fault.
3. Else → enqueue as decode-eligible.

Only decode-eligible rows consume the 16-transaction ceiling. If decode-eligible
count exceeds 16 → admit first 16 by `(slot, signature)`, classify
`TRANSACTION_DECODE_CEILING`, set continuity fault.

### 4.5 Deterministic ordering and admission

1. Enumerate pages in fixture order (page 1 then page 2).
2. Admit by exact signature; conflicts → `CONFLICTING_DUPLICATE` + continuity fault.
3. Reconcile live notifications against finalized history (unchanged).
4. Sort admitted references by `(slot, signature)` ascending — **independent of RPC response order**.
5. Apply fail filter, then decode ceiling, then early-create stop.

### 4.6 Decode outcomes (supported create only)

Use existing `decode_finalized_create`. `create_v2` remains `UNSUPPORTED_VERSION`
(blocked). Successful non-create → `NOT_SUPPORTED_CREATE` (no observation).

Preserve exact creates with mint, bonding curve, ATA, creator
(`OBSERVED_EVIDENCE_ONLY`), signature, slot, block_time, program id.

---

## 5. Continuity Classification Freeze

| Classification | Observation? | Continuity fault? | Notes |
|---|---|---|---|
| Supported finalized `create` | Yes | No | |
| `FAILED_TRANSACTION` | No | **No** | Market noise; factual count retained |
| `NOT_SUPPORTED_CREATE` | No | **No** | Successful non-create activity |
| `EARLY_CREATE_STOP` | No | **No** | Budget productivity after 8 creates |
| `POST_CUTOFF` | No | No | Not admitted |
| `MISSING_FINALITY` | No | **Yes** | Incomplete history quality |
| `UNAVAILABLE_HISTORY` | No | **Yes** | Null/missing body or block time |
| `MALFORMED_TRANSACTION` | No | **Yes** | |
| `UNSUPPORTED_VERSION` / `create_v2` | No | **Yes** | Layout gap; still blocked |
| `WRONG_PROGRAM` / `AMBIGUOUS_CREATE` / `EVENT_MISMATCH` / `SIGNATURE_OR_SLOT_MISMATCH` / `MINT_MISMATCH` | No | **Yes** | |
| `CONFLICTING_DUPLICATE` | No | **Yes** | |
| `UNRECONCILED_LIVE_SIGNATURE` | No | **Yes** | |
| `TRANSACTION_DECODE_CEILING` | No | **Yes** | |
| Live disconnect | n/a | **Yes** | |
| Incomplete two-page interval (`complete_to_prior_cursor` false after max pages) | n/a | **Yes** | Real history gap / incomplete coverage |
| Empty page / unavailable history fixture | n/a | → `UNKNOWN` | Existing rule |

**Rule:** successful non-create traffic alone must **not** create a continuity
emergency. Failed signatures alone must **not** create a continuity emergency.
Genuine unavailable history, missing finality, malformed, unsupported version,
ceiling exhaustion, disconnect, conflict, and incomplete interval remain
explicit gaps.

---

## 6. Bounded Redacted Decode-Class Evidence

Each rejection retains:

- `code` (classification)
- `signature` (when applicable)
- `slot` (when applicable)

Cycle result exposes:

- `rejections` (full ordered classifications)
- `failed_signature_count`
- `non_create_count`
- `decode_attempts`
- existing observations / cursor / accounting

No full RPC transaction body persistence required. No provider rank fields.
Creator remains `OBSERVED_EVIDENCE_ONLY` and never eligibility input beyond
existing create observation fields.

---

## 7. Bounded Mint-Scoped Secondary Origin Lookup

### 7.1 When allowed

Only for secondary merged candidates **already admitted** by
`ORIGIN_VERIFY_ADMISSIONS` (≤8), when:

- mint does **not** already hold direct same-cycle `PUMPFUN_ORIGIN_CONFIRMED`; and
- a planned fixture (or later governed transport) supplies origin operations for that mint.

Provider labels never establish origin. Lookup failure → `FAILED` /
`no_finalized_create` (unchanged gate effect).

### 7.2 Procedure (per admitted mint)

1. **One** governed `pumpfun_origin_signature_reference` → one
   `getSignaturesForAddress` page for the **exact mint address** (not program),
   ≤16 rows, finalized commitment semantics.
2. Apply immutable cycle cutoff: drop `POST_CUTOFF`.
3. Filter failed signatures (count only); require finalized.
4. Sort remaining by `(slot, signature)` ascending.
5. **At most one** governed `pumpfun_origin_transaction_reference` →
   `getTransaction` on the earliest successful finalized signature.
6. `decode_finalized_create(..., expected_mint=<admitted mint>, cutoff_slot=cycle cutoff)`.
7. Exact mint match required. Mismatch → fail closed, no origin claim.
8. `create_v2` / unsupported → fail closed.
9. Zero retries to later signatures (one transaction ceiling per mint).

### 7.3 Ceilings

| Item | Max |
|---|---:|
| Origin signature lookups / cycle | 8 |
| Origin transactions / cycle | 8 |
| Pages per mint | 1 |
| Rows per mint page | 16 |
| Transactions per mint | 1 |

Underlying RPC operations count toward the combined intake underlying ceiling
(45) when executed inside the combined executor.

### 7.4 Work ownership

Origin lookups run under work_type `DISCOVERY_ORIGIN_VERIFICATION` (already in
the combined work order). They do not invent a parallel API loop.

---

## 8. Accounting

### Direct lane (unchanged maxima)

| Kind | Governed ceiling | Underlying ops |
|---|---:|---|
| session | 1 | getSlot + logsSubscribe + optional logsUnsubscribe |
| backfill | 2 | 1 getSignaturesForAddress per page |
| transaction | 16 | 1 getTransaction per decode attempt |
| underlying total | — | ≤45 |

### Origin lane (new usage of adopted kinds)

| Kind | Governed ceiling | Underlying ops |
|---|---:|---|
| origin signature | 8 | 1 getSignaturesForAddress per admitted mint attempted |
| origin transaction | 8 | 1 getTransaction per mint that reaches decode |

Failed mint signatures do not consume origin transaction budget.

---

## 9. Combined Executor Wiring (no migration)

Extend `CombinedDiscoveryFixtures` with optional:

- `origin_lookup_operations: Mapping[mint, Sequence[FixtureOperation]]`
- `origin_cutoff_slot: int | None` (immutable cutoff for mint lookups)

`_origin_and_pumpswap` order for each admitted secondary mint:

1. If direct already confirmed → unchanged.
2. Else if mint in `origin_proofs` with confirmed proof → CONFIRMED (existing).
3. Else if mint in `origin_lookup_operations` → run mint lookup; on observation → CONFIRMED with signature/slot evidence; else FAILED.
4. Else → FAILED `no_finalized_create`.

No gate list changes. No two-or-none changes. Empty create sets still allowed for
`DIRECT_COMPLETE`.

---

## 10. Internal Design Review Checklist

| Check | Result |
|---|---|
| Fits 7B.2 ceilings (2 pages, 16 tx, 8+8 origin) | PASS |
| Fits Governor registry kinds | PASS |
| Fits Scheduler work types | PASS |
| No migration / schema change | PASS |
| Finalized origin authority preserved | PASS |
| Provider labels cannot establish origin | PASS |
| `create_v2` remains blocked | PASS |
| Zero retries / no reconnect | PASS |
| Eligibility / two-or-none / freshness / cooldown untouched | PASS |
| Financial / retrieval locks untouched | PASS |

**Blocker for implementation?** None.

---

## 11. Money-Usefulness

Improves the chance that real finalized Pump creates become origin facts under
honest budgets, so two-slot activation can eventually rest on clean provenance
rather than trending labels. Lower false GAPPED from expected failed/non-create
noise improves operator signal quality without inventing completeness.

---

## 12. What Remains Locked After Design

Implementation details not yet coded; live proof; pilot; `create_v2` adoption;
gate/selection/financial unlocks.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

- Full 2×16 still may yield zero creates in hostile markets.
- One origin transaction per mint may miss create if earliest successful mint tx is not Pump `create`.
- Free RPC retention for mint history remains unproved.
- Early-create stop at 8 may leave later creates unread (acceptable under ceiling policy).

## Exact Next Step

`V2-9.7E.4C — Direct Pump Create-Capture Productivity Implementation` executing
this design only.
