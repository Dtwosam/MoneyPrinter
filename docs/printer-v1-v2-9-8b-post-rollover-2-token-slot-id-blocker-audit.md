# Printer V1 V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M `token_slot_id` Blocker Audit

Date: 2026-08-02

Linear: `DTW-18`

Lane:
`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Audit`

Lane type: read-only blocker audit and documentation only.

This lane executed no wrapper, operational command, provider/source request,
discovery, campaign, database mutation, Memory Factory, memory generation,
retrieval, decision, position, trade, audit, PnL, retry, rerun, resume, restart,
successor, new authorization, or longer-window work. The only intended repository
mutation is this audit report and its commit.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_WINDOW_15M_TOKEN_SLOT_ID_BLOCKER_ROOT_CAUSE_CONFIRMED`

The failure is fully resolved as an evidence question, but it is not repaired.
The durable discovery/selection owner correctly creates each `token_slot_id` and
persists it on both the campaign token-slot row and the selected-item handoff
link. The intermediate activated-slot reader then omits `s.token_slot_id` from
its SQL projection. Its dictionaries are copied without enrichment into the
discovery-selection terminal-stage record. The public coordinator's accounting
consumer correctly requires the durable slot identity and raises
`KeyError: 'token_slot_id'` when it indexes the incomplete record.

Classification:

- durable producer contract: **complete**;
- consumer timing/semantic requirement: **correct, not premature**;
- intermediate transformation: **drops the required field**;
- immediate `record["slots"]` producer contract: **incomplete**;
- evidence gap: **none for the root cause**.

The smallest safe repair boundary is the activated-slot SQL projection in
`origin_lifecycle_campaign._read_activated_slots`: carry the already-durable
`s.token_slot_id` into the returned dictionaries. No identity may be invented,
reconstructed from ordinal/mint/pair, substituted with `token_identity`, or made
optional in the consumer.

This verdict does not authorize that repair, a proof run, or another
authorization.

## 2. Exact baseline and execution identities

| Item | Exact value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-post-rollover-2-token-slot-id-blocker-audit` |
| Audit start HEAD | `de8108b2b5204b0dabae1de71b42406572080f3a` |
| Authorized launch branch | `agent/v2-9-8b-post-rollover-2-fresh-exact-head-window-15m-final-authorization` |
| Authorized launch HEAD | `be6ead74a260d58c7ccca2042de2fe8f2b584242` |
| Authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` |
| Authorization SHA-256 | `1191277816c97589ed05aa0aee8ec4a5af1feb777728c356a51eba40c1595626` |
| Wrapper application time | `2026-08-02T21:52:14.520163+00:00` |
| Execution | `20260802T215214Z-50fece784718` |
| Campaign | `20260802T215214Z-50fece784718-campaign` |
| Campaign run | `20260802T215214Z-50fece784718-campaign-run` |
| Cycle | `20260802T215214Z-50fece784718-cycle` |
| Configuration | `20260802T215214Z-50fece784718-configuration` |
| Supervision | `20260802T215214Z-50fece784718-supervision` |
| Preallocated factory run | `c1dde202-bfc0-47b8-93d5-6e57c12b1e02` |
| Child terminal | `CHILD_EXITED_NONZERO`, exit code `1` |
| Command terminal | `OPERATIONAL_COMMAND_BLOCKED` |
| Campaign terminal | `OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE` |
| First terminal cause | `OPERATIONAL_CAMPAIGN_FAILED:KeyError` |
| Error | `KeyError: 'token_slot_id'` |
| Reported source calls | `6` |
| Reported database writes | `0` |
| Reported Scheduler runtime calls | `0` |
| Retry/rerun/resume/restart/successor | `0 / 0 / 0 / 0 / 0` |

The relevant active source, wrapper, validation identity, ledger, and focused-test
files have no diff between authorized HEAD `be6ead7...` and audit HEAD
`de8108b...`. The current operational command SHA-256 is
`16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b`,
exactly the identity recorded by the authorization. Therefore the current line
numbers and contract trace below describe the code that failed.

The pre-existing untracked Migration-050 and consumed-authorization evidence
directories were treated as immutable evidence. They are not part of this
audit's commit.

## 3. Consumed application and terminal evidence

The complete authorization-specific external application directory is:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

| File | Bytes | SHA-256 | Finding |
| --- | ---: | --- | --- |
| `application-marker.json` | 897 | `6df364e6298b64bba2133028ff80081810396190fc20a4067eeb36e38d1a0a3e` | create-once consumption marker |
| `git-provenance-manifest.json` | 4785 | `90b8b2df48a3f56b1d74d1ed30a2775e9d519725bf16631d0c0206a9572d11e0` | exact package/repository manifest |
| `child-stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | empty |
| `child-stderr.txt` | 335 | `3c6ef62f39fe65f0d13a3a7cbdb382e978ff1ce7f7e16c6787b6aed2463d40ab` | structured blocker envelope |
| `wrapper-terminal.json` | 1743 | `fafab041cddd4251872a97359274460c774c893916d19f9c544871bce663e97d` | one child, nonzero terminal |

