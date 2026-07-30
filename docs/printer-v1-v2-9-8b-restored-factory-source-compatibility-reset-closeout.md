# Printer V1 V2-9.8B Restored Factory Source Compatibility Reset Closeout

Date: 2026-07-30

Lane: `V2-9.8B Restored Factory Source Compatibility Reset`

Verdict: `V2_9_8B_RESTORED_FACTORY_SOURCE_COMPATIBILITY_RESET_PASS`

## Scope and work gate

This closeout covers the single operator-authorized sequence:

```text
source-boundary confirmation
-> replacement design
-> complete implementation
-> frozen offline proof
-> closeout
```

The work began on `master` at exact clean HEAD
`e54ce92aef59d0c9edd2266f69e3572d4b084c97`. The authoritative database
`data/printer_v1.sqlite3` retained SHA-256
`e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`.
No provider, RPC, WebSocket, Memory Factory, N2, N7, recovery, tracking,
snapshot, window or memory operation was run against that database. The proof
used frozen transports and disposable migration-049 databases only.

The Python Builder Guide investigation classified the four failures as
`CONTRACT_DRIFT`: PumpPortal's current authentication contract conflicts with
Printer's wallet/key/funding locks, Jupiter and public Solana endpoint
assumptions were stale, and preflight represented only part of the ordinary
runtime graph. Code change was therefore justified and remained limited to the
source-compatibility boundary.

## PumpPortal removal boundary

PumpPortal has no import, construction, secret, authentication, wallet, funding,
stream or fallback path in ordinary `operational-memory-factory run`.
`operational_memory_factory_command.py` now constructs the direct Solana
transport and passes it to the restored front door. The front door and
`direct_migration_discovery.py` accept exactly one collection round, zero
settling time and no automatic re-verification.

Historical PumpPortal code, contract documentation and evidence remain present
only for deferred/historical reproduction. They are not runtime authority.
No PumpPortal API key was requested or added; no linked wallet, private key,
funding, paid/metered stream or silent fallback exists.

## Replacement locator architecture

```text
Central Scheduler ordinary run
  -> Source Governor: one finalized Pump-program signature page
  -> Source Governor: bounded finalized transaction lookups
  -> pinned Pump migrate instruction/account decoder
  -> governed PumpSwap transaction/account reads
  -> exact Pump/PumpSwap program, PDA, owner, layout, pool and mint join
  -> existing graduated-candidate registry
  -> existing exact-pool eligibility and two-token selection
  -> existing two-token/two-pair WINDOW_15M lifecycle
```

The new adapter is a stateless, newest-first live-tail observation. It requests
one page of at most 12 signatures and at most 12 transactions, with explicit
`finalized` commitment. Every governed request performs exactly one RPC
operation. It has no cursor, continuity, recovery, backfill or generic candidate
admission interface. It makes no historical completeness claim and cannot
reactivate the deferred candidate-acquisition subsystem.

The exact verification path reuses the pinned Pump/PumpSwap program IDs, IDL
hashes, migration discriminator/account order, PDA derivations, pool
discriminator/layout, account owner, base mint, quote mint, vault and LP mint
checks. The locator adapter, shared source registry and complete preflight are
new. The graduated registry, eligibility policy, liquidity front door,
two-token selector, tracking, lifecycle, audit, report and replay owners remain
the existing restored path.

## Jupiter and Solana contract reset

Jupiter remains keyless and paper-quote-only at
`https://api.jup.ag/swap/v1/quote`, paced locally at 30 requests/minute
(0.5 RPS) with zero automatic retry. The adapter now reconciles exact input and
output mint identities, input amount, slippage, positive output and threshold
amounts, finite non-negative price impact, non-empty route topology, hop
identity/amount continuity and exact route allocation. Entry and exit use the
same strict parser with reversed identities. Null, malformed, throttled, error,
wrong-mint, wrong-amount, wrong-slippage and contradictory routes fail closed.
No build, swap, transaction, signing or execution endpoint was introduced.

