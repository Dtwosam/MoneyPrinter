# Printer V1 V2-9.8B Post-DTW99 Temporal Owner Interface Repair — Implementation and Focused Proof Closeout

## Verdict

`V2_9_8B_POST_DTW99_BUILD_GRADUATED_SUPPLY_TEMPORAL_OWNER_INTERFACE_REPAIR_IMPLEMENTATION_PROOF_PASS`

## Baseline

- branch: `agent/v2-9-8b-post-dtw99-temporal-owner-interface-repair-implementation`
- starting HEAD: `f45176d8c89ace554f308ce3b5504177848e7457`
- tracked worktree clean at start
- authoritative DB at start: `d896e03e99cff954caa8f9f936f28926481ea4ed57f4a875b1189757cef9a9ab` (post-DTW99)

## What this fixes

The `PRODUCTION_COMPOSITION_INTERFACE_FORWARDING_GAP` that consumed the DTW99
one-use authorization. `build_graduated_supply` did not declare
`temporal_refresh_owner` and had no `**kwargs` catch-all, while the production
caller injected it through `**supply_kwargs` and the lower-level
`run_persistent_eligible_token_supply` already declared it. Python raised
`TypeError` at that seam in `CAMPAIGN_PRE_LIFECYCLE`, before any lifecycle or
provider work.

## Production change

One file, one parameter, one forwarded argument, six inserted lines:

```text
src/printer_v1/operator_cli/graduated_supply_front_door.py | 6 ++++++
1 file changed, 6 insertions(+)
```

1. `build_graduated_supply(...)` gains `temporal_refresh_owner: Any | None = None`
   as the final keyword-only parameter, typed to match the lower-level
   declaration exactly.
2. The existing `run_persistent_eligible_token_supply(...)` call forwards
   `temporal_refresh_owner=temporal_refresh_owner` unchanged, with a comment
   recording why.

`run_persistent_eligible_token_supply` was **not** modified. No other production
behaviour changed. No new owner, discovery engine, retry path, source, selector,
scheduler rule, migration or capability.

## Strict TDD

### RED (on the unmodified production tree)

`tests/test_v2_9_8b_post_dtw99_build_graduated_supply_temporal_owner_interface.py`

```text
8 failed, 2 passed
```

The controlling failure was the exact DTW99 string, reproduced at the real
boundary:

```text
TypeError: build_graduated_supply() got an unexpected keyword argument
           'temporal_refresh_owner'
```

The two passing tests were the pre-existing invariants (900-second horizon,
30-operation budget, lower-level declaration), which were already true and must
stay true — they are guards, not the defect.

### GREEN

```text
10 passed
```

## Proof design honoured

The regression keeps the **real** `build_graduated_supply` under test. It never
replaces the front door with a permissive stub, because a
`fake_build_graduated_supply(db_path, **kwargs)` stub is exactly what hid this
defect at
`tests/test_v2_9_8b_post_dtw98_temporal_persistence_completion.py:307`.

Only the *lower-level* service is substituted, so the forwarded argument can be
captured — and that substitute validates every call against
`inspect.signature(run_persistent_eligible_token_supply)` before accepting it, so
it cannot absorb an undeclared keyword the way the DTW98 stub did.

Proved:

1. the real signature declares `temporal_refresh_owner`, keyword-only, default
   `None`, with no `**kwargs` catch-all, and binds a non-null owner without
   `TypeError`;
2. the **same object** arrives at the supply service, asserted with `is`; a
   companion test proves an equal-but-distinct object is *not* accepted as
   identity, so the proof cannot pass on equality alone;
3. omitting the argument forwards `None`; passing `None` explicitly forwards
   `None`;
4. zero provider/source calls — the injected `migration_transport` is never
   invoked (asserted call count `0`);
5. no database is opened at all. `permanent_availability` defaults to `False`, so
   the front door reaches the supply boundary without connecting; the test asserts
   its `db_path` and even its parent directory are never created. The
   authoritative database is never referenced.

## Focused verification

| Suite | Result |
| --- | --- |
| New DTW99 interface regression | `10 passed` |
| `post_dtw98_temporal_persistence_completion` | passed |
| `post_dtw98_pre_lifecycle_temporal_persistence` | passed |
| `post_dtw98_temporal_persistence_bounded_proof` | passed |
| `pre_lifecycle_readiness_artifact_and_auth_gate` | passed |
| `v2_9_8b_21_eligible_token_supply_architecture` | passed |
| `v2_9_7e_44_full_pilot_supply_integration` | 2 pre-existing failures |
| `end_to_end_pre_lifecycle_failure_propagation` | 1 pre-existing failure |

