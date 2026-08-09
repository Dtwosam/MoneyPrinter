# Printer V1 V2-9.8B Post-DTW99 Consumed Pre-Lifecycle Interface Failure Audit Closeout

## Verdict

`V2_9_8B_POST_DTW99_CONSUMED_PRE_LIFECYCLE_INTERFACE_FAILURE_AUDIT_PASS`

## Classification

`PRODUCTION_COMPOSITION_INTERFACE_FORWARDING_GAP`

The DTW99 attempt did not fail on market truth, source availability, provider
error, Scheduler behaviour, migration state, or the temporal-persistence repair
itself. It failed on a pure Python signature seam in the production composition
path, before any lifecycle or provider work began.

## Audit baseline

- audit branch: `agent/v2-9-8b-post-dtw99-consumed-pre-lifecycle-interface-failure-audit`
- audit HEAD: `048c86908f5441559be7a9c28be6ea3b383758d3`
- tracked worktree clean at audit start
- preceding closeout: `8ab6dac27c8233e166d4e691bd072267ac36aa20` (post-054 authorization review PASS)

## DTW99 consumed attempt — verified evidence

Every value below was re-measured from the preserved marker directory, not
copied forward from the request.

- authorization: `V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z`
- execution: `20260809T165814Z-e16ee84dc4c7`
- application-marker SHA-256: `560ae8286875795c0b7a17c1ff3e82b9081a8636aafe03f65a17dc85f75b2370` — verified
- child-terminal SHA-256: `466ec36d79ee2649869f3d7b1f741ff435205f77bf4a6c9f375e7311978063a7` — verified
- post-attempt DB SHA-256: `d896e03e99cff954caa8f9f936f28926481ea4ed57f4a875b1189757cef9a9ab` — verified against the live authoritative database
- DB identity before attempt: `a56439948196c68267f6923b4469b33e9a5d8cd2f7e789c3e21b5253c0013dff` (the exact authorized binding)
- failure phase: `CAMPAIGN_PRE_LIFECYCLE`
- terminal category: `OPERATIONAL_COMMAND_BLOCKED`
- process exit code: `1`
- `lifecycle_started`: `null`
- controlling cause: `TypeError:build_graduated_supply() got an unexpected keyword argument 'temporal_refresh_owner'`
- source calls: `0`
- Scheduler runtime calls: `0`
- fresh external transport attempts: `0`
- database writes: `6`
- cleanup complete: `true`
- lease released: `true`
- marker consumed: `true`
- restart created: `false`; successor created: `false`
- terminal truth status: `RECONSTRUCTED`

The six database writes are fully accounted for and are campaign-identity rows
only: one insert each into `printer_memory_factory_campaign_configurations`,
`printer_memory_factory_campaign_cycles`, `printer_memory_factory_campaign_runs`
and `printer_memory_factory_campaign_supervision`, plus terminal-state updates to
`printer_memory_factory_campaigns` and `printer_memory_factory_campaign_runs`. No
discovery, source, token, snapshot, memory, decision, position, trade or PnL
table changed; every other table delta is `0`.

## Post-attempt residue state

Re-measured read-only at audit time:

- DTW99 campaign / run / cycle state: `TERMINAL_FAILED`; supervision `TERMINAL`
- active campaigns / runs / supervision: `0`
- `printer_pre_lifecycle_discovery_refresh_waits`: `0` total rows, `0` `WAITING`/`CLAIMED`
- scheduler locked: `0`; scheduler pending or running: `0`
- migration count: `54` (unchanged)
- no WINDOW_15M memory produced; no memory window, fingerprint or report row created

Authorization `V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z` is permanently consumed
and non-reusable. It must not be retried, rerun, restarted, resumed or succeeded.

## Runtime call chain — traced from source, not assumed

The previous helper probes assumed a specific textual/AST location for the
production call and did not find it. That assumption was wrong, and this audit
did not repeat it. The reason the literal call text does not exist is now
established:

The production caller never writes `build_graduated_supply(temporal_refresh_owner=…)`
as source text. It injects the keyword into a dictionary and splats it. A textual
or AST search for the keyword as a direct call argument therefore cannot find it.

Verified chain:

1. `operator_cli/operational_memory_factory_command.py:3390` builds the owner via
   `_build_pre_lifecycle_temporal_refresh_owner(...)` (defined at line 1547) in
   operational mode.
2. `operator_cli/operational_memory_factory_command.py:3515` passes it onward as
   `pre_lifecycle_temporal_refresh_owner=…`.
3. `operator_cli/authoritative_live_operational_campaign.py:2339` receives it as
   `pre_lifecycle_temporal_refresh_owner: Any | None = None`.
