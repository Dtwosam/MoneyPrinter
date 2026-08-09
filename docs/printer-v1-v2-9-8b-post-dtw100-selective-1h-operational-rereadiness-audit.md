# Printer V1 V2-9.8B Post-DTW100 Selective WINDOW_1H Operational Rereadiness Audit

## Verdict

```text
V2_9_8B_POST_DTW100_SELECTIVE_1H_REREADINESS_BLOCKED_AUTHORIZATION_INTEGRATION_DESIGN_REQUIRED
```

The historical E2Q blocker is retired and the current selective `WINDOW_1H` memory/runtime path remains structurally present. However, the path is **not ready for a new post-DTW100 operational proof** because the hardened post-DTW99/DTW100 one-use execution-authority boundary is implemented only for ordinary `run` / `WINDOW_15M` operation.

Current selective-1h proof mode can still be dispatched directly with `--operator-approved` and does not consume the one-use Git-provenance manifest/application-marker/child-terminal authorization chain that DTW100 established as the authoritative operational trust boundary.

This is an audit/readiness closeout only. It does not design or implement the repair, create authorization, invoke a wrapper, run providers/RPC, start Scheduler runtime, mutate the authoritative database, generate memory, run `WINDOW_15M` or `WINDOW_1H`, activate longer windows, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

---

## 1. Baseline and branch verification

- Repository: `Dtwosam/MoneyPrinter`
- Required starting audit closeout: `b07a946d56886d923129b3eacade775f19f58d71`
- Starting branch checked: `agent/v2-9-8b-post-dtw100-e2q-window1h-current-state-audit`
- Observed branch state before this lane: exactly `b07a946d56886d923129b3eacade775f19f58d71`, 0 ahead / 0 behind
- New audit branch: `agent/v2-9-8b-post-dtw100-selective-1h-rereadiness`
- New branch created exactly from `b07a946d56886d923129b3eacade775f19f58d71`
- DTW100 closeout ancestor: `059f4fad26d508b09cc361bc267049adc3cdb9ce`
- Delta from DTW100 closeout to this lane start: only the post-DTW100 E2Q audit plan + closeout documentation

No local checkout or authoritative DB was mutated by this audit.

---

## 2. Source stack applied

