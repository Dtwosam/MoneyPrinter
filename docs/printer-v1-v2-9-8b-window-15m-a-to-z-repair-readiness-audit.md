# Printer V1 V2-9.8B WINDOW_15M A-to-Z Repair Readiness Audit

Date: 2026-08-03

Lane:

```text
V2-9.8B Full WINDOW_15M Pre-Lifecycle Readiness and Exact Success-Path Repair
```

Phase:

```text
Phase 1 — Verify the five repair findings (read-only)
```

Post-Phase-0 HEAD:

```text
5d995d0bf208347e6d952a0332dca485f8b0b286
```

Subject: `Close latest repaired 15m shortage evidence`

Parent baseline HEAD (required execution HEAD at lane start):

```text
3c426ad546511f759309714c2c3b56d3faf5823e
```

No source was modified in this phase. Each finding is proved or disproved against
the post-Phase-0 tree with exact file / function / line evidence.

## 1. Verdict (Phase 1)

| Finding | Disposition |
| --- | --- |
| 1. Final authorization preparation does not require a fresh full pre-lifecycle readiness result | **CONFIRMED** |
| 2. Malformed DexScreener `pairs` does not persist presence/type diagnostics | **CONFIRMED** |
| 3. Exact public composition uses compressed `0.05`s window; does not prove 900 logical seconds | **CONFIRMED** |
| 4. `campaign_window_registration` is added after close-step `result_json` already persisted | **CONFIRMED** |
| 5. Lane K documentation and implementation disagree on E2Y mandatory for individual promotion | **CONFIRMED** |

All five findings remain eligible for Phase 2 design. None was disproved.
No implementation in this phase.

## 2. Finding 1 — Authorization preparation lacks full pre-lifecycle readiness artifact

### Claim

Final authorization preparation does not require a fresh full pre-lifecycle
readiness result that proves two simultaneously eligible candidates under the
ordinary owners.

### Evidence

| Surface | Location | Observation |
| --- | --- | --- |
| Latest package readiness reference | `operator-runs/…/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/readiness_reference.md` | Binds controlling readiness **audit document** and classification `READY_FOR_FRESH_ONE_USE_WINDOW_15M_AUTHORIZATION`; does **not** bind a live two-candidate pre-lifecycle readiness artifact |
| Authorization package report | same package `authorization_report.md` | Binds parent HEAD, branch, SHA-256, capacity, wrapper law; no simultaneous-eligible-candidate proof |
| Controlling readiness audit | `docs/printer-v1-v2-9-8b-post-rollover-2-repaired-authoritative-window-15m-current-head-readiness-audit.md` | Classifies readiness after **code/repair** closeouts; explicitly allows that live `SOURCE_VISIBILITY_SHORTAGE` may recur |
| Runtime package validators | `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` (`validate_git_provenance_authorization`, package root/file set) | Validates package membership, hashes, provenance — **not** a two-candidate qualification artifact |
| One-shot wrapper | `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` (`_resolve_authorization`, `apply_authorization_once`) | Consumes package + marker law; no pre-lifecycle readiness artifact gate |
| Existing pre-lifecycle stop surface | `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` ~1386–1955 (`stop_before_lifecycle`) | Can return a readiness/admission bundle when invoked, but this path is **not** a mandatory prerequisite of authorization preparation |
| Bounded readiness report | `src/printer_v1/operator_cli/bounded_readiness_report.py` `build_bounded_readiness_report` | Zero-source projection from durable SQLite facts for a run/cycle — not a frozen two-candidate full pre-lifecycle readiness artifact used as an auth gate |

### Proof result

**CONFIRMED.** Formal preparation for the latest one-use package is document- and
provenance-driven. There is no enforceable code gate requiring a fresh full
pre-lifecycle readiness artifact with exactly two simultaneously eligible
candidates before an authorization package may PASS.

### Repair implication

Phase 2 must extend the existing bounded qualification architecture (ordinary
discovery/selection owners + optional `stop_before_lifecycle`) into a durable
readiness artifact, and gate future final-authorization preparation / independent
review on that artifact. Do not invent a parallel selection engine.

## 3. Finding 2 — Malformed DexScreener `pairs` lacks schema diagnostics

### Claim

A malformed DexScreener `pairs` field does not persist presence/type diagnostics
through the normalizer and governed failure recorder.

### Evidence

