# Printer V1 V2-9.8B — Operational Selective WINDOW_1H Proof Command Closeout

## Final verdict

```text
V2_9_8B_OPERATIONAL_SELECTIVE_1H_PROOF_COMMAND_PASS
```

This package implements and tests the missing canonical operator command
surface. It does not apply migration 047, run an operational campaign, call a
source, invoke Scheduler runtime, or authorize the selective 1h proof.

PASS permits the manual operator-readiness review to be repeated. Migration
application and the live bounded proof remain separate, explicit operator
actions.

## Command ownership

The command remains owned by the existing canonical path:

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
  -> printer_v1.operator_cli.operational_memory_factory_command
  -> AuthoritativeLiveOperationalCampaignOwner.run_operational
  -> OriginToLifecycleCampaignDriver
  -> run_one_command_15m_factory
```

No parallel runner, provider loop, Scheduler owner, or Source Governor owner
was created.

## Exact modes

The wrapper and Python command owner now expose:

- `selective-1h-preflight`
- `selective-1h-proof`

`selective-1h-preflight` is read-only and reports zero source calls, zero
Scheduler runtime calls, and zero database writes. It fails closed unless the
Git tree is exact and clean, the authoritative DB target is quiescent and
healthy, the migration ledger includes 047, the selective implementation is
available, later windows remain locked, and the fixed proof policy is intact.

`selective-1h-proof` requires `--operator-approved`. It reuses the existing
V2-9.8B campaign owner, sets `selective_1h_continuation=True`, keeps
`continuous_four_hour=False`, and owns exactly one campaign and one cycle.

The ordinary `run` mode remains unchanged and 15m-only:

```text
selective_1h_continuation=False
```

No generic CLI flag can enable 1h through normal `run`.

## Fixed proof policy and ceilings

| Item | Ceiling / rule |
|---|---:|
| Starting tokens | maximum 2 |
| Campaigns | exactly 1 |
| Cycles | exactly 1 |
| 15m phase | 900 seconds |
| Selective continuation | 2700 seconds |
| Total command duration ceiling | 3900 seconds |
| Discovery requests | 2 |
| Governed requests per token | 45 |
| Governed requests total | 92 |
| Scheduler rows | 82 |
| Mandatory close steps reserved inside the ceilings | 4 |
| Admission-operation ceiling | 45 |
| Storage | 64 MiB |
| Failures | 20 |
| Automatic retries / restarts / successors | 0 / false / false |

The worst-case TRACK_FAST request derivation is:

```text
per token = 16 WINDOW_15M cadence/close requests
          + 5 close-time context requests
          + 24 WINDOW_1H continuation cadence/close requests
          = 45

campaign = 2 discovery + (2 * 45) = 92
```

The Scheduler derivation is:

```text
per token = 16 WINDOW_15M jobs
          + 24 WINDOW_1H jobs
          + 1 discovery/handoff allowance
          = 41

campaign = 2 * 41 = 82
```

The cadence remains owned by the committed policy: TRACK_FAST uses 60-second
15m and 120-second 1h targets (16 and 24 required snapshots); TRACK_NORMAL uses
120-second 15m and 240-second 1h targets (9 and 13 required snapshots). Close
work has capacity reserved inside the finite ceilings and cannot be replaced by
ordinary continuation snapshots.

Zero, one, or two tokens may receive the categorical `CONTINUE` outcome. Only
those tokens receive continuation work. The predecessor must be an
authoritative clean 15m episode; a raw partial window cannot authorize 1h.

## Migration, host-awake, backup, and replay requirements

- Required migration: `047_campaign_oneshot_linkage_binds.sql` must already be
  applied before the proof preflight can pass.
- This package did not apply migration 047 to `data/printer_v1.sqlite3`.
- The operator approval for the proof affirms that the host will remain awake;
  `caffeinate` is the recommended macOS guard. Lease expiry terminalizes the
  campaign fail-closed and creates no restart.
- The canonical operational backup and disposable restore-rehearsal owner must
  pass before campaign creation.
- Existing report-only replay remains zero-source, zero-Scheduler-runtime, and
  zero-write.

## Tests and checks

All tests use temporary databases, fixtures, mocked owners, or static command
inspection. They prove the wrapper modes, fixed normal/proof policy separation,
read-only preflight, missing-047 block, explicit approval, 1h-on/4h-off proof
configuration, zero/one/two continuation outcomes, one-campaign ceiling,
no retry/restart/successor, enforced Source Governor/Scheduler ceilings,
zero-source replay, and downstream locks.

The nearest migration-ledger regression fixture was updated from its stale
hard-coded migration-046 expectation to the already-committed canonical
migration-047 state. Product migration behavior was not changed.

Final verification:

- focused public-command + selective-1h tests: 29 passed;
- combined nearest operational regressions: 108 passed, 12 subtests passed;
- changed Python modules compiled successfully;
- `git diff --check` passed.

## Rollback

Revert the cohesive command commit. Normal `run` will remain 15m-only. Do not
apply or reverse migration 047 as part of this command rollback. If a later
operator separately applies 047, its own backup/restore and rollback procedure
must govern that action.

## What remains locked

- `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` operational collection
- normal-production `WINDOW_1H`
- retrieval and similarity activation
- paper decisions and BUY/SELL/HOLD
- positions, trade events, audits, and PnL
- live execution, wallets, private keys, signing, and real funds
- paid APIs
- scoring, ranking, confidence percentages, and weighted logic
- embeddings and vectors
- source fetching outside Source Governor
- runtime outside Central Scheduler
- automatic retry, restart, resume, or successor campaigns

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Setback / blocker | Mitigation |
|---|---|---|
| Migration 047 absent on the authoritative DB | Proof cannot bind campaign/factory lineage | Preflight blocks before artifact or campaign creation |
| Host sleeps during 1h continuation | Lease expiry and incomplete evidence | Keep host awake; terminal fail-closed; no restart |
| Both tokens continue | Highest bounded source/Scheduler demand | Dedicated 92/82 ceilings derived from TRACK_FAST cadence |
| Close capacity is consumed by ordinary snapshots | Incomplete or false 1h close | Four mandatory close steps are reserved inside the policy |
| Partial 15m row treated as authority | Dirty 1h continuation | Require the authoritative clean episode and categorical CONTINUE |
| Operator repeats a terminal command | Duplicate campaign risk | One campaign per invocation; no automatic successor or resume |
| Stale migration-count assertions | False regression failures | Nearest fixture now follows committed migration 047 |

## Next permitted lane

Repeat the manual operator-readiness review for one bounded operational
selective `WINDOW_1H` proof. This closeout does not itself authorize migration
047 application or the live proof.
