# Printer V1 V2-9.7E.42 — Direct Pump Migration Discovery and Graduated-Candidate Supply Micro-Design

## Status

Frozen micro-design for the operator-approved E.42 continuous repair. It adopts no
new provider, adds no paid dependency, and adds no source-budget increase. It uses
the already-adopted keyless PumpPortal `subscribeMigration` free stream, the
already-adopted governed PumpSwap on-chain signature→pool resolution and pool
confirmation, the Source Governor and the Central Scheduler. It adds exactly one
new durable table (`printer_pumpswap_graduated_candidate_registry`) modelled on the
E.5 finalized-origin registry. It makes BL-41-04 operational for the direct
migration channel: real graduated Pump.fun candidate supply from migration events,
with no manual migration signature.

## Root problem restated (BL-41-04)

After E.41, graduation-only selection is enforced but **no channel supplies
already-graduated Pump.fun tokens for fresh live discovery** without an
operator-supplied migration-signature locator. `export_graduated_pilot_candidates`
is empty because the only persistence owner
(`printer_pumpfun_finalized_origin_registry`) stores pre-graduation origins.

Three concrete gaps block the direct migration channel:

1. **Signature dropped.** `_normalize_pumpportal_event` for `pumpfun_migration_stream`
   emits mint + pool but **discards the migration `signature`**, so the on-chain
   verifier has no locator to fetch the finalized transaction.
2. **No exact Pump-migration proof.** The existing PumpSwap signature resolver
   proves a unique PumpSwap pool, but nothing proves the finalized transaction is
   the applicable **Pump** migration for the exact mint (adopted program evidence).
3. **No graduated persistence.** There is no store for
   `PUMPSWAP_GRADUATED_CONFIRMED` candidates, so confirmed graduations cannot
   persist, refresh, or mix across cycles.

## Authoritative evidence chain (frozen)

```text
PumpPortal subscribeMigration      (keyless free stream — locator evidence only)
  -> exact mint + migration signature
  -> governed getTransaction(signature) finalized   (pumpswap source, read-only)
  -> EXACT PUMP MIGRATION PROOF (adopted program evidence):
       * meta.err == null (success)
       * exact mint present in account keys (static + ALT)
       * Pump.fun program 6EF8rre… present in account keys (invoked)
       * PumpSwap AMM program pAMMBay… present in account keys (pool created here)
       * finalized block time present (migration evidence only)
  -> resolve unique PumpSwap pool from the signature
       (owner == pAMMBay…, base_mint@43 == mint, unique-or-fail)
  -> confirm the pool account (owner + base_mint@43 == mint)
  -> persist PUMPSWAP_GRADUATED_CONFIRMED candidate
```

PumpPortal is **notification/locator evidence only**. The finalized Solana
transaction plus PumpSwap account confirmation are the authoritative graduation
evidence. The Pump-migration proof uses only **adopted** program identities
(`PUMP_PROGRAM_ID`, `PUMPSWAP_AMM_PROGRAM_ID`); the exact migration instruction
discriminator remains `UNKNOWN_REQUIRES_RESEARCH` and is deliberately **not**
invented. Program-presence + unique PumpSwap pool creation in the same finalized
transaction is the adopted graduation proof.

## Migration intake (bounded governed channel)

`intake_migration_events(normalized_payload)` over the governed
`pumpfun_migration_stream` result:

- skips acknowledgment / non-event frames (no mint);
- requires a valid exact `mint` **and** `signature`;
- deduplicates by mint and by migration signature;
- records malformed, missing-mint, missing-signature and conflicting events
  honestly (same mint↔different signature, or same signature↔different mint) and
  never uses a conflicting pair;
- performs no wallet, authentication, payment, trade subscription or execution.

The keyless migration transport already exists
(`build_pumpportal_migration_transport`, hard bounds ≤5 events / ≤120s, zero
reconnect). `_normalize_pumpportal_event` is extended to carry
`migration_signature` for migration request kinds only (never a timestamp; never
`token_created_at`).

## On-chain verification (per candidate, fail-closed)

`build_graduation_verifier_transport(migration_signature, expected_mint)` is a
governed read-only transport under the pumpswap `pumpswap_signature_pool_resolution`
request kind. Same governed operations as the existing resolver
(`getTransaction` + batched `getMultipleAccounts`), plus the pure Pump-migration
proof over the already-fetched transaction:

1. `prove_pump_migration_transaction(tx_result, expected_mint)` — pure. Fails
   closed on: transaction not found, missing meta, failed transaction, mint not
   referenced, Pump program absent, PumpSwap program absent, or missing block time.
2. `resolve_pumpswap_pool_from_transaction(...)` — existing unique-or-fail pool
   resolution (owner + base_mint@43 == mint).
3. `confirm_pumpswap_pool_from_account(...)` — existing owner + base_mint@43 == mint.