This audit used the active Printer V1 stack, including:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-9-8b-dtw100-window15m-clean-memory-campaign-closeout.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-e2q-window1h-current-state-audit-closeout.md`
- current selective-1h implementation, proof-command, ownership, E2Q/E2Z, one-shot-wrapper, authorization, and focused test surfaces
- historical selective-1h comprehensive repair closeout and operator-readiness lineage

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside the source stack, not the sole source of truth.

---

## 3. DTW100 authoritative trust anchor carried forward

The DTW100 closeout independently established the post-run authoritative DB trust anchor:

- SHA-256: `6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb`
- migrations: `54`
- migration head: `054_pre_lifecycle_discovery_refresh_wait.sql`
- integrity: `ok`
- foreign-key violations: `0`
- SQLite sidecars: none
- zero active/locked Scheduler residue at closeout
- two clean-promoted `WINDOW_15M` campaign windows

Migration `047_campaign_oneshot_linkage_binds.sql`, required by the selective-1h campaign/factory lineage, remains in the canonical migration history and is therefore contained by the later migration-054 authoritative state.

This audit did not reopen the operator-host database. The exact byte identity above remains the latest committed trust anchor. Any later authorization-preparation lane must independently re-read and bind the then-current authoritative DB identity; this audit does not assume the local file can never drift outside Git history.

Classification: `READY_AS_LAST_VERIFIED_TRUST_ANCHOR`, with fresh byte-identity verification required before any later authorization.

---

## 4. Current selective WINDOW_1H core path

The canonical selective continuation owner remains:

- `src/printer_v1/operator_cli/operational_selective_1h.py`

The public operational command still exposes:

- `selective-1h-preflight`
- `selective-1h-proof`

The current policy remains bounded and separate from ordinary production:

- token capacity: maximum 2
- main early window: `WINDOW_15M`
- main 15m span: `900s`
- selective 1h continuation phase: `2700s`
- selective lifecycle envelope: `3900s`
- governed selective request ceiling: `92`
- governed requests per token: `45`
- Scheduler row ceiling: `82`
- automatic retries: `0`
- `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`: locked
- ordinary `run`: still `selective_1h_continuation=False`

The selective owner still consumes authoritative clean predecessor episodes, exact campaign/factory/window lineage, categorical token-local continuation policy, safety/continuity facts, and no scoring/ranking/confidence/weighted logic.

Classification: `READY_AS_COMMITTED` for the core selective continuation architecture.

---

## 5. E2Q / E2Z and clean-memory semantics

The preceding audit already closed the historical X14 E2Q blocker as superseded with proof.

Current E2Q admits genuine `WINDOW_1H` only through its distinct anti-fabrication rules and keeps `WINDOW_5M_MICRO_EVENT` support-only.

Current E2Z allows `WINDOW_15M`, `WINDOW_1H`, and `WINDOW_4H` candidates at the per-window clean-promotion boundary. The current atomic clean-object owner derives the actual episode kind from the window itself:

```text
f"{window['window_kind']}_CLEAN_MEMORY"
```

Therefore a genuine 1h promotion becomes `WINDOW_1H_CLEAN_MEMORY`; the older `E2Z_EPISODE_KIND = WINDOW_15M_CLEAN_MEMORY` constant is stale compatibility surface and is not the active insert value.

No current E2Q/E2Z blocker was found that justifies another historical audit-gate repair.

Classification: `READY_AS_COMMITTED`.

---

## 6. Historical selective-1h repair status

The July 28 comprehensive selective-1h repair closed the known in-repository runtime blockers from three retained attempts, including:

- cooldown expiry/state-machine defects;
- exact-lane requalification claim;
- tracking-aware reserve progression;
- avoidable exact-pool source work;
- provider-vs-market-shortage reporting;
- pre-lifecycle candidate/admission reporting;
- selective-mode reporting before factory-run creation;
- earlier safety linkage, close ordering, immutable continuation, campaign-window, and replay issues.

Its verdict was:

```text
V2_9_8B_SELECTIVE_1H_COMPREHENSIVE_REPAIR_PASS
```

It explicitly left the repaired full live route operationally unproven and required a fresh read-only readiness review before another live proof.

No reason was found to reopen those already-repaired defects from history.

---

## 7. Post-DTW100 execution-authority blocker

### 7.1 Current hardened one-shot boundary is ordinary WINDOW_15M only

DTW100 ran through:

```text
scripts/Start-PrinterV1-Window15M-OneShot.ps1
  -> printer_v1.operator_cli.window_15m_one_shot_wrapper
  -> create-once application marker
  -> exact Git-provenance manifest + authorization binding
  -> child terminal binding
  -> printer_v1.operator_cli.operational_memory_factory_command run --operator-approved
```

The wrapper is intentionally narrow and currently validates all of the following:

- authorization command mode must be `run`;
- authorization is for an approved ordinary run;
- campaign `main_window` must be `WINDOW_15M`;
- `selective_1h_continuation` must be `false`;
- invocation count must be exactly one;
- automatic retry/manual rerun/restart/resume/successor must all be false;
- the child command is hardcoded to `run --operator-approved`.

That behavior is correct for ordinary WINDOW_15M and must not be loosened merely to force a selective-1h proof through it.

Classification: `EXPECTED_OPERATIONAL_CONFIGURATION`.

### 7.2 Current command accepts provenance bindings only for ordinary run/preflight

Current `operational_memory_factory_command.py` declares:

```text
GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES = ("preflight-only", "run")
```

If manifest/application-marker bindings are supplied to `selective-1h-preflight` or `selective-1h-proof`, the command fails because those modes are not supported by the integration.

The child-terminal binding is also accepted only for ordinary `run`.

Classification: `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` for post-DTW100 selective-1h authority.

### 7.3 Selective proof still dispatches without the one-use authority object

Current CLI dispatch is effectively:

```text
selective-1h-proof --operator-approved
  -> run_selective_1h_proof(operator_approved=True)
