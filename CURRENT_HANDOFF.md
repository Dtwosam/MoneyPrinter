# Printer V1 Handoff

## Current HEAD

This handoff is committed with the post-holder non-quantum resume repair.
Use `git rev-parse HEAD` for the exact committed HEAD.

## Authoritative DB

`data/printer_v1.sqlite3`

Latest post-run identity from the consumed child terminal:
SHA-256 `6cd6e9c3135ba92fd9c5490ffb76f827a3989cb60f829c36d41da619f311c180`,
size `171319296`, inode `1230526`, mtime_ns
`1788709511519326180`.

The child reported cleanup complete, lease released, zero locked Scheduler work,
zero pending/running Scheduler work, and zero Scheduler runtime calls.
Re-derive exact DB identity, integrity/FK health, sidecars, and zero-active-work
locally before any future authorization package is prepared.

## Latest consumed authorization

One-shot authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260906T151614Z_ea7f69c4` was consumed exactly
once by execution `20260906T152505Z-1c1ea941dc1c`, campaign
`20260906T152505Z-1c1ea941dc1c-campaign`. It exited 1 in
`CAMPAIGN_PRE_LIFECYCLE` after 23 source calls and 6 DB writes. The durable
first terminal cause was
`CampaignSixUnitError:SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID:20260906T152505Z-1c1ea941dc1c-campaign|20260906T152505Z-1c1ea941dc1c-campaign-run|20260906T152505Z-1c1ea941dc1c-cycle|DIRECT_MIGRATION|1`.
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

The failed run proved that post-holder canonical resume reached beyond the
same-scope holder-collision repair but then re-entered campaign-start direct
migration and attempted to seal deterministic `DIRECT_MIGRATION|1` a second
time.

The repair keeps the six-unit duplicate guard unchanged and fixes the resume
owner instead:

- non-quantum cooperative resume is explicitly existing-inventory continuation;
- it skips campaign-start direct migration, fresh nomination, unknown-liquidity
  backup, and early protocol-confirmation stages;
- it rehydrates the canonical graduated registry and continues through the
  durable-sequenced market path;
- the first pass's exact `StageBudget` snapshot is restored and required, so
  resume cannot regain already-spent stage-specific capacity;
- later-cycle cooperative quantums remain phase-driven and unchanged.

Verification on GitHub Actions for the repair code:
- focused post-holder/reconciliation/holder-scope/resume suite: 25 passed;
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