The marker says `allowed_invocation_count=1`, records the consumption timestamp,
and fixes `automatic_retry_allowed`, `manual_rerun_allowed`, `resume_allowed`,
`restart_allowed`, and `successor_allowed` to `false`. The wrapper terminal says
the child was started exactly once, exited `1`, and all retry/rerun/resume/
restart/successor counters are zero. The wrapper's create-once canonical
directory also causes a second application attempt to fail closed.

**The authorization is consumed, non-reusable, and cannot support a repair
proof or another campaign.** A blocked child still consumes it under the
authorization's honest-terminal law.

The action artifact root contains only the pre-campaign backup, its disposable
restore rehearsal, and `terminal-summary.json`; no report directory or campaign
report was produced. The backup and restore both hash to the authorized
pre-campaign DB identity
`56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5`.

The terminal summary confirms:

- three source stages were sealed before the blocker (`LOCATOR`,
  `DIRECT_MIGRATION`, `EXACT_LIQUIDITY`);
- accounting was blocked as
  `OPERATIONAL_STAGE_FAILED_BEFORE_ACCOUNTING_COMPLETION`;
- no factory run was found and no campaign window or campaign report was
  created;
- cleanup completed, the lease was released, and active owned work was zero;
- both selected slots were terminalized to `MANUAL_REVIEW`, with their tracking
  queues `SKIPPED`;
- no restart or successor was created.

## 4. Exact failure line and call chain

The exact failing line is
`src/printer_v1/operator_cli/operational_memory_factory_command.py:1784`:

```python
subject_identity=str(slot["token_slot_id"]),
```

Exact call chain:

1. `scripts/Start-PrinterV1-Window15M-OneShot.ps1` invokes the one-shot wrapper.
2. `window_15m_one_shot_wrapper.apply_authorization_once()` creates the marker,
   validates the manifest/marker pair, and starts exactly one child:
   `operational_memory_factory_command run --operator-approved`.
3. `operational_memory_factory_command.main()` calls
   `run_operational_campaign()`, then `_run_operational_campaign()`.
4. `_run_operational_campaign()` installs `_observe_full_run_stage` as
   `lifecycle_kwargs["full_run_stage_observer"]` and calls
   `AuthoritativeLiveOperationalCampaignOwner.run_operational()`.
5. The authoritative owner calls `OriginToLifecycleCampaignDriver.run()`.
6. The driver calls `CombinedPumpfunCampaignExecutor.execute()`.
7. The executor's initial two-slot path calls
   `_atomic_initial_two_slot_handoff()`, then `_handoff_one_slot()` twice.
8. `_handoff_one_slot()` creates and persists each deterministic
   `token_slot_id`, and passes the same ID to `link_selected_item()`.
