# V2-9.7E.17 Live Clean-Memory Evidence and Pilot Terminal Audit

**Status:** AUDIT COMPLETE — definitive read-only trace

**Verdict:** `V2_9_7E_17_LIVE_CLEAN_MEMORY_AND_TERMINAL_AUDIT_PASS`

## Baseline

- Commit: `06140eb16aedae276ce80fdf7d121f12177ce052` (`Close final two-token
  operational pilot blocker`); clean tracked tree.
- Audit target (read-only, `mode=ro`):
  `C:\Users\dtwof\PrinterPilot\E15\printer-v1-e15-pilot.sqlite3`.
- Audit-only: static + read-only DB inspection + documentation. No provider
  contact, no DB mutation, no production/test change, no rerun, no V2-9.7F/8.

## Headline correction to the E.15 root-cause

The E.15 closeout attributed the dirty memory to the context/safety/quote
adapters being "`ALLOWED_FIXTURE_ONLY` and failing live." **The pilot DB
disproves this.** GoPlus (`safety_reference`), CoinGecko (`broad_market_context`)
and Jupiter (`paper_quote_realism`) all issued **live** requests, and GoPlus and
Jupiter succeeded (GoPlus `COMPLETE/CLEAN_DATA`; Jupiter entry+exit quote
evidence applied). The two true hard blockers were narrower:

1. `solana_rpc holder_concentration_reference` **failed** (2× rate-limited, 2×
   transport failure on the free public RPC) → the safety composite's
   `holder_concentration_label` was `HOLDER_CONCENTRATION_UNKNOWN` →
   `NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE` / `SAFETY_BLOCKED_FOR_15M_MEMORY`.
2. `dexscreener pair_market_snapshot` succeeded but returned **NULL** for the 5m
   and 15m micro-structure (`price_change_5m`, `price_change_15m`, `volume_15m`,
   `txns_15m`) and `liquidity_usd` for these essentially-untraded flat tokens →
   `SNAPSHOT_CRITICAL_FIELDS_MISSING`.

## Q1 — Per-token dirty-cause matrix

Both activated tokens are **identical** in cause. Redacted mints: T-A
`ARcD…pump` (window 1, token_id 2), T-B `BNsh…pump` (window 2, token_id 1).

| Context section | source_status / data_quality | Hard-blocks clean 15m? |
|---|---|---|
| chart_volatility | COMPLETE / CLEAN_DATA | no (clean) |
| liquidity_exit | COMPLETE / CLEAN_DATA | no (clean) |
| trading_flow | COMPLETE / CLEAN_DATA | no (clean) |
| safety | PARTIAL / MISSING_CRITICAL_DATA | **YES** — missing `holder_concentration_label` |
| micro_event | PARTIAL / MISSING_CRITICAL_DATA | **YES** — `SNAPSHOT_CRITICAL_FIELDS_MISSING` |
| chain_heat | PARTIAL / MISSING_CRITICAL_DATA | no (not in authoritative hard-blocker set) |
| market | PARTIAL / MISSING_CRITICAL_DATA | no (not in authoritative hard-blocker set) |

Authoritative hard-blocker set (`shared_window_15m_context_evidence.blockers`,
both windows): **`NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE`** and
**`SNAPSHOT_CRITICAL_FIELDS_MISSING`** → `e2q_audit_status = DIRTY_MEMORY`,
`outcome_label = OUTCOME_UNKNOWN`.

Trace per hard cause:

- **Safety:** `printer_safety_evidence_contributions` shows GoPlus
  `TOKEN_SAFETY` = `COMPLETE/CLEAN_DATA` (mint authority renounced, freeze
  disabled), but `solana_rpc HOLDER_CONCENTRATION` = `FAILED /
  MISSING_CRITICAL_DATA` (`source_failure_id` set;
  `holder_concentration_label = HOLDER_CONCENTRATION_UNKNOWN`). The composite is
  therefore `PARTIAL / ACCEPTABLE_PARTIAL_DATA`, and
  `memory_build_evidence_overlays.hard_blocking_safety_fields =
  ["holder_concentration_label"]`, `safety_15m_memory_policy_label =
  SAFETY_BLOCKED_FOR_15M_MEMORY`. Source: `solana_rpc
  holder_concentration_reference` (4 attempts, all failed: `solana_rpc_rate_limited`
  ×2, `solana_rpc_transport_failure` ×2).
