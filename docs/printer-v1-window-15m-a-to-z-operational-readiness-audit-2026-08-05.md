# Printer V1 — `WINDOW_15M` A-to-Z Operational Readiness Audit

**Date:** 2026-08-05  
**Audit type:** static repository inspection + read-only incident/DB evidence review  
**Code baseline:** `7a4152bb90b14317513bb10879ee3861410270c7`  
**Branch audited:** `agent/v2-9-8b-pre-authorization-migration-ledger-drift-guard`

## 1. Verdict

### Audit verdict

`V2_9_8B_WINDOW_15M_A_TO_Z_OPERATIONAL_READINESS_AUDIT_PASS_WITH_CONFIRMED_BLOCKERS`

### Operational readiness verdict

`V2_9_8B_WINDOW_15M_END_TO_END_READINESS_BLOCKED`

Printer is **not ready for another one-use `WINDOW_15M` authorization**.

The audit confirms that substantial portions of the pipeline are structurally sound: exact authorization binding, atomic two-slot identity, durable campaign ownership, deterministic reserve freeze, Scheduler handoff, post-handoff compensation, 15-minute close mechanics, clean/dirty classification, terminal cleanup, and locked downstream capabilities.

However, the exact ordinary production composition still contains deterministic blockers that can be found without contacting a provider. The latest one-use attempt exposed one of them only after authorization consumption and database mutation. The same code contains a mirror defect that would fail on the opposite backup direction.

The correct next action is one unified design and implementation section covering the blocker bundles in §11, followed by one exact integrated offline proof. Do not create or review another authorization before that proof and its closeout pass.

---

## 2. Scope and restrictions

This audit covers the complete intended path:

`authorization → child preflight → campaign creation → discovery → reserve conversion → holder/safety context → deterministic freeze/selection → atomic handoff → Scheduler lifecycle → 900-second collection → close/audit → clean-memory promotion → terminal report/replay/cleanup`

Audit actions were limited to:

- static inspection at exact Git HEAD;
- review of existing tests and closeouts;
- read-only review of the failed attempt and authoritative database evidence supplied by the operator;
- comparison with the active Printer V1 source stack.

No code or documentation was modified in the repository. No provider was contacted. No Scheduler or campaign runtime was started. No database write, authorization creation, cleanup, rerun, resume, restart, or successor occurred.

All V1 locks remain in force: Solana-only, Solana-memecoin-only, paper-only, no wallet/private key/signing/real funds/live execution, no paid dependency, no scoring/ranking/confidence/weighted system, no embeddings/vectors, no retrieval or decision activation, no BUY/SELL/HOLD, no positions, trades, audits, or PnL. `WINDOW_5M_MICRO_EVENT` remains support-only.

---

## 3. Controlling incident evidence

Consumed authorization:

`V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z`

Authorized code:

`7a4152bb90b14317513bb10879ee3861410270c7`

Failed action identities:

- execution: `20260805T101812Z-c127b90a8ea2`
- campaign: `20260805T101812Z-c127b90a8ea2-campaign`
- campaign run: `20260805T101812Z-c127b90a8ea2-campaign-run`

Terminal exception:

`PermissionError: GeckoTerminal adapter requires an explicit transport`

The wrapper passed, created its application marker, launched exactly one child, and permanently consumed the authorization. The child terminalized nonzero.

### Authoritative database mutation

Authorized pre-attempt database:

- SHA-256: `5cf5326c4a820538a2f648a274bf14797c23a988bfae0f25aa49f01205cfafdc`
- size: `68,009,984`

Post-attempt database:

- SHA-256: `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb`
- size: `68,067,328`
- inode: `1230526`
- `mtime_ns`: `1785925095953652677`
- migration: `52 / 052_memory_observation_eligibility_layers.sql`
- integrity: `ok`
- foreign-key violations: `0`
- sidecars: none

The database gained 57,344 bytes. The read-only inspection itself left the file unchanged.

### Durable incident graph

The attempt persisted and terminalized:

- campaign configuration;
- campaign;
- campaign run;
- campaign cycle;
- supervision;
- first terminal cause `OPERATIONAL_CAMPAIGN_FAILED:PermissionError`;
- cleanup completion and lease release.

Forty-eight reserve-layer rows were associated with this campaign:

- 25 rows carried DexScreener request `1926`;
- 23 rows carried GeckoTerminal request `1928` and response `1721`.

The GeckoTerminal-linked observations predated campaign start and were retained/reused evidence; they must not be counted as 23 new provider calls. The DexScreener-linked rows were written during the campaign stage. Some reserve rows were inserts and some were updates/re-attributions; the current exception envelope does not reconstruct that distinction.

---

## 4. A-to-Z readiness matrix

| Stage | Current owner/path | Audit status | Finding |
|---|---|---:|---|
| Authorization package and one-use wrapper | `window_15m_one_shot_wrapper` + manifest validator + migration guard | **PROVEN_READY, policy gap** | Exact HEAD/DB/package binding and pre-consumption migration guard work. Wrapper expiry remains operator-enforced rather than code-enforced. |
| Child activation preflight | `build_activation_preflight` | **CONFIRMED BLOCKER** | Checks imports, contracts, DB, Git, budgets and active state, but does not construct the complete production adapter/factory graph. |
| Runtime dependency construction | `assert_runtime_dependency_preflight` | **PARTIAL / UNUSED CAPABILITY** | It already supports `adapter_builders` and rejects builders that raise or return `None`; ordinary production calls it with no builders. |
| Campaign graph creation | `_run_operational_campaign` | **CONFIRMED BLOCKER** | Campaign/config/run/cycle/supervision/heartbeat are created before the full source composition is constructed and proven usable. |
| Primary discovery and nomination | eligible supply + permanent discovery | **PROVEN READY STATIC** | Main GeckoTerminal nomination constructs a default transport. DexScreener batch and PumpSwap protocol confirmation have default builders. |
| Opposite-source unknown-liquidity backup | `run_bounded_unknown_liquidity_backup` | **CONFIRMED BLOCKER** | Both fallback directions can create an enabled adapter with `transport=None` when no factory is injected. Latest attempt hit the GeckoTerminal direction; DexScreener direction is the mirror latent failure. |
| Supplied factory return validation | discovery and lifecycle DI seams | **CONFIRMED BLOCKER** | Several paths check whether a factory exists but do not validate that its returned adapter/transport is non-null and contract-correct. |
| Durable reserve conversion | permanent discovery availability | **PROVEN READY STATIC / LIVE UNCERTAINTY** | Categorical reserve layers and exact identities are persisted. Live supply, liquidity and provider availability remain uncertain by nature. |
| Holder and safety separation | authoritative campaign owner | **PROVEN READY STATIC** | Migration 052/current owner separates `memory_observation_eligible` from holder/future-action eligibility. Holder failure remains context, not a memory-admission veto. |
| Holder partial accounting | holder funnel | **PROVEN READY STATIC** | Releases write transaction before I/O and preserves partial governed attempts. Still needs exact production-composition proof with default builders. |
| Four-deep reserve freeze | `freeze_eligible_reserve` | **PROVEN READY STATIC** | Requires fresh, unique mint/pool, memory-observation eligibility, and neutral deterministic selection of two plus two alternates. |
| Source-request reconciliation before readiness | permanent discovery diagnostics | **PROVEN READY STATIC** | Campaign-wide request IDs and coverage are assembled before readiness. This truth is not reused by the public exception envelope. |
| Atomic two-slot handoff | combined executor + origin driver | **PROVEN READY OFFLINE** | Exact slot identities, one selection batch, superseded-job cancellation, and no reselection are implemented. |
| Post-handoff compensation | origin driver | **PROVEN READY OFFLINE** | Exact-scope teardown exists for six post-handoff fault points and terminalizes scoped work. |
| Scheduler lifecycle | one-command factory | **PROVEN READY STATIC/OFFLINE** | Opening jobs, anchored cadence jobs, claims, no retry, token-local failure isolation, and final cancellation are implemented. |
| Real 900-second current composition | factory + public coordinator | **EVIDENCE GAP** | Production code enforces the 900-second evidence span, but retained exact-public-composition proof uses `_window_seconds=0.05`; no current-HEAD exact production-composition 900-second controlled-clock proof was found. |
| Exact-pair snapshot and fallback | DexScreener primary + GeckoTerminal fallback | **PROVEN READY STATIC** | Default adapter factories exist and one eligible transient fallback is bounded. Concrete construction is not included in activation preflight. |
| Pre-close context | CoinGecko, GoPlus, Jupiter, Solana RPC/Helius | **PROVEN READY STATIC / LIVE UNCERTAINTY** | Defaults are concrete and governed. Provider data may honestly be unavailable or dirty. Injected factories are not universally return-validated. |
| 15-minute close and ledger attachment | E2O + factory | **PROVEN READY STATIC** | Closing snapshot is attached before context resolution; real evidence duration must be at least 900 seconds. |
| Window audit | E2Q | **PROVEN READY STATIC** | `WINDOW_15M` clean/dirty/audit-only classification and fail-closed gates are present. |
| Clean-memory promotion | Lane Q/U2/E2Z | **CONFIRMED OWNERSHIP GAP** | `_execute_close` invokes the global E2Z pipeline, which scans all eligible 15-minute candidates in the DB rather than only the current run/window. |
| Current-run clean-memory success proof | public composition test | **EVIDENCE GAP** | Test asserts two successful closes and `CAMPAIGN_PASS`, but does not assert current-run `CLEAN_MEMORY`, current-run episode creation, fingerprint linkage, or two clean outcomes. |
| Campaign acceptance semantics | full-run accounting | **CONTROL GAP** | `CAMPAIGN_PASS` intentionally means lifecycle/accounting/cleanup passed; memory quality does not lower it. A clean-memory success verdict must remain separate and explicit. |
| Exception source accounting | public CLI exception envelope | **CONFIRMED BLOCKER** | Reads only the latest holder-operation ledger. Discovery failures before that ledger can report `source_calls: 0` despite durable discovery requests/evidence. |
| Exception DB mutation accounting | public CLI exception envelope | **CONFIRMED BLOCKER** | Returns `UNKNOWN_ON_EXCEPTION` after action identity. It does not produce a durable table-by-table action mutation inventory. |
| Terminal reconciliation and cleanup | unified closure + supervision | **PROVEN READY IN INCIDENT** | Latest attempt ended terminal failed, cleanup completed, lease released, integrity/FK passed, no sidecars. |
| Report-only replay | factory report loader | **PROVEN READY OFFLINE** | Zero-source, zero-write replay is implemented and previously tested. |
| Locked downstream capabilities | command/factory/full-run accounting | **PROVEN LOCKED** | No current path unlocks retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits or PnL. |

