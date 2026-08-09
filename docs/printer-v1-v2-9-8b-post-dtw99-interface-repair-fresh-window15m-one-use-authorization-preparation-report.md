# Printer V1 V2-9.8B Post-DTW99 Interface-Repair Fresh WINDOW_15M One-Use Authorization Preparation

## Status

`FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_READY`

This document freezes the preparation contract for exactly one fresh post-DTW99 `WINDOW_15M` authorization. It creates no authorization, application marker, runtime permission, source work, Scheduler work, or memory.

## Baseline

- preparation branch: `agent/v2-9-8b-post-dtw99-interface-repair-window15m-authorization-preparation`
- parent rereadiness closeout: `d0ceb81967402358296135374ab81024a92161dc`
- rereadiness verdict: `V2_9_8B_POST_DTW99_INTERFACE_REPAIR_WINDOW_15M_REREADINESS_PASS`
- DTW99 authorization remains permanently consumed and non-reusable.

The exact preparation HEAD is the commit containing this document and must be read from Git after commit creation. Any authorization package created from this preparation must bind to that exact HEAD and require a clean tracked worktree.

## Authoritative DB binding

The new authorization must bind the post-DTW99 authoritative DB identity proven by rereadiness:

- SHA-256: `d896e03e99cff954caa8f9f936f28926481ea4ed57f4a875b1189757cef9a9ab`
- size: `74760192`
- inode: `1230526`
- mtime_ns: `1786294694745597037`
- migration count: `54`
- migration head: `054_pre_lifecycle_discovery_refresh_wait.sql`
- migration-ledger digest: `b2e26dd36cee8a8fff4839632bb95e02842ed970f6c0ff96ccf08620386ffd2d`

Any DB drift blocks package creation.

## Authorization contract

Reuse the established WINDOW_15M one-use authorization machinery and schema. Do not invent a new package format.

The fresh authorization must:

- have a new unique authorization ID;
- authorize exactly one ordinary `WINDOW_15M` invocation;
- expire 24 hours after creation;
- bind exact preparation branch, exact preparation HEAD, and exact DB identity above;
- require a clean tracked worktree;
- preserve the repaired 900-second pre-lifecycle acquisition horizon;
- preserve the cumulative 30-operation discovery budget;
- preserve zero automatic retry/rerun/restart/resume/successor semantics;
- preserve all V1 locks;
- keep `WINDOW_1H/4H/12H/24H` locked;
- keep `WINDOW_5M_MICRO_EVENT` support-only;
- have no application marker before invocation.

Historical consumed authorizations, including DTW99 `V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z`, remain permanently non-reusable.

Retained MIG050 provenance-package fields must continue to resolve through the established fixed `MIGRATION_PACKAGE_ROOT`; they are provenance evidence, not the current DB migration head. The separate DB binding above remains authoritative at migration 054.

## Required zero-I/O preparation gates

Before package creation, re-prove:

- exact preparation Git branch/HEAD and clean tracked tree;
- authoritative DB identity, integrity `ok`, FK `0`, sidecars none, unchanged during preparation;
- migration guard PASS at 54/54;
- source contract READY with zero external requests;
- ordinary concrete WINDOW_15M composition READY;
- runtime dependency preflight READY;
- holder budget READY;
- zero active campaign/run/supervision/discovery/factory/proof/Scheduler residue;
- temporal refresh wait table zero total / zero `WAITING` or `CLAIMED`;
- locked capability baseline PASS;
- historical null-position paper-audit invariant preserved;
- repaired `build_graduated_supply` temporal-owner interface remains present and the ordinary production owner path remains ready;
- historical authorization non-reuse set remains exact and current candidate ID is not already present/consumed.

## Money-usefulness contribution

This preparation permits one fresh attempt to reach real governed market truth with the DTW99 interface seam repaired, while preventing reuse of consumed attempts or execution against drifted Git/DB state.

## What this improves

- freezes the exact post-repair Git and DB identities for the next attempt;
- preserves the bounded 3-of-4 wait/refresh path;
- prevents another one-use attempt from being spent on stale or mismatched prerequisites.

## What this does not unlock

This document does not create an authorization and does not permit runtime by itself. It does not prove eligible supply, lifecycle entry, clean memory, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, PnL, or any later window.

## Proof before completion

A package prepared under this contract must receive an independent authorization review before wrapper invocation. Runtime is allowed only after that review passes.

## Functionality Risks / Setbacks / Efficiency Blockers

- live eligible supply may still honestly remain below the four-candidate reserve requirement;
- the 900-second acquisition horizon and 30-op source budget remain hard ceilings and must not be weakened to force success;
- stale test fixtures remain outstanding but rereadiness classified them as non-live-reachable;
- the production `**supply_kwargs` pattern remains a future interface blind spot, although the DTW99 parameter now has a real-boundary regression;
- any Git or DB drift after package preparation requires a fresh review and blocks invocation.

## Stop condition

Preparation/package creation only. No application marker, wrapper invocation, Printer runtime, `WINDOW_15M`, or later capability.