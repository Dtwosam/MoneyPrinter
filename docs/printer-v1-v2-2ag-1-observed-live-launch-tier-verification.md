# Printer V1 V2-2AG.1 Observed Live Launch Tier Verification

**Lane:** V2-2AG.1 - Independent OBSERVED_LIVE_LAUNCH Tier Verification
**Type:** Verification only
**Verdict:** `VERIFICATION_PASS_WITH_BLOCKERS`
**Target commit verified:** `5c88f26 Add V2-2AG observed live launch tier`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, paper positions, trades, audits, and PnL remain paused.

This verification did not run live sources and did not change implementation
code or tests.

---

## 1. Source Stack Read

| Document | Role |
|---|---|
| `AGENTS.md` | Highest local build rules and active anchors |
| `docs/printer-v1-clean-master-spec.md` | V1 master safety/specification rules |
| `docs/printer-v1-memory-growth-build-order-v2.md` | Active V2 memory-growth roadmap |
| `docs/printer-v1-v2-2af-pumpportal-launch-timestamp-evidence-design-update.md` | OBSERVED_LIVE_LAUNCH design update |
| `docs/printer-v1-v2-2ag-observed-live-launch-tier-implementation.md` | Implementation closeout for target commit |
| `docs/printer-v1-v2-2ae-pumpportal-live-event-diagnostics.md` | Prior live event diagnostics |
| `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md` | T2 token-age evidence contract and invariants |

The source stack preserves the same V1 constraints: Solana-only,
paper-trading-only, free/public sources only, no wallet/private-key/signing,
no live execution, no scoring/ranking/confidence/weighted logic, no retrieval
activation, no paper decisions, no BUY/SELL/HOLD, no positions, and no PnL.

---

## 2. Files Inspected

Target commit file list:

| File | Verification result |
|---|---|
| `src/printer_v1/sources/pumpportal.py` | OBSERVED_LIVE_LAUNCH flag is bounded to mint-bearing launch events with no timestamp keys |
| `src/printer_v1/discovery/parser.py` | T2 precedence and observed-live tier derivation verified |
| `tests/test_v2_2x2_t2_token_age_evidence.py` | T2 preservation and no-age behavior covered |
| `tests/test_v2_2ag_observed_live_launch_tier.py` | New observed-live tier behavior covered |
| `docs/printer-v1-v2-2ag-observed-live-launch-tier-implementation.md` | Implementation proof/report added by target commit |

Static path scan found no target-commit changes in memory, retrieval, paper,
trading, scheduler, runtime, wallet, signing, or PnL paths.

Selection metadata path inspected:

| File | Verification result |
|---|---|
| `src/printer_v1/discovery/selection_batch.py` | `_METADATA_FIELDS` carries `token_age_evidence_tier`; A3 and age buckets still require `token_age_seconds` |

---

## 3. T2 Preservation Result

T2 still takes precedence over OBSERVED_LIVE_LAUNCH.

Verified behavior:

- `pumpportal.py` extracts explicit launch timestamp fields in priority order:
  `tokenCreatedAt`, `createdTimestamp`, then `timestamp`.
- `parser.py` returns `token_age_evidence_tier = "T2"` when:
  - `source_name == "pumpportal"`
  - `request_kind == "pumpfun_launch_stream"`
  - an explicit source-provided `token_created_at` value exists
  - `token_age_seconds` can be derived.
- OBSERVED_LIVE_LAUNCH is evaluated only after T2 fails.
- A stale, invalid, zero, or malformed timestamp key still counts as a
  timestamp field being present; it does not fall through to observed-live.

Safety conclusion: T2 evidence remains stronger than observed-live evidence,
and bad explicit timestamp evidence is not converted into a fake observed-live
age tier.

---

## 4. OBSERVED_LIVE_LAUNCH Behavior Result

OBSERVED_LIVE_LAUNCH is correctly narrow.

Verified behavior:

- `_normalize_pumpportal_event()` returns `None` before tier logic if the event
  has no mint, so subscription acknowledgements and missing-mint events are
  excluded.
- `live_observed_launch=True` can only be set when:
  - `request_kind == "pumpfun_launch_stream"`
  - a mint-bearing event is being normalized
  - no explicit timestamp key exists among `tokenCreatedAt`,
    `createdTimestamp`, and `timestamp`
  - `token_created_at` remains `None`.
- `parser.py` maps that flag to `token_age_evidence_tier =
  "OBSERVED_LIVE_LAUNCH"` only for `pumpportal` / `pumpfun_launch_stream`.
- OBSERVED_LIVE_LAUNCH leaves:
  - `token_created_at = None`
  - `token_age_seconds = None`

Safety conclusion: the implementation records that a live launch event was
observed without pretending that the token creation timestamp is known.

---

## 5. Captured-At Boundary

`captured_at` does not populate `token_created_at`.

Verified behavior:

- `parser.py` derives `token_created_at` only from explicit
  `token_created_at` / `tokenCreatedAt` input, not from `captured_at`.
- OBSERVED_LIVE_LAUNCH candidates keep `token_created_at` and
  `token_age_seconds` empty.
- The tests cover no-timestamp live launch events and assert that observed-live
  tier does not create token age.

Safety conclusion: observation time remains observation time. It is not reused
as token creation time.

---

## 6. A3 Lock Result

A3 remains locked without real token age.

Verified behavior in `selection_batch.py`:

