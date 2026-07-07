# Printer V1 Lane X10.7 — Manual Discovery + 15m Memory Growth Proof Report

**Type:** documentation only — no new code, no DB mutation, no automation, no commit.

**Date:** 2026-07-06

**Verdict:**
- `PARTIAL_READY_WITH_TOKEN_LIST_MISMATCH`
- `SAFE_TO_PROCEED_TO_X11_DOC_ONLY`
- `NOT_READY_FOR_AUTOMATED_DISCOVERY_TO_X5_SELECTION`

---

## 1. Purpose

Lane X10.7 is a bounded, fully manual proof that the Printer V1 discovery-to-memory-growth pipeline operates end-to-end without unlocking any financial, retrieval, or automated-selection capability.

It does not claim a full discovery-to-selected-token memory proof. It demonstrates that:

1. Bounded discovery can find and accept a new Solana token via the governed source path.
2. Lane X6 selection repair can classify and queue candidates from the tracking database.
3. Lane X10.6 can produce a structured traceability artifact over those candidates.
4. The Lane X5 five-token WINDOW_15M runner can collect real snapshots, close 15m windows, and grow clean memory against a known good token list.
5. All BUY, SELL, HOLD, paper-decision, position, PnL, and retrieval locks remain unbroken across the full proof sequence.

The proof is partial because the X5 memory growth cycle ran against the pre-existing repaired Lane K token list (BONK, WIF, EAGLE250, WEN, ANSEM) rather than the tokens freshly selected by X6/X10.6 in this proof session. This mismatch is documented in Section 11.

---

## 2. Commands Run

All commands were run manually by the operator. No automation, no Central Scheduler, no Source Governor bypass.

| # | Command | Parameters |
|---|---|---|
| 1 | `printer-db-counts` | `--db-path data/printer_v1.sqlite3 --format json` |
| 2 | DB backup (before discovery) | `Copy-Item` to `data/manual-x10-7-backups/` |
| 3 | `printer-discover-candidates-once` | `--operator-approved --source-name dexscreener --chain solana --max-candidates 3 --db-path data/printer_v1.sqlite3` |
| 4 | `printer-db-counts` | Post-discovery verification |
| 5 | `printer-run-lane-x6-discovery-selection-repair` | `--operator-approved --max-candidates 5 --backup-proof-path <pre-discovery-backup>` |
| 6 | `build_selection_batch()` | Called directly in Python (X10.6 module); `operator_approved=True`, `db_path=data/printer_v1.sqlite3`, `backup_proof_path=<pre-discovery-backup>` |
| 7 | DB backup (before X5 run) | `Copy-Item` to `data/manual-x10-7-backups/` |
| 8 | `printer-run-lane-x5-five-token-cycle` | `--operator-approved --token-list-path operator-runs/x5-token-list-lane-k-repaired-1h-20260705-223349.json --backup-proof-path <pre-x5-backup> --duration 1h --window-kind WINDOW_15M --snapshot-interval-seconds 90 --window-close-interval-seconds 900 --source-budget-max-failures 5 --throttle-backoff-seconds 2 --format json` |
| 9 | `printer-report-e2u-15m-cycle-closeout` | `--operator-approved --db-path data/printer_v1.sqlite3 --format json --no-color` |
| 10 | `printer-run-lane-v-clean-memory-report` | `--db-path data/printer_v1.sqlite3 --window-kind WINDOW_15M --format json --no-color` |
| 11 | `printer-db-counts` | Final post-run counts |

---

## 3. Backup Paths

| Backup | Path | Size |
|---|---|---|
| Before discovery (X10.7 start) | `data/manual-x10-7-backups/printer_v1.before-manual-x10-7-proof.20260706-225124.sqlite3` | 10,641,408 bytes |
| Before X5 run | `data/manual-x10-7-backups/printer_v1.before-x10-7-x5-run.20260706-225624.sqlite3` | 10,657,792 bytes |

Both backups exist on disk. The pre-discovery backup was taken before any DB mutation in this proof session.

---

## 4. Discovery Result

**Command:** `printer-discover-candidates-once --operator-approved --source-name dexscreener --chain solana --max-candidates 3`

| Field | Value |
|---|---|
| Source | DEXSCREENER_SEARCH |
| Chain filter | solana |
| Candidates fetched | 30 |
| Candidates accepted | **1** |
| Candidates rejected | 29 |
| Source failures | **0** |

**Accepted candidate:**

