# Printer V1 V2-9.8B Selective-1h Continuation Repair Design

Status: `DESIGN_COMPLETE_NARROW_IMPLEMENTATION_AUTHORIZED`

Starting baseline: branch `master`, commit `cfbae1f8075b6bc0674f9cf728a15a5f7b6103ad`, clean worktree.

## Scope and source-grounded classification

This design repairs four committed-code defects proven by the selective-1h continuation eligibility audit:

1. The continuation adapter searched safety composites only by `memory_window_id`, although the real producer creates the accepted composite before the memory window and therefore persists `memory_window_id=NULL`. The authoritative memory-window context already retains the exact accepted `safety_composite_id`.
2. Campaign-wide evaluation ran from the final token's still-`RUNNING` close path. The campaign barrier treated that close as terminal while the authoritative B.1 promotion adapter correctly required `SUCCEEDED`.
3. Successfully completed predecessor campaign windows stayed `AUDITING` and generic terminal closure later changed them to `CANCELLED`.
4. Canonical terminal reporting did not project selective-1h token plans, counts, categorical outcome, or actual persisted 1h work.

Under the Python Builder Guide these are `COMMITTED_CODE_DEFECT` findings. This lane does not change policy, admission strictness, proof ceilings, provider behavior, or capability locks.

## Authoritative ownership and call path

The canonical campaign-wide barrier remains owned by the one-command bounded factory orchestration in `one_command_15m_factory.py`. It may be entered only after a successful starting-token `WINDOW_CLOSE` step has been persisted as `SUCCEEDED` and its scheduler job completed. It performs one non-polling readiness check across every activated starting-token close. If any applicable close is not authoritative, it returns without evaluating.

When all applicable closes are authoritative, the barrier:

1. resolves each B.1 promotion outcome;
2. persists/reconciles each predecessor `WINDOW_15M` campaign window;
3. invokes the single campaign-wide selective evaluator;
4. persists or returns the immutable `CONTINUATION_4A` objects;
5. schedules only newly created `CONTINUE` decisions through Central Scheduler; and
6. writes the same campaign-wide result into the participating close results.

No current close is admitted while `RUNNING`. Close arrival order is irrelevant. The barrier supports zero, one, or two starting-token results and adds no polling, retry, restart, resume, or successor mechanism.

## A. Exact safety-evidence resolver

`campaign_authority_adapters.py` will own one canonical memory-window safety resolver. Its lookup key is the exact `safety_composite_id` at:

`memory_windows.supporting_context_json.memory_build_evidence_overlays.safety_composite_id`

The resolver loads that exact composite and verifies all of the following:

- graph-bound token row and mint;
- graph-bound pair row and pair address;
- exact closing snapshot (`snapshot_end_id`);
- memory-window lineage: a non-null composite `memory_window_id` must equal the authoritative window; a null producer field is allowed only because the exact accepted composite ID is retained by that window's immutable build context;
- target identity and target-kind compatibility;
- freshness at the authoritative checkpoint cutoff;
- complete, traceable request/response/snapshot contribution provenance;
- absence of blocker or conflict state; and
- the unchanged timeframe-aware safety acceptance predicate.

The resolver fails closed for a missing ID, missing row, wrong token, wrong pair, wrong closing snapshot, wrong non-null window lineage, stale evidence, partial/unacceptable evidence, blocker, conflict, malformed provenance, or untraceable contribution. It never searches for the latest composite, matches only by mint or pair, falls back to prior evidence, or rewrites unknown raw fields as safe.

Raw labels and optional unknowns remain in the returned evidence. Legacy `SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY` can support 1h only when the existing timeframe-aware projection yields `SAFETY_CONTEXT_ACCEPTABLE`; the underlying label is not changed.

## B. Authoritative campaign-wide evaluation barrier

An applicable close is authoritative only when its exact activated `WINDOW_CLOSE` step is `SUCCEEDED`, has its exact memory-window linkage, and B.1 can resolve its promotion outcome. The prior exception that counted the current `RUNNING` close is removed.

Evaluation is moved out of the close body and behind step success/job completion. The first close can reach the barrier and defer. The last authoritative close reaches the same barrier and evaluates the entire starting-token set. An episode existing while its close step is still running is insufficient.

If all close steps are terminal but an authoritative promotion outcome cannot be resolved, the barrier fails closed as a system evaluation defect. It does not manufacture token eligibility.

## C. Immutable continuation-object idempotency

The first complete evaluation owns the two token-local `CONTINUATION_4A` objects. A repeated internal invocation must load those objects before performing side effects:

- two existing objects whose authoritative decision payloads equal recomputation are returned unchanged;
- a partial persisted object set fails closed;
- any recomputation that conflicts with an existing BLOCK or CONTINUE fails closed;
- an existing object is never replaced;
- persisted BLOCK never becomes CONTINUE and CONTINUE never becomes BLOCK;
- existing evaluation causes no new campaign window or scheduler work;
- deterministic campaign-window IDs, step identities, and scheduler deduplication remain secondary defenses.

This design deliberately does not add a second evaluation after an earlier premature immutable decision; it prevents premature ownership instead.

## D. Campaign-window terminal-state reconciliation

The authoritative B.1 outcome maps the predecessor `WINDOW_15M` campaign window as follows:

| Promotion outcome | Campaign-window terminal state |
|---|---|
| `CLEAN_PROMOTED` | `CLEAN_PROMOTED` |
| `ALREADY_EXISTS_IDEMPOTENT` | `CLEAN_PROMOTED` |
| dirty/unsafe/do-not-train completed memory | `DIRTY` |
| policy/evidence/lineage blocked completed close | `BLOCKED` |
| authoritative close with no promotion | `NO_PROMOTION` |
| genuinely cancelled/incomplete lifecycle | `CANCELLED` |

Reconciliation is idempotent. A completed predecessor is never cancelled merely because its 1h decision is BLOCK. The continuation verdict remains in `CONTINUATION_4A` and reporting.

## E. Canonical terminal reporting

The canonical campaign report receives a bounded `selective_1h` projection built from authoritative campaign windows and continuation objects. The same persisted report is used by zero-source replay. It includes:

- token plans, per-token verdicts, and categorical reasons;
- continue, block, and stop counts;
- campaign-window counts by kind and state;
- actual persisted `WINDOW_1H` count;
- explicit zero-continuation truth;
- downstream unlocks (none);
- restart and successor status (false); and
- one secondary outcome field with exactly these categories:
  - `ZERO_ELIGIBLE_CONTINUATIONS`
  - `ONE_CONTINUATION`
  - `TWO_CONTINUATIONS`
  - `EVALUATION_BLOCKED_SYSTEM_DEFECT`
  - `EVALUATION_NOT_REACHED`

The normal campaign terminal cause is preserved. A normal campaign with zero eligible continuations remains normally completed but is not represented as a successful 1h proof.

## F. Scheduler and lifecycle behavior

Only newly authoritative CONTINUE plans schedule work, through the existing Central Scheduler continuation owner, retaining exact campaign, run, predecessor window, token, and pair linkage. Zero, one, or two eligible tokens yield exactly zero, one, or two `WINDOW_1H` campaign windows and scheduler lifecycles. No repeated invocation creates duplicate work.

This repair creates no 4h, 12h, or 24h work and no retrieval, decision, position, trade, audit, PnL, wallet, signing, or funds capability. Normal production remains 15m-only; selective 1h remains separately proof-authorized.

## Persistence and migration decision

No migration is required. Exact safety linkage already exists in memory-window context; immutable objects, campaign windows, scheduler identities, close result JSON, and canonical report JSON can express the repaired truth. The authoritative database and retained historical artifacts will not be mutated or rewritten.

## Implementation boundary

Permitted owners are limited to:

- `src/printer_v1/operator_cli/campaign_authority_adapters.py`
- `src/printer_v1/operator_cli/operational_selective_1h.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- directly focused tests

Other owners may be changed only if compilation or an existing canonical call contract proves it necessary. Discovery, sources, liquidity, memory generation/promotion policy, retrieval, and paper systems remain untouched.

## Offline proof matrix

Temporary databases, fixtures, and mocks must cover:

1. real-producer accepted composite with `memory_window_id=NULL` and exact context ID;
2. wrong composite ID, token, pair, closing snapshot, and non-null window lineage;
3. stale, partial, blocked/conflicted, and untraceable evidence;
4. unchanged effective safety acceptance and preservation of raw unknowns;
5. token close orders 1-then-2 and 2-then-1, including a later close;
6. episode existence while the current close is still `RUNNING` does not pass the barrier;
7. evaluation only after all required closes are authoritative;
8. zero, one, and two continuation outcomes;
9. repeated invocation returns existing decisions and creates no duplicate 1h window or scheduler work;
10. conflicting recomputation fails closed;
11. clean-promoted, dirty, blocked/no-promotion, and genuine-cancellation campaign-window states;
12. truthful canonical report, zero-source replay, and explicit zero-continuation outcome;
13. absence of retry, restart, successor, 4h/12h/24h, retrieval, and paper/financial deltas; and
14. equality of authoritative database hashes before and after.

Only focused tests and nearest affected regressions will run. No network-bearing, discovery, Scheduler runtime, campaign runtime, lifecycle runtime, memory-generation, or live proof command is authorized.

## Rollback

Rollback is the single repair commit. No schema or authoritative-data rollback is required. Historical failed-proof artifacts remain unchanged.

## Money-usefulness contribution

The repair protects the integrity of the clean-memory growth funnel: exact accepted safety evidence can qualify without relaxed rules, all predecessor memories are evaluated only after authoritative completion, immutable decisions remain stable, and operator reports distinguish clean campaign completion from actual 1h continuation. It produces no financial decision or profit claim.

## Functionality Risks / Setbacks / Efficiency Blockers

- Exact linkage deliberately fails closed for older windows that do not retain a traceable composite ID.
- Immutable first-evaluation ownership means a system defect requires an explicitly approved repair/recovery lane; silent re-evaluation is prohibited.
- Two-token barrier ownership depends on accurate activated-close enumeration; focused order and partial-arrival tests are mandatory.
- Report projection must tolerate campaigns where selective evaluation was never authorized or never reached.
- A later live proof remains necessary to validate real operational composition, but this lane does not authorize it.

## Completion and next lane

Implementation may begin only against this completed design. A PASS closeout authorizes only a fresh read-only selective-1h operator-readiness review. It does not authorize another live proof.
