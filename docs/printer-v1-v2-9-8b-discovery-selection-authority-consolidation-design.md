# Printer V1 V2-9.8B Discovery and Selection Authority Consolidation Design

Date: 2026-07-30

Lane: `V2-9.8B Discovery and Selection Authority Consolidation`

Status: `DESIGN_FOR_COHESIVE_IMPLEMENTATION`

## Work gate

- Branch / required HEAD: `master` /
  `98263872315ca8556b2620a80e6418c73a50e8eb`
- Authoritative database SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head remains `049` unless the smallest append-only migration is
  proven necessary (this design does not require a schema migration).
- Sequence: full code audit → consolidation design → complete implementation →
  frozen offline proof → closeout.
- Forbidden during this lane: live provider/RPC/WebSocket probe, Memory Factory
  campaign against the authoritative database, N2/N7, cursor, recovery,
  backfill, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
  audits, PnL, wallets, private keys, signing, funding, paid APIs, scoring,
  ranking, confidence, weighting, embeddings/vectors.

## Mandatory source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION:
CONTRACT_DRIFT + DESIGN_GAP (cohesive surface)

EVIDENCE:
Fourteen reproducible discovery/selection authority defects remain after the
measured-budget design and the BLOCKED source-compatibility correctness lane.
They are not independent micro-repairs; selection, accounting, endpoint
ownership, role validation, deadlines, cooldown, handoff and report/replay all
share one ordinary-run authority surface.

OFFICIAL / PRINTER CONTRACT COMPARISON:
- Solana getMultipleAccounts max 100 accounts; v0 tx up to 256 account keys
  => PumpSwap verification is 1 getTransaction + 1..3 account batches.
- Pinned Pump migrate IDL defines exactly 25 ordered roles.
- Measured budget architecture defines six independent unit types.
- Ordinary restored path is direct Pump live tail, not PumpPortal.
- Exactly two active tokens; WINDOW_15M only; 5m support-only.

ROOT CAUSE:
Request-count ledgers, partial migrate-role checks, multi-owner selection,
latest/persisted readiness columns, frozen-now deadlines, fail-open cooldown
absence handling, and fixture-era carriers co-own the ordinary discovery path.

CODE CHANGE JUSTIFIED:
YES — one cohesive implementation across the discovery/selection authority
surface. Partial patches are prohibited by the lane.

MINIMUM SAFE RESPONSE:
Implement the full contract below with frozen transports and disposable
migration-049 databases only.

FOCUSED PROOF:
Frozen offline proof covering the 14 repair items plus focused and one broad
affected operational suite. No live source probe.

AUTHORIZATION STATUS:
This design is the implementation authority for this lane only.
```

## Final active call graph

```text
public operational `run`
  -> resolve Solana RPC once (immutable SolanaRpcConfiguration)
  -> zero-I/O preflight (same resolved endpoint + typed prohibitions)
  -> direct Pump live-tail adapter (1 signature page + <=12 txs)
  -> exact pinned 25-role migrate decode + PumpSwap join
       (1 getTransaction + 1..3 getMultipleAccounts per candidate, m<=5)
  -> graduated registry persistence
  -> DexScreener fresh-profile bundle (2 HTTP) + bounded exact-pair evaluation
  -> holder/safety readiness funnel (injected same Solana endpoint)
  -> CANONICAL_SELECTION_AUTHORITY.select_two_candidates
       (neutral two-candidate contract; provenance is attribute only)
  -> atomic two-or-none activation + lifecycle materialization
       (or fully compensating rollback)
  -> WINDOW_15M Scheduler-led lifecycle
  -> terminal report with six-unit accounting
  -> zero-source replay equality
  -> safe stop (no retry / restart / successor)
