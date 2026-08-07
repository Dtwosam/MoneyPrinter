# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Disposable Public Composition Proof Design

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PUBLIC_COMPOSITION_PROOF_DESIGN_APPROVED`

- Checkpoint 8 baseline: `1ceefb94746ea04152adb0fc3265048e258617de`
- Audit commit: `5177af1f08c4ab7cc060b31b68ef26f75057a130`
- Audit verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_PUBLIC_COMPOSITION_AUDIT_CONFIRMED_FOUR_BLOCKERS`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-8-full-disposable-public-composition-proof`
- Linear: `DTW-34`

This design resolves the four audit blockers without creating a second operational runner, weakening the production authorization boundary, replacing the authoritative campaign owner, using provider execution, or unlocking any downstream financial capability.

No proof run is authorized by this design alone.

## Design goal

Make the existing ordinary public coordinator `run_operational_campaign()` provable end-to-end on one disposable migrated DB with a complete deterministic fixture implementation of the ordinary composition registry.

The C8 proof path must preserve the real:

- public coordinator;
- `AuthoritativeLiveOperationalCampaignOwner`;
- Source Governor ownership/accounting;
- Central Scheduler ownership;
- natural ordinary `WINDOW_15M` lifecycle;
- campaign/full-run accounting;
- cleanup and lease release;
- clean-memory closeout;
- canonical terminal report publication;
- report-only replay.

Only external capabilities differ: the database is disposable and every provider transport is an explicit fixture.

## Non-goals

C8 does not:

- use or consume a final one-shot authorization;
- change `window_15m_one_shot_wrapper`;
- permit production DB execution without authorization;
- create a fake campaign owner;
- create a second Source Governor or Scheduler;
- compress or predeclare natural lifecycle dispositions;
- run `WINDOW_1H` or longer windows;
- activate retrieval or paper/financial paths.

## 1. One public coordinator, one optional proof capability

Extend the existing ordinary callable only:

`run_operational_campaign(..., disposable_proof=None)`

and thread the same optional capability into `_run_operational_campaign()`.

There is no new CLI mode and no second operational runner.

Rules:

- `main(... run ...)` never constructs or accepts the proof capability;
- the one-shot wrapper never constructs or accepts it;
- production behavior when `disposable_proof is None` is byte-for-byte/contract-equivalent to current behavior;
- `disposable_proof` is legal only for `_NORMAL_CAMPAIGN_POLICY`;
- `disposable_proof` and external `git_provenance_authorization` are mutually exclusive;
- proof capability targeting the canonical production DB is rejected before artifact or DB mutation;
- proof capability with any provider/live fallback allowed is rejected before mutation.

This resolves blocker 1 without weakening the normal validated-authorization requirement.

## 2. Typed two-phase disposable proof identity

Add a dedicated proof-only type in a small C8 module, for example:

`DisposablePublicCompositionProofPlan`

Pre-mutation fields:

- proof schema/version;
- proof id;
- resolved disposable DB path;
- pre-mutation DB SHA-256;
- canonical migration count;
- canonical migration head;
- resolved disposable artifact root;
- exact composition-registry label tuple/hash;
- `provider_execution_allowed=False`;
- `automatic_retry_allowed=False`;
- `manual_rerun_allowed=False`;
- `resume_allowed=False`;
- `restart_allowed=False`;
- `successor_allowed=False`.

The coordinator validates the plan before any artifact/campaign creation.

After it generates the real execution/campaign/run/cycle/configuration identities, it derives one immutable invocation capability:

`DisposablePublicCompositionProofBinding`

Additional bound fields:

- execution id;
- campaign id;
- campaign run id;
- cycle id;
- configuration id;
- DB target identity;
- exact fixture-composition manifest hash.

No authorization id, authorization SHA, application-marker SHA, authorization consumption fact, or fake one-shot invocation history is placed in this type.

## 3. Separate proof DB-binding law; production binding unchanged

Do not overload `AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF` with fake authorization values.

Add a separately typed target kind, for example:

`DISPOSABLE_PUBLIC_COMPOSITION_PROOF`

and a dedicated durable expectation, for example:

`DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_V1`.

The configuration-owned proof expectation must contain only proof-owned truth:

- target kind;
- exact resolved non-production DB path;
- exact pre-mutation SHA-256 / DB target identity;
- migration count/head;
- proof id and proof schema version;
- execution/campaign/run/cycle/configuration identities;
- exact fixture-composition manifest hash;
- provider execution false;
- all retry/rerun/resume/restart/successor flags false.

Validation order at `fifteen_minute_only=True`:

1. if the existing production/authorized binding is present, use the existing law unchanged;
2. else if a C8 proof binding is present, require the dedicated proof expectation and validate it exactly;
3. else fail as today.

The C8 proof binding must fail on:

- canonical production DB path;
- missing/changed DB SHA;
- migration mismatch;
- ownership identity drift;
- fixture-manifest drift;
- provider execution allowed;
- any reuse flag true.

This resolves blocker 2 without disabling database-target validation.

## 4. Exact full-registry fixture composition

Add one typed runtime fixture registry owned beside the existing composition registry, for example:

`Window15MFixtureComposition`.

It contains an ordered mapping:

`COMPOSITION_MATRIX label -> zero-I/O fixture builder`

Validation before first mutation must require:

- labels exactly equal `ordinary_window_15m_builder_identities()`;
- same order/identity hash as the production registry;
- no missing labels;
- no extra labels;
- every builder callable;
- every built adapter/transport explicitly fixture-marked;
- no production/default fallback;
- zero external requests while validating builders.

Introduce an explicit fixture transport marker if needed, parallel to existing `ProductionFixtureAdapter`, so Pump/secondary raw transport shapes cannot be mistaken for production implementations.

The proof registry is runtime-only; durable evidence stores only its stable manifest/identity, never Python callables.

## 5. Derive existing injection seams; do not create parallel source logic

The proof coordinator converts the validated fixture registry into the existing dependency-injection surfaces already owned by each stage.

Examples include:

- Pump origin transport;
- secondary discovery transport;
- direct migration transport;
- graduation verifier factory;
- DexScreener discovery/front-door factories;
- GeckoTerminal nomination/reconciliation factories;
- exact-pair lifecycle primary/fallback adapters;
- preclose CoinGecko/GoPlus/Jupiter adapters;
- holder primary/backup adapters.

`build_graduated_supply()` already accepts explicit verifier, DexScreener, GeckoTerminal, locator, and nomination transport factories. C8 should populate those existing parameters from the fixture registry instead of patching provider modules.

Holder/preclose/lifecycle context factories must likewise receive the corresponding fixture-derived factories through their existing DI surfaces.

No fixture builder may be omitted and allowed to fall back to a production constructor.

This resolves blocker 4.

## 6. Defense-in-depth network tripwire

The controlling C8 proof harness installs a process-local network tripwire before invoking the public coordinator.

It must fail immediately if any non-fixture path attempts external network creation, including the standard HTTP/RPC/WebSocket mechanisms reachable by Printer.

The exact fixture-registry validation is the primary guarantee; the tripwire is independent proof evidence that no provider fallback escaped that guarantee.

The tripwire is proof-harness-only and is not production runtime behavior.

Proof report must record:

- provider/network attempt count = 0;
- fixture transport operation count > 0;
- exact fixture registry manifest/hash.

## 7. Holder-stage accounting independent of external authorization

For an ordinary C8 proof, accountable holder work must use the same `_seal_holder_stage` owner used by the authorized path.

Coordinator rule:

- use `_seal_holder_stage` when external authorization is present **or** when a validated C8 disposable proof capability is present;
- leave selective/unrelated paths unchanged.

Do not synthesize holder identities.

The holder transport ledger remains the source of owner-side transport evidence, and the transport observer remains the independent action-local measurement side.

Owner/action-local equality remains mandatory.

This resolves blocker 3.

## 8. Disposable DB and artifact isolation

The proof harness creates a fresh temporary/disposable DB using the canonical migration owner.

Before invoking the coordinator it records:

- DB path;
- SHA-256;
- migration count/head;
- integrity/FK result;
- protected-capability table counts.

The DB path must not equal the canonical production DB path.

Artifacts go to a fresh disposable C8 artifact root, never `~/PrinterOperations/v2-9-8` production evidence.

The proof capability binds both exact locations before mutation.

After proof, the disposable DB and artifacts are retained long enough for independent inspection; no automatic second campaign is allowed.

## 9. Ordinary natural time/lifecycle law

C8 must preserve the operational owner restriction that rejects:

- `compressed_two_token_proof_plan`;
- externally supplied/predeclared `operational_natural_disposition`.

The controlling success proof is one ordinary natural `WINDOW_15M` lifecycle.

No fake window-close timestamp, no predeclared outcome, and no 1h continuation.

Fixture source responses may be deterministic by request identity/ordinal, but lifecycle/Scheduler ownership and close timing remain the real ordinary path.

## 10. Deterministic success fixture

The controlling fixture set must deterministically produce exactly two lawful Solana memecoin tracking candidates and sufficient clean evidence for both current-run windows.

The fixture must preserve real owners/gates:

- exact mint/pair identities;
- valid present-pool/migration evidence as required by the chosen admission routes;
- liquidity above existing floor;
- tracking handoff eligible;
- holder/context evidence structurally valid;
- exact-pair lifecycle snapshots at the real requested boundaries;
- sufficient preclose context;
- no malformed/stale/source mismatch;
- no injected outcome or score/rank/confidence.

Do not bypass selection, tracking, holder, E2Q, E2Z, Source Governor, or Scheduler gates.

## 11. Exact successful closeout acceptance

The C8 controlling success proof passes only if all are true.

### Public composition

- exactly one call to `run_operational_campaign()` with the validated disposable proof capability;
- real `AuthoritativeLiveOperationalCampaignOwner` used;
- no fake owner argument;
- ordinary policy / `WINDOW_15M` only;
- no authorization object;
- no provider/network execution.

### Lifecycle / memory

- exactly two campaign-owned terminal `WINDOW_15M` windows;
- both current-run memory windows are closed E2Q clean candidates;
- both have canonical `CLEAN_MEMORY` episodes;
- both episodes have fingerprints;
- no unrelated clean-memory promotion;
- `clean_memory_outcome_pass=True`;
- campaign full-run acceptance verdict `CAMPAIGN_PASS`.

This matches the existing `build_current_run_clean_memory_outcome()` contract, which requires all current-run windows to be clean candidates with one clean episode and fingerprint each.

### Terminal / cleanup

- precise first-terminal cause/status is internally consistent;
- supervision `TERMINAL`;
- cleanup completed;
- lease released with valid timestamps;
- lease file absent;
- active owned work after cleanup = 0;
- zero active/locked Scheduler work;
- campaign/run/cycle/factory terminal;
- no orphan discovery/factory/supervision work.

### Report / replay

- exactly one canonical terminal report row;
- exact canonical `.campaign-report.json` artifact exists;
- row hash/artifact bytes match;
- public `report_only()` returns `REPLAYED` for the exact identity;
- replay source calls = 0;
- replay Scheduler runtime calls = 0;
- replay DB writes = 0;
- DB mtime/hash unchanged by replay where the existing replay contract requires it.

### Locks

Zero delta / no activation for:

- retrieval queries/matches;
- paper decisions/audits;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet/signing/funds;
- paid API dependency;
- embeddings/vectors;
- score/rank/confidence/weighted logic;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot be a main outcome memory window.

### Reuse

- automatic retry = 0;
- manual rerun = 0;
- resume = 0;
- restart = 0;
- successor = 0.

## 12. Focused fail-closed contracts before the full proof

Implementation must add deterministic RED→GREEN contracts for the new C8 boundary only:

1. proof capability targeting canonical production DB blocks before mutation;
2. proof capability plus external authorization blocks before mutation;
3. fixture composition with one missing label blocks before mutation;
4. fixture composition with one extra label blocks before mutation;
5. non-fixture/live builder in proof registry blocks before mutation;
6. proof DB SHA/migration/identity drift blocks at binding validation;
7. any reuse flag true blocks;
8. C8 proof path seals holder-stage owner evidence and preserves owner/action-local parity;
9. public production path with no proof capability still requires validated authorization exactly as before.

No broad repository suite is required at this stage.

## 13. Bounded proof sequence

After implementation GREEN:

1. create one fresh disposable migrated DB and artifact root;
2. capture pre-run protected-table counts and DB identity;
3. construct exact full-registry deterministic fixture composition;
4. install network tripwire;
5. invoke `run_operational_campaign()` exactly once;
6. allow the ordinary 15m lifecycle to complete naturally;
7. collect returned terminal/report evidence;
8. run exact public `report_only()` once;
9. capture post-run integrity/FK/active-residue/locked-capability facts;
10. freeze proof summary + hashes;
11. **do not run a second campaign**;
12. perform independent read-only inspection from the frozen DB/artifacts;
13. write final C8 closeout only if both controlling proof and independent inspection pass.

Any failed controlling full proof stops the lane for review; no automatic or manual rerun is implied by this design.

## 14. Independent inspection

Independent inspection must not trust the proof runner's final booleans.

It reopens the disposable DB read-only and independently checks:

- canonical migration ledger;
- exact campaign/run/cycle/configuration/factory identity graph;
- exactly two terminal campaign windows and their memory-window linkage;
- both clean episodes/fingerprints;
- campaign acceptance evidence/hash reconstruction;
- supervision cleanup/lease timestamps;
- zero active/locked work;
- source/Scheduler accounting evidence;
- terminal report row/hash/artifact parity;
- report-only frozen result;
- protected capability zero deltas;
- no longer-window activation;
- no retry/restart/resume/successor;
- fixture registry manifest/hash and zero network-attempt evidence.

Inspection writes only a separate proof artifact; it does not mutate the proof DB.

## Money-usefulness contribution

C8 proves that Printer can turn one deterministic but source-governed two-token intake into two truthful clean 15m memories through the same composition intended for later operations, while cleaning up completely and preserving every downstream lock.

This is the integration evidence needed before trusting automated memory growth as useful paper-only learning input.

## What this design improves

- no-auth disposable proofability without weakening production authorization;
- exact full-registry fixture coverage;
- zero-provider proofability;
- DB target safety for disposable composition;
- holder accounting parity in the proof path;
- end-to-end public composition verification;
- independent closeout evidence.

## What this design still does not unlock

- provider-backed production execution;
- a new final authorization;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL;
- live wallet/keys/signing/funds;
- paid APIs;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- 1h proof rerun;
- 4h/12h/24h activation.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Proof capability leakage into CLI/production would be an authorization bypass. No CLI surface and canonical-DB rejection are mandatory.
2. Fixture registry fallback to defaults would make provider execution possible. Exact registry coverage + fixture marker + network tripwire are mandatory.
3. The ordinary natural proof consumes real 15m lifecycle time. Do not add compressed/predeclared dispositions to shorten it.
4. The proof-only DB binding is security-sensitive because it creates a second lawful target kind. It must be narrower than production, never broader, and reject the canonical DB structurally.
5. Fixture data can accidentally encode the desired outcome. Fixtures must provide source responses only; E2Q/E2Z outcomes remain derived by production owners.
6. Independent inspection must recompute facts from DB/artifacts rather than reuse runner booleans.
7. A failed full proof cannot be silently rerun because exactly-once/no-rerun evidence is part of the checkpoint.

## Design stop condition

After this design, implementation may begin only for the explicit C8 proof capability, proof DB binding, fixture registry plumbing, holder-stage proof accounting, focused tests, and proof/inspection harnesses described above.

Do not run the full public-composition proof until focused implementation GREEN and a pre-proof readiness review pass.