| Location | Observation |
| --- | --- |
| `src/printer_v1/sources/dexscreener.py` `normalize_dexscreener_fixture_result` lines **682–691** | `pairs = payload.get("pairs")`; if `not isinstance(pairs, list)` returns `NormalizedSourceResult` with `failure_type="dexscreener_malformed_fixture"` and **no** `normalized_payload` |
| Same function lines **727–738** | Valid empty list `pairs: []` correctly returns `PARTIAL` / `ACCEPTABLE_PARTIAL_DATA` with payload `{pairs: [], no_matching_pairs: True, ...}` |
| Same function lines **649–666** | Other fixture failure branches **do** attach `measured_payload` (transport metadata only) |
| `DexScreenerAdapter.execute` lines **106–116** | All transports normalize through `normalize_dexscreener_fixture_result` |
| `src/printer_v1/sources/governed_execution.py` lines **260–270** | On failure, `record_source_failure(..., normalized_payload=result.normalized_payload)` — empty/missing payload → no schema diagnostics persisted |
| `src/printer_v1/sources/recording.py` `record_source_failure` lines **135–179** | Persists `normalized_payload_json` only when payload is non-empty |

Live attempt corroboration (Phase 0): exhaustion certificate shows 18
`LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL` outcomes with
`failure_type=dexscreener_malformed_fixture` and detailed reason
`DexScreener fixture missing pairs` — without structured
`pairs_field_present` / `pairs_field_type` diagnostics on the failure row.

### Proof result

**CONFIRMED.** Missing / non-list `pairs` fails closed (correct outcome) but does
not attach bounded schema diagnostics (`pairs_field_present`,
`pairs_field_type`, measured transport metadata, HTTP status when available).

### Repair implication

Preserve existing outcome taxonomy exactly; for missing/non-list `pairs`, attach
bounded normalized diagnostic payload and ensure the governed failure recorder
persists it through the existing field. No new provider/retry/fallback.

## 4. Finding 3 — Exact public composition is compressed (0.05s), not 900 logical seconds

### Claim

The exact public-composition offline proof uses a compressed `_window_seconds=0.05`
window and does not prove a 900-logical-second lifecycle success path.

### Evidence

| Location | Observation |
| --- | --- |
| `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py` lines **163–166** | Lifecycle kwargs set `"_window_seconds": 0.05`, `"total_duration_seconds": 3.0`, controlled `_sleep` / `_monotonic` |
| Same file harness `offline_exact_public_composition_lifecycle_entry` | Uses real public coordinator / authoritative owner / origin driver / factory / Scheduler ownership with frozen adapters — structural composition, compressed time |
| Contrast: Lane S spaced proof | `tests/test_post_lane10_lane_s_real_spaced_15m_window_proof.py` asserts `elapsed >= 900` for **window** closeout units, but is not the full exact-public two-token campaign composition path |

### Proof result

**CONFIRMED.** Current exact-public-composition node is a fast structural
regression under a 0.05-second window. It does not prove:

- each window elapsed duration ≥ 900 logical seconds;
- full WINDOW_15M close / E2Q / Lane Q / clean-memory / campaign registration
  success path under authoritative 900s law.

### Repair implication

Retain compressed composition as structural regression. Add a focused exact
public-composition test with `_window_seconds=900.0`, controlled clock (no
wall-clock sleep), and full success-path assertions listed in the lane brief.

## 5. Finding 4 — `campaign_window_registration` not re-persisted into close-step `result_json`

### Claim

`campaign_window_registration` is added after the close-step `result_json` has
already been persisted, so the durable step row can omit the registration payload.

### Evidence