9. After the atomic handoff commits, the driver calls
   `_read_activated_slots()` and obtains dictionaries missing
   `token_slot_id`.
10. The driver copies those dictionaries into
    `record["slots"]` at `origin_lifecycle_campaign.py:1451`, then invokes the
    full-run stage observer at line 1446.
11. `_observe_full_run_stage()` enumerates the two dictionaries. Its first
    `slot["token_slot_id"]` index raises the observed `KeyError` before the
    lifecycle factory is invoked.
12. The exception returns to the public coordinator, which blocks the six-unit
    owner, terminalizes the initialized campaign graph, writes the terminal
    summary, and re-raises. `main()` emits the structured blocker envelope and
    exits `1`; the wrapper records `CHILD_EXITED_NONZERO`.

This timing explains why source and discovery work occurred while the Memory
Factory itself did not start.

## 5. Slot identity contract and live shape

### 5.1 Where `token_slot_id` is created

`combined_executor._handoff_one_slot()` constructs:

```python
slot_id = f"slot-{fixtures.cycle_id}-{ordinal}"
```

It inserts that value as the primary key of
`printer_memory_factory_campaign_token_slots` and uses the same value in
`printer_discovery_selected_item_links.token_slot_id`. Schema foreign keys and
immutability triggers bind the ID to the exact campaign/run/cycle, token row,
mint, pair row, and tracking queue. This is the authoritative creation boundary.

The current DB preserves both exact identities:

| Ordinal | `token_slot_id` | token row / mint | pair row / pool | lifecycle | queue |
| ---: | --- | --- | --- | --- | ---: |
| 1 | `slot-20260802T215214Z-50fece784718-cycle-1` | `28` / `2C3CURT1uZUdqxoxFcMGwbVevom1ETu6FNDcaaByDR7A` | `32` / `AR4eDzUGi3wfPJGwXSJMAXLN3Y49oBAD2srexBCorV59` | `PUMPSWAP_GRADUATED_CONFIRMED` | 32 |
| 2 | `slot-20260802T215214Z-50fece784718-cycle-2` | `27` / `Av2cD8GQT5dnCiC2cav2X37hs9z2mbBSxAMGkRbwkdt2` | `31` / `REUdyzJNhNYJbgxAWfjiicvcTsfSJhyd61oN1JhhJXo` | `PUMPSWAP_GRADUATED_CONFIRMED` | 33 |

Both selected-item links contain those exact IDs, are
`HANDOFF_RECORDED`, and point to Scheduler jobs `1374` and `1375` respectively.

### 5.2 Actual `record["slots"]` keys

`origin_lifecycle_campaign._read_activated_slots()` selects only:

```text
slot_ordinal
token_row_id
pair_row_id
mint_identity
pair_identity
token_state
pair_address
token_status
```

At the callback boundary both records necessarily had
`token_state='SELECTED'`, because that is the reader's SQL predicate. Their
actual semantic payload was:

| Key | Slot 1 | Slot 2 | Meaning |
| --- | --- | --- | --- |
| `slot_ordinal` | `1` | `2` | position inside the two-slot cycle |
| `token_row_id` | `28` | `27` | `printer_tokens.id` |
| `pair_row_id` | `32` | `31` | `printer_pairs.id` |
| `mint_identity` | `2C3CURT...DR7A` | `Av2cD8...dt2` | Solana token mint |
| `pair_identity` | `AR4eDz...V59` | `REUdyz...JXo` | selected PumpSwap pool address |
| `token_state` | `SELECTED` | `SELECTED` | live post-handoff slot state |
| `pair_address` | same as pair identity | same as pair identity | joined pair-table address |
| `token_status` | `TRACK_NORMAL` | `TRACK_NORMAL` | joined token-table status |

The durable IDs shown in Section 5.1 existed at this moment but were absent from
both dictionaries. The reader also omits other durable slot fields such as
`token_identity`, `lifecycle_identity`, and `tracking_queue_id`; those omissions
do not cause this specific consumer failure.

