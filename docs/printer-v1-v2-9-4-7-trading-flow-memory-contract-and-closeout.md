# Printer V1 V2-9.4.7 Trading-Flow Clean-Memory Contract and Closeout

Lane: `V2-9.4.7 - Design and implement the trading-flow clean-memory contract`
Base commit: `b14d95e`

Preflight passed: HEAD exactly `b14d95e`, tracked tree clean, no proof runtime,
no one-proof lock (`runs/v2-9-one-proof.lock.json` absent).

---

# PHASE A — STATIC CONTRACT DESIGN

## A.0 Headline finding: the premise of this lane is false

The V2-9.4.5 and V2-9.4.6 closeouts both recorded, as a risk, that *partial
trading flow still gates clean promotion* and that this was the most likely
remaining blocker for an Attempt 7. **That claim is false. It was never verified
against the code, and this lane disproves it.**

Measured against the real resolver on an Attempt 6-shaped fixture whose flow
payload has no split volume and no wallet fields:

```
clean_memory_context_ready = True
blockers                   = []
trading_flow  can_support_clean_memory = True   status = READY
trading_flow_payload_quality_label     = TRADING_FLOW_CONTEXT_PARTIAL
flow_memory_gate_label                 = FLOW_CONTEXT_CAUTION
```

Partial trading flow **already** permits clean memory, and the flow section
**already** reports its partial status truthfully while doing so. The approved
contract below is, in the live path, already implemented.

The real defect this lane found is different and narrower: **two exported
helpers encode the opposite contract**, and one of them is unsatisfiable by any
provider the repository actually has. They are dead in production today, so they
cause no live harm — but they are a live trap for whoever wires them in.

## A.1 What the specifications actually require

| Source | Rule |
| --- | --- |
| `AGENTS.md:549` | "Trading flow and chart behavior are memory **labels, not standalone signals**." |
| `AGENTS.md:69` | `flow score` is in the forbidden list — no scoring/ranking/weighting. |
| `printer-v1-memory-factory-guide.md:593` | Clean memory requires "trading flow/chart evidence is available **where relevant**" — a qualified requirement, not "every field present". |
| `printer-v1-memory-factory-guide.md:586-589` | Precedent for optional context: market regime and chain heat may be "attached **or explicitly recorded as acceptable/known missing under current policy**". |
| `printer-v1-memory-factory-guide.md:601` | "Clean memory is evidence quality plus outcome clarity, not price performance." |
| `solana-builder-source-of-truth/README.md:103` | "**No fabrication.** Missing data is recorded as missing/failed. No source may invent a program ID, endpoint, or field." |
| `source-governor-evidence-rules.md:108` | Precedent: a missing/mismatched T3 trace "must leave token age **unknown**" — the record survives without the optional field; it is never estimated. |

The specifications support a clear, safe contract. Flow is a memory *label*.
Absent optional context is recorded as unknown, never invented, and does not by
itself destroy an otherwise trustworthy memory.

## A.2 Provider reality (proved by repository evidence)

Established by inspection of `src/printer_v1/sources/dexscreener.py` and a grep
across all of `src/printer_v1/sources/`:

| Field group | Supplied? | Evidence |
| --- | --- | --- |
| `volume_5m/15m/1h/24h` | YES | `dexscreener.py:433` |
| `txns_5m/1h/24h` | YES | `dexscreener.py:436-438` |
| `buys_5m/1h/24h`, `sells_5m/1h/24h` (**counts**) | YES | `dexscreener.py:439-444` |
| `buy_volume_*` / `sell_volume_*` (**split volume**) | **NO** | no adapter in `src/printer_v1/sources/` emits these |
| `unique_wallets_*`, `new_wallets_*`, `repeat_wallets_*` | **NO** | no adapter in `src/printer_v1/sources/` emits these |

No provider claim beyond this is asserted. Whether any keyless, free, permitted
source could supply split volume or wallet participation is
**UNKNOWN_REQUIRES_RESEARCH** — it is not proved by current repository evidence
and this lane does not assume it.

Consequence: `classify_trading_flow_payload_quality`'s `required_for_clean` set
(`buy_volume_5m`, `sell_volume_5m`, `unique_wallets_5m`) **can never be satisfied
in production**. `TRADING_FLOW_CONTEXT_CLEAN` is unreachable from live data;
`TRADING_FLOW_CONTEXT_PARTIAL` / `FLOW_CONTEXT_CAUTION` is the best real outcome.

## A.3 The seven determinations

### 1. Mandatory fields for authentic, trustworthy flow

