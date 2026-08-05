# Printer V1 — V2-9.8B `WINDOW_15M` A-to-Z Deterministic Readiness Repair Design

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M A-to-Z Deterministic Readiness Repair`  
**Branch:** `agent/v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair`  
**Baseline HEAD:** `12c3c3ed077a4f298bcb84da3979794ce57da3a3`  
**Baseline branch:** `agent/v2-9-8b-window-15m-end-to-end-readiness-unified-repair`  
**Operator audit verdict (supplied):** `V2_9_8B_WINDOW_15M_FRESH_POST_REPAIR_A_TO_Z_AUDIT_PASS_WITH_BLOCKERS`  
**Operational state:** `V2_9_8B_WINDOW_15M_END_TO_END_READINESS_BLOCKED`

## 1. Design verdict

`V2_9_8B_WINDOW_15M_A_TO_Z_DETERMINISTIC_READINESS_REPAIR_DESIGN_PASS`

This design closes the eight confirmed deterministic readiness gaps (R1–R5) without weakening prior Scheduler, lifecycle, memory-close, cleanup, replay, Source Governor, Central Scheduler, or capability-lock proofs. No real authorization and no live campaign are authorized by this design.

## 2. Baseline identity (recorded, not mutated)

| Fact | Value |
|---|---|
| Exact HEAD | `12c3c3ed077a4f298bcb84da3979794ce57da3a3` |
| Tracked worktree | clean (only untracked operator-runs evidence) |
| Authoritative DB path | `data/printer_v1.sqlite3` |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` |
| Size | `68067328` |
| Inode | `1230526` |
| Migration ledger | `52` / head `052_memory_observation_eligibility_layers.sql` |
| Integrity | `ok` |
| Foreign keys | `0` violations |
| Sidecars | none (`-wal`/`-shm`/`-journal` absent) |
| Open handles | none |

The authoritative DB is not open or actively owned. It must not be mutated at any point.

## 3. Confirmed blockers (against current code)

| ID | Bundle | Confirmed defect |
|---|---|---|
| D1 | R1 | Consumed untracked packages (`…AUTH_20260805T101248Z`, mig050 non-sqlite evidence) block exact inventory coexistence with a future current package |
| D2 | R1 | Authorization temporal validity is `OPERATOR_ENFORCED_ONLY`; missing/malformed/expired/over-age/future-issued packages are not code-blocked before staging |
| D3 | R2 | Composition preflight catch-and-substitutes official public RPC when explicit `PRINTER_SOLANA_RPC_URL` is invalid, diverging from child resolution |
| D4 | R3 | Manually claimed 18-entry composition matrix omits ordinary-path direct Pump migration transport/adapter and exact graduation-verifier transport |
| D5 | R3 | Adapter validation treats missing `enabled`/`transport` as implicit fixture exemption; arbitrary objects can pass |
| D6 | R4 | Mutation inventory omits several ordinary-path tables (eligible reserve, graduated registry, tokens/pairs, selections, tracking, lifecycle, context, coverage, audits) |
| D7 | R4 | Count-delta `0` is labelled `UNCHANGED`; net row growth is emitted as `database_writes`; update-only / retained-reuse / projection-only are not categorically distinguished |
| D8 | R5 | Fingerprint `tracking_lane` stores window `supporting_context_json` (object/string blob); categorical lane and exact identity linkage are not honest |

Prior unified-repair closures (B1–B8 composition/backup/clean-memory) remain closed and must not be reopened or weakened.

## 4. Repair design

### R1 — Historical evidence rollover and temporal authorization

**Historical adoption**

1. Secret-scan every consumed untracked migration/authorization package file.
2. If any secret material is present → stop `BLOCKED` (do not commit, do not invent archive systems).
3. If secret-free → `git add` exact paths under the existing tracked-history model expected by the manifest validator.
4. Preserve paths, hashes, consumed status, and historical identity. Do not delete, silently move, rewrite, or reuse consumed evidence.
5. Gitignored SQLite binaries (`.sqlite3`) remain ignored; their non-sqlite package siblings are adopted.

**Temporal validity (before staging, marker, or consumption)**

Central owner: `printer_v1.operator_cli.authorization_temporal_validity` (new, pure).

Policy constants (single owner):

- `AUTHORIZATION_MAX_VALIDITY_SECONDS = 86400` (24h maximum age / validity span)

Required fields (use existing names):