`LocalValidationIdentity.subject_identity` is defined as the exact subject a
named local validation ran against. For
`SELECTION_HANDOFF_VALIDATED`, the durable campaign token-slot primary key is
the correct subject. Mint, pair, token row, ordinal, or lifecycle label is not a
semantically interchangeable replacement.

## 6. Every transformation from selection to the failing consumer

| Boundary | Shape/operation | `token_slot_id` state |
| --- | --- | --- |
| `_handoff_one_slot()` | constructs `slot-{cycle_id}-{ordinal}` | present |
| token-slot insert | durable primary key and immutable campaign identity | present |
| `link_selected_item()` | durable selected-item handoff lineage | present |
| executor transaction commit | atomic two-or-none activation | present |
| first `_read_activated_slots()` | SQL projection for compensation recorder | **dropped** |
| second `_read_activated_slots()` | SQL projection assigned to local `slots` | **dropped** |
| `materialize_origin_activated_batch()` | fresh call to the same incomplete reader; mirrors token/pair into a selection batch | unavailable in returned projection |
| `[dict(row) for row in slots]` | shallow dict copy into stage record | still absent |
| `record.get("slots", ())` | passes the two dicts directly | still absent |
| `slot["token_slot_id"]` | required validation subject lookup | `KeyError` |

No transformation after `_read_activated_slots()` removes a present field. The
loss occurs exactly in that SQL select list. The selection batch is not an
alternate identity authority; the durable slot table and selected-item link
remain authoritative.

Working WINDOW_15M comparable code confirms the intended pattern. At the
campaign-window close boundary,
`one_command_15m_factory._register_campaign_window_at_close_boundary()` queries
`SELECT token_slot_id, lifecycle_identity` from the same token-slot table and
passes `slot["token_slot_id"]` to `register_campaign_window_close()`. Full-run
terminal accounting likewise explicitly selects and carries
`token_slot_id`. These paths consume the durable identity rather than deriving
it.

## 7. Why focused tests did not expose the live shape

The gap is composition coverage, not absence of token-slot tests:

- origin-to-lifecycle integration tests run the real driver without supplying
  `full_run_stage_observer`; they validate mint/token/pair identity and lifecycle
  completion but never exercise the stage-record consumer;
- the operational active-path restoration proof invokes
  `AuthoritativeLiveOperationalCampaignOwner.run_operational()` directly, also
  without the public coordinator's observer; it even queries slot rows without
  selecting `token_slot_id` while separately confirming the handoff link has it;
- full-run wiring tests start from manually seeded token slots containing
  `token_slot_id` and manually seal the discovery-selection boundary validation;
  they do not pass the real `_read_activated_slots()` output into the real
  nested coordinator consumer;
- accounting tests construct identity-rich dictionaries or rows explicitly,
  so their fixtures already satisfy the consumer contract;
- the outer command failure test injects an owner that raises before returning a
  stage record; it proves terminalization, not successful owner/driver/callback
  composition.

Git history makes the mismatch precise. `_read_activated_slots()` and its
eight-column projection originated in commit `d3ea14ee` on 2026-07-21. The new
full-run stage observer and the consumer's `slot["token_slot_id"]` requirement
were added in commit `02f87289` on 2026-08-01. That change added extensive
accounting tests but no test that joins the real activated-slot reader to the
real public callback. The older projection contract was therefore never
revalidated against the newer consumer.

## 8. Blast radius

Confirmed direct blast radius:

- the authoritative public ordinary WINDOW_15M path fails after a successful
  two-slot discovery/selection handoff whenever it installs the full-run stage
  observer;
- the failure is deterministic for every nonempty `record["slots"]` produced by
  the current reader, independent of which valid tokens or pools are selected;
- it occurs before `run_one_command_15m_factory()` starts, so it blocks all new
  WINDOW_15M snapshots, window closes, episodes, fingerprints, and campaign
  terminal accounting for that attempt;
