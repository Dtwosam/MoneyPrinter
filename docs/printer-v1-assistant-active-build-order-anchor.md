# Printer V1 Assistant Active Build Order Anchor

## Purpose and authority

This document aligns ChatGPT, Codex, Claude, and future assistants before Printer V1 memory-growth work.

It does not replace:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`; or
- `docs/printer-v1-memory-growth-build-order-v2.md`.

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth build order, not the sole source of truth. Later committed audits, designs, implementations, proofs, closeouts, and reconciliations control exact current lane position.

## Current durable state

V2-9.8B has consumed two separately authorized standard-four-hour attempts. Neither is a successful 4h proof and neither authorization may ever be reused.

A **third** standard-four-hour authorization has since been prepared and independently reviewed. It is **unconsumed** and approved for at most one canonical application while still temporally valid.

Durable anchors include:

- DTW100 `WINDOW_15M` campaign closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`;
- post-DTW100 E2Q audit closeout: `b07a946d56886d923129b3eacade775f19f58d71`;
- first-hour Checkpoint 1-6 offline-composition chain closeout: `7c793dca805bccf79a8bbadaed2fb57e426c6b93`;
- standard-four-hour current-state audit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`;
- first consumed standard-four-hour runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- first-attempt repair implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- first-attempt repair closeout: `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`;
- post-repair standard-four-hour rereadiness closeout: `8fd74f5d13225b72ebb56890dfd17224600189c5`;
- second standard-four-hour launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`;
- second standard-four-hour runtime classification closeout: `623ea64657555341419fe92f000435e11ab52d5c`;
- second-attempt 1h→4h safety/provenance repair-scope audit: `303227dd76b96b144dab75c11bf1cb827563babc`;
- second-attempt 1h→4h safety/provenance repair design: `695fd3e53781b1faba13d21226f323d1e586cbb1`;
- partial implementation status checkpoint: `81ca0385ac258c496df54e5034b94b4529de0a66`;
- second-attempt 1h→4h safety/provenance repair implementation closeout: `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`;
- post-safety-repair operational rereadiness audit closeout: `f153a6bc24efb3b708e6fb86c1e262f258613b67`;
- second standard-four-hour public budget-authority repair-scope audit: `146261d41cdd5ac9a13054bd3e8237d78d98db83`;
- second standard-four-hour public budget-authority repair design: `ba2843f0e26d67ad6175d27adce0ab63e30bb308`;
- second standard-four-hour public budget-authority repair implementation closeout: `61647122d33cbf45f0e321a989f4ea14ca00b1b1`;
- post-public-budget-authority-repair operational rereadiness closeout: **PASS** at `61647122d33cbf45f0e321a989f4ea14ca00b1b1`;
- fresh one-use standard-four-hour authorization preparation HEAD: `0be6b4f7f56a501a40b2ef02521689ccaffb0ce9`;
- independent fresh standard-four-hour authorization review closeout: **PASS** (see "Third standard-four-hour authorization" below).

DTW97 remains permanently consumed. DTW100 remains closed. No historical authorization may be reused.

## Second consumed standard-four-hour attempt

Fresh authorization:

- ID: `V2_9_8B_STANDARD_4H_AUTH_20260811T010152Z`;
- SHA-256: `f58788685f836a3c0979bfb71ddd079beb84ffba568a5ad70823554fa2bb7612`;
- frozen launch branch: `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`;
- exact launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`.

Attempt identity:

- execution: `20260811T011906Z-2e278d795b54`;
- campaign: `20260811T011906Z-2e278d795b54-campaign`;
- campaign run: `20260811T011906Z-2e278d795b54-campaign-run`;
- authoritative factory run: `7a84b80b-4f51-4516-84e9-828132a45009`;
- first terminal cause: `SAFE_STOP_4H_TERMINAL_INCOMPLETE`;
- wrapper child exit: `0`;
- child terminal valid: true;
- retry / rerun / resume / restart / successor: none.

The authorization passed preparation and independent review, was consumed exactly once, and is permanently non-reusable.

## Second-attempt runtime truth

Read-only reconstruction closed PASS with root-cause classification:

`COMMITTED_CODE_DEFECT_AT_WINDOW_1H_TO_WINDOW_4H_SAFETY_PROVENANCE_INTEGRATION_BOUNDARY`

Both selected tokens completed valid physical and clean `WINDOW_15M` and `WINDOW_1H` memories. The standard-four-hour barrier later reached its two-token decision point but returned zero eligible slots and zero planned 4h jobs.

Both tokens received identical `BLOCK_CONTINUATION` reasons:

- `predecessor_evidence_stale`;
- `governed_provenance_untraceable`;
- `mandatory_safety_context_missing`.

Those three reasons derive from one systemic missing authority input, not three independent market failures.

The standard-4h consumer correctly requires the exact predecessor 1h memory to retain `supporting_context_json.memory_build_evidence_overlays.safety_composite_id`. The produced first-hour memories contained no such binding. The B.2 safety adapter therefore failed closed.

There were zero campaign/physical `WINDOW_4H` rows, zero 4h Scheduler jobs/work rows, no 4h collection, and no 4h memory. `SAFE_STOP_4H_TERMINAL_INCOMPLETE` is the downstream terminal symptom, not the root cause.

No attempt-linked retrieval, paper-decision, position, trade, audit, or PnL rows were created. All downstream financial capabilities remain locked.

## Repair audit result

The repair-scope audit closed PASS:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_SCOPE_AUDIT_PASS`

The audit proved the defect is broader than a missing copied ID. The committed safety composite freshness contract is 30 minutes, while the first-hour close is beyond the earlier 15m safety checkpoint. Therefore copying the old 15m safety-composite ID into the 1h memory is prohibited and would not constitute a valid repair.

The canonical repair is fresh first-hour safety authority:

1. during the already Scheduler-owned `CONTINUATION_CLOSE`, collect fresh safety through the existing Source-Governed context path;
2. persist that evidence/composite against the exact first-hour closing snapshot;
3. close the exact `WINDOW_1H` predecessor;
4. bind the exact fresh `safety_composite_id` into that first-hour memory before outcome/audit/E2Z;
5. leave the B.2 exact safety consumer and all freshness/provenance/safety hard gates unchanged.

The bounded worst-case first-hour safety bundle is three source transports, so `CONTINUATION_CLOSE` requires four reserved source operations total: one exact-pair close observation plus three first-hour safety reservations. No new Scheduler job is required.

Target standard request ceilings become:

- FAST + FAST: `236`;
- FAST + NORMAL: `188`;
- NORMAL + NORMAL: `140`.

Scheduler ceilings remain `210`, `162`, and `114` respectively.

## Repair design result

The repair design closed PASS:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_DESIGN_PASS`

Required exact order:

```text
Scheduler-owned CONTINUATION_CLOSE
-> collect fresh safety-only governed context
-> persist final exact-pair closing snapshot
-> persist fresh safety/composite against that exact snapshot
-> resolve exact current-run 15m predecessor
-> close exact WINDOW_1H
-> bind exact fresh safety composite ID
-> derive first-hour outcome
-> audit / E2Z
-> later standard 4h barrier consumes unchanged B.2 authority
```

`lane_e2o_1h_window_close.py` remains source-free. Source calls stay in `one_command_15m_factory.py`. B.2 must not fall back to an arbitrary latest safety composite. No freshness, provenance, safety, Source Governor, Scheduler, identity, or continuity gate may be weakened.

## Completed implementation status

Repair branch:

`agent/v2-9-8b-second-standard-4h-safety-provenance-repair`

Durable implementation verdict:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

Exact repaired implementation HEAD:

`0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`

Implementation is complete and the focused bounded offline proof passed.

Completed implementation surfaces:

- `src/printer_v1/operator_cli/first_hour_safety_binding.py` — exact source-free fail-closed first-hour safety-composite binding helper;
- `src/printer_v1/sources/measured_transport.py` — `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3` and `CONTINUATION_CLOSE = 4` reservation capacity;
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` — explicit first-hour safety request components in one-token and standard campaign lifecycle budgets;
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — Scheduler-owned `CONTINUATION_CLOSE` collects safety-only governed context before the final exact-pair snapshot, persists it against that exact closing snapshot, binds the exact fresh composite into the produced `WINDOW_1H` before outcome/audit/E2Z, threads `context_adapter_factories`, raises factory-local request ceilings, and labels the three first-hour safety reservations;
- `src/printer_v1/operator_cli/operational_standard_4h.py` — `LIFECYCLE_REQUEST_OUTER_CEILING = 236`, Scheduler outer ceiling unchanged at `210`.

