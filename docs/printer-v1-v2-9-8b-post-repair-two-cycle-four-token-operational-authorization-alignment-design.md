# Printer V1 V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Design

Date: 2026-08-18

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_DESIGN_PASS`

Implementation disposition: `IMPLEMENTATION_REQUIRED`

## 1. Design goal

Define the minimum safe operational authority needed to run one bounded V2-9.8B Memory Factory invocation with exactly two governed cycles, exactly two fresh distinct token/pair slots per cycle, and exactly four through-4h token slots total, while preserving the repaired runtime, the existing two-token Standard-4H authority, and the existing proof-only authority.

This design also defines the post-repair Git-provenance repair required to align the four-token authorization chain with canonical Migration 058.

This document does not implement the design, create or consume an authorization, run providers/RPC/WebSockets, mutate the authoritative campaign database, activate 12h/24h, enable retrieval/financial capabilities, or create Migration 059.

Repaired product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Design parent/audit handoff:

`282066b2711b35e9a83117571fe278edf5e91dc5`

## 2. Binding source conclusions

The active source stack requires bounded operator-approved memory growth, Source Governor ownership, Central Scheduler ownership, clean/dirty evidence truth, and no premature financial/retrieval activation. The Memory Factory guide defines 15m as the first main window, 5m as support-only, standard continuation through 1h and eligible 4h for otherwise-valid activated tokens, and later 12h/24h as separately gated.

The existing two-token `standard-four-hour-run` authority is valid product law for exactly one standard two-slot campaign. It must not be widened or redefined.

The existing multi-cycle policy is already the canonical capacity owner for exact two-token cycles and supports a configured four-token envelope as exactly two active cycles. The persisted coordinator explicitly reuses the existing campaign/factory/Scheduler/Source-Governor ownership model and already rejects duplicate historical campaign slot identities.

The existing `four-token-bounded-capacity-proof-run` remains proof-only. Its proof wrapper, application namespace, authorization profile and terminal evidence must remain distinguishable from ordinary operational corpus growth.

## 3. Architectural decision

### 3.1 New explicit operational mode

Add one new wrapper-bound public child mode:

`four-token-standard-four-hour-run`

Add a matching zero-source/read-only preflight mode only if the existing command architecture requires a mode-specific preflight label:

`four-token-standard-four-hour-preflight`

The new run mode is operational Memory Factory authority, not a proof label and not a capacity selector. It has one exact immutable shape: 4 through-4h slots / 2 cycles / 2 slots per cycle.

Direct invocation without the fresh one-use operational wrapper remains unauthorized and must fail closed before campaign/source mutation.

### 3.2 Preserve existing modes

`standard-four-hour-run` remains exactly the current two-token Standard-4H authority.

`four-token-bounded-capacity-proof-run` remains explicitly proof-only.

Neither mode is renamed, aliased to the new operational authority, or given broader authority.

### 3.3 Reuse one canonical runtime composition

The new operational mode must delegate to the already-repaired four-token/multi-cycle composition under the existing public operational command and authoritative campaign owner. It must not create:

- a second Memory Factory runner;
- a second Scheduler;
- a second Source Governor;
- an independent provider/source loop;
- a separate database/schema owner;
- a separate candidate-selection algorithm;
- a separate lifecycle continuation engine.

A small neutral operational facade may be introduced if needed to prevent production code from depending directly on proof-named wrapper semantics. The facade may delegate to existing proven multi-cycle/controller/adapter primitives. Broad renaming/refactoring of proof modules is not required for this lane and should be avoided unless a focused test proves it is necessary.

## 4. Exact operational 4/2/2 policy

The new operational authority must derive its capacity from:

`scaled_standard_four_hour_capacity_contract(4)`

No independent numeric copy is authoritative.

Expected comparison projection from the current baseline:

- configured through-4h token slots: 4;
- configured active cycles: 2;
- total cycle admission ceiling: 2;
- tokens per cycle: 2;
- minimum cycle admission spacing: at least 300 seconds;
- lifecycle requests per token: 117;
- lifecycle request outer ceiling: 472;
- lifecycle Scheduler outer ceiling: 420;
- automatic retries: 0;
- endpoint rotation: false;
- long windows activated: false.

If implementation derives different values from the exact launch checkout, it must stop and reconcile the underlying canonical contracts. It must not force these comparison numbers into code.

The operational policy version should be distinct from both existing authorities:

`V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`

Root main window:

`WINDOW_15M`

Locked windows:

`WINDOW_12H`, `WINDOW_24H`

5m remains support-only.

The existing proven four-token bounded clocks may be reused as the operational 4/2/2 bounded envelope unless implementation inspection proves a contract mismatch:

- pre-lifecycle acquisition envelope: 2,400 seconds;
- post-supply bounded lifecycle envelope: 18,000 seconds.

These clocks do not raise provider rate ceilings and do not create retry authority. Their purpose is only to give the second fresh cycle and its through-4h lifecycle a finite same-invocation wall-time envelope.

## 5. Cycle semantics

This is one invocation and one campaign ownership graph, not two separate campaign launches.

Cycle 1 owns exactly two selected slots.

Cycle 2 is admitted only through the existing multi-cycle admission gates after the configured minimum spacing and only while source/provider/Scheduler/close-reserve/supervision/lease/DB/discovery/protected-work health allows it.

Cycle 2 may overlap Cycle 1 under the existing multi-cycle policy. It is not a successor process and does not create a second authorization.

Every admitted cycle remains pair-atomic: exactly two slots with ordinals 1 and 2.

Across the same campaign/run, all four slot identities must be distinct under the existing persisted identity guards, including mint and pair identities. A Cycle-1 token/pair may appear in discovery diagnostics or rejection evidence, but it cannot consume a Cycle-2 fresh slot.

Cycle 2 must obtain supply from the repaired governed later-cycle acquisition path. Manual token lists, manual pair substitution, stale carry-forward, fabricated Pump origin, or bypass of `MARKET_PRESENT_POOL`/direct Pump-PumpSwap authority is forbidden.

Honest source scarcity or inability to acquire two lawful fresh Cycle-2 candidates is a market/source/evidence terminal outcome, not permission to reuse Cycle-1 slots or weaken admission.

## 6. Window continuation contract

Each cycle preserves the current standard through-4h lifecycle law:

`WINDOW_15M -> WINDOW_1H -> eligible WINDOW_4H`

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot create independent continuation authority.

Continuation remains token-local under the current hard evidence/identity/provenance/safety/source rules. Outcome magnitude, learning label, holder concentration description, score, rank or confidence cannot decide continuation.

The exact predecessor cutoff remains binding: a later snapshot or later safety observation cannot repair a missing first-hour decision boundary after the fact.

The 4h planning barrier remains cycle-local: both owned 1h verdicts for that exact two-slot cycle must be terminal before that cycle's 4h planning proceeds. Cycle 2 does not have to wait for all Cycle-1 4h work to finish if the existing multi-cycle capacity and due-work gates lawfully admit overlap.

12h/24h planning remains absent.

## 7. New one-use operational authorization boundary

Introduce a distinct operational one-use wrapper rather than converting the proof wrapper.

Recommended module/authority name:

`four_token_standard_four_hour_one_shot_wrapper.py`

Recommended application namespace:

`~/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications`

Recommended repository authorization package root:

`operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization`

Recommended package kind:

`FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE`

Recommended manifest schema identity:

`PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1`

Recommended final-authorization schema identity:

`PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`

The one-use document must bind, at minimum:

- fresh authorization ID;
- exact authorized command mode `four-token-standard-four-hour-run`;
- exact branch and HEAD;
- operator approval;
- temporal validity;
- exact one-shot policy;
- exact derived 4/2/2 operational policy;
- authoritative DB path, SHA-256, size, inode and mtime_ns;
- migration count and migration head;
- exact current migration-evidence execution ID;
- prior authorization non-reuse evidence.

One-shot policy is exactly:

- allowed invocation count: 1;
- automatic retry: false;
- manual rerun: false;
- resume: false;
- restart: false;
- successor: false.

The application marker must be created at most once and must launch exactly one child process. A blocked pre-consumption readiness/zero-state check must leave the authorization unconsumed.

No per-cycle authorization exists. The single wrapper authorizes the exact bounded 4/2/2 child only.

## 8. Authorization separation and historical visibility

The new operational authorization profile must be a fourth distinct Git authorization profile alongside ordinary, standard-four-hour and four-token-proof profiles.

Historical authorization enumeration for the new profile must be able to see the relevant prior roots for ordinary, Standard-4H, four-token proof and this new operational four-token authority, but visibility never creates reuse authority.

No ordinary, two-token Standard-4H or proof authorization may be reinterpreted as authority for the new operational mode.

The preceding repository handoff proves no fresh Standard-4H authorization was created in that preparation lane. If additional authorization packages exist only on the actual host, later host-local preparation must enumerate and classify them by exact identity before issuing the new authorization.

## 9. Migration 058 provenance design

### 9.1 Current evidence

For both the repaired four-token proof profile and the new operational four-token profile, current schema-transition evidence must be Migration 058, matching the current zero-state gate and canonical database ledger.

Define a distinct current package kind for Migration 058, for example:

`MIGRATION_058_EVIDENCE`

The canonical package root should follow the existing migration evidence convention, for example:

`operator-runs/v2-9-8b-migration-058-application`

This is a design target, not a claim that committed GitHub evidence proves the host package currently exists at that exact path. Implementation/preparation must reconcile the actual repair evidence before binding it. If the exact existing Migration-058 evidence cannot be established, stop as an evidence/readiness block; do not manufacture files or identities merely to satisfy the profile.

The authorization-bound current migration package continues to be hashed and bound through the existing manifest mechanism under its exact migration execution ID.

### 9.2 Historical evidence

Migration 057 must be demoted from current authority to a distinct preserved historical migration package, exactly as 055 and 056 were previously demoted when successors became current.

The historical four-token chain after repair must preserve distinct evidence identities for:

- Migration 050;
- Migration 055;
- Migration 056;
- Migration 057.

Migration 057 needs its own historical evidence class, exact execution ID, expected complete file count and immutable inventory SHA-256. Those values must come from the actual preserved Migration-057 operator evidence. They are not established by this design and must not be guessed.

If the complete Migration-057 historical inventory cannot be proven, implementation must stop before weakening the historical package completeness law.

### 9.3 Profiles affected

The scoped provenance repair may change:

- `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` so its current migration package is 058 and its historical chain includes 057;
- the new operational four-token authorization profile with the same 058-current / 050+055+056+057-historical migration chain.

Do not alter ordinary or two-token Standard-4H authorization profile semantics in this lane unless a directly affected focused test proves the new four-token profile registration requires a mechanical shared-validator change. No broad migration-profile cleanup is authorized.

## 10. Pre-consumption zero-state/readiness design

The existing four-token zero-state SQL domains, host-process check, DB integrity/FK checks, migration-ledger guard, source configuration check and active-ownership checks remain mandatory.

Do not duplicate their SQL/host-process logic into a second independent implementation.

Implementation should either:

1. generalize the existing four-token zero-state gate into a neutral shared 4/2/2 gate with mode-specific authorization validation; or
2. add a thin operational wrapper around shared read-only projection/process helpers while preserving the proof entry point.

The operational gate must require:

- exact canonical DB identity from the authorization;
- migration count 58;
- migration head `058_direct_pump_migration_cursor.sql`;
- integrity `ok`;
- zero FK violations;
- no active conflicting Printer runtime;
- zero conflicting durable ownership in all existing zero-state domains;
- valid free/public source configuration;
- exact 4/2/2 policy and locked 12h/24h;
- no authorization marker already present.

A failure here blocks before consumption and starts no child.

## 11. Public command wiring

`operational_memory_factory_command.py` remains the only public operational command module.

Implementation may add the new mode to its exact parser/policy/manifest-supported-mode sets and create one exact operational policy object whose numeric ceilings derive from `scaled_standard_four_hour_capacity_contract(4)`.

The new mode must enter the same canonical four-token/multi-cycle campaign composition currently exercised by the bounded proof. Mode distinction is authorization/provenance/operator authority, not a fork of discovery, lifecycle, accounting or terminal closure logic.

The public command must retain a fail-closed wrapper-binding requirement for the new mode. No `--max-tokens`, arbitrary cycle count, or capacity selector is introduced.

## 12. Terminal/accounting behavior

The new operational mode keeps the repaired full-run accounting and first-terminal-cause law.

Every source request/response/failure remains durable evidence and attributable to exact campaign/run/cycle/stage/Scheduler ownership.

Cycle-level accounting remains exact for two slots. Campaign-level closeout must cover both admitted cycles and all four slots without treating proof acceptance as operational memory acceptance.

SOURCE versus INTERNAL failure classification remains truthful.

Promotion reporting and safety reporting remain separate authorities.

Zero-work/read-only replay remains provider-free and DB-write-free.

A terminal campaign cannot spawn a successor or restart itself.

## 13. Minimum implementation scope

Likely product files are limited to the authority/wiring seam:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
- a new `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py`;
- the existing four-token zero-state gate or a narrow shared/refactored gate;
- only the smallest neutral 4/2/2 facade/helper needed to reuse the existing multi-cycle runtime without proof-authority leakage.

Existing proof runtime, coordinator, later-cycle acquisition, campaign owner, Scheduler and Source Governor files should not change unless a concrete integration seam requires a minimal edit.

No migration file is expected. Migration 059 is forbidden.

No provider adapter/source protocol change is expected.

## 14. Minimum sufficient implementation tests

Implementation verification must be focused but cross-cutting because authorization, provenance and public runtime wiring are involved.

Required focused coverage:

- new operational wrapper builds exactly one child command with mode `four-token-standard-four-hour-run`;
- second application of the same authorization is refused;
- blocked zero-state leaves authorization unconsumed;
- exact 4/2/2 policy is derived, not independently copied;
- policy rejects widening to a third cycle, fewer/more slots, retries, endpoint rotation or long windows;
- direct child invocation without wrapper binding fails closed;
- existing `standard-four-hour-run` remains exactly two-token authority;
- existing proof mode remains proof-only and distinct;
- new operational mode enters the same canonical four-token/multi-cycle composition rather than a second runner;
- Cycle-2 selection cannot reuse Cycle-1 mint/pair identities;
- later-cycle fresh supply path remains Source-Governed and Scheduler-led;
- Migration 058 is current evidence for the repaired proof and new operational profiles;
- Migration 057 is required preserved historical evidence with immutable complete inventory identity;
- missing/modified/extra 057 historical evidence fails closed;
- wrong migration count/head fails before consumption;
- 12h/24h remain locked;
- terminal one-shot flags remain zero/false;
- focused existing four-token proof, standard-four-hour, multi-cycle coordinator, later-cycle bridge, Git-provenance and zero-state tests remain green.

Compile changed modules and perform source/diff scans for forbidden capability drift.

Do not run a broad full suite merely for the implementation lane unless the focused results reveal cross-cutting uncertainty. A broader directly affected regression set is appropriate at the subsequent proof/closeout gate because this seam touches authorization and public command routing.

## 15. Bounded proof/test design after implementation

No live campaign is authorized immediately after coding.

The next proof must be offline/disposable and bounded, using migration-058 fixture state, fake/frozen transports and deterministic time. It must prove in one child invocation:

- one campaign/run ownership graph;
- Cycle 1 exact two slots;
- Cycle 2 admitted through the existing gate after lawful spacing/readiness;
- four distinct mint/pair slot identities total;
- Cycle 2 obtains fresh governed supply rather than reusing Cycle 1;
- per-cycle Scheduler/source/accounting ownership remains exact;
- cycle-local 1h-terminal barrier precedes eligible 4h planning;
- no 12h/24h planning;
- one terminal closeout and no successor/retry/rerun/resume/restart;
- operational authorization/profile identity is distinct from proof and two-token standard authority.

Negative proof cases must include duplicate Cycle-2 identity, insufficient fresh supply, stale/wrong migration evidence, incomplete historical Migration-057 package, active conflicting zero-state ownership, and second marker/application attempt.

Provider/RPC/WebSocket live calls remain zero during this proof.

## 16. Closeout and later host authorization sequence

After implementation, the required sequence remains:

`implementation -> bounded proof/test -> closeout -> host-local authorization preparation -> independent authorization review -> operator-approved one-use run`

The host-local authorization preparation must bind the actual launch checkout and actual `data/printer_v1.sqlite3` filesystem identity. GitHub-only evidence cannot substitute for path/SHA-256/size/inode/mtime_ns.

Only after implementation/proof/closeout PASS may a fresh operational 4/2/2 authorization be prepared. Preparation must stop without consuming it. Only after independent review PASS may the operator-approved wrapper consume it once.

## 17. Stop conditions

Stop implementation or later preparation if any required change would:

- create a second Scheduler/Source Governor/source loop/factory runner;
- silently widen `standard-four-hour-run`;
- convert the proof mode into ordinary operational authority;
- permit arbitrary token/cycle capacity selection;
- bypass fresh Cycle-2 discovery/identity exclusion;
- hand-edit capacity values instead of deriving them;
- weaken historical migration inventory completeness;
- fabricate Migration-057 or Migration-058 evidence;
- require Migration 059;
- activate 12h/24h;
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits or PnL;
- add wallet/private-key/signing/real-fund/live-execution logic;
- require a paid API;
- add scoring/ranking/confidence/weighted logic or embeddings/vectors.

A host evidence/package/DB identity problem is a readiness block unless evidence proves a product-code defect. Honest source scarcity or market supply exhaustion is not a code defect.

## 18. Design acceptance

This design is accepted because it:

- preserves the active V1 locks and lane sequence;
- keeps the existing two-token Standard-4H authority unchanged;
- keeps the four-token proof authority distinct;
- reuses the repaired multi-cycle runtime rather than inventing a parallel architecture;
- makes the requested 4/2/2 operational authority explicit and one-use;
- requires fresh Cycle-2 discovery and four distinct slots;
- aligns four-token provenance to Migration 058 while preserving 057 history;
- refuses to invent missing host evidence;
- defines focused implementation and bounded proof gates before any live run.

## 19. Exact next permitted lane

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Implementation`

Implementation only. No live provider campaign, no authorization consumption, no Migration 059 and no future capability unlocks.

If exact preserved Migration-057 evidence needed for historical inventory binding is not available to the implementation environment, classify that point as `BLOCKED_READINESS` and stop before weakening provenance law.
