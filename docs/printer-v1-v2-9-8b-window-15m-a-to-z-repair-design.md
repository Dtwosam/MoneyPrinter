# Printer V1 V2-9.8B WINDOW_15M A-to-Z Repair Design

Date: 2026-08-03

Lane:

```text
V2-9.8B Full WINDOW_15M Pre-Lifecycle Readiness and Exact Success-Path Repair
```

Phase:

```text
Phase 2 — Final design
```

Post-Phase-0 HEAD at audit:

```text
5d995d0bf208347e6d952a0332dca485f8b0b286
```

Controlling audit:

`docs/printer-v1-v2-9-8b-window-15m-a-to-z-repair-readiness-audit.md`

All five findings were **CONFIRMED**. This design covers only those findings.
No real readiness artifact or authorization is created in this lane.

## 1. Design verdict

```text
V2_9_8B_WINDOW_15M_A_TO_Z_REPAIR_DESIGN_READY
```

Authority resolutions:

| Question | Resolution |
| --- | --- |
| Pre-lifecycle readiness expiry | **Resolved** — use existing `SOURCE_REGISTRY[*].stale_after_seconds` against each gate evidence timestamp; artifact `expires_at = min(evidence_received_at + stale_after_seconds)` over all embedded evidence rows. Not an invented free-floating TTL. |
| Scheduler ownership for qualification mode | **Resolved** — existing `stop_before_lifecycle` / pre-lifecycle path must not start Scheduler lifecycle runtime, tracking enqueue, memory windows, or factory retain. No Scheduler ownership-law change. |
| Promotion contract | **Resolved** — source-stack history (`lane-x10` yield report, V2-6.1a closeout) adopts **individual promotion** as authoritative for mixed operational batches; E2Y remains mandatory for batch mode (`individual_promotion=False`). |
| Wrapper one-use law | **Unchanged** — gate is enforced at authorization-preparation / independent-review owners; wrapper is not modified unless those owners cannot enforce (not required here). |

No design stop codes apply:

- `BLOCKED_PRE_LIFECYCLE_READINESS_EXPIRY_CONTRACT_UNRESOLVED` — not raised
- `BLOCKED_PRE_LIFECYCLE_READINESS_AUTHORITY_UNRESOLVED` — not raised
- `BLOCKED_REQUIRES_SEPARATE_WRAPPER_LAW_APPROVAL` — not raised
- `BLOCKED_PROMOTION_CONTRACT_CONFLICT` — not raised
- `BLOCKED_REQUIRES_SEPARATE_SCHEMA_APPROVAL` — not expected (no migration)

## 2. Contract A — DexScreener schema diagnostics

### Owner

`src/printer_v1/sources/dexscreener.py` → `normalize_dexscreener_fixture_result`

Persistence owner (unchanged):

`src/printer_v1/sources/governed_execution.py` → `record_source_failure(..., normalized_payload=result.normalized_payload)`

### Preserve outcomes exactly

| Input | Outcome |
| --- | --- |
| `pairs` list with rows | existing normalization / COMPLETE or eligibility filters |
| valid `pairs: []` | `PARTIAL` / `ACCEPTABLE_PARTIAL_DATA` (unchanged) |
| missing `pairs` | malformed (`dexscreener_malformed_fixture`) |
| `pairs: null` | malformed |
| string / object / number / boolean `pairs` | malformed |
| no malformed / no-match candidate becomes liquidity eligible | unchanged |

### Change

When `pairs` is missing or not a list, return the same FAILED / MISSING_CRITICAL_DATA
outcome, but attach a **bounded** `normalized_payload` containing:

| Field | Rule |
| --- | --- |
| existing measured transport metadata | via current `merge_transport_payload_metadata` / measured fields when present on payload |
| `pairs_field_present` | `False` if key absent; `True` if key present (including null) |
| `pairs_field_type` | categorical label only |
| `pairs_count` | always `null` for non-list |
| `source_http_status` | from existing payload keys when already available (e.g. `_source_status_code`); else omit or null |
| `request_kind` | requested kind |
| raw body | **never** |
| secrets / headers | **never** |

