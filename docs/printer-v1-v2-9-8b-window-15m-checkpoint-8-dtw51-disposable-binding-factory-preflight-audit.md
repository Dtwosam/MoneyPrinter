# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-51 Disposable Binding Factory Preflight Audit

Date: 2026-08-07

Linear: `DTW-51`

Parent: `DTW-34`

Baseline HEAD:

`da49a81769362c9fc4cc53a4e3e246f7180323a4`

Consumed proof:

`C8_REPROOF_AFTER_DTW50_20260807`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW51_DISPOSABLE_BINDING_FACTORY_PREFLIGHT_AUDIT_PROVEN`

## Audit scope

Read-only static proof of the complete disposable binding path:

```text
C8 disposable proof binding
→ public composition owner bridge
→ AuthoritativeLiveOperationalCampaignOwner
→ OriginToLifecycleCampaignDriver
→ run_one_command_15m_factory() preflight
```

No implementation, no provider/network work, no controlling proof, and no operational memory activation.

## Frozen runtime evidence (already consumed)

From the frozen post-DTW50 attempt:

- first runtime cause: `SAFE_STOP_PREFLIGHT_FAILED`
- first factory blocked reason class: `operational persistent mode requires the authoritative corpus`
- DTW-50 held: holder request keys under campaign root; pre-lifecycle recon `OK`; transport identity completeness `OK`
- 16 governed requests / 20 transport operations
- two selected slots reached pilot-input readiness
- factory runs/steps/windows: `0`
- cleanup/lease release clean; DB integrity OK / FK 0
- no retry/rerun/resume/restart/successor

## Canonical binding owner

The only lawful C8 disposable binding owner is:

`_build_disposable_public_composition_owner_bridge()`
in `operational_memory_factory_command.py`

It constructs one `DisposablePublicCompositionProofBinding` via
`build_disposable_public_composition_proof_binding()` and places it on:

```text
_DisposablePublicCompositionOwnerBridge.disposable_public_composition_proof_binding
```

It intentionally sets:

```text
operational_database_target_binding = None
```

Production authoritative/authorized bindings remain a separate capability
(`OperationalDatabaseTargetBinding`) and are not used for ordinary C8 disposable composition.

Durable configuration for C8 stores the disposable expectation through
`build_disposable_public_composition_proof_expectation()` under
`operational_database_target_expectation` with:

- `expectation_version = DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_V1`
- `target_kind = DISPOSABLE_PUBLIC_COMPOSITION_PROOF`

That expectation deliberately contains **no** authorization-marker fields.

## Proven path (outer acceptance works)

### 1. Public composition owner

`run_operational_campaign(disposable_proof=...)` builds the owner bridge, validates the disposable binding at campaign construction, and stores the disposable expectation.

### 2. Authoritative owner entry

When `fifteen_minute_only=True`, `AuthoritativeLiveOperationalCampaignOwner` calls
`_validate_fifteen_minute_database_target_binding()`.

That helper:

1. prefers a non-null production `operational_database_target_binding` and validates it with production law;
2. else, if `disposable_public_composition_proof_binding` is present, validates it with
   `validate_disposable_public_composition_proof_invocation()`;
3. else fails closed through production binding-missing law.

**Finding:** outer fifteen-minute binding acceptance already knows the disposable C8 binding and accepts it without treating the disposable DB as the authoritative corpus.

This matches the frozen attempt reaching pilot-input readiness after outer validation.

### 3. Lifecycle handoff (gap begins)

After pre-lifecycle readiness, the owner invokes:

```text
self._driver.run(
    ...
    proof_mode=not fifteen_minute_only,                 # False for C8
    operational_persistent_mode=fifteen_minute_only,    # True for C8
    operational_database_target_binding=operational_database_target_binding,  # None for C8
    lifecycle_kwargs=lk,
)
```

Critical omissions:

- `disposable_public_composition_proof_binding` is **not** an argument of
  `OriginToLifecycleCampaignDriver.run()`;
- it is therefore **not** forwarded into `run_one_command_15m_factory()`;
- only `operational_database_target_binding=None` is forwarded.

### 4. Factory preflight (gap completes)

`run_one_command_15m_factory()` operational-persistent preflight:

```text
if operational_persistent_mode:
    if path != canonical and operational_database_target_binding is None:
        reasons.append(
            "operational persistent mode requires the authoritative corpus"
        )
    validate_bound_operational_invocation(operational_database_target_binding, ...)
