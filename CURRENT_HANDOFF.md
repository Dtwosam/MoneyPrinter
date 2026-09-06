# Printer V1 Handoff

## Current HEAD

Use `git rev-parse HEAD`. This handoff is committed with the bounded
post-holder SQLite ownership repair. The repair started from
`f1a103e0c7c94bda9296b9b717fb1e7efbfaa219`.

## Authoritative DB

`data/printer_v1.sqlite3`

SHA-256: `e244ed70c8b3c413191255c496b328042d7192a23ea667d5061c87eda13aa5f8`

Latest retained post-run identity: size `168710144`, inode `1230526`,
mtime_ns `1788639431417133892`. The latest operational run completed cleanup
and released its lease before this development repair.

## DB identity reconciliation

The historical pre-run SHA
`cb0ee82c4f4be453b8e7980ee080f131af276b4a343e0ebb2861fd67285135a4`
belongs to consumed one-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260905T195512Z_f2e9b730`. Its campaign
`20260905T200642Z-477a285e52df-campaign` failed closed in
`CAMPAIGN_PRE_LIFECYCLE` with `OperationalError: database is locked`.
The authorization is permanently non-reusable; no retry, restart, resume,
successor, or authorization reuse is implied.

## Current working capability

The bounded Solana-only, paper-only memory-factory path retains governed source
acquisition, strict measured-transport accounting, clean-memory gates, and the
4/2/2 Standard-4H capability locks. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and trading capability remain locked.

## Latest meaningful result

The audited lock condition was nested SQLite writer ownership: after holder
persistence the main campaign connection could retain a deferred write
transaction while the coverage-blocked freeze path entered the temporal refresh
owner, whose separate connection must enqueue Scheduler-owned refresh work. The
repair now releases/commits the campaign connection immediately before that
path-owned refresh call. A focused disposable regression captures both the
pre-repair lock shape and the repaired two-writer boundary. No busy timeout,
retry, Scheduler, Source Governor, reconciliation, or fail-closed policy was
weakened.

## Known blocker

The consumed campaign cannot be rerun. This environment could edit and review
the connected GitHub repository but could not clone it for local pytest
execution because outbound GitHub DNS is unavailable. The focused regression,
directly related owner tests, `py_compile`, and `git diff --check` therefore
must be executed from the project checkout before any authorization
preparation.

## Next permitted action

Run focused development verification only for this repair. If it is green,
review the exact commit diff and confirm the authoritative DB remained
unchanged during development. Only after that may a separate fresh task begin
with exact HEAD/DB, integrity, zero-work, and non-reuse preflight. Any future
operational execution requires an entirely new independently reviewed one-shot
authorization plus separate explicit operator approval.