| Field | Value |
|---|---|
| Token mint | `pumpgrWRAztPTe9HpqUUj23hWDcz1qvkbMRiDM6wint` |
| Pair address | `3FdTQD9QYpQaP6X842j48SQrQZc9kJsgdTFtovbnMHWp` |
| Token ID assigned | 14 |
| Discovery candidate ID | 12 |
| Tracking lane | TRACK_FAST |

**Rejection summary for 29 rejected:** non-Solana chain or duplicate pair/token already in DB.

**DB deltas from discovery:**

| Table | Before | After | Delta |
|---|---|---|---|
| `printer_tokens` | 13 | 14 | +1 |
| `printer_pairs` | 14 | 15 | +1 |
| `printer_tracking_queue` | — | 12 | — |

Discovery is locked to source-governed, bounded, operator-approved intake. No automated repeat, no alpha signal, no buy signal was produced.

---

## 5. X6 Result

**Command:** `printer-run-lane-x6-discovery-selection-repair --operator-approved --max-candidates 5`

**Status:** `LANE_X6_COMPLETED`

| Field | Value |
|---|---|
| Candidates evaluated | 5 |
| Candidates selected | 5 |
| Candidates rejected | 0 |

**Selected candidates:**

| Token Mint (prefix) | Pair (prefix) | Lane | Source Channel |
|---|---|---|---|
| `pumpgrWRAzt...` | `3FdTQD9...` | TRACK_FAST | DEXSCREENER_SEARCH |
| `yMJPZbn...` | `7G7hXmR...` | TRACK_FAST | GECKOTERMINAL_TRENDING_POOL |
| `66pQgfL...` (WEN) | `HZyqZR...` | TRACK_FAST | GECKOTERMINAL_TRENDING_POOL |
| `AXLmMWk...` (EAGLE250) | `3Qhv2Z6...` | TRACK_FAST | GECKOTERMINAL_TRENDING_POOL |
| `69FVkZNR...` | `GAitmex...` | TRACK_NORMAL | DEXSCREENER_SEARCH |

4 TRACK_FAST + 1 TRACK_NORMAL selected. X6 does not write a persistent DB record of the selection — it classifies from existing tracking rows. No financial locks were touched.

---

## 6. X10.6 Traceability Result

**Method:** `build_selection_batch()` called directly in Python with `operator_approved=True`.

**Artifact:** `operator-runs/manual-x10-7/x10-6-selection-batch.json`

**Status:** `LANE_X10_6_COMPLETED`

| Field | Value |
|---|---|
| Candidates input | 5 |
| Selected | 5 |
| Rejected | 0 |
| Override required / missing | 0 / 0 |
| Pair drift pending acknowledgment | 0 |
| Event kind (all) | `AMBIGUOUS_MEMORY_CANDIDATE` |
| `is_balanced` | false (informational — all fresh AMBIGUOUS, no price/volume data attached) |
| `automated_selection_locked` | **true** |
| `discovery_is_intake_not_alpha` | **true** |
| `selection_is_memory_value_based_not_buy_probability` | **true** |
| `buy_enabled` | false |
| `paper_decisions_created` | 0 |
| `positions_created` | 0 |

All 5 candidates were classified as `AMBIGUOUS_MEMORY_CANDIDATE` because no price/volume/txn fields were populated in the candidate dicts passed to the classifier. This is expected for fresh queue candidates — the event-kind classifier fires on market data fields that are not present until a snapshot is taken.

`is_balanced=False` is informational only. A batch of all-AMBIGUOUS candidates is valid and proceeds to COMPLETED.

The X10.6 module writes no DB rows. The artifact is a JSON file on disk only.

---

## 7. X5 15m Run Result

**Command:** `printer-run-lane-x5-five-token-cycle --duration 1h --window-kind WINDOW_15M --snapshot-interval-seconds 90 --window-close-interval-seconds 900`

**Token list used:** `operator-runs/x5-token-list-lane-k-repaired-1h-20260705-223349.json`
(BONK, WIF, EAGLE250, WEN, ANSEM — the pre-existing repaired Lane K list)

**Run duration:** approximately 42 minutes of the intended 1h. The process was killed manually by the operator. The last batch of windows had already been closed before the kill — no windows were left open.

