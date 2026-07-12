# Printer V1 — Staged/Native 15m Evidence Source-Stack Slice

**Status:** DOCUMENTATION, REPOSITORY AUDIT, AND DESIGN ONLY.
No production implementation, migrations, DB mutation, live source calls,
discovery runs, memory generation, retrieval, or paper decisions.

---

## 1. Purpose

This document defines the official-source-backed contract distinguishing how
`price_change_15m`, `volume_15m`, and `txns_15m` are (or are not) populated
in Printer V1 snapshot rows.

The three evidence kinds are:

| Kind | Meaning |
|---|---|
| `NATIVE_15M` | Source API directly provides a rolling 15-minute window measurement; value comes from upstream, not from Printer derivation |
| `DERIVED_STAGED_SNAPSHOT` | Price-change percentage computed from two confirmed-clean snapshots captured 720–1080 seconds apart; `volume_15m` and `txns_15m` not derivable by this method |
| `NULL` | Field is null; no native source provides it and staged derivation either did not apply, was not attempted, or found no eligible pair |

---

## 2. Lane Boundaries

**In scope:**
- Audit of all active source adapters for native 15m field availability
- Classification of each 15m field as NATIVE / DERIVED / NULL
- Definition of the annotation contract (`price_change_15m_source_kind`)
- Stale-note correction in `solana-mint-addresses.md`
- Creation of this design document

**Out of scope (permanently or deferred):**
- Implementing a native 15m source adapter
- Implementing 15m volume/txns derivation
- Modifying E2Q gate to accept DERIVED_STAGED_SNAPSHOT as clean
- Live source calls, DB mutations, memory generation, retrieval
- Paper decisions, positions, trades, audits, PnL
- BUY/SELL/HOLD; A3; V2-3; T3; scored/ranked/confidence-weighted logic
- SB-3 or broader source-stack adoption lanes

---

## 3. Fields at Stake

All three fields map to DB columns in `printer_token_snapshots` and appear in
`normalized_snapshot_payload_json`.

| Field | DB column | Snapshot role | Evidence window |
|---|---|---|---|
| `price_change_15m` | `price_change_15m` REAL | Percentage price change over ~15 minutes | Rolling 15m from source OR staged from two snapshots |
| `volume_15m` | `volume_15m` REAL | USD trading volume in the last 15 minutes | Rolling 15m from source only |
| `txns_15m` | `txns_15m` INTEGER | Transaction count in the last 15 minutes | Rolling 15m from source only |

---

## 4. Source-by-Source 15m Field Audit

### 4.1 DexScreener (primary pair-snapshot source)

**Adapter:** `src/printer_v1/sources/dexscreener.py`
**Normalization:** `normalize_dexscreener_fixture_result` (lines 203–301)

DexScreener public API exposes `priceChange`, `volume`, and `txns` objects.
Available sub-keys verified from adapter normalization code:

| Field | API sub-key | Extracted |
|---|---|---|
| `price_change_5m` | `priceChange.m5` | Yes |
| `price_change_15m` | `priceChange.m15` | **Not present in DexScreener API** |
| `price_change_1h` | `priceChange.h1` | Yes |
| `price_change_24h` | `priceChange.h24` | Yes |
| `volume_5m` | `volume.m5` | Yes |
| `volume_15m` | `volume.m15` | **Not present in DexScreener API** |
| `volume_1h` | `volume.h1` | Yes |
| `volume_24h` | `volume.h24` | Yes |
| `txns_5m` | `txns.m5` | Yes |
| `txns_15m` | `txns.m15` | **Not present in DexScreener API** |
| `txns_1h` | `txns.h1` | Yes |
| `txns_24h` | `txns.h24` | Yes |

**Conclusion:** DexScreener provides NO native 15m window data for any of the
three fields. The adapter is confirmed correct: it extracts only the sub-keys
the upstream API actually returns.

**Authority note:** DexScreener's public API documentation does not publish an
`m15` sub-key for `priceChange`, `volume`, or `txns`. This is A6 evidence
(Printer implementation evidence). A4 documentation verification is required
before any claim that DexScreener will never add m15 fields — that verification
is deferred to a future SB provider-API contract lane.

