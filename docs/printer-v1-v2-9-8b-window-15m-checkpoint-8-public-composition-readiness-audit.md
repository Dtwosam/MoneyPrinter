# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Public Composition Readiness Audit

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PUBLIC_COMPOSITION_AUDIT_CONFIRMED_FOUR_BLOCKERS`

Checkpoint 8 is started at the audit/readiness stage only.

- Baseline / Checkpoint 7 closeout: `1ceefb94746ea04152adb0fc3265048e258617de`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-8-full-disposable-public-composition-proof`
- Linear: `DTW-34`
- Audit mode: static/read-only inspection only

No authorization was created, consumed, or fabricated. No provider/RPC/WebSocket call, Source Governor runtime, Central Scheduler runtime, public campaign execution, database mutation, memory generation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, PnL, or longer-window activation occurred.

## Checkpoint 8 required outcome

DTW-34 requires one real public-composition proof using disposable migrated databases and deterministic fixture transports. The proof must demonstrate:

- one complete successful ordinary `WINDOW_15M` clean-memory closeout;
- the real public coordinator/composition rather than a fake campaign owner;
- deterministic fixture transports only, with no provider execution;
- major fail-closed boundaries;
- exact terminal-cause propagation;
- cleanup, lease release, zero active/locked residue, and report/replay integrity;
- all V1 capability locks preserved;
- independent post-proof inspection and final closeout;
- no operator/final authorization dependency for the proof.

This checkpoint is not permission to run the one-shot authorization wrapper or any provider-backed campaign.

## Existing readiness that should be preserved

### Public ordinary coordinator is the correct proof subject

`operational_memory_factory_command.run_operational_campaign()` is the public ordinary `WINDOW_15M` coordinator. It owns campaign construction, supervision, heartbeat signalling, the authoritative operational owner, cleanup, terminal reconciliation, full-run acceptance, clean-memory outcome construction, canonical terminal report publication, and terminal summary production.

The proof must keep this coordinator in the call graph.

### Shared production composition registry exists

`window_15m_concrete_composition.py` owns one `COMPOSITION_MATRIX` for the ordinary path and exposes the same registry to zero-I/O preflight and production runtime default constructors.

This is useful for C8 because fixture composition should replace transport implementations without inventing a second source graph or bypassing source ownership.

### Explicit fixture validation concept already exists

`ProductionFixtureAdapter` and `require_concrete_adapter(..., validation_mode="fixture" / test_only=True)` already establish that fixture adapters can be explicit and auditable rather than accepted because attributes happen to be missing.

### Disposable DB/module targets are testable

The public command resolves `AUTHORITATIVE_DB` and `ARTIFACT_ROOT` at runtime in multiple proof/test seams rather than permanently binding every function default at import time. A C8 proof can therefore use isolated migrated targets without touching the real operational database, provided the downstream target-binding law is satisfied by an approved proof capability.

### Operational mode rejects compressed proof plans

The authoritative owner rejects `compressed_two_token_proof_plan` and externally supplied `operational_natural_disposition`, then forces the ordinary natural-disposition law. C8 must not weaken this just to make the proof convenient.

## Four confirmed blockers

### 1. `PUBLIC_ORDINARY_RUN_REQUIRES_VALIDATED_EXTERNAL_AUTHORIZATION`

Current `run_operational_campaign()` cannot start an ordinary run with `git_provenance_authorization=None`.

The coordinator calls `validated_authorization_runtime_facts(git_provenance_authorization)` for ordinary `WINDOW_15M`; that owner raises `VALIDATED_AUTHORIZATION_REQUIRED` when the argument is `None`.

Why this blocks C8:

- DTW-34 explicitly says no authorization;
- using a real/final authorization would consume or depend on an operational authorization path that C8 is supposed to validate before later use;
- inventing a fake `ValidatedGitProvenanceAuthorization` would make the proof circular and would not prove a true no-authorization disposable composition boundary.

Required design direction:

Create an explicit C8 proof-only capability that reaches the same public ordinary coordinator without pretending an operator authorization exists. It must be impossible to select this capability for the canonical production DB or through the one-shot wrapper.

Do not weaken the normal production requirement for validated authorization.

### 2. `DISPOSABLE_15M_DB_BINDING_HAS_NO_NO_AUTH_PROOF_CAPABILITY`

