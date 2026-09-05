# Printer V1 Handoff

## Current HEAD

Use `git rev-parse HEAD`. This handoff is committed with the verified
engineering change, so the containing repository commit is the authoritative
current identity. The repair review was verified from
starting HEAD `7461198883351ef985a056a959ad5a57167d4290`.

## Authoritative DB

`data/printer_v1.sqlite3`

SHA-256: `e01c509fc37909e300b148169c7b117ccad1505d4813d5e8a4d5a9efa9aed29c`

Verified read-only identity: size `167768064`, inode `1230526`, mtime_ns
`1788614471640591606`. Development and regression tests did not mutate this
database.

## DB identity reconciliation

The prior SHA
`3b88aa9a0ffb8c4f8beca09b78d7e56c5f1bd1a51706f280c3f3a145771af7fe` is the
historical pre-run identity for consumed one-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260905T121103Z_69a40595`. Its campaign
`20260905T131106Z-c212affa13ae-campaign` failed closed in
`CAMPAIGN_PRE_LIFECYCLE`: durable requests 4928/4929 were absent from both the
stage-reported set and manifest. The marker is consumed and permanently
non-reusable; no retry, restart, resume, successor, or authorization reuse is
implied.

## Current working capability

The bounded Solana-only, paper-only memory-factory path retains governed
source acquisition, strict measured-transport accounting, clean-memory gates,
and the 4/2/2 Standard-4H capability locks. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and trading capability remain locked.

## Latest meaningful result

The repair binds each initial/refresh GeckoTerminal fresh-pool transport to its
truthful `FRESH_POOL_NOMINATION` opportunity identity, then carries completed
pre-lifecycle refresh request IDs and coverage independently through the
acquisition ledger into final campaign reconciliation. The reproduced branch
now proves durable IDs equal stage-reported IDs equal manifest IDs without
weakening duplicate transport or reconciliation guards.

## Known blocker

The consumed campaign cannot be rerun. This repair used disposable databases
only and performed no operational execution, provider call, or Central
Scheduler runtime. Retained terminal campaign history is evidence, not an
authorization.

## Next permitted action

Begin a new task with fresh sync and exact HEAD/DB identity verification. Any
further preparation requires migration/integrity/zero-work/non-reuse preflight;
any operational execution requires a newly prepared and independently reviewed
one-shot authorization plus separate explicit operator approval.
