# Printer V1 A4 Failed-Pump Repair Closeout

Status: `A4_WIRING_PASS_LIVE_SAMPLE_BLOCKED`

Date: 2026-07-12

Scope: A4 `FAILED_PUMP` only. GROUP_A was not started.

## Audit Finding

The existing `derive_failed_pump_bucket()` helper already implemented the
approved categorical market meaning:

- the prior observation was A1, A2, or A3;
- the current observation no longer satisfies the existing fast-tier gate;
- current liquidity remains above the existing near-zero threshold, so a full
  liquidity-removal case remains C3 rather than A4.

No A4 threshold needed repair. The production gap was the deferred evidence
handoff: `assign_bucket()` received only a current candidate, while the latest
persisted governed observation for the same mint and pair was available only
in `printer_discovery_candidates` and its linked source-response row.

## Design Decision

The production discovery selector now evaluates A4 only after loading the
latest exact prior discovery row from the same DB. The evidence contract is:

1. Both mint and pair identities are non-null and match exactly.
2. Prior and current evidence have distinct governed source-response IDs.
3. Both evidence records have source request and response IDs.
4. Both are `COMPLETE / CLEAN_DATA`.
5. Both have valid observation times and current is strictly newer.
6. The prior persisted row derives as A1, A2, or A3.
7. The current row satisfies the unchanged failed-pump helper.

No duration threshold was invented. "Stale" remains a categorical source/data
quality rejection, and temporal ordering only proves that evidence is genuinely
prior versus current.

## Minimal Repair

- Added `evaluate_failed_pump_evidence()` as the fail-closed wrapper around the
  existing A4 helper.
- Added an exact mint/pair DB lookup joining prior discovery evidence to its
  governed source response.
- Applied the wrapper before duplicate/resurfacing gates so a genuine A-tier to
  A4 transition can enter the existing distinct-evidence path.
- Preserved the validated A4 request, response, observation, source, prior-row,
  and prior-bucket fields through discovery normalization and selection-batch
  metadata JSON.
- Stripped all source-supplied `a4_*` fields before evaluation. A source cannot
  self-assert the internal A4 evidence marker.
- Kept A3 independent and unchanged. No A3 threshold, T3 rule, pair-age rule,
  or recent-active rule changed.

No migration was added.

## Deterministic Tests

Focused tests prove:

- valid clean exact prior/current evidence produces `A4 / FAILED_PUMP`;
- missing prior evidence fails closed;
- stale, failed, or dirty evidence fails closed;
- mint or pair mismatch fails closed;
- missing request/response/discovery provenance fails closed;
- same-response and non-newer evidence fail closed;
- current evidence that remains fast does not qualify;
- liquidity removal does not qualify as A4;
- a non-A prior bucket does not qualify;
- incomplete or source-forged A4 markers cannot force classification;
- two governed fixture cycles through the production selector persist A1 first
  and A4 second for the exact same mint/pair;
- A4 provenance survives candidate persistence and selection metadata;
- memory, retrieval, paper, position, trade, and audit rows remain zero.

## Bounded Isolated Proof

The bounded proof used one temporary isolated SQLite DB and two governed fixture
responses for one synthetic Solana mint/pair:

| Cycle | Evidence | Result |
|---|---|---|
| Prior | liquidity `8000`, 5m volume `2500`, 5m transactions `14` | `A1 / FAST_PUMP_FOLLOW` |
| Current | liquidity `2000`, 5m volume `50`, 5m transactions `2` | `A4 / FAILED_PUMP` |

The current evidence retained liquidity above the existing C3 threshold but no
longer met either fast-tier activity threshold. The second response was newer,
clean, governed, and linked to a distinct source request/response. The persisted
selection metadata retained the prior discovery row ID and separate prior and
current source identities.

The proof created only isolated source, discovery, tracking handoff, and
selection evidence required by the existing audit-safe path. It created zero
memory windows, retrieval queries/matches, paper decisions, paper positions,
paper trade events, and paper trade audits. No PnL table is present in the test
schema.

## Live-Sample Audit

The operator DB was inspected read-only before closeout:

- database: `data/printer_v1.sqlite3`;
- discovery rows: `15`;
- exact mint/pair groups: `15`;
- repeated exact mint/pair groups: `0`;
- existing potential A-tier to A4 sequences: `0`.

Its SHA-256 remained unchanged before and after inspection:

`97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb`

No live source retry was appropriate: a genuine A4 observation requires an
already-governed prior A-tier row and a later collapse row for the same pair.
The current operator evidence contains no such repeated pair. The absence of a
live A4 sample is therefore a market/evidence-history blocker, not a production
wiring blocker.

## Verdict

`A4_WIRING_PASS_LIVE_SAMPLE_BLOCKED`

The A4 production handoff is repaired and bounded-fixture proven without
changing its meaning or thresholds. A genuine live A4 observation remains
blocked until normal governed collection records an A1/A2/A3 observation and a
later qualifying collapse for the same mint and pair.

GROUP_A remains unstarted. Memory, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL, wallets, keys, paid APIs, execution, scoring,
ranking, confidence, and weighted logic remain locked.

## Remaining Blocker And Next Step

Do not retry sources merely to force A4. The smallest next action is an
operator decision to wait for a naturally occurring governed repeated-pair
sequence and run one bounded observation proof. Do not begin GROUP_A without a
separate explicit lane.
