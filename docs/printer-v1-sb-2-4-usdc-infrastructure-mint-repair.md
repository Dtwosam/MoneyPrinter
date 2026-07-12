# SB-2.4 USDC Infrastructure Mint Repair

**Status:** PRODUCTION REPAIR AND PROOF LANE

---

## Design and Readiness Section

### Lane Goal

Replace the incorrect Solana USDC infrastructure-mint constant in the GeckoTerminal
discovery adapter and its targeted test with the official Circle Solana USDC address.
No legacy alias is retained. Prove the official USDC address is excluded as a
discovery candidate.

### Official USDC Address (A4: Circle Inc.)

| Item | Value | Authority |
|---|---|---|
| Correct Solana USDC mint | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` | A4: Circle Inc., `https://developers.circle.com/stablecoins/usdc-contract-addresses.md`, verified 2026-07-12 |
| Incorrect Printer constant | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej` | Printer implementation before SB-2.4 |

The gap was first identified in SB-2.2 and independently confirmed in SB-2.3.
No production repair was made in those lanes. SB-2.4 is the production repair lane.

### Pre-Repair Occurrence Map

| Address | File | Line | Classification |
|---|---|---|---|
| `EPjF...CH8Ej` (incorrect) | `src/printer_v1/sources/geckoterminal.py` | 51 | Production code: `_SOLANA_NATIVE_QUOTE_MINTS` filter |
| `EPjF...CH8Ej` (incorrect) | `tests/test_post_rc_geckoterminal_discovery_adapter.py` | 435 | Test: class-level USDC constant for leak-prevention tests |
| `EPjF...CH8Ej` (incorrect) | `docs/solana-builder-source-of-truth/solana-mint-addresses.md` | 35 | Documentation note recording implementation gap (not repaired in SB-2.4; stale after this repair — requires documentation cleanup) |
| `EPjF...CH8Ej` (incorrect) | `docs/printer-v1-sb-0-...` | 146, 411 | Historical inventory documentation only; not changed |
| `EPjF...CH8Ej` (incorrect) | `docs/printer-v1-sb-2-2-...` | 43, 194 | Audit report; records gap — not changed |
| `EPjF...CH8Ej` (incorrect) | `docs/printer-v1-sb-2-solana-core-source-stack-authoring-report.md` | 190, 410 | Report; records gap — not changed |
| `EPjF...TDt1v` (official) | `docs/solana-builder-source-of-truth/solana-mint-addresses.md` | 126 | Source-stack module authority table — already correct |
| `EPjF...TDt1v` (official) | `docs/printer-v1-sb-2-2-...`, `docs/printer-v1-sb-2-...` | multiple | Documentation records — already correct |
| `EPjF...TDt1v` (official) | Production code, tests | — | Absent before SB-2.4; this lane adds it |

### Allowed Files

1. `src/printer_v1/sources/geckoterminal.py`
2. `tests/test_post_rc_geckoterminal_discovery_adapter.py`
3. `docs/printer-v1-sb-2-4-usdc-infrastructure-mint-repair.md` (this document)

### Readiness Requirements

- [x] Official Circle Solana USDC address verified by A4 authority (SB-2.2, SB-2.3)
- [x] Incorrect constant location confirmed: `geckoterminal.py:51`
- [x] Test file location confirmed: `tests/test_post_rc_geckoterminal_discovery_adapter.py:435`
- [x] No legacy alias to retain (task instruction explicit)
- [x] WSOL, USDt, control flow, selection logic, Source Governor, and scheduler behavior: unchanged
- [x] Target test identified: `tests/test_post_rc_geckoterminal_discovery_adapter.py`
- [x] V1 locks: no live calls, no DB mutation, no memory generation, no retrieval, no paper decisions, no positions, no PnL, no T3, no A3, no staged/native 15m, no V2-3, no source-stack adoption

### Implementation Plan

1. Replace `"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej"` with
   `"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"` in `geckoterminal.py` line 51.
   Update inline comment from `# USDC` to `# USDC (Circle official Solana mainnet)`.
