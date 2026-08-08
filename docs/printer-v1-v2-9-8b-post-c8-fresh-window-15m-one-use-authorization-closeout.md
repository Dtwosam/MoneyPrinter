# Printer V1 V2-9.8B Post-C8 Fresh WINDOW_15M One-Use Authorization — Closeout

Date: 2026-08-08

Linear: `DTW-72`

## Verdict

`V2_9_8B_POST_C8_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

DTW-72 is complete. Exactly one fresh one-use authorization has been created and independently reviewed. This closeout permits only the separately authorized manual one-shot wrapper invocation for that exact authorization. It does not permit retry, rerun, resume, restart, successor, second execution, direct operational-command bypass, or any broader capability.

## Exact authorization

- authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z`;
- authorization SHA-256: `a0d297ab2cb1d76bd34914366170a1b2c843fef27d6e0e617f9f54b9ae0aa57b`;
- authorized branch: `agent/v2-9-8b-post-c8-window15m-authorization-preparation`;
- authorized exact HEAD: `15978c6c54eab0243db8fe07237b6ec354e532a1`;
- authoritative DB SHA-256: `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- authorized at: `2026-08-08T12:20:00Z`;
- expires at: `2026-08-09T12:20:00Z`;
- validity: `86400` seconds;
- main window: `WINDOW_15M`;
- selective 1h continuation: `false`;
- allowed invocation count: `1`;
- retry/rerun/resume/restart/successor: all `false`.

## Fresh application-boundary review

The operator installed the exact reviewed authorization bytes on the Mac and performed the bounded pre-marker review at the exact authorized HEAD.

Observed PASS facts:

- local branch exactly `agent/v2-9-8b-post-c8-window15m-authorization-preparation`;
- local HEAD exactly `15978c6c54eab0243db8fe07237b6ec354e532a1`;
- authorization SHA exact;
- temporal status `TEMPORALLY_VALID`;
- migration guard PASS;
- authoritative DB integrity `ok`;
- foreign-key violations `0`;
- no unexpected/non-terminal operational state;
- source configuration origin `OPERATOR_CONFIGURED_APPROVED_HTTPS`;
- redacted source identity `https://solana-mainnet.g.alchemy.com/`;
- current authorization has no canonical application and no staging entry;
- no historical authorization remains temporally current;
- in-memory manifest construction PASS;
- manifest file count `13`;
- historical evidence count `5`;
- manifest not written;
- marker not written;
- runtime not started;
- tracked/index remained clean;
- DB byte identity remained unchanged.

Final operator markers:

- `DTW72_APPLICATION_BOUNDARY_PREMARKER_REVIEW_PASS`;
- `DTW72_EXACT_AUTHORIZATION_INSTALLED_AND_APPLICATION_BOUNDARY_REVIEWED`;
- `NO_MANIFEST_MARKER_OR_RUNTIME_CREATED`.

## Runtime boundary

The only next allowed action is one manual invocation through:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

with the exact authorization file and SHA above plus explicit `-OperatorApproved`.

The wrapper remains the sole one-shot application owner. No direct call to `printer_v1.operator_cli.operational_memory_factory_command` is authorized.

Once wrapper execution begins, the authorization is consumed regardless of PASS, block, safe-stop, interruption, or failure. No retry/rerun/resume/restart/successor or second execution is allowed.

## Money-usefulness contribution

This authorization converts the completed post-C8 readiness work into one bounded opportunity to collect new ordinary `WINDOW_15M` operational memory on the hardened lineage while preventing stale authority or accidental repetition.

## What remains locked

- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet/private keys/signing/real funds/live execution;
- paid API dependency;
- scoring/ranking/confidence/weighted decisions;
- embeddings/vectors;
- Source Governor bypass;
- Central Scheduler bypass.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- authorization is single-use and is consumed once wrapper execution begins, even if the child blocks or fails;
- any tracked HEAD drift or DB drift before invocation must fail closed;
- temporal expiry invalidates the package rather than allowing extension or reuse;
- runtime success is not guaranteed by authorization review;
- post-run terminal evidence must be captured before deciding whether further audit or repair work is needed.

## Stop condition

DTW-72 stops at authorization-review PASS. Proceed with exactly one manual wrapper invocation only. After it terminalizes, stop and perform terminal evidence review/closeout; do not invoke a second command.