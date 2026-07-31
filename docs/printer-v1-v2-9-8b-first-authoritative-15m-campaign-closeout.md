# Printer V1 V2-9.8B First Authoritative WINDOW_15M Campaign Closeout

Date: 2026-07-30

Authorized launch commit:
`b5761b6501ad757eecdfc8cfabce6828d5a899bd`

Authorization record commit:
`0f91ec4175d5c3b5f2a364f417000674e9075f99`

Attempt execution id:
`20260731T002406Z-7612696c7295`

Verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`

## Boundary

Exactly one authorized campaign attempt ran. No retry, replacement campaign,
discovery-only supplement, cursor reset, recovery, 1h continuation, longer
window, retrieval, paper decision, position, trade, audit, or PnL was authorized
or executed after terminalization.

## Evidence Reviewed

- exact clean synchronized launch baseline;
- fresh zero-source preflight PASS;
- permanent one-attempt marker;
- campaign stdout/stderr and exit code;
- post-terminal `status`;
- post-terminal `report-only`;
- post-terminal `preflight-only`;
- before/after authoritative DB SHA-256;
- final Git state.

## Factual Result

The campaign command exited `1` after approximately 23 seconds with:

```text
status: OPERATIONAL_COMMAND_BLOCKED
error_message: SIX_UNIT_ACCOUNTING_BLOCKED
action_run_id: 20260731T002406Z-7612696c7295-campaign-run
campaign_source_calls: 30
restart_created: false
successor_created: false
```

The current attempt terminalized safely at the supervision level:

- supervision state: `TERMINAL`;
- terminal status: `COMPLETED`;
- first terminal cause: `SOURCE_VISIBILITY_SHORTAGE`;
- lease released;
- no new child work allowed;
- zero active Scheduler/runtime residue in the post-terminal preflight.

However, the current attempt did not produce a usable terminal campaign report.
`report-only` returned the older campaign from `20260728T224158Z-6bf2c4fd8e7e`
with 14 source calls and terminal cause `COOLDOWN_REOPEN_REQUIRED`, not the
current July 31 attempt with 30 source calls. The current attempt therefore
cannot be reconciled through the canonical report path.

## Why This Is BLOCKED_UNSAFE

The fail-closed accounting rule worked correctly by refusing to create a
synthetic matched-zero report when six-unit evidence was incomplete. But the
closeout cannot prove complete current-attempt accounting because:

1. the command reported 30 campaign source calls;
2. no current-attempt terminal report was written;
3. `report-only` replayed an older campaign with 14 source calls;
4. candidate observed/validated/eligible/selected counts for the current attempt
   are unavailable from the canonical replay;
5. the exact partial six-unit evidence for the current attempt was not surfaced
   in the supplied operator packet.

This is not an honest market-shortage closeout. The underlying first terminal
cause may be source visibility shortage, but terminal accounting/reporting is
incomplete and the durable report surface is stale for this attempt.

## Preserved Safety Properties

- one attempt only;
- permanent no-rerun marker created;
- no restart or successor;
- lease released;
- zero active campaign, run, supervision, discovery work, factory steps,
  Scheduler jobs, locks, or proof supervision after terminalization;
- migration head remained 049;
- integrity remained `ok`;
- foreign-key violations remained zero;
- locked retrieval/financial baselines remained exact;
- final Git tree remained clean;
- no wallet, private key, signing, real funds, live execution, or paid API was
  introduced.

The authoritative DB hash changed from
`e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6` to
`f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511`, which is
expected for an authoritative campaign attempt but requires exact forensic
reconciliation before any future campaign consideration.

## Money-Usefulness Contribution

The attempt proved that terminal safety and no-rerun controls remain effective
under a real accounting failure. It also exposed a money-relevant reliability
defect: a campaign can consume governed source budget and terminalize without a
current-attempt canonical report, preventing trustworthy learning from the
attempt and risking confusion with stale historical evidence.

## What This Attempt Improved

- exercised the real authoritative command once;
- confirmed fresh preflight, backup boundary, supervision, lease release, and
  fail-closed accounting behavior;
- exposed stale `report-only` selection after a report-blocked current attempt;
- preserved all retrieval and financial locks.

## What This Still Does Not Unlock

No campaign rerun, recovery, source fetch, memory generation, 1h or longer
window, V2-10, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit,
PnL, wallet, signing, real funds, paid API, scoring, ranking, confidence,
weighting, embedding, or vector capability is unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- current-attempt accounting evidence is incomplete;
- `report-only` can surface an older terminal report after a newer report-blocked
  attempt;
- source-call totals disagree across the current command error and stale replay;
- the current attempt's candidate and stage outcomes are not available through
  the canonical report surface;
- direct DB repair or report fabrication would weaken auditability and is not
  authorized;
- the permanent attempt marker correctly prevents a shortcut rerun.

## Exact Next Permitted Task

```text
V2-9.8B First Authoritative WINDOW_15M Campaign Read-Only Forensic Audit
```

The next task is audit-only. It may inspect the authoritative database and
existing artifacts read-only to reconstruct the exact current attempt lineage,
30 source operations, candidate outcomes, partial six-unit evidence, failure
summary, and why `report-only` selected the older report.

It must not mutate the DB, repair or generate a report, contact providers/RPC,
run another campaign, remove the attempt marker, invoke recovery, or unlock any
later capability.
