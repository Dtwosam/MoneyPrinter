# Printer V1 V2-9.7E.42 — Direct Pump Migration Discovery Closeout

## Verdict

`V2_9_7E_42_DIRECT_MIGRATION_SUPPLY_PASS`

Real graduated Pump.fun candidate supply is now operational directly from
PumpPortal `subscribeMigration` events, with no manual migration signature. A
bounded live discovery attempt confirmed **three** real graduated Pump.fun
candidates end-to-end — exceeding the ≥2 PASS requirement.

## Starting commit

`6e10e4412be7628804ea6acaf4a25024dd7ca7d9` (`Repair graduation-only mixed
discovery admission`).

## Ending commit

This closeout + blocker-register update (`Close direct Pump migration discovery
repair`). No tag.

## What became operational (BL-41-04, direct migration channel)

The direct migration channel now supplies already-graduated Pump.fun candidates
for fresh live discovery without an operator-supplied migration-signature locator:

```text
PumpPortal subscribeMigration (keyless free stream — locator only)
  -> exact mint + migration signature
  -> governed getTransaction(signature) finalized  (pumpswap source, read-only)
  -> EXACT PUMP MIGRATION PROOF (adopted program evidence):
       meta.err == null; exact mint referenced; Pump program 6EF8rre… present;
       PumpSwap program pAMMBay… present; finalized block time present
  -> resolve unique PumpSwap pool from the signature (owner + base_mint@43 == mint)
  -> confirm the pool account (owner + base_mint@43 == mint)
  -> persist PUMPSWAP_GRADUATED_CONFIRMED candidate
```

PumpPortal is notification/locator evidence only; the finalized Solana transaction
plus PumpSwap account confirmation are the authoritative graduation evidence.

## Money-usefulness contribution

Before E.42, graduation-only selection was enforced but no channel actually
supplied confirmed graduated candidates for fresh discovery — a cold-start pilot
honestly blocked `BLOCKED_INSUFFICIENT_GRADUATED_POOL` (BL-41-04). E.42 makes the
direct migration channel a real, operational, keyless graduated-candidate source:
every candidate that reaches the persisted graduated registry is a Pump.fun token
whose graduation to a live PumpSwap market has been independently proven on-chain.
This is the missing supply that turns the graduation-only law from a correct-but-
unproductive gate into a productive, honest graduated-candidate feed.

## Implementation

- `src/printer_v1/sources/pumpportal.py` — the migration normalizer now carries
  `migration_signature` (locator only; never a timestamp; never `token_created_at`).
- `src/printer_v1/sources/pump_migration.py` (new) —
  `prove_pump_migration_transaction` (exact Pump migration proof using only adopted
  program identities), `verify_graduation_from_transaction` (proof + unique
  PumpSwap pool resolution + confirmation), and the governed
  `build_graduation_verifier_transport`.
- `src/printer_v1/sources/pumpswap_graduated_registry.py` (new) — durable immutable
  graduated-candidate persistence (record / lookup / touch / export / import).
  Migration block time is graduation evidence only; no `token_created_at` column.
- `migrations/040_pumpswap_graduated_candidate_registry.sql` (new) — immutable-
  evidence registry (only observation fields mutable; delete blocked).
- `src/printer_v1/discovery/direct_migration_discovery.py` (new) — governed
  multi-round intake, per-candidate governed verification, persistence, and the
  fresh (`LATEST_GRADUATED`) vs persisted (`PERSISTED_ACTIVE`) category mix.
- `src/printer_v1/operator_cli/persistent_candidate_pool.py` —
  `export_graduated_pilot_candidates` reads the graduated registry.

## E.41 preservation

Graduation-only selection, no bonding-curve candidate, no 900-second FULL_PILOT
gate, deterministic categorical two-slot distribution, and the no-score / no-rank /
no-weight / no-confidence / no-duplicate-boost rules are unchanged. E.42 only
supplies confirmed graduated candidates; it does not alter the executor selection
law. `LATEST_GRADUATED` maps to the E.41 latest category; persisted candidates map
to non-latest.

