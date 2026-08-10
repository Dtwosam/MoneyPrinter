# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Operational Activation Integration Design

## 1. Design verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OPERATIONAL_ACTIVATION_INTEGRATION_DESIGN_PASS`

Printer shall add one explicit, authorization-bound production path for the already-proven standard lifecycle:

`discovery -> WINDOW_15M -> genuine WINDOW_1H -> hard-gated 0/1/2 WINDOW_4H -> close/memory -> terminal cleanup`

The activation must reuse the existing Source Governor, Central Scheduler, campaign/factory ownership, standard eligible-subset composer, long-window collector and memory close path. It must not convert the historical `four_hour_proof_mode` into production authority.

This design creates no runtime authority by itself, performs no source call, creates no authorization and leaves real 4h collection disabled until the separately tested implementation is committed.

## 2. Controlling baseline

Design baseline:

`e3faf7fde28632030511ffc3df61f1d850ee2cee`

The repeated operational rereadiness verdict at that baseline permits this design and no more.

## 3. Public mode contract

Add two explicit modes to the existing canonical public operational command:

- `standard-four-hour-preflight`
- `standard-four-hour-run`

`standard-four-hour-preflight` is zero-source/read-only and may validate configuration, migrations, static owners, authoritative DB identity and lock readiness. It does not consume an authorization and cannot start campaign work.

`standard-four-hour-run` is the only new production mode allowed to reach genuine standard 4h work. It must fail before source/runtime work unless an exact standard-four-hour one-shot manifest + create-once application marker has already been validated.

Ordinary `run`, `selective-1h-proof`, historical proof modes and every existing auxiliary mode retain their current authority. None may inherit standard-four-hour authority from cadence activation.

Fixed production policy identity:

`V2-9.8-STANDARD-4H-OPERATIONAL-V1`

## 4. Lifecycle and duration envelope

The post-supply lifecycle duration is policy-derived:

- WINDOW_15M close: 900 seconds from lifecycle opening;
- WINDOW_1H continuation: additional 2,700 seconds;
- WINDOW_4H continuation from the genuine 1h predecessor: additional 10,800 seconds;
- terminal/cleanup margin: 300 seconds.

Therefore the standard-four-hour post-supply operational duration ceiling is:

`14,700 seconds`

The existing bounded pre-lifecycle acquisition horizon remains a separate:

`900 seconds`

The one-shot wall-time policy records both fields separately. It must never hide acquisition inside lifecycle accounting or double-count it as a lifecycle source budget.

## 5. Resource envelope

The authorization carries a fail-closed outer maximum sufficient for the worst supported two-token lane shape:

- lifecycle request outer ceiling: `230`
- lifecycle Scheduler outer ceiling: `210`
- per-token lifecycle request outer maximum: `114` for TRACK_FAST
- automatic retries: `0`
- endpoint rotation: `False`

These maxima are not the runtime truth after lane/subset resolution.

The exact runtime budget must be derived and persisted/reported through `standard_campaign_lifecycle_budget(tracking_lanes, continuing_mask)`:

- FAST+FAST none `92 / 82`, one `161 / 146`, both `230 / 210`;
- FAST+NORMAL none `74 / 64`, FAST only `143 / 128`, NORMAL only `113 / 98`, both `182 / 162`;
- NORMAL+NORMAL none `56 / 46`, one `95 / 80`, both `134 / 114`.

The pre-lifecycle acquisition operation budget stays separately governed by its existing owner. Runtime may never spend a blocked slot's unused 4h allowance merely because the authorization's outer maximum is larger.

## 6. Standard 1h barrier and eligible-subset composition

Production standard 4h planning occurs only after the exact two campaign slots have reached a successful genuine first-hour close boundary sufficient to produce their hard-gate verdicts.

Add one narrow campaign-level owner, preferably `operational_standard_4h.py`, that:

1. loads the exact two campaign slot identities and authoritative factory-run binding;
2. resolves each exact `WINDOW_1H` predecessor and physical 1h close truth;
3. evaluates the already-adopted token-local 1h->4h hard-gate policy without scores, ranks, confidence or learning-need authority;
4. constructs the exact two candidate records required by the existing standard composer;
5. derives the explicit eligible token-slot set (`0/1/2`);
6. calls `plan_standard_campaign_4h_handoff(...)` once at the campaign barrier;
7. returns/persists the exact subset budget and composition truth for terminal reporting.

A successful first-hour close may be ineligible for 4h. That slot still participates in the two-slot eligibility manifest but receives no 4h window or long work.

A failed/ambiguous first-hour close that prevents exact campaign-barrier truth fails closed; the implementation must not manufacture an ineligible manifest merely to continue the peer unless the approved hard-gate owner can still establish an exact successful close identity for both manifest slots.

## 7. Factory authority separation

Add an explicit factory configuration flag/enum representing standard production authority, for example:

`standard_four_hour_campaign=True`

It is categorical and mutually exclusive with `four_hour_proof_mode`.

Required validation:

- standard mode requires the exact campaign/run/cycle identities;
- exactly two selected campaign slots;
- continuous genuine first-hour path;
- standard-four-hour public operational policy binding;
- current 4h cadence enabled for real collection;
- 12h/24h remain disabled;
- `four_hour_proof_mode` must be false.

In standard mode the existing per-token `plan_current_run_4h(... explicit_proof_mode=...)` call must **not** be the production planner. The campaign barrier owner above creates the long plan through `plan_standard_campaign_4h_handoff`.

The historical proof path continues to use `explicit_proof_mode=True` and remains non-public proof machinery.

Long-step execution may reuse the existing 4h collector/state/accounting owners, but every standard-production long step must have exact stage-scoped campaign Scheduler ownership and an eligibility manifest proving that its token slot is expected to continue.

## 8. Runtime authority gate in the 4h module

Do not replace `explicit_proof_mode` with an ambiguous boolean that makes proof and production indistinguishable.

Where a long-window primitive needs an execution authority, use an explicit categorical authority such as:

- `DISABLED`
- `PROOF`
- `STANDARD_CAMPAIGN`

or an equivalent pair of mutually-exclusive validated parameters.

`STANDARD_CAMPAIGN` requires campaign/run/cycle/slot/window ownership plus `STANDARD_4H_ELIGIBILITY_V1` manifest truth. `PROOF` retains historical proof validation. Neither may imply the other.

## 9. Cadence activation

During the activation implementation, and only after the command/wrapper/factory authority checks are in place, change the authoritative FAST/NORMAL `WINDOW_4H` cadence entries to:

`enabled_for_real_collection=True`

This is an intentional capability change in this explicit activation lane.

It is not sufficient authority by itself. Ordinary `run` must still be unable to reach 4h, and direct invocation of `standard-four-hour-run --operator-approved` without the exact one-shot binding must fail before source/runtime work.

Keep:

- `WINDOW_12H.enabled_for_real_collection=False`
- `WINDOW_24H.enabled_for_real_collection=False`
- `WINDOW_5M_MICRO_EVENT` support-only and non-main.

Remove/replace the temporary eligible-subset-repair assertion that rejects a plan merely because 4h cadence is now enabled. Replace it with the explicit production/proof authority contract above.

## 10. One-shot wrapper and final-authorization contract

Do not broaden the existing `PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1` contract to silently accept a four-hour run.

Add a distinct standard-four-hour application owner, e.g.:

`standard_four_hour_one_shot_wrapper.py`

with schema:

`PRINTER_V1_STANDARD_FOUR_HOUR_ONE_SHOT_WRAPPER_V1`

It consumes exactly one final authorization, creates exactly one application marker and launches exactly one child:

`python -m printer_v1.operator_cli.operational_memory_factory_command standard-four-hour-run --operator-approved`

The final authorization schema is distinct and versioned, e.g.:

`PRINTER_V1_STANDARD_FOUR_HOUR_FINAL_AUTHORIZATION_V1`

Required authorization bindings include:

- authorization ID and exact SHA-256;
- exact repository branch/head;
- exact authoritative DB identity and migration ledger expected by the later fresh rereadiness;
- mode `standard-four-hour-run`;
- `operator_approved=true`;
- allowed invocation count exactly one;
- automatic retry/manual rerun/resume/restart/successor all false;
- token capacity exactly two;
- root main window `WINDOW_15M`;
- standard lifecycle through genuine `WINDOW_1H` and hard-gated `WINDOW_4H`;
- `STANDARD_4H_ELIGIBILITY_V1` expected-subset contract;
- 12h/24h locked;
- pre-lifecycle duration/operation ceiling separated from lifecycle duration/request/Scheduler ceilings;
- outer maxima `230 / 210` plus the required dynamic subset-budget contract identity;
- storage/failure/lease safety inherited from the existing operational campaign contract;
- no downstream retrieval/financial capability.

No real authorization instance is created during activation implementation/proof.

## 11. Git provenance manifest / application marker

The ordinary 15m manifest/marker schemas and validator behavior must remain backward compatible.

Extend the shared Git-provenance authorization module through a new explicit contract profile or versioned V3 path rather than weakening the V2 ordinary-run checks.

The standard-four-hour profile must bind:

- its distinct authorization package root/kind;
- exact command mode `standard-four-hour-run`;
- exact authorization SHA;
- exact repository branch/head;
- create-once marker;
- one invocation and all no-retry/no-resume/no-successor flags;
- current/historical authorization evidence without making any historical authorization reusable.

The public command accepts the manifest environment only for the exact expected standard-four-hour mode. A manifest prepared for ordinary `run` cannot authorize `standard-four-hour-run`, and vice versa.

## 12. Child terminal truth

Extend the child-terminal owner with a versioned standard-four-hour mode/profile while preserving ordinary `run` behavior byte-for-byte where practical.

The standard-four-hour child terminal must additionally make terminal scope unambiguous by reporting/binding:

- mode `standard-four-hour-run`;
- exact campaign/factory identities;
- whether the 1h barrier was reached;
- expected eligible 4h continuation count (`0/1/2`) when established;
- 4h terminal reconciliation status;
- cleanup/lease release;
- active locked work after closeout;
- exact terminal report identity/hash;
- source/Scheduler/DB accounting already available from the operational terminal truth.

The wrapper validates child-terminal mode/schema against its own authorization. stderr is never terminal truth.

## 13. No new schema migration by default

The current database can represent:

- exact campaign/run/cycle/slot/window ownership;
- stage-scoped Scheduler ownership;
- eligibility manifests in `CONTINUATION_CLOSE.result_json`;
- long run steps/jobs;
- terminal memory/report bindings.

Therefore the design requires **no migration** unless implementation inspection proves a genuinely missing durable fact. If that occurs, implementation must stop and return to a migration design rather than inventing a schema change inside the activation patch.

## 14. Expected implementation scope