### 4.2 GeckoTerminal (backup/OHLC source)

**Adapter:** `src/printer_v1/sources/geckoterminal.py`
**Grep result:** zero matches for `m15`, `volume_15m`, `txns_15m`, or
`price_change_15m` in the GeckoTerminal adapter.

GeckoTerminal's OHLCV API offers per-candle data at multiple resolutions
(including 15-minute candlesticks via `/networks/{network}/pools/{address}/ohlcv/{timeframe}`
with `timeframe=minute&aggregate=15`). However, the current GeckoTerminal
adapter does **not** implement OHLCV extraction. It is used only for
pool-list discovery and is classified as a backup source.

**Conclusion:** GeckoTerminal currently provides NO native 15m data through
the Printer adapter. Native 15m OHLCV integration from GeckoTerminal is a
future implementation path, not a current capability.

**Authority note:** GeckoTerminal OHLCV endpoint is documented on GeckoTerminal's
developer portal. Verification against A4 authority is required before any
implementation. This is deferred to a future SB GeckoTerminal provider-API
contract lane.

### 4.3 PumpPortal (launch stream source)

**Adapter:** `src/printer_v1/sources/pumpportal.py`
**Grep result:** zero matches for `volume_15m`, `txns_15m`, or `price_change_15m`.

PumpPortal provides a WebSocket launch-event stream. It emits token-launch
events, not rolling market-window measurements. It carries no 15m price,
volume, or transaction data.

**Conclusion:** PumpPortal cannot provide any native 15m window evidence and
was never a candidate for this role.

### 4.4 Other sources (coingecko, defillama, solana_rpc, jupiter_quote, pumpswap, goplus, alternative_me)

None of these sources provide rolling 15m market data for memecoin pair
snapshots. They are not in the 15m evidence path and are not audited here.

---

## 5. Current Pipeline State

### 5.1 price_change_15m

**How it gets populated today:**

1. A snapshot is inserted for `(token_id, pair_id, source_name)` with
   `source_status = COMPLETE` and `data_quality_label = CLEAN_DATA`.
2. `apply_staged_derivation` is called as a post-insert hook
   (`src/printer_v1/snapshots/staged_derivation.py` line 191).
3. It queries `printer_token_snapshots` for a CLEAN_DATA COMPLETE snapshot
   from the same `(token_id, pair_id, source_name)` captured 720–1080 seconds
   before the new snapshot's `captured_at`.
4. If a candidate is found, `derive_price_change_15m` computes
   `((end_price - start_price) / start_price) * 100`, rounded to 6 decimal places.
5. The end snapshot row is updated:
   - `price_change_15m` column set to the derived value
   - `normalized_snapshot_payload_json` annotated with
     `"price_change_15m_source_kind": "DERIVED_STAGED_SNAPSHOT"` and a 17-field
     provenance dict
6. If no eligible candidate exists, `price_change_15m` remains NULL.
7. If the existing `normalized_snapshot_payload_json` already carries
   `"price_change_15m_source_kind": "NATIVE_SOURCE"`, the staged derivation
   is skipped (guard at `staged_derivation.py` line 247).

**Classification:**
- When populated: `DERIVED_STAGED_SNAPSHOT`
- When not populated: `NULL` (first snapshot of a pair, or derivation tolerance miss)
- When a native source is later wired: `NATIVE_SOURCE` (guard exists, path not yet active)

**What staged derivation does NOT compute:**
- It does not fill `volume_15m` (intentional; confirmed by tests
  `test_volume_15m_remains_none_after_derivation` and
  `test_volume_15m_not_set_by_derivation`)
- It does not fill `txns_15m` (same intent; confirmed by analogous tests)

### 5.2 volume_15m

**Current state:** Always NULL.

No active source adapter extracts a `volume.m15` or `volume_15m` field. The
`normalize_candidate` function in `parser.py` (line 249) looks for
`("volume", "m15")` and `("volume_15m",)` in candidate payloads, but no
current source supplies these keys.

