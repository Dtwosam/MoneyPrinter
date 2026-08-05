# Printer V1 V2-9.8B WINDOW_15M Retained-Evidence Exactness Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_RETAINED_EVIDENCE_EXACTNESS_REPAIR_PASS`

This is an implementation and isolated-test closeout only. No proof ran, no
authorization was created or consumed, no provider was contacted, no discovery
or Scheduler runtime ran, and the authoritative database was not opened or used
by tests.

## Baseline and final commit

- Required branch baseline:
  `agent/v2-9-8b-window-15m-memory-activation-clean-object-integrity-repair`
- Required / starting HEAD:
  `71880828787607d69fd982698c417d2297260583`
- Baseline ancestry: verified with `git merge-base --is-ancestor`.
- Starting tracked worktree: clean.
- Repair branch:
  `agent/v2-9-8b-window-15m-retained-evidence-exactness-repair`
- Final commit:
  `ee9231a266d9533bb22e1f8fd0c2ddc131f48ba9`
  (`Repair WINDOW_15M retained evidence exactness`).
- Python environment: repository `.venv`.
- No active Printer/database process or authoritative-database handle was found
  before or after implementation.

## Files changed

Implementation:

- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

Tests:

- `tests/test_v2_9_8b_window_15m_retained_evidence_exactness_repair.py` (new)
- `tests/test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair.py`

Documents:

- this closeout

No migration was added.

## Confirmed blockers and disposition

### 1. Per-reference transport identity coverage can be empty

**Disposition: repaired.** Successful retained references now require at least one
exact transport identity. Empty keys raise
`RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING`. Typed manifest entries carry the
exact owned key set; count-only acceptance is rejected.

### 2. Transport keys were not bound to exact request/manifest stage and count

**Disposition: repaired.** `ManifestRequestEntry` and coverage rows now carry
`transport_identity_keys` owned by the request and logical stage. Validation
requires:

- exact source name and request kind when declared on the entry;
- exact logical stage ID;
- identity count equal to `transport_identity_count`;
- no key shared across unrelated request IDs;
- no source-name / request-kind-only fallback;
- campaign/run/cycle ownership validated against the current activation command
  and stage prefix, not only values copied from the reference.

The same-kind fallback in `_build_frozen_memory_activation_set` was removed.

### 3. Production contract carried only `MARKET_OBSERVATION`

**Disposition: repaired.** Each selected candidate must carry exact references for
`ORIGIN_LINEAGE`, `PUMPSWAP_CONFIRMATION`, and `MARKET_OBSERVATION`. Each role
preserves original request/response/hash/transport/source/kind/time/mint/pool
and campaign/run/cycle stage. Origin-verification and PumpSwap-confirmation
projection rows cite retained role request/response IDs, hashes and transport
keys in durable `evidence_detail`. Missing role evidence blocks before handoff.
No synthetic source rows are created.

### 4. Runtime source-row reconciliation returned assumed empty deltas

**Disposition: repaired.** `measure_source_row_ids` captures exact request,
response and failure ID sets before retained projection and after the atomic
two-slot handoff. `reconcile_activation_source_rows` reports before/after IDs,
newly created IDs, referenced manifest IDs, per-role request IDs,
missing/unmanifested IDs, request-to-transport binding results and final status.
PASS requires zero newly created source request, response or failure IDs.
Hard-coded empty deltas are no longer returned as a success authority.

### 5. Durable channel and selection-reason described the legacy selector

**Disposition: repaired.** For `MEMORY_OBSERVATION` mode:

- selection reason is exactly `memory_observation_frozen_selection`;
- true provenance is persisted as channel/provenance authority
  (`true_provenance` / `channel_authority`);
- observation channel labels remain in the lawful CHANNELS vocabulary and are
  mapped from provenance, never from slot ordinal;
- readiness ID, selection seed, slot ordinal, mint and pool are persisted in
  retained observation evidence;
- reports no longer claim `_select()` or uniform selection ran for memory mode.

Legacy non-memory modes keep `uniform:{seed}` selection reason and their
selector.

### 6. Tracking exclusion evidence stored holder facts under tracking_handoff

**Disposition: repaired.** Tracking assessment is persisted under
`tracking_handoff` with eligible, reason code, category, queue ID/status,
requalification-required, cooldown and assessed time. Holder facts remain under
a separate `holder_safety` field. Tracking admission rules are unchanged.

## Focused tests and results

Disposable temporary databases only.

