# Printer V1 V2-9.8B Restored Operational Factory Live-Source Contract and Preflight Readiness Review

Date: 2026-07-30

## Verdict

`V2_9_8B_RESTORED_FACTORY_LIVE_SOURCE_AND_PREFLIGHT_READINESS_BLOCKED`

The restored ordinary `run` path is **not ready for an operator-authorized live
campaign**.

The repository, authoritative database, process state, backup target, disk
capacity, dependency installation, fixed two-token policy, Scheduler/Governor
boundaries, and locked-capability baseline pass the permitted read-only
preflight. The terminal BLOCKED verdict is caused by current official
live-source contracts:

1. PumpPortal now documents its WebSocket as requiring an API key. The only
   documented key-creation path found creates a linked Lightning wallet and
   exposes a private key. The active code uses a keyless WebSocket URL, and the
   V1 policy prohibits adopting the documented wallet/private-key path.
2. Jupiter's current migration contract replaces `lite-api.jup.ag` with
   keyless `api.jup.ag` access. The mandatory paper-quote adapter still calls
   `lite-api.jup.ag`.
3. Solana's current public-cluster documentation publishes
   `https://api.mainnet.solana.com`; the active PumpSwap verifier and conditional
   holder source use the undocumented legacy hostname
   `https://api.mainnet-beta.solana.com`.
4. The local zero-source contract preflight does not cover the mandatory
   PumpPortal, PumpSwap, DexScreener fresh-profile/token-batch, CoinGecko, or
   Jupiter dependencies. It also embeds the legacy Solana hostname as its
   independent “official” value. Its local `READY` result therefore cannot
   establish current end-to-end live-source readiness.

This review did not probe any provider. It did not run the Memory Factory, a
campaign, RPC, WebSocket, N2, N7, recovery, replay, snapshot, window, memory, or
financial path. It made no runtime, provider, configuration, migration, budget,
or database change.

## 1. Authority, scope, and non-authorization

This is the separately requested documentation/read-only contract and
preflight review after:

`V2_9_8B_OPERATIONAL_FACTORY_ACTIVE_PATH_RESTORATION_PASS`

The active authority stack reviewed for this lane was:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-post-lane10-architecture-review.md`;
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-memory-growth-automation-audit.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-v2-9-final-closeout.md`;
- `docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md`;
- `docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration-closeout.md`;
- `docs/printer-v1-assistant-active-build-order-anchor.md`; and
- `docs/printer-v1-python-builder-guide.md`.

The restoration remains offline-only until a later explicit authorization.
This review does not authorize:

- the published `run` command or any live campaign;
- any provider, RPC, WebSocket, or source smoke call;
- API-key, wallet, account, funding, or paid-tier acquisition;
- a source endpoint or authentication repair;
- a preflight, budget, Scheduler, Governor, runner, or configuration repair;
- N2, N7, candidate-acquisition, cursor, recovery, or retry work;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- live execution, signing, wallets, private keys, scoring, ranking, confidence,
  weighted logic, embeddings, or vectors.

## 2. Exact starting state

| Gate | Required | Observed | Result |
| --- | --- | --- | --- |
| repository | `/Users/Dtwo1/Developer/MoneyPrinter` | exact path | PASS |
| branch | `master` | `master` | PASS |
| HEAD | `6e085ff67e45914b223abfa3523f2c3bde2a7ce7` | exact match | PASS |
| tracked tree | clean | clean | PASS |
| authoritative DB | `data/printer_v1.sqlite3` | exact resolved target | PASS |
| DB SHA-256 | `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6` | exact match | PASS |
| SQLite sidecars | none | no WAL/SHM/journal | PASS |
| Printer processes | zero | zero matched processes | PASS |

The restored implementation is already on `master`; no branch switch,
cherry-pick, merge, rebase, reset, or source edit was needed or authorized.

## 3. Mandatory source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION:
EXTERNAL_PROVIDER_CONTRACT_DRIFT_AND_INCOMPLETE_LOCAL_PREFLIGHT_COVERAGE

EVIDENCE:
The ordinary run graph was traced from the published wrapper and registered
entry point before evaluating source contracts. Its mandatory intake uses a
PumpPortal migration WebSocket without an API key. Its mandatory pre-close
paper-realism bundle uses Jupiter's lite-api hostname. Its mandatory PumpSwap
verification and conditional holder fallback use the legacy Solana public-RPC
hostname. Current official provider documentation no longer supports those
three exact configurations.

