# V2-9.7D.5A Trajectory, Transition, and Checkpoint Objects Closeout

## Scope

V2-9.7D.5A adds pure, immutable representations for token-local trajectories,
fixed phase and reversal claims, visible evidence gaps, scheduled checkpoints,
and approved-event checkpoints linked to the V2-9.7D.4B support trigger.

The objects consume already-governed observations. They do not fetch data,
schedule work, mutate a database, create memory, activate retrieval, issue a
paper decision, or perform any financial action.

## Money Usefulness

These objects make later research more honest by preserving exactly what was
known at a checkpoint. They prevent later price action from rewriting the
evidence cutoff, eligible evaluation paths, gaps, phases, or reversals. An
observed peak is retained only as a chart fact; whether an exit was realistically
capturable remains explicitly unknown and requires later research.

## What Improves

- Ordered observations carry exact campaign, run, cycle, slot, token, mint,
  pair, root-15m lifecycle, main-window, scheduler, and source provenance links.
- Fixed phase, reversal, checkpoint-kind, and evaluation-path vocabularies
  replace open-ended labels; unsupported phase and reversal labels preserve an
  explicit unknown state.
- Duplicate, conflicting, out-of-order, foreign, untraceable, post-cutoff, and
  gap-crossing evidence fails closed.
- Scheduled cadence/deadline checkpoints and 4B approved-event checkpoints are
  distinct immutable forms.
- Later evidence produces a separate immutable evaluation and cannot rewrite
  the original checkpoint.

## Still Locked

Source fetching, scheduler execution, orchestration, database mutation, memory
creation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, wallets, keys, signing, and live execution remain locked. The 5m window is
support-only and has no main-window, continuation, retrieval, decision, or
financial authority.

## Proof

Focused tests cover every fixed vocabulary, unknown preservation, chronology,
identity and provenance mismatch, visible gaps, exact supporting observations,
gap-crossing claims, cutoff enforcement, all fixed evaluation paths, scheduled
checkpoints, exact 4B event linkage, immutability, later-evidence separation,
observed-peak semantics, and permanent 5m non-authority.

### Adjacent Verification Repair

The prior combined command ran the snapshot, main-window cadence,
snapshot-continuity/provenance, and 4B trigger-linkage files in one subprocess
with a 240-second timeout. Its captured output ended with
`subprocess.TimeoutExpired`; no assertion failure was reported. Git inspection
confirmed `a7b4cf7` remained HEAD, the three 5A files were untracked, and no
tracked adjacent production or test file had been modified.

A repository-local temporary directory was created and deleted successfully
before pytest. Each adjacent file was then collected and run independently with
pytest cache disabled and `-vv -s --durations=0 --maxfail=1`:

| Adjacent suite | Collection | Result | Pytest duration | Measured wall time |
| --- | ---: | ---: | ---: | ---: |
| `tests/test_phase6_token_level_snapshots.py` | 21 | 21 passed | 53.32s | 53.845s |
| `tests/test_post_lane10_lane_u_cadence_policy.py` | 105 | 105 passed | 211.66s | 212.298s |
| `tests/test_v2_6_1_snapshot_cadence_continuity.py` | 22 | 22 passed | 0.11s | 0.595s |
| `tests/test_v2_9_7d_4b_conditional_support_only_5m_capture.py` | 13 | 13 passed, 27 subtests passed | 0.11s | 0.547s |

The timeout was cumulative, not a hang or regression. The main-window cadence
suite was the consumer: its
`LaneURunnnerTwoIntervalTests::test_no_warning_at_or_above_target` test took
94.01 seconds. Together, the first two suites required about 266 seconds of wall
time, so the original combined 240-second subprocess bound necessarily expired
before the remaining two suites could complete. All setup, execution, teardown,
and temporary-directory cleanup completed normally in the repaired verification.

## Functionality Risks / Setbacks / Efficiency Blockers

- The representations deliberately do not infer phases or reversals; producing
  those claims remains a later, separately approved research concern.
- Realistic exit capturability remains unknown because this lane has no execution
  realism model and must not infer profit from chart peaks.
- Visible gaps block dependent claims rather than interpolating missing evidence,
  so sparse campaigns may yield fewer usable trajectory descriptions.
- Objects are in-memory contracts only; persistence and operational integration
  remain outside this lane.

## Verdict

V2_9_7D_5A_TRAJECTORY_TRANSITION_CHECKPOINT_OBJECTS_PASS