2. Replace `USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej"` with
   `USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"` in test file line 435.
3. Run `python -m pytest tests/test_post_rc_geckoterminal_discovery_adapter.py -q`.
4. Record proof results below.

### Stop Conditions

- Any file outside the three allowed files changes: STOP.
- Test failure that is not caused by a stale test using the old address: STOP, investigate.
- Any unlock of V1 restrictions required to complete repair: STOP, report.

---

## Proof Results

**Command:** `python -m pytest tests/test_post_rc_geckoterminal_discovery_adapter.py -q`

**Result:** 44 passed, 1 failed (pre-existing failure unrelated to USDC change)

**Pre-existing failure (confirmed pre-existing by stash verification):**
```
FAILED GeckoTerminalCLIDiscoveryTests::test_non_solana_pool_rejected_as_non_solana_candidate
AssertionError: 'NOT_EXECUTED' != 'FAILED'
```
This failure is about non-Solana pool rejection behavior at the CLI layer.
It was failing identically before any SB-2.4 changes (confirmed by `git stash`,
running the single test, then `git stash pop`). The USDC address change did not
introduce this failure.

**USDC/WSOL/USDt leak-prevention tests: ALL PASSED**

The following targeted tests all passed:
- `test_wsol_as_base_token_is_skipped_not_discovered` — PASSED
- `test_usdc_as_base_token_is_skipped` — PASSED (official USDC now excluded)
- `test_usdt_as_base_token_is_skipped` — PASSED
- `test_memecoin_with_wsol_as_quote_still_discovered` — PASSED
- `test_real_trending_pool_wsol_base_shape_is_skipped` — PASSED

---

## Implementation Record

### Changes Applied

**`src/printer_v1/sources/geckoterminal.py` line 51:**
- Before: `"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej",  # USDC`
- After: `"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Circle official Solana mainnet)`

**`tests/test_post_rc_geckoterminal_discovery_adapter.py` line 435:**
- Before: `USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej"`
- After: `USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"`

No other files changed.

### Post-Repair Occurrence Map

| Address | File | Line | Classification |
|---|---|---|---|
| `EPjF...CH8Ej` (incorrect) | Production code | — | ABSENT after repair |
| `EPjF...CH8Ej` (incorrect) | Tests | — | ABSENT after repair |
| `EPjF...TDt1v` (official) | `src/printer_v1/sources/geckoterminal.py` | 51 | Production code: `_SOLANA_NATIVE_QUOTE_MINTS` filter — CORRECT |
| `EPjF...TDt1v` (official) | `tests/test_post_rc_geckoterminal_discovery_adapter.py` | 435 | Test: class-level USDC constant — CORRECT |

---

## Test Results

**Command run:**
```
python -m pytest tests/test_post_rc_geckoterminal_discovery_adapter.py -q
```

**Result:** 44 passed, 1 failed (pre-existing failure; see Proof Results section above).

All USDC/WSOL/USDt leak-prevention tests passed. The official Circle Solana USDC
address `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` is correctly excluded as
a base_token by `_SOLANA_NATIVE_QUOTE_MINTS` in `geckoterminal.py`.

---

## Risks

| Risk | Severity | Status |
|---|---|---|
| `solana-mint-addresses.md` line 35 still says "Printer's current implementation still uses `EPjF...CH8Ej`" | Low | Documentation stale after this repair. The source-stack module authority table at line 126 already uses the correct address. The stale note at line 35 requires a documentation-only cleanup in a later SB lane (not a code risk). |
| Historical docs (SB-0, SB-2 report, SB-2.2 report) still contain the old address | Informational | These are audit records; they correctly document the historical state. No change needed. |
| Circle or Tether changes their official Solana mint in the future | Low | Risk-based freshness policy from SB-1/SB-2 applies. Infrastructure mints should be re-verified within 30 days before any live quote or routing use. |

---

## What Remains Locked