```

It has:

- no parameter for `disposable_public_composition_proof_binding`;
- no disposable validation branch;
- no awareness of the already-accepted outer disposable binding.

Therefore for C8 disposable DB + `operational_persistent_mode=True` + binding `None`:

1. first reason: `operational persistent mode requires the authoritative corpus`
2. second reason class from production validation of `None`: `OPERATIONAL_DB_BINDING_MISSING`
   (and/or durable production-expectation mismatch if a disposable expectation is loaded)

Factory returns `SAFE_STOPPED` / `SAFE_STOP_PREFLIGHT_FAILED` before any factory run row, window, or clean-memory work.

## Root cause (exact)

**Contract gap / lost binding propagation, not a Source Governor, budget, holder, or reconciliation defect.**

The already-validated C8 disposable public composition binding is accepted at the outer fifteen-minute owner boundary, then discarded before lifecycle factory preflight. Factory operational-persistent law only accepts:

1. the canonical authoritative corpus, or
2. a non-null production `operational_database_target_binding`.

It never re-validates the disposable binding that C8 already owns.

Classification:

`DTW51_DISPOSABLE_BINDING_LOST_BEFORE_FACTORY_PREFLIGHT`

## What is intentionally not the root cause

- DTW-50 holder request-key scope (held; recon OK)
- transport identity completeness (OK)
- request/transport six-unit accounting counts at pre-lifecycle (16/20 observed)
- cleanup/lease release
- provider/network
- generic desire to weaken factory preflight
- treating disposable DB as production corpus

## Secondary harness packaging fault

Harness post-terminal error:

`CHECKPOINT8_TERMINAL_IDENTITY_MISSING`

Cause:

- `run_operational_campaign()` terminal payload includes `campaign_id` and `execution_id`
- it does **not** include top-level `run_id`
- nested `terminal["report"]` is the `write_campaign_terminal_report()` return surface, which also lacks `run_id`
- durable campaign-report body identity *does* contain `run_id`, but the harness identity extractor does not read `report.identity.run_id`

This fault occurs **after** the real runtime stop and did not cause `SAFE_STOP_PREFLIGHT_FAILED`.

Classification:

`DTW51_SECONDARY_TERMINAL_RUN_ID_PACKAGING_GAP`

Recommendation: keep out of the primary binding-propagation repair unless a one-line identity packaging fix is free of scope expansion. Prefer a separate narrow packaging lane after primary GREEN.

## Existing offline remapper is not a substitute

`tests/test_v2_9_8b_exact_offline_public_composition_lifecycle_entry_harness.py` and
`offline_exact_public_composition_lifecycle_entry()` remap disposable entry to
`proof_mode=True` / `operational_persistent_mode=False`.

The controlling C8 public path does **not** use that remapper. It keeps ordinary
fifteen-minute mapping (`operational_persistent_mode=True`) and therefore depends
on disposable-binding acceptance under operational-persistent factory preflight.

Repair must not replace C8 with a silent mode remapper that bypasses the binding contract.

## Production law that must remain unchanged

1. Ordinary production without disposable binding still requires the authoritative corpus or a valid production `operational_database_target_binding`.
2. Production binding validation and authorization-marker law remain unchanged.
3. No generic non-canonical DB bypass.
4. No fabrication of a production binding from disposable proof facts.
5. No provider/network unlock, no operational memory activation, no WINDOW_1H+, no retrieval/decision/trade surfaces.

## Minimum later repair surface (audit only; not implemented)

Likely files if a design is approved:

1. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
2. `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
3. `src/printer_v1/operator_cli/one_command_15m_factory.py`
4. focused regression test(s) under `tests/test_v2_9_8b_window_15m_checkpoint8_*.py`

Owner-bridge construction already correct; do not invent a second disposable binding owner.

## Deterministic RED required for later implementation

Offline fixture RED must prove:

1. outer `_validate_fifteen_minute_database_target_binding()` accepts a valid disposable binding;
2. lifecycle entry under C8-mapped flags reaches `run_one_command_15m_factory` with disposable binding absent / operational binding `None`;
3. factory preflight therefore emits `SAFE_STOP_PREFLIGHT_FAILED` including
   `operational persistent mode requires the authoritative corpus`;
4. zero factory runs created.

## Focused GREEN required for later implementation

1. With the same validated disposable binding propagated into factory preflight, factory no longer emits the corpus reason solely because disposable binding was dropped.
2. Production corpus/production-binding paths remain fail-closed without disposable binding.
3. No fabricated production binding is created.
4. No network attempts.
5. Optional secondary: terminal packaging includes exact campaign `run_id` only if designed in this lane; otherwise leave secondary open.

## Verdict

The first post-DTW50 controlling blocker is a **proven disposable-binding propagation gap** between outer C8 acceptance and factory operational-persistent preflight.

DTW-51 is justified for a narrow offline repair design and later implementation.

Secondary terminal `run_id` packaging is real but not the runtime stop cause.

## Locks preserved

No C8 re-proof, no operational WINDOW_15M memory growth, no WINDOW_1H+, no retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL are authorized by this audit.