## Repair performed this session (BL-42-01)

**Attempt 1** revealed a repairable live-discovery robustness defect: a PumpPortal
migration notification arrives before its finalized transaction is queryable on the
public multi-backend RPC, so immediate verification fails closed with a transient
RPC/not-found reason (`pumpswap_rpc_transport_error`). The pipeline itself was
correct — re-verifying the exact Attempt-1 event minutes later confirmed it end-to-
end (proven Pump migration; unique pool `6jijdQkZ6Dm9skniw9vJu8Tk2LUD49vBW2CyAoaE7dbU`;
owner + base_mint@43 confirmed).

**Repair (`5dc63f5`)** added bounded, governed, recorded robustness to the
orchestrator, with fixture defaults unchanged:

- `collection_rounds` — accumulate deduplicated locator pairs over N bounded
  governed migration requests;
- `settle_seconds` — one bounded wait before verification so fresh migrations
  finalize;
- `reverify_on_transient` — exactly one extra governed verification per candidate
  whose first attempt failed transiently (never on a genuine graduation failure —
  wrong owner, mint mismatch, zero/ambiguous pool, failed tx are never retried).

## Proof attempts

| Attempt | HEAD | Events | Valid pairs | Confirmed | Terminal | Notes |
|---|---|---|---|---|---|---|
| 1 | `f29c8b9` | 1 | 1 | 0 | transient verify failure | BL-42-01: migration tx not yet finalized/queryable at t≈0 (`pumpswap_rpc_transport_error`); pipeline proven correct by later re-verify. Repaired at `5dc63f5`. |
| 2 | `5dc63f5` | 3 | 3 | **3** | **PASS** | 3 confirmed graduated candidates end-to-end, all `verify_attempts=1`, forbidden deltas 0, integrity ok. |

A third attempt was not required — Attempt 2 confirmed three real graduated
candidates (≥2) from a clean post-repair HEAD.

## Attempt 2 confirmed candidates (live, no manual signature)

| Mint | PumpSwap pool | Graduation block time | Slot |
|---|---|---|---|
| `AVuU5FZriQjWcmqnWVsuDbkrJKXVDNMidS2xhCLS4vdC` | `6MNGrmRLTST3UjdzMcoLNmD5zdrhK3suDFMEKcP8TcxY` | 1784841493 | 434790795 |
| `Hj3Kg6St8BZ7wCijWfYf2ATMEiQ1EW9ahAjH2EjCpump` | `E3EmqM1HvDSf4occyju2b87X4R8xptnEih3LRDjzqjng` | 1784841550 | 434790930 |
| `2KpU8qUzgRjSjvB3bXtEUqXhyY2KcGL9c58GmhRipump` | `5SKDccVfdhZjCPnQZkjR2nk8H2PhP4kDfQdbkr2aZGpa` | 1784841665 | 434791204 |

Source-operation ledger: 6 governed requests (3 migration rounds + 3 verifies), 5
responses, 1 failure (one migration round whose bounded window contained no
graduation — honest empty round). All three verifications succeeded on the first
attempt after the settle window. `forbidden_capability_deltas` all 0;
`PRAGMA integrity_check == ok`; `PRAGMA foreign_key_check == []`.

## Tests

New: `tests/test_v2_9_7e_42_direct_migration_discovery.py` (29 tests) — migration-
signature intake (locator only, dedup, conflict), exact Pump migration proof and
its fail-closed matrix, full verification fail-closed matrix (wrong owner, mint
mismatch, zero/multiple pools), end-to-end confirmed persistence, no
`token_created_at` column/field, idempotent duplicates, cross-cycle persist/refresh,
fresh-vs-persisted category distinction, origin-only pool export stays empty,
`export_graduated_pilot_candidates` reads the registry, immutable evidence + blocked
delete + idempotent import, integrity/FK/forbidden-delta zero, and BL-42-01
transient re-verify / non-transient no-retry / multi-round dedup.