- Source-stack adoption: NO
- Live RPC calls: NO
- DB mutation: NO
- Discovery runs: NO
- Memory generation: NO
- Retrieval: NO
- Paper decisions: NO
- BUY, SELL, HOLD: NO
- Positions, trades, audits, PnL: NO
- T3 live proof: NO (V2-2AL.4C DB persistence repair still required before V2-2AL.5)
- A3: LOCKED
- Staged/native 15m blocker: PARTIAL — DEFERRED, NOT RESOLVED
- V2-3: PAUSED
- SB-3 (protocol modules): NOT STARTED

---

## Verdict

```
LANE: SB-2.4 — USDC Infrastructure Mint Repair
EXECUTOR: Claude Sonnet 4.6
DATE: 2026-07-12
ANCHOR_COMMIT: fd19015 (Verify SB-2.2 core Solana authority corrections)
VERDICT: USDC_INFRASTRUCTURE_MINT_REPAIR_PASS
FILES_CHANGED: 3 (geckoterminal.py, targeted test, SB-2.4 doc)
AGENTS_MD_CHANGED: NO
PRODUCTION_CODE_CHANGED: YES (address constant only; no logic change)
TESTS_CHANGED: YES (test constant updated to match production)
LIVE_RPC_CALLS: NONE
DB_MUTATION: NONE
MEMORY_GENERATION: NONE
RETRIEVAL: LOCKED
PAPER_DECISIONS: LOCKED
T3_STATUS: UNCHANGED — V2-2AL.4C still required before V2-2AL.5
A3_STATUS: LOCKED
STAGED_NATIVE_15M_BLOCKER: PARTIAL — DEFERRED, NOT RESOLVED
V2_3_STATUS: PAUSED
PRE_EXISTING_FAILURE: test_non_solana_pool_rejected_as_non_solana_candidate (NOT introduced by this lane)
NEXT_LANE: Source-stack slice for staged/native 15m evidence (DO NOT BEGIN)
```

---

## Git Checks

```
git diff --check          : NO WHITESPACE ERRORS (LF/CRLF conversion warnings only)
git status --short        : M  src/printer_v1/sources/geckoterminal.py
                            M  tests/test_post_rc_geckoterminal_discovery_adapter.py
                            ?? docs/printer-v1-sb-2-4-usdc-infrastructure-mint-repair.md
                            (plus untracked non-committed artifacts — not staged)
git diff --cached --stat  : 3 files changed, 195 insertions(+), 2 deletions(-)
git diff --cached --name-only:
  docs/printer-v1-sb-2-4-usdc-infrastructure-mint-repair.md
  src/printer_v1/sources/geckoterminal.py
  tests/test_post_rc_geckoterminal_discovery_adapter.py
```

---

## Commit

**Message:** `Repair Solana USDC infrastructure mint filter`

**Files committed:**
1. `src/printer_v1/sources/geckoterminal.py`
2. `tests/test_post_rc_geckoterminal_discovery_adapter.py`
3. `docs/printer-v1-sb-2-4-usdc-infrastructure-mint-repair.md`

---

## Remaining Blockers

| Blocker | Owner lane |
|---|---|
| `solana-mint-addresses.md` stale note at line 35 | Documentation cleanup in future SB lane |
| V2-2AL.4C: DB persistence repair for T3 failure provenance | V2-2AL.4C |
| V2-2AL.5: Bounded live T3 proof (approved mint: `6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`) | V2-2AL.5 (after V2-2AL.4C) |
| Mainnet RPC endpoint name gap (`api.mainnet.solana.com` vs `api.mainnet-beta.solana.com`) | Verify before V2-2AL.5 |
| SB-6 finality contract | SB-6 |
| SB-3 protocol source-stack modules | SB-3 |

---

## Next Lane

`Source-stack slice for staged/native 15m evidence`

Do not begin it.

---

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | SB-2.4: design/readiness section authored; production repair applied to `geckoterminal.py` and targeted test; test proof recorded; verdict issued | Claude Sonnet 4.6 / SB-2.4 |