Stable type labels:

```text
MISSING | NULL | LIST | OBJECT | STRING | NUMBER | BOOLEAN | OTHER
```

(`LIST` is not used on the malformed path; empty list is the PARTIAL path.)

No new provider, retry, rotation, or fallback.

## 3. Contract B — Full pre-lifecycle readiness artifact

### Architecture rule

Extend existing bounded qualification architecture only:

- ordinary graduated supply / exact pool confirmation
- liquidity floor ≥ `$3,000` on exact pool
- tracking / cooldown eligibility
- holder eligibility
- neutral two-candidate selection
- source-quality gates
- optional `stop_before_lifecycle` / readiness-only surfaces

**Do not** create a parallel discovery or selection engine.

### Generation precondition

Artifact is generated **only after** ordinary owners prove **exactly two** distinct
candidates simultaneously pass all admission gates above.

If fewer than two pass → no artifact (block / fail closed).

### Artifact contents

| Field group | Content |
| --- | --- |
| Identity | schema version; qualification/execution identity; exact implementation HEAD |
| DB identity | exact path, SHA-256, size, mtime |
| Time | `created_at`; `expires_at` (see freshness law) |
| Candidates | exactly two mint/pool identities |
| Source lineage | request / response / failure IDs used for each admission gate per candidate |
| Evidence timestamps | liquidity and holder evidence timestamps |
| Gate results | categorical PASS/FAIL per gate |
| Downstream confirmation | tracking, lifecycle, memory, Scheduler runtime **did not start** |
| Capability deltas | all zero for retrieval / financial / forbidden tables |

### Freshness / expiry law (source stack)

Use `printer_v1.sources.registry.SOURCE_REGISTRY[source_name].stale_after_seconds`
(existing Source Governor law; see `governor.is_source_result_stale`).

For every embedded evidence row with `(source_name, received_at)`:

```text
row_expires_at = received_at + stale_after_seconds(source_name)
artifact.expires_at = min(row_expires_at over all rows)
```

If a required evidence row lacks timestamp or unknown source_name → fail closed
(no artifact / invalid artifact).

Validation at any later time `now`:

- `now <= expires_at`
- each evidence row still non-stale under the same law
- candidate count == 2; identities match; gates PASS; no lifecycle/memory/tracking started claims violated

### Scheduler

Qualification mode must record `scheduler_runtime_started=false` and must not
enqueue tracking or open memory windows. No Scheduler ownership-law edit.

### New owner module (proposed)

`src/printer_v1/operator_cli/pre_lifecycle_readiness_artifact.py`

Functions:

- `build_pre_lifecycle_readiness_artifact(...)`
- `validate_pre_lifecycle_readiness_artifact(...)`
- `compute_readiness_artifact_expiry(...)`

## 4. Contract C — Authorization preparation gate

### Formal owners

| Role | Owner |
| --- | --- |
| Package structure / apply-time validation | `git_provenance_authorization_manifest.py` (`_validate_authorization_document`, `validate_git_provenance_authorization`) |
| One-shot apply | `window_15m_one_shot_wrapper.py` (unchanged one-use law) |
| Preparation / independent-review gate (new) | `pre_lifecycle_readiness_authorization_gate.py` — pure validator invoked by future preparation and independent-review procedures |

### Gate rules (fail closed)

A future authorization package preparation may PASS only if a readiness artifact
validates and:

| Failure | Condition |
| --- | --- |
| absent | no artifact |
| expired | `now > expires_at` or any evidence stale |
| HEAD differs | artifact HEAD ≠ preparation HEAD |
| DB identity differs | path/sha256/size/mtime mismatch |
| candidate count | not exactly two |
| mint/pool identity | differs from artifact |
| liquidity/holder gate | not PASS |
| source lineage | incomplete |
| candidate state | no longer eligible (when rechecked from provided state snapshot) |
| downstream claim | artifact claims tracking / lifecycle / memory work occurred |