`normalize_snapshot_payload` in `quality.py` (line 152) includes `volume_15m`
in the numeric-normalisation pass, but will always receive `None`.

`classify_snapshot_quality` (quality.py line 101–106) treats `volume_15m` as
a non-critical field: its absence produces `PARTIAL_SNAPSHOT`, not
`MISSING_CRITICAL_FIELDS`. This is why all 154 live WINDOW_15M rows in the
current-state audit have `PARTIAL_SNAPSHOT` snapshots.

Staged derivation cannot fill `volume_15m`: staged derivation computes a
price percentage from two snapshots, not an aggregate of trading volume.
There is no arithmetic path from snapshot price data to a 15m volume sum.

### 5.3 txns_15m

**Current state:** Always NULL.

Same reasoning as `volume_15m`. `parser.py` line 252 looks for `("txns", "m15")`
and `("txns_15m",)` but no current source supplies these. Treated as non-critical
in `quality.py`. Cannot be derived by staged derivation.

---

## 6. Evidence Classification Contract

This is the official contract for Printer V1 15m evidence. Any future
implementation lane must conform to these definitions.

### 6.1 NATIVE_15M

A 15m field value is **NATIVE** if and only if:

- A governed source adapter calls a provider endpoint that returns a rolling
  15-minute window measurement as a first-class field in the response
- The adapter extracts the field directly without arithmetic combination of
  other response fields
- The snapshot row carries `"price_change_15m_source_kind": "NATIVE_SOURCE"`
  in `normalized_snapshot_payload_json` (for price change) or the equivalent
  provenance annotation for volume/txns

No current source adapter produces NATIVE 15m evidence.

### 6.2 DERIVED_STAGED_SNAPSHOT

A `price_change_15m` value is **DERIVED_STAGED_SNAPSHOT** if and only if:

- `staged_derivation.py:apply_staged_derivation` successfully paired the
  snapshot with an eligible start snapshot
- Both snapshots: same `token_id`, same `pair_id`, same `source_name`;
  both `source_status = COMPLETE`, both `data_quality_label = CLEAN_DATA`;
  both `snapshot_quality_label` not in `{DIRTY_SNAPSHOT, STALE_SNAPSHOT,
  MISSING_CRITICAL_FIELDS, CONFLICTING_SNAPSHOT}`
- Interval between start and end `captured_at` is 720–1080 seconds inclusive
- The snapshot row carries
  `"price_change_15m_source_kind": "DERIVED_STAGED_SNAPSHOT"` and a 17-field
  `"price_change_15m_provenance"` dict in `normalized_snapshot_payload_json`

`volume_15m` and `txns_15m` cannot be DERIVED_STAGED_SNAPSHOT; they are either
NATIVE or NULL.

### 6.3 NULL

A 15m field is **NULL** if:

- For `price_change_15m`: no NATIVE source provided the value and staged
  derivation found no eligible snapshot pair (or was not attempted because
  `NATIVE_SOURCE` annotation was present and no override occurred)
- For `volume_15m` and `txns_15m`: no NATIVE source has been wired for this
  field (current state; always NULL)

NULL is not a failure state when no native source is active and no eligible
staged pair exists. It means evidence is not available.

### 6.4 Annotation vocabulary (normalized_snapshot_payload_json)

| Annotation key | Value | Meaning |
|---|---|---|
| `price_change_15m_source_kind` | `"NATIVE_SOURCE"` | Value came directly from provider API; staged derivation must not overwrite |
| `price_change_15m_source_kind` | `"DERIVED_STAGED_SNAPSHOT"` | Value computed by staged derivation; provenance dict also present |
| `price_change_15m_source_kind` | absent | No derivation was applied; field may be null |
| `price_change_15m_provenance` | 17-field dict | Present only when `source_kind = DERIVED_STAGED_SNAPSHOT` |