- `_tok_age_known = candidate.get("token_age_seconds") is not None`
- A3 (`LATE_BUY_TRAP`) requires `_tok_age_known`, known `price_change_1h`,
  token age at or above the late-buy threshold, and negative 1h price change.
- `derive_age_bucket()` still reads `token_age_seconds`; missing token age
  remains `AGE_UNKNOWN`.
- Observed-live candidates keep `token_age_seconds=None`, so they cannot
  satisfy `_tok_age_known`.

Safety conclusion: OBSERVED_LIVE_LAUNCH does not unlock A3, recent-active
priority, or token-age buckets.

---

## 7. Migration Exclusion Result

Migration events remain excluded from observed-live launch tier.

Verified behavior:

- `pumpportal.py` only sets `live_observed_launch=True` in the
  `pumpfun_launch_stream` branch.
- `parser.py` returns `None` for token-age evidence tier unless
  `request_kind == "pumpfun_launch_stream"`.
- The observed-live tests cover migration events and confirm they do not get
  OBSERVED_LIVE_LAUNCH.

Safety conclusion: migration timing is not treated as token creation timing,
preserving the STNP and late-buy-trap boundary.

---

## 8. Metadata Persistence Result

Observed-live tier persists safely as metadata.

Verified behavior:

- `token_age_evidence_tier` is part of `NORMALIZED_FIELDS` in
  `parser.py`.
- `token_age_evidence_tier` is included in `_METADATA_FIELDS` in
  `selection_batch.py`.
- The selection-batch regression suite passed, including metadata handoff
  behavior.
- The V2-2AG test suite verifies that an OBSERVED_LIVE_LAUNCH candidate carries
  the tier into selection metadata while keeping token age unknown.

Safety conclusion: the tier is auditable downstream as categorical metadata
without becoming a token-age substitute or trade signal.

---

## 9. Tests And Checks Run

| Command | Result |
|---|---|
| `python -m pytest tests/test_v2_2ag_observed_live_launch_tier.py -q` | Passed: 30 passed |
| `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q` | Passed: 82 passed |
| `python -m pytest tests/test_v2_2ab_pumpportal_live_transport.py -q` | Passed: 43 passed |
| `python -m pytest tests/test_v2_2c_selection_batch.py -q` | Passed: 120 passed |

Pytest emitted the existing local `gltest.config.yaml` notice and pytest cache
warning. These did not fail the focused suites.

Git checks are recorded in the final lane response after this document is
created.

---

## 10. Safety Confirmations

| Safety item | Result |
|---|---|
| No live source run in this lane | Confirmed |
| No source expansion | Confirmed |
| No runtime/scheduler activation | Confirmed |
| No memory generation | Confirmed |
| No retrieval activation | Confirmed |
| No paper decisions | Confirmed |
| No BUY/SELL/HOLD | Confirmed |
| No positions, trades, audits, or PnL | Confirmed |
| No wallet/private-key/signing/live execution | Confirmed |
| No scoring/ranking/confidence/weighted logic | Confirmed |
| No embeddings/vectors | Confirmed |
| Migration events excluded from token-age tier | Confirmed |
| `captured_at` not used as `token_created_at` | Confirmed |
| OBSERVED_LIVE_LAUNCH leaves token age unknown | Confirmed |
| A3 remains locked without `token_age_seconds` | Confirmed |

---

## 11. Remaining Blockers

| Blocker | Status | Impact |
|---|---|---|
| Live proof after implementation has not run | BLOCKING NEXT PROOF | OBSERVED_LIVE_LAUNCH is verified in code/tests, but real PumpPortal event behavior must still be proven in a bounded live lane |
| T2 explicit timestamps are still absent in observed live samples | CARRY-FORWARD | T2 token age remains unavailable unless real payloads include timestamp fields |
| OBSERVED_LIVE_LAUNCH is not token age | INTENTIONAL | It improves auditability but does not unlock A3 or recent-active tiers |
| V2-3 remains paused | CONFIRMED | Discovery/selection is still inside V2-2 proof/repair lanes |

---

## 12. Exact Next Recommended Lane

`V2-2AH - OBSERVED_LIVE_LAUNCH Live Proof`

Recommended scope:

- Use isolated proof DB only.
- Run one bounded, operator-approved PumpPortal `pumpfun_launch_stream` proof.
- Confirm whether real mint-bearing no-timestamp launch events produce
  OBSERVED_LIVE_LAUNCH.
- Confirm persistent DB remains unchanged.
- Confirm zero memory/retrieval/paper/trading/PnL deltas.
- Do not unlock V2-3 unless the operator explicitly accepts the remaining
  V2-2 blockers.

---

## 13. Final Verification Verdict

```text
VERDICT: VERIFICATION_PASS_WITH_BLOCKERS
TARGET_COMMIT_VERIFIED: 5c88f26
OBSERVED_LIVE_LAUNCH_SCOPE: mint-bearing pumpfun_launch_stream events with no timestamp fields
T2_PRECEDENCE: PRESERVED
CAPTURED_AT_AS_TOKEN_CREATED_AT: BLOCKED
TOKEN_CREATED_AT_FOR_OBSERVED_LIVE_LAUNCH: None
TOKEN_AGE_SECONDS_FOR_OBSERVED_LIVE_LAUNCH: None
A3_UNLOCKED_BY_OBSERVED_LIVE_LAUNCH: NO
MIGRATION_EVENTS_EXCLUDED: YES
METADATA_PERSISTENCE: VERIFIED
LIVE_PROOF_STATUS: STILL_REQUIRED
V2_3_STATUS: PAUSED
```