`PRINTER_SOLANA_RPC_URL` is an optional approved endpoint override. It must be
absolute HTTPS with a hostname, no user-info or fragment, and no placeholder
value. Diagnostics reveal only scheme/host/port and the presence of a path or
query; credentials and private URL details are not printed. With no override,
the explicitly bounded free/public fallback is
`https://api.mainnet.solana.com`. Required transaction/account reads preserve
explicit finalized commitment and strict JSON-RPC response validation. Helius
remains only the existing conditional governed holder-evidence backup.

## Complete ordinary-run preflight matrix

| Dependency | Classification | Authentication / environment | Adopted contract / pacing | Failure effect |
|---|---|---|---|---|
| Direct Pump migration locator | MANDATORY | keyless; validated optional `PRINTER_SOLANA_RPC_URL` | Pump pin; one finalized page plus bounded transactions; 30/min | blocks before lifecycle or honest insufficient-supply stop |
| Pump program contract | MANDATORY | none | pinned program, IDL hash, migrate discriminator/accounts | blocks preflight |
| PumpSwap exact join | MANDATORY | governed Solana RPC | pinned AMM, IDL, pool layout, PDA and mint join | blocks candidate |
| Solana transaction/account verification | MANDATORY | approved HTTPS override or official bounded fallback | exact JSON-RPC/finalized; 30/min | blocks locator or candidate |
| DexScreener latest profiles | MANDATORY | keyless | current profiles contract; 60/min | blocks discovery nomination |
| DexScreener token batch | MANDATORY | keyless | current Solana token-batch contract; 60/min | blocks candidate supply |
| DexScreener exact pair | MANDATORY | keyless | current exact-pair contract; 60/min | governed exact-pair fallback may apply only on eligible failure |
| GeckoTerminal exact pair / 15m | CONDITIONAL | keyless | API v2/version header; 10/min | fallback failure blocks candidate or dirties window |
| GoPlus safety | CONDITIONAL | keyless | Solana token-security v1; 20/min | explicit risk blocks; unavailable evidence stays unknown |
| Solana holder evidence | CONDITIONAL | governed Solana RPC | finalized largest-accounts and supply; 30/min | eligible transient failure may use Helius |
| Helius holder backup | CONDITIONAL | `PRINTER_HELIUS_API_KEY` only when selected | fixed HTTPS host; 30/min; zero retry | missing backup cannot hide mandatory failure |
| CoinGecko context | MANDATORY | keyless | public API v3; 20/min | context fails closed / window dirty |
| Jupiter entry and exit quotes | MANDATORY | keyless | quote v1 exact-response contract; 30/min | paper-realism evidence fails closed |
| PumpPortal | DEFERRED | prohibited in ordinary run | no active endpoint | no fallback |
| Candidate acquisition / cursor / recovery | DEFERRED | not applicable | historical/importable only | no runtime authority |
| Alternative.me / DefiLlama | DORMANT | keyless | registered broad-context contracts | not in ordinary graph |

For each row the zero-I/O preflight reports classification, authentication,
environment state, redacted endpoint/transport, free/public compatibility,
request/response version, pacing, budget and failure effect. The same shared
contract registry supplies runtime and preflight constants. A missing or
drifted mandatory contract, malformed required environment value, incomplete
active graph, owner bypass, constant disagreement, or wallet/key/funding/paid
marker makes the result non-READY. Conditional absence remains visible and
cannot erase mandatory failure.

## Files changed

Documents:

- `docs/printer-v1-v2-9-8b-restored-factory-source-compatibility-reset-design.md`
- `docs/printer-v1-v2-9-8b-restored-factory-source-compatibility-reset-closeout.md`
- `docs/solana-builder-source-of-truth/pumpportal-api-contract.md`
- `docs/solana-builder-source-of-truth/solana-core-rpc-reference.md`
- `docs/solana-builder-source-of-truth/pump-fun-bonding-curve-protocol.md`
- `docs/solana-builder-source-of-truth/pumpswap-pool-confirmation-contract.md`
- `docs/solana-builder-source-of-truth/jupiter-route-quote-api-contract.md`
- `docs/solana-builder-source-of-truth/source-governor-evidence-rules.md`