- `captured_at` (a real observation time)
- Target identity: `token_id` or `token_mint`, plus `pair_id`/`pair_address` for provenance
- At least one real flow fact: `volume_5m|volume_15m|txns_5m|txns_15m|buys_5m|sells_5m|buy_volume_5m|sell_volume_5m`
- Acceptable `source_status` and `data_quality_label`
- A clean governed source trace (request/response ids resolving to a clean, non-failed trace)
- Resolved `flow_direction_label` and `flow_pressure_label` (not `FLOW_UNKNOWN` / `PRESSURE_UNKNOWN`)

### 2. Missing DexScreener fields that cause `TRADING_FLOW_CONTEXT_PARTIAL`

`buy_volume_5m`, `sell_volume_5m`, `unique_wallets_5m` — exactly the
`required_for_clean` triple. All three are unavailable from every current
adapter (A.2).

### 3. Optional context that may remain explicitly UNKNOWN

- Split buy/sell **volume** (`buy_volume_*`, `sell_volume_*`)
- Wallet participation (`unique_wallets_*`, `new_wallets_*`, `repeat_wallets_*`)

Their absence surfaces as `WALLETS_UNKNOWN` and
`TRADING_FLOW_CONTEXT_PARTIAL` / `FLOW_CONTEXT_CAUTION`. These stay visible in
the flow section even when the overall memory is clean.

### 4. Deterministically derivable from Printer's exact snapshot ledger

From persisted snapshot facts only, with no new source call:

- Buy/sell **count** imbalance → `imbalance_label` (count ratio)
- Directional pressure from the count ratio → `flow_pressure_label`
- `volume_5m|15m` → `volume_activity_label`
- `txns_5m|15m` → `tx_activity_label`
- Composite `flow_direction_label`

### 5. NOT derivable — must never be fabricated or estimated

- **Split buy/sell volume.** DexScreener supplies transaction *counts*, not the
  USD volume on each side. Volume cannot be split by count without inventing an
  average trade size. Forbidden.
- **Unique / new / repeat wallet counts.** No provider supplies them; they are
  not recoverable from aggregates.
- **Any provider data never collected.** Recorded missing, never back-filled.

Zero is not a permitted stand-in for "unknown": `0` is a factual claim that no
wallets traded, and `observed_zero_pair` deliberately treats a real `(0,0)` as
`BALANCED`. Defaulting absent fields to zero would corrupt that distinction.

### 6. Conditions that must still block clean memory

- Failed, stale, or conflicting sources → `TRADING_FLOW_CONTEXT_STALE` / `_CONFLICTING` / `_DO_NOT_USE_FOR_MEMORY`
- Token/pair/provenance mismatch, or a missing/invalid governed trace
- Insufficient exact-ledger coverage (`< 2` snapshots, boundary mismatch, non-ledger rows)
- Contradictory flow evidence (`IMBALANCE_NOISY` from count/volume disagreement)
- `FLOW_WASH_LIKE` and any authenticity failure → `FLOW_CONTEXT_DO_NOT_TRAIN`
- Missing mandatory fields → `TRADING_FLOW_CONTEXT_UNKNOWN` → `FLOW_CONTEXT_AUDIT_ONLY`

### 7. May trustworthy memory stay CLEAN_MEMORY when optional flow fields are unknown?

**Yes** — and it already does. `memory/quality.py:43` rejects only
`FLOW_CONTEXT_DO_NOT_TRAIN`; `FLOW_CONTEXT_CAUTION` never produces
`REJECT_DIRTY_FLOW_CONTEXT`. The resolver's `flow_clean` requires known
direction/pressure and a gate outside `{AUDIT_ONLY, DO_NOT_TRAIN}`, which
`CAUTION` satisfies. This is consistent with guide:593 ("where relevant") and
guide:586-589 (explicitly-known-missing optional context).

## A.4 Clean / partial / dirty rules (the approved contract)

| Condition | Flow gate | Memory effect |
| --- | --- | --- |
| Mandatory present, optional present | `FLOW_CONTEXT_ACCEPTABLE` | may be `CLEAN_MEMORY` |
| Mandatory present, optional unknown | `FLOW_CONTEXT_CAUTION` (partial, visible) | **may be `CLEAN_MEMORY`** |
| Mandatory missing / unresolvable | `FLOW_CONTEXT_AUDIT_ONLY` | not clean |
| Stale / conflicting source | `FLOW_CONTEXT_AUDIT_ONLY` | audit-only |
| Failed / dirty / do-not-train source | `FLOW_CONTEXT_DO_NOT_TRAIN` | `DIRTY_MEMORY` |
| `FLOW_WASH_LIKE` (authenticity) | `FLOW_CONTEXT_DO_NOT_TRAIN` | `DIRTY_MEMORY` |

