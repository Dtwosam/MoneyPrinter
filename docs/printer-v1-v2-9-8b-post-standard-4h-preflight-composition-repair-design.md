# Printer V1 — Post-Standard-4H Preflight Composition Repair Design

## Verdict

`V2_9_8B_POST_STANDARD_4H_PREFLIGHT_COMPOSITION_REPAIR_DESIGN_PASS`

The repair is approved as a narrow two-boundary production correction. It does not change source budgets, holder policy, discovery/selection law, cadence, Scheduler ownership, memory quality, 4h barrier semantics, one-shot authorization, later-window locks, retrieval, decisions, or paper-financial capability.

Controlling audit:

`docs/printer-v1-v2-9-8b-post-standard-4h-preflight-composition-repair-scope-audit.md`

Consumed incident closeout:

`docs/printer-v1-v2-9-8b-standard-four-hour-consumed-preflight-runtime-closeout.md`

## 1. Problem being repaired

The first authorized standard 15m->1h->4h campaign consumed its one-shot authorization and stopped at factory preflight with `SAFE_STOP_PREFLIGHT_FAILED` before either `WINDOW_15M` lifecycle stage could start.

The repair-scope audit proved two adjacent defects:

1. `AuthoritativeLiveOperationalCampaignOwner.run_operational()` unconditionally injects the historical `operational_natural_disposition=True` lifecycle option even when `standard_four_hour_campaign=True`.
2. If that legacy flag is merely removed, `run_one_command_15m_factory()` still routes the standard campaign through the generic historical `continuous_first_hour` fallback that requires exactly one autonomous token, contradicting the standard campaign's exact two-token requirement.

A one-line flag deletion is therefore insufficient.

## 2. Design principle

Standard four-hour is its own explicit production authority.

It must not inherit any historical proof/disposition authority merely because it reuses the same lifecycle machinery.

Mode partition at the factory boundary must be explicit:

```text
STANDARD_FOUR_HOUR_CAMPAIGN
  -> exact persistent two-token standard path
  -> standard first-hour continuation
  -> standard 4h barrier

OPERATIONAL_NATURAL
  -> historical natural two-token behavior

COMPRESSED_TWO_TOKEN_PROOF
  -> historical proof behavior

PLAIN_CONTINUOUS_FIRST_HOUR
  -> historical one-token autonomous proof behavior
```

These modes remain mutually exclusive where their contracts conflict.

## 3. Production change A — live owner mode-scoped disposition

File:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

Current behavior:

- caller-supplied `compressed_two_token_proof_plan` and `operational_natural_disposition` are correctly rejected;
- the owner then unconditionally writes `operational_natural_disposition=True`.

Required behavior:

- preserve rejection of caller-supplied proof/disposition keys;
- when `standard_four_hour_campaign=False`, preserve the existing operational-natural behavior exactly by injecting `operational_natural_disposition=True`;
- when `standard_four_hour_campaign=True`, do not inject operational-natural disposition authority;
- do not substitute `four_hour_proof_mode`, compressed proof plans, or any other historical authority.

Preferred implementation shape:

```python
if not standard_four_hour_campaign:
    lk["operational_natural_disposition"] = True
```

The standard path therefore reaches the driver/factory with the dedicated standard authority only.

## 4. Production change B — factory preflight mode partition

File:

`src/printer_v1/operator_cli/one_command_15m_factory.py`

The existing dedicated `if standard_four_hour_campaign:` preflight checks remain authoritative and must be preserved:

- persistent operational mode required;
- `four_hour_proof_mode=False`;
- historical compressed/natural dispositions excluded;
- exactly two token slots;
- standard first-hour continuation required;
- continuous four-hour required;
- exact campaign ownership identities required;
- existing global owner/budget/integrity/capability checks remain intact.

The later generic `if continuous_first_hour:` historical-shape branch must not reinterpret a valid standard campaign as a one-token proof.

Required ordering:

```text
if continuous_first_hour:
    if standard_four_hour_campaign:
        # dedicated standard checks already own the shape
        # do not apply historical natural/compressed/one-token shape rules
        pass
    elif compressed_two_token_proof_plan is not None:
        existing compressed proof checks
    elif operational_natural_disposition:
        existing operational-natural checks
    elif max_selected_tokens != _CONTINUOUS_MAX_SELECTED_TOKENS:
        existing one-token proof rejection

    existing mutually incompatible V2-5 proof check still applies
```

Do not widen `_CONTINUOUS_MAX_SELECTED_TOKENS` from 1 to 2. That would silently change historical one-token proof semantics.

Do not make `standard_four_hour_campaign` count as `_two_token_lifecycle()` merely to satisfy old compressed/natural budget logic. Standard campaigns already have their own cumulative standard-four-hour budget path and 4h barrier.

## 5. Explicit non-changes

Do not modify:

- `standard_four_hour_one_shot_wrapper.py`;
- Git-provenance authorization profiles;
- authorization validity/non-reuse semantics;
- holder candidate ceiling, holder fallback, or holder budget behavior;
- discovery/selection admission;
- Source Governor or Central Scheduler ownership;
- 15m/1h/4h cadence;
- standard 1h->4h eligibility;
- standard 4h handoff/barrier;
- long-window request/Scheduler ceilings;
- memory quality/audit/promotion logic;
- `WINDOW_5M_MICRO_EVENT` support-only law;
- `WINDOW_12H` / `WINDOW_24H` locks;
- retrieval or paper-financial surfaces.

## 6. TDD requirements

Implementation begins RED.

At minimum add tests that fail on the current baseline for both defects:

### RED A — live owner standard mode does not inherit natural authority

Exercise `AuthoritativeLiveOperationalCampaignOwner.run_operational()` through a production-shaped offline dependency-injected path and prove:

- ordinary operational mode still reaches the driver with `operational_natural_disposition=True`;
- standard-four-hour reaches the driver with standard authority and without operational-natural disposition authority.

### RED B — factory accepts exact standard two-token preflight shape

Exercise the actual factory preflight with the standard configuration:

- `standard_four_hour_campaign=True`;
- persistent operational mode;
- `continuous_first_hour=True`;
- `selective_1h_continuation=True`;
- `continuous_four_hour=True`;
- `four_hour_proof_mode=False`;
- `max_selected_tokens=2`;
- no historical disposition/proof plan;
- exact campaign/run/cycle/config identities.

The current baseline must fail specifically because the generic one-token continuous-first-hour rule still applies.

After implementation, the same case must pass that preflight boundary.

### Negative regressions

Prove unchanged fail-closed behavior for:

- ordinary operational-natural mode without required natural disposition;
- operational-natural two-token mode without terminal 4h proof mode;
- compressed proof and operational-natural disposition mixed together;
- standard campaign plus operational-natural disposition;
- standard campaign plus `four_hour_proof_mode=True`;
- standard campaign with one or three selected tokens;
- standard campaign missing required campaign ownership identities;
- standard campaign with V2-5 three-token proof mode.

## 7. Focused offline production-shaped proof

After GREEN, run only minimum sufficient directly affected proof:

1. new repair tests;
2. existing standard-four-hour final-public-wiring tests;
3. existing standard-four-hour factory-barrier tests;
4. existing standard-four-hour operational-activation tests;
5. authoritative live operational campaign regression tests directly covering ordinary natural behavior;
6. a production-shaped offline composition path that reaches:
   - factory-run creation;
   - both first `WINDOW_15M` lifecycle stage plans;
   - no source network calls beyond injected fixtures;
   - no authoritative live DB mutation;
   - no 4h/12h/24h live collection.

Do not run a broad repository suite merely for this narrow repair. A broader standard-4h/checkpoint suite belongs at the repair closeout/pre-live rereadiness gate if the focused proof is clean.

## 8. Acceptance gate

Implementation/proof may close PASS only if all are true:

- standard-four-hour does not inherit `operational_natural_disposition`;
- standard exact two-token configuration passes factory preflight;
- ordinary operational-natural behavior is unchanged;
- historical one-token continuous-first-hour behavior remains one-token;
- invalid mixed configurations still fail closed;
- standard campaign reaches factory-run and both first-15m stage plans offline;
- no source-budget/holder/Scheduler/DB/memory-quality law is weakened;
- no later capability is unlocked.

If any additional production defect appears after this preflight boundary, stop and classify it separately rather than broadening this repair silently.

## Money-usefulness contribution

This repair lets Printer reach the already-designed continuous first-four-hour observation path instead of spending one-shot authority on a deterministic configuration contradiction. It improves the system's ability to collect trustworthy longer-horizon learning evidence. It does not prove profitability or authorize any paper action.

## What this lane improves

- clean separation of standard production authority from historical proof/natural disposition modes;
- exact two-token standard preflight semantics;
- preservation of ordinary historical behavior;
- a production-shaped proof gap that the previous 145/145 isolated suite missed.

## What this lane still does not unlock

- no new live/source run;
- no fresh authorization;
- no automatic rerun/successor of the consumed attempt;
- no 12h/24h collection;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions/trades/audits/PnL;
- no wallet/private key/signing/real funds/live execution;
- no paid APIs;
- no scoring/ranking/confidence/weighted decision logic;
- no embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Removing the natural flag globally would regress ordinary operational mode; the change must be standard-mode scoped.
- Widening the generic continuous-first-hour token count would weaken historical proof semantics; standard mode must be a separate branch.
- Reclassifying standard mode as compressed/natural two-token lifecycle could corrupt budget/accounting semantics; keep the dedicated standard budget path.
- Source-inspection-only tests are insufficient because they previously missed the exact composed runtime shape.
- Passing preflight may expose a later independent defect; if so, stop and classify rather than masking it.
- Another live proof before offline composition proof and fresh rereadiness would risk consuming a second authorization unnecessarily.

## Next permitted lane

`V2-9.8B Post-Standard-4H Preflight Composition Repair Implementation + Focused Offline Proof`

Implementation must begin with RED and remain offline/proof-bounded. No authorization or provider runtime is authorized by this design.