Runtime:

- `src/printer_v1/sources/operational_source_contracts.py`
- `src/printer_v1/sources/direct_pump_migration.py`
- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/readiness_source_contract_preflight.py`
- `src/printer_v1/operator_cli/durable_external_operation_log.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- `src/printer_v1/operator_cli/two_token_operational_pilot_runner.py`
- `src/printer_v1/sources/jupiter_quote.py`
- `src/printer_v1/sources/pump_contracts.py`
- `src/printer_v1/sources/pump_migration.py`
- `src/printer_v1/sources/pumpfun_origin.py`
- `src/printer_v1/sources/pumpswap.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/sources/coingecko.py`
- `src/printer_v1/sources/dexscreener.py`
- `src/printer_v1/sources/geckoterminal.py`
- `src/printer_v1/sources/geckoterminal_15m.py`
- `src/printer_v1/sources/goplus.py`
- `src/printer_v1/sources/helius_holder.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/sources/solana_rpc_token_age.py`

Tests:

- `tests/test_v2_9_8b_restored_factory_source_compatibility_reset.py`
- `tests/test_v2_9_7e_28_readiness_contract_preflight.py`
- `tests/test_post_rc_real_evidence_collection.py`
- `tests/test_v2_9_7e_14_two_token_operational_pilot_runner.py`
- `tests/test_v2_9_7e_33_canonical_readiness_boundary.py`
- `tests/test_v2_9_8b_5_7_discovery_productivity.py`

## Frozen offline proof

1. **PumpPortal absent:** source inspection and the focused ordinary-runtime
   test prove no PumpPortal import or construction in the ordinary graph.
2. **No prohibited PumpPortal path:** focused tests reject the presence of
   PumpPortal keys, wallet/private-key/funding fields, paid transport or
   fallback construction.
3. **Exact direct migration success:** a frozen finalized signature and
   transaction traverse the strict Pump decoder, exact PumpSwap verification
   and graduated registry on a disposable migration-049 database.
4. **Exact failure closure:** null/malformed transactions, unsupported
   instructions, wrong program, wrong pool owner/identity and wrong base mint
   are rejected without admission.
5. **Deferred state isolated:** the new adapter has no cursor/recovery/
   candidate-acquisition interface or import; disposable proof shows zero
   cursor/recovery/candidate delta.
6. **Jupiter exact entry/exit:** frozen forward and reversed quote fixtures
   reconcile mint, amount, slippage, route, allocation and impact exactly.
7. **Jupiter failures:** malformed, null, throttled and wrong-mint fixtures fail
   closed, alongside wrong-amount/slippage and contradictory route cases.
8. **Solana configuration:** official fallback and valid override resolve;
   HTTP, user-info, fragment and placeholder URLs fail; secret path/query
   details remain redacted.
9. **Graph completeness:** preflight's required active source keys equal the
   shared ordinary runtime graph.
10. **Mandatory removal:** removing or drifting each mandatory contract makes
    preflight non-READY.
11. **Conditional truth:** Helius absence is explicitly reported while the
    eligible Solana holder route remains available and cannot hide a mandatory
    failure.
12. **Shared constants:** runtime endpoint/version/pacing constants are the
    same registry objects consumed by preflight.
13. **Restored frozen lifecycle:** the existing restored-path regression still
    completes exact two-token, two-pair `WINDOW_15M` lifecycle composition.
14. **Accounting:** restored regression plus Source Governor/Scheduler boundary
    tests reconcile requests, transport operations, rows, bytes, report and
    deterministic replay. The direct migration success case reconciles three
    governed requests to four explicitly reported underlying transport
    operations (one signature page, one transaction and one two-operation
    PumpSwap verification).
15. **Candidate/cursor/recovery delta:** restored disposable-database proof
    retains zero delta for deferred subsystem tables.
