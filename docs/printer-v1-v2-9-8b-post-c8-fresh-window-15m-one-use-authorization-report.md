# Printer V1 V2-9.8B Post-C8 Fresh WINDOW_15M One-Use Authorization Report

Date: 2026-08-08

Linear: `DTW-72`

## Verdict

`V2_9_8B_POST_C8_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REPORT_PASS`

The operator explicitly authorized exactly one new real operational ordinary `WINDOW_15M` cycle under DTW-72, with no retry, rerun, resume, restart, or successor. This report issues the authorization identity and freezes the package contract. It does not create a manifest or application marker and does not run Printer.

## Fresh authorization identity

`V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z`

Authorized at: `2026-08-08T12:20:00Z`

Expires at: `2026-08-09T12:20:00Z`

Validity: `86400` seconds maximum.

The ID is distinct from all historical authorization IDs established by the fresh Mac audit.

## Exact reviewed operational input

- Proven Mac branch before authorization-report alignment: `agent/v2-9-8b-post-c8-operational-window15m-rereadiness-audit`
- Proven Mac HEAD: `cd0a422d84a0076dd03ba34f1a764fc8795f6aaf`
- Authoritative DB SHA-256: `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`
- DB size: `69328896`
- DB inode: `1230526`
- DB mtime_ns: `1786022001929258221`
- migration count/head: `52 / 052_memory_observation_eligibility_layers.sql`
- integrity/FK: `ok / 0`
- WAL/SHM/journal: absent
- all inspected campaign/run/supervision/factory/window/discovery/Scheduler states: terminal only
- zero-I/O concrete-composition preflight: PASS

The final authorization JSON must bind the commit created by this report on branch `agent/v2-9-8b-post-c8-window15m-authorization-preparation`, not the older `cd0a422...` operational baseline. Before wrapper application, the Mac must be aligned non-destructively to that exact authorized report commit and the DB/readiness facts must be rechecked.

## Historical authorization non-reuse set

The final authorization JSON must include this exact lexicographically sorted `prior_authorizations_non_reusable` set:

1. `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`
2. `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`
3. `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`
4. `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`
5. `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z`
6. `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`
7. `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z`
8. `V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z`
9. `V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z`
10. `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z`
11. `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z`
12. `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z`
13. `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`
14. `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`

No historical package is reusable. Directory presence alone creates no authority.

## Required final authorization law

The one JSON package must require:

- `mode = run`
- `operator_approved = true`
- `allowed_invocation_count = 1`
- automatic retry `false`
- manual rerun `false`
- resume `false`
- restart `false`
- successor `false`
- main window `WINDOW_15M`
- `WINDOW_5M_MICRO_EVENT` support-only
- selective `WINDOW_1H` continuation `false`
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` locked
- Solana-only, Solana-memecoin-only, paper-only
- Source Governor and Central Scheduler preserved
- no paid API dependency
- no wallet/private key/signing/real funds/live execution
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, or PnL
- no scoring/ranking/confidence/weighting/embeddings/vectors

## Retained migration package

Migration execution ID remains:

`V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Migration 050 must not be rerun.

## Independent review requirement

After the report commit exists and the untracked JSON is created, independently verify its exact SHA-256, report-commit binding, temporal validity, historical non-reuse set, DB binding, launch-chain policy, one-shot flags, and absence of any marker/application for the new ID.

A package-level review may be completed before Mac alignment. Final application-boundary review additionally requires the Mac to be on the exact authorized report commit with tracked/index clean, authoritative DB unchanged, migrations/integrity/FK clean, no sidecars, terminal-only operational state, current source configuration zero-I/O validation PASS, and no competing current authority.

## Money-usefulness contribution

This report turns the completed post-C8 readiness work into one scarce, bounded permission candidate for collecting fresh `WINDOW_15M` clean-memory evidence without weakening one-shot safety or reviving stale authority.

## What remains locked

This report does not start Printer and does not authorize any second invocation. No manifest, marker, provider/source call, Source Governor/Scheduler runtime, DB mutation, memory generation, longer-window activation, retrieval, decision, BUY/SELL/HOLD, position, trade, audit, or PnL occurs here.

## Functionality Risks / Setbacks / Efficiency Blockers

- any tracked change after this report commit changes the exact authorized HEAD and must fail closed unless separately reviewed;
- DB drift before application must block;
- package expiry must block rather than be extended in place;
- historical staging remains evidence only and must not be deleted to manufacture readiness;
- the final wrapper invocation remains a separate manual step after independent review PASS.
