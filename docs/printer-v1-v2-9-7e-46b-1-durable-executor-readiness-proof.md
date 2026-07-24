# Printer V1 — V2-9.7E.46B.1 Durable-Executor Readiness Proof

**Verdict: `V2_9_7E_46B_1_READINESS_PASS`.**

Exactly one canonical `PILOT_INPUT_READINESS` execution was run from a durable
local PowerShell process and reached a governed terminal on its own, producing one
immutable `PILOT_INPUT_READY` bundle from two distinct fully eligible tokens. This
is proof-only: no product code was audited, redesigned or modified, and no
`FULL_PILOT` was run. A PASS makes a **separately authorized** E.46 full-pilot
retry ready. It does not run that pilot and does not unlock V2-9.7F.

- **Baseline HEAD:** `b68977e0ae5e9f856ddf21f907615e0ccc54e88c`
- **Live execution HEAD:** `b68977e0ae5e9f856ddf21f907615e0ccc54e88c` (identical; the
  tracked tree was clean before, during and after the execution)
- **Live date:** 2026-07-24
- **Execution / authorization identity:** `e46b1-readiness-20260724-b68977e`
- **Isolated artifacts:** `C:\Users\dtwof\PrinterPilot\E46B1\e46b1-readiness-20260724-b68977e\`
  (outside the repository; never entered any persistent corpus)

## 1. Durable launcher method and process lifetime

The E.46B block was an executor-lifetime block: a short-lived command process
terminated the run at roughly two minutes. This lane therefore ran the canonical
proof outside any short-timeout tool process.

| Property | Value |
|---|---|
| Launch mechanism | `Start-Process powershell.exe … -PassThru` (detached, not a piped child) |
| Launcher location | temporary, outside the repository, in the session scratchpad |
| Arguments | `-NoProfile -NonInteractive -ExecutionPolicy Bypass -File <launcher.ps1>` |
| Retained process ID | **452** (`powershell.exe`), child `python.exe` **32620** |
| stdout / stderr | redirected to isolated attempt files `executor-stdout.txt` / `executor-stderr.txt` |
| Timeout | **none** — no timeout shorter than (or at all bounding) the readiness window |
| Monitoring | by process ID and by terminal artifacts (`executor-done.marker`, `terminal-result.json`) |
| Retry / restart / successor | none |
| Timing compression | none — canonical collection timing untouched |

Process lifetime:

- `DURABLE_EXECUTOR_START_UTC` = `2026-07-24T22:06:14.856Z`
- `DURABLE_EXECUTOR_END_UTC` = `2026-07-24T22:12:53.019Z`
- Supervised execution: `2026-07-24T22:06:21.822Z` → `2026-07-24T22:12:52.808Z`
- Runner wall time: **396.4 s**; `PYTHON_EXIT_CODE=0`

The executor lived **6 min 38 s**, comfortably past the ~2-minute point at which the
E.46B attempt died, and terminated because the canonical runner finished — not
because anything killed it. The launcher additionally held
`ES_CONTINUOUS | ES_SYSTEM_REQUIRED` for the window so the host could not idle-sleep,
and released it at exit. No persistent power policy was changed.

The run finished faster than E.46A (875 s) for an honest reason: the bounded
migration discovery reached its confirmed-LATEST depth in three rounds and the
front-door/holder funnel then completed without exhausting its budget. No stage was
skipped or shortened.

## 2. Authorization, fresh identities, preconditions

Every precondition was verified **before** authorization:

| Precondition | Result |
|---|---|
| Exact clean HEAD | `b68977e0ae5e9f856ddf21f907615e0ccc54e88c`, re-verified immediately pre-launch |
| Clean tracked tree | clean (untracked proof artifacts only) |
| Active Printer process / campaign / lease / proof lock | none; the sole stray `python.exe` was an unrelated Google Cloud SDK proxy |
| Network stability | 5/5 TCP:443 handshakes to both `api.dexscreener.com` and `mainnet.helius-rpc.com`; DNS resolving; Wi-Fi up at 144 Mbps |
| Power / sleep | standby-idle disabled on AC and DC; hibernate-idle 16 h; **on battery at 51%** (ample for a 20-minute window), plus the executor's wake hold |
| Fresh executor secret | `PRINTER_HELIUS_API_KEY` present **by presence only**; never printed, logged or persisted |
| Isolated artifacts | fresh directory; target and backup did not pre-exist |

Fresh identities (no reuse of any E.46/E.46A/E.46B identity):

- authorization / execution `e46b1-readiness-20260724-b68977e`
- campaign `e46b1-readiness-20260724-b68977e-campaign`
- run `e46b1-readiness-20260724-b68977e-campaign-run`
- cycle `e46b1-readiness-20260724-b68977e-cycle`
- configuration `e46b1-readiness-20260724-b68977e-configuration`
- selection seed `e46b1-readiness-20260724-b68977e`

## 3. Preflight result

Zero-source readiness source-contract preflight, run in the fresh executor before
any provider contact:

| Field | Value |
|---|---|
| Status | `READY` |
| Issues | 0 |
| External requests | **0** |
| `secret_material_recorded` | `false` |
| `helius_secret_present` | `true` (presence only) |
| Operation ceiling | 45 |
| Zero-transport operations | 9 |
| Reserved snapshot / completion operations | 2 / 4 |

Target preparation: `PILOT_TARGET_READY` — schema validated, backup byte-identical
(`target_hash == backup_hash == e0c466d3df5ac1f8c4fdfcbdbb6768b55c26f1d8b455a2184b4d35930368a8aa`),
restore rehearsal passed on a disposable copy that was then removed, no active
lease, `persistent_unchanged = true`. Immutable isolated export
`pilot-export:e46b1-readiness-20260724-b68977e:attempt.sqlite3`, 10 rows,
provenance hash `f4de69c896e145890d0ae72dfa4e68a0dc789637fb71860a761be5c1135a5a1a`.

## 4. Complete candidate and rejection ledger

Bounded direct-migration discovery ran **3** PumpPortal rounds at canonical timing
(r0 22:06:23 complete, r1 22:08:26 → `pumpportal_no_valid_solana_events` at
22:10:27, r2 22:10:27 complete at 22:12:17). A round that yields no valid events is
a governed round outcome, not a retry. Five confirmed-LATEST PumpSwap
signature→pool resolutions followed (22:12:23–22:12:33), taking the attempt registry
from 10 to **15** rows.

The combined seeded-uniform pool then took **6** governed exact-pool DexScreener
liquidity requests — drawn from **both** partitions, which is the E.46B combined
pool working as designed:

| # | Partition | Mint | Exact PumpSwap pool | Fresh liquidity | Result |
|---|---|---|---|---:|---|
| 1 | LATEST | `Hp5x54szrpHzpebY4a2euci9zTuRrntvpJpFHbuapump` | — | — | **Source failure** (`dexscreener_malformed_fixture`, `MISSING_CRITICAL_DATA`) — fail-closed, not a target mismatch |
| 2 | LATEST | `GHvGDy5VDgBFyuY3pyhi35FNyd5GkNpQgJwpCVEpump` | `AFYpfqZaqEVVW1VpdJpCbLHqmWR8wofGa8MRigN5XSZj` | **$297,019.76** | Eligible → **SELECTED** |
| 3 | LATEST | `CR7gzSampCC76acKLE3P6M4FsL78i88eB6QQMW9Fpump` | `EqHWeRaypinrDJXVju1piyi59tBT8c5AcGS3KPLWaQui` | **$12,888.98** | Eligible → **SELECTED** |
| 4 | PERSISTED | `23NK7f4sLSZJXaRgb9qpERnY3txZYWRa9o8ybBeLpump` | `5usEXo5HpuAnSBHDPNrgaKBTZjc9igrVhFS9DWyGdkem` | $35.56 | Rejected below `$3,000` |
| 5 | PERSISTED | `Gds9MSe4H8SMcPwd5sqMx1n8ak1nkQRCWnQftKyHpump` | `HSoMcpnQLnC6h4HvXVfhKZqqYhGPRrvYegCdDBv3sSMJ` | $35.27 | Rejected below `$3,000` |
| 6 | PERSISTED | `4yxNHzN7E9iPBiYVKWrbo5r4CSVkiAxVm1PNaw6gpump` | `AeaiCGUsEs6BUat3c8PCyokKypi11asoZah9asjr5nSJ` | $1,738.09 | Rejected below `$3,000` |

“LATEST” = confirmed by this execution's bounded migration refresh; “PERSISTED” =
present in the pre-run canonical registry (10 mints). No candidate or rejection was
silently promoted; the `$3,000` floor was never weakened.

Admission summary: `candidate_universe` 2, `candidate_cap` 2,
`graduated_admitted` 2, eligibility rule `GRADUATION_ONLY`,
`latest_vs_non_latest` = `{LATEST_GRADUATED: 2, NON_LATEST_GRADUATED: 0}`,
`staged_pending_discovery_this_cycle` 0.

## 5. Selected provenance composition

**`LATEST_GRADUATED` + `LATEST_GRADUATED`** — recorded truthfully in the bundle as
`{"latest": "LATEST_GRADUATED", "persisted": "LATEST_GRADUATED"}`. Neither token was
relabelled to satisfy a partition slot.

This is the decisive result for E.46B's thesis. All three `$3,000+`-capable
candidates in this cycle were LATEST; every PERSISTED candidate was far below the
floor. Under the pre-E.46B mandatory mixed `LATEST + PERSISTED` quota this cycle
would have blocked despite two genuinely liquid, holder-valid tokens being
available. Partition-flexible sourcing converted an artificial block into an honest
PASS without loosening any gate.

## 6. Liquidity and holder evidence

Fresh exact-pool liquidity, both ≥ `$3,000`, governed DexScreener
`pair_market_snapshot`, `CLEAN_DATA`:

- `CR7gzSamp…pump` / `EqHWeRaypinrDJXVju1piyi59tBT8c5AcGS3KPLWaQui` — **$12,888.98**, received `22:12:36.836Z`
- `GHvGDy5V…pump` / `AFYpfqZaqEVVW1VpdJpCbLHqmWR8wofGa8MRigN5XSZj` — **$297,019.76**, received `22:12:36.372Z`

Holder funnel — both candidates used exactly the committed fixed order
GoPlus → public Solana RPC → Helius Free backup. No rotation, racing or retry:

| Candidate | GoPlus | Public RPC | Helius Free (backup) | Holder result |
|---|---|---|---|---|
| `CR7gzSamp…pump` | complete (safety context) | `solana_rpc_rate_limited` | complete | `VALID_EXACT_TARGET_HOLDER_EVIDENCE`, eligible, `HOLDER_CONCENTRATION_HEALTHY` |
| `GHvGDy5V…pump` | complete (safety context) | `solana_rpc_rate_limited` | complete | `VALID_EXACT_TARGET_HOLDER_EVIDENCE`, eligible, `HOLDER_CONCENTRATION_EXTREME` |

Six durable `printer_holder_evidence_attempts` rows carry exact mint identity,
endpoint role, redacted host, request/response/failure linkage and lineage. The
public-RPC rate limit was recorded as a transport/rate failure, **not** a target
mismatch — correct failure precedence. Two `printer_holder_maturation_work` rows
are `COMPLETED` with `maturation_threshold_state = UNPROVEN_DISABLED`.

`HOLDER_CONCENTRATION_EXTREME` is a truthful categorical label, not a rejection
reason: the E.45/E.46 gate requires *valid exact-target holder evidence*, which both
tokens have. It is recorded here explicitly so a later authorized full pilot treats
that token's concentration as known and adverse rather than unexamined.

## 7. Source and operation accounting

Campaign holder-operation ledger (`printer_holder_campaign_operation_ledgers`):

| Field | Value |
|---|---|
| Operation ceiling | 45 |
| Governed requests | 22 |
| Underlying transport operations | 24 |
| Zero-transport operations | 9 |
| Reserved snapshot operations | 2 |
| Reserved snapshot-completion operations | 4 |

Durable source rows: **21** requests, **17** responses, **4** failures
(17 + 4 = 21, internally consistent), by source/kind:

| Source | Request kind | Count |
|---|---|---:|
| dexscreener | `dexscreener_fresh_profiles` (locator) | 1 |
| dexscreener | `pair_market_snapshot` | 6 |
| pumpportal | `pumpfun_migration_stream` | 3 |
| pumpswap | `pumpswap_signature_pool_resolution` | 5 |
| goplus | `safety_reference` | 2 |
| solana_rpc | `holder_concentration_reference` | 2 |
| helius_free | `holder_concentration_reference` | 2 |

The four failures were `pumpportal_no_valid_solana_events` (1),
`dexscreener_malformed_fixture` (1) and `solana_rpc_rate_limited` (2). All stayed
within the ceiling with reserves intact.

**Observed reconciliation gap (reported, not explained away):** the campaign ledger
records `governed_requests = 22` while the durable `printer_source_requests` table
holds **21** rows — a difference of one. Both figures are reported as observed. This
lane is proof-only and did not investigate or change the accounting owners; the
discrepancy is carried forward as a finding for a future audit lane. It does not
affect any eligibility decision, and the ceiling (45) was not approached on either
count.

## 8. Readiness bundle

One row in `printer_pilot_input_readiness_bundle`:

| Field | Value |
|---|---|
| `readiness_id` | `…-campaign-run:…-cycle:pilot-input` |
| `readiness_state` | `PILOT_INPUT_READY` |
| Slot A mint / pool | `CR7gzSampCC76acKLE3P6M4FsL78i88eB6QQMW9Fpump` / `EqHWeRaypinrDJXVju1piyi59tBT8c5AcGS3KPLWaQui` |
| Slot A liquidity / route | `$12,888.98` / `GRADUATION_NATIVE` |
| Slot B mint / pool | `GHvGDy5VDgBFyuY3pyhi35FNyd5GkNpQgJwpCVEpump` / `AFYpfqZaqEVVW1VpdJpCbLHqmWR8wofGa8MRigN5XSZj` |
| Slot B liquidity / route | `$297,019.76` / `GRADUATION_NATIVE` |
| Provenance | `{"latest": "LATEST_GRADUATED", "persisted": "LATEST_GRADUATED"}` |
| Selection seed | `e46b1-readiness-20260724-b68977e` |
| Git provenance identity | `b68977e0ae5e9f856ddf21f907615e0ccc54e88c` |
| Configuration hash | `b45638f65ae8d7c71efc87525fd1724acb7abcabb0a6be27c2724728264dbe9f` |
| Bundle hash | `7d7053023e4e30ea7fc2cd4b6926cf173636d7cc34be5486390ea38234233a15` |
| Created / expires | `2026-07-24T22:06:13+00:00` / `2026-07-24T22:16:13+00:00` |

Immutability is enforced structurally, not by convention: `BEFORE UPDATE` and
`BEFORE DELETE` triggers both `RAISE(ABORT, 'pilot input readiness bundle is
immutable')`, and table CHECKs enforce `readiness_state = 'PILOT_INPUT_READY'`, both
liquidity columns `>= 3000.0`, distinct mints, and a 64-character bundle hash.

**Timestamp semantics (stated precisely).** `created_at`,
`latest_liquidity_observed_at` and `persisted_liquidity_observed_at` all carry the
campaign evaluation reference time `22:06:13Z` supplied at launch, and `expires_at`
is that reference + 10 minutes. They are **not** the wall-clock instants at which
the provider answered. Actual freshness is proven independently by the durable
governed response receipts at `22:12:36.372Z` and `22:12:36.836Z` — roughly 16
seconds before the bundle was written at the `22:12:52.8Z` terminal, and well inside
the reference TTL. This distinction is recorded so no later lane mistakes the
reference stamp for an observation time.

## 9. Replay, terminal metadata, cleanup and integrity

**Replay — stated honestly.** The terminal is *pre-lifecycle*: no factory lifecycle
run started, so no factory terminal report exists. The runner's returned
`replay_deterministic: true` and `replay_new_source_calls: 0` on this path are
**structural constants, not the result of an executed replay** — the runner only
invokes `pilot_report_only_replay` when `lifecycle_started` is true. This was
confirmed empirically: invoking `pilot_report_only_replay` against a disposable copy
raises `ValueError: terminal report not found for run_id=…`. The lane therefore does
not claim a factory replay it did not run.

What *is* replayable — the durable readiness evidence — was replayed for real,
read-only (`mode=ro`), against a disposable copy:

| Check | Result |
|---|---|
| Pass 1 / pass 2 evidence hash | `c1833c6d…88f1` / `c1833c6d…88f1` — identical |
| Deterministic | **true** |
| New source calls during replay | **0** (21 → 21 request rows) |
| Database bytes changed by replay | none |
| Original attempt DB touched | no |
| Disposable copy | removed |

Terminal metadata reconciliation (E.46B item 9) executed on this governed
pre-lifecycle terminal — the exact behaviour the killed E.46B attempt could not
demonstrate:

- campaign → `TERMINAL_STOPPED`, run → `TERMINAL_STOPPED`, cycle → `TERMINAL_STOPPED`,
  all at `2026-07-24T22:12:52.852901+00:00`, cause `PILOT_INPUT_READY`
- no `RUNNING/RUNNING/PLANNED` metadata survives with zero active work

Supervision and cleanup: `execution_status = TERMINAL`,
`terminal_status = GOVERNED_SAFE_STOP`, `first_stop_reason = PILOT_INPUT_READY`,
`one_proof_lock_released = true` (lock file absent), `pending_or_running_run_steps` 0,
`running_jobs_after_stop` 0, rollback journal removed, restore-rehearsal DB removed,
`restart_created = false`, `successor_created = false`.

Integrity on the attempt DB (`journal_mode = delete`):

- `PRAGMA integrity_check` → **`ok`**
- `PRAGMA foreign_key_check` → **0 violations**
- schema migrations applied: 41

## 10. Forbidden-delta proof

`forbidden_deltas` from the runner was empty. Independently verified by scanning all
**84** tables in the attempt DB by capability category:

| Category | Tables scanned | Rows |
|---|---:|---:|
| lifecycle / tracking queue | 2 | **0** |
| memory / episode / window / promotion / clean | 18 | **0** |
| retrieval / similarity | 2 | **0** |
| decision | 2 | **0** |
| position | 1 | **0** |
| trade | 2 | **0** |
| audit | 5 | **0** |
| PnL / profit | 0 | **0** |
| **Total forbidden rows** | | **0** |

The only populated tables are governance and evidence: campaign/run/cycle/
configuration metadata (1 each), the readiness bundle (1), supervision (1), the
graduated registry (15), holder ledger (1), holder evidence attempts (6), holder
maturation work (2), source requests/responses/failures (21/17/4), and schema
migrations (41). No lifecycle started, no window opened, no memory, retrieval,
decision, position, trade, audit or PnL row was created anywhere.

**No code was modified after the live execution to force PASS.** HEAD is unchanged at
`b68977e0ae5e9f856ddf21f907615e0ccc54e88c` and the tracked tree remained clean
throughout; the only repository change in this lane is this closeout document.

## 11. Money-usefulness contribution

This is the first live evidence that E.46B's partition-flexible sourcing actually
converts real market conditions into a usable pilot input set. In this cycle every
persisted reserve was under `$40`–`$1,738` while three freshly graduated tokens were
liquid; the old mixed-pair quota would have blocked on supply that genuinely existed.
Two liquid, holder-verified tokens now qualify on their merits. No liquidity floor,
exact pool/mint identity rule, or holder-evidence gate was weakened, and no memory,
paper result, trade or profit claim is made.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

- **Risk:** the readiness bundle carries a 10-minute TTL from the campaign evaluation
  reference (`expires_at 22:16:13Z`), which had already lapsed by the time this
  closeout was written. A separately authorized full-pilot retry must obtain its own
  fresh readiness rather than consume this bundle — this PASS proves the path works,
  not that this specific input set is still live.
- **Risk:** one selected token is labelled `HOLDER_CONCENTRATION_EXTREME`. It is
  lawfully eligible under the committed gate, but a later authorized pilot should
  treat its concentration as a known adverse condition, not an unexamined one.
- **Setback:** three of six pooled candidates were below the `$3,000` floor and one
  liquidity request failed outright, leaving exactly two eligible tokens — a PASS with
  no margin. A slightly worse cycle would have blocked honestly.
- **Efficiency blocker / open finding:** the campaign ledger's `governed_requests`
  (22) and the durable source-request row count (21) differ by one. Proof-only scope
  prevented investigation; it is carried forward for a future audit lane.
- **Observation:** the public Solana RPC rate-limited both holder lookups, so both
  tokens' holder evidence came from the Helius Free fixed backup. The committed fixed
  order held, but primary-RPC holder reliability remains weak, as in E.20–E.24.

## 13. Verdict and remaining locks

**`V2_9_7E_46B_1_READINESS_PASS`.**

Every PASS requirement is met: two distinct fully eligible tokens of a lawful
provenance composition; fresh exact-pool liquidity of `$12,888.98` and `$297,019.76`;
valid exact-target holder evidence for both; one immutable `PILOT_INPUT_READY`
bundle; exact operation accounting within the ceiling (with the one-request gap
reported); governed terminal campaign/run/cycle metadata; deterministic zero-source
replay of the durable evidence; released lock; integrity `ok`; zero FK violations;
zero lifecycle, memory, retrieval, decision, position, trade, audit and PnL rows; and
no retry, restart or successor.

A separately authorized **E.46 full-pilot retry is now ready** — and only ready. This
lane does not run that pilot, does not consume its authorization, and does not unlock
V2-9.7F. All permanent Printer V1 locks remain in force: Solana memecoin only, paper
only, no wallets/private keys/funds/live execution, no paid APIs, no
scoring/ranking/confidence/weighted logic, no Source Governor or Central Scheduler
bypass, no dirty memory for decisions, and no BUY/SELL/HOLD, positions, trade, audit
or PnL unlock. V2-9.7E remains active; V2-9.7F was not started.