Evidence quality and market outcome stay separate (V2-9.4.5). Negative outcomes
may be clean. Partial status stays visible even when the memory is clean.

## A.5 Affected modules

| Module | Assessment |
| --- | --- |
| `context_evidence/window_15m.py` (`flow_clean`) | **Already correct.** No change. |
| `memory/quality.py` | **Already correct** (blocks only `FLOW_CONTEXT_DO_NOT_TRAIN`). No change. |
| `trading_flow/parser.py` | Correct: absent fields stay `None`, never defaulted. No change. |
| `trading_flow/classifier.py` — `classify_trading_flow_payload_quality`, `classify_flow_memory_gate` | Correct and truthful. No change. |
| `trading_flow/classifier.py` — `trading_flow_context_can_support_clean_memory` | **Drifted.** Requires `TRADING_FLOW_CONTEXT_CLEAN`; unreachable in production; always `False`; contradicts the resolver. Align. |
| `trading_flow/lookup.py` — `trading_flow_snapshot_is_valid_for_memory` | **Drifted.** Same unreachable requirement; makes `find_trading_flow_snapshot_before` / `find_nearest_trading_flow_snapshot` structurally always return `None`. Align. |
| E2Q, Lane Q | Zero flow references. Unaffected. |
| Lane K / E2Z | Consumes `clean_memory_context_ready` only (`e2z_clean_memory_creation.py:131`). Unaffected. |

## A.6 Migration assessment

**No migration required.** No schema change, no new column, no CHECK change. The
contract uses existing enum values already present in
`trading_flow/contracts.py`. Zero files under `migrations/`.

## A.7 Phase A verdict

None of the BLOCKED conditions apply:

- the active specifications **do** support a clear safe contract (A.1);
- **no** new provider is required — clean memory is already reachable without one;
- **no** migration is required (A.6);
- clean memory does **not** require weakening any authenticity or provenance
  gate — every gate in A.6/§6 stays intact and fixture-proven.

Phase A proves a safe, migration-free contract. Proceeding to Phase B with the
smallest change: align the two drifted helpers so the codebase encodes this
contract exactly once. The live path is already compliant and is left untouched.

---

# PHASE B — IMPLEMENTATION

## B.1 What changed

The live path was already compliant (A.0) and is **untouched**. The smallest
change is to align the two drifted helpers so the codebase encodes the approved
contract exactly once.

| File | Change |
| --- | --- |
| `src/printer_v1/trading_flow/classifier.py` | `trading_flow_context_can_support_clean_memory` now accepts `FLOW_CONTEXT_ACCEPTABLE` **or** `FLOW_CONTEXT_CAUTION`, instead of requiring the unreachable `TRADING_FLOW_CONTEXT_CLEAN` + `ACCEPTABLE` pair. Every fault still routes to `AUDIT_ONLY`/`DO_NOT_TRAIN` and is still rejected. |
| `src/printer_v1/trading_flow/lookup.py` | `trading_flow_snapshot_is_valid_for_memory` accepts `TRADING_FLOW_CONTEXT_PARTIAL` alongside `_CLEAN`. Its `COMPLETE`/`CLEAN_DATA`/`blocks_clean_memory`/freshness checks are unchanged. |

Both functions are unused by production code today (grep across `src/`), so this
change has **no live behaviour effect**. Its value is removing a trap: either
function, if wired in, would have re-introduced exactly the false blocker that
V2-9.4.5 and V2-9.4.6 removed elsewhere.

No production module needed a semantic change:

- `context_evidence/window_15m.py` `flow_clean` already permits `CAUTION`.
- `memory/quality.py:43` already rejects only `FLOW_CONTEXT_DO_NOT_TRAIN`.
- `trading_flow/parser.py` already leaves absent fields `None`, never `0`.
- `classify_trading_flow_payload_quality` already labels partial payloads
  `PARTIAL` — which is truthful and must stay visible.

Deliberately **not** done: `required_for_clean` was left as-is. It is the reason
the label reads `PARTIAL`, and that label is *correct* — the evidence genuinely
is partial. The contract requires partial status to stay visible, not to be
redefined away.

## B.2 Contract properties, measured