No equivalent annotation exists yet for `volume_15m` or `txns_15m` because
those fields have never been populated. When a native source is wired for them,
`volume_15m_source_kind` and `txns_15m_source_kind` should follow the same
pattern.

---

## 7. Why volume_15m and txns_15m Cannot Be Staged

Staged snapshot derivation computes a price percentage:
`((end_price - start_price) / start_price) * 100`

This works because `price_usd` is a point-in-time observation — the current
price at the moment the snapshot was captured. The difference between two
point-in-time prices is a valid proxy for price change.

Volume and transaction count are **cumulative rolling window totals** reported
by the source for the preceding 15 minutes. They are not point-in-time
measurements. Subtracting two rolling 15m totals captured 15 minutes apart
would produce the volume accumulated in an approximate 15m window only if the
source's rolling window and the capture interval aligned exactly — and the
source's rolling window resets independently of capture timing. This approach
is not a valid derivation and must not be implemented.

**Conclusion:** `volume_15m` and `txns_15m` require a native source that
reports a true 15m rolling window. They cannot be inferred from staged
snapshot comparisons.

---

## 8. Clean-Memory Gate Implications

The current memory pipeline has the following dependency on 15m evidence:

| Gate | 15m evidence requirement | Current state |
|---|---|---|
| `classify_snapshot_quality` (quality.py) | `volume_15m` and `txns_15m` non-null for `CLEAN_SNAPSHOT`; their absence yields `PARTIAL_SNAPSHOT` | All live snapshots are `PARTIAL_SNAPSHOT` |
| E2Q (`e2q_memory_window_audit.py`) | Audits `WINDOW_15M` only; accepts `PARTIAL_SNAPSHOT` quality label | 1H windows blocked (X14) |
| `derive_price_change_15m` / `apply_staged_derivation` | Requires two CLEAN_DATA COMPLETE snapshots 720–1080s apart | Works for price_change_15m; volume/txns remain null |

The current clean-memory path accepts `PARTIAL_SNAPSHOT` for `WINDOW_15M`
windows (E2Q accepts it). `price_change_15m` may be DERIVED_STAGED_SNAPSHOT
or NULL depending on snapshot history. `volume_15m` and `txns_15m` are always
NULL.

No gate currently blocks a WINDOW_15M from becoming `E2Q_AUDIT_CLEAN_CANDIDATE`
solely due to null `volume_15m` or `txns_15m`. That constraint may be
introduced in a future gate lane.

---

## 9. NATIVE_SOURCE Guard Design

`staged_derivation.py` line 247 contains:
```python
if merged.get("price_change_15m_source_kind") == "NATIVE_SOURCE":
    return False
```

This guard prevents staged derivation from overwriting a native-source value.
**No current code path writes `"price_change_15m_source_kind": "NATIVE_SOURCE"`.**
The guard is forward-looking design. When a native 15m adapter is implemented,
it must:

1. Set `"price_change_15m_source_kind": "NATIVE_SOURCE"` in
   `normalized_snapshot_payload_json` before or during the snapshot insert
2. Set `price_change_15m` in the snapshot payload to the provider-supplied value
3. The existing guard will then prevent staged derivation from overwriting it

Volume and txns do not yet have equivalent guards. These must be added alongside
the native implementation.

---

## 10. Blocker Inventory

| Blocker | Severity | Owner lane |
|---|---|---|
| No source provides native `volume_15m` or `txns_15m` | HIGH — these fields always null; `CLEAN_SNAPSHOT` unreachable | Future native 15m implementation lane |
| No source provides native `price_change_15m` | MEDIUM — staged derivation fills it when eligible | Future native 15m implementation lane |
| E2Q gate hardcoded to `WINDOW_15M` only | HIGH — blocks 1H window graduation (X14 blocker) | Separate E2Q gate fix lane |
| `PARTIAL_SNAPSHOT` is the best achievable label today | Structural — no path to `CLEAN_SNAPSHOT` without native source | Future native 15m implementation lane |
| DexScreener provides no `m15` sub-keys | Confirmed by A6 audit; A4 verification deferred | Future SB DexScreener provider-API contract lane |
| GeckoTerminal OHLCV 15m capability not integrated | GeckoTerminal OHLCV is a candidate native source; not yet implemented | Future native 15m implementation lane |

