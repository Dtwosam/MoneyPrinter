# V2-9.7E.4E Direct Pump Cutoff and Historical-Origin Productivity Audit

**Status:** PASS
**Lane:** V2-9.7E.4E — Direct Pump Cutoff and Historical-Origin Productivity Audit
**Boundary:** read-only audit; no network; no production change
**Date:** 2026-07-21
**Baseline HEAD:** `cc748e9aea84cdf54140bbdcde04bc6c34549812`

## Verdict

`V2_9_7E_4E_DIRECT_PUMP_CUTOFF_HISTORICAL_ORIGIN_AUDIT_PASS`

Concrete fix targets are identified for a bounded design/repair. This does **not**
implement them and does **not** authorize live proof or pilot.

## Todo / Checklist

- [x] Verify HEAD `cc748e9…`.
- [x] Read 4A–4D evidence, 4B/4C design, adapter, origin path, governor contracts.
- [x] Classify cutoff lag, pagination, mint-history depth, budget.
- [x] Write this audit (no network).

## Method

Static read of:

- `src/printer_v1/sources/pumpfun_direct.py` (`run_fixture_cycle`, `run_mint_origin_lookup`)
- 4B design / 4C closeout
- Uncommitted 4D closeout + redacted `V2_9_7E_4D_LIVE_PROOF_RESULT.json`
- 7B.2 ceilings; Source Governor registry kinds

No network calls in this phase.

---

## 1. Why finalized `getSlot` cutoff lagged all signature slots (4D)

### Observed (4D, one live run)

| Fact | Value |
|---|---|
| Cutoff from `getSlot` + `commitment=finalized` | `434336267` |
| Program signature pages | 2 × 16 = 32 |
| Classifications | **`POST_CUTOFF` × 32** |
| Decode attempts | 0 |
| Creates | 0 |

### Mechanism

1. Owner/harness freezes cutoff **once** via `getSlot` **before** signature pages (4B immutable-cutoff rule).
2. `getSignaturesForAddress` returns **newest-first** program activity.
3. Free public RPC (`api.mainnet-beta.solana.com`) is a multi-backend pool: a subsequent signature response can include slots **greater than** a just-observed finalized slot from another backend or a slightly lagging `getSlot`.
4. Owner correctly rejects `slot > cutoff` as `POST_CUTOFF` (no admission, no decode).
5. With **only two pages**, if those 32 newest rows are entirely newer than cutoff, the cycle never sees any in-cutoff signature — even though older program history almost certainly exists.

### Classification

| Aspect | Class |
|---|---|
| Rejecting post-cutoff rows | **correct contract behavior** (not a defect) |
| Empty usable sample when first pages are all post-cutoff | **productivity limitation** + **RPC limitation** (multi-node lag) |
| Not walking older until in-cutoff material appears within page budget | **implementation / design gap** in transport+owner pagination expectations |
| Treating post-cutoff as continuity emergency | **not** current 4C behavior (`POST_CUTOFF` is non-fault) — good |

---

## 2. Should newer-than-cutoff signatures be skipped vs continuity gaps?

**Answer: skip, do not treat as continuity faults.**

| Rule | Rationale |
|---|---|
| `POST_CUTOFF` → no admission, no decode, **no continuity fault** | Already frozen in 4C; still correct |
| Post-cutoff-only enumeration after max pages | Honest empty/create-poor cycle; cold start stays `UNKNOWN`; do **not** invent CONTIGUOUS |
| Must not empty the *usable* sample if older in-cutoff rows exist within page budget | Requires pagination that continues **older** via `before` while pages remain |

---

## 3. Bounded use of `before` / `until` / cursor / cutoff-anchor

| Tool | Role |
|---|---|
| Immutable `getSlot` cutoff | Admission ceiling only; never raised mid-cycle; no bind-to-page |
| `before` | **Primary** pagination: walk older from oldest signature of prior page |
| `until` | Optional stop at prior contiguous cursor signature when present |
| Prior contiguous cursor | Lower bound for CONTIGUOUS interval completeness; cold start has none |
| Cutoff-anchor signature | **Not** required if `before` walk continues until in-cutoff rows appear or pages exhaust |

**Correct bounded program walk (conceptual):**

1. Freeze cutoff.
2. Page 1: newest signatures.
3. Admit only `slot ≤ cutoff`; count `POST_CUTOFF` skips.
4. If pages remain and more history needed: next page with `before=<oldest signature of previous page>` (deterministic).
5. Stop at page ceiling (2), empty page, or `complete_to_prior_cursor`.

---