Confirmed repaired lifecycle budget truth:

| lanes | 4h eligible | requests | Scheduler |
|---|---|---:|---:|
| FAST + FAST | both | 236 | 210 |
| FAST + NORMAL | both | 188 | 162 |
| NORMAL + NORMAL | both | 140 | 114 |
| FAST + FAST | none | 98 | 82 |

`CONTINUATION_CLOSE` reserves exactly `4`: one exact-pair close observation plus three worst-case fresh 1h safety transports. No new Scheduler job was introduced. The unchanged B.2 consumer `load_authoritative_window_safety()` and source-free `lane_e2o_1h_window_close.py` were not modified.

Unrelated pre-existing Git-provenance fixture failures remain separately documented; they are not a reason to reinterpret the safety repair as failed. The count was previously recorded here as three; the measured count on the current branch is `31 failed, 29 passed`, identical before and after the budget-authority repair.

## Fresh operational rereadiness result — HISTORICAL, SUPERSEDED

> Superseded. The blocking drift below was repaired and closed, and fresh operational rereadiness has since closed **PASS** at `61647122d33cbf45f0e321a989f4ea14ca00b1b1`. Retained as the historical record of why the repair chain was required.

Post-safety-repair operational rereadiness was **BLOCKED** with verdict:

`V2_9_8B_POST_SAFETY_PROVENANCE_REPAIR_OPERATIONAL_REREADINESS_BLOCKED_PUBLIC_BUDGET_AUTHORITY_DRIFT`

Audit closeout:

`docs/printer-v1-v2-9-8b-post-safety-provenance-repair-operational-rereadiness-audit.md`

Primary classification:

`PUBLIC_STANDARD_FOUR_HOUR_BUDGET_AUTHORITY_DRIFT_AFTER_FIRST_HOUR_SAFETY_REPAIR`

Static exact-HEAD inspection proved the repair's `236` worst-case request contract did not propagate through every live public/authorization owner:

- `one_token_4h_runtime` and `operational_standard_4h` carry the repaired lifecycle truth;
- `operational_memory_factory_command.py` still publishes and persists standard-four-hour `230` total / `114` per-token request capacity;
- `standard_four_hour_one_shot_wrapper.py` still generates and validates one-use authorization documents with request outer ceiling `230`;
- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py` still explicitly pins those stale `230/114` public and wrapper contracts while other repaired tests pin `236`.

A fresh authorization prepared from the current committed wrapper would therefore bind a request-capacity contract that contradicts the repaired lifecycle planner/factory contract.

This is sufficient to block rereadiness before host-local execution. No fresh host/DB rereadiness PASS is claimed. The historical rereadiness helper is also not reusable unchanged because it encodes older branch/DB/application-marker state and the old `230` ceiling.

No Printer provider/source run, Central Scheduler runtime, authoritative DB mutation, memory generation, new authorization, authorization reuse, standard-four-hour rerun/resume/restart/successor, or downstream financial action occurred in this rereadiness audit.

## Public budget-authority repair chain — CLOSED

The blocking drift above is **repaired and closed offline**.

Implementation closeout:

`docs/printer-v1-v2-9-8b-second-standard-four-hour-public-budget-authority-repair-implementation-closeout.md`

Verdict:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

Implementation branch: `agent/v2-9-8b-public-budget-authority-repair-implementation`

`operational_standard_4h.standard_four_hour_capacity_contract()` now derives the standard worst-case public capacity from the canonical `one_token_4h_runtime.standard_campaign_lifecycle_budget(...)` FAST+FAST / both-eligible calculation. The public command and the one-shot wrapper own no independent standard-four-hour numeric capacity and project that one contract.

Exact cross-owner equality proven offline:

- canonical worst-case lifecycle: `236 / 210`;
- public standard contract: `236 / 117 / 210`;
- command standard policy, standard preflight, immutable campaign config: `236 / 117 / 210`;
- one-shot wrapper authorization: `236 / 210`;
- a newly constructed `230` authorization document: **rejected, fail-closed**;
- mixed/normal lifecycle budgets unchanged: `188/162` and `140/114`;
- FAST+FAST no-4h prefix unchanged: `98/82`;
- `CONTINUATION_CLOSE` still reserves exactly `4`;
- no Scheduler increase; no stale-15m safety fallback.

Focused proof: `48 passed, 14 subtests passed`. Selective-1h behavior unchanged; the adjacent `92/45` versus `98/48` drift remains separately recorded.

No provider/source run, Central Scheduler runtime, authoritative DB mutation, memory generation, authorization creation/review/reuse, or standard-four-hour run occurred in the repair implementation lane. The frozen consumed launch branch `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation` at `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7` is unchanged.

## Post-public-budget-authority-repair operational rereadiness — CLOSED PASS

Fresh read-only host rereadiness closed PASS at exact HEAD `61647122d33cbf45f0e321a989f4ea14ca00b1b1`.

Closeout:

`docs/printer-v1-v2-9-8b-post-public-budget-authority-repair-operational-rereadiness-closeout.md`

Verdict:

`V2_9_8B_POST_PUBLIC_BUDGET_AUTHORITY_REPAIR_OPERATIONAL_REREADINESS_CLOSEOUT_PASS`

Rereadiness branch: `agent/v2-9-8b-post-public-budget-authority-repair-operational-rereadiness`

Durable rereadiness facts:

- authoritative DB SHA-256 before and after: `1ec5bfe3bb3f554cae975720d9a9c7411bfc03c51628f75e76012138ca2d73d1` — byte-identical, trust anchor matched exactly, no new anchor adopted;
- migrations `54`, head `054_pre_lifecycle_discovery_refresh_wait.sql`, integrity `ok`, foreign-key violations `0`, no SQLite sidecars;
- all active campaign/run/discovery/factory/Scheduler/proof-supervision counts `0`; locked downstream capability baseline unchanged (validator PASS);
- host quiescent before and after: no Printer processes, no DB open handles, no campaign lease locks, no ordinary or standard wrapper staging residue, no stale wrapper-bound environment variables;
- frozen consumed launch branch `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation` still exactly `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`;
- retained untracked evidence advanced `27` → `28`, digest `4b177980d054d79866d88d91ba3987a544cbb71672231a7f58bd74aae8d1a4bb`, identical before and after. The prior `27`-file inventory reproduced its recorded digest `e8e20503c391384fb1f2363d34b88d189c4c501afbfb38b3fa3950067f36f53f` byte-exactly; the only addition is the second consumed authorization file. Authority remains `AUDIT_ONLY_NOT_RUNTIME_ALLOWLIST`;
- both consumed authorizations verified by binding, not marker count: each marker's `authorization_id`/`authorization_sha256`/`manifest_sha256` resolve to its own authorization and manifest, each `child-terminal.json` carries its own execution identity, and every reuse flag (`automatic_retry`, `manual_rerun`, `resume`, `restart`, `successor`) is `False` with `allowed_invocation_count = 1`. Both carry historical `230` policy and would now be rejected as fresh authorization policy;
- zero-I/O readiness proven under active egress and DB-write guards: source contract `READY`, concrete composition `READY` (`20` builders), runtime dependency `READY`, holder budget `READY`; external source requests `0`, Scheduler runtime calls `0`, authoritative DB writes `0`, runtime artifacts `0`, authorization created `false`, campaign started `false`;
- repaired capacity freshly re-measured at this HEAD: canonical FAST+FAST both-eligible lifecycle `236 / 210`; public standard contract, command policy and standard preflight projection `236 / 117 / 210`; wrapper authorization contract `236 / 210`; Scheduler outer ceiling unchanged at `210`; `CONTINUATION_CLOSE` reserves exactly `4`; first-hour safety transports `3` per token; `WINDOW_12H` and `WINDOW_24H` locked; automatic retries, restarts and successors all zero.

No Git-provenance authorization was fabricated. The historical rereadiness helper was **not** executed — it encodes an older branch, older DB anchor, a zero-marker assumption and the stale `230` ceiling; its inventory table was read statically as historical reference only.

No provider/source run, Central Scheduler runtime, authoritative DB mutation, memory generation, authorization creation/review/reuse, wrapper application, standard-four-hour run, or downstream financial action occurred in this rereadiness lane.

## Third standard-four-hour authorization — PREPARED AND INDEPENDENTLY REVIEWED, UNCONSUMED

Closeout:

`docs/printer-v1-v2-9-8b-fresh-one-use-standard-four-hour-authorization-review-closeout.md`

Verdict:

`V2_9_8B_FRESH_ONE_USE_STANDARD_FOUR_HOUR_AUTHORIZATION_REVIEW_CLOSEOUT_PASS`

Review branch: `agent/v2-9-8b-independent-fresh-standard-4h-authorization-review-closeout` (started from, and evaluated at, exactly `0be6b4f7f56a501a40b2ef02521689ccaffb0ce9`)

Review closeout documentation commit: `d80c8dadfb054c6a959515f8fc58ae47821da7d5`. The final closeout SHA is the tip of that review branch. The branch carries documentation only.

Authorization identity:

- ID: `V2_9_8B_STANDARD_4H_AUTH_20260811T135326Z`;
- path: `operator-runs/v2-9-8b-standard-four-hour-final-authorization/V2_9_8B_STANDARD_4H_AUTH_20260811T135326Z/final_authorization.json` (untracked);
- SHA-256: `446e50cf376e576bf308ceee254d025e8fa3221683c9e91e1dcc1f0d2976db36`;
- frozen launch branch: `agent/v2-9-8b-fresh-one-use-standard-4h-authorization-preparation`;
- exact launch HEAD: `0be6b4f7f56a501a40b2ef02521689ccaffb0ce9`;
- authorized `2026-08-11T13:53:26.614842+00:00`, **expires `2026-08-12T01:53:26.614842+00:00`**, validity `43200`s.

The authorization stays bound to the frozen preparation branch, **not** to the review-closeout branch.

Durable review facts:

- committed standard-four-hour validator PASS; schema, ID, branch, HEAD, mode `standard-four-hour-run`, operator-approved `true`, token capacity `2`, request ceiling `236`, Scheduler ceiling `210`, `WINDOW_12H`/`WINDOW_24H` locked, `allowed_invocation_count = 1`, retry/rerun/resume/restart/successor all `false` — all exact;
- temporal validity re-evaluated live at review: `TEMPORALLY_VALID`, `42488`s remaining;
- authoritative DB binding exact on all seven fields (`1ec5bfe3…2d73d1`, `79515648`, inode `1230526`, `mtime_ns` `1786414776320865281`, migrations `54`, head `054_pre_lifecycle_discovery_refresh_wait.sql`); integrity `ok`, FK violations `0`, no sidecars, no open handle; DB **byte-identical before and after**;
- `prior_authorizations_non_reusable`: `18` IDs, sorted, unique, current excluded, both consumed standard-four-hour IDs present, each verified by exact identity/binding (file hashed, embedded ID parsed) rather than directory count;
- manifest independently rebuilt in memory via committed `build_manifest_bytes(...)`: `848971c3e43ae6652b6f5d39acfa2c023856313eed8dca681a6ffe9e26a462ae`, byte-identical to expectation; the external preparation manifest was secondary hash evidence only;
- allowed-file-set SHA-256 after pre-marker validation: `3a304d8ecb3aa2739a5c1762867df2465f4fa3a62136faa1bbe40040a4403865`, allowed paths `31`;
- `operator-runs/` fully reconciled: `78` tracked + `29` untracked-visible + `2` git-ignored-but-allowed = `109`; no unexplained visible or ignored file; untracked-visible advanced `28` → `29` (sole addition: this authorization);
- live pre-marker Git provenance PASS against the real branch/HEAD/worktree/inventory/migration package/authorization package/historical evidence, no check weakened;
- the `31` Git-provenance fixture failures reproduce but are **root-caused** as one stale fixture `migration_execution_id` failing fail-closed (negative tests still block, only the message differs); the same validator passes live, so they are **not** a current-host provenance defect. Still unrepaired and unowned;
- migration-ledger guard PASS in review/read-only mode: claimed == observed, `honest: true`, ledger digest `b2e26dd36cee8a8fff4839632bb95e02842ed970f6c0ff96ccf08620386ffd2d`, no mutation;
- zero-I/O readiness under active egress and DB-write guards: source contract `READY` (external requests `0`, secret material `false`), concrete composition `READY` (`20` builders), runtime dependency `READY`, holder budget `READY` (source calls `0`); capacity `236 / 117 / 210`, Scheduler outer ceiling `210`, `CONTINUATION_CLOSE = 4`, first-hour safety transports `3`, 12h/24h locked; external provider requests `0`, Scheduler runtime calls `0`, authoritative DB writes `0`, campaign starts `0`;
- **proven unconsumed**: no application-marker, no `child-terminal.json`, no canonical application directory for this authorization anywhere under `~/PrinterOperations`, no standard-four-hour child process, `0` DB rows referencing the authorization ID, no consumption timestamp, no staging residue. `apply_authorization_once(...)` was not called and the PowerShell/start wrapper was not invoked.

The older consumed launch branch `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation` remains exactly `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`. The frozen preparation branch was not committed to, edited, reset, merged, rebased, or moved.

## Current lane boundary

Current branch:

`agent/v2-9-8b-independent-fresh-standard-4h-authorization-review-closeout`

The authorization is now **unconsumed but independently approved for at most one canonical application, while still temporally valid and while all launch-time checks still pass at consumption time**. It is not reusable and is not blanket permission.

The only next permitted lane is:

`SEPARATELY_OPERATOR_STARTED_STANDARD_FOUR_HOUR_BOUNDED_ATTEMPT`

That lane is **not** unlocked automatically by this review closeout. It requires a separate explicit operator start, it must begin before `2026-08-12T01:53:26.614842+00:00`, and every launch-time check must pass again at that moment. After expiry this approval is void and a fresh preparation plus independent review cycle is required.

Still not allowed:

- consuming this authorization outside a separately operator-started attempt;
- reuse of this authorization beyond its single permitted application;
- creating another authorization;
- provider/source fetching outside the operator-started attempt;
- Central Scheduler runtime outside the operator-started attempt;
- authoritative DB mutation outside the operator-started attempt;
- memory generation outside the operator-started attempt;
- reuse of any of the `18` historical authorizations;
- rerun/resume/restart/successor of this or either consumed attempt;
- a second standard-four-hour attempt from this authorization;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL.

Preserve the required sequence:

```text
repair-scope audit
-> design/specification
-> implementation if approved
-> bounded offline proof/test
-> closeout
-> fresh operational rereadiness            <- CLOSED PASS
-> fresh one-use authorization preparation  <- CLOSED
-> independent authorization review/closeout <- CLOSED PASS here
-> separately operator-started bounded standard-four-hour attempt <- next permitted lane
```

No step authorizes the next automatically.

## Permanent restrictions

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence, or weighted decision logic;
- no embeddings or vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval before its explicit approved lane;
- no paper decisions before their explicit approved lane;
- no BUY/SELL/HOLD before its explicit approved lane;
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Assistant execution rule

Preserve the V2 sequence and use minimum sufficient risk-based verification.

The public budget-authority blocker is now audited, designed, implemented, proven offline, and closed. Do not create another authorization or run another standard-four-hour attempt until that closed repair chain is followed by a fresh operational rereadiness PASS and an independent authorization closeout.