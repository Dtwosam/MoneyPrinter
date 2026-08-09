# Printer V1 V2-9.8B — Post-DTW93 Fresh WINDOW_15M One-Use Authorization Closeout

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW93_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

The fresh post-DTW93 authorization package passed independent review. This closeout authorizes at most one future ordinary `WINDOW_15M` wrapper application under the existing one-shot contract. It does not itself invoke the wrapper or start Printer runtime.

## Controlling source stack and lane law

The active Printer V1 source stack remains:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside this stack, not the sole source of truth.

The permitted runtime remains two-token ordinary `WINDOW_15M` only. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_1H+`, retrieval and all paper/financial capabilities remain locked.

## Exact Git binding

- rereadiness closeout: `e65b5476de12a1319fd8a66ec160d497088f33ca`
- frozen preparation branch: `agent/v2-9-8b-post-dtw93-window15m-authorization-preparation`
- frozen authorized HEAD: `6c30377c28d62c578020ad3f7d32e020c393fc0e`

The authorization package binds exactly that branch and HEAD. The frozen preparation branch must not move before application.

## Fresh authorization identity

- authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260809T011312Z`
- package path: `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T011312Z/final_authorization.json`
- package SHA-256: `db453fa7c14bd892bf13fb7fe9a96a43f6beb29b7d33ad5858fafcd3b1ac3eb4`
- authorized at: `2026-08-09T01:13:12Z`
- expires at: `2026-08-10T01:13:12Z`
- temporal status at preparation: `TEMPORALLY_VALID`
- allowed invocation count: one
- automatic retry: false
- manual rerun: false
- resume: false
- restart: false
- successor: false

The preceding empty directory `V2_9_8B_WINDOW_15M_AUTH_20260804T014448Z` was independently inspected on the operator Mac, contained no authorization file and had no application marker, and was removed with `rmdir`. It is not an authorization and is not added to the non-reuse trust root.

Historical non-reusable authorization count remains exactly 22, including consumed DTW93 authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z`.

## Authoritative database binding

The package binds exactly:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `6a0f7afc2f4d542854bcf7f1db6857c6405f50f9085dded922fc419e938bfc35`
- size: `71127040`
- inode: `1230526`
- mtime_ns: `1786227161080487776`
- migration count: `53`
- migration head: `053_pilot_input_readiness_route_domain.sql`

Preparation reported the database byte identity unchanged throughout package generation/review.

## Readiness and package review evidence

The operator-supplied machine output reported:

- overall status: `PASS`
- package verdict: `V2_9_8B_POST_DTW93_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PACKAGE_REVIEW_PASS`
- migration guard prepare: PASS
- migration guard review: PASS
- non-Git readiness: READY
- source contract: READY
- source-contract external requests: 0
- concrete composition: READY
- runtime dependency: READY
- holder budget: READY
- active campaign/run/supervision/discovery/factory/scheduler/proof counts: all zero
- locked Scheduler jobs: 0
- historical null-position paper audit rows preserved: 1
- source calls: 0
- Scheduler runtime calls: 0
- database writes: 0
- application marker created: false
- Printer runtime started: false
- Scheduler runtime started: false
- `WINDOW_15M` started: false
- wrapper invoked: false

Pre-marker provenance review reported:

- allowed file count: `22`
- allowed file-set SHA-256: `ee026b9179b3f74eeb95f03c06e32980dc3636973e49718ae9043a956330b4ee`
- manifest SHA-256: `267d086d0771429aa5db47cb11397535a6286683293ee19f6840c22fec1a7bf1`

These checks establish authorization readiness only. They do not prove future provider availability, candidate supply, lifecycle completion or clean-memory production.

## DTW93 repair and host-awake prerequisite

The post-DTW93 local-validation observer repair is already implemented and bounded-offline-proved. The subsequent rereadiness audit reconciled the repaired Git state and authoritative DB before this authorization was prepared.

The previous real attempt's controlling terminal cause was `LEASE_RENEWAL_LEASE_EXPIRED`, consistent with host suspension. Therefore any application of this authorization must preserve the existing heartbeat/lease fail-closed contract and launch the one-shot wrapper under the approved macOS host-awake safeguard `caffeinate -dimsu` (or an exact repository-approved equivalent).

Do not widen lease or heartbeat limits as a shortcut.

## Money-usefulness contribution

This authorization permits one bounded chance to test whether the repaired accounting path can now complete real 15-minute evidence under stable host supervision. It may grow trustworthy memory only if the campaign itself earns acceptance; authorization readiness is not a profit or memory-quality claim.

## What this lane improves

- binds the repaired exact Git HEAD to the current authoritative DB identity;
- preserves all historical authorization non-reuse rules;
- confirms zero-I/O construction/readiness before application;
- carries the DTW93 accounting repair into one independently reviewable real attempt;
- makes host-awake protection mandatory for the later runtime application.

## What this lane still does not unlock

This closeout does not unlock or authorize:

- more than one wrapper application;
- retry, rerun, resume, restart or successor;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H` or `WINDOW_24H`;
- retrieval;
- paper decisions or BUY/SELL/HOLD;
- paper positions, trade events, paper trade audits or PnL;
- wallet/private-key/signing/real-fund/live execution;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors;
- Source Governor or Central Scheduler bypass.

## Functionality Risks / Setbacks / Efficiency Blockers

- Host suspension can still invalidate the campaign if the host-awake guard is omitted or ineffective.
- Provider/source/candidate conditions can still block the campaign honestly.
- The authoritative DB must remain byte-identical to the authorization binding until application begins.
- Any Git drift on the frozen preparation branch invalidates this authorization.
- The authorization expires at `2026-08-10T01:13:12Z` and must not be used afterward.
- A wrapper start consumes the authorization regardless of campaign outcome.
- A successful process exit alone is not campaign PASS; terminal campaign acceptance and clean-memory outcome must be reviewed afterward.

## Exact application boundary

The next permitted action is exactly one manual invocation of `scripts/Start-PrinterV1-Window15M-OneShot.ps1` using this authorization file and SHA-256, with `-OperatorApproved`, under the approved macOS host-awake safeguard.

After that single invocation starts, the authorization is permanently consumed. Do not retry or rerun it for any reason. Reconcile the resulting terminal evidence before any later lane.

No wrapper invocation occurs in this closeout document.
