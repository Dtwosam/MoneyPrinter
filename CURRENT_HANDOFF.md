# Printer V1 Handoff

## Current HEAD

Use `git rev-parse HEAD`. This handoff is committed with the verified
engineering change, so the containing repository commit is the authoritative
current identity. The repair review was verified from
`fa2c6cf5a0adfd86e6349966e6ecb283c3395819`.

## Authoritative DB

`data/printer_v1.sqlite3`

SHA-256: `3b88aa9a0ffb8c4f8beca09b78d7e56c5f1bd1a51706f280c3f3a145771af7fe`

Verified read-only state: size `167223296`, inode `1230526`, mtime_ns
`1788530617119879531`; `PRAGMA integrity_check=ok`; zero FK violations; 62
migrations through `062_pre_admission_attempt_evidence.sql`; no SQLite
sidecars; and every required active-work, supervision, lease, refresh-wait,
and Scheduler domain is zero.

## DB identity reconciliation

The prior handoff SHA
`9ac31309c4f7a6233bc9f5d77944f88cd15a16a1659f98db665524f18dcb7a23` was the
pre-state of consumed one-shot application
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260904T104053Z_9463ab6e`. That run wrote its
durable campaign history and terminated at source-request reconciliation,
leaving the proven intermediate SHA
`bfb7eb12db3107cdec5f47c80745da103cca3800c320954c3936ccde6f85e603`.

That intermediate SHA is the exact pre-campaign backup and bound DB identity
for consumed one-shot application
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260904T125630Z_001904ef`, whose campaign
`20260904T130245Z-34072c98e685-campaign` terminalized at its bounded safe
stop. It produced the current SHA. Both application markers record one use;
no retry, restart, resume, successor, or authorization reuse occurred.
Cleanup and lease release terminalized, migrations did not change, and
financial/retrieval capability tables did not change. The identity difference
is therefore expected, fully accounted durable history, not DB drift.

## Current working capability

The bounded Solana-only, paper-only memory-factory path retains governed
source acquisition, strict measured-transport accounting, clean-memory gates,
and the 4/2/2 Standard-4H capability locks. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and trading capability remain locked.

## Latest meaningful result

The repair review confirms token-local Standard-4H eligibility budgets,
cycle-scoped request accounting, canonical Pump refresh-root propagation,
later-cycle replay, and terminal accounting retain their owner boundaries and
fail-closed evidence semantics. The legacy V2.4 compressed-time test now
asserts the current contract: impossible pre-close timing is
`TIMELY_ACQUISITION_NOT_PRODUCIBLE`, creates no context evidence, and cannot
create clean memory or financial/retrieval effects.

## Known blocker

No active orphan or proven code defect is open. Canonical production
preparation now exists for the four-token Standard-4H authorization profile,
but it is strictly non-consuming: it writes only a final authorization package,
validates manifest/pre-marker parity, and creates no application marker or
runtime. Development used disposable repositories/databases only; no real
authorization or operational execution occurred. Retained terminal campaign
history is evidence, not a live blocker.

## Next permitted action

After this code commit, a new task must begin with fresh sync, exact-HEAD and
exact-DB identity, migration/integrity/zero-work/non-reuse preflight, then
prepare exactly one real authorization and independently review it. Stop before
consumption. Any operational execution remains separately subject to explicit
operator approval and its own one-shot authorization.
