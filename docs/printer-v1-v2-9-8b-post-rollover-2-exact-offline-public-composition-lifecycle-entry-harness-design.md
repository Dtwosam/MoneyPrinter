# Printer V1 V2-9.8B Post-Rollover-2 Exact Offline Public Composition Lifecycle-Entry Harness Design

Date: 2026-08-03

Baseline: `9f2163bbeb7f6a79d66de655a5bcedd077cb1422`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_EXACT_OFFLINE_PUBLIC_COMPOSITION_LIFECYCLE_ENTRY_HARNESS_DESIGN_PASS`

Classification implemented by this design:

```text
TEST_ONLY_DEPENDENCY_INJECTION_REQUIRED
```

## Design objective

Provide the smallest lawful offline exact-composition lifecycle entry that
preserves the full public chain:

```text
public coordinator
  → authoritative campaign owner
  → real discovery and two-slot activation
  → OriginToLifecycleCampaignDriver
  → real run_one_command_15m_factory
  → two compressed WINDOW_15M closes
  → strict accounting
  → campaign acceptance
```

on a disposable Migration-050 database with frozen transports, without
weakening production preflight or touching the authoritative corpus.

## Selected seam

### Existing production ports (unchanged)

| Port | Owner | Role |
| --- | --- | --- |
| `AuthoritativeLiveOperationalCampaignOwner(driver=…)` | production | DI for origin driver |
| `OriginToLifecycleCampaignDriver(lifecycle_runner=…)` | production | DI for lifecycle factory |
| `run_one_command_15m_factory(..., proof_mode=…, operational_persistent_mode=…)` | production | lawful disposable proof entry already exists |

### Harness-only remapper (new, tests only)

```text
offline_exact_public_composition_lifecycle_entry(db_path, backup_path, **kwargs)
  → force:
       proof_mode=True
       operational_persistent_mode=False
       continuous_first_hour=False
       continuous_four_hour=False
       four_hour_proof_mode=False
       operational_natural_disposition=False
  → call real run_one_command_15m_factory(db_path, backup_path, **kwargs)
