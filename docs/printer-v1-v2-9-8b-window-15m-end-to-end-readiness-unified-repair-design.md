# Printer V1 — V2-9.8B `WINDOW_15M` End-to-End Readiness Unified Repair Design

**Date:** 2026-08-05  
**Design status:** Approved  
**Audit basis:** `docs/printer-v1-window-15m-a-to-z-operational-readiness-audit-2026-08-05.md`  
**Code baseline:** `7a4152bb90b14317513bb10879ee3861410270c7`  
**Audited branch:** `agent/v2-9-8b-pre-authorization-migration-ledger-drift-guard`

## 1. Verdict

`V2_9_8B_WINDOW_15M_END_TO_END_READINESS_UNIFIED_REPAIR_DESIGN_PASS`

This design authorizes one coordinated implementation-and-proof lane to repair every deterministic blocker confirmed by the A-to-Z audit. It is not four independent repair lanes and it does not authorize another live or authoritative `WINDOW_15M` run.

## 2. Roadmap alignment

The design is aligned with the active V2 source stack because:

- the audit/readiness step is complete;
- this design is the required specification step;
- implementation is limited to proven V2-9.8B operational blockers;
- proof is disposable, frozen-source and controlled-clock only;
- closeout is required before any new authorization;
- no retrieval, paper decision, position, trade, PnL, wallet, paid source, score, ranking, confidence, embedding or vector capability is added.

The failed campaign and post-incident authoritative DB remain preserved as terminal evidence. They are not cleanup targets.

## 3. Goal

Make the ordinary public `WINDOW_15M` path capable of reaching a truthful, exact, current-run clean-memory outcome without:

1. deterministic adapter/transport construction failures after mutation;
2. a missing mirror fallback path;
3. misleading zero source-call or unknown mutation reporting;
4. promotion of unrelated historical windows;
5. conflating lifecycle completion with clean-memory success.

## 4. Unified architecture

### 4.1 One concrete-composition readiness boundary

Keep `assert_runtime_dependency_preflight()` as the preflight authority. Add one focused module that supplies the exact ordinary `WINDOW_15M` builder specifications and shared runtime validators.

Recommended new module:

`src/printer_v1/operator_cli/window_15m_concrete_composition.py`

Required responsibilities:

- enumerate every default transport/adapter factory reachable by ordinary `WINDOW_15M` operation;
- construct each with fixed syntactically valid sample identities and zero I/O;
- reject `None`, disabled adapters, missing transports, wrong source names or wrong request-kind contracts;
- expose the same validators for runtime factory outputs;
- return bounded non-secret readiness facts with `external_requests=0` and `database_writes=0`.

Recommended interfaces:

```python
class ConcreteCompositionError(RuntimeError): ...


def require_concrete_transport(label: str, transport: object) -> object: ...


def require_concrete_adapter(
    label: str,
    adapter: object,
    *,
    expected_source_name: str,
) -> object: ...


def window_15m_preflight_builders(
    *,
    timeout_seconds: float,
) -> tuple[tuple[str, Callable[[], object]], ...]: ...
```

The one-shot wrapper must run the same zero-I/O guard after exact child-interpreter selection and migration-ledger review, but before staging, canonical application directory, manifest, application marker or child launch. The wrapper must prove its executing interpreter is the same repository-venv interpreter selected for the child; it must not launch a second probe child. A block therefore leaves the authorization unconsumed.

`build_activation_preflight()` must rerun the same builders as the final child defense before campaign identity, execution artifacts, supervision, heartbeat, source work or DB mutation.

Transport/factory objects that can be constructed without I/O must be resolved before campaign creation. Runtime market data is not pre-proven; only the executable composition is.

### 4.2 Repair both unknown-liquidity fallback directions

Modify the existing opposite-source backup owner. Do not add another adapter or source owner.

Required behavior:

- DexScreener-origin `LIQUIDITY_UNKNOWN` uses the existing GeckoTerminal token-pools transport builder when no factory is injected;
- GeckoTerminal-origin `LIQUIDITY_UNKNOWN` uses the existing DexScreener mint/batch transport builder when no factory is injected;
- a supplied factory is invoked once and its result is validated before adapter construction;
- one opposite-source attempt remains the maximum;
- exact mint/pool identity and categorical failure outcomes remain unchanged;
- no retry, provider rotation, score, rank or paid endpoint is added.

