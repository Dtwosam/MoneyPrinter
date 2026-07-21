# V2-9.7E.4F Direct Pump Cutoff and Historical-Origin Design

**Status:** PASS (internal design review)
**Lane:** V2-9.7E.4F — Cutoff and Historical-Origin Design
**Authority:** 4E audit, 4B/4C freezes, 7B.2 ceilings, Governor registry
**Date:** 2026-07-21
**Baseline HEAD:** `cc748e9aea84cdf54140bbdcde04bc6c34549812`

## Design Verdict

`V2_9_7E_4F_DIRECT_PUMP_CUTOFF_HISTORICAL_ORIGIN_DESIGN_PASS`

Fits existing contracts and **45** underlying ceiling without migration, without
provider-label origin, without safety-rule weakening. Implementation authorized
only as **V2-9.7E.4G**.

---

## 1. Preserved invariants

- Immutable finalized cutoff from one `getSlot` (no bind-to-page, no mid-cycle raise).
- Finalized exact-mint Pump `create` origin only.
- Source Governor + Central Scheduler ownership on every fixture op.
- Zero ordinary retries / endpoint rotation / background reconnect.
- Underlying RPC ceiling **45**.
- `create_v2` blocked (`UNSUPPORTED_VERSION`).
- Two-or-none, freshness, cooldown, eligibility gates unchanged.
- No schema/migration/public command/financial unlock.

---

## 2. Operation budget (exactly 45 max)

| Activity | Underlying max | Governed kind |
|---|---:|---|
| Finalized cutoff | 1 | `pumpfun_create_event_subscription` |
| Live session sub/unsub | 2 | same session envelope |
| Program signature pages | 2 | `pumpfun_create_signature_backfill` |
| Program transaction decodes | 16 | `pumpfun_create_transaction_reference` |
| Origin signature pages (all mints) | **16** | `pumpfun_origin_signature_reference` |
| Origin transaction decodes (all mints) | **8** | `pumpfun_origin_transaction_reference` |
| **Total** | **45** | |

Governed request-id ceilings remain registry-aligned (session 1, backfill 2,
transaction 16, origin sig 8, origin tx 8). Multiple underlying pages/txs for
one mint may reuse one request_id so governed counts stay within 8+8 while
underlying uses the pools above.

---

## 3. Cutoff-bound program-history pagination

### 3.1 Freeze

1. Resolve cutoff once (`getSlot`, finalized semantics) before any signature page.
2. Page 1: newest program signatures (≤16).
3. For each row: if `slot > cutoff` → classify `POST_CUTOFF`, **skip** (no decode, no continuity fault, no decode-budget use).
4. Subsequent pages (max **2** total): chained with `before` = oldest signature of the previous page (deterministic).
5. Optional `until` / `complete_to_prior_cursor` when a trusted prior contiguous cursor exists.
6. Stop when: page ceiling hit, empty page, or complete-to-prior-cursor.

### 3.2 Post-cutoff handling

| Case | Continuity | Notes |
|---|---|---|
| Some in-cutoff rows admitted | Normal rules | Decode only in-cutoff successful finalized |
| All rows across both pages `POST_CUTOFF` | Cold → `UNKNOWN`; trusted prior incomplete → `GAPPED`/`UNKNOWN` per prior rules | Honest empty; **not** CONTIGUOUS |
| Mix post/pre cutoff | Post-cutoff ignored for admission | In-cutoff rows usable |

**Post-cutoff must not create a continuity emergency by itself.**

### 3.3 Cold start vs persisted cursor

| Prior | Interval complete meaning | Advance cursor? |
|---|---|---|
| None / not CONTIGUOUS | Cannot claim contiguous coverage | No; result `UNKNOWN` if history unknown rules fire |
| CONTIGUOUS boundary | `complete_to_prior_cursor` true and no genuine faults | Yes → largest admitted `(slot, signature)` |

### 3.4 Decode path (unchanged productivity rules from 4C)

Failed signatures filtered before decode; non-create non-fault; early-create stop 8;
decode ceiling 16; `create_v2` blocked.

---

## 4. Bounded historical mint-origin pagination

### 4.1 Per-mint algorithm

Inputs: `expected_mint`, immutable `cutoff_slot`, fixture operation stream.

1. Fetch up to **`ORIGIN_SIGNATURE_PAGE_CEILING = 3`** signature pages for the **mint** address (≤16 rows each).
2. Page 1 newest; page *n+1* uses `before` = oldest signature of page *n*.
3. Stop paging early if empty page (history exhausted) or fixture marks complete.
4. Collect all in-cutoff rows; sort candidates by `(slot, signature)` **ascending** (oldest first — create tends earliest).
5. Skip failed / non-finalized with redacted counts.
6. Attempt up to **`ORIGIN_TRANSACTION_ATTEMPTS_PER_MINT = 2`** `getTransaction` decodes in that order.
7. **Stop immediately** on first successful `decode_finalized_create(..., expected_mint=...)`.
8. On `NOT_SUPPORTED_CREATE` / failed meta: continue to next candidate within attempt budget.
9. On `UNSUPPORTED_VERSION` (`create_v2`): count, continue to older candidate (do not adopt).
10. On `MINT_MISMATCH` / malformed that disproves path: fail closed for that attempt; continue only if another candidate remains and attempts remain; if none succeed → no observation.
11. Exhausted pages/candidates without create → `observation=None`, rejections retained.

### 4.2 Global pools (enforced by combined accounting / fixture planning)

- Origin signature pages across all mints ≤ **16** underlying.
- Origin transactions across all mints ≤ **8** underlying.
- Admission order for mints unchanged (deterministic secondary admission).

### 4.3 Fail-closed cases

Unavailable/null tx, ceiling exhaustion, unsupported layout, mint mismatch without success, empty history → no origin claim. Provider labels never establish origin.

---

## 5. Continuity advancement and honest gaps

| Classification | Continuity fault? |
|---|---|
| `POST_CUTOFF` | No |
| `FAILED_TRANSACTION` | No |
| `NOT_SUPPORTED_CREATE` | No |
| `EARLY_CREATE_STOP` | No |
| `MISSING_FINALITY` / `UNAVAILABLE_HISTORY` / `MALFORMED_*` / `UNSUPPORTED_VERSION` / conflicts / decode ceiling / disconnect / incomplete trusted interval | Yes |
| Empty/unavailable history fixture | → `UNKNOWN` |

---

## 6. Redacted evidence fields

Direct cycle adds/keeps:

- `post_cutoff_count`
- `failed_signature_count`, `non_create_count`, `decode_attempts`
- rejection codes only (no raw payloads)

Mint lookup adds:

- `pages_used`, `decode_attempts`, rejection codes, observation or none

---

## 7. Internal design review

| Check | Result |
|---|---|
| No migration | PASS |
| No provider-label origin | PASS |
| No increase of 45 underlying ceiling | PASS |
| No eligibility/two-or-none/freshness/cooldown weaken | PASS |
| `create_v2` blocked | PASS |
| Fits Governor kinds | PASS |

**Blocker for implementation?** None.

## Exact next step

`V2-9.7E.4G` — implement this freeze with synthetic fixtures only.
