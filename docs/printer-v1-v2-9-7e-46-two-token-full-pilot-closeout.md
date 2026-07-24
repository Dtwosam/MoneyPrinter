# Printer V1 — V2-9.7E.46 Two-Token Full Pilot Closeout

**Verdict: `V2_9_7E_46_BLOCKED_HOLDER_EVIDENCE`.**

The canonical E.45 production path was repaired only where live preflight exposed
genuine production defects, then executed three times with fresh isolated
authorization, campaign, run, cycle, DB, artifact and immutable candidate-export
identities. No sustained lifecycle attempt began: the first execution exposed and
preserved supply-accounting defects, and the next two independently reached two
real exact-pool `$3,000+` graduated candidates but failed closed at holder evidence.
The fixed public Solana RPC returned HTTP 429 for every holder query and the fixed
Helius Free backup was unavailable because `PRINTER_HELIUS_API_KEY` was not
configured. That is an environment/provider-evidence blocker, not justification
for endpoint rotation, provider racing, hidden retries or a weakened holder gate.

- **Starting commit:** `d54d8920f46991abc5f68fdd178e8e7552c03065`
  (`Close canonical graduated supply and full-pilot repair`).
- **Ending commit:** the closeout commit containing this document
  (`Close two-token full pilot proof`; exact SHA reported by the committing task).
- **Live date:** 2026-07-24.
- **Sustained attempts consumed:** 0 of 3. All executions stopped before lifecycle
  launch, so none consumed a sustained-attempt authorization.

## Repair commits

| Commit | Classification | Narrow repair | Proof |
|---|---|---|---|
| `e86c6a2bbde5f43261c006b521cb8259fd48d33a` | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | Completed the committed E.45 owner chain in the canonical E.14 runner: migration transport, graduated supply, deterministic holder reserves, immutable `PILOT_INPUT_READY`, fresh identities and candidate-only export. | 47 focused E.14/E.44/E.45 tests + 23 activation/lifecycle regressions. |
| `18f9c6bba956ad2503eb30bfc9e4628a486b2af5` | `COMMITTED_CODE_DEFECT` | Removed irrelevant create acquisition from graduation-native supply, routed the locator through durable Source Governor accounting, preserved a bounded 2-LATEST/2-PERSISTED refresh batch, and made export identity attempt-local. | 31 focused tests + 23 activation/lifecycle regressions. |
| `08a1c9d8f7ab69203ed212a4afaa5dea519ebd3b` | `COMMITTED_CODE_DEFECT` | Made idempotent graduated-registry merge work with SQLite's default tuple row factory. | 7 focused registry tests. |

No policy, gate, source endpoint, retry ceiling, lifecycle duration, continuation
law, memory-quality rule or permanent V1 lock was weakened.

## Execution ledger

The initially prepared `attempt-1` command failed locally while decoding its
PowerShell-quoted JSON before an attempt DB or source call existed. It was corrected
as an invocation/preflight issue and did not consume an attempt.

| Execution | HEAD | Fresh identities | Immutable export | Wall clock | First terminal cause | Lifecycle |
|---|---|---|---|---:|---|---|
| `attempt-1b` | `e86c6a2bbde5f43261c006b521cb8259fd48d33a` | see exact identity ledger below | `pilot-export:attempt.sqlite3`; 0 rows; hash `1762930d3cc2825e854b0f5376f159c3b6a205a1b8e27a286c549cf091ae129a` | 424.8 s | `BLOCKED_INSUFFICIENT_GRADUATED_POOL` | Not started |
| `attempt-2` | `18f9c6bba956ad2503eb30bfc9e4628a486b2af5` | see exact identity ledger below | `pilot-export:attempt-2:attempt.sqlite3`; 4 rows; hash `d340e868dfbb34845717c9891ffbac0f8596eeb19da03160ec84a88797aac3dd` | 426.8 s | `PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED` | Not started |
| `attempt-3` | `08a1c9d8f7ab69203ed212a4afaa5dea519ebd3b` | see exact identity ledger below | `pilot-export:attempt-3:attempt.sqlite3`; 6 rows; hash `bbf5e56dca8b5db61ef46cdee3c407972fc402ba51a6e2ed6c9c56426b06d9f0` | 368.4 s | `PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED` | Not started |

