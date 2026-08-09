# Printer V1 V2-9.8B Post-DTW99 `build_graduated_supply` Temporal Owner Interface Repair Design

## Verdict

`V2_9_8B_POST_DTW99_BUILD_GRADUATED_SUPPLY_TEMPORAL_OWNER_INTERFACE_REPAIR_DESIGN_PASS`

## Scope

Design only. This document specifies the narrowest repair that closes the
`PRODUCTION_COMPOSITION_INTERFACE_FORWARDING_GAP` established by the DTW99
consumed-attempt audit closeout. No production code is modified by this lane.

The repair is one parameter and one forwarded argument. Nothing else.

## Defect being closed

```text
authoritative_live_operational_campaign.py:2514  supply_kwargs["temporal_refresh_owner"] = owner
authoritative_live_operational_campaign.py:2517  build_graduated_supply(..., **supply_kwargs)
graduated_supply_front_door.py:767               def build_graduated_supply(...)   # parameter absent
graduated_supply_front_door.py:882               run_persistent_eligible_token_supply(...)  # not forwarded
eligible_token_supply.py:653                     temporal_refresh_owner: Any | None = None   # already declared
```

## Repair specification

### 1. Declare the parameter

In `src/printer_v1/operator_cli/graduated_supply_front_door.py`, add to the
`build_graduated_supply` signature:

```python
temporal_refresh_owner: Any | None = None,
```

Keyword-only (it falls after the existing `*`), defaulting to `None`, typed to
match the lower-level declaration at `eligible_token_supply.py:653` exactly. Place
it adjacent to `campaign_source_request_scope` at the end of the existing
keyword block so the diff stays minimal and no existing parameter moves.

### 2. Forward it unchanged

In the existing `run_persistent_eligible_token_supply(...)` call at
`graduated_supply_front_door.py:882`, add exactly one argument:

```python
temporal_refresh_owner=temporal_refresh_owner,
```

Passed through by reference, unwrapped, unwrapped-again, uncopied, unadapted and
unvalidated. The front door must not inspect the owner, call any method on it,
substitute a default, or construct one. It is a conduit.

### 3. Nothing else changes

No new owner type, discovery engine, retry path, source, selector, scheduler
rule, migration or capability. No new module, no new constant, no new evidence
field, no signature change to any other function, and no change to
`run_persistent_eligible_token_supply` itself — it already declares the parameter
and needs no edit.

### 4. Default `None` behaviour preserved

Every existing caller that does not pass `temporal_refresh_owner` continues to
bind `None` and reach the identical downstream behaviour it has today. The
lower-level service already guards on `if temporal_refresh_owner is not None:`
(`eligible_token_supply.py:1190`) and `if temporal_refresh_owner is None or
acquisition_ledger is None:` (line 1233), so a `None` owner takes the existing
non-temporal path unchanged. Legacy and non-operational callers are unaffected.

### 5. Invariants preserved unchanged

- 900-second pre-lifecycle acquisition horizon:
  `discovery/pre_lifecycle_temporal_acquisition.py:37`
  `PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = 900` — not touched.
- Cumulative 30-operation discovery budget:
  `discovery/eligible_token_supply.py:78`
  `DEFAULT_DISCOVERY_OPERATION_BUDGET = 30` — not touched.
- The `deadline_at` computation at `authoritative_live_operational_campaign.py:2508`
  already binds correctly and is not modified.
- 600-second refresh cadence and the one-refresh-opportunity envelope are owned by
  the temporal refresh owner and are not touched.

## Why this is the correct altitude

The lower level already declares the parameter. The caller already sends it. Only
the intermediate front door is missing the pass-through. Adding the parameter to
the front door is therefore a restoration of an already-designed contract, not a
new capability. Any wider change — a new owner abstraction, a retry path, a
budget adjustment — would exceed the proven defect and would need its own audit.

## Required proof design

The implementation lane must add a focused regression that binds against the
**real `build_graduated_supply` boundary**. A `**kwargs` stub is explicitly
disallowed as the primary mechanism, because that is exactly what concealed the
defect at
`tests/test_v2_9_8b_post_dtw98_temporal_persistence_completion.py:307`.

The regression must prove:

1. **No `TypeError` at the real boundary.** The production caller can pass a
   non-null temporal owner through `build_graduated_supply` without
   `TypeError`. Asserting against the genuine signature — via
   `inspect.signature(build_graduated_supply).bind(...)` and/or a real call — is
   what makes this proof load-bearing.
2. **Exact object identity forwarded.** The object received by
   `run_persistent_eligible_token_supply` is the *same object* the caller passed,
   asserted with `is` (identity), not `==` (equality). Equality would pass for a
   copy or a re-wrapped adapter and would not prove pass-through.
3. **Default `None` backward compatibility.** Calling `build_graduated_supply`
   without `temporal_refresh_owner` still binds `None` downstream, and the
   existing non-temporal path is unchanged.
4. **Zero source calls.** The interface proof needs no provider I/O. The
   lower-level service may be substituted to capture the forwarded argument, but
   the *front door under test* must remain real.
5. **Zero authoritative DB mutation.** The proof must not open the authoritative
   database for writing. Any database need is served by a disposable SQLite file.
6. **Affected temporal-persistence tests remain green**, including the
   post-DTW98 completion, ratification and bounded-proof tests.
7. **No broad suite run** unless a focused failure requires widening.

### Additional recommendation

The completion test's `fake_build_graduated_supply(db_path, **kwargs)` stub should
be tightened so it can no longer silently absorb an undeclared keyword — for
example by binding the captured kwargs against the real
`inspect.signature(build_graduated_supply)` before accepting them. This is
recorded as a recommendation of the design; the load-bearing requirement is
proof item 1, which does not depend on it.

## Explicitly out of scope

Implementation, the regression itself, rereadiness, a fresh authorization,
wrapper invocation, Printer runtime and WINDOW_15M all remain future lanes. This
design creates no execution permission.

## Locks retained

All V1 locks remain binding: Solana-only, Solana memecoin-only, paper-only, no
live wallet, no private keys, no real funds, no live execution, no paid API
dependency, no scoring/ranking/confidence/weighted decisions, no embeddings or
vectors, no Source Governor or Central Scheduler bypass, and no retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, paper trade audits or PnL before
explicit approved lanes. `WINDOW_5M_MICRO_EVENT` remains support-only.
WINDOW_1H/4H/12H/24H remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Closing this seam does not prove eligible supply. The 3-of-4 reserve shortage
  that motivated the temporal-persistence repair remains unproven, and the next
  authorized attempt can still honestly exhaust.
- The same `**supply_kwargs` splat remains a general blind spot for any future
  keyword; this repair fixes one parameter, not the pattern.
- The next authorization must bind the post-DTW99 database identity
  `d896e03e99cff954caa8f9f936f28926481ea4ed57f4a875b1189757cef9a9ab`, not the
  consumed pre-attempt binding.
- A green focused regression is not a WINDOW_15M operational pass.

## Next lane

`V2-9.8B Post-DTW99 build_graduated_supply Temporal Owner Interface Repair
Implementation and Focused Proof`.
