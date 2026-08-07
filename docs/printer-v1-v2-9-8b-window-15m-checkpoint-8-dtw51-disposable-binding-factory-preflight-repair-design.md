# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-51 Disposable Binding Factory Preflight Repair Design

Date: 2026-08-07

Linear: `DTW-51`

Audit commit: `fdfc33c6a88519e0fe3676bfada44b60255e6786`

Baseline HEAD: `da49a81769362c9fc4cc53a4e3e246f7180323a4`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW51_DISPOSABLE_BINDING_FACTORY_PREFLIGHT_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Design decision

Propagate the already-validated C8 `disposable_public_composition_proof_binding` from the authoritative owner through the lifecycle driver into `run_one_command_15m_factory()` preflight, and accept that exact disposable binding as the sole non-corpus operational-persistent alternative for C8 disposable composition.

Do **not**:

- fabricate a production `OperationalDatabaseTargetBinding`;
- remap C8 into proof-mode via the offline remapper as a substitute;
- accept arbitrary non-canonical DBs;
- weaken production corpus/production-binding law;
- change Source Governor, Scheduler, budgets, six-unit accounting, holder law, or reconciliation.

## Canonical owner (unchanged)

Binding continues to be created only by:

`_build_disposable_public_composition_owner_bridge()`
→ `build_disposable_public_composition_proof_binding()`

Owner bridge remains:

```text
operational_database_target_binding = None
disposable_public_composition_proof_binding = <validated binding>
```

No second binding constructor.

## Minimum propagation seam

### Seam A — Authoritative owner → driver

In `AuthoritativeLiveOperationalCampaignOwner` lifecycle handoff, forward the already-held disposable binding into the driver:

```text
disposable_public_composition_proof_binding=disposable_public_composition_proof_binding
```

alongside the existing:

```text
operational_database_target_binding=operational_database_target_binding
```

Flags remain C8-ordinary:

```text
proof_mode = not fifteen_minute_only
operational_persistent_mode = fifteen_minute_only
```

### Seam B — Driver → factory

Extend `OriginToLifecycleCampaignDriver.run()` with optional:

```text
disposable_public_composition_proof_binding: Any | None = None
```

Pass it unchanged into `run_one_command_15m_factory(...)`.

### Seam C — Factory preflight acceptance

Extend `run_one_command_15m_factory()` with optional:

```text
disposable_public_composition_proof_binding: Any | None = None
```

Under `operational_persistent_mode=True`, replace the “None binding ⇒ corpus required” short-circuit with this ordered law:

1. **If** `operational_database_target_binding is not None`  
   → keep existing production `validate_bound_operational_invocation(...)` unchanged.

2. **Elif** `disposable_public_composition_proof_binding is not None`  
   → load durable expectation from configuration (already written as disposable expectation) **or** rebuild expectation only from the same binding via `build_disposable_public_composition_proof_expectation()` when durable load is the disposable expectation shape;  
   → validate with existing `validate_disposable_public_composition_proof_invocation(...)` using the same ownership inputs the outer owner uses;  
   → on validation failure, append the returned reason (fail closed);  
   → on success, **do not** emit the corpus reason.

3. **Else**  
   → retain exact current behavior:  
     `operational persistent mode requires the authoritative corpus` when `path != canonical`,  
     then production missing-binding validation.

Hard constraints for branch 2:

- must reject canonical DB (`DISPOSABLE_PROOF_CANONICAL_DB_FORBIDDEN` already exists);
- must not invent authorization markers;
- must not call production binding validation against a disposable expectation;
- must not accept a disposable binding when a production binding is also supplied in conflicting ways (production binding remains precedence if non-null).

## What remains fail-closed without repair scope expansion

| Path | Required outcome after repair |
|------|-------------------------------|
| Production non-canonical DB, no production binding, no disposable binding | Still `authoritative corpus` / binding-missing stop |
| Production binding present | Unchanged production validation |
| Disposable binding present but mismatched path/sha/ownership | Disposable validation reason; still stop |
| Disposable binding absent | Unchanged corpus rule |