16. **Retrieval/financial delta:** restored production-readiness proof retains
    zero delta for retrieval, decision, position, event, audit and PnL tables.
17. **Database integrity:** disposable databases remain at migration head 049;
    integrity, foreign-key and cleanup checks pass.

The same focused and regression proofs verify that source calls remain behind
Source Governor and scheduler ownership. The endpoint reset changes transport
compatibility only; it does not give aggregators Pump lineage authority, change
provider precedence, or create a direct source bypass.

## Verification record

Passing checks:

- final reset and complete-preflight focus: 21 passed;
- expanded reset focus after exact wrong-program/pool/base cases: 12 passed;
- reset, preflight and Jupiter-selected checks: 32 passed, 137 deselected;
- Jupiter adapter selection in the broad evidence suite: 19 passed,
  130 deselected;
- pinned Pump/PumpSwap contract selection: 1 passed, 24 deselected;
- restored path, Source Governor registry/boundary and production-readiness
  regressions: 36 passed;
- public command and pilot non-live selection: passed;
- Python compilation for `src` and `tests`: passed;
- `git diff --check`: passed.

The required broad affected `test_post_rc_real_evidence_collection.py` run
produced 146 passes and three failures. Each exact failure was reproduced
unchanged from an archive of baseline HEAD
`e54ce92aef59d0c9edd2266f69e3572d4b084c97`: an environment-selected Alchemy
RPC where an old test expects the legacy default, an existing rate-limit
`next_step_hint` wording mismatch, and an existing forbidden-word assertion
against `goplus_normalizer`. They are baseline conditions outside this lane and
do not intersect the reset proof. One canonical-readiness activation-only
expectation was likewise reproduced at baseline; graduation-only law correctly
keeps it NOT_READY without required proof inputs.

No broad unrelated suite was run.

## Money-usefulness contribution

The restored factory can now be reviewed against current free/public,
wallet-free source contracts without relying on an incompatible PumpPortal
authentication path. Exact Pump/PumpSwap identity remains the admission
authority, Jupiter paper-entry/exit realism fails closed on contradictory
quotes, and complete preflight prevents partial READY claims. This improves the
credibility of future bounded memory collection while creating no trade,
position, PnL or live-execution capability.

## Preserved locks and untouched scope

- Solana-only, memecoin-only and paper-only;
- active capacity exactly two and ordinary run `WINDOW_15M` only;
- 5m support-only;
- Source Governor and Central Scheduler ownership;
- eligibility, evidence-quality and clean/dirty policy unchanged;
- source/storage/observation ceilings unchanged except the documented
  provider-specific current pacing;
- migration head remains 049; no schema/migration change;
- zero automatic retry, restart or successor;
- candidate acquisition, N2/N7, cursors, recovery/backfill, optional-global
  observer and capacity above two remain deferred;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits,
  PnL, live execution, wallets, keys, signing, paid dependencies,
  scoring/ranking/confidence/weighted logic and vectors remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- A single stateless signature page may miss a migration outside its bounded
  live tail. It deliberately cannot backfill; insufficient supply must safe-stop.
- Solana's public fallback is bounded and rate-limited. A validated
  operator-configured approved HTTPS endpoint is preferred for a future
  explicitly authorized probe.
- Frozen fixtures establish contract composition and fail-closed behavior, not
  live provider availability or current market coverage.
- Jupiter Swap v1 quote remains suitable for read-only paper evidence but is
  described as superseded by execution-oriented v2 surfaces. Any future
  removal or response change requires another explicit source-contract review.
- Baseline test debt recorded above remains outside this lane and should not be
  hidden by future verification.

## Exact next permitted task

Operator review of the committed reset and this closeout. After that review,
only a separately explicit, bounded live source-contract probe is permitted.
This PASS does **not** authorize the Memory Factory campaign, a provider/RPC
run now, N2, N7, recovery, cursor work, tracking, snapshots, windows, memory
creation, retrieval or any financial capability.