| # | Required property | Status |
| --- | --- | --- |
| 1 | Optional unavailable fields remain explicit UNKNOWN | already held; fixture-pinned |
| 2 | Their absence alone does not make evidence DIRTY_MEMORY | already held; fixture-pinned |
| 3 | Mandatory flow evidence remains required | already held; fixture-pinned |
| 4 | Ledger-derived summaries use only persisted facts | already held |
| 5 | No synthetic buy/sell volume or wallet values | already held; fixture-pinned |
| 6 | `FLOW_WASH_LIKE` / authenticity failures stay DO_NOT_TRAIN | already held; fixture-pinned |
| 7 | Failed/stale/conflicting/mismatched fails closed | already held; fixture-pinned |
| 8 | Partial flow status visible even when memory is clean | already held; fixture-pinned |
| 9 | Outcome labels truthful and independent of quality | held since V2-9.4.5; fixture-pinned |
| 10 | Retrieval/decisions/financials locked | already held; fixture-pinned |

---

# PHASE C — BOUNDED FIXTURE PROOF

`tests/test_v2_9_4_7_trading_flow_memory_contract.py` — **13 passed, 12
subtests**. Pure in-memory classifier/gate fixtures; no DB required.

| # | Fixture | Result |
| --- | --- | --- |
| 1 | Complete evidence, split volume + wallets absent | flow visibly `PARTIAL`/`CAUTION`; memory `CLEAN_MEMORY`; no `REJECT_DIRTY_FLOW_CONTEXT` |
| 2 | Fully evidenced round trip | `CLEAN_MEMORY`, `ROUND_TRIP` preserved, zero rejection reasons |
| 3 | Fully evidenced dump / pump-and-dump / missed upside / dead token | `CLEAN_MEMORY`, truthful negative outcome |
| 4 | Missing mandatory identity or flow fact | `TRADING_FLOW_CONTEXT_UNKNOWN` → `AUDIT_ONLY`; not clean |
| 5 | Failed / dirty source | `DIRTY_MEMORY` |
| 5 | Stale / conflicting source | `AUDIT_ONLY_MEMORY` |
| 5 | Stale by age | cannot support clean memory |
| 6 | Insufficient ledger coverage (`<2` snapshots) | `DIRTY_MEMORY`, `REJECT_MISSING_SNAPSHOTS` |
| 6 | Incomplete-coverage flag | `DIRTY_MEMORY` |
| 6 | Missing critical snapshot fields | `DIRTY_MEMORY`, `REJECT_MISSING_CRITICAL_FIELDS` |
| 7 | `FLOW_WASH_LIKE` | `DO_NOT_TRAIN` gate → `DIRTY_MEMORY`, `REJECT_DIRTY_FLOW_CONTEXT` |
| 8 | Contradictory flow evidence (counts vs volume disagree) | `IMBALANCE_NOISY`; not accumulation |
| 9 | Unavailable wallet/split-volume fields | never invented, never defaulted to `0` |
| 9 | Observed `(0,0)` vs unknown | `BALANCED` vs `IMBALANCE_UNKNOWN` — distinct |
| 10 | Clean memory unlocks nothing | training-eligibility only; dirty/audit-only cannot train |

Flow direction/pressure/imbalance are all proven derivable from persisted count
facts alone, with no split volume and no wallet data.

## Verification performed

| Check | Result |
| --- | --- |
| New V2-9.4.7 fixtures | 13 passed, 12 subtests |
| Changed trading-flow + shared-context contracts (phase11, V2-4.1, V2-9.4.5, V2-9.4.6) | 58 passed, 15 subtests |
| Nearest memory-quality, chart, E2Q, Lane Q, Lane K/E2Z, E2Z clean-memory | 415 passed |
| Python compilation | `COMPILE_OK` |
| Persistent DB hash unchanged | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |
| `git diff --check` | clean |
| Migration added | none — zero files under `migrations/` |
| Temporary isolated fixtures only; no live sources; no full repository suite | confirmed |

---

# PHASE D — CLOSEOUT

## Verdict

`V2_9_4_7_FLOW_MEMORY_CONTRACT_PASS`

The contract is designed, recorded, and proven. The live path already satisfied
it; the two drifted helpers that contradicted it are aligned; fixtures now pin
every clause so it cannot silently regress.

## Money-usefulness contribution

The practical result is a correction to the roadmap, not a new capability.
Partial trading flow was recorded — by me, in two prior closeouts — as the most
likely blocker for a 4h clean memory and therefore for Attempt 7. **It is not a
blocker and never was.** Acting on that false claim would have meant hunting a
wallet-data provider (a paid-API or new-dependency risk) to solve a problem that
does not exist.

The durable contribution is the contract itself: Printer can now build clean
memory from the fields DexScreener actually supplies, and that position is
written down, evidence-backed, and fixture-pinned, so nobody re-derives the same
false conclusion. No clean memory is created by this lane.