## Secondary terminal `run_id` packaging

**Out of primary DTW-51 implementation scope.**

Reason: frozen evidence proves packaging occurs after the real stop and did not cause factory preflight failure.

Optional follow-up (separate commit/lane unless implementation is trivially free and tests already touch the terminal surface):

- add top-level `run_id=command.run_id` to the `run_operational_campaign` terminal payload;
- and/or teach harness identity extraction to accept `report["identity"]["run_id"]` only if that remains exact and non-ambiguous.

Do not block the primary binding repair on packaging.

## Approved implementation file manifest

Production (primary):

1. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
2. `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
3. `src/printer_v1/operator_cli/one_command_15m_factory.py`

Proof:

4. `tests/test_v2_9_8b_window_15m_checkpoint8_disposable_binding_factory_preflight.py`  
   (new focused DTW-51 regression)

No other production file may change in the primary implementation commit.

Owner-bridge construction, disposable expectation builder, and disposable validators remain reused as-is unless a pure call-site wiring fix proves a tiny helper extraction is required inside the three production files above.

## Deterministic RED

At audit/design baseline, focused offline regression must show:

1. a valid disposable binding passes outer `_validate_fifteen_minute_database_target_binding()`;
2. under C8-mapped flags (`operational_persistent_mode=True`, `proof_mode=False`) with disposable DB and `operational_database_target_binding=None`, factory preflight returns:
   - `run_status=SAFE_STOPPED`
   - `stop_reason=SAFE_STOP_PREFLIGHT_FAILED`
   - blocked reason contains `operational persistent mode requires the authoritative corpus`
3. factory run count remains `0`.

RED classification:

`DTW51_DISPOSABLE_BINDING_LOST_BEFORE_FACTORY_PREFLIGHT_RED_CONFIRMED`

## GREEN acceptance

Primary:

1. Same disposable binding, once propagated into factory preflight, does **not** emit the corpus reason solely due to dropped binding.
2. Factory preflight either:
   - accepts the disposable binding and proceeds past this specific corpus gate, **or**
   - stops for an unrelated later lawful reason that is not corpus-missing-from-dropped-binding.
3. Production negative remains: disposable DB + operational-persistent + no bindings still emits corpus reason.
4. Production binding path remains intact (no behavior change when production binding is supplied).
5. `py_compile` of changed modules.
6. dedicated DTW-51 regression green.
7. existing C8 real-consumer compatibility remains green.
8. focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` suite remains green.
9. exact approved-file manifest.
10. `git diff --check` clean.
11. zero provider/network attempts in fixture proof.

Minimum sufficient offline proof is the above. No controlling C8 proof is authorized by this design.

## Money-usefulness contribution

Restores the only lawful disposable path by which Checkpoint 8 can enter the already-proven factory lifecycle after pilot-input readiness, without weakening production database-target law. This is necessary before clean 15-minute memory can be proven on the ordinary public composition.

## What remains locked

- no controlling C8 proof;
- no operational WINDOW_15M memory growth;
- no WINDOW_1H+;
- no retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL;
- no provider/network execution;
- no authoritative corpus mutation.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Factory must not treat disposable expectation as production expectation (`OPERATIONAL_DATABASE_TARGET_EXPECTATION_V1` vs disposable expectation version).
2. Production precedence must remain: non-null production binding wins and keeps production law.
3. Do not “fix” by remapping C8 to proof_mode offline entry; that would hide the ordinary fifteen-minute contract under test.
4. A later C8 attempt remains one-shot and separately authorized only after offline closeout + independent readiness.
5. Secondary terminal `run_id` packaging can still break harness `report_only` wiring after a future PASS candidate if left unfixed; track separately.

## Implementation readiness

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW51_READY_FOR_OFFLINE_IMPLEMENTATION`

Stop before implementation. No C8 re-proof is authorized.