```

No `git_provenance_authorization` is passed to that branch.

The committed public-command test explicitly protects that old shape: selective proof dispatch is expected to call only `run_selective_1h_proof(operator_approved=True)`.

Therefore current source contains two incompatible operational authority eras:

1. **post-DTW99/DTW100 ordinary run:** exact one-use authorization + manifest + application marker + child terminal binding;
2. **older selective-1h proof:** direct operator-approved mode with its own preflight but no one-use authorization consumption.

A fresh post-DTW100 selective proof must not bypass the newer trust boundary.

Classification: `DESIGN_GAP` + `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`.

---

## 8. No selective-1h one-shot authorization bridge found

Static repository review found no later selective-1h equivalent that:

- creates a selective-1h final authorization package;
- binds exact current Git branch/HEAD and DB byte identity;
- creates a selective-1h create-once application marker;
- enumerates the allowed file set under the current authorization inventory law;
- passes exact manifest/marker bindings into `selective-1h-proof`;
- provides a selective-1h child terminal envelope;
- atomically launches exactly one selective proof;
- permanently prevents reuse after consumption.

The absence is material because the preceding post-DTW100 E2Q audit explicitly requires any future 1h operational proof to use its own approved readiness/authorization sequence and exact current bindings.

Verdict impact: BLOCKING.

---

## 9. Post-DTW98 wall-time drift in the old selective readiness wording

The current policy dataclass now includes a separate pre-lifecycle acquisition horizon:

```text
pre_lifecycle_acquisition_duration_seconds = 900
```

Current runtime records this as separate from the post-supply lifecycle duration and computes:

```text
total_wall_time_envelope_seconds =
    pre_lifecycle_acquisition_duration_seconds + duration_seconds