- `authorized_at` — timezone-aware issue time
- `expires_at` — timezone-aware expiry (or derive from `authorized_at + validity_seconds` when `expires_at` absent but `validity_seconds` present; still fail if neither usable expiry exists)
- `validity_seconds` — optional; when present must be positive and ≤ central max

Rules (all fail closed, unconsumed):

| Condition | Failure code |
|---|---|
| Missing issue time | `AUTHORIZATION_ISSUE_TIME_MISSING` |
| Malformed / naive issue or expiry | `AUTHORIZATION_TEMPORAL_MALFORMED` |
| Future-issued (issue > now + small skew) | `AUTHORIZATION_FUTURE_ISSUED` |
| Expiry ≤ issue | `AUTHORIZATION_EXPIRY_NOT_AFTER_ISSUE` |
| validity_seconds over central max | `AUTHORIZATION_OVER_MAX_AGE_POLICY` |
| now > expiry | `AUTHORIZATION_EXPIRED` |
| now < issue | `AUTHORIZATION_NOT_YET_VALID` |
| issue age > central max | `AUTHORIZATION_OVER_AGE` |

Integration points:

1. Wrapper `apply_authorization_once` — immediately after authorization document resolution, before child-interpreter / migration / composition / staging.
2. Manifest document validation — same pure function so pre-marker and full validation cannot stage an invalid package.

No new archive system. No secret commit. No rewrite of historical packages.

### R2 — Exact wrapper/child source-readiness parity

**Shared owner:** `resolve_solana_rpc_configuration` in `operational_source_contracts` remains the sole configuration law.

Changes:

1. Remove composition preflight catch-and-substitute of invalid explicit RPC.
2. Add `validate_window_15m_source_configuration(environment)` that:
   - missing RPC → documented official public fallback (success);
   - present malformed / placeholder / non-HTTPS / userinfo / invalid → fail with exact code.
3. Wrapper validates the **same child environment mapping** that will be launched (parent env with binding vars updated/cleared as today), before marker creation.
4. Parent environment remains unchanged.
5. No retries, endpoint rotation, paid fallbacks, or hidden environment mutation.

### R3 — Runtime-derived composition registry and strict adapter contract

**Single registry** used by production preflight and runtime builder enumeration:

- Rename/maintain `COMPOSITION_MATRIX` as the authoritative registry of ordinary persistent `WINDOW_15M` default constructors.
- Add missing ordinary-path entries:
  - `direct_pump_finalized_migration_transport` / adapter (`build_direct_pump_migration_transport` / `build_direct_pump_migration_adapter`)
  - `exact_pump_pumpswap_graduation_verifier_transport` (`build_graduation_verifier_transport`)
- Keep existing PumpSwap account confirmation, DexScreener/GeckoTerminal nomination/market/backup, lifecycle exact-pair primary/fallback, Coingecko, GoPlus, Jupiter entry/exit, Solana holder primary, Helius free backup.
- Builders remain zero-I/O construction only.

**Strict adapter validation** (`require_concrete_adapter`):

Production mode requires:

- callable `execute`
- canonical `contract` or `metadata` with exact expected source identity
- enabled state where applicable
- callable explicit transport where required
- compatible governed request kind (contract `allowed_request_kinds` contains expected kind when supplied)

Arbitrary non-`None` objects fail.

Fixture exceptions: explicit `ProductionFixtureAdapter` marker type **or** `validation_mode="fixture"` / `test_only=True` keyword — never missing attributes as implicit exemption.

### R4 — Honest action-local mutation and transport truth

Expand `_MUTATION_TABLES` to every ordinary-path reachable table, including:

- eligible reserve, graduated registry, tokens, pairs
- selections / tracking / lifecycle events
- context / coverage / audits / windows / episodes / fingerprints
- campaign ownership, Scheduler, source ledgers (existing + gaps)

Classification law (categorical, no unbounded SQL trace):

| Case | Label |
|---|---|
| Net positive row growth | `INSERT_NET_POSITIVE` |
| Net zero growth + identity changed (or campaign-scoped update evidence) | `UPDATE_WITHOUT_NET_GROWTH` (never `UNCHANGED`) |
| Net zero + identity unchanged | `UNCHANGED` |
| Net negative | `NET_NEGATIVE_OR_DELETE` |
| No baseline | `UNKNOWN_NOT_ATTRIBUTABLE` |

Transport / write truth:

- `fresh_external_transport_attempts` — measured transport rows or request IDs with fresh transport
- `retained_evidence_reuse_zero_transport` — campaign-linked rows without new transport
- `projection_only_writes` — report/projection tables only
- `database_writes` — numeric **only** when owner-emitted authoritative write IDs exist; otherwise `null` / `UNKNOWN_NOT_ATTRIBUTABLE`
- Do **not** assign net row growth to `database_writes`
- Preserve immutable first terminal cause; cleanup/reporting faults remain secondary