```

Wiring:

```text
_ExactPublicCompositionOwner(
  driver=OriginToLifecycleCampaignDriver(
    lifecycle_runner=offline_exact_public_composition_lifecycle_entry,
  ),
  …frozen snapshot/context/timing…
)
```

### Why this is the smallest valid boundary

1. Public coordinator and owner stay real and unchanged.
2. Discovery, secondary contract, and two-slot activation stay real.
3. Driver stays real; only its already-supported `lifecycle_runner` is supplied.
4. Factory stays real; only entry flags are remapped to the existing disposable
   proof contract.
5. No production preflight rule, corpus constant, or public CLI mode is added or
   weakened.

## Exact lifecycle-entry contract

| Surface | Offline exact harness value | Ordinary public operational default |
| --- | --- | --- |
| Public coordinator | used | used |
| Authoritative owner | used | used |
| `fifteen_minute_only` at owner API | `True` (public path) | `True` |
| Lifecycle factory `proof_mode` | **`True` (remapped)** | `False` |
| Lifecycle factory `operational_persistent_mode` | **`False` (remapped)** | `True` |
| Continuous 1h / 4h | `False` | `False` |
| `operational_natural_disposition` at factory | **`False` (remapped)** | `True` |
| Database | disposable Migration-050 | `CANONICAL_PERSISTENT_DB` |
| Transports | frozen fixtures | live |
| Timing | compressed proof-only params | real wall clock |
| Scheduler | real enqueue/claim/terminal | real |
| Six-unit accounting | real strict path | real |
| Campaign acceptance | real gate | real |

### fifteen_minute_only proof equivalent

Public `fifteen_minute_only` semantics required by this proof:

1. exactly two selected tokens;
2. only `WINDOW_15M` lifecycle closes (no 1h/4h continuation unlock);
3. compressed timing only through existing `_window_seconds` /
   `total_duration_seconds` proof parameters.

Those semantics are preserved by keeping continuous/4h flags false and using
the standard two-token disposable proof factory path. They are **not**
preserved by forcing `operational_persistent_mode=True` on a disposable DB;
that is an incorrect harness choice and is rejected by production preflight.

`operational_natural_disposition` must be cleared for disposable proof entry
because factory preflight couples operational-natural 15m-only to operational-
persistent mode (authoritative corpus). Clearing it is harness-only and does
not change the owner’s live force-True default.

## Production defaults preserved

Ordinary public operational use remains:

```text
proof_mode=False
operational_persistent_mode=True
authoritative corpus required
operational_natural_disposition=True
fifteen_minute_only=True
```

Invariants:

- Remapper is defined only in the offline exact composition test module.
- Public CLI and non-test owners never install the remapper.
- Factory preflight strings and corpus checks are unmodified.
- `CANONICAL_PERSISTENT_DB` is unmodified and never patched by this design.
- Operational-persistent + non-canonical path continues to safe-stop.

## Implementation owners (allowed)

| Owner | Change |
| --- | --- |
| `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py` | Install DI lifecycle_runner remapper on the exact owner |
| New focused harness proof module | Deterministic coverage of the 15 required surfaces |
| Four lane documents | Audit/design/implementation/focused-proof record |

## Explicit non-owners (locked)

Do not modify:

- production preflight rules;
- `CANONICAL_PERSISTENT_DB`;
- Scheduler implementation or claim/ownership law;
- Source Governor;
- six-unit accounting;
- schema or migrations;
- discovery/secondary contracts;
- authorization;
- retry/restart/resume/successor behavior;
- downstream capability locks;
- ordinary public CLI entry points.

## Focused proof design

Create focused tests (not the exact node) proving:

1. Ordinary public 15m operational mode still requires the authoritative corpus.
2. Disposable DB + operational-persistent mode still safe-stops with the exact
   reason string.
3. Approved offline composition path enters lifecycle in proof mode
   (`db_mode=PROOF_ONLY` or factory preflight pass with proof flags).
4. Public coordinator and authoritative owner are not bypassed (call/chain
   evidence).
5. Origin driver receives the same two activated slots.
6. Lifecycle factory uses the disposable DB lawfully (path is temp DB; not
   canonical).
7. Exactly two compressed `WINDOW_15M` lifecycles can complete under the remapped
   entry.
8. Scheduler transitions are real (jobs terminal; no active/locked residue).
9. Strict accounting remains unchanged (handoff validations / zero financial).
10. Campaign acceptance can evaluate the completed proof.
11. No live provider/RPC/WebSocket calls (`urlopen` uncalled; frozen transports).
12. No authoritative DB is opened or mutated.
13. No retry, restart, resume, or successor occurs.
14. All retrieval and financial surfaces remain zero.
15. Previous `SAFE_STOP_PREFLIGHT_FAILED` case remains covered as a negative test.

Run only directly affected suites. Do **not** run
`test_exact_public_coordinator_owner_driver_factory_composition` in this lane.

## Money-usefulness contribution

The design isolates a test-only DI remapper so offline composition can prove
real two-window memory-factory completion without ever authorizing production
to treat a disposable DB as the authoritative corpus. That keeps money-useful
proofs honest while preserving the operational safety stop that protects live
data.

## What improves

- Exact offline composition has a lawful lifecycle entry.
- Harness defect is repaired without production risk.
- Negative preflight coverage remains explicit.

## What remains locked

All capability locks listed in the audit remain locked. The exact composition
node remains unauthorized until a later explicit authorization.

## Proof performed / required

Design is source-grounded against the audited owners. Implementation must ship
the remapper + focused suite, compile changed Python, pass `git diff --check`,
and record focused counts. Exact composition remains unexecuted.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Mitigation |
| --- | --- |
| Remapper could be copied into production by mistake | Keep it in tests only; no production import |
| Forgetting to clear operational-natural | Remapper forces False; focused test asserts preflight matrix |
| Future owner changes bypass driver DI | Focused test constructs owner with explicit driver= |
| Exact node still may fail for unrelated reasons | Out of scope; this lane only proves lifecycle entry |
| Application-level network assertion | Same boundary as prior exact family; not packet capture |