4. `operator_cli/authoritative_live_operational_campaign.py:2507` tests
   `if pre_lifecycle_temporal_refresh_owner is not None:` and, inside that branch,
   sets **two** dictionary entries — `supply_kwargs["deadline_at"]` (line 2508) and
   `supply_kwargs["temporal_refresh_owner"]` (line 2514).
5. `operator_cli/authoritative_live_operational_campaign.py:2517` calls
   `build_graduated_supply(command.db_path, cycle_seed=…, migration_transport=…,
   now=…, **supply_kwargs)`.
6. `operator_cli/graduated_supply_front_door.py:767` declares
   `build_graduated_supply` with no `temporal_refresh_owner` parameter and no
   `**kwargs` catch-all. Python raises `TypeError` at call time.
7. `discovery/eligible_token_supply.py:653` already declares
   `temporal_refresh_owner: Any | None = None` as a keyword-only parameter on
   `run_persistent_eligible_token_supply`.
8. `operator_cli/graduated_supply_front_door.py:882` calls
   `run_persistent_eligible_token_supply(...)` and forwards 30+ keywords but
   **not** `temporal_refresh_owner`.

Of the two keywords injected at step 4, `deadline_at` **is** declared on
`build_graduated_supply` and passes cleanly. Only `temporal_refresh_owner` is
undeclared. The gap is exactly one parameter wide.

Because the branch at step 4 is conditional on a non-null owner, the defect is
unreachable for any legacy or non-operational caller and fires only in the
operational path that DTW99 exercised. This is why the defect survived until a
consumed one-use authorization spent itself on it.

## Independent reproduction without execution

The failure was reproduced by pure signature binding — no campaign, no provider
transport, no database, no runtime:

- `build_graduated_supply` declares `temporal_refresh_owner`: `False`
- `build_graduated_supply` has a `**kwargs` catch-all: `False`
- `build_graduated_supply` declares `deadline_at`: `True`
- `run_persistent_eligible_token_supply` declares `temporal_refresh_owner`: `True`
  (default `None`, `KEYWORD_ONLY`)
- binding the real signature with `temporal_refresh_owner=<object>` raises
  `TypeError: got an unexpected keyword argument 'temporal_refresh_owner'`

This is byte-for-byte the controlling cause recorded in the DTW99 child terminal.

## Audit conclusion

The failure is exactly the hypothesised interface seam:

```text
production caller (authoritative_live_operational_campaign:2517, via **supply_kwargs)
  -> build_graduated_supply(... temporal_refresh_owner=owner)
  -> build_graduated_supply does not declare that parameter   <-- the gap
  -> run_persistent_eligible_token_supply already declares it
```

Classification: `PRODUCTION_COMPOSITION_INTERFACE_FORWARDING_GAP`.

The temporal-persistence implementation ratified post-DTW98, migration 054, the
post-054 rereadiness closeout and the post-054 authorization review were all
themselves sound. The wiring between the campaign composition layer and the
supply front door was not.

## Why existing tests did not catch it

`tests/test_v2_9_8b_post_dtw98_temporal_persistence_completion.py:307` replaces the
real front door with:

```python
def fake_build_graduated_supply(db_path, **kwargs):
```

A `**kwargs` stub accepts every keyword by construction, so it accepted
`temporal_refresh_owner` and reported the plumbing as working. The test asserted
that the campaign layer *sends* the owner; nothing asserted that the real front
door *accepts* it. The defect lived precisely in the gap between those two claims.

This is a monkeypatch-shaped blind spot, not a missing assertion: no assertion
added to that stub could have caught it, because the stub itself is what hid the
signature.

## Money-usefulness contribution

This audit converts a consumed authorization into a permanent, precisely located
one-parameter defect with a reproduction that needs no authorization, no
provider budget and no runtime. The next authorization can be spent on real
market truth instead of re-discovering a wiring fault.

## What this closeout does not do

It does not rerun DTW99, create or prepare an authorization, modify production
code, run a proof, start Printer, or invoke WINDOW_15M. It changes no locks. All
V1 locks remain binding and `WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- The repair is narrow, but the class of defect is not: any keyword injected via
  `**supply_kwargs` is invisible to textual/AST call-site search and unchecked by
  `**kwargs` test stubs.
- A passing focused regression on this seam is not evidence of eligible supply;
  the underlying 3-of-4 reserve shortage remains unproven either way.
- Six identity rows from the consumed attempt remain in the authoritative
  database as honest terminal history and must not be deleted.
- The post-attempt DB SHA is now `d896e03e…f9ab`; any future authorization must
  bind that identity, not the pre-attempt `a5643994…3dff`.

## Next lane

`V2-9.8B Post-DTW99 build_graduated_supply Temporal Owner Interface Repair`
(design recorded separately; implementation, proof, rereadiness and a fresh
authorization all remain future lanes).
