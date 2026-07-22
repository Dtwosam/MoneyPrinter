# V2-9.7E.18 Clean Live Memory and Operational Terminal Repair — Design

**Status:** DESIGN GATE NOT PASSED — M1 has no permitted, safe, offline-verifiable repair

**Design verdict:** `V2_9_7E_18_BLOCKED_DESIGN`

## Baseline

- Commit: `5f6635ec587a7124ec501a361155fbe6c4142025` (`Audit live clean-memory and
  pilot terminal blockers`); clean tracked tree.
- Read-only pilot DB re-inspected for design evidence
  (`C:\Users\dtwof\PrinterPilot\E15\printer-v1-e15-pilot.sqlite3`). No provider
  contact, no DB mutation, no production change, no rerun.

The design gate states: "Do not implement until the design confirms no safety or
source-law weakening." M2, M3 and O1 admit safe designs (below). **M1 does not**:
every candidate reliability improvement either (a) is already present, (b) is
explicitly forbidden (new retries/backoff/rotation/paid), (c) weakens the safety
contract, or (d) crosses the Governor **Evidence Isolation Rule**. Because the
clean-memory goal depends on M1 (the safety hard-block is independent of the
snapshot hard-block), implementing M2/M3/O1 alone would misleadingly imply the
clean-memory blocker is resolved. The gate is therefore not passed and no
production change is committed.

## Precise dirty-cause evidence (both tokens identical)

Authoritative hard blockers (`shared_window_15m_context_evidence.blockers`):

1. **`NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE`** — the safety composite is
   `PARTIAL` because `holder_concentration_label = HOLDER_CONCENTRATION_UNKNOWN`.
   Trace: GoPlus `TOKEN_SAFETY` succeeded `COMPLETE/CLEAN` but returned
   `holder_concentration_label = UNKNOWN` (no holder data for these fresh
   tokens); the on-chain `solana_rpc holder_concentration_reference` primary
   (`api.mainnet-beta.solana.com`) returned HTTP 429, and its one governed backup
   (`solana-rpc.publicnode.com`, V2-9.6 redundancy) read-timed-out. Both attempts
   are recorded (`…:context:holder`, `…:context:holder_backup`) per token.
2. **`SNAPSHOT_CRITICAL_FIELDS_MISSING`** — the DexScreener `pair_market_snapshot`
   succeeded but returned NULL `price_change_5m/15m`, `volume_15m`, `txns_15m`,
   `liquidity_usd`, `token_age_seconds` for these near-untraded, flat tokens
   (≈4 tx/1h, 0 volume 5m).

The two causes are independent; each alone blocks clean memory.

## M3 — Operational terminal semantics (safe design; ready)

**Owner:** `one_command_15m_factory.py` `_four_hour_terminal_validation`.

**Current behavior:** enabled by `config["continuous_four_hour"]`. In operational
mode `run_operational` sets `continuous_four_hour=True` and
`four_hour_proof_mode=True`. With no natural continuation, `phase_state ==
"NOT_STARTED"` → reason `four_hour_phase_not_started`, `complete=False` →
`SAFE_STOPPED` / `SAFE_STOP_4H_TERMINAL_INCOMPLETE`.

**Design:**
- Derive `operational = bool(config.get("operational_natural_disposition")) and
  _compressed_two_token_plan(config) is None` (operational-natural mode, mutually
  exclusive with the E.9 proof plan).
- When `operational` and `phase_state == "NOT_STARTED"`: do **not** append
  `four_hour_phase_not_started`; treat completion as valid, i.e.
  `complete = (phase_state in ("NOT_STARTED","STARTED")) and not reasons` for
  operational mode, unchanged (`phase_state == "STARTED" and not reasons`) for
  proof mode. A started 4h phase is still fully validated in both modes, so a
  qualifying natural 1h/4h continuation is **not** weakened, and pending/running,
  source-failure and budget reasons still block.
- Proof-only mode (E.9 compressed plan; or `four_hour_proof_mode` without
  operational-natural) keeps requiring its configured 4h terminal.
- `STOP_COMPLETED` already means "clean or dirty results reported"; a dirty
  operational stop completes honestly and produces zero clean promotion, so it
  cannot yield a false clean/PASS.

**Offline proof:** two clean 15m stop outcomes → `COMPLETED` operationally;
barrier intact; a qualifying continuation still reaches 1h/4h; proof mode still
requires its terminal; a dirty stop yields no clean promotion.

**Migration:** none.

## M2 — Verified absent-vs-zero snapshot semantics (safe design; ready)

**Owner:** the DexScreener snapshot normalizer + `context_evidence/window_15m.py`
snapshot critical-field gate (`SNAPSHOT_CRITICAL_FIELDS_MISSING`).

**Design:** convert absent 5m/15m activity fields to a factual **zero** only when
positive observation evidence proves the market was observed and inactive, all of:
valid exact pair identity + target match; a successful, non-stale, non-malformed
current snapshot response; a valid `price_usd` and a valid `liquidity_usd`
observation; and valid wider-window activity fields (e.g. `volume_1h`/`txns_1h`)
present. Only then are missing `volume_5m/15m`, `txns_5m/15m`,
`price_change_5m/15m` normalized to `0` with an explicit
`SNAPSHOT_VERIFIED_INACTIVE` provenance, enabling a truthful flat/`NO_PUMP`
classification. Any failed, malformed, stale, or identity-mismatched response —
**or a missing `liquidity_usd`/`price_usd`** — keeps the fields missing and the
memory dirty. No price/liquidity/volume/txn value is ever invented.

**Note (does not rescue E.15):** the E.15 snapshots had NULL `liquidity_usd`, so
the positive-evidence gate would correctly still fail closed. M2 is a valid
general improvement for tokens that have valid price+liquidity but zero recent
activity; it does not clean the E.15 illiquid tokens.