```

Deferred / never on ordinary `run`:

- PumpPortal
- candidate-acquisition N2/N7, cursors, recovery, backfill
- CombinedDiscoveryFixtures constructed-dead selection paths as authority
- lexicographic mint preference as a selection criterion
- latest/persisted compulsory pair quota

## Defect map (audit findings)

| # | Defect | Current owner | Required authority |
|---|---|---|---|
| 1 | Hardcoded `2 * pumpswap` / request-count ops | `direct_migration_discovery`, eligible supply | Measured `SOURCE_TRANSPORT_OPERATION` identities |
| 2 | Partial migrate role checks | `pump_contracts.decode/verify` | All 25 ordered roles + relationships |
| 3 | Holder may re-resolve RPC independently | `solana_rpc_holder`, evidence fill | One injected `SolanaRpcConfiguration` |
| 4 | Incomplete prohibition schema | `OperationalSourceContract` | Typed wallet/key/sign/fund/paid/exec fields + recursive scan |
| 5 | Fragmented selectors | mixed two-slot, holder pair, reserve slice | One canonical deterministic selector |
| 6 | Lexicographic mint preference | fresh-profile `sorted(mints)` | Identity for determinism only inside seeded shuffle; no lex preference |
| 7 | `selected_latest` / `selected_persisted` readiness columns | front door / GraduatedSupply | Neutral two-candidate contract |
| 8 | Deadline uses frozen `now` | `eligible_token_supply` | Real monotonic wall-clock deadline |
| 9 | Cooldown/state fail-open on missing tables | `_cooldown_ok`, market floor | Fail closed |
| 10 | Provider row/byte bounds incomplete | Dex adapters / ledgers | Explicit byte + row ceilings fail closed |
| 11 | Activation-to-lifecycle not fully compensating | handoff owners | Atomic two-or-none or full compensate |
| 12 | Fixture-era carriers on ordinary path | `FixtureOriginProof` names / fixtures | Ordinary carriers are graduation-native; fixtures offline-only |
| 13 | Report mixes request counts | campaign report/replay | Canonical six-unit accounting |
| 14 | Active docs still drift | assistant anchor / intersecting tests | Align current authority |

## Contracts

### Measured transport identities (item 1, 10, 13)

Six units (from measured budget architecture):

1. `SOURCE_TRANSPORT_OPERATION`
2. `LOCAL_VALIDATION_STEP`
3. `SCHEDULER_WORK_ITEM`
4. `SOURCE_RESPONSE_BYTES`
5. `NORMALIZED_SOURCE_ROWS`
6. `LIFECYCLE_RESERVED_TRANSPORT_OPERATION`

Every transport identity includes stage, source, endpoint owner, method,
ordinal, target category, bytes, rows, and categorical result. Parsing and
validation never count as transports. Missing, duplicate or over-ceiling
identities fail closed before continuation.

PumpSwap verification declares actual batches: `1 + ceil(account_keys/100)`
with `1 <= batches <= 3`. DexScreener fresh profiles declare exactly two HTTP
operations inside one governed request when the bundle is attempted.

Stage ceilings and ordinary emergency stop remain those of the measured budget
architecture (candidate-supply 46, ordinary campaign 136). This lane does not
raise ceilings to force PASS.

### Complete 25-role migrate contract (item 2)

| Pos | Role | Relationship |
|---:|---|---|
| 0 | `global` | PDA `["global"]` on Pump = fixed GLOBAL |
| 1 | `withdraw_authority` | present valid pubkey; must not equal global/system |
| 2 | `mint` | exact expected mint |
| 3 | `bonding_curve` | PDA `["bonding-curve", mint]` |
| 4 | `associated_bonding_curve` | ATA(bonding_curve, SPL Token, mint) |
| 5 | `user` | present valid pubkey (signer identity in instruction) |
| 6 | `system_program` | fixed |
| 7 | `token_program` | fixed SPL Token |
| 8 | `pump_amm` | fixed PumpSwap program |
| 9 | `pool` | canonical pool PDA index 0 |
| 10 | `pool_authority` | PDA `["pool-authority", mint]` on Pump |
| 11 | `pool_authority_mint_account` | ATA(pool_authority, SPL Token, mint) |
| 12 | `pool_authority_wsol_account` | ATA(pool_authority, SPL Token, WSOL) |
| 13 | `amm_global_config` | PDA `["global_config"]` on PumpSwap |
| 14 | `wsol_mint` | fixed WSOL |
| 15 | `lp_mint` | PDA `["pool_lp_mint", pool]` on PumpSwap |
| 16 | `user_pool_token_account` | ATA(user, Token-2022, lp_mint) |
| 17 | `pool_base_token_account` | ATA(pool, SPL Token, mint) |
| 18 | `pool_quote_token_account` | ATA(pool, SPL Token, WSOL) |
| 19 | `token_2022_program` | fixed |
| 20 | `associated_token_program` | fixed |
| 21 | `pump_amm_event_authority` | PDA `["__event_authority"]` on PumpSwap |
| 22 | `event_authority` | PDA `["__event_authority"]` on Pump |
| 23 | `program` | Pump program |
| 24 | `rent` | Rent sysvar |

Each role failure emits a distinct reason code. Undocumented aliases fail closed.

### One Solana endpoint (item 3)

`resolve_solana_rpc_configuration()` once per ordinary campaign/preflight.
Inject the immutable configuration into:

- direct Pump transport
- PumpSwap / graduation verifier
- primary Solana holder evidence
- preflight redacted identity

No independent module-fallback selection on the ordinary path.

### Typed prohibitions (item 4)

Every `OperationalSourceContract` carries explicit booleans/fields:

- `wallet_required`
- `private_key_required`
- `signing_required`
- `funding_required`
- `paid_dependency`
- `metered_account_or_trade_stream`
- `transaction_submission`
- `execution_endpoint`
- `credential_requirement`
- `allowed_credential_category`

Recursive serialized-profile inspection rejects any prohibited true/required
value on active ordinary profiles. Local validation only.

### Canonical selector and neutral two-candidate contract (items 5–7)

Single owner: `printer_v1.discovery.selection_authority`.

```text
eligible_candidates (provenance attribute retained)
  -> combined seeded-uniform order (identity-stable, no score/rank/weight)
  -> optional holder/safety evaluator in that order
  -> exactly two distinct (mint, pair) or none
  -> TwoCandidateSelection {
        candidate_a, candidate_b,
        composition_label,  # diagnostic only
        rejection_funnel, reason_codes
     }