## What improves

- The codebase encodes **one** flow contract instead of two contradictory ones.
- `trading_flow_context_can_support_clean_memory` can now return `True` — before,
  it was a public predicate that no live payload could ever satisfy.
- `find_trading_flow_snapshot_before` / `find_nearest_trading_flow_snapshot` can
  now return a real snapshot instead of structurally always `None`.
- The mandatory/optional boundary is written down and testable, so "which fields
  do we actually need?" has an evidence-backed answer.
- A false roadmap blocker is retired, on the record.

## What remains locked

Retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper trade audits, PnL, live execution, wallets, private keys, paid APIs,
scoring, ranking, confidence, weighted logic, embeddings, vectors, `WINDOW_12H`
and `WINDOW_24H` remain locked. `WINDOW_5M_MICRO_EVENT` stays support-only. No
memory growth, no V2-10.

## Proof still required

Nothing in this lane is proven end-to-end against live data. Fixtures prove the
contract under controlled conditions only. A real bounded 4h run remains the only
way to prove the full path, and it requires separate operator approval.

## 15m close ordering remains unresolved

**Explicit statement:** the 15m close-ordering defect identified in V2-9.4.6 is
**not** addressed here and remains open. `_execute_close` resolves shared context
at `one_command_15m_factory.py:1198`, while the close step's `snapshot_id` is not
written to the run ledger until line 2712. The 15m path therefore still cannot
take the ledger-exact identity protection the 4h path has. This lane did not
touch it.

## Attempt 7 remains blocked

**Explicit statement:** Attempt 7 is **not** authorised or unblocked by this
lane. It requires separate, explicit operator approval. This lane ran no live
sources, launched no proof, and changed no launcher or supervision code.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Wash-trading detection is currently blind, and this lane does not fix it.**
   `FLOW_WASH_LIKE` requires `unique_wallets_*`/`repeat_wallets_*`, which **no
   adapter supplies**. In production `classify_wallet_participation` therefore
   always returns `WALLETS_UNKNOWN`, and `FLOW_WASH_LIKE` can never fire from
   live data. The authenticity gate is real, correct, and fixture-proven — but it
   has no data to act on. This is the most consequential finding in this lane:
   accepting partial flow as clean-capable is correct per the specification, yet
   it means clean memory is currently created **without any wallet-level
   authenticity check having been possible**. That trade-off is now explicit
   rather than hidden. Closing it needs a provider that supplies wallet
   participation, which is `UNKNOWN_REQUIRES_RESEARCH` and out of scope here.
2. **Two prior closeouts contain a false claim.** V2-9.4.5 (risk 4) and V2-9.4.6
   (risk 2) both assert partial flow gates clean promotion. It does not. Those
   documents are left unedited — historic records are not rewritten — so a reader
   of either will be misled unless they reach this one. This document supersedes
   both on that point.
3. **`required_for_clean` still names fields no provider supplies**, so
   `TRADING_FLOW_CONTEXT_CLEAN` stays unreachable in production and every real
   window will read `PARTIAL`. That is truthful, but it means the `CLEAN` flow
   label is currently decorative and its absence carries no information.
4. **The changed helpers are unused, so the fixtures prove the contract, not the
   integration.** If a future lane wires them in, their interaction with the
   resolver needs its own proof.
5. **`IMBALANCE_NOISY` (contradictory evidence) does not itself block clean
   memory.** It changes direction away from accumulation but produces no
   rejection reason. Whether contradiction alone should downgrade is a genuine
   open question this lane did not decide; the existing contract stands.
6. **The 4h blocker is now unidentified.** Removing flow as the suspect means
   there is no known remaining reason a boundary-correct 4h window would fail —
   which means the next failure will be discovered empirically, in an attempt,
   rather than predicted.

## Files changed

- `src/printer_v1/trading_flow/classifier.py`
- `src/printer_v1/trading_flow/lookup.py`
- `tests/test_v2_9_4_7_trading_flow_memory_contract.py` (new)
- `docs/printer-v1-v2-9-4-7-trading-flow-memory-contract-and-closeout.md` (this file)

## Next recommended phase

Given risk 1, the highest-value next lane is a decision on wallet-level
authenticity: either accept that clean memory is built without a wash check and
record that explicitly in the spec, or research whether a keyless, free,
permitted source can supply wallet participation
(`UNKNOWN_REQUIRES_RESEARCH`). Second: the 15m close-ordering repair. Both need
separate operator approval, as do Attempt 7, V2-10, memory growth, retrieval, and
any financial unlock. **Not started here.**