Exact identity ledger:

- Attempt 1b: authorization/execution e46-attempt-1b-20260724; campaign e46-attempt-1b-20260724-campaign; run e46-attempt-1b-20260724-campaign-run; cycle e46-attempt-1b-20260724-cycle.
- Attempt 2: authorization/execution e46-attempt-2-20260724; campaign e46-attempt-2-20260724-campaign; run e46-attempt-2-20260724-campaign-run; cycle e46-attempt-2-20260724-cycle.
- Attempt 3: authorization/execution e46-attempt-3-20260724; campaign e46-attempt-3-20260724-campaign; run e46-attempt-3-20260724-campaign-run; cycle e46-attempt-3-20260724-cycle.

Every execution ended `GOVERNED_SAFE_STOP`, released the proof lock, left zero
pending/running steps and scheduler jobs, made zero replay source calls, created no
restart or successor, and used a fresh isolated `attempt.sqlite3` plus artifact
directory. The attempt databases and terminal evidence are retained under
`operator-runs/v2-9-7e-46/`.

## Complete candidate and rejection ledger

The ledger below is the complete exact-pool refresh set inside each frozen
four-candidate cap. “Eligible” means only the E.43 exact-pool liquidity front door;
it does not imply holder or activation eligibility.

### Attempt 1b

| Partition | Mint | Exact PumpSwap pool | Fresh liquidity | Result |
|---|---|---|---:|---|
| LATEST | `Gds9MSe4H8SMcPwd5sqMx1n8ak1nkQRCWnQftKyHpump` | `HSoMcpnQLnC6h4HvXVfhKZqqYhGPRrvYegCdDBv3sSMJ` | `$18.13` | Rejected below `$3,000` |
| LATEST | `6vsKxhKwXdRZvYdGZHtLDZALYTShxqJa75hJRXhFpump` | `EF8vBA5Y7HPW9WwuuGVALUNcm5PRZkoEZ5HDwR4gEE7R` | `$11,925.71` | Front-door eligible |
| LATEST | `6Gbgy3A1WzHGVfLixj25zKPu4L4S1T8rEhBB3Nzipump` | `GigPeTgN7TjAihsyvLZ16tJtUVxtnUTka29F9nnhQ3pc` | `$4.50` | Rejected below `$3,000` |
| LATEST | `23NGxdJi5ovKCTtW3FktqxznV4JFpeEoJxXBpWNypump` | `BArrguk94BQu1F6bEJqs7ZsnebiBH5ZeFdPScptf8EvX` | `$4.54` | Rejected below `$3,000` |

Only one candidate could enter the old cap because unrelated create acquisition
had already spent the operation budget. This exposed the supply-accounting defect;
the run safely stopped and the four confirmed rows were merged into the durable
registry.

### Attempt 2

| Partition | Mint | Exact PumpSwap pool | Fresh liquidity | Result |
|---|---|---|---:|---|
| LATEST | `9XuWt4W2WxfJMEL8pkB5bEavhoyBjAMoL7cDEkspump` | `PKztZQTMFRFA6ERj51ggDT764k1bnT32hd6ovDZDddE` | `$7,756.75` | Front-door eligible; holder evidence blocked |
| LATEST | `ktP2UH8AfjPtXvUkBchVYdBdASnmo7AV2XRDWSKpump` | `8QFCrXgjkLepiw9E798ms57i3EB3rMNibGAZ5dRPH7mi` | `$390,616.28` | Front-door eligible; holder evidence blocked |
| PERSISTED | `Gds9MSe4H8SMcPwd5sqMx1n8ak1nkQRCWnQftKyHpump` | `HSoMcpnQLnC6h4HvXVfhKZqqYhGPRrvYegCdDBv3sSMJ` | `$30.45` | Rejected below `$3,000` |
| PERSISTED | `23NGxdJi5ovKCTtW3FktqxznV4JFpeEoJxXBpWNypump` | `BArrguk94BQu1F6bEJqs7ZsnebiBH5ZeFdPScptf8EvX` | `$2.46` | Rejected below `$3,000` |

