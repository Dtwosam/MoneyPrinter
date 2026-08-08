# Printer V1 V2-9.8B Post-C8 Fresh WINDOW_15M Authorization Package Independent Review

Date: 2026-08-08

Linear: `DTW-72`

## Verdict

`V2_9_8B_POST_C8_FRESH_WINDOW_15M_AUTHORIZATION_PACKAGE_LEVEL_INDEPENDENT_REVIEW_PASS`

This is a package-level, pre-marker, pre-runtime independent review. It does not apply or consume the authorization and does not run Printer.

Reviewed authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z`.

Authorization JSON SHA-256: `a0d297ab2cb1d76bd34914366170a1b2c843fef27d6e0e617f9f54b9ae0aa57b`.

Authorized branch: `agent/v2-9-8b-post-c8-window15m-authorization-preparation`.

Exact authorized report HEAD: `15978c6c54eab0243db8fe07237b6ec354e532a1`.

Authorized at `2026-08-08T12:20:00Z`; expires `2026-08-09T12:20:00Z`; validity `86400` seconds.

## Independent package checks

PASS:

- fresh authorization ID relative to the 14 historical IDs from the Mac audit;
- package contains exactly one file, `final_authorization.json`;
- exact JSON SHA reproduced;
- exact report-commit binding reproduced;
- authoritative DB binding exact: SHA `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`, size `69328896`, inode `1230526`, mtime_ns `1786022001929258221`, migration `52 / 052_memory_observation_eligibility_layers.sql`;
- historical non-reuse set has 14 unique sorted IDs and excludes current ID;
- temporal window exactly 86400 seconds and valid at review time;
- command `run`, operator-approved, invocation count one;
- automatic retry/manual rerun/resume/restart/successor all false;
- main window `WINDOW_15M`, selective 1h false, 5m support-only, longer windows locked;
- Source Governor and Central Scheduler bypasses false;
- no retrieval/decision/BUY/SELL/HOLD/position/trade/audit/PnL/wallet/private-key/signing/real-fund/live-execution/paid-API/scoring/ranking/confidence/weighting/embedding/vector authority;
- manifest false, marker false, runtime false.

Git comparison from `cd0a422d84a0076dd03ba34f1a764fc8795f6aaf` to the authorized report HEAD contains documentation/control-plane files only, so production launch-chain code is unchanged from the exact re-readiness code that passed zero-I/O concrete composition.

## Application-boundary checks still required

Before wrapper invocation, the Mac must align non-destructively to exact authorized HEAD `15978c6c54eab0243db8fe07237b6ec354e532a1`, install the exact reviewed JSON untracked at its canonical package path, reproduce its SHA, recheck tracked/index clean, DB identity, migration/integrity/FK/sidecars, terminal-only state, temporal validity, migration-ledger guard review, historical-package manifest construction in memory only, zero-I/O source configuration, and absence of a pre-existing application/marker or competing current authority.

Any mismatch blocks without replacing this authorization.

Runtime remains a separate manual one-shot wrapper action after final application-boundary review PASS.