| # | Requirement | Result |
|---|---|---|
| 1 | Empty per-reference transport identities block | PASS |
| 2 | Key belonging to another request blocks | PASS |
| 3 | Same-source/same-kind ambiguity blocks | PASS |
| 4 | Transport identity count mismatch blocks | PASS |
| 5 | Wrong logical stage blocks | PASS |
| 6 | Wrong campaign/run/cycle ownership blocks | PASS |
| 7 | All three evidence roles mandatory | PASS |
| 8 | Each role preserves exact request/response/hash/transport | PASS |
| 9 | Origin and PumpSwap projection cite retained role refs | PASS |
| 10 | Activation creates zero source requests/responses/failures | PASS |
| 11 | Runtime pre/post reconciliation is measured | PASS |
| 12 | Frozen slot order unchanged | PASS |
| 13 | Durable selection reason is `memory_observation_frozen_selection` | PASS |
| 14 | Durable provenance not derived from slot ordinal | PASS |
| 15 | Tracking exclusion evidence is assessment, not holder facts | PASS |
| 16 | Holder fail/unknown remains valid memory context | PASS |
| 17 | Atomic clean-object tests remain green | PASS |
| 18 | Legacy non-memory behavior remains unchanged | PASS |
| 19 | Capability locks remain unchanged | PASS |

Commands/results:

- Focused exactness + integrity suite: `35 passed`.
- Directly affected regressions (exactness, integrity, freeze/holder budget,
  campaign manifest evidence, remaining runtime blocker): `84 passed in 55.72s`.
- Python compilation of changed modules: PASS.
- `git diff --check` on changed implementation/test files: PASS.

## Per-role source and transport reconciliation

For each selected candidate the contract now requires:

| Role | Durable surfaces |
|---|---|
| `ORIGIN_LINEAGE` | source request/response IDs, hash, transport keys, source/kind, time, mint/pool, campaign/run/cycle; cited on origin-verification projection |
| `PUMPSWAP_CONFIRMATION` | same surfaces; cited on pumpswap-confirmation projection |
| `MARKET_OBSERVATION` | same surfaces; projected as retained provider observation |

Manifest entries own exact `transport_identity_keys` and
`transport_identity_count` for each request and logical stage. Cross-request key
sharing and count mismatch fail closed.

## Measured pre/post source-row deltas

Runtime path:

1. measure source request/response/failure ID sets before retained projection;
2. project retained evidence without `_governed_request` / `_store_response`;
3. measure again after atomic two-slot handoff;
4. reconcile; non-zero newly created IDs block.

Focused tests prove both measured zero-delta PASS and illicit new-request BLOCKED
paths without hard-coded empty success.

## Durable selection and provenance evidence

Memory mode persists:

- `selection_reason = memory_observation_frozen_selection` on selection batch items;
- `true_provenance` and `channel_authority` from the frozen candidate;
- `readiness_id`, `selection_seed`, `slot_ordinal`, mint and pool on retained
  observation factual payload;
- frozen selected order into slots 1 and 2 without `_select()`.

## Authoritative database identity

Recorded without connecting to the database:

- Path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- Before size: `68067328` bytes
- Before mtime: `2026-08-05T11:18:15+0100`
- Before SHA-256:
  `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb`
- After size: `68067328` bytes
- After mtime: `2026-08-05T11:18:15+0100`
- After SHA-256:
  `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb`

Identity is unchanged. No open handles were observed.

## Money-usefulness contribution

Exact retained-evidence binding makes memory activation auditable: every selected
observation points at real governed request/response/transport facts already
measured during supply, with truthful selection provenance and tracking
exclusion evidence. That prevents false source history and mislabeled selection
authority from contaminating 15-minute clean-memory comparison.

## What remains locked

- No WINDOW_15M authorization or proof.
- No provider contact, discovery runtime, Scheduler runtime or memory generation.
- No redesign of holder-memory separation, neutral freeze selection, atomic
  two-slot handoff, clean episode/fingerprint transaction, E2Q, Lane K or
  clean-object promotion, authorization/database binding, or proof retention
  beyond the direct repairs above.
- Solana-only, memecoin-only, paper-only.
- No 1h/4h/12h/24h production, retrieval, BUY/SELL/HOLD, paper decisions,
  positions, trades, audits, PnL, wallets, signing, funding, paid APIs, scoring,
  ranking, confidence, weighting, embeddings or vectors.
- Source Governor and Central Scheduler ownership unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Activation now requires all three retained evidence roles. Older disposable
  carriers with only market request coverage continue to stop before lifecycle
  with categorical retained-evidence blockers; they are not fabricated into
  success.
- Exact request-to-transport ownership fails closed on ambiguous same-source/
  same-kind manifests without owned keys on the coverage entry.
- Observation channel column remains limited to the lawful CHANNELS vocabulary;
  true provenance is the authority field and is not forced by slot ordinal.
- Production supply still must attach origin and PumpSwap request/response IDs
  and per-request transport keys on coverage for full live activation; missing
  role evidence blocks honestly rather than inventing rows.
- No migration was required or performed.

## Confirmation

No proof ran. No authorization was created or consumed. No provider was
contacted. No discovery or Scheduler runtime ran. No memory was generated. The
authoritative database identity is unchanged.

PASS does not authorize a campaign, provider contact, proof, authorization,
retrieval activation or any financial action. The only next step is an
independent read-only review of this branch, commit and closeout.