The frozen persisted partition was exhausted: neither persisted reserve remained
above the front-door floor. The two latest candidates proceeded to holder evidence,
where both failed closed. The two new confirmations were merged into the durable
registry.

### Attempt 3

| Partition | Mint | Exact PumpSwap pool | Fresh liquidity | Result |
|---|---|---|---:|---|
| LATEST | `23NK7f4sLSZJXaRgb9qpERnY3txZYWRa9o8ybBeLpump` | `5usEXo5HpuAnSBHDPNrgaKBTZjc9igrVhFS9DWyGdkem` | `$43.80` | Rejected below `$3,000` |
| LATEST | `4yxNHzN7E9iPBiYVKWrbo5r4CSVkiAxVm1PNaw6gpump` | `AeaiCGUsEs6BUat3c8PCyokKypi11asoZah9asjr5nSJ` | `$8,765.55` | Selected latest; holder evidence blocked |
| PERSISTED | `9XuWt4W2WxfJMEL8pkB5bEavhoyBjAMoL7cDEkspump` | `PKztZQTMFRFA6ERj51ggDT764k1bnT32hd6ovDZDddE` | `$8,019.03` | Selected persisted; holder evidence blocked |
| PERSISTED | `23NGxdJi5ovKCTtW3FktqxznV4JFpeEoJxXBpWNypump` | `BArrguk94BQu1F6bEJqs7ZsnebiBH5ZeFdPScptf8EvX` | `$2.46` | Rejected below `$3,000` |