### Wrapper

Not modified. Existing authorization-law owners can enforce the prerequisite at
preparation/review time via the new gate function. No
`BLOCKED_REQUIRES_SEPARATE_WRAPPER_LAW_APPROVAL`.

### Non-goals this lane

- Do not create a real readiness artifact
- Do not create a real authorization package
- Do not break historical packages that predate the gate (gate is an explicit
  preparation/review call; historical apply path remains package-byte validation)

## 5. Contract D — Durable campaign-window registration result

### Owner

`src/printer_v1/operator_cli/one_command_15m_factory.py` WINDOW_CLOSE success path
(~4611–4628)

### Preserve transaction ordering

1. Close step becomes `SUCCEEDED` in the pending transaction (`_update_step`)
2. Campaign-window registration validates and writes exact ownership graph
3. Registration failure rolls back the pending step update (same transaction)
4. Scheduler job is terminalized only after successful registration (`complete_job`)

### Change

After successful registration mutates in-memory `result` with
`campaign_window_registration`, **re-persist** close-step `result_json` with the
enriched payload **before** `complete_job()` and `commit`.

Do not create a second memory window or duplicate campaign-window row.

Minimal approach: second `_update_step` / targeted `UPDATE result_json` while status
remains `SUCCEEDED`, still inside the open transaction.

## 6. Contract E — Promotion-contract alignment

### Adopted contract (source history)

Individual promotion is authoritative for mixed operational batches:

- retain `individual_promotion=True` in Lane K operational path
- E2Y remains available for batch mode; informational in mixed operational batches
- batch mode (`individual_promotion=False`) still requires E2Y passage

### Documentation updates

In `lane_k_e2z_pipeline_wiring.py`:

- module docstring: align with individual promotion + informational E2Y
- `_RECOMMENDED_NEXT_ACTION`: stop implying E2Y batch fix is mandatory for individual promotion
- keep inline comments that already state informational E2Y

### Regression tests

- batch mode still requires E2Y
- individual mode still requires every per-window gate (`_gate_window` / dirty blocks)
- mixed batch can promote clean windows when E2Y set gate fails

## 7. Contract F — Exact 900-logical-second public composition proof

### New focused test node

Reuse real public coordinator / authoritative owner / origin driver / one-command
factory / ordinary Scheduler ownership / frozen adapters / disposable Migration-050
DB / controlled clock.

Parameters:

- `_window_seconds=900.0`
- total logical duration > 900 seconds
- no wall-clock sleep; no network

Assert full success path listed in the lane brief (two slots, factory identity,
lifecycle started, open/close snapshots, elapsed ≥ 900, cadence, two WINDOW_CLOSE,
two WINDOW_15M, E2Q + Lane Q, clean-memory episodes, campaign terminal state,
`campaign_window_registration` in close-step `result_json`, campaign acceptance
PASS, report-only replay, zero residue, zero retry/restart/resume/successor,
zero retrieval/financial deltas).

### Retain

Existing compressed `0.05` composition as fast structural regression.

## 8. Hard locks (design)

Unchanged from lane brief: Solana-only, paper-only, no live provider contact,
no new authorization, no wrapper execution, no 1h/4h, no retrieval/financial
unlock, no Source Governor / Scheduler bypass, ceilings and $3,000 floor frozen.

## 9. Implementation scope (Phase 3)

| Area | Files (expected) |
| --- | --- |
| A | `src/printer_v1/sources/dexscreener.py` |
| B | `src/printer_v1/operator_cli/pre_lifecycle_readiness_artifact.py` (new) |
| C | `src/printer_v1/operator_cli/pre_lifecycle_readiness_authorization_gate.py` (new) |
| D | `src/printer_v1/operator_cli/one_command_15m_factory.py` |
| E | `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py` |
| Tests | focused new / extended offline tests only |
| Docs | audit (done), design (this), closeout (Phase 5) |

No migration. No wrapper edit. No live execution.

## 10. Phase 2 stop

Design is ready for Phase 3 implementation of confirmed findings only.