- it happens after governed source work, campaign initialization, discovery
  persistence, slot activation, handoff Scheduler work, and campaign Scheduler
  projection, so every failed authorized attempt can consume scarce source and
  authorization budget and leave terminal historical rows requiring review;
- direct owner/driver paths that omit the observer can appear healthy and are
  not proof that the public command is healthy.

Not in the blast radius of this defect:

- durable slot construction and selected-item linkage are correct;
- token/mint/pair/tracking identity constraints remain intact;
- terminal cleanup reached zero active residue;
- no Memory Factory row, memory window, snapshot, retrieval, decision, position,
  trade, audit, or PnL row was created by this attempt.

## 9. DB, Scheduler, memory, and protected-capability reconciliation

All database inspection used immutable/read-only SQLite URIs. No sidecar was
present before or after inspection.

### 9.1 Database identity and integrity

| State | SHA-256 | Size |
| --- | --- | ---: |
| Authorized pre-campaign DB / action backup / restore rehearsal | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` | 65,671,168 |
| Current authoritative DB | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` | 65,806,336 |

- current DB SHA-256 before this audit equals current DB SHA-256 after the
  read-only inspection: `d85442e6...25cbe`;
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: zero rows.
- `printer_v1.sqlite3-wal`, `-shm`, and `-journal`: absent.

The current DB differs from the pre-campaign backup because the consumed action
persisted pre-lifecycle and terminal-cleanup evidence. Relevant count deltas
from the exact backup are:

| Surface | Delta |
| --- | ---: |
| campaign / configuration / campaign run / cycle / supervision | `+1` each |
| campaign token slots | `+2` |
| campaign Scheduler work | `+10` |
| discovery batch | `+1` |
| discovery work | `+8` |
| selected-item links | `+2` |
| Scheduler jobs | `+10` |
| campaign windows / campaign reports | `0 / 0` |
| factory runs / factory steps | `0 / 0` |
| memory windows / token snapshots / fingerprints | `0 / 0 / 0` |

Therefore `database_writes: 0` in `child-stderr.txt` is the blocked command
envelope's fixed outward counter, not a literal assertion that the action made
no durable mutation. The exact campaign-scoped rows and pre/current hashes prove
that writes occurred before the exception and during terminal cleanup. A future
proof must not use that envelope field as a database-mutation reconciliation.

The exact campaign, run, and cycle are all `TERMINAL_FAILED` with first cause
`OPERATIONAL_CAMPAIGN_FAILED:KeyError`. Supervision is `TERMINAL/FAILED`, cleanup
is complete, and the lease is released. Both slots are `MANUAL_REVIEW`; queues
32 and 33 are `SKIPPED/MANUAL_REVIEW`.

### 9.2 Scheduler reconciliation

Global active-residue counts are all zero:

| Active surface | Count |
| --- | ---: |
| Scheduler jobs (`PENDING`/`RUNNING`) | 0 |
| locked Scheduler jobs | 0 |
| active campaigns | 0 |
| active campaign runs | 0 |
| active/stopping supervision | 0 |
| active discovery work | 0 |
| pending/running factory steps | 0 |
| active proof supervision | 0 |

The exact action has ten attributable Scheduler jobs: eight `SUCCEEDED` and two
`CANCELLED`. Its eight discovery-work rows are all `SUCCEEDED`. Campaign
Scheduler work contains eight `DISCOVERY_SELECTION` rows without slot linkage
and one `FIRST_15M_HANDOFF` row for each exact slot.

Thus the reported `scheduler_runtime_calls: 0` and terminal summary
`campaign_scheduler_calls: 0` are consistent with the Memory Factory runtime
not starting, but they are not a count of all pre-lifecycle Scheduler persistence
or Scheduler-owner activity. There is terminal Scheduler history and zero active
Scheduler residue.

### 9.3 Memory and protected capabilities

Pre-campaign to current deltas are all zero for:

- `printer_memory_factory_runs` and `printer_memory_factory_run_steps`;
- `printer_memory_windows`, `printer_token_snapshots`, and
  `printer_memory_fingerprints`;
- memory retrieval queries and matches;
- paper decisions, positions, trade events, trade audits, and audit reports.

Current protected-capability baselines remain exactly:

| Table | Current | Delta |
| --- | ---: | ---: |
| `printer_memory_retrieval_queries` | 10 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 |
| `printer_paper_decisions` | 2 | 0 |
| `printer_paper_positions` | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 |
| `printer_paper_audit_reports` | 1 | 0 |

The attempt created no memory and unlocked no protected capability. Existing
historical retrieval/decision/audit rows were not changed by this attempt.

## 10. Smallest safe repair boundary

The minimum implementation is bounded to the activated-slot projection:

1. add the authoritative `s.token_slot_id` column to
   `_read_activated_slots()`;
2. preserve the returned value unchanged through the existing dict copy and
   callback;
3. retain the consumer's required direct index and exact
   `SELECTION_HANDOFF_VALIDATED` subject identity.

Do not:

- synthesize `token_slot_id` from `cycle_id` and `slot_ordinal`;
- fall back to mint, pair, token row, `token_identity`, or lifecycle identity;
- weaken the consumer to `.get()` or silently skip missing slot validations;
- change selection authority, Scheduler ownership, six-unit totals, database
  schema, wrapper, authorization semantics, or lifecycle behavior;
- use the consumed live DB as a repair fixture or run another live campaign.

Adding an explicit producer-side shape assertion may improve diagnostics, but it
must not replace carrying the durable column. Any broader refactor is outside
the minimum repair boundary and requires separate justification.

## 11. Minimum focused tests and bounded proof

Before another authorization can be considered, the repair lane must provide at
least:

1. **Activated-slot projection regression** — on a disposable migration-050 DB,
   create two valid durable slots and assert `_read_activated_slots()` returns
   exactly two ordered records whose nonempty `token_slot_id` values exactly
   equal the persisted primary keys. Also prove the token/mint/pair identities
   remain unchanged.
2. **Real driver callback integration** — run the real combined discovery
   executor and `OriginToLifecycleCampaignDriver` with frozen/injected evidence
   and a `full_run_stage_observer`; assert its terminal-stage `record["slots"]`
   contains two distinct durable IDs equal to both the token-slot table and
   selected-item links. This is the missing live-shape composition test.
3. **Public accounting-boundary integration** — exercise the real
   `_observe_full_run_stage` composition on a disposable DB without wrapper or
   provider contact; assert two `SELECTION_HANDOFF_VALIDATED`
   `LocalValidationIdentity` records use those exact IDs, the stage seals, and no
   `KeyError` occurs.
4. **Negative shape proof** — demonstrate that a deliberately malformed slot
   record without the durable ID fails closed before lifecycle work and cannot be
   counted as a successful validation. The diagnostic may improve, but silent
   omission is forbidden.
5. **Bounded end-to-end WINDOW_15M offline proof** — frozen transports,
   disposable migration-050 DB, exact public coordinator/owner/driver wiring,
   no provider, no authoritative DB, no wrapper, no authorization. Prove the
   repaired boundary proceeds into the factory, terminalizes cleanly, leaves
   zero active/locked residue, preserves FK/integrity, and has zero protected-
   capability deltas.
6. **Focused regression set** — rerun the origin-to-lifecycle, post-handoff
   compensation, full-run wiring/accounting, terminal-safety, operational
   active-path, and wrapper tests affected by the contract. Tests that manually
   preseed the stage remain supporting evidence, not substitutes for item 2.

The bounded-proof report must record exact source/test hashes, test commands and
results, disposable DB before/after identities, slot records at the callback,
stage validation identities, Scheduler terminal/active counts, memory deltas,
protected-capability deltas, and zero source/provider contact. An independent
repair closeout must then verify the source diff is limited to the approved
boundary and tests, and that no live authorization or action was created.

