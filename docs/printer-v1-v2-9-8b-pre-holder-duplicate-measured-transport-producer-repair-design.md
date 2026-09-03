# V2-9.8B pre-holder duplicate measured-transport producer repair design

## 1. Baseline and governing forensic

| Field | Bound value |
| --- | --- |
| Design baseline HEAD | `e5248c1c` — the committed fec30eaa forensic-closeout documentation HEAD |
| Governing forensic | `docs/printer-v1-v2-9-8b-auth-fec30eaa-pre-holder-duplicate-measured-transport-forensic-closeout.md` |
| Governing forensic verdict | `V2_9_8B_AUTH_FEC30EAA_PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_FORENSIC_CLOSEOUT_PASS` |
| Forensic classification | `UPSTREAM_TRUE_DUPLICATE_TRANSPORT_PRODUCER_DEFECT` |
| Authoritative DB SHA-256 | `9ac31309c4f7a6233bc9f5d77944f88cd15a16a1659f98db665524f18dcb7a23` |
| Consumed authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T215031Z_fec30eaa` — permanently non-reusable |
| Future prior-non-reuse derivation | Existing 60-ID root plus `fec30eaa`, expected 61 IDs subject to the canonical validator |

The fec30eaa campaign failed before lifecycle; `scheduler_runtime_calls=0` and
the first terminal cause was
`HolderBudgetError:PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY`.
The holder error is an integrity block, not holder-context budget exhaustion.
This design preserves the forensic result and proposes no reclassification.

## 2. Exact 4801 versus 4811 root mismatch

The original completed transport was request `4801`:

```text
producer:     run_direct_migration_discovery
caller:       initial campaign discovery / direct migration intake
execution:    20260903T220426Z-d312c7b4308f
campaign/run: 20260903T220426Z-d312c7b4308f-campaign /
              20260903T220426Z-d312c7b4308f-campaign-run
cycle:        20260903T220426Z-d312c7b4308f-cycle (Cycle 1)
typed root:   v2-9-8b-window15m-20260903T220426Z-d312c7b4308f
request key:  v2-9-8b-window15m-20260903T220426Z-d312c7b4308f-
              migration-page-live-tail
```

The duplicate was request `4811`:

```text
producer:     run_direct_migration_discovery
caller:       build_pre_lifecycle_refresh_stage refresh ordinal 1
execution:    20260903T220426Z-d312c7b4308f
campaign/run: same campaign and run as 4801
cycle:        same Cycle 1
lookup root:  20260903T220426Z-d312c7b4308f
request key:  20260903T220426Z-d312c7b4308f-refresh-1-pump-
              migration-page-live-tail
```

Therefore:

```text
4801 canonical ownership root =
v2-9-8b-window15m-20260903T220426Z-d312c7b4308f

4811 lookup/request root =
20260903T220426Z-d312c7b4308f
```

`cycle_pump_live_tail_head_already_completed` searched only the supplied bare
root before it called the producer.  The typed request key for `4801` is not
equal to that root and does not have that bare root followed by the required
`-` delimiter.  Consequently the helper could not see the existing complete,
clean `address|before=HEAD` evidence and the producer made a second governed
RPC request.  The two responses have the same canonical transport identity and
the same response SHA.

## 3. Canonical request-root owner

Design owner classification: `CANONICAL_TYPED_REQUEST_ROOT_AT_CALLER`.

The existing authority is in
`src/printer_v1/discovery/permanent_discovery_availability.py`:

```python
derive_campaign_source_request_key_root(execution_id)
# -> "v2-9-8b-window15m-" + execution_id

request_key_belongs_to_root(request_key, request_key_root)
# -> key == root or key.startswith(root + "-")
```

`CampaignSourceRequestScope` already binds that root to the exact
`execution_id`, `campaign_id`, `run_id`, and `cycle_id`; its validator rejects
a root not derived from that execution.  This repair reuses that owner and does
not introduce a second root scheme, a raw `startswith()` check, or a broad
multi-root lookup.

## 4. First incorrect caller/owner

| Item | Exact finding |
| --- | --- |
| First incorrect function | `_build_pre_lifecycle_temporal_refresh_owner` |
| File / current lines | `src/printer_v1/operator_cli/operational_memory_factory_command.py:1854-2015` |
| Incorrect call | Initial `compose_owner(...)` at `2009-2015` |
| Actual root | `owner_request_key_prefix=execution_id` |
| Expected root | `derive_campaign_source_request_key_root(execution_id)` |
| Downstream caller | `compose_owner` passes the value unchanged to `build_pre_lifecycle_refresh_stage` at `1959-1981` |
| Minimum correction | Derive the existing canonical typed root immediately before the initial `compose_owner` call and supply that value. Leave `cycle_rebinder` propagation unchanged. |

Initial Cycle-1 construction is the only bad binding.  The later-cycle rebinder
already receives the distinct later-cycle root it must preserve.  Classification
of why the bare root existed: `TYPED_SCOPE_CONVERSION_OMISSION`.

## 5. Selected repair boundary

The implementation lane must change only the initial caller boundary, before
refresh composition:

```text
execution_id
-> derive_campaign_source_request_key_root(execution_id)
-> initial compose_owner(owner_request_key_prefix=canonical_root)
-> build_pre_lifecycle_refresh_stage(request_key_prefix=canonical_root)
-> completed-tail check under canonical_root
-> either skip before Source Governor request, or issue one lawful first call
```

It must not make the helper search the bare root plus an unrelated typed root.
Such a fallback would make scope ownership ambiguous and could suppress lawful
work belonging to another cycle or campaign.  The repair is upstream producer
prevention, not downstream evidence cleanup.

## 6. Root propagation law

The intended request-key relationship is:

```text
canonical Cycle-1 root:
v2-9-8b-window15m-<execution_id>