| Field | Value |
|---|---|
| Tokens run | BONK (token 7), WIF (token 8), EAGLE250 (token 10), WEN (token 11), ANSEM (token 13) |
| Cadence cycles completed (approx) | ~28 of ~40 (142 snapshots ÷ 5 tokens) |
| New WINDOW_15M opened | 10 (windows 136–145) |
| New WINDOW_15M closed | 10 (all closed before kill) |
| Source requests (delta) | +144 |
| Source responses (delta) | +142 |
| Source failures (delta) | +2 |
| Source failure rate | 1.4% (2 of 144 requests) |
| Forced safe-stop triggered | No |
| Output file | `operator-runs/manual-x10-7/x5-1h-proof-run-output.txt` (empty — PowerShell `Out-File` never flushed before kill; DB is the authoritative record) |

---

## 8. Clean / Dirty / Audit Memory Result

### Clean memories created (this proof session)

| Episode ID | Window ID | Token ID | Pair ID | Memory Status | Created at |
|---|---|---|---|---|---|
| 42 | 136 | 7 (ANSEM) | 16 (new pair) | CLEAN_MEMORY | 2026-07-06 22:12 UTC |
| 43 | 138 | 10 (EAGLE250) | 10 | CLEAN_MEMORY | 2026-07-06 22:12 UTC |
| 44 | 139 | 11 (WEN) | 11 | CLEAN_MEMORY | 2026-07-06 22:12 UTC |
| 45 | 142 | 8 (WIF) | 8 | CLEAN_MEMORY | 2026-07-06 22:30 UTC |
| 46 | 143 | 10 (EAGLE250) | 10 | CLEAN_MEMORY | 2026-07-06 22:30 UTC |
| 47 | 144 | 11 (WEN) | 11 | CLEAN_MEMORY | 2026-07-06 22:30 UTC |
| 48 | 145 | 13 | 14 | CLEAN_MEMORY | 2026-07-06 22:30 UTC |

**Total clean memories added: +7** (18 → 25 cumulative)

### Dirty / partial windows from this run

| Window ID | Pair ID | Token ID | Data Quality | Memory Status | Cause |
|---|---|---|---|---|---|
| 141 | 17 (ANSEM new) | 7 | MISSING_CRITICAL_DATA | DIRTY_MEMORY | ANSEM pair drift — new pair 17 had no usable data |
| 142 | 8 (WIF) | 8 | CLEAN_DATA | PARTIAL_MEMORY | Killed mid-cadence (not dirty; cadence incomplete) |
| 143 | 10 (EAGLE250) | 10 | CLEAN_DATA | PARTIAL_MEMORY | Killed mid-cadence |
| 144 | 11 (WEN) | 11 | CLEAN_DATA | PARTIAL_MEMORY | Killed mid-cadence |

**1 DIRTY_MEMORY window** (pair drift artifact), **3 PARTIAL_MEMORY windows** (clean data, incomplete cadence at kill). No AUDIT_ONLY windows created in this run.

### Cumulative memory state (post-proof)

| Metric | Count |
|---|---|
| Total WINDOW_15M | 145 |
| Closed WINDOW_15M | 125 |
| WINDOW_15M_CLEAN_MEMORY episodes | 25 |
| do_not_train=1 episodes | 0 |
| E2U repeatable_15m_window_proof | true |
| E2U bounded_operator_cycle_ready | true |

---

## 9. Source Failure Result

| Metric | Before proof | After proof | Delta |
|---|---|---|---|
| `printer_source_failures` | 45 | 47 | **+2** |
| `printer_source_requests` | 879 | 1023 | +144 |
| `printer_source_responses` | 834 | 976 | +142 |

Failure rate: 1.4% (2 of 144 requests). Both failures were absorbed by the `--source-budget-max-failures 5` budget. No forced safe-stop was triggered. No failure cascade was observed. Discovery phase had 0 source failures (all 2 occurred during the X5 snapshot collection phase).

---

## 10. ANSEM Pair Drift Finding

ANSEM (token_id=7) now has **3 distinct pair rows** in the DB:

| Pair ID | Pair address | Provenance | Episodes |
|---|---|---|---|
| 7 | `FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC` | Original Lane K proof | 4 clean |
| 16 | (new address) | Created during first X10.7 X5 cycle | 1 clean |
| 17 | (newer address) | Created during second X10.7 X5 cycle | 1 dirty (MISSING_CRITICAL_DATA) |

This confirms the pair drift finding from Lane X10.5. ANSEM migrates pairs and the runner detects a different pair on each run cycle. The X10.6 `pair_drift_acknowledged=True` gate was designed for exactly this situation.

**Implication:** Any future selection batch that includes ANSEM must carry:
- `pair_drift_acknowledged=True`
- `manual_override=True`
- `manual_override_reason` (non-empty string)

Without these fields, X10.6 will reject ANSEM from the batch. This is correct and intentional behavior.

