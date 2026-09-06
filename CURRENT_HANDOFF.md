# Printer V1 Handoff

## Current HEAD

This handoff is committed with the same-scope holder-resume collision repair.
Use `git rev-parse HEAD` for the exact committed HEAD.

## Authoritative DB

`data/printer_v1.sqlite3`

Latest post-run identity from the consumed child terminal:
SHA-256 `f0f33ec8deaf8d7bc7ef40a587dcf43537c96efc2871328dddd0651c3fa2aad6`,
size `170545152`, inode `1230526`, mtime_ns
`1788706298562345817`.

The child reported cleanup complete, lease released, zero locked Scheduler work,
and zero pending/running Scheduler work. Re-derive exact DB identity,
integrity/FK health, sidecars, and zero-active-work locally before any future
authorization package is prepared.

## Latest consumed authorization

One-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260906T143909Z_23f8f65e` was consumed exactly
once by execution `20260906T144132Z-14d9e450d867`, campaign
`20260906T144132Z-14d9e450d867-campaign`. It exited 1 in
`CAMPAIGN_PRE_LIFECYCLE` after 20 source calls and 6 DB writes. The durable
first terminal cause was
`CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS:CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS`.
The authorization is permanently non-reusable. No retry, rerun, restart,
resume, successor, or reuse is permitted or implied.

## Current working capability

The bounded Solana-only, memecoin-only, paper-only memory-factory path retains
Source Governor as sole governed source-request owner and Central Scheduler as
sole scheduler owner. Strict measured-transport, manifest, duplicate,
reconciliation, data-quality, and clean-memory guards remain fail-closed.
The 4/2/2 Standard-4H policy is unchanged. `WINDOW_5M_MICRO_EVENT` remains
support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Retrieval,
financial, position, and live-trading capabilities remain locked.

## Latest meaningful result

The post-holder canonical supply resume now distinguishes two separate
contracts correctly:

- discovery resume coverage contains only discovery/supply-owned evidence plus
  post-holder refresh evidence; holder-owned coverage is not re-owned by
  discovery;
- the cooperative same-root collision validator recognizes the exact lawful
  terminal holder request shapes that may already occupy the campaign root:
  GoPlus safety, Solana core safety, Solana holder concentration, and the
  single Solana/Helius holder backup.

The validator remains exact and fail-closed for foreign sources, wrong request
kinds, out-of-range holder ordinals, malformed keys, non-terminal rows, missing
terminal artifacts, and foreign scope identity.

Verification on GitHub Actions for the repair code:
- focused post-holder/reconciliation/holder-scope suite: 23 passed;
- shared-boundary suite: 127 passed + 7 subtests, with two legacy E.44
  assertions deselected because both fail on the pre-repair HEAD under
  superseded contracts;
- affected-module `py_compile`: passed;
- `git diff --check`: passed.

## Known blocker

No unresolved code blocker is proven in this repair lane.

Operational readiness is not established for this new HEAD or the mutated
post-run authoritative DB. The latest authorization is consumed and cannot be
reused.

## Next permitted action

Sync this exact branch HEAD locally and prove a clean tracked/staged tree.
Then run the canonical read-only authoritative-DB / migration / integrity / FK /
sidecar / zero-active-work / prior-authorization-non-reuse gates against the
post-run DB. If and only if those gates are green, a fresh authorization package
may be prepared bound to the new HEAD and current DB identity. Do not consume it
or run Printer operationally without fresh explicit operator approval.