initial child form:
<root>-migration-page-live-tail

refresh child form:
<root>-refresh-<positive-ordinal>-pump-migration-page-live-tail

membership:
request_key_belongs_to_root(child, root) == true
```

A request key is not a canonical transport identity.  Request keys establish
which durable evidence a lawful ownership scope may rehydrate; the canonical
transport identity decides whether the completed `address|before=HEAD` page is
the exact transport that may be skipped.  Both tests are required.

The helper's SQL candidate query may use a broad `LIKE` for retrieval, but its
authoritative membership decision remains the existing delimiter-safe
`request_key_belongs_to_root`; implementation must not replace it with raw
prefix matching.

## 7. Cycle and campaign isolation

The repair retains these laws:

| Case | Required result |
| --- | --- |
| Same Cycle-1 root, completed clean HEAD | Later refresh sees it and skips before a new request. |
| Cycle 2 root | Cycle-1 evidence does not suppress Cycle 2.  Existing Cycle-2 root construction remains distinct (for example `<execution_id>:c0002` before typed-root derivation). |
| Foreign campaign | No suppression. |
| Foreign execution | No suppression. |
| Different real cursor | `before=<signature>` is not `before=HEAD`; no suppression. |

The existing delimiter law prevents a Cycle-1 root from matching a Cycle-2 key
that continues with `:c0002-`, rather than `-`.  The complete typed scope
continues to bind execution, campaign, run, and cycle, so an execution cannot
borrow historical evidence from a foreign campaign/run/cycle.

## 8. Existing completed-tail helper disposition

Disposition: `HELPER_CORRECT__CALLER_ROOT_WRONG`.

`cycle_pump_live_tail_head_already_completed(connection, *, request_key_root)`
requires `NO_BEHAVIORAL_CHANGE`.

Its canonical comparison reconstructs the exact direct Pump signature-page
identity for the indexed address and `before=HEAD`; its response filter requires
`COMPLETE + CLEAN_DATA`; and it applies `request_key_belongs_to_root` after the
candidate retrieval query.  Those laws correctly reject failure, partial,
dirty, malformed, foreign-root, and real-cursor evidence.  The only failed
input in fec30eaa was the caller's bare root.

The approved Sep-3 Cycle-2 skip remains intact.  Supplying the proper initial
Cycle-1 root lets the same helper enforce the same law without a second
pre-holder-specific Pump dedupe helper.

## 9. Holder guard preservation

No change is permitted to:

```text
PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY
CampaignSixUnitOwner
MeasuredTransportLedger
canonical_transport_identity_key
pre-holder uniqueness assertion
```

The existing strict duplicate rejection is a required downstream integrity
defence.  The repair prevents the second producer call; it does not silently
deduplicate a manifest, alter canonical identity with request/stage/job data,
or delete/recount measured evidence.

## 10. Source Governor preservation

Source Governor remains the sole governed-request owner.  The completed-tail
check must execute before `run_direct_migration_discovery` and therefore before
a second Source Governor request.  The repaired skip reports zero new Pump
source requests; it does not issue a request and suppress accounting afterward.
There is no retry, endpoint rotation, extra source budget, provider change, or
Central Scheduler change.

## 11. Exact production and test files

### Required production file

`src/printer_v1/operator_cli/operational_memory_factory_command.py`

At the initial `compose_owner` call, import or otherwise reuse
`derive_campaign_source_request_key_root` and pass its result.  No production
change is planned in Source Governor, Scheduler, direct Pump producer,
pre-lifecycle refresh composition, six-unit accounting, holder accounting, or
measured transport identity code.

### Required focused test file for implementation

Create
`tests/test_v2_9_8b_pre_holder_pump_request_root_propagation_repair.py`.
It must seed disposable SQLite with the first typed Cycle-1 Pump HEAD response,
exercise the initial temporal-owner construction/re-entry boundary, and count
actual calls to `run_direct_migration_discovery` / durable source requests.

### Existing test files to run unchanged

| File | Purpose |
| --- | --- |
| `tests/test_v2_9_8b_cycle2_pump_live_tail_refresh_reentry_repair.py` | Preserve the approved Cycle-2 helper skip and its isolation/strict-duplicate cases. |
| `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py` | Preserve pre-holder duplicate integrity rejection. |
| `tests/test_v2_9_8b_standard4h_budget_and_cycle2_refresh_reentry_joint_seam.py` | Lightweight proof that the four-token ceiling remains 118 and the Cycle-2 skip seam remains intact. |

Schema change: `SCHEMA_CHANGE_NOT_REQUIRED`.  Source Governor core change: no.
Scheduler change: no.  Holder guard change: no.

## 12. Exact focused proof matrix

| Proof | Disposable setup | Required assertion |
| --- | --- | --- |
| A — fec30eaa duplicate prevention | Seed one typed Cycle-1 `COMPLETE/CLEAN_DATA` Pump HEAD response under `<root>-migration-page-live-tail`; invoke the initial refresh/re-entry boundary that formerly received bare `execution_id`. | Captured caller root equals `derive_campaign_source_request_key_root(execution_id)`; helper returns completed; `run_direct_migration_discovery` calls = 0; governed Pump requests for K3 = 1; no duplicate stage evidence; no `PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY`. |
| B — root propagation | Inspect/capture the root supplied by `_build_pre_lifecycle_temporal_refresh_owner`; seed original request under the canonical child key. | Original request membership and refresh lookup-root membership are both true via `request_key_belongs_to_root`. Do not mock the helper to true. |
| C — same Cycle-1 re-entry | Repeat the exact first Cycle-1 HEAD transport and refresh under the same root. | The producer is skipped before Source Governor; transport count remains 1. |
| D — isolation | Seed HEAD under Cycle 2, a foreign campaign, and a foreign execution; separately seed `before=<real-signature>`. | None suppresses current Cycle-1 HEAD.  Cycle-1 and Cycle-2 remain separate; real cursor remains distinct. |
| E — guard regression | Directly inject a genuine duplicate transport into existing six-unit/pre-holder accounting. | Existing strict duplicate error, including `PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY` at the applicable layer, remains fail-closed. |
| F — pre-holder progression | Use the deterministic offline fixture after producer prevention. | Measured transports are unique and pre-holder snapshot construction does not raise this duplicate-integrity error.  No admission/lifecycle proof is required. |
| G — recent-repair seam | Run the existing focused joint seam. | `_token_ceiling_for_run_config` remains 118 and the focused Cycle-2 completed-HEAD skip still passes. |

Proof A's governed request count is the acceptance criterion.  A fixture that
makes two provider calls and deduplicates later is a failure.

## 13. Interaction with prior repairs

The fec30eaa campaign did not reach four-token pre-4H lifecycle budget
enforcement or Cycle-2 acquisition.  This implementation is not live proof of
either prior repair and does not reopen them.  The implementation proof runs
their lightweight existing seam only; it does not rerun the historical broad
suite unless changed ownership code demonstrably expands beyond this boundary.

## 14. Exclusions

This design excludes provider rate limits and GeckoTerminal behavior; all
request ceilings (`476 / 118 / 444`); retries; endpoint rotation; Cycle-2
timing; holder capacity; scoring, selection, and ranking; Source Governor core;
Central Scheduler; schema; longer windows; retrieval; and all financial,
position, trade, audit, or PnL functionality.

## 15. Risks

The material risk is over-broad root equivalence.  It would incorrectly treat
similar request-key strings as the same lawful evidence scope and could suppress
new Cycle-2, foreign-campaign, or foreign-execution work.  The selected repair
avoids that risk by forwarding the already-authoritative typed root and by
retaining exact canonical identity and delimiter-safe membership checks.

The opposite risk is changing only the refresh request-key child form while
leaving the lookup root bare.  That would retain the pre-request false negative.
The proof matrix therefore asserts both the caller-root value and the provider
request count.

## 16. Implementation stop conditions

Stop implementation and return to design if evidence requires any schema or
migration; Source Governor core rewrite; Central Scheduler rewrite; holder-guard
relaxation; canonical identity change; broad multi-root searching with unclear
ownership; a background worker; timing/policy change; or provider-budget
increase.  In that event classify the result as `DESIGN_BLOCKED_BY_SCOPE_EXPANSION`.

## 17. Verdict

`V2_9_8B_PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_PRODUCER_REPAIR_DESIGN_PASS`

Classification: `NARROW_CANONICAL_REQUEST_ROOT_PROPAGATION_REPAIR_DESIGN`.

```text
helper disposition:                 HELPER_CORRECT__CALLER_ROOT_WRONG
canonical root owner:               CANONICAL_TYPED_REQUEST_ROOT_AT_CALLER
first incorrect production owner:   _build_pre_lifecycle_temporal_refresh_owner
schema change required:             no
Source Governor core change:        no
Scheduler change:                   no
holder guard change:                no
```

## 18. Next permitted lane

`PRE-HOLDER DUPLICATE MEASURED TRANSPORT PRODUCER REPAIR — IMPLEMENTATION + BOUNDED PROOF`

This design does not authorize implementation, a new authorization, an
application marker, Printer execution, provider/RPC/WebSocket activity,
Central Scheduler operation, DB mutation, retry, rerun, resume, restart, or
successor.  `fec30eaa` remains permanently consumed and non-reusable.
