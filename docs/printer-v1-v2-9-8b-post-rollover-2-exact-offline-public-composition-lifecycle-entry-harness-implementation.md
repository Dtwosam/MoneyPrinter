# Printer V1 V2-9.8B Post-Rollover-2 Exact Offline Public Composition Lifecycle-Entry Harness Implementation

Date: 2026-08-03

Baseline: `9f2163bbeb7f6a79d66de655a5bcedd077cb1422`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_EXACT_OFFLINE_PUBLIC_COMPOSITION_LIFECYCLE_ENTRY_HARNESS_IMPLEMENTATION_PASS`

Classification:

```text
TEST_ONLY_DEPENDENCY_INJECTION_REQUIRED
```

## Implemented contract

The exact offline public-composition harness installs a **test-only** lifecycle
runner on the real `OriginToLifecycleCampaignDriver` through the existing owner
`driver=` dependency-injection port.

```text
public coordinator
  → AuthoritativeLiveOperationalCampaignOwner (real)
  → OriginToLifecycleCampaignDriver (real)
  → offline_exact_public_composition_lifecycle_entry (test remapper)
  → run_one_command_15m_factory (real)
```

Remapper forces:

| Flag | Value |
| --- | --- |
| `proof_mode` | `True` |
| `operational_persistent_mode` | `False` |
| `continuous_first_hour` | `False` |
| `continuous_four_hour` | `False` |
| `four_hour_proof_mode` | `False` |
| `operational_natural_disposition` | `False` |

Rationale for clearing `operational_natural_disposition`: factory preflight
couples operational-natural 15m-only to operational-persistent mode, which
requires the authoritative corpus. Clearing it is the smallest lawful
disposable proof equivalent of two compressed `WINDOW_15M` closes only.

## Files changed

| File | Purpose |
| --- | --- |
| `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py` | DI lifecycle-entry remapper on exact owner |
| `tests/test_v2_9_8b_exact_offline_public_composition_lifecycle_entry_harness.py` | Focused deterministic coverage of the 15 required surfaces |
| audit / design / implementation / focused-proof docs | Lane record |

## Production defaults preserved

Ordinary public operational use is unchanged:

```text
proof_mode=False
operational_persistent_mode=True
authoritative corpus required
operational_natural_disposition=True
fifteen_minute_only=True
```

- No production source files modified.
- `CANONICAL_PERSISTENT_DB` unmodified and unpatched by this implementation.
- Factory preflight strings and corpus checks unmodified.
- Public coordinator still hard-codes `fifteen_minute_only=True`.
- Authoritative owner still maps that flag to operational-persistent + natural.

Focused proof shows the owner still **emits** public operational flags into the
driver; only the harness remapper converts them for disposable entry.

## Exact lifecycle-entry contract (implemented)

1. Public coordinator and authoritative owner remain on the path.
2. Real origin driver and lifecycle factory remain on the path.
3. Disposable Migration-050 DB only.
4. `proof_mode=True`, `operational_persistent_mode=False`.
5. Two-token, 15m-only semantics via continuous/4h flags false and natural
   cleared for disposable proof entry.
6. Frozen snapshot/context transports and compressed proof-only timing retained
   by the existing exact owner overrides.
7. Real Scheduler enqueue/claim/terminal transitions.
8. Strict six-unit accounting and campaign acceptance unchanged.
9. No authoritative corpus open/mutate; no live network.

## Money-usefulness contribution

Offline composition can now lawfully complete the public discovery → activation
→ two owned `WINDOW_15M` → accounting → acceptance chain on a disposable DB.
That proves money-useful memory-factory completion without risking the live
corpus or weakening production operational-persistent safety.

## What improves

- Exact harness no longer collides with the operational-persistent corpus
  preflight when using a disposable Migration-050 database.
- Production corpus preflight remains the hard stop for non-proof operational use.
- Prior `SAFE_STOP_PREFLIGHT_FAILED` harness defect is covered as a permanent
  negative test.

## What remains locked

Production preflight, `CANONICAL_PERSISTENT_DB`, Scheduler law, Source Governor,
six-unit accounting, schema/migrations, discovery/secondary contracts,
authorization, retry/restart/resume/successor, retrieval, decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, funds, paid
APIs, scoring/ranking/confidence/weights, embeddings, vectors, and the exact
public-composition node execution (requires separate authorization).

## Proof performed / required

Implementation is covered by the focused suite in the companion focused-proof
document. The exact public-composition node was **not** executed.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Disposition |
| --- | --- |
| Remapper lives only in tests | Intentional; cannot activate from ordinary public CLI |
| Owner still forces operational-natural before remapper | Expected; remapper clears it for disposable proof entry |
| Exact composition outcome still unknown until authorized run | Correct stop condition for this lane |
| Application-level `urlopen` patch | Same zero-network boundary as prior exact family |
