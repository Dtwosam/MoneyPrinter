# Printer V1 V2-9.7E.43 — $3K Graduated Discovery and Selection Front-Door Design

## Purpose

E.41 froze the graduation-only tracking law (no bonding-curve token is ever
selectable). E.42 made real graduated Pump.fun candidate supply operational via
the direct PumpPortal `subscribeMigration` → on-chain verification →
`printer_pumpswap_graduated_candidate_registry` (migration 040) path. Both are
preserved unchanged.

E.43 adds the missing **market-performance front door**: a graduated candidate may
enter active selection only once its **exact PumpSwap pool** carries a governed,
fresh liquidity of **`liquidity_usd >= 3000`**. Below-floor and unproven-liquidity
graduated candidates remain durable discovery evidence but never consume an active
tracking slot.

`$3,000` is the **only** numeric market-performance threshold introduced. No
volume, transaction, age, holder, trend, boost, score, confidence or weighting
gate is added anywhere.

## Frozen policy (E.43 selection front-door law)

Every exactly confirmed graduated Pump.fun token may be retained as discovery
evidence regardless of liquidity.

A candidate may enter **active selection** only when all of the following hold:

1. exact Pump.fun origin is confirmed (E.42 migration proof);
2. exact PumpSwap graduation and pool identity are confirmed (E.42 registry);
3. current governed market evidence belongs to that **exact** Solana mint and
   **exact** PumpSwap pool;
4. existing source-quality and categorical activity gates pass;
5. `liquidity_usd >= 3000`;
6. existing deduplication, STNP, cooldown and rotation gates pass.

Liquidity classification (the only numeric comparison):

| Condition | Result |
|---|---|
| `liquidity_usd < 3000` | `LIQUIDITY_BELOW_SELECTION_FLOOR` (retained, not selectable) |
| `liquidity_usd >= 3000` | liquidity gate passes |
| missing / stale / conflicting / estimated / token-level / wrong-pool / non-exact | `LIQUIDITY_UNPROVEN` (retained, not selectable) |

Missing liquidity is **never** converted to zero. `$2,999.99` fails; `$3,000.00`
passes when every other gate passes; a `$30` pool is retained but never selected.

## Reused owners (no duplicates created)

| Concern | Reused owner |
|---|---|
| Graduated candidate supply (LATEST) | `discovery/direct_migration_discovery.py` (E.42, unchanged pipeline) |
| Durable graduated registry | `sources/pumpswap_graduated_registry.py` (migration 040) |
| Graduated export | `operator_cli/persistent_candidate_pool.export_graduated_pilot_candidates` |
| Exact-pair market evidence | `sources/dexscreener.py` `build_dexscreener_pair_snapshot_transport` + `normalize_dexscreener_fixture_result` (request kind `pair_market_snapshot`) |
| Governed execution + ledger | `sources/governed_execution.execute_source_request_with_governor` |
| Deterministic seeded selection primitive | `discovery/combined_executor._fisher_yates`, `_token_identity` |
| Categorical two-slot law | mirrors `combined_executor._categorical_two_slot` (one LATEST + one non-latest) |
| STNP / cooldown gates | `discovery/selection_batch.check_token_selection_cooldown`, `check_pair_selection_cooldown` |
| Handoff contract | `lifecycle/tracking_queue.enqueue_tracking_item` shape (compatibility proved, not invoked) |

New file: `discovery/graduated_liquidity_front_door.py` — the E.43 owner. It does
**not** re-implement discovery, verification, the registry, the selection
algorithm, or the handoff; it composes them and adds the liquidity floor.

## Exact-pool liquidity enrichment (governed)

For every graduated candidate (LATEST and PERSISTED), one governed DexScreener
`pair_market_snapshot` request is made against the confirmed PumpSwap pool
(`GET /latest/dex/pairs/solana/{pool}`), executed through the Source Governor and
recorded in the source ledger. `liquidity.usd` is accepted **only** when:

* the governed response is `COMPLETE`/`CLEAN` (a `STALE`/`FAILED`/rate-limited
  result → `LIQUIDITY_UNPROVEN`; this is the adopted freshness contract — the
  request is made fresh in the current cycle, one transport is one charged
  operation, no retry / rotation / reconnect / fallback);