OFFICIAL-SOURCE COMPARISON:
PumpPortal documents an API-key query parameter for the data WebSocket and
documents a wallet/private-key-producing key setup. Jupiter documents keyless
access on api.jup.ag replacing lite-api.jup.ag. Solana documents
api.mainnet.solana.com as the public mainnet endpoint.

PRINTER-CONTRACT COMPARISON:
V1 prohibits wallets, private keys, funding, paid dependencies, live execution,
and unreviewed provider/configuration changes. The lane requires every mandatory
and conditional source contract to be current before a run. The local preflight
must fail closed rather than report full source readiness from a partial static
comparison.

ROOT CAUSE:
Provider contracts changed after the embedded runtime/preflight contracts were
frozen, and the consolidated preflight covers only a subset of the actual
ordinary-run dependency graph.

CODE CHANGE JUSTIFIED:
NOT DECIDED BY THIS LANE. Source/configuration and preflight repairs require a
separately authorized source-grounded repair investigation and design. The
PumpPortal authentication model must first be resolved without violating V1.

MINIMUM SAFE RESPONSE:
Return BLOCKED, document exact drift and coverage gaps, preserve the
authoritative DB byte-for-byte, and do not probe, repair, or run.

UNTOUCHED SCOPE:
Python, configuration, providers, source budgets, migrations, authoritative DB,
Scheduler, Source Governor, runtime, credentials, campaign artifacts, and all
retrieval/financial capabilities.

AUTHORIZATION STATUS:
Documentation/read-only inspection only.

NEXT ROADMAP-COMPLIANT STEP:
Operator review of this terminal BLOCKED closeout only.
```

## 4. Exact ordinary `run` dependency graph

### 4.1 Public command, preflight, and ownership

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
-> .venv/bin/python
-> printer_v1.operator_cli.operational_memory_factory_command
-> main
-> mode run
-> run_operational_campaign
-> _NORMAL_CAMPAIGN_POLICY
-> _run_operational_campaign
-> build_activation_preflight                 [zero source, read-only]
-> operational_backup_restore_preflight       [would write only during run]
-> campaign supervision + heartbeat owner
-> AuthoritativeLiveOperationalCampaignOwner.run_operational
```

The console registration remains:

```text
printer-run-v2-9-8-memory-factory
-> printer_v1.operator_cli.operational_memory_factory_command:main
```

The repository-local `.venv` does not contain an installed console-script
shim. This is not a blocker because the committed PowerShell wrapper uses the
registered module directly through `.venv/bin/python -m ...`, and that exact
module/help/preflight path is available.

### 4.2 Candidate supply and selection

Ordinary `run` always constructs a PumpPortal migration transport and passes it
to the canonical owner:

```text
PumpPortal WebSocket subscribeMigration
-> Source-Governed migration request
-> bounded migration event normalization
-> Solana RPC getTransaction(migration signature)
-> Solana RPC getMultipleAccounts(transaction account keys)
-> exact PumpSwap program owner equality
-> exact PumpSwap Pool.base_mint equality at the current Anchor layout offset
-> durable graduated-candidate registry
-> DexScreener latest token profiles
-> DexScreener token batch for exact Solana mint/pair facts
-> exact graduated-market floor and tracking feasibility
-> exact-pair DexScreener liquidity evidence
-> fixed categorical eligibility
-> exactly two identities
-> atomic two-slot tracking handoff
```

The current supply policy is bounded:

- three migration collection rounds;
- up to four events per WebSocket transport collection;
- at most five verification candidates;
- six-second settle and one transient re-verification boundary;
- a six-candidate front-door ceiling;
- no automatic campaign retry or successor.

### 4.3 Holder/readiness boundary

For each bounded candidate:

```text
GoPlus Solana token security
-> holder concentration present?
   -> yes: retain GoPlus evidence
   -> no: Solana getTokenLargestAccounts + getTokenSupply(finalized)
          -> eligible transient primary failure only:
             Helius Free same two RPC methods, one backup attempt
-> exact-pair market readiness
-> two-token activation or honest pre-lifecycle safe stop
```

GoPlus absence, incomplete holder evidence, a source failure, identity
mismatch, unsupported pool ownership, or insufficient supply fails closed; it
does not authorize a weaker candidate.