This execution proved the required pre-holder supply composition: one genuine
LATEST and one genuine PERSISTED candidate, both with exact confirmed PumpSwap
pools and fresh liquidity above `$3,000`. Other newly confirmed rows
(`74rH41B2M8J4krHjqRPJ5JHEGcBdDZoLsAesqe2Qpump`,
yTB8V6n8J9JEaLFWB5ZLCnF5o68Ass553r32c41pump`) remained outside the frozen two-LATEST refresh
slice and were not silently evaluated or promoted. The durable registry ended with
10 exact graduated rows, `integrity_check == ok`, and zero foreign-key violations.

## Holder reserve funnel

Attempt 2 evaluated both front-door-eligible latest candidates. Attempt 3 evaluated
the one lawful candidate in each required partition. For all four evaluations:

- GoPlus completed with `CLEAN_DATA`, `exact_target == 1`, but correctly remained
  `HOLDER_CONCENTRATION_UNKNOWN`; it is safety context, not wallet concentration.
- Fixed public primary `api.mainnet-beta.solana.com`
  `getTokenLargestAccounts(finalized)` returned HTTP 429
  (`solana_rpc_rate_limited`), one underlying operation each.
- Fixed Helius Free backup failed `helius_auth_missing`
  (`HELIUS_FREE_API_KEY_REQUIRED`), zero underlying operations.
- The result stayed `HOLDER_CONCENTRATION_UNKNOWN`; no candidate was labelled
  holder-eligible.

Holder ledger arithmetic:

| Execution | Ceiling | Governed requests | Underlying operations | Zero-transport operations | Snapshot reservation | Snapshot-completion reservation |
|---|---:|---:|---:|---:|---:|---:|
| Attempt 2 | 45 | 17 | 15 | 9 | 2 | 4 |
| Attempt 3 | 45 | 19 | 17 | 9 | 2 | 4 |

There was no lawful same-partition reserve replacement that could overcome this
provider-wide evidence outage: below-floor candidates were already ineligible, and
every eligible holder query used the same adopted primary/backup contract. The
planner did not stop on a token-local holder rejection while a lawful alternative
remained; it stopped on the common evidence channel being unavailable.

## Activation, readiness, lifecycle and memory

- **Atomic activation:** not attempted; exact two-or-none behavior preserved.
- **`PILOT_INPUT_READY`:** no row written. Mandatory HOLDER evidence was absent, so
  the immutable bundle owner failed closed.
- **WINDOW_15M / WINDOW_1H / WINDOW_4H:** no window started or completed.
- **Continuation:** not evaluated and not forced.
- **WINDOW_5M_MICRO_EVENT:** not created.
- **Clean/dirty/blocked memories and promotions:** zero; no false dirty label was
  assigned to a provider-evidence failure and no memory was fabricated.
- **Authoritative reporting:** terminal holder block preserved; lifecycle
  clean/dirty/blocked reporting was inapplicable because lifecycle never launched.

## Source and Scheduler accounting

| Execution | Durable source requests | Responses | Failures | Notable source arithmetic |
|---|---:|---:|---:|---|
| Attempt 1b | 11 | 10 | 1 | PumpPortal 3, PumpSwap verification 4, exact-pool DexScreener 4 |
| Attempt 2 | 16 | 11 | 5 | locator 1, PumpPortal 3, PumpSwap 2, exact-pool 4, GoPlus 2, public RPC 2, Helius Free 2 |
| Attempt 3 | 18 | 14 | 4 | locator 1, PumpPortal 3, PumpSwap 4, exact-pool 4, GoPlus 2, public RPC 2, Helius Free 2 |

The sole non-holder live failure was one honest
`pumpportal_no_valid_solana_events` window. There was no paid RPC, arbitrary RPC,
endpoint rotation, provider racing or hidden retry. Central Scheduler lifecycle
work remained zero because readiness failed before launch.

## Replay, cleanup, integrity and forbidden deltas

All three execution reports recorded deterministic replay with
`replay_new_source_calls == 0`; because no lifecycle run existed this was the
canonical deterministic pre-lifecycle replay/terminal path. Each execution recorded
zero pending/running run steps, zero running scheduler jobs, proof lock released,
no restart and no successor.

Every attempt DB and the final durable graduated registry returned
`PRAGMA integrity_check == ok` and zero `foreign_key_check` rows. Every attempt DB
retained zero rows in:

- memory retrieval queries and matches;
- paper decisions and decision audits;
- paper positions;
- paper trade events and trade audits.

No PnL owner/table was activated. The terminal reports recorded empty forbidden
deltas. No wallet, private key, transaction signing, live trading or fund movement
was introduced.

## Money-usefulness contribution

This lane proved that the canonical machine can now build a truthful mixed
LATEST/PERSISTED graduated cohort on exact `$3,000+` pools without starving the
persisted partition or spending the holder budget on irrelevant create acquisition.
It also prevented fake money-usefulness: a token with attractive liquidity and
price action was not admitted when holder concentration could not be evidenced.
No profit, trade quality or memory-quality claim is made.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk:** graduation-native activation through sustained lifecycle
  remains live-unproven because the holder gate correctly prevented launch.
- **Setback:** the adopted fixed public RPC was rate-limited in two fresh executions
  for both selected tokens; the adopted Helius Free backup had no configured key.
- **Efficiency blocker:** fresh live migration rounds take several real minutes
  even when the common holder channel is unavailable. This is expected bounded
  live-source cost, not permission to cache stale holder evidence or add endpoints.
- **Residual repair risk:** all three production repairs are focused-test proven,
  but the post-holder live path remains unexercised until valid holder evidence is
  available.

## Roadmap and operator state

V2-9.7E remains **active** with exact unresolved first cause:
`PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED` under the adopted fixed public RPC primary
and fixed Helius Free backup contract. V2-9.7F is **not ready** and was not started.
The active build order is unchanged.

A future retry is lawful only with fresh identities and fresh evidence after the
adopted holder source contract is operational—for example, after the operator
configures the already-approved Helius Free credential through the existing secret
boundary, or the fixed public RPC returns valid evidence. This closeout does not
authorize a paid plan, a new endpoint, endpoint rotation, or a contract redesign.

All permanent Printer V1 locks remain in force.