---

## 5. Confirmed deterministic blockers

### B1 — Complete production composition is not validated before mutation

`build_activation_preflight()` calls `assert_runtime_dependency_preflight()` without `adapter_builders`. The helper already knows how to construct builders and reject exceptions or `None`, but the ordinary `WINDOW_15M` path does not supply the real production builders.

The preflight therefore establishes that modules and source contracts exist, not that every runtime branch can construct a usable adapter/transport.

**Consequence:** a deterministic construction error can pass preflight, consume authorization, create campaign state, mutate the corpus, and only then fail.

### B2 — GeckoTerminal unknown-liquidity backup has no default transport

For a DexScreener-origin `LIQUIDITY_UNKNOWN` row, the opposite-source backup does:

```text
factory present -> factory(mint)
factory absent  -> None
build_geckoterminal_adapter(enabled=True, fixture_transport=None)
```

The adapter then fails with the exact latest error.

This is the direct root cause of the consumed 2026-08-05 attempt.

### B3 — DexScreener unknown-liquidity backup has the mirror defect

For a GeckoTerminal-origin `LIQUIDITY_UNKNOWN` row, the same function does:

```text
factory present -> factory(mint)
factory absent  -> None
build_dexscreener_adapter(enabled=True, fixture_transport=None)
```

The latest attempt did not reach this branch, but it is a deterministic latent blocker under normal market input.