### 4.4 Main 15m lifecycle

```text
Central-Scheduler-led exact-pair snapshot jobs
-> DexScreener exact-pair snapshot
   -> eligible transient failure only:
      one governed GeckoTerminal exact-pool fallback
-> conditional support-only 5m evidence
-> mandatory pre-close bundle:
   CoinGecko broad market context
   GoPlus token safety
   Jupiter paper ENTRY quote (WSOL -> exact mint)
   Jupiter paper EXIT quote (exact mint -> WSOL)
   conditional Solana/Helius holder evidence when GoPlus holder data is unknown
-> closing exact-pair snapshot
-> WINDOW_15M close/audit/episode/report
-> cooldown/archive/rotation
-> terminal cleanup and zero-source report replay capability
```

All live requests in this path are intended to enter through the Source
Governor, and lifecycle work is intended to enter through the Central
Scheduler. No independent provider loop was found in the ordinary path.

### 4.5 Constructed but dead for ordinary `run`

`_run_operational_campaign` constructs:

- `OneShotUrllibPumpTransport(FREE_PUBLIC_SOLANA_RPC)`; and
- `OneShotUrllibSecondaryTransport()`.

Because ordinary `run` also always supplies `migration_transport`,
`run_operational` sets `graduation_native_only=True`. That branch deliberately
skips:

- direct Pump create-index/origin acquisition through the Pump transport; and
- the legacy GeckoTerminal/DexScreener secondary-enrichment adapter.

The objects are constructed but do not issue a request in the ordinary
restored `run` graph. This distinction matters: the current run still depends
on PumpPortal migration location, PumpSwap on-chain verification, and the
graduated-supply DexScreener locator; it does not fall back to direct Pump
origin acquisition.

### 4.6 Registered or available but not invoked by ordinary `run`

- `solana_rpc_token_age` is not invoked. Age context is derived from the exact
  pair data, including `pairCreatedAt`; age is not an eligibility score.
- No independent SPL Token or Token-2022 mint-owner RPC validation was found in
  the ordinary restored graph. Exact mint identity is enforced through the
  PumpPortal event, PumpSwap pool owner/base-mint check, and exact-pair
  aggregator equality. SPL Token/Token-2022 official-contract review is
  therefore not an invoked live-source dependency of this command.
- GeckoTerminal OHLCV/trade adapters remain registered and included in the
  static readiness contract, but the ordinary lifecycle traced here performs
  exact-pair GeckoTerminal fallback through the pair snapshot path. The
  registered OHLCV/trade request kinds do not become an independent main-memory
  path.
- Candidate-acquisition N2/N7, global Pump cursor, recovery, and migration
  observation remain deferred and are not read or advanced.

## 5. Official live-source contract review

Official contracts were reviewed on 2026-07-30. No endpoint was called.

| Source/contract | Ordinary-run role | Current code/config | Current official contract | Result |
| --- | --- | --- | --- | --- |
| Pump program | deterministic bonding-curve PDA context | program `6EF8...F6P`; seeds `bonding-curve`, mint | official program and PDA seeds match | PASS |
| PumpPortal | mandatory migration locator | `wss://pumpportal.fun/api/data`; `subscribeMigration`; no key | official WebSocket includes `?api-key=...`; migration events are free, but an API key is still documented | **BLOCKED** |
| PumpSwap | mandatory exact graduation/pool identity | program `pAMM...XEA`; owner equality; base mint at offset 43 | official program matches; Pool fields begin bump, index, creator, base mint, so the base-mint offset remains 43 | PASS |
| Solana public RPC | mandatory PumpSwap verification; conditional holder source | `https://api.mainnet-beta.solana.com` | current public-cluster documentation publishes `https://api.mainnet.solana.com` | **BLOCKED** |
| Solana RPC methods | mandatory/conditional | `getTransaction`, `getMultipleAccounts`, `getTokenLargestAccounts`, `getTokenSupply`; read-only | official method shapes support these read operations; unsupported/null responses fail closed | PASS apart from endpoint |
| DexScreener | mandatory fresh-profile/token-batch locator, exact-pair liquidity, main snapshots | public endpoints, no key; local ceilings below 60/300 RPM | official profile endpoint is 60 RPM; tokens batch supports up to 30 addresses at 300 RPM; exact-pair endpoint is 300 RPM; response fields align | PASS |
| GeckoTerminal | conditional exact-pair fallback | public API v2, versioned Accept header; local ceiling 10 RPM | official public beta is keyless; current public ceiling is 30 RPM; local 10 RPM is conservative | PASS |
| GoPlus | mandatory safety/holder evidence | keyless Solana token-security endpoint; local 20 RPM | official API is free at 30 RPM; higher limits may use an access token | PASS |
| Helius Free | conditional holder backup | fixed mainnet host plus redacted query API key; local 10 RPS cap | official endpoint/auth shape matches; free tier is available; limits vary by plan | PASS for offline contract/config presence |
| CoinGecko | mandatory pre-close broad context | keyless `/api/v3/simple/price` | current keyless public root and example include this endpoint; dynamic IP throttling applies | PASS |
| Jupiter | mandatory ENTRY and EXIT paper-realism quotes | `https://lite-api.jup.ag/swap/v1/quote`; no key | current migration contract replaces Lite with keyless `api.jup.ag` at 0.5 RPS; current v1 quote docs use `api.jup.ag`; v1 is no longer actively maintained | **BLOCKED** |
| token-age registry | not invoked | no ordinary-run call | not applicable to this graph | NOT ACTIVE |
| SPL Token / Token-2022 RPC owner validation | not invoked | no ordinary-run call | not applicable to this graph | NOT ACTIVE |

