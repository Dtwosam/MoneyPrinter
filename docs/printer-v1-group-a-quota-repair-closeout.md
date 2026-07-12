# Printer V1 Group A Quota Repair Closeout

Status: `GROUP_A_QUOTA_PASS`

Date: 2026-07-13

Scope: Group A selection/quota handoff only. GROUP_A classification thresholds,
A3, A4, memory, retrieval, and paper features were not expanded.

## Audit Finding

Production discovery already generated A3 and A4 categorically from governed
evidence, but the discovery command built only an informational quota view over
all accepted candidates. It did not compose a bounded quota-valid view. Excess
A1 candidates could therefore keep the Group A quota invalid even when a real
A3 or A4 was available. The validator also lacked the documented Group A total
and share caps and the complete six-plus Group B requirements.

The missing handoff was selection composition, not an A3/A4 classifier defect.
No threshold change was required.

## Minimal Repair

- Added a pure bounded quota composer over active and audit-only candidates.
- Removed caller-supplied `primary_bucket` before re-running the real classifier.
- Preserved the Group A cap of four, the 40 percent share cap, and A1 max two.
- Required at least one classifier-produced A2/A3/A4 whenever Group A is present.
- Preserved six-plus requirements for Group B, a B2/B4 decay case, Group D/D1,
  and WATCH_ONLY, including a minimum 30 percent Group B share.
- Preserved exact mint/pair deduplication and governed source-response identity.
- Limited audit-only supplementation to the D1/WATCH_ONLY quota dimensions.
- Kept audit-only candidates out of active persistence, tracking, scheduler, and
  rotation-state paths.
- Added `group_a_quota_report` to the bounded discovery payload.

The composer is pure and does not replace or weaken the existing cooldown and
rotation gates. No migration was added.

## Deterministic Production-Path Proof

The proof used a temporary isolated SQLite DB, one governed discovery fixture,
and governed fixture T3 enrichment. Six candidates entered the production
discovery/classification path:

| Kind | Final bucket | Candidate mode | Quota contribution |
|---|---|---|---|
| Fast pump | A1 | ACTIVE_TRACKING | Group A winner |
| Older declining fast candidate with T3 | A3 | ACTIVE_TRACKING | Group A trap/failure requirement |
| Momentum decay | B2 | ACTIVE_TRACKING | Group B decay requirement |
| Sustained activity | B1 | ACTIVE_TRACKING | Group B share |
| Consolidation | B3 | ACTIVE_TRACKING | Group B share |
| Dead/low-activity candidate | D1 | AUDIT_ONLY / WATCH_ONLY | Group D, D1, WATCH_ONLY |

Final composition was `{A1: 1, A3: 1, B1: 1, B2: 1, B3: 1, D1: 1}`.
The result passed every quota rule. Group A was 2/6, Group B was 3/6, A1 stayed
below its cap, and the A3 retained real T3 provenance. A deliberately supplied
false A3 bucket marker was ignored and reclassified as B1.

## Safety And DB Deltas

The proof DB created only the governed source/discovery rows required by the
existing audit-safe command. The audit-only D1 created:

- zero token persistence rows for its mint;
- zero tracking queue rows;
- zero scheduler jobs;
- zero selection rotation-state rows.

The proof asserted zero rows in memory windows, retrieval queries/matches,
paper decisions, paper positions, paper trade events, and paper trade audits.
No PnL table exists in the isolated test schema. The persistent operator DB was
not opened for writing and remained unchanged.

## Tests And Checks

Focused coverage proves classifier-only bucket use, Group A caps, Group B and
decay requirements, deterministic six-candidate production composition, A3/A4
handoff preservation, audit-only isolation, cooldown/rotation preservation, and
controlled discovery compatibility.

## Verdict

`GROUP_A_QUOTA_PASS`

Production-generated A3/A4 classifications can now satisfy the existing Group A
quota through a bounded classifier-derived composition path. The proof does not
claim a timing-dependent live A3/A4 sample and does not unlock any downstream
capability.

## Remaining Blockers

Live A3 and A4 observations remain dependent on naturally qualifying governed
market samples. Memory, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, wallets, keys, execution, paid APIs, scoring, ranking,
confidence, and weighted logic remain locked. GROUP_A work is complete for this
bounded quota handoff only; no later lane was started.