The authoritative 15m owner always calls `validate_bound_operational_invocation()` when `fifteen_minute_only=True`.

The current `OperationalDatabaseTargetBinding` supports `PRODUCTION_AUTHORITATIVE` and `AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF`, but both downstream validation and the durable expectation require authorization/marker/one-shot history facts such as:

- `authorization_id`;
- authorization marker SHA;
- application marker SHA;
- `authorization_consumed_once=True`;
- invocation count exactly one;
- reuse flags all false.

A `None` binding fails with `OPERATIONAL_DB_BINDING_MISSING`.

Why this blocks C8:

Even if the public command is pointed at a disposable migrated DB, the real 15m owner cannot lawfully enter the lifecycle under a no-authorization proof.

Required design direction:

Add a separately typed, proof-only disposable target capability whose truth comes from the exact disposable DB identity, migration ledger, execution/campaign/run/cycle/configuration identities, and explicit no-provider/no-retry proof contract — not from fabricated operator authorization facts.

The existing production and authorized-disposable paths must remain unchanged and stricter.

### 3. `NO_AUTH_HOLDER_STAGE_OWNER_EVIDENCE_GAP`

The coordinator currently passes `_seal_holder_stage` to the authoritative owner only when `git_provenance_authorization is not None`.

At the same time, holder transport identities can be observed into the independent action-local ledger.

Why this blocks C8:

A no-authorization proof that merely bypassed the first two authorization gates could observe holder transports action-locally without sealing the matching holder-stage transport evidence into the campaign owner. That risks an owner/action-local six-unit mismatch and, more importantly, would make the proof incomplete.

Required design direction:

Holder-stage accounting ownership must depend on lifecycle/accounting truth, not on whether the run came from a final operator authorization. The C8 proof path must seal the same holder-stage evidence whenever accountable holder work occurs.

Do not loosen owner/action-local equality or synthesize missing transport identities.

### 4. `FULL_PUBLIC_COMPOSITION_FIXTURE_TRANSPORT_INJECTION_INCOMPLETE`

The public `run_operational_campaign()` DI surface exposes only:

- `owner`;
- Pump transport;
- secondary transport;
- migration transport;
- external authorization.

The shared ordinary composition registry contains many additional source dependencies used by discovery/front-door, exact-pair lifecycle snapshots, preclose context, holder context, and quote/safety evidence.

The zero-I/O concrete-composition preflight can accept explicit fixture builders, but the real runtime public coordinator has no equivalent full-registry fixture-constructor input. Deeper holder/preclose context receives `context_adapter_factories` from lifecycle kwargs, yet the public coordinator does not expose a supported C8 input for them.

Why this blocks C8:

A proof using only the current public DI cannot guarantee that every reachable source transport is deterministic and offline. Broad monkeypatching of unrelated module globals would make source coverage difficult to prove and could accidentally leave a provider-backed constructor reachable.

Required design direction:

Expose one bounded, explicit C8 fixture-composition capability based on the existing `COMPOSITION_MATRIX` identity set. It must:

- require exact label coverage with no missing/extra builders;
- require explicit fixture adapters/transports;
- preserve Source Governor accounting and Central Scheduler ownership;
- never replace `AuthoritativeLiveOperationalCampaignOwner` with a fake owner;
- never change production default constructors;
- fail before mutation on incomplete fixture composition;
- make provider execution impossible by construction during C8 proof.

## Public wrapper boundary

`window_15m_one_shot_wrapper.apply_authorization_once()` is intentionally an authorization-consumption owner. It validates a final authorization, creates the one-shot marker, then launches the operational command child.

C8 must not use this wrapper for its controlling proof because DTW-34 explicitly prohibits authorization. The wrapper remains an important later production boundary and must not be weakened.

The C8 proof subject is the ordinary public campaign composition beneath the authorization-consumption wrapper.

## Required design before implementation/proof

A C8 design must specify one narrow proof-only composition contract that resolves all four blockers without adding a parallel production runner.

At minimum it must define:

1. the exact public callable used by C8;
2. the explicit proof-only capability/type and how production use is structurally rejected;
3. disposable migrated DB identity and migration-ledger binding;
4. exact full `COMPOSITION_MATRIX` fixture-builder coverage;
5. zero-provider enforcement before first mutation;
6. holder-stage owner/action-local accounting parity independent of operator authorization;
7. ordinary natural `WINDOW_15M` lifecycle semantics — no compressed proof plan bypass;
8. exact success acceptance: two terminal 15m windows, at least the required clean-memory outcome, campaign PASS, cleanup/lease release, zero active/locked work, canonical row+artifact parity, deterministic report-only replay;
9. fail-closed cases to exercise in the bounded proof;
10. explicit forbidden-capability zero deltas;
11. no retry/rerun/resume/restart/successor;
12. independent post-proof inspection before closeout.

## Minimum proof requirements after design/implementation

The later C8 bounded proof should require, at minimum:

- a fresh disposable DB built through the canonical migration owner;
- a second independent disposable/replay or inspection copy where useful;
- exact fixture-composition manifest equal to the ordinary production composition registry;
- zero provider/network execution;
- real Source Governor request/evidence ownership for fixture transport operations;
- real Central Scheduler ownership for lifecycle work;
- exactly one ordinary public composition invocation;
- two-token ordinary `WINDOW_15M` lifecycle completion;
- clean-memory outcome truth from the real closeout path;
- campaign acceptance `CAMPAIGN_PASS`;
- terminal cause/report/child evidence parity where applicable;
- supervision terminal, cleanup complete, lease released;
- zero active/locked Scheduler/campaign/factory residue;
- exact canonical report row/artifact parity;
- public report-only deterministic replay with zero source calls, zero Scheduler runtime calls, and zero DB writes;
- zero deltas for retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL;
- `WINDOW_1H` and longer windows remain locked;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- no automatic retry, manual rerun, resume, restart, or successor;
- independent inspection after the controlling proof.

Use risk-based verification. Do not run the full repository suite merely because C8 adds a proof capability; tests should cover the new proof boundary and the production locks it could affect.

## Money-usefulness contribution

Checkpoint 8 is the integration proof that the individually hardened segments can actually produce one trustworthy ordinary clean-memory result through the real composition while leaving no residue and no hidden provider, authorization, or financial shortcut.

That matters because later memory growth is useful only if the whole public path preserves the same evidence, cleanup, and lock guarantees proven in isolation.

## What this checkpoint improves

Once completed, C8 will improve confidence in:

- end-to-end ordinary `WINDOW_15M` composition;
- deterministic offline proofability of the real source graph;
- disposable DB safety;
- terminal/cleanup/replay integration;
- clean-memory closeout integration;
- proof that segment-level fixes compose without bypasses.

## What this checkpoint still does not unlock

Checkpoint 8 does not unlock:

- provider-backed production execution by itself;
- a new operator authorization;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- live wallet, private keys, signing, execution, or real funds;
- paid API dependencies;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- a new `WINDOW_1H` proof rerun;
- `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H` activation.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A proof-only capability that can target the production DB would be an unsafe bypass. Structural target-kind/path rejection is mandatory.
2. A fixture map with partial coverage could silently fall through to live defaults. Exact registry coverage and no fallback are mandatory.
3. Fabricated authorization/marker facts would make the proof circular and could weaken the one-shot boundary. C8 must use explicit proof identity rather than pretend authorization.
4. Disabling DB-binding validation for convenience would remove one of the main protections the integration proof is supposed to test. C8 needs a proof-specific binding, not no binding.
5. Removing holder-stage evidence requirements would make six-unit accounting self-inconsistent. The correct repair is authorization-independent evidence ownership.
6. Replacing the authoritative campaign owner with a fake owner would not prove public composition.
7. Compressing or predeclaring natural dispositions would violate the operational owner boundary. The proof must preserve ordinary natural `WINDOW_15M` semantics.
8. Broad monkeypatching across provider modules would make zero-provider coverage hard to prove and should not be the final C8 design.

## Audit conclusion / stop condition

Checkpoint 8 is **not ready for the bounded public-composition proof yet**.

The four blockers above require design before any implementation or proof run.

Next permitted step: Checkpoint 8 design/specification only.

Do not create/consume authorization, call providers, run the public campaign, mutate an authoritative DB, or begin any retrieval/paper/financial/longer-window capability before the C8 design is reviewed and approved.