Apply the shared validator to other injected `WINDOW_15M` factory seams that can return unusable dependencies, including snapshot primary/fallback and pre-close context adapters. Existing valid defaults stay unchanged.

### 4.3 Action-local terminal truth

Add one read-only terminal-truth helper rather than another ownership table.

Recommended new module:

`src/printer_v1/operator_cli/action_local_terminal_truth.py`

Recommended interfaces:

```python
@dataclass(frozen=True)
class ActionLocalBaseline:
    database_identity: Mapping[str, object]
    table_counts: Mapping[str, int]
    bounded_row_fingerprints: Mapping[str, Mapping[str, str]]


def capture_action_local_baseline(...) -> ActionLocalBaseline: ...


def build_action_local_terminal_truth(
    db_path: str | Path,
    *,
    baseline: ActionLocalBaseline,
    execution_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    supervision_id: str | None,
    first_terminal_cause: str,
) -> dict[str, object]: ...
```

The helper must reuse existing campaign ownership, stage evidence, request manifests, Source Governor rows and external-operation evidence.

It must report:

- all action-attributable source request IDs;
- response, failure and measured transport counts;
- fresh transport, proven zero-transport reuse and projection-only categories;
- DB identity before/after;
- table deltas and insert/update/terminalization classifications where deterministically provable;
- `UNKNOWN_NOT_ATTRIBUTABLE` where exact classification is impossible;
- campaign/run/cycle/supervision cleanup state;
- first terminal cause unchanged.

The public exception envelope must use this report. It must not use the holder ledger as the sole source-call authority and must never report zero when durable attributable source work exists.

### 4.4 Explicit current-window promotion scope

Extend the existing Lane K pipeline; do not create a second clean-memory writer.

Required compatible interface:

```python
def run_e2z_pipeline(
    db_path: str | Path | None,
    *,
    operator_approved: bool = False,
    production_mode: bool = False,
    candidate_window_ids: Sequence[int] | None = None,
) -> dict[str, Any]: ...
```

Rules:

- `candidate_window_ids=None` preserves the existing explicit global/backlog behavior;
- an explicit list is normalized to unique positive IDs and becomes the complete write scope;
- E2X eligibility is intersected with that scope;
- Lane Q, Lane U2, quality downgrade and E2Z writes operate only on scoped IDs;
- explicit operational scope does not run a global E2Y query as authority; E2Y is `NOT_APPLICABLE_EXPLICIT_WINDOW_SCOPE` or similarly explicit;
- report requested, eligible, blocked, promoted and already-existing IDs;
- report exact episode IDs and existing fingerprint linkage from the canonical fingerprint owner;
- no unrelated window, episode, fingerprint or coverage row may change.

`_execute_close()` must call the pipeline with the exact newly closed `window_id`.

If fingerprint creation is owned by a separate existing canonical module, wire that owner after E2Z. Do not invent a second fingerprint schema or writer.

### 4.5 Two independent success verdicts

Preserve `CAMPAIGN_PASS` as lifecycle/accounting/cleanup truth.

Add to the canonical terminal report:

```text
operational_lifecycle_pass
clean_memory_outcome_pass
clean_memory_outcome
```

`clean_memory_outcome` must include:

- expected current-run `WINDOW_15M` IDs;
- E2Q-clean-candidate, dirty/audit-only and blocked window IDs;
- exact window status/quality/data-quality and `do_not_train` state;
- episode and fingerprint IDs;
- exact window/token/pair linkage;
- unrelated promotion count;
- categorical blocker reasons.

A normal live campaign may legitimately have `operational_lifecycle_pass=true` and `clean_memory_outcome_pass=false`. The final integrated repair proof passes only when both are true.

## 5. Primary files

Expected new files:

- `src/printer_v1/operator_cli/window_15m_concrete_composition.py`
- `src/printer_v1/operator_cli/action_local_terminal_truth.py`

Expected modified files:

- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py` only if the existing builder-preflight result contract needs extension
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/discovery/eligible_token_supply.py` only for exact factory threading
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py`
- `src/printer_v1/operator_cli/full_run_window_15m_accounting.py`
- the canonical existing fingerprint owner if required

Do not broadly restructure these modules. Use the smallest changes that satisfy the complete design.

## 6. Verification

### 6.1 Focused tests

Create or extend focused tests for:

1. concrete composition preflight PASS with all defaults;
2. wrapper-level composition failure blocks before staging/marker/child and leaves the authorization unconsumed;
3. every required builder raising or returning `None` blocks before campaign identity and DB mutation;
4. DexScreener → GeckoTerminal backup exactly once;
5. GeckoTerminal → DexScreener backup exactly once;
6. invalid injected factory output blocks before backup-stage writes;
7. exception after a fresh request reports exact request/response/failure/transport truth;
8. retained evidence reuse is reported as zero-transport reuse, not a new provider call;
9. reserve mutation and terminal cleanup appear in the action-local inventory;
10. explicit E2Z scope cannot mutate unrelated eligible historical windows;
11. lifecycle PASS and clean-memory PASS remain independent.

### 6.2 Exact integrated proof

Use one disposable Migration-052 DB and the exact public coordinator → authoritative owner → origin driver → real factory composition.

Required proof semantics:

- `proof_mode=False`;
- `operational_persistent_mode=True`;
- ordinary `fifteen_minute_only` path;
- controlled clock with `_window_seconds=900.0`;
- no wall-clock wait;
- patch only authoritative-path identity and frozen provider transports in the test;
- do not remap the lifecycle to proof-only mode;
- patched raw outbound network count is zero.

Positive node must prove:

- four fresh unique memory-observation-eligible reserve candidates;
- two selected plus two alternates;
- two exact token slots;
- expected Scheduler cadence with two terminal current-run 15-minute windows;
- both evidence spans `>=900s`;
- both source windows `WINDOW_CLOSED`, E2Q-audited, `PARTIAL_MEMORY`, `CLEAN_DATA`, `do_not_train=0`;
- exactly two current-run `CLEAN_MEMORY` episodes, one per source window;
- canonical fingerprint linkage present;
- zero unrelated historical promotion;
- exact source and mutation truth;
- `operational_lifecycle_pass=true`;
- `clean_memory_outcome_pass=true`;
- zero active/locked residue;
- cleanup and lease release;
- zero forbidden capability deltas;
- report-only replay performs zero source calls and zero writes and is stable.

Negative node must inject one required builder returning `None` and prove:

- preflight BLOCKED;
- no campaign/config/run/cycle/supervision identity;
- no source request;
- no Scheduler work;
- no DB mutation;
- no authorization or live wrapper is involved.

## 7. Acceptance and closeout

Implementation verdict:

- `V2_9_8B_WINDOW_15M_END_TO_END_READINESS_UNIFIED_REPAIR_PASS`, or
- `V2_9_8B_WINDOW_15M_END_TO_END_READINESS_UNIFIED_REPAIR_BLOCKED`

Required closeout:

`docs/printer-v1-v2-9-8b-window-15m-end-to-end-readiness-unified-repair-closeout.md`

The closeout must include:

- money-usefulness contribution;
- exact files and interfaces changed;
- focused test results;
- integrated positive and negative proof results;
- source, Scheduler, DB and forbidden-table deltas;
- what remains locked;
- what this repair still does not guarantee;
- Functionality Risks / Setbacks / Efficiency Blockers;
- full commit SHA and clean tracked worktree state.

## 8. Stop conditions

Stop BLOCKED without committing if:

- baseline HEAD differs;
- the repair requires a live provider call or authoritative DB write;
- a second source/Scheduler/memory owner is needed;
- an exact action-local fact would need to be fabricated;
- unrelated historical promotion cannot be prevented;
- controlled 900-second proof requires changing operational semantics;
- any retrieval or financial table changes;
- any 1h/4h/12h/24h capability is activated;
- tests expose a separate architectural blocker outside this design.

After all focused and integrated nodes pass, run one final repository-approved broad regression suite because this is a multi-module closeout. Do not expand scope for unrelated pre-existing failures; document them exactly.

## 9. What this design does not unlock

No new authorization, live run, authoritative DB mutation, 1h/4h operation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallet, signing, funds, paid APIs, scores, rankings, confidence, embeddings or vectors.
