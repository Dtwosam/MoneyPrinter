# Printer V1 V2-9.8B WINDOW_15M Checkpoint 6 — Collection and Clean-Memory Closeout Audit

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_6_COLLECTION_CLEAN_MEMORY_AUDIT_CONFIRMED_FOUR_BLOCKERS`

Checkpoint 6 audit/readiness is complete. Design, implementation, bounded proof, and closeout remain pending.

- Baseline: `e5409431cb13cb169af5ae8ab1b32611c8af951b`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-6-collection-clean-memory-closeout`
- Linear: `DTW-32`
- Phase: audit/readiness only

No provider, RPC, WebSocket, authorization, public Printer runtime, authoritative database mutation, memory generation, retrieval, decision, BUY/SELL/HOLD, position, trade, paper-trade audit, PnL, or longer-window activation was performed.

## Audit boundary

Static/read-only inspection followed the ordinary `WINDOW_15M` path through:

1. Scheduler-owned snapshots and close;
2. exact token/pair and current-run ledger identity;
3. 900-second evidence duration;
4. governed close-time context persistence;
5. 15m outcome derivation and window quality classification;
6. E2Q audit;
7. Lane Q integrity and cadence checks;
8. Lane U2 coverage persistence;
9. explicit exact-window E2Z promotion scope;
10. atomic clean episode + fingerprint creation;
11. support-only `WINDOW_5M_MICRO_EVENT` capture/linkage;
12. anti-look-ahead boundaries.

## Confirmed ready contracts

The following current contracts remain sound and do not require redesign in Checkpoint 6:

- the close snapshot is exact-linked to the current run, token, and pair before context resolution;
- a main `WINDOW_15M` close requires persisted opening/closing snapshots and at least 900 seconds of evidence;
- the 15m outcome is derived from current-window evidence and persisted to `printer_memory_windows.outcome_label` before E2Q/E2Z promotion;
- E2Q audits the exact candidate window and does not itself create clean episodes or fingerprints;
- Lane Q requires `WINDOW_15M`, `CLEAN_DATA`, `do_not_train=0`, partial-memory promotion status, exact boundaries, snapshot anchors, at least 900 seconds, and acceptable cadence/gaps;
- Lane U2 persists coverage and downgrades blocked coverage so it cannot become clean;
- the operational close calls E2Z with an explicit `candidate_window_ids=[window_id]` scope rather than a global clean-candidate scan;
- clean episode and fingerprint creation is transactional and identity-linked;
- duplicate/incomplete clean-object states fail closed;
- `WINDOW_5M_MICRO_EVENT` cannot itself become `CLEAN_MEMORY`, retrieval, a paper decision, BUY/SELL/HOLD, a position, or PnL.

## Confirmed blocker 1 — `CLEAN_EPISODE_OUTCOME_NOT_PERSISTED`

### Evidence

`_attach_context_and_gate_window()` derives and persists the canonical 15m `outcome_label` on `printer_memory_windows` before promotion.

`promote_clean_object()` then inserts the canonical `CLEAN_MEMORY` episode without writing `episode_outcome_label`. The insert supplies identity, quality, window kind, supporting context, and timestamps only. The resulting episode therefore receives the database default `NULL` outcome.

The same owner later builds the fingerprint with a fallback expression:

`episode["episode_outcome_label"] or window["outcome_label"]`

so the fingerprint may know the window outcome while the canonical clean episode itself does not.

Historical retained Printer evidence also contains complete clean episodes whose `episode_outcome_label` is `null`.

### Contract conflict

The Clean Master Spec defines an episode as a completed token behavior window tied to an outcome and requires a clean episode to have a clear outcome label and memory-quality label.

A canonical `CLEAN_MEMORY` episode with no outcome is therefore structurally incomplete even when its source window had a truthful categorical outcome.

### Money-usefulness impact

Printer cannot later explain what happened in a supposedly clean episode from the episode object itself. That weakens future memory comparison and makes episode/fingerprint outcome truth asymmetric.

## Confirmed blocker 2 — `CLEAN_FINGERPRINT_CONTEXT_COLLAPSED_TO_MINIMAL_EPISODE_CONTEXT`

### Evidence

During promotion, `episode_context` is intentionally small and contains only:

- source window id;
- snapshot id;
- E2Q audit status;
- tracking lane;
- creator label.

`_fingerprint_payload()` loads both the source window context and this episode context, but because `episode_context` is non-empty it uses:

- `episode_context or window_context` as the fingerprint `supporting_context`;
- `(episode_context or window_context).get(...)` for token-age, pair-age, and discovery labels.

The canonical fingerprint builder expects condition sections such as market regime, chain heat, safety, liquidity/exit, trading flow, chart/volatility, and micro-events. Those sections exist on the full source-window context, not on the minimal episode context. They therefore collapse to categorical `UNKNOWN` even when the clean source window had usable context.

Exact fingerprint IDs and the window-outcome fallback remain correct; the defect is condition-quality loss, not identity loss.

### Contract conflict

The Clean Master Spec requires condition fingerprints to describe market regime, chain heat, discovery, safety, liquidity/exit, flow, chart/volatility, token/pair age, micro-event state, and memory window without using a score.

### Money-usefulness impact

A technically clean fingerprint can become too empty to support useful later clean-memory comparison. That damages similarity quality while appearing structurally valid.

## Confirmed blocker 3 — `SUPPORT_5M_TRIGGER_LOOKAHEAD_FROM_15M_OUTCOME`

### Evidence

The current operational natural-disposition owner reads the already closed 15m window's `memory_quality_label` and final `outcome_label`. Outcomes such as `SHORT_TERM_PUMP`, `DUMP`, `SLOW_BLEED`, and `DEAD` are mapped to support trigger families.

After the full 15m window is closed/classified, `_natural_disposition_schedule()` calls that disposition owner. Only when the completed 15m outcome says to continue does it call `_capture_same_stream_5m_support()`, which retrospectively chooses snapshots from the first `<=300` seconds of the completed 15m stream.

The support data are early snapshots, but the decision that a 5m support object should exist is made using evidence from the later 15m outcome.

### Contract conflict

The adopted V2-9.7C support contract explicitly says:

- a 5m trigger inferred only from a later main-window outcome is a negative no-capture case;
- support evidence cutoff is the trigger time;
- 5m does not select lifecycle disposition or independently trigger continuation.

The current path reverses this relationship: final 15m disposition decides whether an early 5m prefix is backfilled and which trigger family it receives.

### Money-usefulness impact

This creates look-ahead contamination. Early support evidence can be labelled because of what happened later, which would teach Printer a hindsight-defined micro-event rather than an event-time condition.

## Confirmed blocker 4 — `SUPPORT_5M_DURABLE_OWNERSHIP_LINKAGE_INCOMPLETE`

### Evidence

`capture_5m_support_evidence()` durably stores useful partial linkage:

- exact token id;
- exact pair id;
- parent `WINDOW_15M` id;
- factory run id;
- tracking lane;
- opening/closing snapshot ids and timestamps.

However, the stored 5m context does not durably bind all of the adopted support-object ownership/provenance requirements. It does not store the campaign/cycle/root-lifecycle identity, approved trigger family and trigger-time evidence, source provenance, or Scheduler work identity.

The factory also inserts the synthetic `SUPPORT_5M` run-step row without a `scheduler_job_id`. The trigger family is attached to the returned Python mapping only after `capture_5m_support_evidence()` has already written the support window and support step, so it is not part of those durable support records.

### Contract conflict

The adopted support contract requires each support object to exact-link campaign, run, cycle, token/mint, pair, root 15m lifecycle, containing main window, triggering snapshots, source provenance, and Scheduler work, with an event-time cutoff.

AGENTS also requires 5m support to remain exact-linked to token, pair, run, and main 15m lifecycle and remain Scheduler-led.

### Money-usefulness impact

After process memory disappears, Printer cannot prove the complete ownership and trigger provenance of a support-only micro-event from the support object itself. That weakens replay/audit trust and makes anti-look-ahead verification harder.

## Required design before implementation

Checkpoint 6 must not patch these independently without a single narrow design covering the four seams.

The design must preserve existing owners and specify:

1. how a new clean episode receives the already-proven source-window outcome without recomputing or inventing an outcome;
2. how the canonical fingerprint consumes the full clean source-window condition context while retaining exact episode/window/token/pair identity and categorical `UNKNOWN` for genuinely unavailable fields;
3. how 5m trigger eligibility is proven from evidence available by the 5m trigger cutoff, using only already-adopted categorical trigger semantics and no new threshold/score/rank/confidence system;
4. how the support object durably binds required campaign/run/cycle/root-lifecycle/trigger/source/Scheduler identities without creating a second Scheduler owner or independent source loop;
5. how existing historical clean episodes/fingerprints with missing fields are treated without silent authoritative-DB backfill or history rewriting.