**Offline proof:** positively-verified inactive market → factual zero + clean
flat/no-pump; failed/malformed/stale/mismatched or missing-liquidity → missing +
dirty; existing active-market classification unchanged.

**Migration:** none (uses existing snapshot columns + provenance).

## O1 — Campaign discovery cleanup (safe design; ready)

**Owner:** campaign terminal cleanup (`one_command_15m_factory.py` terminal path
/ `campaign_supervision.py`).

**Evidence:** 10 `DISCOVERY_REFRESH` jobs (`target_table=printer_discovery_batches`,
job_names `DISCOVERY_*:discovery-batch:pilot-camp:pilot-run:pilot-cyc`) remained
`PENDING` after terminal closeout; inert but campaign-scoped.

**Design:** at campaign/run terminalization, cancel campaign-owned pending/running
`DISCOVERY_REFRESH` jobs selected **only** by the exact campaign/run/cycle scope
(via job_name scope or a campaign-owned discovery-batch join), leaving all other
Scheduler work untouched, idempotently (re-running cancels nothing new).

**Offline proof:** terminal campaign leaves zero campaign-owned pending/running
discovery jobs; unrelated jobs unchanged; repeated cleanup safe.

**Migration:** none.

## M1 — Holder-concentration reliability (design gate FAILS)

**Requirement:** "one transient free-RPC fault does not make clean 15m memory
impossible," preserving governance, without new retries/backoff (unless the
active source policy explicitly permits the exact bounded behavior), without
endpoint rotation or paid fallback, preferring an existing governed alternative
or a more reliable single bounded RPC composition, and **without removing holder
concentration from the safety contract**.

Options considered, each blocked:

1. **Prefer the existing governed alternative (GoPlus).** Already implemented:
   `safety/composite.py` uses GoPlus `holder_concentration_label` first and only
   falls to the on-chain `solana_rpc` field when GoPlus is `UNKNOWN`. In E.15
   GoPlus genuinely returned `UNKNOWN` (no holder distribution for fresh tokens).
   Nothing to add.
2. **The "one transient fault" tolerance already exists.** The committed V2-9.6
   `safety_context_source_redundancy` provides exactly one governed, distinct-
   endpoint backup for the on-chain holder field on eligible transient primary
   failure. It is wired into the operational window-close path and **fired** in
   E.15. The E.15 failure was **two independent transient faults** (primary 429 +
   backup timeout) plus the GoPlus data gap — beyond "one fault."
3. **More reliable single bounded RPC composition (getTokenLargestAccounts +
   GoPlus supply).** This would source total supply for the *authoritative
   on-chain* holder-concentration field from a *provider* source (GoPlus),
   composing one source's field from another's evidence. This **violates the
   Governor Evidence Isolation Rule** ("evidence stamped by one source must never
   be attributed to another"; holder concentration is the designated on-chain
   field, deliberately separated from GoPlus provider-risk in V2-9.6). It is a
   source-law weakening the design gate forbids; its live reliability benefit is
   also unverifiable offline (no provider contact permitted).
4. **A second backup endpoint / bounded retry / different primary endpoint /
   endpoint rotation / paid endpoint.** All are either explicitly forbidden
   (retries/backoff without policy permission, rotation, paid) or a source-policy
   change beyond this repair lane's mandate, and none is offline-verifiable.
5. **Decouple holder-concentration from the 15m safety hard-block.** Explicitly
   forbidden ("Do not remove holder concentration from the safety contract merely
   to raise clean yield").

**Conclusion:** there is **no** permitted, safety-preserving, source-law-
respecting, offline-verifiable M1 change that improves reliability beyond the
existing one-fault tolerance. The observed E.15 dirtiness from the safety lane is
a genuine transient/ data-availability condition (self-inflicted RPC contention +
provider data gap for fresh tokens), correctly failing closed — not a code defect
with a safe repair. The design gate cannot confirm "no safety or source-law
weakening" for any M1 change, so it is not passed.

## Why this blocks the lane (not just M1)

The safety hard-block (M1) and the snapshot hard-block (M2) are **independent**.
Even with M2, M3 and O1 implemented, the E.15-class tokens stay dirty (holder
concentration unknown; and their liquidity was also absent, so M2's
positive-evidence gate correctly fails too). Shipping M2/M3/O1 as
"clean-live-memory repair" would misrepresent the state: clean live memory would
still not be achievable for the conditions that motivated the lane.

## Minimum operator decision required to unblock

Exactly one of:

1. **Explicit source-policy authorization** for a specific, bounded holder-
   concentration reliability mechanism (e.g. a named second free/public backup
   endpoint, or a single bounded retry with defined limits) — stating the exact
   permitted behavior so it does not require inferring an unapproved policy.
2. **An explicit safety-contract review lane** deciding whether an exact-target
   holder-concentration that is *provably unavailable after the full governed
   attempt* may degrade to an explicit `SAFETY_HOLDER_UNAVAILABLE` state that is
   audit-recorded but does not hard-block a clean 15m **outcome** memory (while
   still blocking any paper decision) — a genuine contract change, not a yield
   hack, requiring its own manipulation-aware review.
3. **Accept an operational token-selection constraint** (bias toward active,
   liquid tokens whose holder distribution and 5m/15m micro-structure are
   populated), turning the clean-memory question into selection rather than a
   safety/RPC change.

M3 and O1 (and M2 as a general improvement) may then proceed in a lane whose M1
mandate is one of the above; they are specified above and ready.

## Locks

No production code, schema, migration, source policy, safety contract, retrieval
or financial capability was changed. All Printer V1 locks remain intact. No
provider was contacted; the pilot was not rerun.