## 4. Cold start without contiguous cursor

| State | Behavior today | Audit note |
|---|---|---|
| `prior_cursor.boundary is None` or continuity ≠ CONTIGUOUS | Cycle → `UNKNOWN`; boundary not advanced | Correct |
| Observations still retained if exact creates found | Yes | Correct |
| `complete_to_prior_cursor` | Usually false on cold busy program | Yields non-contiguous / unknown; honest |

Cold start must still **search** in-cutoff newest history via `before` walk; UNKNOWN does not mean “only read tip and stop.”

---

## 5. Page ordering and reaching ≤ cutoff

- Solana returns pages newest-first.
- Deterministic owner order for decode remains `(slot, signature)` ascending among **admitted** rows.
- Reaching ≤ cutoff requires **older pages**, not reordering within a tip page of only post-cutoff rows.
- Fixture owner consumes planned pages; transport/harness must supply `before`-chained older pages.
- **Defect class:** 4D harness paged twice but both pages remained post-cutoff under RPC lag — within 2-page ceiling this is also **RPC/productivity limitation**. Repair must at least prove owner+pagination contract for “page1 all post-cutoff, page2 older in-cutoff.”

---

## 6. Why mint-scoped lookup searched only newest history

4C freeze:

- `ORIGIN_SIGNATURE_PAGE_CEILING = 1`
- One page ≤16 rows (newest)
- One `getTransaction` on earliest successful finalized among that page

For trending pilot mints, the **original Pump `create` is typically far older** than the newest 16 mint-involving transactions (which are buys/sells). Earliest-of-newest-16 is still a recent non-create → `NOT_SUPPORTED_CREATE` (4D).

### Classification

**Design/productivity limitation** (implementation faithfully followed 4C), not decoder crash.

---

## 7. Does mint-address signature history contain the original create?

| Claim | Assessment |
|---|---|
| Pump `create` includes the mint account | **Yes** (create account[0] = mint) → mint appears in that tx |
| `getSignaturesForAddress(mint)` eventually lists the create | **Yes**, if RPC retains that history |
| Newest page alone lists the create for active mints | **Usually no** |
| Public RPC retention of full mint history | **Not guaranteed** → `UNAVAILABLE_HISTORY` / empty pages possible |

Classification: **productivity limitation** + residual **RPC retention unknown**.

---

## 8. Bounded depth for historical origin

Within **45 underlying** and no governed-ceiling *increase*:

| Pool | Max underlying |
|---|---:|
| Direct session (slot+sub+unsub) | 3 |
| Program signature pages | 2 |
| Program decode txs | 16 |
| Origin signature pages (all mints) | **16** |
| Origin decode txs (all mints) | **8** |
| **Sum** | **45** |

Per-mint practical bound under global pools:

- up to **3** signature pages (16 rows) walking older with `before`
- up to **2** transaction attempts oldest-first until exact create or exhaust
- stop immediately on successful finalized supported create

Still may fail for very old hot mints — honest `FAILED` / exhausted history.

---

## 9. Public RPC retention / null history

| Risk | Class |
|---|---|
| Null `getTransaction` | `UNAVAILABLE_HISTORY` (genuine gap) |
| Empty signature page mid-walk | history exhausted / unavailable |
| Multi-node slot disagreement | RPC limitation (already seen as post-cutoff tip) |

---

## 10. Finding classification summary

| Finding | Class |
|---|---|
| Post-cutoff reject is correct | contract-correct |
| Tip-only pages can leave zero in-cutoff rows under RPC lag | productivity + RPC limitation |
| Need deterministic older `before` pagination contract in owner/tests | design gap → repair |
| Mint origin single newest page | design/productivity limitation (4C) |
| One tx on earliest-of-newest fails for aged mints | design/productivity limitation |
| Decoder create path | not primary defect |
| Provider labels as origin | not used (good) |
| Need >45 RPC | **not required** if pools rebalanced as above |
| Whether 3 pages always reach create | **unknown** / residual limitation |

## Concrete fix targets (for 4F)

1. Program path: prove and enforce cutoff-bound pagination expectations; post-cutoff skips never consume decode budget; post-cutoff-only after max pages is honest empty, not false CONTIGUOUS.
2. Mint path: multi-page older walk + multi-attempt decode with immediate stop on exact create; keep global origin page/tx pools inside 45.
3. Compact redacted counts: `post_cutoff_count`, origin pages used, origin txs used.
4. No migration; no `create_v2`; no eligibility changes.

## Next

`V2-9.7E.4F` design freeze, then `V2-9.7E.4G` repair if design PASS.