### 5.1 Primary official sources

- Pump program and PDA:
  [Pump official program README](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md)
- PumpSwap program and Pool layout:
  [PumpSwap official program README](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md) and
  [official Pump AMM IDL](https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump_amm.json)
- PumpPortal:
  [real-time data contract](https://pumpportal.fun/data-api/real-time/),
  [fees](https://pumpportal.fun/fees/), and
  [API-key setup](https://pumpportal.fun/trading-api/setup/)
- Solana:
  [clusters and public RPC endpoints](https://solana.com/docs/references/clusters),
  [getTransaction](https://solana.com/docs/rpc/http/gettransaction),
  [getMultipleAccounts](https://solana.com/docs/rpc/http/getmultipleaccounts),
  [getTokenLargestAccounts](https://solana.com/docs/rpc/http/gettokenlargestaccounts), and
  [getTokenSupply](https://solana.com/docs/rpc/http/gettokensupply)
- DexScreener:
  [official API reference](https://docs.dexscreener.com/api/reference)
- GeckoTerminal:
  [public API introduction](https://apiguide.geckoterminal.com/),
  [authentication](https://apiguide.geckoterminal.com/authentication), and
  [rate-limit FAQ](https://apiguide.geckoterminal.com/faq)
- GoPlus:
  [Solana token-security reference](https://docs.gopluslabs.io/reference/solanatokensecurityusingget) and
  [free API/rate-limit support contract](https://docs.gopluslabs.io/reference/support)
- Helius:
  [authentication](https://www.helius.dev/docs/api-reference/authentication) and
  [quickstart/free tier](https://www.helius.dev/docs/quickstart)
- CoinGecko:
  [keyless public API](https://docs.coingecko.com/docs/keyless-public-api)
- Jupiter:
  [Developer Platform migration](https://developers.jup.ag/docs/portal/migration) and
  [v1 quote guide](https://developers.jup.ag/docs/swap/v1/get-quote)

## 6. Terminal blockers

### B-01 — PumpPortal authentication conflicts with the active contract

The mandatory runtime URL is:

```text
wss://pumpportal.fun/api/data
```

The current official data page publishes:

```text
wss://pumpportal.fun/api/data?api-key=your-api-key-here
```

It marks `subscribeMigration` as free, so the issue is not a per-event payment.
However, the current setup page's API-key flow generates a linked Lightning
wallet, exposes a wallet private key, and then describes funding that wallet.
The active source stack permits PumpPortal only as a free/keyless migration
locator and explicitly prohibits wallet, private-key, funding, paid fallback,
and metered account/trade-stream behavior.

No approved V1-compatible PumpPortal authentication path was established. No
key was generated, requested, stored, or tested. This mandatory intake source
alone requires the terminal BLOCKED verdict.

### B-02 — Jupiter mandatory quote hostname is stale

The ordinary pre-close bundle always asks for an ENTRY and EXIT paper quote.
The adapter calls:

```text
https://lite-api.jup.ag/swap/v1/quote
```

Jupiter's current migration documentation says keyless access now uses
`api.jup.ag` at 0.5 RPS and replaces `lite-api.jup.ag`. The current v1 quote
guide also uses `api.jup.ag` and warns that Metis Swap API v1 is no longer
actively maintained.

A free/keyless current host appears to exist and is compatible in principle
with V1's no-paid-dependency rule, but changing the endpoint, pacing, response
contract, or version is a code/configuration repair outside this lane. The
mandatory quotes therefore remain BLOCKED.

### B-03 — Solana public-RPC hostname is not current documented configuration

The active PumpSwap verifier and conditional holder adapter use:

```text
https://api.mainnet-beta.solana.com
```

The current official clusters page publishes:

```text
https://api.mainnet.solana.com
```

This lane prohibited a live probe and required current official documentation
to prove the contract. The legacy hostname may not be treated as proven merely
because it existed historically or may still resolve as an alias. PumpSwap
verification is mandatory, so this unresolved exact endpoint contract is a
blocker.

The current official public endpoint is rate-limited and is not intended for
production-grade reliability. A bounded, paper-only operation may still be
compatible with it, but that suitability and any endpoint change require a
separate authorized review.

### B-04 — Local source preflight gives a false-complete readiness signal

`build_readiness_source_contract_preflight()` covers:

- GoPlus;
- Solana RPC holder calls;
- Helius holder backup;
- DexScreener exact-pair snapshot; and
- GeckoTerminal readiness/OHLCV/trades.

It does not cover these ordinary-run dependencies:

- PumpPortal migration WebSocket and authentication;
- Pump/PumpSwap current program/layout contract;
- PumpSwap `getTransaction`/`getMultipleAccounts` verification transport;
- DexScreener latest-profile and token-batch locator;
- CoinGecko broad market context; or
- Jupiter ENTRY/EXIT paper quotes.

Its `_OFFICIAL_CONFIGURATION` also embeds
`https://api.mainnet-beta.solana.com`, so it compares the runtime against a
stale local literal rather than proving the current official Solana contract.

Consequently:

```text
source_contract.status=READY
```

means only that a partial set of runtime constants matches a partial set of
embedded literals. It is not an end-to-end live-source readiness verdict. A
live campaign must not be authorized from that result.

## 7. Redacted environment and dependency review

No secret value was printed or recorded.

| Item | Result |
| --- | --- |
| `PRINTER_HELIUS_API_KEY` present | yes |
| minimum structural length | pass |
| allowed structural character set | pass |
| obvious placeholder marker | none |
| key validity/provider plan | not network-verified by this lane |
| PumpPortal key variable/path in active runtime | none |
| Jupiter key variable/path in active runtime | none |
| `websockets` import | pass |
| installed `websockets` version | `16.1.1` |
| required minimum | `12.0` |
| package root | exact repository `src/printer_v1` |
| external requests made by dependency preflight | `0` |

The Helius key is a conditional backup credential, not authority to call
Helius. Its presence does not cure the mandatory PumpPortal, Jupiter, or Solana
configuration blockers.

## 8. Database, process, backup, and disk preflight

### 8.1 Authoritative database

| Check | Observed | Result |
| --- | --- | --- |
| size | `64,827,392` bytes | below `67,108,864`-byte storage ceiling |
| SHA-256 | exact required hash | PASS |
| migration count | `49` | PASS |
| latest migration | `049_candidate_acquisition_integration.sql` | PASS |
| `PRAGMA integrity_check` | `ok` | PASS |
| foreign-key violations | `0` | PASS |
| WAL/SHM/journal sidecars | none | PASS |

### 8.2 Active operational state

Independent immutable/read-only SQL checks returned:

| State | Count |
| --- | ---: |
| active campaign runs | 0 |
| active campaign supervision | 0 |
| active campaigns | 0 |
| pending/running discovery work | 0 |
| active factory steps | 0 |
| locked/running Scheduler jobs | 0 |
| active proof supervision | 0 |
| active candidate-acquisition integrations | 0 |
| active candidate-acquisition leases | 0 |

The process-list check found zero Printer/Memory Factory processes.

### 8.3 Backup target and capacity

The actual `run` path would create an execution-specific root under:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8
```

Static/read-only checks established:

- the artifact root and parent exist;
- both are owned by the current operator;
- the authoritative DB and artifact root are on device `16777233`;
- the filesystem has approximately `842 GiB` available at 7% capacity;
- the 64.8 MB DB is far below available capacity; and
- the backup code retains copy, SHA-256 equality, disposable restore,
  canonical migration, and atomic publish checks.

The backup preflight was not executed because an actual backup/restore
preflight creates directories and files. That mutation was prohibited by this
lane. Static path/device/capacity readiness passes; the source-contract verdict
blocks before any campaign authorization.

## 9. Scheduler, Source Governor, pacing, and budget review

The exact ordinary graph retains:

- Source-Governed source request construction and persistence;
- Central-Scheduler-led lifecycle work;
- campaign supervision and heartbeat ownership;
- one campaign/one cycle;
- fixed token capacity `2`;
- no automatic retry, restart, or successor;
- request pacing outside SQLite write transactions;
- exact-pair identity and source-response provenance;
- failure-preserving conditional fallbacks; and
- terminal cleanup/replay boundaries.

Local zero-source budget preflight returned `READY`:

| Budget | Ceiling/reservation |
| --- | ---: |
| admission operations | 45 |
| discovery requests | 2 |
| governed 15m requests | 65 |
| governed requests per token | 21 |
| Scheduler rows | 51 |
| failures | 20 |
| storage bytes | 67,108,864 |
| holder worst-case operations | 5 |
| reserved snapshot operations | 2 |
| reserved snapshot completion operations | 4 |
| zero-transport validation operations | 9 |

Provider comparison:

- DexScreener pacing is below official profile and pair ceilings.
- GeckoTerminal's local 10 RPM ceiling is below the current 30 RPM public
  ceiling.
- GoPlus's local 20 RPM ceiling is below the official free 30 RPM ceiling.
- Helius is conditionally paced below the locally adopted free limit, although
  the credential's exact account plan was not probed.
- CoinGecko's keyless pool has dynamic IP throttling, so only bounded fail-closed
  use is supportable; no fixed public allowance can be assumed.
- Jupiter's current keyless contract is 0.5 RPS. The active adapter is on the
  wrong hostname, so pacing compatibility must be re-qualified with any future
  endpoint repair.
- PumpPortal requires one WebSocket at a time. The current bounded transport
  does not create per-token sockets, but its missing supported authentication
  still blocks it.
- Solana public limits are mutable and the public service is not advertised for
  production-grade reliability. The exact official endpoint must first be
  adopted/reviewed.

The local budget result is necessary but not sufficient. It cannot override
endpoint or authentication drift.

## 10. Timeframe and capability locks

The preflight policy remains:

| Capability | State |
| --- | --- |
| active token capacity | exactly 2 |
| main window | `WINDOW_15M` |
| 5m | support-only |
| `WINDOW_1H` | locked in ordinary `run` |
| `WINDOW_4H` | locked |
| `WINDOW_12H` | locked |
| `WINDOW_24H` | locked |
| automatic retries | 0 |
| restart/successor creation | false |
| candidate acquisition N2/N7/cursor authority | deferred, false |
| retrieval matches | 0 |
| paper positions | 0 |
| paper trade events | 0 |
| paper trade audits | 0 |

The preserved historical baseline includes 10 retrieval-query rows, 2 paper
decision rows, and 1 null-position paper-audit report, exactly as required by
the existing activation preflight. This lane created none and did not interpret
them as active authority.

## 11. Checks performed

All checks were read-only or documentation-only:

- exact branch, HEAD, merge ancestry, and clean-worktree checks;
- authoritative DB SHA-256 before documentation;
- SQLite sidecar scan;
- process-list scan;
- static active source-stack review;
- exact public `run` call-graph trace;
- Source Governor, Central Scheduler, pacing, timeframe, and fallback trace;
- current official provider documentation review;
- redacted environment structure check;
- `websockets` dependency/version check;
- module `--help`;
- module `preflight-only` with `source_calls=0`,
  `scheduler_runtime_calls=0`, and `database_writes=0`;
- immutable/read-only SQLite integrity, migration, foreign-key, active-state,
  lease, integration, and locked-capability checks;
- backup-root existence, device, ownership, DB size, and free-space checks; and
- diff/status review.

No provider request, RPC, WebSocket, campaign, proof, replay, runner, snapshot,
window, memory, N2, N7, recovery, or financial command ran.

## 12. Pass/fail matrix

| Gate | Result |
| --- | --- |
| exact repository/branch/HEAD | PASS |
| clean starting tree | PASS |
| exact authoritative DB hash | PASS |
| DB integrity/migrations/FKs | PASS |
| zero sidecars/processes/active work/leases | PASS |
| backup path/device/capacity static readiness | PASS |
| runtime dependency installation | PASS |
| fixed two-token, 15m-only ordinary policy | PASS |
| Source Governor/Central Scheduler ownership | PASS |
| local static budget arithmetic | PASS |
| locked retrieval/financial baseline | PASS |
| Pump/PumpSwap program and layout contract | PASS |
| DexScreener contract | PASS |
| GeckoTerminal conditional contract | PASS |
| GoPlus contract | PASS |
| Helius conditional offline configuration | PASS |
| CoinGecko keyless contract | PASS |
| PumpPortal mandatory authentication contract | **BLOCKED** |
| Jupiter mandatory quote endpoint contract | **BLOCKED** |
| Solana mandatory public-RPC endpoint contract | **BLOCKED** |
| complete current-source preflight coverage | **BLOCKED** |
| operator-authorized live campaign readiness | **BLOCKED** |

## 13. Functionality Risks / Setbacks / Efficiency Blockers

1. **PumpPortal has no approved V1-compatible current auth contract.** The
   documented API-key setup crosses the wallet/private-key boundary. Treating
   free migration events as keyless would contradict the current connection
   examples and fee notice.
2. **A locally green preflight can mask mandatory-source drift.** Its coverage
   and independent contract literals are incomplete. This is the highest
   operational false-readiness risk.
3. **Jupiter v1 is aging in addition to the hostname drift.** A hostname-only
   edit may be insufficient if the current response, pacing, availability, or
   successor API contract changes.
4. **Solana public RPC is a best-effort public service.** Even after exact
   hostname review, rate limits and availability can change without notice.
5. **Helius credential validity was not live-tested.** The secret is present and
   structurally non-placeholder, but this lane cannot prove account state or
   plan limits.
6. **CoinGecko keyless limits are dynamic.** The bounded campaign must continue
   to fail closed on throttling rather than adding paid fallback.
7. **Constructed dead transports obscure the real graph.** Direct Pump and
   legacy secondary transports are instantiated but skipped under
   `graduation_native_only`; future reviews can misclassify them as active
   dependencies unless the branch condition is traced.
8. **No active SPL mint-owner validation was found in this graph.** This review
   does not convert that observation into a new gate or authorize an
   implementation; it is retained as exact scope evidence.

## 14. Files changed

- `docs/printer-v1-v2-9-8b-restored-factory-live-source-contract-and-preflight-readiness-review.md`

No active pointer needed modification. The active lane remains V2-9.8B, and the
restoration's operator-review-only boundary remains in force.

## 15. What was built

A documentation-only, source-grounded terminal readiness review that:

- traces the exact ordinary `run` dependency graph;
- distinguishes mandatory, conditional, constructed-dead, and dormant sources;
- compares each invoked source against current official documentation;
- audits redacted environment, DB, process, backup, disk, Scheduler, Governor,
  pacing, budget, timeframe, and locked-capability state; and
- returns an exact terminal BLOCKED verdict without probing or repairing.

## 16. What was not touched

- Python or tests;
- source/provider configuration or endpoint constants;
- environment variables or secrets;
- source budgets, rate limits, Scheduler, or Source Governor;
- migrations or database contents;
- Memory Factory runtime or artifacts;
- active roadmap/policy pointers;
- candidate acquisition, N2, N7, cursors, recovery, or provider/RPC code;
- retrieval, paper decisions, positions, trades, audits, PnL, or live execution.

## 17. Pass/fail status

**FAIL / BLOCKED**

Exact terminal status:

`V2_9_8B_RESTORED_FACTORY_LIVE_SOURCE_AND_PREFLIGHT_READINESS_BLOCKED`

## 18. Exact next permitted task

**Operator review of this BLOCKED review and its redacted evidence only.**

This verdict does not authorize a provider probe, API-key or wallet setup,
endpoint repair, preflight repair, new design/implementation lane, retry,
campaign, N2, N7, cursor/recovery action, or successor task.