Likely production scope:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`
- new `src/printer_v1/operator_cli/operational_standard_4h.py`
- new `src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py`
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- child-terminal owner (versioned extension or a narrow standard-four-hour companion)
- `src/printer_v1/snapshots/cadence_policy.py`
- focused tests only.

The existing ordinary 15m wrapper should remain unchanged unless a tiny shared-helper change is strictly required and its ordinary contract is proven unchanged.

## 15. Minimum sufficient RED/GREEN proof

Before implementation, add focused RED contracts for:

1. public standard-four-hour mode exists only through exact one-shot binding;
2. direct public invocation without standard manifest/marker blocks before source/Scheduler/DB mutation;
3. ordinary `run` still cannot reach 4h after cadence activation;
4. proof mode remains distinct and cannot satisfy production authorization;
5. wrapper rejects ordinary 15m authorization, wrong mode/head/DB/schema, reused marker and any retry/resume/successor permission;
6. standard manifest and marker cannot cross-authorize ordinary mode;
7. exact 14,700-second post-supply and separate 900-second pre-lifecycle horizons;
8. outer 230/210 ceilings plus exact dynamic 0/1/2 subset budgets;
9. both eligible, FAST-only, NORMAL-only and zero-eligible campaign barriers;
10. only manifest-eligible slots create/execute 4h work;
11. 4h terminal close/memory/cleanup works for one and two eligible slots and zero eligible no-op;
12. any partial/foreign 4h Scheduler ownership fails closed;
13. 12h/24h remain absent/disabled;
14. ordinary 15m wrapper/manifest/child-terminal regression contracts remain passing.

GREEN uses only fixture/disposable DB/source transports. No real source call and no authoritative DB mutation.

Because this activation crosses public command, authorization, Scheduler, cadence and terminal boundaries, the final implementation closeout may run the directly affected broader integration set, but not unrelated repository-wide suites unless an actual cross-cutting failure requires it.

## 16. Independent exact-head proof

After a production-only implementation commit, run a separate disposable read-only/fixture proof from the exact production SHA.

It must prove:

- exact production head;
- public authority separation;
- exact 0/1/2 subset composition and budgets;
- Source Governor/Central Scheduler ownership;
- one-use wrapper/manifest/terminal contracts using fixture authorization only;
- 4h cadence enabled only as designed;
- 12h/24h locked;
- no retrieval/financial rows;
- no real network calls;
- tracked tree unchanged.

Only then may activation implementation close PASS.

## 17. Post-implementation operational sequence

Even after offline activation implementation/proof PASS:

1. perform a fresh operator-host read-only rereadiness check;
2. re-read actual current DB bytes, migration ledger, integrity/FKs, sidecars, process/lease/Scheduler/campaign residue and exact Git state;
3. only if that passes, prepare a fresh one-use standard-four-hour authorization;
4. independently review and close that authorization;
5. only then execute one bounded real standard-first-four-hour campaign;
6. the attempt is consumed once; no automatic/manual rerun or resume;
7. independently close the real run before any next capability.

## 18. Money-usefulness contribution

This activation makes Printer capable of collecting real, clean first-four-hour trajectory memory under the same hardened production controls already proven for 15m/1h. It improves survival/collapse/distribution/liquidity-deterioration evidence while preserving token-local hard gates and resource truth.

It does not prove profit, enable retrieval or authorize a paper trade.

## 19. What this lane improves

- explicit production authority for standard 4h instead of proof-mode reuse;
- exact one-use authorization and Git binding;
- policy-derived full-lifecycle duration/resource accounting;
- exact 0/1/2 subset execution;
- clear proof-vs-production separation;
- terminal truth suitable for a later one-use live campaign.

## 20. What remains locked

This design itself unlocks nothing. Even after implementation, no real run occurs before fresh rereadiness and a separately prepared/reviewed one-use authorization.

12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, signing, live execution, real funds, paid APIs, scoring, ranking, confidence, weighted logic, embeddings and vectors remain locked.

## 21. Functionality Risks / Setbacks / Efficiency Blockers

- A global 4h cadence flag without exact public authority would be a partial unsafe activation; implementation order and tests must prevent it.
- Reusing `four_hour_proof_mode` would make test/proof authority indistinguishable from production authority.
- Reusing the ordinary 15m wrapper or authorization schema would create false declared scope.
- Planning per token immediately at each 1h close would bypass the two-slot durable eligibility barrier; standard planning must happen once at campaign level.
- Using the outer 230/210 maximum as actual runtime allocation would hide subset truth; exact dynamic budget reporting/planning remains mandatory.
- Manifest/marker generalization could accidentally weaken ordinary 15m historical protections; old contract tests are mandatory regressions.
- Enabling cadence before all authority checks are installed could make a direct code path reachable prematurely.
- Current operator-host DB/process truth is intentionally not part of offline implementation proof and remains a later rereadiness dependency.
