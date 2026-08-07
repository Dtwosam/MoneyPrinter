# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Pre-Proof Readiness Review

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PRE_PROOF_READINESS_BLOCKED_THREE_REPAIRS_REQUIRED`

Baseline reviewed:

`0e26058a6a2d12cf80693dba017130bde0c21f66` — `Wire Checkpoint 8 authoritative owner invocation`

This review is audit-only. It authorizes no campaign execution, provider/RPC/WebSocket call, Scheduler runtime, Source Governor runtime, memory generation, report replay against a live/production target, or controlling WINDOW_15M proof.

## What is ready

The focused C8 implementation contracts are GREEN through the authoritative-owner invocation bridge:

- disposable proof and external authorization are mutually exclusive;
- external owner/transport overrides are forbidden in proof mode;
- canonical production DB targeting is forbidden;
- the disposable DB and artifact root are bound before mutation;
- exact full-registry fixture coverage is required;
- fixture outputs are materialized explicitly with no production constructor fallback;
- the real `AuthoritativeLiveOperationalCampaignOwner` receives the proof DI;
- the dedicated proof DB expectation/binding path contains no fabricated authorization facts;
- holder-stage accounting is required for the proof path;
- production authorization behavior remains separate.

Focused result at the reviewed baseline: 41 C8 tests GREEN.

## Blocker 1 — Full-run acceptance still hard-requires authorization-marker truth

The C8 command intentionally omits the production authorization marker when a disposable proof binding is present and persists the dedicated proof expectation instead.

However, `campaign_full_run_accounting.load_authorization_invocation_evidence()` and `evaluate_campaign_acceptance_gate()` still require production authorization-marker facts for `CAMPAIGN_PASS`, including:

- exactly one authorization marker;
- exactly one exact authorization marker;
- authorization/supervision/factory correspondence;
- exact authorization and invocation marker payload identities;
- authorization-marker and invocation-marker hashes.

That contract is correct for the production/authorized path but incompatible with C8's approved no-auth proof law.

Required repair:

- preserve the existing production/authorized acceptance law unchanged;
- add a separate C8 proof invocation-evidence branch based only on the durable proof expectation/binding plus exact supervision/factory identities;
- do not create, synthesize, or persist fake authorization id/SHA/application-marker/consumption facts;
- make full-run acceptance and its hashes mode-aware without weakening any existing production check.

## Blocker 2 — Public report-only fallback still uses the production artifact root

`report_only()` accepts an explicit replay DB and artifact root and uses the supplied artifact root when locating the canonical report directory.

But `_load_exact_terminal_summary()` still resolves `terminal-summary.json` through module-level `ARTIFACT_ROOT`. If the exact report row/artifact is absent or mismatched during a C8 replay, summary verification can inspect the wrong production artifact tree.

Required repair:

- pass the exact replay artifact root into `_load_exact_terminal_summary()`;
- preserve the existing production default when no override is supplied;
- prove disposable replay never inspects `~/PrinterOperations/v2-9-8`;
- preserve zero-source, zero-Scheduler-runtime, zero-write replay.

## Blocker 3 — Controlling proof harness/evidence package is not yet implemented

The C8 branch currently contains proof identity/fixture-routing machinery and focused structural tests, but no committed controlling proof harness that satisfies the approved bounded-proof sequence.

Before the one permitted controlling campaign, the proof harness must:

1. create one fresh canonically migrated disposable DB and fresh artifact root;
2. capture pre-run DB SHA, migration identity, integrity/FK, protected-table counts and downstream-lock counts;
3. build the exact full-registry deterministic success fixture set for exactly two lawful Solana memecoin candidates;
4. install a process-local network tripwire before calling the public coordinator;
5. record network/provider attempts and fixture transport operations independently;
6. invoke `run_operational_campaign()` exactly once with only the disposable proof capability;
7. allow the ordinary natural WINDOW_15M lifecycle to complete without compressed time or predeclared disposition;
8. run public `report_only()` exactly once against the same disposable DB/artifact root and exact campaign/run identity;
9. freeze proof summary and hashes;
10. prohibit retry, rerun, resume, restart and successor;
11. run a separate read-only independent inspector over the frozen DB/artifacts;
12. never automatically launch a second campaign if the controlling proof fails.

The deterministic success fixtures must exercise the real Source Governor, Central Scheduler, discovery/selection/tracking, holder/context, lifecycle, clean-memory, cleanup, reporting and replay owners. They may replace only external provider transports.

## Money-usefulness contribution

This review prevents a false-positive C8 proof. It ensures Printer cannot claim a successful two-token clean-memory closeout by fabricating authorization evidence, reading the wrong artifact tree, or using an incomplete proof harness.

## What this review improves

- separates production authorization truth from C8 proof truth;
- identifies the remaining replay isolation defect before proof execution;
- identifies the missing one-shot harness/network-tripwire/independent-inspection evidence package;
- preserves the real public coordinator, authoritative owner, Source Governor, Scheduler and natural 15m lifecycle as the proof subject.

## What remains locked

This review unlocks nothing. Still locked:

- the controlling C8 WINDOW_15M proof until all three blockers are repaired and a focused entry gate passes;
- provider/live execution;
- WINDOW_1H proof rerun and longer windows;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, paper-trade audits and PnL;
- wallet/private-key/signing/real-fund capability;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Required next stage

Do not run the controlling proof.

Next: one focused C8 pre-proof repair design covering only:

1. proof-aware full-run acceptance/replay evidence without fabricated authorization facts;
2. exact disposable artifact-root propagation in terminal-summary replay;
3. the repository-owned one-shot deterministic C8 proof harness, network tripwire, frozen proof summary and independent read-only inspector.

After design approval: RED contracts -> implementation -> focused GREEN/pre-proof entry gate -> exactly one controlling proof -> independent inspection -> C8 closeout.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Reusing production authorization checks unchanged in C8 makes a lawful no-auth proof impossible.
2. Weakening those checks globally to make C8 pass would create an authorization regression; mode separation is mandatory.
3. A report-only artifact-root fallback to production can make replay inspect unrelated evidence.
4. A fixture harness without a low-level network tripwire cannot prove zero provider fallback independently.
5. A deterministic fixture that injects outcomes, skips Source Governor/Scheduler, compresses lifecycle time, or predeclares disposition would not prove the public composition.
6. The natural 15m proof is expensive to repeat; therefore all deterministic entry checks must pass before the single controlling run.