- **Snapshot:** the closing `printer_token_snapshots` rows have `price_usd`,
  `volume_5m=0`, `volume_1h`, `txns_5m=0`, `txns_1h`, `price_change_1h` present
  but **NULL** `price_change_5m`, `price_change_15m`, `volume_15m`, `txns_15m`,
  `liquidity_usd`, `token_age_seconds`. For these near-dead tokens (≈4 tx/1h, 0
  volume 5m, perfectly flat price 2.172e-06, 8 flat candles) DexScreener
  supplied no 5m/15m micro-structure. The classifier reads this as
  `MISSING_CRITICAL_DATA` → `micro_event_state_label = MICRO_EVENT_UNKNOWN`,
  `held_to_15m_result_label = HELD_TO_15M_UNKNOWN`, `rug_risk_label =
  RUG_RISK_UNKNOWN`.

Independence: **each cause independently blocks clean memory** — removing either
still leaves the other. Minimum true dirty-cause set = { missing
holder-concentration (safety), missing 5m/15m snapshot micro-structure (outcome) }.

Mandatory-for mapping:

| Missing field | basic clean 15m outcome | safety claim | market/manip. context | tradeability/quote | future paper decisions only |
|---|---|---|---|---|---|
| `holder_concentration_label` | via safety hard-block | **yes** | — | — | also used downstream |
| 5m/15m `price_change`/`volume`/`txns` | **yes** (micro-event/held-to-15m) | — | partly | — | — |
| `liquidity_usd` | contributes | (rug/liq) | — | (quote realism) | — |
| broad `market_regime` | no (not hard-blocking) | — | yes | — | — |
| Jupiter route/quote | **no** | — | — | yes | yes |

## Q2 — Provider authority / readiness matrix (from the live pilot)

| Provider · request_kind | Governor rule | Live E.15 result | Scheduler-owned | Contributes | Required for clean 15m? |
|---|---|---|---|---|---|
| solana_rpc · `pumpfun_create_transaction_reference` (×8) | YES (RPC origin) | success | yes | finalized Pump origin (T3) | yes (upstream, worked) |
| solana_rpc · `holder_concentration_reference` (×4) | safety sub-field | **FAILED** (rate-limited/transport) | yes | `holder_concentration_label` (hard-blocking safety) | **yes — actual safety blocker** |
| dexscreener · `pair_market_snapshot` (×18) | `dexscreener_discovery` YES | success **but incomplete** | yes | 15m price/volume/txn/liquidity | **yes — actual outcome blocker (5m/15m NULL)** |
| dexscreener · `dexscreener_fresh_profiles` (×1) | discovery | HTTP_403 | yes | secondary discovery | no |
| geckoterminal · `trending`/`active_pool` (×2) | `ALLOWED_FIXTURE_ONLY` | HTTP_403 (attempted **live**) | yes | secondary discovery enrichment | no (non-gating) |
| goplus · `safety_reference` (×2) | `ALLOWED_FIXTURE_ONLY` | **success `COMPLETE/CLEAN`** | yes | token safety (mint/freeze auth) | contributes safety; worked |
| coingecko · `broad_market_context` (×2) | market | PARTIAL (regime UNKNOWN) | yes | broad market regime | no (not hard-blocking) |
| jupiter_quote · `paper_quote_realism` (×4) | `ALLOWED_FIXTURE_ONLY` | **applied** (entry+exit) | yes | quote/tradeability realism | no (paper-decision claim) |

**GeckoTerminal discrepancy reconciled:** the Governor evidence rules mark
`geckoterminal_*` as `ALLOWED_FIXTURE_ONLY` for *evidence contribution*, yet the
committed E.11 `LiveSecondaryDiscoveryAdapter` issues **live** GeckoTerminal
calls as non-gating secondary enrichment. Both are consistent: the live call is
enrichment whose facts never enter gates, so its HTTP_403 failure was isolated
and did **not** cause the dirty memory. The "fixture-only" flag concerns
gate/evidence contribution, not whether a non-gating live enrichment call is
attempted. E.15's implication of GeckoTerminal (and of GoPlus/CoinGecko/Jupiter)
as the dirty cause was incorrect.

## Q3 — Clean-memory contract verdict