Aggregate across the focused set: `48 passed` + `57 passed` + `10 passed`, with
three failures.

### Pre-existing failures — not introduced by this change

All three were reproduced on the unmodified starting tree by stashing the
production diff and re-running. The failing set is identical with and without the
repair:

- `full_pilot_supply_integration::test_closed_supply_stage_flows_to_top_accounting_owner`
  and `::test_e46_holder_reserve_writes_readiness_before_lifecycle` — assert
  `PILOT_INPUT_READY` but observe
  `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`.
- `end_to_end_pre_lifecycle_failure_propagation::test_public_coordinator_returns_no_stage_failure_and_never_builds_none_placeholder`
  — `AttributeError: '_NoopHeartbeat' object has no attribute 'failure_event'` at
  `operational_memory_factory_command.py:1596`.

They are unrelated to temporal-owner forwarding and are recorded here as
outstanding, not as passes. No broad suite was run; scope was not expanded,
because no focused failure required it.

## Invariants verified unchanged

- DTW99 `unexpected keyword argument 'temporal_refresh_owner'` is now impossible
  at this seam
- 900-second pre-lifecycle acquisition horizon: `900`, unchanged
- 30-operation cumulative discovery budget: `30`, unchanged, and still applied
  when unspecified
- front-door parameter count increased by exactly one; no `**kwargs` catch-all
  introduced
- lower-level signature untouched
- no Source Governor or Central Scheduler ownership change; the only lines in the
  diff matching owner/governor/scheduler are the new parameter, its comment and
  its forwarding
- exactly one production file changed

## Authoritative database

- before: `d896e03e99cff954caa8f9f936f28926481ea4ed57f4a875b1189757cef9a9ab`
- after: `d896e03e99cff954caa8f9f936f28926481ea4ed57f4a875b1189757cef9a9ab`
- size `74760192`, inode `1230526`, mtime_ns `1786294694745597037`, sidecars none

Byte-identical. Zero authoritative database writes. All test databases were
disposable or absent entirely.

## Side-effect accounting

Source/provider calls `0` · Scheduler runtime `0` · authoritative DB writes `0` ·
authorizations created `0` · application markers created `0` · wrapper
invocations `0` · Printer runtime starts `0` · WINDOW_15M executions `0` · new
capability unlocks `0`.

## Money-usefulness contribution

The next authorization can now reach real market truth instead of dying in
`CAMPAIGN_PRE_LIFECYCLE` on a wiring fault. The bounded temporal-persistence
repair — Printer's ability to survive a temporary 3-of-4 reserve shortage by
waiting inside the 900-second acquisition horizon rather than terminating
instantly — is finally connected to the code path that actually runs. The defect
that consumed DTW99 is now guarded by a regression that binds against the real
signature, so it cannot silently return.

## What remains locked and unproven

This is an interface repair, not an operational result. It does **not** prove
eligible supply: the underlying 3-of-4 reserve shortage remains unproven, and the
next authorized attempt can still honestly exhaust. A green regression is not a
WINDOW_15M operational pass.

All V1 locks remain binding: Solana-only, Solana memecoin-only, paper-only, no
live wallet, no private keys, no real funds, no live execution, no paid API
dependency, no scoring/ranking/confidence/weighted decisions, no embeddings or
vectors, no Source Governor or Central Scheduler bypass, and no retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, paper trade audits or PnL before
explicit approved lanes. WINDOW_1H/4H/12H/24H remain locked and
`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- The `**supply_kwargs` splat in
  `authoritative_live_operational_campaign.py:2517` remains a general blind spot:
  this repair fixes one parameter, not the pattern. Any future keyword injected
  the same way is again invisible to call-site text search.
- The DTW98 completion stub at line 307 still uses `**kwargs` and could still
  mask a *different* future signature defect. The design recorded tightening it
  as a recommendation; that work is not done here.
- Three pre-existing focused-suite failures remain outstanding and are unrelated
  to this seam. They should be triaged before the next authorization, since two
  of them concern pre-lifecycle selection coverage.
- The next authorization must bind the post-DTW99 database identity
  `d896e03e…f9ab`, not the consumed pre-attempt `a5643994…3dff`.
- Reaching the supply boundary is necessary, not sufficient: the acquisition
  horizon and refresh cadence must not be tuned merely to force a PASS.

## Stop condition

Stops after implementation and focused proof. No rereadiness, no fresh
authorization, no wrapper invocation, no Printer runtime, no WINDOW_15M.
