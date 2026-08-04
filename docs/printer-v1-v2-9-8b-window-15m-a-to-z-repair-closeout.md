# Printer V1 V2-9.8B WINDOW_15M A-to-Z Repair Closeout

Date: 2026-08-03

Lane:

```text
V2-9.8B Full WINDOW_15M Pre-Lifecycle Readiness and Exact Success-Path Repair
```

## 1. Verdict

```text
V2_9_8B_WINDOW_15M_A_TO_Z_READINESS_AND_SUCCESS_PATH_REPAIR_PASS
```

Readiness classification:

```text
READY_FOR_BOUNDED_LIVE_PRE_LIFECYCLE_READINESS_PROOF
```

This PASS means only that offline repairs and focused proof for the five
confirmed blockers are complete. It does **not** authorize provider contact,
live readiness artifact creation, a new final authorization, wrapper execution,
or another WINDOW_15M campaign.

## 2. Starting and final HEAD

| Item | Value |
| --- | --- |
| Required baseline HEAD (lane start) | `3c426ad546511f759309714c2c3b56d3faf5823e` |
| After Phase 0 evidence commit | `5d995d0bf208347e6d952a0332dca485f8b0b286` |
| Final HEAD (this closeout commit) | subject `Repair full 15m readiness blockers` (resolve: `git rev-parse HEAD`) |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Push | Not performed |
| `/private/tmp/mp-preclaim` | Untouched at `8fb4256c70d4e81660c177238253322cb37ae947` |

## 3. Exact files changed (lane-scoped)

### Phase 0 (prior commit)

- `docs/printer-v1-v2-9-8b-latest-repaired-window-15m-shortage-outcome-closeout.md`
- eight-file package under
  `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/`

### Phase 1–5 (this commit)

| Path | Role |
| --- | --- |
| `docs/printer-v1-v2-9-8b-window-15m-a-to-z-repair-readiness-audit.md` | Phase 1 audit |
| `docs/printer-v1-v2-9-8b-window-15m-a-to-z-repair-design.md` | Phase 2 design |
| `docs/printer-v1-v2-9-8b-window-15m-a-to-z-repair-closeout.md` | This closeout |
| `src/printer_v1/sources/dexscreener.py` | A — pairs schema diagnostics |
| `src/printer_v1/operator_cli/pre_lifecycle_readiness_artifact.py` | B — readiness artifact (new) |
| `src/printer_v1/operator_cli/pre_lifecycle_readiness_authorization_gate.py` | C — auth prep gate (new) |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | D — durable registration result |
| `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py` | E — promotion doc alignment |
| `src/printer_v1/operator_cli/campaign_full_run_accounting.py` | Success-path quality consistency ↔ E2Z |
| `tests/test_v2_9_8b_dexscreener_pairs_schema_diagnostics.py` | DexScreener matrix (new) |
| `tests/test_v2_9_8b_pre_lifecycle_readiness_artifact_and_auth_gate.py` | Artifact + gate matrix (new) |
| `tests/test_v2_9_8b_lane_k_promotion_contract_alignment.py` | Promotion contract (new) |
| `tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py` | Exact 900s composition (new) |
| `tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py` | Quality unit alignment |

No migration. No wrapper edit. Migration-050 package not added.

## 4. Audit findings and disposition

| # | Finding | Disposition | Implementation |
| --- | --- | --- | --- |
| 1 | Auth prep lacks full pre-lifecycle readiness artifact | **CONFIRMED → repaired** | Artifact builder/validator + authorization preparation gate |
| 2 | Malformed DexScreener `pairs` lacks diagnostics | **CONFIRMED → repaired** | Bounded `pairs_field_present` / `pairs_field_type` payload via governed failure recorder |
| 3 | Exact public composition only compressed 0.05s | **CONFIRMED → repaired** | New 900-logical-second composition node; compressed retained |
| 4 | `campaign_window_registration` not re-persisted | **CONFIRMED → repaired** | Re-`_update_step` after registration, before `complete_job` |
| 5 | Lane K doc vs E2Y/individual promotion | **CONFIRMED → repaired** | Docstring + recommended action aligned; regression tests |

Additional success-path alignment (surfaced by 900s composition):

| Issue | Disposition |
| --- | --- |
| Campaign acceptance quality consistency required `CLEAN_MEMORY` on window while E2Z requires `PARTIAL_MEMORY` for clean candidates | **Aligned** — clean candidate = `PARTIAL_MEMORY` or legacy `CLEAN_MEMORY` + `CLEAN_DATA` + `do_not_train=0` |

## 5. Before / after contracts

### A. DexScreener schema diagnostics

| Before | After |
| --- | --- |
| Non-list `pairs` → FAILED, empty payload | FAILED + bounded diagnostics (`MISSING`/`NULL`/`STRING`/…) + measured transport |
| Empty list → PARTIAL | Unchanged PARTIAL |
| Valid rows → COMPLETE | Unchanged |

### B/C. Pre-lifecycle readiness + auth prep gate

| Before | After |
| --- | --- |
| Authorization prep document-only; no two-candidate frozen artifact | Artifact freezes two-candidate qualification; gate fail-closed on absent/expired/HEAD/DB/identity/gates/lineage/downstream |
| Expiry undefined | `expires_at = min(received_at + SOURCE_REGISTRY[source].stale_after_seconds)` |

### D. Campaign-window registration result