---

## 11. Token-List Mismatch

The X5 memory growth cycle ran against the **pre-existing repaired Lane K token list** (BONK, WIF, EAGLE250, WEN, ANSEM), not the token batch freshly selected by X6 and traced by X10.6 in this proof session.

| X6/X10.6 freshly selected | In X5 list used? | Reached memory factory? |
|---|---|---|
| `pumpgrWRAzt...` (newly discovered) | No | **No** |
| `yMJPZbn...` (GECKOTERMINAL_TRENDING_POOL) | No | **No** |
| `66pQgfL...` = WEN | Yes (as token 11) | Yes |
| `AXLmMWk...` = EAGLE250 | Yes (as token 10) | Yes |
| `69FVkZNR...` (TRACK_NORMAL, ineligible for X5) | No | **No** (ineligible by kind) |

**Reason for the mismatch:** The X5 runner requires exactly 5 TRACK_FAST operator-approved tokens in a JSON file. The X6 batch produced 4 TRACK_FAST + 1 TRACK_NORMAL — not 5 TRACK_FAST. Rather than fail the proof entirely, the operator chose to use the existing proven 5-TRACK_FAST list to demonstrate that memory growth still works after the X10.6 layer was built.

**What this means:** The end-to-end chain "discovery selects token → X6 queues it → X10.6 traces it → X5 grows memory for it" was NOT completed for `pumpgrWRAzt` (the new token). Two of the five X6-selected tokens (WEN and EAGLE250) did run through memory growth because they were already in the X5 list — but not because the operator built a new list from the X6/X10.6 artifact.

**What the next proof must do:** Build an X5 token list explicitly from the X6/X10.6 batch artifact, so the chain is end-to-end for at least one freshly discovered token. This is required before the PARTIAL_READY label can be removed.

---

## 12. Locks Status

All locks held across the full proof sequence (discovery → X6 → X10.6 → X5 → closeout).

| Lock | Status |
|---|---|
| `buy_enabled` | false |
| `sell_enabled` | false |
| `hold_enabled` | false |
| `paper_decisions_created` (delta) | **0** |
| `paper_positions` (delta) | **0** |
| `paper_trade_events` (delta) | **0** |
| `paper_trade_audits` (delta) | **0** |
| `pnl_created` (delta) | **0** |
| `retrieval_activation` | false |
| `memory_retrieval_matches` (delta) | **0** |
| `memory_fingerprints` (delta) | **0** |
| `paid_api_dependency` | false |
| `wallet_private_key` | false |
| `live_execution` | false |
| All 10 E2U hard locks | **true** |
| All 12 Lane V hard locks | **true** |
| All 20 X10.6 hard locks | **true** |

Pre-existing `printer_paper_decisions=2` and `printer_paper_audit_reports=1` rows are from earlier proof runs. Delta is zero for this session.

---

## 13. Risks and Blockers

| Risk | Severity | Status |
|---|---|---|
| **X5 killed mid-run** | Low | All windows closed cleanly before kill. No corrupt state. DB is consistent. |
| **Token list mismatch** | Medium | `pumpgrWRAzt` (fresh discovery) never reached the memory factory. Must be resolved in the next proof before removing PARTIAL_READY. |
| **ANSEM pair drift (3 active pairs)** | Medium | Each X5 run may open ANSEM on a different pair, causing DIRTY or MISSING_CRITICAL_DATA windows. Requires `pair_drift_acknowledged=True` override before any future ANSEM inclusion in a selection batch. |
| **PARTIAL_MEMORY windows (142–144)** | Low | Data is CLEAN_DATA; cadence is incomplete due to kill. Not dirty. Not flagged do_not_train. |
| **running_jobs=1 leftover** | Low | Cosmetic artifact from the killed process. Window data is closed and clean. Should be confirmed resolved before the next E2Z pipeline run. |
| **X5 output file empty** | Informational | PowerShell `Out-File` never flushed before kill. DB and closeout reports are the authoritative records. |
| **No DB record of X10.6 batch** | Low | The X10.6 module produces a JSON artifact only. A future lane (X11 or X12) should define a `printer_selection_batches` table if DB persistence is required. |

---

## 14. Final Verdict

### `PARTIAL_READY_WITH_TOKEN_LIST_MISMATCH`

The discovery, X6, and X10.6 layers all operated correctly and produced valid output. Memory growth worked for the X5 token list that was run. However, the freshly discovered token (`pumpgrWRAzt`) and the other X6-only selections (`yMJPZbn`) were never fed into the memory factory in this proof session. The end-to-end chain discovery → X6 → X10.6 → X5 memory growth was not demonstrated for any token that was newly discovered in this session.