```

Removed as ordinary authority:

- compulsory one-latest + one-persisted readiness columns
- `selected_latest` / `selected_persisted` as selection product
- lexicographic mint preference outside deterministic shuffle seeding
- multi-owner reserve-first-two vs mixed-two-slot vs holder-pair divergence

Provenance remains a truthful attribute (`LATEST_GRADUATED` /
`PERSISTED_GRADUATED`) and may appear in diagnostics. It is never a score and
never a compulsory pair quota.

### Real monotonic deadlines (item 8)

Campaign deadline is compared to wall-clock UTC on every loop iteration, not to
the frozen start timestamp. Exhaustion terminalizes honestly as
`CAMPAIGN_DURATION_EXHAUSTED`.

### Fail-closed cooldown/state (item 9)

Missing rotation-state or market-floor tables, malformed timestamps, or DB
errors fail closed with categorical reasons. No silent pass on absence for
ordinary migrated schema (049).

### Atomic handoff (item 11)

Activation materializes both slots or neither. Injected mid-handoff failure
rolls back token/pair/tracking/scheduler residue for the attempt. Partial one-
slot activation is rejected.

### Ordinary path vs fixture era (item 12)

Ordinary `run` constructs direct Pump transport + graduated supply path only.
`CombinedDiscoveryFixtures` remains available for offline combined-executor
proofs but is not the ordinary intake authority. Carrier type names used by
ordinary graduation remain graduation-native semantics even if historical
class names persist for import compatibility; new authority modules do not
introduce constructed-dead discovery selection logic.

### Report/replay six-unit equality (item 13)

Terminal report and zero-source replay both emit and compare the six unit
totals. Replay creates zero new source transports.

### Document and test alignment (item 14)

Active-authority sections state:

- direct bounded Pump/PumpSwap is the ordinary locator
- PumpPortal is deferred
- one-page stateless incomplete live tail
- honest insufficient-supply safe stop
- no cursor/recovery/backfill

Intersecting tests are updated with the cohesive contract. Unrelated baseline
debts remain untouched.

## Preserved locks

- direct, stateless, one-page Pump live tail
- no PumpPortal on ordinary run
- no N2/N7, cursor, recovery or backfill as operational authority
- at most five verification candidates
- exactly two active tokens
- `WINDOW_15M` only; 5m support-only
- Source Governor and Central Scheduler ownership
- zero automatic retry, restart or successor
- migration head 049
- all retrieval and financial locks
- identity, holder, safety, liquidity, freshness, tradeability, cooldown and
  clean-memory rules are not weakened

## Implementation modules

| Module | Role |
|---|---|
| `sources/measured_transport.py` | identity ledger + six-unit totals |
| `discovery/selection_authority.py` | canonical selector + two-candidate contract |
| `sources/pump_contracts.py` | complete 25-role validation |
| `sources/operational_source_contracts.py` | typed prohibitions + recursive check |
| `discovery/direct_migration_discovery.py` | measured ops reconciliation |
| `discovery/graduated_liquidity_front_door.py` | fail-closed cooldown; neutral product |
| `discovery/eligible_token_supply.py` | wall-clock deadline; transport budgets |
| `operator_cli/graduated_supply_front_door.py` | two-candidate wiring |
| `operator_cli/operational_memory_factory_command.py` | single RPC resolve + inject |
| active authority docs + intersecting tests | alignment |

## Proof plan

Frozen transports + disposable migration-049 DBs must prove:

1. exact public-command composition
2. one/two/three PumpSwap account batches
3. complete 25-role rejection coverage
4. exact operation/byte/row/validation/Scheduler/reservation reconciliation
5. deterministic bounded DexScreener handling
6. one Solana endpoint across preflight and runtime
7. truthful two-candidate provenance attributes
8. real deadline exhaustion
9. fail-closed database-state errors
10. two-or-none activation under injected failures
11. exactly two distinct mints and pairs
12. honest insufficient-supply safe stop
13. report/replay equality on six units
14. zero candidate-acquisition/cursor/recovery deltas
15. zero retrieval/decision/position/trade/audit/PnL deltas
16. migration, integrity, FK and cleanup PASS

## Exact next permitted task after design

Cohesive implementation of this design, then frozen offline proof and closeout
inside the same lane. PASS authorizes only operator review — not a live probe
or campaign.