Directly affected regressions (all pass): `test_pumpswap_signature_pool_resolution`,
`test_post_rc_pumpswap_confirmation_adapter`, `test_pumpportal_pumpswap_readiness`,
`test_v2_9_7e_41_graduation_only_mixed_discovery`,
`test_v2_9_7e_40b_persistent_candidate_pool`,
`test_post_rc_pumpportal_discovery_adapter`, `test_v2_2ab_pumpportal_live_transport`
(175 combined) and `test_v2_9_7e_40_full_pilot_admission` (8).

## What remains

- The **trending/top** graduated-discovery channels (GeckoTerminal, Solana Tracker)
  remain `SKIPPED_BLOCKED_CONTRACT` (BL-41-04, contract adoption) — a separate
  operator lane. The direct migration channel does not require them.
- Richer persisted categories (`DUMP` / `CONSOLIDATION` / `DECAY` / `REVIVAL`)
  require adopted DexScreener exact-market delta evidence not computed in this
  discovery lane; persisted candidates degrade honestly to `PERSISTED_ACTIVE`.
- The exact Pump **migration instruction discriminator** remains
  `UNKNOWN_REQUIRES_RESEARCH`; the adopted graduation proof is program-presence +
  unique PumpSwap pool creation in the same finalized transaction, which is
  sufficient and was live-proven three times.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Risk (supply rate):** graduations are sparse; a single bounded 120s window may
  yield only one event (Attempt 1). Mitigated by bounded multi-round accumulation
  within adopted source budgets (Attempt 2 accumulated three across three rounds).
- **Setback (freshness):** BL-42-01 — a just-migrated transaction is briefly not
  queryable; the bounded settle + single transient re-verify resolves it without a
  reconnect loop or unbounded retry.
- **Efficiency blocker:** public multi-backend RPC latency/availability governs
  verification success; failures are honest and recorded, never fabricated.

## Zero-unlock verification

No retrieval, paper decision, position, trade event, trade audit, episode, or
memory window was created; foreign-key and integrity checks pass; all
forbidden-capability deltas are zero. No BUY/SELL/HOLD, no PnL, no wallet/keys/
signing/funds, no paid API, no scoring/ranking/confidence/weighted logic, no
embeddings/vectors, no Source Governor or Central Scheduler bypass. No FULL_PILOT,
lifecycle, memory, retrieval, decisions, positions or financial work ran in this
lane. All source execution was governed and recorded.

## Readiness for the next continuous full-pilot session

- **Correctness:** ready — the direct migration channel supplies confirmed
  graduated candidates that satisfy the E.41 graduation-only selection contract
  (exact mint, confirmed PumpSwap graduation, valid post-graduation market
  identity), and persistence + export are wired.
- **Productivity:** a fresh full-pilot session can now obtain real graduated
  candidates by running direct migration discovery (bounded, multi-round, with
  settle) before selection, instead of blocking on empty graduated supply. Live
  supply rate is market-dependent; two candidates were reliably obtainable within
  bounded windows in this session.
- **Exact next action (operator):** authorize a full-pilot session that seeds the
  graduated registry via direct migration discovery, then runs the E.41 graduation-
  only selection + lifecycle. Trending/top channel adoption (BL-41-04) remains a
  separate optional lane.

## Permanent locks preserved

Solana-only; Solana memecoin-only; paper-only; no wallet/keys/signing/funds/
execution; no paid APIs; no scoring/ranking/confidence/weighted decisions; no
embeddings/vectors; no Source Governor or Central Scheduler bypass; 5m support-only;
no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/trade events/paper
audits/PnL; no FULL_PILOT/lifecycle/memory in this lane; no V2-9.7F / V2-9.8 or
later work.
