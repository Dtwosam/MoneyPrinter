# Printer V1 Handoff

## Current HEAD

Use `git rev-parse HEAD`. This handoff is committed with the wrapper-bound
returned-campaign terminal truth repair. The repair started from
`b0ecbcb8830c55bb6242647cda23335201a3981e`.

## Authoritative DB

`data/printer_v1.sqlite3`

The last exact identity verified before the latest consumed operational run was
SHA-256 `e244ed70c8b3c413191255c496b328042d7192a23ea667d5061c87eda13aa5f8`,
size `168710144`, inode `1230526`, mtime_ns `1788639431417133892`.

That identity is now historical pre-run evidence. The latest child terminal did
not carry a post-run database identity, so the current authoritative DB identity
must be re-derived read-only from the local checkout before any further
preflight or authorization work.

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

The exact durable source-request reconciliation defect from execution
`20260906T101455Z-cbbcf503d01b` has not been repaired. Its source-request IDs,
stage-reported coverage, manifest coverage, and earliest ownership mismatch must
be audited from the retained local stdout/DB evidence before changing
reconciliation or source-accounting code. The consumed authorization cannot be
rerun.

## Next permitted action

First run focused development verification for this terminal-semantics repair
and re-derive the current authoritative DB identity read-only. Then audit the
latest campaign's exact durable reconciliation mismatch from retained
`child-stdout.txt` and DB rows. Do not prepare a new authorization or run
operational code until that proven reconciliation defect is repaired, verified,
and reviewed.
