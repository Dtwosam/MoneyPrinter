# V2-9.8B pre-holder duplicate measured-transport producer repair closeout

## 1. Implementation baseline

| Field | Value |
| --- | --- |
| Implementation baseline HEAD | `acb761395ecf40d25c602f19fff6fdb89e207379` |
| Governing design commit | `e43ccba54238b09da5ce38d7a1729fef8957b8de` |
| Governing design | `docs/printer-v1-v2-9-8b-pre-holder-duplicate-measured-transport-producer-repair-design.md` |
| Governing forensic | `docs/printer-v1-v2-9-8b-auth-fec30eaa-pre-holder-duplicate-measured-transport-forensic-closeout.md` |
| Consumed authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T215031Z_fec30eaa` — permanently non-reusable |
| DB SHA before and after | `9ac31309c4f7a6233bc9f5d77944f88cd15a16a1659f98db665524f18dcb7a23` |

## 2. Exact production change

Only `src/printer_v1/operator_cli/operational_memory_factory_command.py` changed
in production. `_build_pre_lifecycle_temporal_refresh_owner` now derives
`initial_cycle_request_key_root` through the existing
`derive_campaign_source_request_key_root(execution_id)` and supplies it to the
initial `compose_owner` call. The former bare `execution_id` root is removed
from that failing owner.

```text
before: owner_request_key_prefix = execution_id
after:  owner_request_key_prefix =
        derive_campaign_source_request_key_root(execution_id)
```

No Source Governor, Scheduler, refresh-helper, direct-Pump producer,
CampaignSixUnitOwner, holder accounting, canonical identity, schema, or
migration code changed.

## 3. Fec30eaa regression and provider-call proof

New focused disposable-SQLite proof:

`tests/test_v2_9_8b_pre_holder_duplicate_measured_transport_root_propagation_repair.py`

It persists the first Cycle-1 Pump `COMPLETE + CLEAN_DATA`
`address|before=HEAD` transport under the typed root, constructs the actual
initial temporal-refresh owner, and captures the root passed into real refresh
composition. It proves:

```text
captured initial root == derive_campaign_source_request_key_root(execution_id)
captured initial root != bare execution_id
request_key_belongs_to_root(first_request_key, captured_root) == true
existing completed-tail helper skips the Pump channel
run_direct_migration_discovery second call == 0
durable governed Pump request count for K3 == 1
second measured transport == 0
second stage evidence == 0
```

The test first failed against the unmodified caller because it captured the
bare execution ID. After the one production correction it passed.

## 4. Pre-holder integrity and downstream guard

The fec30eaa proof passes the retained first transport as the sole manifest,
campaign-owner, and action-local measured identity into
`build_pre_holder_budget_snapshot`; snapshot construction succeeds with one
unique measured identity and no
`PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY`.

Downstream strictness remains independently proven by the passing
`duplicate_transport` pre-holder parameter and
`test_duplicate_transport_inside_one_cycle_still_fails_closed`. The repair
prevents a second producer call; it does not deduplicate or weaken downstream
accounting.

## 5. Prior-repair regressions

| Focused proof | Result |
| --- | --- |
| Cycle-2 Pump live-tail refresh-reentry repair | 7 passed |
| Four-token 118 / Cycle-2 seam | passed; `_token_ceiling_for_run_config` remains `118` |
| Direct temporal-owner compatibility tests | 3 passed |
| Authoritative Cycle-2 rebinding test | passed |

Cycle-2 behavior remains isolated: the existing helper still rejects foreign
roots and real cursors, and a Cycle-1 completed HEAD does not suppress the
separate Cycle-2 root.

## 6. Test results and bounded exception

Focused result set:

```text
new fec30eaa root propagation proof:                           1 passed
Cycle-2 Pump refresh-reentry focused file:                    7 passed
strict downstream duplicate proofs:                           2 passed
four-token/Cycle-2 joint seam + owner compatibility:          4 passed
Cycle-2 authoritative rebinding selected proof:               1 passed
```

The broader holder test file was inspected. Its exact `duplicate_transport`
parameter passes. Three unrelated legacy fixture expectations fail: the normal
snapshot fixture omits the now-required `transport_identity_keys`, and two
parameters expect a single historical category where the already-present
August aggregator emits
`MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS`. This repair modifies neither
that holder test nor holder production code; the discrepancy is a pre-existing,
out-of-scope test expectation and is not used to relax any guard or claim a
broader suite pass.

`py_compile` passed for the touched production file. `git diff --check` passed.

## 7. DB integrity and exclusions

The authoritative DB was not opened for writing. SHA-256 remained the exact
value above; SQLite `integrity_check` returned `ok` and `foreign_key_check`
returned no violations.

Excluded and unchanged: provider rate limits/scarcity, budgets `476 / 118 /
444`, retries, endpoint rotation, timing, holder capacity, selection/ranking,
Source Governor core, Scheduler, schema, longer windows, retrieval, and all
financial capabilities. This is offline proof only, not a live campaign success
claim.

## 8. Implementation verdict

`PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_PRODUCER_REPAIR_PASS`

`V2_9_8B_PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_PRODUCER_REPAIR_IMPLEMENTATION_BOUNDED_PROOF_PASS`

The canonical typed root is now propagated at the first incorrect owner; the
completed-tail helper sees the first Pump HEAD transport and prevents the
second provider request before Source Governor acquisition. Source Governor and
Scheduler ownership remain unchanged, and strict duplicate guards remain active.

## 9. Exact next lane

`INDEPENDENT CODE / PROOF REVIEW — PRE-HOLDER DUPLICATE MEASURED TRANSPORT PRODUCER REPAIR`

No authorization preparation/application, Printer execution, provider/RPC/
WebSocket activity, Central Scheduler operation, retry, rerun, resume, restart,
or successor is authorized by this closeout.