- **Minimum evidence for a clean `WINDOW_15M`:** (a) a complete per-token 15m
  snapshot micro-structure (5m/15m price change, volume, txns; liquidity), and
  (b) valid exact-target safety including `holder_concentration_label`. The
  clean sections (chart_volatility, liquidity_exit, trading_flow) show the rest
  of the pipeline works on live data.
- **May safety / market / quote remain explicitly unknown?** Market regime being
  PARTIAL did **not** hard-block (it is not in the authoritative blocker set).
  Quote (Jupiter) did **not** block clean memory. Safety, however, **hard-blocks**
  on a single missing sub-field (`holder_concentration_label`) even though GoPlus
  already returned clean token safety — this is **tight coupling** worth review.
- **Is Jupiter required for clean outcome memory?** **No.** Entry+exit quote
  evidence was applied but is not a hard blocker; it supports execution/quote
  realism for future paper decisions only.
- **Did E.15 follow the intended contract, or is clean memory impossible by
  construction?** Clean memory is **not** impossible by construction. It was
  blocked by (1) a **transient** free-RPC rate-limit on holder-concentration and
  (2) DexScreener returning **absent** (not zero) 5m/15m fields for
  essentially-untraded, dead-flat tokens. The contract behaved mechanically
  correctly (fail-closed on missing evidence), but two coupling issues make clean
  memory unnecessarily hard: (i) one missing safety sub-field hard-blocks clean
  15m *outcome* memory; (ii) the snapshot normalizer treats **no trading
  activity** (legitimately zero) the same as **missing data**, so a genuinely
  dead/flat token cannot yield a clean `NO_PUMP` outcome memory. Neither missing
  field is spurious — the fix is reliability + absent-vs-zero semantics, **not**
  weakening a genuinely mandatory field.

## Q4 — Terminal-semantics verdict

Run config confirms operational mode runs with `operational_natural_disposition=
True`, `continuous_four_hour=True` and **`four_hour_proof_mode=True`**
(hardcoded by `run_operational`), `max_selected_tokens=2`.

- Was THIS run a valid completed operational outcome? **No** — both 15m windows
  were **DIRTY** (not clean), so regardless of terminal semantics it could not
  PASS.
- Is the *hypothetical* "two clean 15m windows, both validly stop, no natural
  continuation, report/replay/cleanup pass" a valid completed campaign outcome?
  **It should be** — that is legitimate operational memory growth (two clean 15m
  memories).
- Sufficient for a V2-9.7E PASS? For an *operational* pilot, yes it should be;
  for a *proof* it is not.
- Is 4h mandatory for every pilot? **No** — 4h completion is a **proof-mode**
  requirement, not an operational-correctness requirement.
- Does `four_hour_proof_mode` incorrectly convert honest no-continuation into
  incomplete proof? **Yes, in operational mode.** With it forced on, even two
  clean 15m windows that both validly stop are terminalized as
  `SAFE_STOP_4H_TERMINAL_INCOMPLETE` rather than `COMPLETED`. This is a genuine
  terminal-semantics coupling defect for operational mode — but **secondary** to
  the dirty-memory cause in this run.

## Q5 — Pending-discovery cleanup verdict

Classification: **`CAMPAIGN_CLEANUP_DEFECT`** (minor, inert).

Trace: the 10 PENDING jobs are `DISCOVERY_REFRESH`, `target_table =
printer_discovery_batches`, `target_id = NULL`, all `scheduled_for` the launch
instant, never locked/run. Their `job_name`s are **campaign-scoped**
(`DISCOVERY_PUMPFUN_LATEST:discovery-batch:pilot-camp:pilot-run:pilot-cyc`,
`DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE:…`, `DISCOVERY_DEXSCREENER_ACTIVE:…`).
They are campaign discovery-cadence work, not run-step lifecycle jobs, and the
operational owner performs its own finalized-origin discovery without consuming
them. Terminal cleanup cancels only run-step-linked jobs, so these
campaign-scoped discovery jobs were left PENDING. They are **inert** (execution
is TERMINAL, lock released, no scheduler process, disposable isolated target),
created no evidence and no forbidden deltas. This is a real cleanup-completeness
gap (campaign-scoped scheduler work outliving campaign terminalization), of low
severity; it is not a scheduler-ownership fault and not merely reporting.

