# V2-9.7E.4G Direct Pump Cutoff and Historical-Origin Repair Closeout

**Status:** PASS
**Lane:** V2-9.7E.4G — Cutoff and Historical-Origin Repair
**Design authority:** `docs/printer-v1-v2-9-7e-4f-direct-pump-cutoff-historical-origin-design.md`
**Audit:** `docs/printer-v1-v2-9-7e-4e-direct-pump-cutoff-historical-origin-audit.md`
**Date:** 2026-07-21
**Baseline HEAD:** `cc748e9aea84cdf54140bbdcde04bc6c34549812`

## Final Verdict

`V2_9_7E_4EFG_DIRECT_PUMP_CUTOFF_HISTORICAL_ORIGIN_PASS`

Phases 4E (audit), 4F (design), and 4G (repair) completed. Synthetic fixture proof
only. No network, live proof, or pilot.

## Todo / Checklist

- [x] Verify HEAD `cc748e9…`.
- [x] 4E audit of cutoff lag + mint newest-only limitation.
- [x] 4F design freeze; internal PASS (no migration / no ceiling raise / no safety weaken).
- [x] 4G implement program post-cutoff accounting + multi-page mint origin.
- [x] Focused synthetic proofs + regressions.
- [x] Diff checks; commit lane files only (exclude 4D artifacts).

---

## Root Causes (from 4E)

1. **Program empty sample (4D):** Immutable finalized `getSlot` can lag multi-node public RPC tip; newest signature pages may be entirely `slot > cutoff`. Rows correctly skipped as `POST_CUTOFF`, but without older `before` pages the usable in-cutoff sample stayed empty.
2. **Mint origin (4D):** Single newest page + one earliest-of-newest decode never reached historical Pump `create` for aged trending mints → `NOT_SUPPORTED_CREATE`.

Classification: productivity + RPC limitation + design gap (4C single-page mint), not origin-authority defect.

---

## Final Design (executed)

See 4F. Highlights implemented:

- Immutable cutoff preserved; post-cutoff **skip only** (no decode budget, no continuity fault alone).
- Program path counts `post_cutoff_count`; two-page fixtures can place in-cutoff creates on later older pages.
- Mint path: up to **3** signature pages, up to **2** transaction attempts, oldest-first, **stop immediately** on exact finalized create.
- Global pools documented: origin pages ≤16, origin txs ≤8, total underlying ≤45.
- `create_v2` remains blocked; provider labels never establish origin.

---

## Files Changed

| File | Role |
|---|---|
| `docs/printer-v1-v2-9-7e-4e-direct-pump-cutoff-historical-origin-audit.md` | Audit |
| `docs/printer-v1-v2-9-7e-4f-direct-pump-cutoff-historical-origin-design.md` | Design |
| `docs/printer-v1-v2-9-7e-4g-direct-pump-cutoff-historical-origin-repair-closeout.md` | This closeout |
| `src/printer_v1/sources/pumpfun_direct.py` | Repair owner |
| `tests/test_v2_9_7e_4g_cutoff_historical_origin.py` | Synthetic proofs |

**Not committed / not rewritten as authority:** uncommitted 4D harness, evidence JSON, 4D closeout (read-only evidence only).

---

## Operation Ceilings

| Pool | Max |
|---|---:|
| Underlying total | 45 |
| Program pages | 2 |
| Program txs | 16 |
| Origin pages (global) | 16 |
| Origin txs (global) | 8 |
| Origin pages per mint | 3 |
| Origin txs per mint | 2 |

---

## Continuity Behavior

| Class | Fault? | Decode? |
|---|---|---|
| `POST_CUTOFF` | No | No |
| Failed / non-create | No | Failed no; non-create after fetch only |
| Genuine unavailable / unsupported / ceiling / disconnect | Yes | No claim |

Post-cutoff rows cannot empty a sample that still has older in-cutoff pages within the two-page bound (proven).

---

## Historical-Origin Flow

1. Up to 3 mint signature pages (newest then older).
2. Filter post-cutoff / failed / non-finalized.
3. Oldest-first decode attempts (≤2).
4. Immediate stop on exact mint create.
5. Continue after non-create / create_v2 / failed meta within budget.
6. Exhausted / null → fail closed, no origin claim.

---

## Tests

| Suite | Result |
|---|---|
| `tests/test_v2_9_7e_4g_cutoff_historical_origin.py` | PASS |
| `tests/test_v2_9_7e_4c_direct_pump_create_capture_productivity.py` | PASS |
| `tests/test_v2_9_7d_7b_4a_direct_pump_adapter.py` | PASS |
| `tests/test_pumpfun_direct_create_contract_fixture.py` | PASS |
| Combined 4G+prior direct | **39 passed** |
| `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py` | PASS |
| `tests/test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py` | PASS |
| Network / live / pilot | **none** |

Proved: first-page post-cutoff + later-page create; mixed pages; cold/persisted cursor; deterministic order; post-cutoff skips decode budget; mint create on later page; multi-attempt non-create then create; mint mismatch; create_v2 blocked; exhausted/null history; governor/scheduler; replay.

---

## Money-Usefulness

Raises the chance that:

- program capture still sees in-cutoff creates when tip pages are post-cutoff but older pages remain in budget;
- secondary mint origin can walk past recent trades toward the real Pump create

without inventing origin from labels or weakening finalized authority.

---

## Remaining Unknowns

- Whether 2 program pages always pierce public-RPC lag in live markets.
- Whether 3 mint pages + 2 txs suffice for hot aged mints under free retention.
- Live `create_v2` prevalence.

---

## What Remains Locked

- Live re-proof / pilot / V2-9.7F / V2-9.8
- Ceiling increases, migrations, public commands
- Eligibility / freshness / cooldown / Tracker changes
- Retrieval, decisions, positions, trades, PnL
- `create_v2` adoption

## Functionality Risks / Setbacks / Efficiency Blockers

1. Extreme tip lag beyond 32 program signatures still empties direct sample.
2. Hot mint histories deeper than 3×16 still miss create.
3. Free RPC retention gaps remain.
4. Operator harnesses must supply `before`-chained older pages (owner is fixture-driven).

## Stop Boundary

Stop after commit. Do not run live proof, pilot, V2-9.7F, or V2-9.8.