## Required RED proof before repair

Minimum sufficient fail-first regressions:

### RED A — clean episode outcome continuity

Create one disposable promotion-eligible 15m window with a non-null categorical outcome. Promotion must currently demonstrate that the resulting clean episode does not carry that exact outcome.

After repair, the episode outcome must equal the exact source-window outcome and idempotent replay must preserve it.

### RED B — fingerprint condition continuity

Create one disposable promotion-eligible window with representative market/chain/safety/liquidity/flow/chart/age/discovery/micro-event context.

Current promotion must demonstrate which fields collapse to `UNKNOWN` despite source-window evidence. After repair, supported categorical fields must survive exactly; genuinely missing fields must remain `UNKNOWN`.

No score, confidence, weighting, embedding, or vector is allowed.

### RED C — 5m anti-look-ahead

A first-five-minute stream with no approved event-time trigger but a later 15m `SHORT_TERM_PUMP`/other continuation outcome must not be allowed to create a trigger-authoritative 5m support object merely because of the later outcome.

A positive support case must be driven by an approved categorical trigger supported by evidence at or before its cutoff, not by the final 15m label.

### RED D — 5m durable ownership

A created support object must prove its complete adopted ownership/provenance graph after reopening the disposable database. Missing or mismatched campaign/run/cycle/root-lifecycle/trigger/snapshot/source/Scheduler identity must fail closed.

## Minimum bounded GREEN proof

After an approved implementation:

- the four RED regressions must pass;
- existing clean-object atomicity/idempotency tests must pass;
- directly affected fingerprint tests must pass;
- directly affected 5m support-only/linkage tests must pass;
- directly affected 15m close/E2Q/Lane Q/U2 tests must remain green;
- Python compilation and `git diff --check` must pass;
- no retrieval, decision, paper-position, trade, audit, PnL, wallet, key, paid API, scoring/ranking/confidence/weighted, embedding/vector, or longer-window capability may be introduced.

A broad repository suite is not required unless the implementation becomes cross-cutting beyond these owners.

## Money-usefulness contribution

Checkpoint 6 is the point where valid 15m evidence becomes durable learning material. Fixing these blockers makes future clean memories useful rather than merely structurally clean: the episode says what happened, the fingerprint preserves the conditions under which it happened, and 5m support reflects only what was knowable at the time.

## What this checkpoint improves

If the four blockers are repaired and proven, Checkpoint 6 will improve:

- exact outcome continuity from 15m window to clean episode;
- useful categorical condition continuity into the fingerprint;
- event-time truth for support-only 5m evidence;
- durable support ownership/provenance and replayability;
- confidence that only complete, correctly scoped 15m evidence becomes clean memory.

## What this checkpoint still does not unlock

Checkpoint 6 does not unlock:

- provider or public Printer runtime by itself;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- live wallets, keys, signing, execution, or real funds;
- paid APIs;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- Checkpoint 7.

## Functionality Risks / Setbacks / Efficiency Blockers

- Existing historical clean episodes with null outcome labels and historical sparse fingerprints are immutable evidence unless a later explicitly approved repair/migration policy says otherwise. Do not silently backfill the authoritative database in this checkpoint.
- Tightening idempotent clean-object validation may expose historical incomplete objects. The design must distinguish new-object correctness from historical evidence handling rather than weakening the invariant.
- Event-time 5m triggering may require moving evaluation earlier in the 15m lifecycle. It must stay inside Central Scheduler ownership, Source Governor budgets, and the existing finite cadence; no polling loop or automatic retry may be added.
- The support-only object must not become a second main memory or a continuation authority while gaining stronger provenance.
- Fingerprint quality repair must preserve categorical semantics and explicit `UNKNOWN`; it must not infer unavailable context or create a hidden scoring system.
- No change is justified to the already-sound 900-second, cadence, E2Q, Lane Q, U2, explicit-window-scope, or atomic transaction contracts unless a later RED proves a causal defect.

## Audit completion boundary

Checkpoint 6 audit closes with exactly four confirmed reachable deterministic blockers.

The next allowed step is Checkpoint 6 design/specification for these four blockers only. No implementation or proof run is authorized by this audit document, and Checkpoint 7 must not begin.