### B4 — Factory presence is checked more often than factory output

The code has several dependency-injection seams where a supplied callable is trusted. A caller can provide a callable that returns `None` or an adapter with no transport. The production preflight does not exercise these factories, and the stage often fails only after earlier mutations.

The repair should establish one shared “required concrete dependency” validator rather than adding local `if None` patches repeatedly.

### B5 — Mutation starts before full composition readiness

The public coordinator currently performs these actions before the full live composition is exercised:

- external execution artifact directory;
- backup/restore evidence;
- campaign configuration;
- campaign/run/cycle rows;
- supervision and lease;
- heartbeat;
- discovery and reserve writes.

The complete no-I/O composition validation must occur before campaign creation. Runtime-dependent market facts cannot be pre-proven, but adapter/factory construction can.

### B6 — Exception source-call reporting is incomplete

The public exception envelope computes campaign source calls from `printer_holder_campaign_operation_ledgers`. A discovery-stage exception before holder accounting therefore produces `campaign_source_calls=null` and `source_calls=0` even when durable discovery request/evidence exists.

The latest incident demonstrates this defect. Terminal truth must be reconstructed from the complete campaign source-request manifest and durable request/response/failure/external-operation rows, not one holder ledger.

### B7 — Exception mutation reporting is not actionable

After campaign identity exists, the public CLI reports only:

`database_mutation_status=UNKNOWN_ON_EXCEPTION`

That is honest but insufficient. The operator cannot tell which tables were inserted, updated, reused, re-attributed or terminalized without a separate broad DB scan.

The campaign already has exact ownership identities. A bounded mutation inventory can be produced from those identities and a pre-action count/hash snapshot without adding a second database owner.

### B8 — Clean-memory promotion is globally scoped during a current-run close

`_execute_close()` invokes `run_e2z_pipeline(db_path, production_mode=True)`. The pipeline collects all eligible `WINDOW_15M` candidates in the database. It is not passed the newly closed current-run `window_id` as an authority boundary.

Consequences:

- a current campaign can promote an older pending window;
- unrelated memory/coverage writes may occur during this campaign;
- action-local DB deltas can include historical backlog work;
- current-run clean-memory success is harder to prove exactly.

The pipeline needs an explicit current-window/current-run candidate scope for operational close. Existing unscoped batch/backlog behavior can remain available only as a separate explicit maintenance mode.

---

## 6. Evidence and proof gaps

### E1 — No exact current-HEAD 900-second public composition proof

The real factory schedules the close at opening snapshot + 900 seconds and blocks evidence spans below the required window. That logic is present.

The retained public-composition test, however, changes the lifecycle to:

- `_window_seconds=0.05`;
- `total_duration_seconds=3.0`;
- disposable proof mode;
- test-only lifecycle remapper;
- frozen adapters.

It proves structural integration, not the exact production 900-second composition.

A controlled clock can prove 900 logical seconds without wall-clock waiting. The proof must preserve the ordinary production composition and only replace external response bodies and time.

### E2 — Public composition PASS does not prove a clean current-run memory

The retained exact composition test asserts:

- terminal `COMPLETED`;
- `campaign_pass=True`;
- exactly two succeeded `WINDOW_CLOSE` steps;
- zero active residue;
- replay identity;
- locked capability counts zero.

It does not assert:

- two current-run windows classified `CLEAN_MEMORY`;
- `do_not_train=0` on those windows;
- one current-run episode per clean window;
- exact episode-to-window/token/pair linkage;
- fingerprints for those current-run episodes;
- zero unrelated E2Z promotions.

### E3 — Runtime PASS and memory outcome PASS are different by design