| Location | Observation |
| --- | --- |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` `_update_step` lines **2208–2225** | Writes `result_json=_json(result)` into `printer_memory_factory_run_steps` |
| Same file close path lines **4611–4628** | Order is: (1) `_update_step(..., "SUCCEEDED", result)` — **persists** `result_json` **without** `campaign_window_registration`; (2) `result["campaign_window_registration"] = _register_repaired_campaign_window_before_terminalization(...)` — mutates **in-memory** `result` only; (3) `complete_job(...)`; (4) `conn.commit()` |
| `_register_repaired_campaign_window_before_terminalization` lines **2261–2342** | Documents that the close step is already `SUCCEEDED` in the pending transaction; performs ownership-graph registration; returns registration dict; **does not** UPDATE `result_json` |
| `complete_job` (`src/printer_v1/scheduler/scheduler.py` ~284) | Terminalizes scheduler job; does not write factory step `result_json` |

There is **no** second `UPDATE ... result_json=...` between registration assignment
and `commit` on this success path.

### Proof result

**CONFIRMED.** Durable close-step `result_json` can lack
`campaign_window_registration` even when registration succeeded in the same
transaction. In-memory result (and any observers fed that dict) may still see it.

### Repair implication

Preserve transaction ordering (SUCCEEDED → register → fail rolls back step →
terminalize job only after registration success). After successful registration,
re-persist enriched `result_json` containing `campaign_window_registration`
**before** `complete_job()` and commit. No second memory window / duplicate
campaign-window row.

## 6. Finding 5 — Lane K doc vs implementation on E2Y vs individual promotion

### Claim

Lane K documentation and implementation disagree about whether E2Y batch passage
is mandatory for individual clean-memory promotion.

### Evidence — documentation (E2Y mandatory / gates E2Z)

| Location | Text |
| --- | --- |
| `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py` module docstring lines **10–18** | Pipeline lists `E2Y → E2Z`; states "**E2Y (and therefore E2Z)** still requires all 5+ candidates to share the same (token_id, pair_id)"; "Zero clean memories is a valid outcome when E2Y does not pass" |
| Same file `_RECOMMENDED_NEXT_ACTION` lines **125–130** | Advises fixing E2Y set-gate conditions (5 same-pair PARTIAL_MEMORY windows) when E2Y did not pass |

### Evidence — implementation (individual promotion; E2Y informational)

| Location | Text / behavior |
| --- | --- |
| Same file lines **336–341** | Comment: "E2Y set gate — **informational reporting only**"; batch gate "**NOT used to gate E2Z** in mixed batches" |
| Same file lines **364–385** | E2Z eligibility = Lane Q valid ∩ not coverage blocked; calls `create_clean_memory_from_window(..., individual_promotion=True)` |
| Same file ~437 | Notes `"E2Y set gate not passed — individual promotion applied"` when set gate fails |
| `src/printer_v1/operator_cli/e2z_clean_memory_creation.py` lines **178–215** | Documents two modes: batch requires E2Y; `individual_promotion=True` skips E2Y and uses per-window `_gate_window` only |

### Source-stack / closeout history (for Phase 2 contract resolution)

| Source | Adopted contract |
| --- | --- |
| `docs/printer-v1-lane-x10-memory-growth-yield-report.md` (~190–193) | Root cause: E2Y batch gate blocked mixed batches; **fix: E2Y informational; E2Z individual_promotion=True; per-window gate final authority** |
| `docs/printer-v1-v2-6-1a-cadence-fixture-migration-closeout.md` (~110) | Same informational E2Y + individual promotion pattern |

### Proof result

**CONFIRMED** disagreement exists:

- Stale module docstring / recommended-action text claim E2Y gates E2Z.
- Live code path uses `individual_promotion=True` and treats E2Y as informational
  for mixed operational batches.
- Historical closeouts adopt individual promotion as authoritative for operational
  mixed batches; batch mode still requires E2Y when `individual_promotion=False`.

### Repair implication

Do **not** choose by comment alone. Phase 2 must treat source-stack history as
authoritative: individual promotion for mixed operational batches is the adopted
contract; retain `individual_promotion=True`; update stale Lane K docs/comments/
recommended-action; add regression tests that batch mode still requires E2Y and
individual mode still requires every per-window gate. If any higher-order source
stack later reverses this, stop with `BLOCKED_PROMOTION_CONTRACT_CONFLICT`
(not indicated by current history).

## 7. Cross-cutting hard locks (Phase 1)

Verified read-only. No provider contact, no live execution, no authorization
creation, no wrapper run, no DB mutation, no `/private/tmp/mp-preclaim` change.

## 8. Phase 2 design inputs (from confirmed findings only)

| ID | Design contract to draft |
| --- | --- |
| A | DexScreener schema diagnostics on missing/non-list `pairs` |
| B | Full pre-lifecycle readiness artifact via existing qualification owners |
| C | Authorization preparation gate requiring valid readiness artifact |
| D | Durable close-step `result_json` enrichment with `campaign_window_registration` |
| E | Promotion-contract documentation/test alignment (individual promotion authoritative) |

## 9. Phase 1 stop

No source edits. Proceed to Phase 2 design document only.
