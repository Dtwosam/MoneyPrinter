# Printer V1 Handoff

## Current HEAD

This handoff is committed with the post-holder refresh evidence-carrier repair.
The repair started from `b3b6e3d5ffa80d9bee65ec26990f0e11eb45a065`; use
`git rev-parse HEAD` for the committed final HEAD.

## Authoritative DB

`data/printer_v1.sqlite3`

Current post-run identity, derived read-only: SHA-256
`400f63ef7286a71bb751e8b7b2ecfd50cb3c03ccd66e91f55479195e2e1ab769`, size
`169398272`, inode `1230526`, mtime_ns `1788690300902508255`. `integrity_check`
is `ok`, `foreign_key_check` has zero rows, and no WAL, SHM, or journal sidecars
are present. The historical pre-run identity remains non-current evidence only.

## DB identity reconciliation

One-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260906T100937Z_10850240` was consumed exactly
once. Its execution `20260906T101455Z-cbbcf503d01b`, campaign
`20260906T101455Z-cbbcf503d01b-campaign`, returned a pre-lifecycle terminal with
first cause `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` and
`lifecycle_started=False`. The authorization is permanently non-reusable; no
retry, rerun, restart, resume, successor, or reuse is implied.

## Current working capability

The bounded Solana-only, paper-only memory-factory path retains governed source
acquisition, strict measured-transport accounting, clean-memory gates, and the
4/2/2 Standard-4H capability locks. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and trading capability remain locked.

## Latest meaningful result

The preceding SQLite writer-release repair allowed the latest run to progress
past the former `database is locked` blocker. That run then exposed a separate
terminal-semantics defect: a normally returned pre-lifecycle campaign block had
`campaign_pass=False`, yet the public CLI unconditionally wrote child exit 0
with `success=True`. The repair now requires an explicit boolean
`campaign_pass` for wrapper-bound campaign modes and maps it directly to child
exit truth: pass -> 0, blocked -> 1; missing/invalid truth fails closed. Campaign
ownership, reconciliation, Source Governor, Central Scheduler, timeout, retry,
and accounting policy are unchanged.

## Known blocker

The consumed authorization cannot be rerun. Its exact source reconciliation
defect is repaired in development only: the post-holder freeze-coverage wait
called the temporal refresh owner but dropped its completed outcome. Durable
refresh IDs `4979,4980,4981,4982` then had no stage-reported or manifest
coverage. The repair carries that exact owner-produced evidence into the existing
final-refresh reconciliation fields; it does not weaken reconciliation or add
requests. No authorization may be prepared yet.

## Next permitted action

Focused verification passed: the new disposable regression plus the affected
refresh/reconciliation tests (`13 passed`), wrapper terminal tests (`56 passed,
7 subtests`), `py_compile`, and `git diff --check`. Review the exact repair diff
only. Then hard stop before any authorization preparation, provider call, or
operational execution.