```

For selective-1h proof policy:

```text
900 + 3900 = 4800 seconds
```

Therefore the older selective-1h proof-command/readiness statement that `3900s` is the **total command duration ceiling** is stale after the post-DTW98 temporal-acquisition work.

The current selective preflight still reports `proof_ceilings.duration_seconds = 3900` and host-awake requirements, but it does not surface the 4800-second end-to-end wall-time envelope in that selective-specific report.

This is not evidence that runtime duration is unbounded: runtime already carries both values explicitly. It is a readiness/authorization/reporting drift that must be corrected before a fresh proof package is frozen.

Classification: `DOCUMENTATION_OR_REPORTING_GAP` + `DESIGN_INPUT_DRIFT`.

---

## 10. Source-budget / accounting rereadiness

The selective preflight still invokes the static holder/admission budget owner with:

- admission operation ceiling `45`;
- discovery request ceiling `2`;
- governed selective request ceiling `92`;
- per-token ceiling `45`.

The current holder budget preflight validates the authoritative holder/admission constants and records the outer ceilings; it does **not** independently re-derive the full post-DTW98 temporal-acquisition + selective-lifecycle end-to-end source envelope.

DTW100 later introduced and authorization-bound a separate 900-second pre-lifecycle acquisition stage and cumulative discovery-operation controls for ordinary 15m operation.

Therefore a new selective authorization design must re-derive and freeze the **current** source/accounting envelope from present owners. It must not simply copy the July selective proof's `92` wording and call that the total current one-shot source budget without proving the relationship to the newer pre-lifecycle stage.

This audit does not assert that `92` is unsafe or insufficient; it asserts that the current post-DTW100 one-shot authorization package lacks a source-grounded selective derivation covering both stages.

Classification: `READINESS_EVIDENCE_GAP`, design required before authorization.

---

## 11. Scheduler ownership and cleanup

No new Scheduler-owner defect was found statically.

The selective path continues to reuse the existing campaign/factory Scheduler ownership rather than creating an independent timer or API loop. Historical comprehensive repair and focused tests cover bounded 1h scheduling, collection, closeout, cleanup, zero active/orphan residue, and no automatic retry/restart/successor.

The newer pre-lifecycle temporal acquisition path also explicitly assigns delayed refresh work to Central Scheduler and provider work to Source Governor.

A future design must preserve these owners and include the pre-lifecycle waiting/refresh Scheduler rows in its exact authorization/proof accounting.

Classification: `READY_AS_COMMITTED`, subject to new end-to-end authorization binding/proof.

---

## 12. Source Governor ownership

No bypass was found in the current selective continuation architecture. The canonical campaign/factory path remains the owner and all real source work must remain Source-Governed.

The missing piece is not a new provider loop; it is the execution-authority wrapper around the existing governed path.

Classification: `READY_AS_COMMITTED`.

---

## 13. Exact blocker map

| Area | Current state | Classification | Blocking? |
|---|---|---|---|
| E2Q genuine WINDOW_1H | repaired + bounded proof crossed | READY_AS_COMMITTED | no |
| E2Z WINDOW_1H clean promotion | timeframe-aware atomic promotion | READY_AS_COMMITTED | no |
| Migration 047 lineage bind | contained in current migration-054 history | READY_AS_LAST_VERIFIED | no |
| Selective token-local continuation | committed categorical owner | READY_AS_COMMITTED | no |
| 4h/12h/24h locks | preserved | EXPECTED_OPERATIONAL_CONFIGURATION | no |
| Source Governor ownership | existing owner preserved | READY_AS_COMMITTED | no |
| Central Scheduler ownership | existing owner preserved | READY_AS_COMMITTED | no |
| Ordinary WINDOW_15M one-shot wrapper | correctly 15m-only | EXPECTED_OPERATIONAL_CONFIGURATION | no |
| Selective proof one-use authorization | absent | MISSING_APPROVED_IMPLEMENTATION_BOUNDARY | **yes** |
| Manifest/application-marker integration for selective modes | unsupported | DESIGN_GAP | **yes** |
| Child terminal binding for selective proof | ordinary run only | DESIGN_GAP | **yes** |
| Selective wall-time reporting | stale 3900-total wording vs current 4800 envelope | REPORTING/DESIGN_INPUT_DRIFT | **yes before authorization** |
| End-to-end current source/accounting derivation | not frozen for post-DTW100 selective proof | READINESS_EVIDENCE_GAP | **yes before authorization** |
| Current operator-host DB byte identity | latest committed anchor known, not re-read in this audit | FRESH_BINDING_REQUIRED_LATER | no for design; yes before authorization |

---

## 14. Why runtime is not permitted now

Running the current selective proof directly would choose between two bad options:

1. launch `selective-1h-proof --operator-approved` and bypass the newer one-use authorization/marker/child-terminal trust boundary; or
2. try to feed DTW100's ordinary authorization bindings into selective mode, which current code intentionally rejects.

Neither is roadmap-compliant.

The correct response is to stop before runtime and design the missing authority bridge.

---

## 15. Minimum next design boundary

Exact next permitted lane:

```text
V2-9.8B Post-DTW100 Selective WINDOW_1H One-Shot Authorization / Wrapper Integration Design
```

Type: **design/specification only**.

The design must decide the smallest safe integration that preserves ordinary 15m behavior while giving selective-1h its own exact execution authority. It must specify at minimum:

1. selective-1h authorization package/schema identity;
2. exact current branch/HEAD binding;
3. exact authoritative DB byte/migration binding;
4. one-use invocation count and permanent non-reuse;
5. create-once application-marker identity;
6. Git-provenance manifest binding for `selective-1h-proof`;
7. selective child-terminal envelope/binding;
8. wrapper command that launches exactly `selective-1h-proof --operator-approved`;
9. ordinary `run` isolation so its current wrapper stays 15m-only;
10. fixed campaign count/cycle count/token capacity;
11. exact selective policy: 15m predecessor + categorical 1h continuation, 4h+ locked;
12. current 900s pre-lifecycle horizon + 3900s lifecycle envelope + 4800s total wall-time envelope;
13. fresh end-to-end Source Governor operation/request derivation including the newer pre-lifecycle stage;
14. fresh Central Scheduler row/close-reservation derivation including temporal refresh waits;
15. host-awake, lease, heartbeat, safe-stop, cleanup, no-retry/no-restart/no-successor rules;
16. backup/restore rehearsal before any future campaign creation;
17. exact pre-consumption and post-consumption artifact inventory rules;
18. report-only replay / terminal evidence expectations;
19. zero-delta downstream capability checks;
20. rollback and stop-before-runtime conditions.

The design must **not** simply broaden the existing ordinary wrapper's acceptance checks without proving mode separation.

---

## 16. Minimum future sequence after this audit

```text
1. Selective-1h one-shot authorization/wrapper integration design
2. Narrow implementation, if approved
3. Bounded disposable/offline proof of the authority bridge
4. Independent implementation closeout
5. Fresh post-implementation selective-1h rereadiness review
6. Fresh exact-HEAD / exact-DB one-use selective-1h authorization preparation
7. Independent authorization review and closeout
8. Exactly one manually started bounded operational selective WINDOW_1H proof
9. Independent campaign/proof closeout
```

Any blocker found in steps 2-7 must stop the sequence before runtime.

No historical X14, V2-7, July selective-1h attempt, DTW99 authorization, or DTW100 authorization may be reused as execution authority.

---

## 17. Money-usefulness contribution

This audit prevents the project from spending a long live proof through an older, weaker launch path after DTW100 established a stronger one-use operational trust boundary.

The selective-1h capability is useful because it can capture survival, continuation, collapse, and transition evidence beyond the first 15 minutes without tracking every token for every timeframe. But that learning is only useful if the longer run is exact, bounded, attributable, non-reusable, and cleanly closed.

This lane improves **trust in future memory growth**, not trading capability.

---

## 18. What this lane improves

- reconciles selective-1h implementation with the newer DTW100 one-shot trust model;
- identifies execution authority as the real current blocker instead of reopening E2Q;
- catches the post-DTW98 4800-second total wall-time drift;
- separates runtime-ready core memory code from not-yet-ready launch authorization;
- prevents reuse of consumed/historical authorizations;
- gives the next design lane a narrow, source-grounded target.

---

## 19. What this lane still does not unlock

Still locked:

- creation of a selective-1h authorization;
- any wrapper invocation;
- `WINDOW_15M` rerun;
- `WINDOW_1H` operational proof/runtime;
- normal-production 1h activation;
- `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` operation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions;
- trades;
- paper-trade audits;
- PnL;
- wallet/private keys/signing/real funds/live execution;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors;
- Source Governor bypass;
- Central Scheduler bypass;
- dirty-memory use for retrieval/decisions.

---

## 20. Verification performed

Risk-based verification for this audit was static/read-only only:

- exact Git branch/commit comparison;
- active build-order/source-stack review;
- current public PowerShell command inspection;
- current operational command/policy inspection;
- current one-shot wrapper inspection;
- current selective owner inspection;
- current E2Z + atomic clean-object promotion inspection;
- current migration 047 and migration 054 inspection;
- current committed public-command test inspection;
- historical selective comprehensive repair reconciliation;
- DTW99/DTW100 one-use authorization/closeout reconciliation;
- repository search for a later selective-1h authorization bridge.

No tests were executed because no code changed and the blocking behavior is explicit in current source contracts. No authoritative DB inspection was required to establish the control-plane blocker.

---

## 21. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Required control |
|---|---|---|
| Direct selective proof bypasses DTW100 one-use authority | weaker operational trust than current 15m standard | design dedicated selective authority bridge |
| Broadening ordinary wrapper casually | could weaken proven 15m trust boundary | preserve mode isolation; design first |
| Reusing DTW100 authorization | consumed, wrong mode, wrong policy | fresh selective authorization only |
| Treating 3900s as total wall time | host-awake/expiry/supervision assumptions become false | bind 900 + 3900 = 4800 envelope |
| Copying old 92-request wording blindly | newer pre-lifecycle stage may be outside old derivation | fresh source-grounded end-to-end budget derivation |
| Ignoring temporal-refresh Scheduler rows | incomplete ownership/accounting proof | include current pre-lifecycle Scheduler ownership |
| Reopening E2Q repair | wasted lane and risk to already-proven gate | keep E2Q unchanged unless new evidence proves defect |
| Running before exact current DB rebind | proof may target drifted corpus | re-read and freeze DB identity before authorization |
| Provider or market supply failure | live proof can still stop honestly | preserve fail-closed classification; no retry |
| Host sleep during long proof | lease expiry/incomplete evidence | explicit host-awake + supervision contract |

---

## 22. Final closeout

```text
V2_9_8B_POST_DTW100_SELECTIVE_1H_REREADINESS_BLOCKED_AUTHORIZATION_INTEGRATION_DESIGN_REQUIRED
```

Core selective `WINDOW_1H` memory/runtime machinery is not the current blocker. The blocking gap is that selective proof execution has not been adopted into the hardened post-DTW100 one-use authorization, manifest, application-marker, child-terminal, and exact-binding trust boundary.

Stop here. Do not create authorization and do not run 1h. Proceed next only to the design/specification lane named in §15.
