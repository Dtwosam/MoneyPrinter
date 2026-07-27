# Printer V1 V2-9.8B.16 Batch-Scoped Discovery Persistence Repair Design

## 1. Status and classification

```text
LANE: V2-9.8B.16 — Batch-Scoped Discovery Persistence Repair
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
CODE CHANGE JUSTIFIED: YES
IMPLEMENTATION AUTHORITY: this operator-approved combined gated task
PRODUCTION AUTHORITY: NONE
```

Baseline: clean `e89efa47d63032e78458ea57c96f259e0daed393`.

The V2-9.8B.15 audit proved that the combined discovery executor reused a
global observation ID across campaigns while the immutable canonical payload
included batch-specific ownership. The same construction affects merged
candidates, origin verifications, and PumpSwap confirmations.

This design is intentionally narrow. It does not alter discovery policy,
candidate count, liquidity floor, budgets, capacity, cooldowns, windows,
Source Governor, Central Scheduler, memory policy, retrieval, or financial
capabilities.

## 2. Starting gate

Before design or implementation:

- exact HEAD `e89efa4`;
- clean tracked and untracked worktree;
- no active Printer process;
- no active campaign lease;
- no active campaign or Scheduler work;
- SQLite integrity `ok`;
- zero foreign-key violations.

All gates passed. The authoritative database remains read-only for this lane.

## 3. Invariants

The repair must preserve:

1. One immutable discovery object belongs to exactly one discovery batch.
2. The same lawful on-chain fact may be observed independently by later
   campaigns without sharing a batch-owned primary key.
3. Exact repeats inside the same batch remain idempotent.
4. Conflicting repeats inside the same batch remain rejected.
5. Historical IDs and rows are never rewritten.
6. Existing primary keys, unique constraints, canonical hashes, provenance
   links, and foreign keys remain authoritative.
7. A persistence failure rolls back the combined discovery transaction.
8. Source Governor and Central Scheduler ownership remain unchanged.
9. Fault evidence contains no source payload, secret, URL, filesystem path, or
   arbitrary exception text.
10. No touch-only file may be described or retained as captured stdout/stderr.

## 4. Identity design

### 4.1 Deterministic batch-scoped identity

Add one private identity constructor in the canonical combined discovery owner:

```text
<object-kind>:<batch-digest>:<semantic-digest>
```

Where:

- `batch-digest` is the first 24 lowercase hexadecimal characters of SHA-256
  over the full `discovery_batch_id`;
- `semantic-digest` is the first 24 lowercase hexadecimal characters of SHA-256
  over a domain-separated canonical sequence of semantic identity parts;
- all inputs are required, deterministic strings;
- no database read, provider call, score, rank, or timestamp chooses the ID.

The batch digest makes ownership explicit without embedding a very long
campaign/run/cycle string in every primary key. The semantic digest keeps
same-batch repeats stable while preventing delimiter ambiguity.

### 4.2 Affected objects

| Object | Semantic identity parts | New ownership |
|---|---|---|
| provider observation | route/provider, mint, signature or source fact identity | discovery batch |
| merged candidate | exact candidate identity key | discovery batch |
| origin verification | batch-scoped merged candidate ID | discovery batch |
| PumpSwap confirmation | batch-scoped merged candidate ID | discovery batch |

All direct-create, graduation-native, and secondary provider observation IDs
must use the constructor. Fixing only graduation-native observations would
leave the same defect in other provider lanes.

Origin and PumpSwap IDs derive from the already batch-scoped candidate ID and
the same batch identity. Their FKs therefore continue to point to exact
batch-owned candidates.

### 4.3 No migration

No migration is required:

- all four primary-key columns are already `TEXT`;
- no length constraint rejects the new format;
- FKs reference the stored text identity without assuming its old shape;
- existing rows remain valid and immutable;
- new code affects only IDs for future rows.

Any migration or historical rewrite would add risk without solving an unmet
schema requirement and is prohibited in this lane.

## 5. Idempotency and conflict behavior

The persistence owners remain unchanged:

- lookup by object ID;
- return the prior hash/state for a byte-identical repeat;
- raise `DiscoveryPersistenceError` for a conflicting repeat;
- preserve immutable triggers and batch ownership constraints.

The repair changes only the executor-provided identity. Consequently:

- same batch + same semantic identity + same canonical content => same ID and
  idempotent acceptance;
- same batch + same ID + different canonical content => conflict rejection;
- later batch + same mint/signature => different ID and independent row.

## 6. Structured persistence-fault evidence

### 6.1 Envelope

`CampaignExecutionResult` gains an optional `fault_details` mapping. A caught
`DiscoveryPersistenceError` produces only:

```text
exception_type
safe_message
persistence_stage
object_kind
first_terminal_cause
lifecycle_started
```

The first terminal cause remains exactly `PERSISTENCE_FAULT` and
`lifecycle_started` remains false at the activation boundary.

### 6.2 Safe-message policy

Only fixed, repository-owned conflict messages are allowed through verbatim.
All other exception text becomes:

```text
discovery persistence contract rejected
```

This prevents secrets, payload fragments, URLs, or paths from entering terminal
evidence. The exception type is the fixed internal class name, not an arbitrary
module-qualified string.

### 6.3 Propagation

The fault envelope flows through:

```text
CombinedPumpfunCampaignExecutor
-> ActivationResult
-> OriginLifecycleResult.lifecycle
-> canonical terminal report terminal.fault_details
-> terminal-summary.json fault_details
```

It does not change cleanup status, restart policy, source totals, or capability
locks.

## 7. Truthful process output

The public operational command currently creates `stdout.log` and `stderr.log`
with `touch`, but neither Python nor the PowerShell wrapper redirects output to
them. Remove those keys and file creations from the artifact contract.

The wrapper continues to invoke Python in the foreground, so stdout/stderr
truthfully belong to the parent console. This is smaller and safer than adding
an internal tee/redirect layer during a persistence repair.

No existing historical artifact is deleted.

## 8. Implementation scope

Expected code files:

- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/operator_cli/abstract_campaign_command.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Expected focused proof file:

- `tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py`

No schema, migration, source adapter, selector, budget, scheduler, memory,
retrieval, paper, wallet, or financial file may change.

## 9. Disposable proof contract

Fixture sources and disposable migrated SQLite databases only must prove:

1. Two sequential campaigns persist the same mint/signature independently
   through observations, merged candidates, origin verifications, and PumpSwap
   confirmations.
2. Exact same-batch repeats remain idempotent for all four owners.
3. Same-batch conflicting repeats remain rejected.
4. A persistence conflict through the combined executor rolls back staged
   discovery, selection, tracking, Scheduler, factory, and memory mutations.
5. The fault envelope reaches terminal evidence with the six required fields
   and redacts arbitrary secret-like exception text.
6. Operational artifact paths make no stdout/stderr capture claim and create no
   touch-only log.
7. Integrity is `ok`, FKs are clean, active work is zero, and locked capability
   counts do not change.

Focused neighboring regressions:

- combined discovery executor;
- discovery persistence contracts;
- origin-to-lifecycle integration;
- public operational command;
- unified terminal/report path only if the changed-path proof does not already
  cover it.

Stop on the first changed-path failure. Do not run a broad suite.

## 10. Stop conditions

Stop and fail the lane if:

- a migration or historical rewrite becomes necessary;
- same-batch conflicts are weakened;
- cross-batch rows lose exact batch provenance;
- transaction rollback leaves partial work;
- a fault exposes arbitrary exception content;
- source/scheduler ownership or any frozen policy changes;
- any retrieval or financial delta appears;
- a live source or authoritative database would be required.

## 11. Money-usefulness contribution

Persistent memory growth must be able to observe the same lawful token in more
than one campaign. Batch-scoped identities preserve recurrence as independent,
auditable evidence instead of misclassifying it as a database fault. Exact safe
fault evidence also reduces wasted source budget and repair guesswork while
keeping dirty, conflicting, or partial work fail-closed.

## 12. What remains locked

This repair does not authorize production, another campaign, live sources,
clean-memory promotion, 1h/4h/12h/24h production work, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys,
signing, real funds, paid APIs, scoring, ranking, confidence, weighted logic,
embeddings, vectors, unbounded runtime, successor creation, or automatic retry.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Effect | Control |
|---|---|---|
| Partial identity repair | next object type collides after observation succeeds | repair and prove all four objects together |
| Hash-domain ambiguity | two semantic sequences could share joined text | domain separation plus canonical length-delimited parts |
| Over-broad exception text | secrets or payload fragments enter reports | fixed-message allowlist and generic fallback |
| Report propagation drift | executor has detail but terminal artifact loses it | end-to-end terminal payload assertion |
| Replay semantics overstated | a whole campaign rerun is not the same as object idempotency | prove exact persistence-owner repeats; do not authorize campaign resume |
| Existing active rows affect sequential proof | second campaign could be blocked by cooldown/tracking | assert four persistence objects before any policy stop; do not weaken policy |
| Misleading logs remain | empty files imply capture | remove touch-only files and test artifact contract |
| Proof accidentally reaches live/authoritative state | unsafe mutation | temp DB, fixture owners, patched artifact root only |