Any failed stage returns a fail-closed `fixture_status: failure` payload
(`graduation_verification_failed_<stage>_<reason>`) that the existing
`normalize_pumpswap_confirmation_payload` fails closed on. Zero, multiple,
malformed, wrong-owner or mint-mismatched pools all fail closed. Migration block
time / slot are stored as graduation evidence only and never overwrite
`token_created_at`.

## Graduated-candidate persistence and mix

New durable table `printer_pumpswap_graduated_candidate_registry` (migration 040),
modelled on `printer_pumpfun_finalized_origin_registry`. Immutable graduation
evidence; only `latest_observed_at`, `latest_channel`, `observation_count` may be
updated (BEFORE UPDATE / DELETE triggers enforce this). Columns:

- `mint_identity` (PK, exact mint);
- `migration_signature` (UNIQUE), `migration_provenance`;
- `pumpswap_pool`, `pumpswap_program_id` (CHECK == pAMMBay…),
  `pump_program_id` (CHECK == 6EF8rre…), `base_mint_offset`;
- `graduation_block_time`, `graduation_slot`;
- `lifecycle_state` (CHECK == `PUMPSWAP_GRADUATED_CONFIRMED`),
  `market_identity` (`solana-mainnet:pumpswap:<pool>`);
- `discovery_channel`, `confirmation_evidence_hash`, `contract_version`;
- `first_observed_at`, `latest_observed_at`, `latest_channel`, `observation_count`.

There is **no** `token_created_at` column.

Category mix (per cycle):

- a candidate first confirmed / re-observed via a **new migration event this cycle**
  is `LATEST_GRADUATED`;
- a previously confirmed candidate not re-observed this cycle is a non-latest
  category (`PERSISTED_ACTIVE` by default; the richer `DUMP` / `CONSOLIDATION` /
  `DECAY` / `REVIVAL` categories require adopted DexScreener exact-market delta
  evidence, which this discovery lane does not compute — so it degrades honestly
  to `PERSISTED_ACTIVE`, never fabricated).

`export_graduated_pilot_candidates` (persistent pool) now reads the graduated
registry when present and returns the confirmed graduated candidates
(`GRADUATED_ONLY`); with zero graduated rows it keeps the honest empty
`NO_PERSISTED_GRADUATION_EVIDENCE` result (origin-only DBs unchanged).

## E.41 preservation

Graduation-only selection, no bonding-curve candidate, no 900-second FULL_PILOT
gate, deterministic categorical two-slot distribution, and the no-score / no-rank
/ no-weight / no-confidence / no-duplicate-boost rules are all unchanged. This lane
only **supplies** confirmed graduated candidates; it does not alter the executor
selection law. The discovery channel label `LATEST_GRADUATED` maps to the E.41
`_LATEST_CHANNELS` latest category; persisted categories map to non-latest.

## Owners changed / added

- `src/printer_v1/sources/pumpportal.py` — carry `migration_signature` for
  migration events (no timestamp).
- `src/printer_v1/sources/pump_migration.py` (new) — `prove_pump_migration_transaction`,
  `verify_graduation_from_transaction`, `build_graduation_verifier_transport`.
- `src/printer_v1/sources/pumpswap_graduated_registry.py` (new) — durable graduated
  candidate persistence (record / lookup / touch / export / import).
- `src/printer_v1/discovery/direct_migration_discovery.py` (new) — governed intake,
  per-candidate governed verification orchestration, persistence, category mix,
  and the bounded discovery report.
- `migrations/040_pumpswap_graduated_candidate_registry.sql` (new).
- `src/printer_v1/operator_cli/persistent_candidate_pool.py` —
  `export_graduated_pilot_candidates` reads the graduated registry.

No holder, snapshot, lifecycle, memory, retrieval, decision, position, trade,
audit, PnL, Source Governor or Central Scheduler owner is changed.

## Offline proof

`tests/test_v2_9_7e_42_direct_migration_discovery.py` proves the required
properties on fixtures + isolated temporary DBs only (no live pilot, no live
source, no persistent-DB mutation).

## Bounded live discovery proof

Up to three separate discovery-only attempts from a clean committed HEAD, each on a
fresh isolated proof DB and identity, using only adopted source ceilings, collecting
bounded migration events, verifying them on-chain, and persisting confirmed
graduated candidates. No lifecycle, pilot authorization, or memory work. PASS
requires ≥2 real, independently confirmed graduated Pump.fun candidates end-to-end
without manual signatures.

## Permanent locks preserved

Solana-only; Solana memecoin-only; paper-only; no wallet/keys/signing/funds/
execution; no paid APIs; no scoring/ranking/confidence/weighted decisions; no
embeddings/vectors; no Source Governor or Central Scheduler bypass; 5m support-only;
no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/trade events/paper
audits/PnL; no later-lane work.
