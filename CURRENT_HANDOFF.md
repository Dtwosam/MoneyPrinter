# Printer V1 Handoff

## Current HEAD

Use `git rev-parse HEAD`. This handoff is committed with the verified
engineering change, so the containing repository commit is the authoritative
current identity. This repair started from and was reviewed against
`ac1b3f744333fc2e168afb69697e5e983c709506`.

## Authoritative DB

`data/printer_v1.sqlite3`

SHA-256: `cb0ee82c4f4be453b8e7980ee080f131af276b4a343e0ebb2861fd67285135a4`

Verified read-only identity: size `168271872`, inode `1230526`, mtime_ns
`1788627499054299713`. Development and regression tests did not mutate this
database.

## DB identity reconciliation

The historical pre-run SHA
`e01c509fc37909e300b148169c7b117ccad1505d4813d5e8a4d5a9efa9aed29c` belongs
to consumed one-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260905T163447Z_65ffb17a`. Its campaign
`20260905T164812Z-f7eb77e7352e-campaign` failed closed in
`CAMPAIGN_PRE_LIFECYCLE`: durable requests 4942-4944 were absent from the final
stage-reported and manifest sets. The authorization is permanently
non-reusable; no retry, restart, resume, successor, or authorization reuse is
implied.

## Current working capability

The bounded Solana-only, paper-only memory-factory path retains governed
source acquisition, strict measured-transport accounting, clean-memory gates,
and the 4/2/2 Standard-4H capability locks. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and trading capability remain locked.

## Latest meaningful result

The audited root cause was a refresh-ordinal-derived sequence base: initial
unknown-liquidity work had already occupied `UNKNOWN_LIQUIDITY_BACKUP|2`, then
refresh ordinal 1 attempted the same stage ID. The accounting duplicate guard
correctly raised, but the refresh exception path discarded already-completed
request IDs and coverage. The repair now allocates the next backup sequence
from the exact cycle accounting owner and carries immutable producer-owned
partial evidence through a still-failed refresh outcome. Disposable regressions
prove three completed request equivalents appear exactly once in durable,
stage-reported, and manifest sets; genuine mismatches still block.

## Known blocker

The consumed campaign cannot be rerun. This repair used disposable databases
only and performed no operational execution, operational provider call, or
Central Scheduler runtime. Retained terminal campaign history is evidence, not
an authorization.

## Next permitted action

Begin a new task with fresh sync and exact HEAD/DB identity verification. Any
further preparation requires migration/integrity/zero-work/non-reuse preflight;
any operational execution requires a newly prepared and independently reviewed
one-shot authorization plus separate explicit operator approval.