Only after repair design, implementation, bounded proof, and independent
closeout all pass may a separate fresh exact-HEAD readiness/authorization review
be considered. The consumed authorization in this audit is never an input to
that future decision.

## 12. Money-usefulness contribution

This audit creates no revenue, trade, position, PnL, memory, or decision. Its
money-usefulness contribution is reliability and budget protection:

- it prevents another authorization and governed source budget from being spent
  on a deterministic identity-shape failure;
- it preserves exact token-slot attribution required for trustworthy per-token
  accounting and later memory quality evaluation;
- it prevents a fake accounting success produced by silently skipping the two
  selection-handoff validations;
- it confines repair work to an existing durable identity projection instead of
  risking selection, Scheduler, lifecycle, or financial semantics.

This is enabling usefulness only. It does not establish clean-memory growth or
profitability.

## 13. What this audit improves

- Converts the live `KeyError` from a generic blocker into an exact line,
  contract, and call-chain diagnosis.
- Separates authoritative durable identity creation from the incomplete
  intermediate projection.
- Records the two actual live slot shapes and exact omitted identities.
- Explains the focused-test blind spot at the real composition boundary.
- Reconciles the misleading outward zero-write/zero-runtime counters with the
  actual durable pre-lifecycle history and zero active residue.
- Defines a one-query repair boundary and a proof set that can prevent recurrence
  without widening runtime authority.

## 14. What remains locked

All runtime and financial capabilities remain locked, including:

- wrapper application and operational command execution;
- provider/source/RPC contact and Source Governor runtime;
- Central Scheduler runtime and campaign/discovery execution;
- new authorization, retry, rerun, resume, restart, or successor;
- Memory Factory execution, memory generation, retrieval, and decisions;
- BUY, SELL, HOLD, positions, trades, trade audits, and PnL;
- all longer windows;
- wallets, private keys, real funds, live execution, paid APIs, scoring,
  ranking, confidence, weighting, embeddings, and vectors.

The two failed-action slots and queues remain terminal historical evidence in
`MANUAL_REVIEW` / `SKIPPED`; this audit does not reactivate, delete, recover, or
reuse them.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- The public WINDOW_15M path remains deterministically blocked at the first
  selection-handoff validation until the projection is repaired.
- A repair that derives or substitutes an identity could make accounting appear
  complete while breaking durable slot lineage.
- Unit-only proof can repeat the existing blind spot unless the real
  executor-to-driver-to-public-observer composition is exercised.
- The outward `database_writes: 0` counter can be misinterpreted unless future
  closeouts reconcile exact DB rows and hashes.

### Setbacks

- The single authorization was consumed without generating a factory run,
  snapshot, memory window, campaign window, or campaign report.
- Six governed source calls and pre-lifecycle persistence were spent before the
  blocker.
- Two otherwise valid selected tokens were terminalized to `MANUAL_REVIEW`; no
  automatic continuation is lawful.
- The failed action added terminal campaign/discovery/Scheduler history that must
  remain preserved and distinguishable from successful memory work.

### Efficiency blockers

- Extensive focused tests cover adjacent layers but duplicate identity-rich
  fixtures instead of validating the actual inter-layer payload.
- The same incomplete slot reader is called multiple times, multiplying the
  chance that a stale projection contract escapes review.
- The command's fixed outward zero counters do not summarize already-committed
  pre-lifecycle work, forcing artifact/DB reconciliation during incident review.
- No new live attempt is efficient or safe until the narrow repair and bounded
  composition proof close.

## 16. Exact next lane

The exact next lane is:

`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Design`

That lane is design/specification only. It must freeze the one-projection repair
boundary and the proof contract in Section 11. It must not implement the repair,
run the wrapper or operational command, contact a provider, mutate the
authoritative DB, create memory, or create a new authorization.

Final status:

`AUDIT_COMPLETE_REPAIR_REQUIRED_AUTHORIZATION_CONSUMED_RUNTIME_LOCKED`