| Before | After |
| --- | --- |
| Registration mutates in-memory result after `result_json` write | Enriched `result_json` re-persisted before `complete_job` / commit |

### E. Promotion

| Before | After |
| --- | --- |
| Docstring claimed E2Y gates E2Z | Doc + recommended action: individual promotion authoritative; E2Y informational in mixed batches; batch mode still requires E2Y |

## 6. Exact test commands and counts

```bash
# Focused repair suite (primary)
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py \
  tests/test_v2_9_8b_dexscreener_pairs_schema_diagnostics.py \
  tests/test_v2_9_8b_pre_lifecycle_readiness_artifact_and_auth_gate.py \
  tests/test_v2_9_8b_lane_k_promotion_contract_alignment.py \
  tests/test_v2_9_8b_post_rollover_2_pre_lifecycle_factory_run_identity_and_terminal_contract_repair.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py::QualityConsistencyTests \
  -q
# → 41 passed

# Adjacent regressions
.venv/bin/python -m pytest \
  tests/test_phase24_dexscreener_adapter_disabled.py \
  tests/test_dexscreener_productivity_exclusion.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py::TerminalAndQualityTests \
  -q
# → 26 passed

# Compile + whitespace
.venv/bin/python -m py_compile <changed modules>
git diff --check
```

| Suite | Result |
| --- | --- |
| Focused repair | **41 passed** |
| Adjacent dexscreener + quality | **26 passed** |
| `tests/test_dexscreener_fresh_profiles.py` | **9 failed (pre-existing)** — `_FakeHTTP` missing `byte_ceiling` kwarg; unrelated to pairs diagnostics |

Python compilation of changed modules: PASS. `git diff --check`: PASS.

## 7. What remains external market supply

Live `SOURCE_VISIBILITY_SHORTAGE` on the consumed attempt was honest external
supply/visibility under frozen ceilings:

- 0 eligible of 2 required
- 10 below `$3,000` floor
- 18 DexScreener malformed/partial (now better diagnosed)
- tracking exclusions

Code repairs do not manufacture eligible Pump/PumpSwap candidates. Another live
attempt still depends on simultaneous two-candidate market supply under the same
floors and ceilings.

## 8. Money-usefulness contribution

| Improvement | Why it matters |
| --- | --- |
| Schema diagnostics on malformed liquidity | Operators can distinguish missing/null/typed schema failures from true empty markets without raw bodies |
| Pre-lifecycle readiness artifact + auth gate | Future authorizations cannot PASS without frozen two-candidate qualification proof |
| Durable `campaign_window_registration` | Close-step evidence is complete for report-only replay and acceptance |
| 900-logical-second composition | Proves real WINDOW_15M duration law offline, not only 0.05s structural wiring |
| E2Z ↔ acceptance quality alignment | Clean promotion path can reach campaign acceptance PASS under ordinary PARTIAL_MEMORY candidates |

## 9. What improved

- Fail-closed diagnostics on DexScreener pairs shape
- Formal readiness artifact + preparation gate owners
- Close-step registration durability
- Lane K documentation matches individual-promotion law
- Exact 900s offline success path including registration + campaign PASS
- Quality consistency aligned with E2Z clean-candidate shape

## 10. What remains locked

- Solana-only / Solana memecoin-only / paper-only
- No wallet / keys / signing / real funds / live execution this lane
- No paid API / scores / ranks / confidence / weights / embeddings
- No Source Governor or Central Scheduler bypass
- No dirty-memory use / retrieval / BUY/SELL/HOLD / positions / trades / PnL
- No 1h / 4h / 12h / 24h activation
- No new live source call, authorization, wrapper run, or consumed-auth reuse
- `$3,000` floor, source-operation ceilings, candidate capacity, selection authority unchanged

## 11. Proof still needed before another authorization

1. **Bounded live pre-lifecycle readiness proof** producing one real readiness
   artifact under ordinary owners (`stop_before_lifecycle` / readiness-only),
   with exactly two simultaneous eligible candidates, source lineage, and
   zero lifecycle/memory/Scheduler runtime start.
2. Independent review of that artifact under the new preparation gate.
3. Only then: fresh one-use authorization package + independent review +
   wrapper apply (separate lanes; one-shot law preserved).

Do **not** reuse `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Class | Item |
| --- | --- |
| Risk | Live markets may still yield zero eligible pairs under `$3,000` + 30-op discovery budget |
| Risk | Readiness artifact expiry follows shortest source `stale_after_seconds` (dexscreener=90s) — live prep windows are tight |
| Risk | Quality consistency change broadens clean-candidate recognition; dirty/partial-data + clean episode still blocks |
| Setback | Consumed attempt closed as honest shortage — no lifecycle memory gained from that auth |
| Efficiency blocker | Pre-lifecycle readiness still costs full discovery/holder budget when run live |
| Pre-existing | `test_dexscreener_fresh_profiles.py` FakeHTTP/`byte_ceiling` mismatch (out of scope) |

## 13. Hard locks preserved this lane

No provider contact. No live readiness artifact. No final authorization. No
wrapper execution. No memory window start. No 1h+ work. No DB reset/clean of
evidence. `mp-preclaim` untouched.

## 14. Stop

Stop after this closeout commit. Next permitted preparation step (separate lane):

```text
BOUNDED_LIVE_PRE_LIFECYCLE_READINESS_PROOF
```
