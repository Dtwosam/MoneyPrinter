# Printer V1 V2-9.8B Post-Repair Pre-Holder Transport-Identity Reconciliation Audit Closeout

Verdict: `V2_9_8B_POST_REPAIR_PRE_HOLDER_TRANSPORT_IDENTITY_RECONCILIATION_AUDIT_PASS_ROOT_CAUSE_CONFIRMED`

## Controlling attempt

- Authorization: `V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z` — consumed and non-reusable.
- Authorized HEAD: `1667d3a1391ef4e93766fcdc0d5824d3da2f2127`.
- Execution: `20260808T140729Z-5fa4771d212a`.
- Campaign: `20260808T140729Z-5fa4771d212a-campaign`.
- Run: `20260808T140729Z-5fa4771d212a-campaign-run`.
- Cycle: `20260808T140729Z-5fa4771d212a-cycle`.
- Failure phase: `CAMPAIGN_PRE_LIFECYCLE`.
- First cause: `HolderBudgetError:MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS`.

## Audit result

The post-attempt read-only audit completed without source fetching, runtime, or database mutation. The authoritative database remained SHA-256 `3a27598da678c20b96685722c664e14bca45a950e416c586ffdd1f74258109cf`; SQLite integrity was `ok`; foreign-key violations were zero; all inspected operational states were terminal; protected downstream findings were empty; attempt-linked campaign-window findings were empty.

The exact pre-holder identity surfaces were:

- action-local identities A = 5;
- campaign-owner identities C = 5;
- source-request manifest identities M = 9;
- `A_minus_C = 0` and `C_minus_A = 0`;
- `A_minus_M = 0` and `C_minus_M = 0`;
- `M_minus_A = 4` and `M_minus_C = 4`.

The four manifest-only identities were durable GeckoTerminal `candidate_market_batch` transports for mints:

- `6rV3hFypi5aUzuAM6xiY1bD4zhvZuabs7dMy4cVxpump` — request `1982`;
- `BAUi4CNLUTwihs7YqXZ9qTxvJfgW4ACmHHzsdJSppump` — request `1983`;
- `C8Q9V1tFU3eqgqFdJR3SkMEhoaVL2EuQ3EGTmWMApump` — request `1984`;
- `Fpjnb1wHJhBvjygsP2HjT8faTLMwtVZBWvuqrpPYpump` — request `1985`.

Each manifest owner is explicitly `UNKNOWN_LIQUIDITY_BACKUP|1..4`. Each durable request key is the same campaign root followed by `-liq-backup-geckoterminal-...`. The audit script's convenience boolean reported false only because its heuristic looked for `unknown-liq` / `unknown_liq`; that heuristic is not authoritative and does not contradict the exact owner/request evidence.

## Confirmed root cause

`run_bounded_unknown_liquidity_backup()` is the owner gap.

At the authorized code lineage the function:

1. constructs a local `MeasuredTransportLedger`;
2. records normalized payload transports with `record_payload_transports()`;
3. emits those measured identities into `source_request_coverage`, which feeds the authoritative campaign source-request manifest;
4. does **not** accept a `transport_identity_observer` parameter;
5. does **not** set `on_transport_recorded` on its local ledger;
6. does **not** accept a `stage_evidence_sink` parameter;
7. therefore does not seal those backup transport identities into the campaign six-unit owner.

Consequently the same real transport is visible in M but absent from both A and C. The fail-closed pre-holder equality gate correctly rejected continuation. The later equality check is not defective and must not be weakened.

The canonical transport identity itself is not the repair target. In particular, the GeckoTerminal payload currently projects the transport stage as `MINT_MARKET_BATCH`; the audit provides no basis to rename or rewrite that identity. The repair is ownership plumbing only.

## Attempt mutation / safety closeout

The blocked attempt performed the authorized pre-lifecycle source/discovery work and terminal bookkeeping. Terminal evidence reports 10 source calls, 10 source requests, 8 responses, 2 failures, and 6 command-level database writes; the broader mutation envelope also records discovery/exact-market projection changes. No campaign window was linked to this attempt and no protected downstream surface was reached.

Cleanup completed, lease was released, Scheduler runtime calls were zero, active locked Scheduler work was zero, and all retry/rerun/resume/restart/successor counters remained zero.

## Money-usefulness contribution

This audit removes a deterministic accounting blocker that wastes a one-use operational attempt after lawful market-source work. Fixing the ownership gap will allow the existing fail-closed accounting gate to distinguish real transport completeness from actual accounting defects instead of stopping because one lawful backup stage was invisible to two accounting owners.

## What this lane improves

- Establishes the exact failed transport identities and durable request ownership.
- Proves the defect is confined to the unknown-liquidity backup accounting handoff.
- Preserves the manifest/action/campaign three-way equality invariant.
- Identifies the smallest design boundary for repair.

## What this lane does not unlock

This audit does not authorize implementation, a new authorization package, a wrapper rerun, any source/runtime execution, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Proof required before implementation closeout

The next design must specify how every successfully measured unknown-liquidity-backup transport reaches both:

- the action-local observer at measurement time; and
- the campaign six-unit owner through sealed stage evidence;

while preserving zero/failure semantics without inventing transport identities or weakening source-request reconciliation.

After implementation, minimum bounded zero-runtime proof must cover exact identity equality, multi-backup sequencing, failure/zero-transport behavior, and preservation of the existing pre-holder fail-closed check.

## Functionality Risks / Setbacks / Efficiency Blockers

- Wiring only the action-local observer would change A but leave C incomplete.
- Wiring only campaign stage evidence would change C but leave A incomplete.
- Fabricating a transport identity for failed/zero-transport requests would weaken accounting truth.
- Rewriting the provider's canonical transport identity is unnecessary scope expansion.
- Weakening `build_pre_holder_budget_snapshot()` or manifest equality would hide accounting defects rather than repair them.
- The consumed authorization remains permanently non-reusable; a future real attempt requires a completely new explicit operator authorization only after design, implementation, bounded proof, and closeout pass.
