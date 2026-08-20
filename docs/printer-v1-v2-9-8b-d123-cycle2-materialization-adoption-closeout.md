# Printer V1 V2-9.8B D123 Cycle-2 Materialization Adoption Closeout

Date: 2026-08-20

Lane: `V2-9.8B D123 Cycle-2 Materialization Corrective Adoption Closeout`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_D123_CYCLE2_MATERIALIZATION_ADOPTION_CLOSEOUT_PASS`

This PASS closes repository adoption of the D123 corrective only. It does not prove a successful four-token runtime, create or reuse an authorization, contact providers, run Printer, or unlock any protected capability.

## Adopted authority

- Product branch: `agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation`
- Merged PR: `#197` — `Repair Cycle 2 materialization and local fault isolation`
- Adopted merge commit: `8709a971cb463a258525831e82c3672865d21b47`
- Reviewed/rebased PR head: `1bb2acfa948563746a02f8b04b756fae09661fdf`
- Original independently reviewed D123 commit before history-only rebase: `86748f0ca801a50b36f01666e1ded08518368630`
- PR base at merge: `596c2514dffcb9c4d1edc9ed9bf678047e46c52e`

The history-only rebase changed the parent relationship only. The D123 product/test tree remained byte-identical to the independently reviewed repair content.

## Controlling incident

The consumed campaign that exposed D123 was execution `20260819T215053Z-e4fde0d4e4ea`, campaign `20260819T215053Z-e4fde0d4e4ea-campaign`, run `20260819T215053Z-e4fde0d4e4ea-campaign-run`, factory run `b24f02f5-5f74-44f8-8390-7aecdf75990e`.

The latest consumed authorization for that attempt is `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260819T213040Z`. It is permanently consumed and non-reusable.

Observed terminal control outcome was `SAFE_STOP_PREFLIGHT_FAILED`; the Cycle-2 orchestration error was `PreAdmissionMaterializationError: MATERIALIZATION_PERSISTENCE_FAILED`. The pre-admission attempt had already lawfully frozen and consumed two fresh Cycle-2 `MARKET_PRESENT_POOL` candidates before materialization failed.

No rerun, resume, restart, retry, or successor of that authorization is permitted.

## Adopted repairs

### D1 — canonical fresh-market channel freeze

Later-cycle `MARKET_PRESENT_POOL` candidates freeze the canonical channel `FRESH_AGGREGATOR_PROTOCOL_CONFIRMED` instead of reintroducing raw provider labels. DexScreener/GeckoTerminal identity remains source provenance rather than merged-candidate channel authority.

### D2 — bounded typed persistence diagnostics

`PreAdmissionMaterializationError` preserves a stable code plus bounded categorical `persistence_reason`. Unsupported merged-candidate channels map to `UNSUPPORTED_MERGED_CANDIDATE_CHANNEL`; unclassified SQLite failures remain typed outside the cycle-local allowlist.

### D3 — narrow Cycle-2-local isolation

Only the positively classified `UNSUPPORTED_MERGED_CANDIDATE_CHANNEL` case may be isolated locally, and only while Cycle 2 is still fully unstarted: cycle `PLANNED`, exactly two `SELECTED` slots, no tracking queue IDs, zero cycle windows, and zero cycle Scheduler work.

That local case terminalizes Cycle 2 without opening lifecycle work, allows already-valid Cycle-1 work to drain, and surfaces the Cycle-2 terminal cause only after the surviving work drains. Unknown SQLite, ownership, Scheduler, Source Governor, supervision, lease, or other shared faults continue to fail closed globally.

## Proof and adoption evidence

- Original bounded D123 proof: `V2_9_8B_D123_CYCLE2_MATERIALIZATION_CORRECTIVE_BOUNDED_PROOF_PASS`
- Independent review: `V2_9_8B_D123_INDEPENDENT_REVIEW_ADOPT_PASS`
- Repository adoption preparation: `V2_9_8B_D123_REPOSITORY_ADOPTION_PREP_PASS`
- Focused D123 suite: `9 passed`
- Direct affected regressions: `39 passed`
- `py_compile`: PASS
- `git diff --check`: PASS
- Authoritative DB stayed byte-identical during repair/proof/adoption preparation at SHA-256 `79a653f7f8c270bca0c08f271882784660caad954e278bd05b6d7bb9a4be5f8f`
- PR #197 merge-readiness: PASS
- PR #197 final shape: one commit, four files, no unresolved review threads, mergeable before merge
- PR #197 merged successfully at exact reviewed head into merge commit `8709a971cb463a258525831e82c3672865d21b47`

No broad regression suite is required by this closeout because the adopted content is the exact bounded/independently reviewed repair and the integration rebase was content-neutral.

## Locks preserved

Printer V1 remains Solana-only, Solana-memecoin-only, paper-only. No live wallet, private keys, signing, real funds, or live execution. No paid API dependency. No scoring, ranking, confidence percentages, or weighted decision logic. No embeddings/vectors. No Source Governor bypass. No Central Scheduler bypass. No dirty memory in retrieval or decisions. Retrieval and financial capabilities remain locked. BUY/SELL/HOLD, paper positions, trade events, paper audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059 is introduced by D123.

The 4/2/2 policy remains: four total tokens, two cycles, two tokens per cycle, fresh/disjoint Cycle 2, freeze minimum depth 4, exact-pool liquidity floor `$3,000`, minimum spacing `300s`, `WINDOW_15M` root, lawful token-local `15m -> 1h -> 4h`, retries `0`, endpoint rotation `false`, and one-shot/no-rerun/no-resume/no-restart/no-successor controls.

## Exact next permitted lane

`V2-9.8B Post-D123 Two-Cycle/Four-Token Authoritative Readiness`

This lane must inspect the exact adopted executable merge commit `8709a971cb463a258525831e82c3672865d21b47` and current operational-host evidence before any authorization-preparation lane.

Minimum sufficient readiness must verify:

1. exact D123 adopted ancestry and four-file scope;
2. canonical fresh-market provenance remains correct across later-cycle discovery, freeze, materialization, and persistence;
3. the narrow Cycle-2-local isolation allowlist and fully-unstarted preconditions remain intact;
4. unclassified/shared failures still fail closed globally;
5. Cycle-1 lifecycle/Scheduler continuation remains protected when a known Cycle-2-local materialization contract failure is isolated;
6. Source Governor, Central Scheduler, freeze depth 4, `$3,000` exact-pool liquidity, disjointness, one-shot controls, and all V1 locks remain unchanged;
7. the live authoritative SQLite identity, Migration 058 state, and host-local historical/current authorization evidence are freshly reconciled read-only;
8. every prior authorization, including `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260819T213040Z`, is non-reusable and no conflicting application marker exists.

Only a fresh readiness PASS may advance to a separate authorization-preparation lane. Do not create an authorization from this closeout.

The active Printer V1 source stack wins any conflict with this document.
