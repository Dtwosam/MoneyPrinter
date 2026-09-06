# Printer V1 Handoff

## Current HEAD

This handoff is committed with the frozen post-holder refresh carrier repair.
Use `git rev-parse HEAD` for the committed final HEAD.

## Authoritative DB

`data/printer_v1.sqlite3`

Latest post-run identity from the consumed child terminal: SHA-256
`f6e07ca0f32a70e60f6821f44074c73356f57b0d56e98d81e48e92a4f05f46b4`,
size `170061824`, inode `1230526`, mtime_ns `1788696345906968820`.
The child reported cleanup complete, lease released, and zero active/locked
scheduler work. Re-derive integrity/FK health read-only before any future
authorization preparation.

## Latest consumed authorization

One-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260906T111524Z_28455922` was consumed exactly
once. Execution `20260906T114531Z-8cc313cae90d`, campaign
`20260906T114531Z-8cc313cae90d-campaign`, exited 1 in
`CAMPAIGN_PRE_LIFECYCLE` after 22 source calls and 6 DB writes. The durable
first terminal cause was
`FrozenInstanceError:cannot assign to field 'diagnostics'`. The authorization
is permanently non-reusable; no retry, rerun, restart, resume, successor, or
reuse is implied.

## Current working capability

The bounded Solana-only, paper-only memory-factory path retains governed source
acquisition, strict measured-transport accounting, clean-memory gates, and the
4/2/2 Standard-4H capability locks. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and trading capability remain locked.

## Latest meaningful result

The prior post-holder reconciliation repair reached its intended live branch,
but tried to assign a replacement diagnostics mapping directly onto
`GraduatedSupply`, which is a frozen dataclass. The repair now preserves that
immutable carrier with `dataclasses.replace(..., diagnostics=...)`. The focused
regression uses the real frozen `GraduatedSupply` type so this exact failure
cannot pass through a helper-only test again. Source Governor, Central
Scheduler, retry, request-budget, reconciliation, and capability policy are
unchanged.

## Known blocker

The repair has not yet been executed in the local development environment.
No new authorization may be prepared until the focused regression and affected
reconciliation tests pass and the exact repair diff is reviewed.

## Next permitted action

Sync this repair HEAD locally. Run the focused frozen-carrier regression plus
the affected post-holder refresh/reconciliation tests on disposable state,
`py_compile`, and `git diff --check`; then review this exact repair diff.
Hard stop before any new authorization preparation, provider call, or
operational execution.
