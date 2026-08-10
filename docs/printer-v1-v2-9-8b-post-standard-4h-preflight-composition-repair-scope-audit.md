# Printer V1 V2-9.8B Post-Standard-4H Preflight Composition Repair-Scope Audit

## Verdict

`V2_9_8B_POST_STANDARD_4H_PREFLIGHT_COMPOSITION_REPAIR_SCOPE_AUDIT_PASS_TWO_BOUNDARY_DEFECTS_DESIGN_REQUIRED`

The consumed standard 15m -> 1h -> 4h attempt exposed a deterministic production composition defect at the live-owner -> factory preflight seam.

Read-only static inspection confirms **two separate but adjacent preflight defects**:

1. `AuthoritativeLiveOperationalCampaignOwner.run_operational()` unconditionally injects the historical `operational_natural_disposition=True` flag even when `standard_four_hour_campaign=True`, although the standard-four-hour factory contract explicitly rejects that historical disposition.
2. Even if that legacy flag were merely omitted, `run_one_command_15m_factory()` would still enter its generic `continuous_first_hour` preflight branch and fall through to the historical one-autonomous-token rule. Standard-four-hour requires exactly two token slots, so a one-line live-owner fix alone would expose a second deterministic preflight failure.

Therefore the next design must treat standard-four-hour as its own explicit production mode at **both** boundaries:

- live-owner lifecycle-option construction; and
- factory preflight mode classification.

No evidence justifies changing source budgets, holder budgets, discovery/selection, cadence, Source Governor, Central Scheduler, the standard 1h->4h barrier, memory quality, or downstream capability locks.

This audit performed no source fetch, provider call, Scheduler/runtime execution, authoritative DB mutation, memory generation, authorization preparation/application, retrieval, paper decision, position, trade, audit, or PnL work.

## Baseline and authority

Audit branch:

`agent/v2-9-8b-post-standard-4h-preflight-composition-repair-audit`

Parent durable state:

- consumed runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- active-anchor update: `19f33d79e710710695bb212565e9da746b880deb`;
- consumed launch HEAD: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`.

Active source stack reviewed:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-assistant-active-build-order-anchor.md`.

Just-in-time controlling standard-four-hour sources reviewed:

- `docs/printer-v1-v2-9-8b-standard-four-hour-consumed-preflight-runtime-closeout.md`;
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`;
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-activation-wide-integration-proof-closeout.md`;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`;
- `src/printer_v1/operator_cli/one_command_15m_factory.py`;
- `src/printer_v1/operator_cli/operational_standard_4h.py`;
- directly affected standard-four-hour and historical operational-natural tests.

The active V2 completion pattern remains:

```text
audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout
```

No step here authorizes implementation or another operational attempt.

## 1. Consumed incident remains correctly classified

The consumed authorization:

`V2_9_8B_STANDARD_4H_AUTH_20260810T220717Z`

is permanently non-reusable.

The consumed runtime reached governed discovery/protocol/holder work and exact two-token handoff, then safe-stopped with:

`SAFE_STOP_PREFLIGHT_FAILED`

before a factory run or current-run `WINDOW_15M` memory window was created.

Terminal cleanup returned active work to zero. No retry, rerun, resume, restart, or successor occurred.

The prior closeout classification remains correct:

`COMMITTED_CODE_DEFECT`

This audit narrows that classification from one visible contradiction to the complete two-boundary preflight defect set.

## 2. Defect A — live owner injects a forbidden historical disposition

Current live-owner behavior:

1. copies `lifecycle_kwargs`;
2. sets `standard_four_hour_campaign=True` when that mode is requested;
3. rejects caller-supplied `compressed_two_token_proof_plan` and `operational_natural_disposition` keys;
4. then unconditionally writes:

```python
lk["operational_natural_disposition"] = True
```

5. forwards those lifecycle options through the origin->lifecycle driver.

That unconditional injection made sense for the historical V2-9.7E operational-natural lifecycle, but it is no longer valid for the dedicated standard-four-hour production authority.

The factory standard-four-hour preflight explicitly requires:

- operational persistent mode;
- `four_hour_proof_mode=False`;
- exactly two token slots;
- standard first-hour continuation;
- `continuous_four_hour=True`;
- exact campaign ownership identities; and
- **no historical proof disposition**, including `operational_natural_disposition`.

The live owner therefore manufactures a configuration the receiving standard-four-hour preflight is designed to reject.

### Audit conclusion for Defect A

Confirmed committed-code defect.

The design lane should make legacy natural-disposition injection **mode-scoped**, preserving it for existing non-standard operational behavior while preventing it from entering the dedicated standard-four-hour path.

This audit does not approve the final code shape yet.

## 3. Defect B — generic continuous-first-hour preflight still assumes the historical one-token shape

Removing Defect A alone is insufficient.

`run_one_command_15m_factory()` separately validates `standard_four_hour_campaign=True` and correctly requires exactly two token slots.

Later in the same preflight it evaluates generic `continuous_first_hour` mode:

- compressed two-token proof gets its historical branch;
- operational-natural gets its historical two-token branch and requires terminal 4h proof mode;
- otherwise the factory requires `_CONTINUOUS_MAX_SELECTED_TOKENS`, currently one token.

A correct standard-four-hour configuration has:

```text
standard_four_hour_campaign = True
continuous_first_hour = True
selective_1h_continuation = True
continuous_four_hour = True
four_hour_proof_mode = False
max_selected_tokens = 2
operational_natural_disposition = False
compressed_two_token_proof_plan = None
```

With the legacy natural flag removed, that exact configuration still reaches the generic fallback and receives:

`continuous first-hour proof requires exactly one autonomous token`

Therefore standard-four-hour lacks an explicit exemption/branch in the generic continuous-first-hour proof-shape classifier.

### Audit conclusion for Defect B

Confirmed committed-code defect at the same factory preflight boundary.

The design lane must ensure that once the dedicated standard-four-hour contract has validated its exact two-token production shape, historical proof-shape fallback rules are not reapplied to it.

The fix must not weaken those historical rules for their actual modes.

## 4. Runtime after preflight is already mode-distinct

Static inspection does **not** justify a broad runtime rewrite.

After a successful preflight, current code already contains explicit standard-four-hour ownership:

- public policy carries `standard_four_hour_campaign=True` and distinct bounded ceilings;
- the coordinator threads that flag into the live owner and lifecycle kwargs;
- standard mode uses operational persistent authority rather than `four_hour_proof_mode`;
- first-hour machinery is campaign-owned and two-slot aware;
- ordinary historical long-4h proof planning is guarded with `not standard_four_hour_campaign`;
- after `CONTINUATION_CLOSE`, standard mode calls `run_standard_four_hour_campaign_barrier()`;
- that barrier uses `FourHourExecutionAuthority.STANDARD_CAMPAIGN` and the standard campaign handoff planner;
- standard long-window budget calculation reads the durable eligibility manifest;
- `WINDOW_12H` and `WINDOW_24H` remain locked.

Accordingly, the current repair should stop at the preflight/composition seam unless focused proof reveals a separate downstream defect.

## 5. Public wrapper/policy are not the repair target

`operational_memory_factory_command.py` already defines a dedicated standard-four-hour policy:

- mode: `standard-four-hour-run`;
- policy version: `V2-9.8-STANDARD-4H-OPERATIONAL-V1`;
- post-supply duration: `14_700` seconds;
- pre-lifecycle duration: `900` seconds;
- governed request ceiling: `230`;
- per-token ceiling: `114`;
- Scheduler-row ceiling: `210`;
- `continuous_four_hour=True`;
- `standard_four_hour_campaign=True`;
- locked windows: `WINDOW_12H`, `WINDOW_24H`.

The standard one-shot wrapper and authorization profile are also distinct from ordinary `WINDOW_15M` operation.

No audit evidence shows that those contracts caused the stop.

Do not broaden the repair into wrapper/authorization redesign.

## 6. Holder budget is not part of the repair

The consumed run observed:

`HOLDER_CONTEXT_BUDGET_EXHAUSTED`

but the holder owner correctly treats permanent memory-observation exhaustion as bounded context truth:

- remaining candidates may become `SOURCE_NOT_EVALUATED_BUDGET_BOUND`;
- holder condition remains unknown/blocked for future action;
- memory observation is not re-gated on holder pass;
- no automatic budget increase is implied.

The consumed run then reached two-token selection/handoff, proving holder budget exhaustion was not the preflight root cause.

No holder ceiling, provider fallback, source count, or safety policy should change in this repair.

## 7. Why the prior wide integration proof missed the defect

The prior wide integration closeout reported 145/145 directly exercised tests PASS and remains valid historical evidence for the slices it actually exercised.

However, its broad statement that the standard public/live-owner/factory route composed end-to-end is superseded at one precise seam by the consumed runtime evidence and this audit.

The current test structure explains the escape:

### Final public wiring tests

`tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_final_public_wiring.py` mainly proves:

- policy constants;
- read-only preflight projection;
- wrapper dispatch;
- source/signature presence through `inspect.getsource`;
- mocked `_run_operational_campaign` routing.

It verifies that the standard flag is threaded, but not the exact set of lifecycle arguments that finally reaches factory preflight.

### Factory barrier tests

`tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_factory_barrier.py` starts from a prepared disposable DB with first-hour state already present and exercises the downstream 1h->4h barrier directly.

It does not traverse live-owner option construction or the initial factory preflight.

### Historical operational-natural tests

`tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py` strongly covers ordinary operational-natural behavior and explicitly rejects caller injection of the legacy disposition, but its historical production path expects the owner itself to supply natural semantics.

That coverage is important regression protection, but it does not prove the newer standard-four-hour exception.

### Test-gap conclusion

The missing proof is a production-shaped **offline seam test** that traverses:

```text
standard public policy
-> live owner
-> origin/lifecycle driver
-> run_one_command_15m_factory preflight
```

with the exact standard flags together.

## 8. Affected-caller/configuration map

| Surface | Current role | Audit disposition |
|---|---|---|
| `operational_memory_factory_command.py` | Dedicated public standard policy and coordinator | Preserve; not root defect |
| `standard_four_hour_one_shot_wrapper.py` | One-use standard authorization/application boundary | Preserve; not root defect |
| `authoritative_live_operational_campaign.py` | Builds lifecycle options and currently injects legacy natural disposition | **Repair target** |
| `origin_lifecycle_campaign.py` | Forwards lifecycle options into factory | Preserve unless design proves a normalization owner belongs here; current forwarding is truthful |
| `one_command_15m_factory.py` | Validates mode shape and owns initial lifecycle factory | **Repair target** |
| `operational_standard_4h.py` | Standard 1h->4h barrier and exact production 4h authority | Preserve; downstream distinction already correct |
| `one_token_4h_runtime.py` | Shared 4h planning/close primitives and standard subset budget | Preserve absent new proof failure |
| holder reliability/budget owners | Bounded holder context | Preserve |
| Source Governor / Scheduler owners | External request and work authority | Preserve |

## 9. Minimum design scope

The next design should specify exactly two production behavior changes.

### A. Live-owner mode ownership

Define standard-four-hour as excluded from historical operational-natural disposition injection while preserving existing ordinary/non-standard behavior.

The design must state the exact caller matrix:

- ordinary operational 15m: unchanged;
- historical operational-natural path: unchanged;
- selective-1h path: unchanged unless the design proves redundant natural metadata can be removed without behavioral change;
- standard-four-hour path: dedicated standard authority only; no historical disposition.

### B. Factory preflight classification

Define standard-four-hour as a first-class two-token production branch so the generic historical continuous-first-hour one-token fallback does not re-reject a configuration already validated by the standard contract.

Historical invalid combinations must remain fail-closed:

- standard + `four_hour_proof_mode=True`;
- standard + compressed proof plan;
- standard + operational-natural disposition;
- standard with token capacity other than two;
- standard without standard first-hour continuation;
- standard without `continuous_four_hour`;
- standard without exact campaign ownership identities.

No implementation is authorized by this audit.

## 10. Minimum sufficient proof required after implementation

Use risk-based verification, not a broad repository suite.

Required focused proof:

1. **RED before repair:** exact standard production-shaped offline composition reaches factory preflight and reproduces the current contradictory blocker set.
2. **GREEN after repair:** the same composition passes factory preflight and reaches factory-run creation plus both first-15m lifecycle stage plans without source/network access.
3. Confirm exact standard configuration at the factory boundary:
   - `standard_four_hour_campaign=True`;
   - `continuous_first_hour=True`;
   - `selective_1h_continuation=True`;
   - `continuous_four_hour=True`;
   - `four_hour_proof_mode=False`;
   - `max_selected_tokens=2`;
   - no compressed proof plan;
   - no operational-natural disposition.
4. Ordinary operational-natural regression remains unchanged.
5. Invalid mixed standard/proof/natural combinations still fail closed.
6. Existing standard barrier/subset tests remain green.
7. No Source Governor, Central Scheduler, holder, cadence, memory-quality, 5m, 12h/24h, retrieval, decision, or financial lock changes.

A broad/full suite is not required for the narrow implementation itself. Broader directly affected standard-four-hour regression belongs at repair closeout/pre-live rereadiness.

## 11. Money-usefulness contribution

This audit prevents another one-shot authorization from being consumed on a deterministic configuration contradiction.

Repairing the exact production seam allows Printer to spend bounded source/Scheduler capacity on actual 15m->1h->4h observation rather than failing before the first main window starts.

That can improve future corpus usefulness by collecting real full-four-hour trajectories, but it does not prove profitability and does not authorize any paper action.

## 12. What this lane improves

- identifies the complete two-boundary preflight defect rather than only the first visible flag conflict;
- narrows production repair to the smallest justified ownership/preflight surfaces;
- preserves already-proven downstream standard 4h barrier and accounting work;
- explains why the prior broad test suite missed the production seam;
- defines the exact missing production-shaped offline proof.

## 13. What this lane still does not unlock

- no implementation;
- no source/provider call;
- no Scheduler/runtime execution;
- no authoritative DB mutation;
- no memory generation;
- no fresh authorization;
- no rerun/resume/restart/successor of the consumed attempt;
- no `WINDOW_12H` or `WINDOW_24H` activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL;
- no live wallet, private keys, signing, live execution, or real funds;
- no paid API dependency;
- no scoring/ranking/confidence/weighted logic;
- no embeddings/vectors.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Required control | Proof before closeout |
|---|---|---|---|
| Fix only the live-owner flag | Exposes the second one-token preflight blocker | Design both boundaries together | RED/GREEN exact production-shaped preflight |
| Broadly remove operational-natural semantics | Could regress historical ordinary lifecycle behavior | Mode-scoped change only | Historical operational-natural regression |
| Loosen standard factory validation | Could admit proof/disposition drift into production | Preserve exact standard invalid-combination rejects | Negative preflight matrix |
| Rewrite downstream 4h barrier unnecessarily | Expands risk into already-proven ownership/accounting code | Keep repair at preflight seam | Diff-scope check + barrier regression |
| Increase holder/source budgets | Treats an incidental bounded condition as root cause | No budget changes | Configuration diff check |
| Rely again on source-inspection-only tests | Could miss actual argument composition | Add production-shaped offline seam test | Exact boundary values asserted at runtime |
| Run another live proof too early | Could consume another authorization on deterministic code | Offline proof and closeout first | Repair closeout + fresh rereadiness |
| Treat prior 145/145 proof as worthless | Discards valid downstream evidence and creates unnecessary rebuild | Supersede only the unproven seam claim | Audit map preserves proven slices |

## Closeout

Audit result:

`PASS — MINIMAL TWO-BOUNDARY DESIGN REQUIRED`

Production files justified for the next design/implementation consideration:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
- `src/printer_v1/operator_cli/one_command_15m_factory.py`.

No other production change is justified by current evidence.

Next permitted lane:

`V2-9.8B Post-Standard-4H Preflight Composition Repair Design`

That lane is design/specification only. It must not create a fresh authorization or run Printer.