---

## 11. Audit Evidence Files

Files read and classified during this audit:

| File | Role in audit |
|---|---|
| `src/printer_v1/sources/dexscreener.py` | Confirmed no `m15` fields extracted; native 15m absent |
| `src/printer_v1/sources/geckoterminal.py` | Confirmed no `m15` fields extracted; adapter does not use OHLCV endpoint |
| `src/printer_v1/sources/pumpportal.py` | Confirmed no market-window data |
| `src/printer_v1/snapshots/staged_derivation.py` | Defines DERIVED_STAGED_SNAPSHOT path for price_change_15m only |
| `src/printer_v1/snapshots/quality.py` | Confirms volume_15m and txns_15m are non-critical; absence → PARTIAL_SNAPSHOT |
| `src/printer_v1/discovery/parser.py` | Shows lookup keys for m15 fields; confirms no source supplies them |
| `src/printer_v1/operator_cli/e2q_memory_window_audit.py` | Confirms E2Q hardcoded to WINDOW_15M; X14 blocker documented |
| `src/printer_v1/memory/windowing.py` | Confirms WINDOW_15M = 900s; no 15m-specific evidence tracking |
| `tests/test_v2_2z1_staged_15m_price_derivation.py` | Confirms: volume_15m and txns_15m remain null after derivation; NATIVE_SOURCE guard prevents overwrite |

---

## 12. What Remains Locked

- Production implementation of native 15m adapter: NO
- Migrations or DB schema changes: NO
- Live source calls: NO
- Discovery runs or memory generation: NO
- Retrieval activation: NO
- Paper decisions, positions, PnL: NO
- BUY/SELL/HOLD: NO
- A3: LOCKED
- V2-3: PAUSED
- T3 live proof: PAUSED (V2-2AL.4C prerequisite not yet complete)
- E2Q gate fix (hardcoded WINDOW_15M → accept WINDOW_1H): NOT IN THIS LANE
- SB-3 protocol source-stack modules: NOT STARTED

---

## Verdict

```
LANE: Staged/Native 15m Evidence Source-Stack Slice
EXECUTOR: Claude Sonnet 4.6
DATE: 2026-07-12
ANCHOR_COMMIT: 3259544 (Repair Solana USDC infrastructure mint filter)
VERDICT: STAGED_NATIVE_15M_SOURCE_SLICE_READY
FILES_CHANGED: 2 (solana-mint-addresses.md stale-note correction, this doc)
AGENTS_MD_CHANGED: NO
PRODUCTION_CODE_CHANGED: NO
TESTS_CHANGED: NO
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
MEMORY_GENERATION: NONE
RETRIEVAL: LOCKED
PAPER_DECISIONS: LOCKED
T3_STATUS: UNCHANGED — V2-2AL.4C still required before V2-2AL.5
A3_STATUS: LOCKED
V2_3_STATUS: PAUSED
NATIVE_15M_STATUS: NOT IMPLEMENTED — design contract only
E2Q_1H_BLOCKER: OPEN — separate lane required to fix hardcoded WINDOW_15M gate
NEXT_LANE: Staged/native 15m evidence implementation and bounded proof
```

---

## Git Checks

To be recorded after `git diff --check`, `git status --short`,
`git diff --stat`, and `git diff --name-only` are run prior to commit.

---

## Commit Record

**Message:** `Define staged and native 15m evidence source contract`

**Files committed:**
1. `docs/printer-v1-staged-native-15m-source-stack-slice.md` (new)
2. `docs/solana-builder-source-of-truth/solana-mint-addresses.md` (stale-note correction)

---

## Next Lane

`Staged/native 15m evidence implementation and bounded proof`

Do not begin it.

---

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Initial authoring: full source audit, evidence classification contract, blocker inventory, verdict | Claude Sonnet 4.6 / staged-native-15m-slice |