* the returned pair's `chainId == "solana"`;
* the returned pair's `pairAddress` **exactly equals** the confirmed PumpSwap pool;
* the returned pair's `baseToken.address` **exactly equals** the candidate mint;
* `liquidity.usd` is a valid finite non-negative number.

A token-level lookup (multiple pairs) can never substitute: only the pair whose
`pairAddress` exactly matches the confirmed pool is read, and if it is absent the
result is `LIQUIDITY_UNPROVEN`. DexScreener supplies **market evidence only**; it
never proves Pump origin or graduation (those remain owned by the E.42 on-chain
proof + registry).

## Provenance (truthful, non-fabricable)

* `LATEST_GRADUATED` — the mint was confirmed through a migration event in the
  **current** discovery cycle (present in `confirmed_this_cycle`).
* `PERSISTED_GRADUATED` — the mint existed in the durable graduated registry
  **before** the current cycle and was **not** rediscovered as a current-cycle
  migration.

Provenance is derived only from `(current-cycle confirmed set)` vs
`(durable registry)`. It is never taken from caller labels, arbitrary timestamps
or provider ordering. The misleading `PERSISTED_ACTIVE` label (which claimed
activity that no snapshot has proved) is **replaced** by `PERSISTED_GRADUATED`
across the registry, direct-migration discovery, and the executor category map.
`DUMP`/`DECAY`/`REVIVAL`/`CONSOLIDATION` are **not** derived in discovery — they
remain snapshot/memory-owned.

## Persisted refresh

Persisted candidates are re-enriched through the **same** exact-pool liquidity
path each cycle (no continuous pre-selection monitoring loop; one governed request
per evaluation). A later clean observation may move a persisted candidate above or
below the floor:

* crossing to `$3,000+` may make it eligible for a new lifecycle;
* falling below `$3,000` makes it ineligible for a new lifecycle.

## Mixed two-slot selection (preserved)

After enrichment + floor, eligible candidates are partitioned by provenance. When
at least one eligible `LATEST_GRADUATED` and one eligible `PERSISTED_GRADUATED`
exist:

```text
slot 1 -> one LATEST_GRADUATED   (deterministic seeded uniform)
slot 2 -> one PERSISTED_GRADUATED (deterministic seeded uniform)
```

This is exactly the E.41 categorical two-slot anti-concentration rule with the
single non-latest category `PERSISTED_GRADUATED`. Selection inside each partition
uses the shared `_fisher_yates` primitive over an identity-sorted list keyed by
`(_token_identity(mint), market_identity, lifecycle)` — byte-identical to the
canonical `_uniform_pick`. A mint reachable through several channels is one
candidate (registry primary key is the mint) and receives no probability
advantage. Provider order, liquidity magnitude above the floor, boost, rank and
popularity never affect selection — liquidity is a **pass/fail floor only**, never
a comparative key. When only one partition has eligible candidates the rule
degrades honestly (uniform within it; no fabricated diversity).

## Tracking boundary (preserved)

The front door stops at **deterministic selected-pair readiness**: it proves each
selected pair is compatible with the canonical atomic two-slot handoff contract
(non-empty exact mint, `solana-mainnet:pumpswap:{pool}` market identity, exactly
two distinct selected pairs, distinct slots) **without** enqueuing tracking,
starting the scheduler, snapshots, lifecycle, or memory. Snapshots and memory
windows remain the sole owners of every post-selection behavior (pumps, dumps,
decay, revival, consolidation, liquidity collapse, trajectory, outcome).

## Non-goals / locks

No FULL_PILOT, scheduler execution, snapshot, lifecycle, memory, retrieval,
decision, position, trade, audit, or PnL work. No paid API, wallet, keys, signing,
funds. No scoring/ranking/confidence/weighted logic (the floor is a categorical
pass/fail, not a score). No Source Governor or Central Scheduler bypass. Solana
memecoin, paper-only. E.41 graduation-only law and E.42 direct-migration pipeline
are unchanged.