## Q6 — Minimum safe follow-on sequence

Mandatory fixes (required for clean live memory / a valid operational PASS):

- **M1 — holder-concentration reliability / safety coupling.** Make the
  exact-target holder-concentration evidence reliably obtainable within Governor
  limits (bounded backoff, or a governed alternative), and/or review whether a
  single missing safety sub-field should hard-block clean 15m *outcome* memory
  when GoPlus safety is already clean. Do not remove genuine safety signal.
- **M2 — snapshot absent-vs-zero semantics.** Distinguish "no trading activity"
  (legitimately zero 5m/15m volume/txns/price-change) from "data unavailable," so
  a dead/low-activity token yields a clean `NO_PUMP`/flat outcome memory instead
  of `SNAPSHOT_CRITICAL_FIELDS_MISSING` dirty memory. Alternatively/additionally,
  bias selection toward tokens with sufficient activity for complete
  micro-structure.
- **M3 — operational terminal semantics.** Decouple `four_hour_proof_mode` from
  operational mode so "two clean 15m windows, both validly stop, no natural
  continuation" terminalizes as a valid `COMPLETED` operational outcome.

Optional evidence improvements (not required for clean 15m outcome memory):

- **O1 — campaign discovery-job cleanup** (Q5): cancel campaign-scoped
  `DISCOVERY_REFRESH` jobs at terminal closeout.
- **O2 — market/GeckoTerminal robustness**: reduce PARTIAL market regime and
  HTTP_403 secondary-discovery noise (non-gating).

Smallest ordered sequence:

1. **Design** — one lane covering M1, M2, M3 (and O1); explicit contract for
   mandatory vs optional 15m evidence and operational terminal completion.
2. **Implementation** — M1 + M2 + M3 (mandatory); O1 (recommended).
3. **Focused offline proof** — fixtures for: partial/rate-limited
   holder-concentration; absent-vs-zero snapshot micro-structure → clean
   `NO_PUMP`; clean-stop `COMPLETED` terminalization; discovery-job cleanup.
4. **Bounded live proof** — a short readiness-style live check that
   holder-concentration and DexScreener 5m/15m fields resolve on **active**
   tokens, confirming clean memory is achievable live.
5. **Another full pilot** — **required**, under a fresh authorization, to confirm
   clean live memory and a valid operational completion (or an honest block).

## Money-usefulness contribution

The audit replaces a wrong root-cause with a precise, evidence-backed one:
clean-memory growth is blocked by exactly two narrow, fixable issues (a transient
free-RPC rate-limit on holder-concentration and absent-vs-zero snapshot
micro-structure for dead tokens), plus a secondary operational terminal-semantics
coupling. This turns an apparently large "four adapters are fixture-only"
blocker into a small, targeted fix set, and confirms most of the live pipeline
(origin, chart, liquidity, trading-flow, GoPlus safety, Jupiter quote) already
works on live data — materially de-risking the path to real clean memory.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Setback (primary):** clean live 15m memory currently requires both a reliable
  holder-concentration RPC read and complete DexScreener 5m/15m micro-structure;
  fresh/untraded tokens and free-RPC rate-limits break these.
- **Risk (contract coupling):** one missing safety sub-field hard-blocks clean
  outcome memory; the snapshot normalizer conflates zero-activity with
  missing-data — both make clean memory harder than necessary and should be
  reviewed without weakening genuine signal.
- **Defect (secondary):** operational mode inherits `four_hour_proof_mode`, so an
  honest no-continuation clean run is mislabeled `SAFE_STOP_4H_TERMINAL_INCOMPLETE`.
- **Cleanup nuance:** 10 inert campaign-scoped `DISCOVERY_REFRESH` jobs remain
  PENDING after terminal closeout (`CAMPAIGN_CLEANUP_DEFECT`, low severity).
- **Read-only access:** the pilot DB opened cleanly `mode=ro`; no mutation
  occurred; source and corpus untouched.

## Readiness for the next design lane

**READY for a bounded design lane** addressing M1–M3 (and O1). The audit is
complete and definitive; the mandatory fixes are small and localized, separated
from optional evidence improvements. No fix was implemented here. V2-9.7F, V2-9.8,
the operational memory-growth command, and retrieval/decision/financial
capabilities remain locked and were not started; providers were not contacted;
the pilot was not rerun.