### `SAFE_TO_PROCEED_TO_X11_DOC_ONLY`

All financial, retrieval, and automation locks held. The memory growth pipeline is functional. No safety violation occurred. Lane X11 (1h activation readiness — documentation and architecture review only) may proceed.

### `NOT_READY_FOR_AUTOMATED_DISCOVERY_TO_X5_SELECTION`

Automated selection from discovery output directly into an X5 run is not enabled and must not be enabled. The operator must manually build the X5 token list from a reviewed X6/X10.6 batch artifact. This is a gate by design, not a gap.

---

## 15. Recommended Next Step

**Proceed to Lane X11 — documentation only.**

Lane X11 scope (documentation and architecture review, no runtime):
- Define 1h snapshot cadence requirements and window identity rules for WINDOW_1H
- Define dirty-memory gates for WINDOW_1H (analogous to WINDOW_15M gates in Lane Q)
- Define how WINDOW_15M and WINDOW_1H coexist in the same pipeline run
- Do NOT run real 1h collection before Lane X11 is approved
- Preserve all locks: BUY/SELL/HOLD, paper decisions, positions, PnL, retrieval remain off
- 4h / 12h / 24h remain disabled until 1h is proven
- WINDOW_5M_MICRO_EVENT remains support-only

**Before the next memory growth proof (pre-X12 or X10.8):**

1. Build a new X5 token list explicitly from the X6/X10.6 batch artifact, including the freshly discovered token where possible, so the end-to-end chain is provable for at least one discovery-selected token.
2. Include ANSEM only with `pair_drift_acknowledged=True` + `manual_override=True` + `manual_override_reason`, or exclude ANSEM until its pair drift is resolved.
3. Confirm the running_jobs=1 leftover scheduler artifact is resolved before the next E2Z pipeline run.

---

## Files Changed

| File | Action |
|---|---|
| `docs/printer-v1-lane-x10-7-manual-discovery-15m-proof-report.md` | **CREATED** (this file) |
| `data/manual-x10-7-backups/printer_v1.before-manual-x10-7-proof.20260706-225124.sqlite3` | Created during proof (backup) |
| `data/manual-x10-7-backups/printer_v1.before-x10-7-x5-run.20260706-225624.sqlite3` | Created during proof (backup) |
| `operator-runs/manual-x10-7/x10-6-selection-batch.json` | Created during proof (X10.6 artifact) |
| `operator-runs/manual-x10-7/x5-1h-proof-run-output.txt` | Created during proof (empty — kill artifact) |
| `data/printer_v1.sqlite3` | Mutated during proof (discovery + X5 run); covered by both backups |

## What Was Not Touched

- `src/printer_v1/operator_cli/lane_x10_6_selection_traceability.py` — unchanged
- `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py` — unchanged
- `src/printer_v1/operator_cli/lane_x5_five_token_runner.py` — unchanged
- `AGENTS.md` — unchanged
- All DB migration files — unchanged
- All test files — unchanged
- No `pyproject.toml` entries added
- No `commands.py` entries added
- No commits made

## Checks Run

| Check | Result |
|---|---|
| `printer-db-counts` (pre, post-discovery, post-run) | PASS |
| `printer-report-e2u-15m-cycle-closeout --operator-approved` | E2U_REPORT_READY |
| `printer-run-lane-v-clean-memory-report --window-kind WINDOW_15M` | LANE_V_REPORT_READY, 25 clean memories |
| Lock delta review (paper/positions/PnL/retrieval) | All zero delta |
| Backup file existence | Both backups confirmed on disk |
| X10.6 artifact existence | `operator-runs/manual-x10-7/x10-6-selection-batch.json` confirmed |

## Risks (Summary)

1. **Token list mismatch** — fresh discovery token never reached memory factory; must be resolved before PARTIAL_READY can be removed.
2. **ANSEM pair drift** — 3 active pairs; override required in every future ANSEM selection batch.
3. **X10.6 no DB persistence** — batch artifact is JSON only; no `printer_selection_batches` table exists yet.
4. **running_jobs=1** — cosmetic scheduler leftover from kill; verify before next E2Z run.

## Whether X11 Can Proceed

**Yes.** Lane X11 (documentation and architecture review for 1h activation readiness) can proceed. No real 1h collection and no code changes are required before X11 approval. All safety locks are intact.