Full-run accounting intentionally states that memory quality does not lower `CAMPAIGN_PASS`. This is useful: a complete dirty lifecycle should not be mislabeled as a broken Scheduler run.

But operator-facing success must expose two independent outcomes:

1. `operational_lifecycle_pass` — ownership, Scheduler, accounting, terminal cleanup;
2. `clean_memory_outcome_pass` — exact current-run clean windows and episode/fingerprint promotion.

For the next proof, success requires both. A live campaign may still close honestly with the first true and the second false.

---

## 7. What is already sound and should not be redesigned

The following should be preserved and regression-tested rather than rewritten:

- one-use wrapper and exact Git/DB/package binding;
- pre-authorization migration-ledger guard;
- Source Governor and Central Scheduler ownership;
- durable eligible reserve and exact market identities;
- no scoring/ranking/confidence/weights;
- memory-observation eligibility separated from holder/future-action eligibility;
- four-deep freeze with two selected plus two alternates;
- exact token-slot identity;
- origin-to-lifecycle batch projection with no reselection;
- superseded first-15m job cancellation;
- post-handoff scoped compensation;
- opening-snapshot anchored cadence;
- exact 900-second evidence-duration gate;
- token-local lifecycle failure isolation;
- E2Q clean/dirty/audit-only classification;
- individual per-window promotion gates;
- immutable first terminal cause;
- unified terminal reconciliation, cleanup and lease release;
- report-only replay;
- all downstream financial/retrieval locks.

Previously identified defects that are repaired at the audited HEAD and should not be reopened include:

- campaign-run identity being mistaken for factory-run identity;
- missing durable re-persistence of `campaign_window_registration`;
- stale Lane K documentation claiming E2Y always gates individual promotion;
- holder pass being required for memory observation.

---

## 8. Live uncertainties that are not software defects

Even after all confirmed blockers are repaired and proved, a live attempt may honestly produce no clean memory because of:

- insufficient fresh four-deep eligible reserve;
- public provider timeout, throttling, malformed response or unavailable data;
- exact-pair mismatch or stale liquidity evidence;
- incomplete holder evidence;
- missing route/quote realism;
- snapshot gaps or stale close evidence;
- market conditions that classify the window dirty or audit-only.

The software obligation is not to guarantee a clean market outcome. It is to ensure these conditions produce exact, attributable, terminally clean reports without hidden composition failures or misleading zero counts.

---

## 9. Current authoritative DB disposition

Do not delete or manually rewrite the failed campaign or reserve evidence.

The current database is healthy and terminally closed:

- integrity `ok`;
- no FK violations;
- no SQLite sidecars;
- campaign/run/cycle terminal failed;
- supervision terminal;
- cleanup complete;
- lease released.

The incident graph is useful regression evidence. Future authorization must bind the post-incident database identity, not the pre-attempt identity.

Before any future proof or authorization, a read-only residue check must confirm:

- zero active campaign/run/supervision records;
- zero pending/running factory steps;
- zero active/locked Scheduler jobs;
- zero active discovery work;
- no application marker for the future authorization ID;
- locked capability baseline unchanged.

---

## 10. Money-usefulness contribution

This audit improves money-usefulness by protecting the scarce, expensive part of the system: obtaining real, attributable 15-minute market memories without wasting one-use authorizations on deterministic wiring defects.

It establishes that the next repair must focus on:

- dependable discovery and fallback composition;
- exact source and mutation truth;
- current-run-only memory promotion;
- proof that a real 900-second window can become an exact clean episode;
- honest separation between operational completion and memory quality.

It does not claim profitability, predict a token, enable trading, or lower any safety gate.

---

## 11. Dependency-ordered repair plan

The user’s request is to avoid one tiny patch after another. The correct implementation section is therefore one coordinated repair program with four bounded bundles, implemented in order and closed by one integrated proof.

### Bundle A — Pre-mutation concrete composition readiness

Implement one shared production composition builder/validator that runs after child trust preflight but before campaign/artifact/database mutation.

It must, with zero I/O:

- construct the exact default production transport/factory graph;
- validate every required adapter is enabled and carries a non-null explicit transport;
- validate source name/request-kind contracts;
- validate both opposite-source liquidity backup builders;
- validate snapshot primary/fallback builders;
- validate pre-close context builders;
- reuse `assert_runtime_dependency_preflight(adapter_builders=...)` or extend it, not create a second preflight framework;
- fail before campaign identity, supervision, reserve writes or authorization child work if composition is invalid.

Also move runtime transport/factory construction before campaign creation where it can be done without I/O.

### Bundle B — Discovery fallback and factory-output repair

Repair the exact defective branches using existing approved source builders.

Requirements:

- DexScreener-origin liquidity unknown → concrete governed GeckoTerminal backup;
- GeckoTerminal-origin liquidity unknown → concrete governed DexScreener backup;
- preserve one opposite-source attempt only;
- preserve exact mint/pool identity and categorical outcomes;
- no retry, rotation, scoring, ranking, paid dependency or parallel adapter owner;
- reject a supplied factory that returns `None` or an invalid adapter before stage mutation;
- add mirror-path tests so one direction cannot be repaired while the other remains latent.

### Bundle C — Action-local terminal truth

Use existing durable campaign ownership and request manifests to produce exact exception reports.

Requirements:

- all action-attributable source request IDs;
- response/failure/external-operation counts;
- distinguish fresh transport, zero-transport reuse and projection-only writes;
- table-by-table insert/update/terminalization inventory where deterministically attributable;
- DB identity before/after;
- exact campaign/run/cycle/supervision cleanup state;
- no fallback to holder-ledger-only source totals;
- preserve first terminal cause;
- no new ownership tables unless a demonstrated missing identity requires one.

### Bundle D — Current-run clean-memory ownership and success semantics

Scope operational E2Z promotion to the exact newly closed window(s).

Requirements:

- operational close passes explicit current `window_id` or current-run candidate set;
- no unrelated historical candidate promotion;
- exact episode/fingerprint linkage to current run, token, pair and window;
- preserve an explicit separate backlog/maintenance mode only if required;
- retain `CAMPAIGN_PASS` as lifecycle/accounting truth;
- add explicit `clean_memory_outcome_pass` and reasoned blocker set;
- operator success for the next proof requires both verdicts.

---

## 12. Minimum sufficient proof plan

Do not run a broad repository suite after each edit. Use risk-based checks per bundle, then one integrated closeout proof.

### Bundle-level proofs

1. **Composition preflight:** every default builder returns a valid concrete adapter/transport; each `None`/raising builder blocks before campaign identity and DB mutation.
2. **Discovery fallback mirror:** both opposite-source directions execute exactly one governed fixture transport and preserve identity; both missing/invalid factories block before writes attributable to that backup stage.
3. **Exception truth:** inject failures after fresh source request, after retained evidence reuse, after reserve mutation, and after campaign creation; terminal output reconciles exact durable truth and cleanup.
4. **Promotion scope:** close one current-run window while unrelated eligible historical windows exist; only the current window may be promoted in operational mode.

### Final exact integrated proof

Use one disposable Migration-052 database derived from the authoritative schema and one exact public composition:

- public coordinator;
- ordinary operational persistent composition semantics;
- authoritative campaign owner;
- eligible supply and both unknown-liquidity backup directions;
- holder/context defaults;
- origin driver;
- real factory;
- Source Governor;
- Central Scheduler;
- controlled clock with `_window_seconds=900.0`;
- no wall-clock 15-minute wait;
- frozen lawful response bodies only;
- patched outbound network call count zero;
- no test-only change from operational persistent mode to proof-only mode.

The integrated success assertions must include:

- one campaign, one run, one cycle;
- four valid memory-observation-eligible reserve candidates;
- exactly two selected and two alternates;
- two distinct token-slot identities;
- exactly two current-run 15-minute windows;
- evidence span at least 900 seconds for both;
- expected cadence and no gaps;
- exactly two current-run `CLEAN_MEMORY` windows;
- `do_not_train=0` for both;
- exactly two current-run clean episodes or the explicitly adopted expected count;
- exact episode/window/token/pair linkage;
- fingerprints present;
- zero unrelated historical promotions;
- `operational_lifecycle_pass=true`;
- `clean_memory_outcome_pass=true`;
- exact source and DB mutation accounting;
- zero active/locked residue;
- cleanup and lease release;
- zero forbidden capability deltas;
- report-only replay is byte-stable and performs zero writes/source calls;
- no retry/restart/resume/successor.

A second integrated negative node should inject one required adapter returning `None` and prove zero campaign identity, zero source call and zero DB mutation.

---

## 13. Readiness gate before another authorization

Another authorization may be considered only after all of the following are true:

1. Bundles A–D are implemented and committed.
2. Focused bundle tests pass.
3. The exact integrated 900-second clean-memory proof passes.
4. The integrated negative pre-mutation composition proof passes.
5. Closeout independently verifies the remote diff.
6. Authoritative DB is inspected read-only and bound at its current post-incident identity.
7. No active or locked work exists.
8. Wrapper expiry is either enforced in code or the remaining operator-only risk is explicitly accepted before package creation.
9. A new package uses a fresh authorization ID and nonce; no prior authorization is reused.

No source-fetching “readiness run” should be used as a substitute for these deterministic proofs. Live supply and provider conditions remain part of the one bounded authorized attempt and must be allowed to block honestly.

---

## 14. What this audit still does not unlock

This audit unlocks only design work for the blocker bundles.

It does not unlock:

- code implementation without an approved unified design;
- another one-use authorization;
- another live or authoritative `WINDOW_15M` attempt;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` operation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper trade audits or PnL;
- live execution, wallets, signing or funds;
- paid APIs, scoring/ranking/confidence, embeddings or vectors.

---

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Impact | Required control |
|---|---|---|
| Repairing only the observed Gecko branch | Dex mirror fails on next different market input | Mirror-path implementation and tests in one bundle |
| Adding local null checks everywhere | Continues fragmented patch cycle | Shared concrete-dependency validator and production composition plan |
| Treating campaign PASS as clean-memory PASS | False success against the user’s goal | Two independent top-level verdicts |
| Global E2Z scan during current close | Unrelated memory writes and misleading deltas | Current-run/window-scoped promotion |
| Broad test suite after every small change | Slow and noisy | Focused bundle tests, one final integrated proof |
| New live “readiness” attempts before deterministic proof | Burns authorizations and mutates corpus | No authorization until integrated proof/closeout |
| Deleting failed campaign evidence | Destroys regression truth | Preserve terminal incident graph; read-only checks only |
| Overfitting fixtures to one discovery source | Mirror/alternate path remains unproved | Exercise both Dex→Gecko and Gecko→Dex backup directions |
| Controlled clock differs from wall clock | Could hide scheduling bugs | Preserve real Scheduler functions and require logical captured-at span ≥900s |
| Public providers still fail after repair | Honest live block | Exact terminal attribution, no retry, no false code-defect classification |

---

## 16. Final conclusion

Printer’s `WINDOW_15M` architecture is not fundamentally broken. Most core owners exist and several difficult identity, cleanup and memory-safety problems are already repaired.

The current readiness failure comes from a smaller but systemic issue: the project has contract-level readiness without complete concrete-composition readiness. That allows unusable source dependencies to survive until after campaign mutation. The same gap also weakens exception truth and made prior structural PASS evidence insufficient to prove a clean current-run memory.

The next lane should not be “patch GeckoTerminal and retry.” It should be one unified design and implementation section covering:

1. pre-mutation concrete composition validation;
2. both unknown-liquidity fallback directions;
3. exact action-local exception accounting;
4. current-run-scoped clean-memory promotion and dual success verdicts;
5. one exact 900-second clean-memory integrated proof.

Until that section and proof close, the correct status is:

`V2_9_8B_WINDOW_15M_END_TO_END_READINESS_BLOCKED`
