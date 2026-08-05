# Printer V1 — V2-9.8B `WINDOW_15M` A-to-Z Deterministic Readiness Repair Closeout

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M A-to-Z Deterministic Readiness Repair`  
**Branch:** `agent/v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair`  
**Design:** `docs/printer-v1-v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair-design.md`  
**Operator audit (supplied):** `V2_9_8B_WINDOW_15M_FRESH_POST_REPAIR_A_TO_Z_AUDIT_PASS_WITH_BLOCKERS`  
**Operational state before repair:** `V2_9_8B_WINDOW_15M_END_TO_END_READINESS_BLOCKED`

## Final verdict

`V2_9_8B_WINDOW_15M_A_TO_Z_DETERMINISTIC_READINESS_REPAIR_PASS`

## Exact baseline and final commit

| Item | Value |
|---|---|
| Baseline branch | `agent/v2-9-8b-window-15m-end-to-end-readiness-unified-repair` |
| Baseline HEAD | `12c3c3ed077a4f298bcb84da3979794ce57da3a3` |
| Repair branch | `agent/v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair` |
| Final commit | `29d5d3f2738d10431790c78a87dc0f17ff40f9e0` |
| Commit message | `Repair WINDOW_15M A-to-Z deterministic readiness` |

## Authoritative DB before/after identity

Unchanged across the entire repair (read-only; never mutated):

| Fact | Value |
|---|---|
| Path | `data/printer_v1.sqlite3` |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` |
| Size | `68067328` |
| Inode | `1230526` |
| Migration ledger | `52` / head `052_memory_observation_eligibility_layers.sql` |
| Integrity | `ok` |
| Foreign-key violations | `0` |
| Sidecars | none |
| Open handles | none |

## Blocker-by-blocker disposition

| ID | Bundle | Disposition | Proof |
|---|---|---|---|
| D1 | R1 | `CLOSED_WITH_PROOF` | Secret-free consumed packages `…AUTH_20260805T101248Z` and mig050 non-sqlite evidence adopted as immutable tracked history; sqlite binaries remain gitignored |
| D2 | R1 | `CLOSED_WITH_PROOF` | Central `authorization_temporal_validity` enforces timezone-aware issue/expiry, max-age policy (86400s), future-issued/expired/over-age/missing fail before staging; wrapper + manifest document validation |
| D3 | R2 | `CLOSED_WITH_PROOF` | Removed composition catch-and-substitute for invalid explicit RPC; shared `validate_window_15m_source_configuration`; wrapper validates child env mapping before consumption; parent env unchanged |
| D4 | R3 | `CLOSED_WITH_PROOF` | Runtime-derived composition registry (20 builders) shared by production preflight and builder enumeration; includes direct Pump migration + graduation verifier |
| D5 | R3 | `CLOSED_WITH_PROOF` | Strict production adapter contract (execute, contract/metadata, source, enabled, transport, request kind); explicit fixture types only (`ProductionFixtureAdapter` / `PRINTER_EXPLICIT_FIXTURE_ADAPTER` / fixture mode) |
| D6 | R4 | `CLOSED_WITH_PROOF` | Expanded mutation table inventory (eligible reserve, graduated registry, tokens/pairs, selections, tracking, lifecycle, context, coverage, audits, windows, episodes, fingerprints, campaign, Scheduler, source ledgers) |
| D7 | R4 | `CLOSED_WITH_PROOF` | UPDATE-without-net-growth never `UNCHANGED`; net growth not labelled `database_writes`; numeric write count only with owner-emitted authority; first terminal cause preserved |
| D8 | R5 | `CLOSED_WITH_PROOF` | Canonical fingerprint payload: categorical `tracking_lane`, exact episode/window/token/pair identity, age/discovery as values or `UNKNOWN`; idempotent record |

## Files changed

### New

- `src/printer_v1/operator_cli/authorization_temporal_validity.py`
- `tests/test_v2_9_8b_window_15m_a_to_z_deterministic_readiness_repair.py`
- `tests/test_v2_9_8b_window_15m_a_to_z_deterministic_full_path_proof.py`
- `docs/printer-v1-v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair-design.md`
- `docs/printer-v1-v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair-closeout.md`

### Modified

- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` — temporal validity; shared source-config against child env; composition with environment mapping
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` — temporal validity in authorization document validation
- `src/printer_v1/operator_cli/window_15m_concrete_composition.py` — registry + direct migration/graduation builders; strict adapter contract; no RPC catch-and-substitute
- `src/printer_v1/sources/operational_source_contracts.py` — `validate_window_15m_source_configuration`
- `src/printer_v1/sources/governed_execution.py` — explicit fixture marker on `FixtureSourceAdapter`
- `src/printer_v1/operator_cli/action_local_terminal_truth.py` — expanded tables; honest mutation/transport classification
- `src/printer_v1/memory/fingerprints.py` — money-useful categorical payload + idempotent record
- `src/printer_v1/memory/recorder.py` — pass episode_id into fingerprint builder
- Fixture/test updates for temporal fields and composition blocks

### Tracked historical evidence adopted (secret-free)

- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z/*` (7 files)
- `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/*` (10 non-sqlite files; sqlite backups remain gitignored)

## Tests and proof execution identity

### Focused repair suite

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_a_to_z_deterministic_readiness_repair.py \
  tests/test_v2_9_8b_window_15m_a_to_z_deterministic_full_path_proof.py \
  tests/test_v2_9_8b_window_15m_end_to_end_readiness_unified_repair.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py \
  tests/test_phase14_episode_memory_engine.py \
  -q
```

**Result: 151 passed.**

### Exact full-path controlled proof

**Proof execution ID:** `V2_9_8B_WINDOW_15M_A_TO_Z_DETERMINISTIC_FULL_PATH_PROOF_V1`

Covered by `tests/test_v2_9_8b_window_15m_a_to_z_deterministic_full_path_proof.py`:

1. Composition registry + shared source-config law (zero I/O)
2. Disposable Git worktree: historical evidence + fresh fixture authorization; actual one-shot wrapper; one child launch; second application blocked; no second child
3. Disposable Migration-052 DB; 900 logical-second windows; shared registry preflight not patched out; frozen Source-Governed fixtures; zero network; two clean episodes; two payload-valid fingerprints with categorical tracking lane and exact identity; separate lifecycle vs clean-memory PASS; zero active Scheduler residue

## Money-usefulness contribution

- Future one-use authorizations cannot be staged when temporally invalid.
- Consumed evidence can coexist as immutable tracked history with a future current package inventory.
- Wrapper and child share one RPC/configuration law; invalid explicit RPC fails before consumption.
- Ordinary `WINDOW_15M` composition registry includes every default constructor on the persistent path, including direct Pump migration and graduation verification.
- Terminal mutation/transport truth is honest (no false zero writes, no UPDATE-as-UNCHANGED).
- Clean fingerprints carry categorical money-useful condition labels with exact episode linkage.

## What improved

1. Historical rollover of secret-free consumed packages into tracked history  
2. Code-enforced authorization temporal validity (not operator-only)  
3. Wrapper/child source-readiness parity  
4. Runtime-derived 20-builder composition registry + strict adapter contract  
5. Action-local mutation inventory breadth and classification honesty  
6. Canonical fingerprint tracking_lane and identity payload  

## What remains locked

- Solana-only / Solana memecoin-only / paper-only  
- No live wallet, private keys, signing, real funds, or execution  
- No paid API dependency  
- No scoring, ranking, confidence, weighted logic, embeddings, or vectors  
- No Source Governor or Central Scheduler bypass  
- `WINDOW_5M_MICRO_EVENT` support-only; no multi-hour production windows  
- No retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL  
- No automatic retry/restart/recovery/successor  
- No real authorization created by this lane  
- No authoritative DB mutation  

## Proof limits and remaining live uncertainty

- Full-path campaign proof uses frozen Source-Governed fixture bodies and a controlled logical clock (not live market/provider data).
- Ordinary migration/graduation **construction** is proven zero-I/O via the shared registry; campaign offline path still uses frozen direct-origin fixture graduation evidence for candidate supply (live graduated-supply RPC bodies remain live uncertainty).
- Live provider availability, rate limits, and market eligible-supply remain uncertain by nature.
- PASS does **not** authorize a real `WINDOW_15M` run.

## Functionality Risks / Setbacks / Efficiency Blockers

| Class | Note |
|---|---|
| Risk | Temporal validity rejects packages missing `authorized_at`/`expires_at`; historical packages without those fields cannot be re-used as current authority (intended). |
| Risk | Strict production adapter validation rejects arbitrary objects; offline fixtures must use explicit fixture types. |
| Efficiency | Composition preflight constructs 20 builders (zero execute); fixed small cost. |
| Setback | None relative to prior unified-repair closures; those remain closed. |

## Explicit confirmation

- **No real authorization was created.**  
- **No live campaign was run against the authoritative database.**  
- **Authoritative DB identity is unchanged.**  

## Exact next permitted step

Independent **read-only** readiness review before any fresh one-use `WINDOW_15M` authorization.

Do not merge to `master`. Do not create a tag unless separately instructed.