### R5 — Canonical money-useful fingerprint payload

Repair only `build_memory_fingerprint_payload` / recording through existing fingerprint owner.

Payload must include:

- exact `episode_id`, `window_id`, `token_id`, `pair_id` when known
- exact `window_kind` (`WINDOW_15M` for this path)
- source window `outcome_label`
- categorical `tracking_lane` (parse from window supporting context JSON / direct field — **not** the full context object)
- `token_age_bucket`, `pair_age_bucket`, `discovery_label` as canonical values or categorical `UNKNOWN`
- existing market / chain / safety / liquidity / exit-realism / flow / trend / volatility / micro-event labels

Rules:

- no mapping/object stored in a categorical field
- idempotent exact-linked clean fingerprint creation (existing episode uniqueness)
- dirty / audit-only / out-of-scope windows still cannot create clean indexable fingerprints (`fingerprint_can_be_indexed_later`)

No new fingerprint schema, retrieval path, scoring, confidence, ranking, weighting, embedding, or vector.

## 5. Test plan (risk-based minimum)

### Authorization / evidence

- secret-free consumed packages become immutable tracked history
- different current package passes exact inventory reconciliation (disposable fixture)
- consumed history cannot be reused as current authority
- missing / malformed / future-issued / expired / over-age fail before staging or consumption
- temporal failure creates no marker and launches no child

### Wrapper/child parity

- missing RPC → documented fallback
- invalid explicit RPC fails in wrapper before consumption
- wrapper and child produce the same configuration verdict from the same environment
- parent environment unchanged

### Composition registry

- registry labels equal production runtime builder identities
- direct migration + graduation-verifier included
- every registered builder constructs with zero network I/O
- builder raise / None / disabled / missing transport / wrong source / unsupported request kind / arbitrary object fail before request, campaign identity, supervision, or DB mutation

### Mutation truth

- insert-only, update-only, mixed, retained-reuse, projection-only, unattributable classified honestly
- update-only never reported as unchanged or zero writes
- no false numeric write count
- first terminal cause unchanged when accounting/cleanup also fails

### Fingerprints

- payload contains exact outcome and tracking lane
- age/discovery facts canonical or `UNKNOWN`
- no mapping/object in categorical fields
- exact episode/window/token/pair linkage
- second invocation idempotent
- dirty/audit-only/out-of-scope cannot create clean fingerprints

### Exact full-path controlled proof

One retained zero-network proof after R1–R5:

- disposable Migration-052 SQLite
- disposable Git worktree with fresh fixture authorization + historical evidence
- actual one-shot wrapper boundary, manifest/marker validation, child activation preflight
- shared runtime composition registry
- ordinary persistent eligible-supply owner
- frozen lawful Source-Governed transports
- zero external network; no preassembled `graduation_proofs`; no `graduated_supply=None` / `migration_transport=None` production bypasses as proof of ordinary path (test may still inject frozen transports at DI seams that production uses)
- controlled logical time for real 900-second `WINDOW_15M`
- asserts the 17 proof requirements listed in the lane brief

## 6. Documentation / deliverables

- This design
- Closeout: `docs/printer-v1-v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair-closeout.md`
- Tests under `tests/test_v2_9_8b_window_15m_a_to_z_deterministic_readiness_repair.py` (+ focused proof reuse/extension)

## 7. Hard locks (unchanged)

Solana-only; Solana memecoin-only; paper-only; no live wallet/keys/signing/funds/execution; no paid API; no scoring/ranking/confidence/weighted logic; no embeddings/vectors; no Source Governor or Central Scheduler bypass; `WINDOW_5M_MICRO_EVENT` support-only; no multi-hour production windows; no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/trades/audits/PnL; no automatic retry/restart/recovery/successor; no real authorization; no live provider call; no authoritative DB mutation.

## 8. Explicit non-goals

- No real `WINDOW_15M` authorization or live campaign
- No merge to `master`
- No tag
- No weakening of prior unified-repair proofs
- PASS does not authorize a live run; next step after PASS is independent read-only readiness review

## 9. Implementation sequence

1. Confirm blockers (this design)  
2. Implement R1–R5  
3. Targeted tests  
4. Exact full-path controlled proof  
5. Closeout + commit only on full PASS  
6. Push repair branch only  
