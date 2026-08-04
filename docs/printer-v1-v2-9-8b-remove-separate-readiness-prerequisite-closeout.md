# Printer V1 V2-9.8B Remove Separate 15m Readiness Prerequisite Closeout

Date: 2026-08-03

## Verdict

```text
V2_9_8B_REMOVE_SEPARATE_READINESS_PREREQUISITE_PASS
```

Separate live pre-lifecycle readiness is no longer mandatory for normal
`WINDOW_15M` final-authorization preparation or independent review.

## Starting baseline

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Required HEAD | `1be704c8c618bbb72a34b2bd5b2e86d4c02a059a` |
| Subject | `Repair full 15m readiness blockers` |
| Parent | `5d995d0bf208347e6d952a0332dca485f8b0b286` |
| Tracked tree | Clean (Migration-050 package intentionally untracked, untouched) |
| `/private/tmp/mp-preclaim` | Untouched |

## Operator decision (standing)

Printer must not require or run any separate:

* live readiness proof;
* discovery-only qualification;
* pre-lifecycle readiness campaign;
* readiness certificate generation run;
* provider-consuming qualification before the real 15-minute attempt.

The real `WINDOW_15M` command remains responsible for discovering and validating
candidates before lifecycle entry. Honest shortage remains an acceptable terminal
outcome.

## Production owners (from `1be704c`)

| Role | Owner | Change |
| --- | --- | --- |
| Pre-lifecycle readiness artifact validation | `pre_lifecycle_readiness_artifact.py` | Left dormant; validator retained for optional integrity |
| Final-authorization preparation / independent review gate | `pre_lifecycle_readiness_authorization_gate.py` | **Absent artifact no longer blocks** |
| Package apply / provenance / one-use | `git_provenance_authorization_manifest.py` / `window_15m_one_shot_wrapper.py` | Unchanged |

## Contract after correction

1. Fresh authorization preparation succeeds without a readiness artifact.
2. Independent review succeeds without a readiness artifact.
3. Existing provenance, branch, HEAD, package-hash, one-use marker, and
   independent-review rules remain mandatory.
4. Ordinary live discovery, Pump/PumpSwap identity, liquidity ($3,000 floor),
   holder, tracking/cooldown, two-token capacity, Source Governor, Central
   Scheduler, cleanup, and safe-stop checks remain on the real run path.
5. Fewer than two eligible candidates still produce an honest pre-lifecycle
   shortage (runtime path unchanged by this gate correction).
6. No candidate is fabricated or made eligible by this correction.
7. Source budgets, retries, holder rules, selection, Scheduler ownership, and
   Source Governor ownership are unchanged.
8. Other `1be704c` repairs retained (DexScreener schema diagnostics, durable
   `campaign_window_registration`, Lane K promotion alignment, clean-memory
   quality consistency).

## Files changed

| Path | Role |
| --- | --- |
| `src/printer_v1/operator_cli/pre_lifecycle_readiness_authorization_gate.py` | Gate: absent → `NOT_REQUIRED` PASS; optional supplied artifact still validated |
| `tests/test_v2_9_8b_pre_lifecycle_readiness_artifact_and_auth_gate.py` | Updated gate matrix for non-mandatory contract |
| `tests/test_v2_9_8b_remove_separate_readiness_prerequisite.py` | Focused proof (new) |
| `docs/printer-v1-v2-9-8b-remove-separate-readiness-prerequisite-closeout.md` | This closeout |

## Focused checks run

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_remove_separate_readiness_prerequisite.py \
  tests/test_v2_9_8b_pre_lifecycle_readiness_artifact_and_auth_gate.py \
  tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  -q --tb=short
# 110 passed

.venv/bin/python -m compileall -q \
  src/printer_v1/operator_cli/pre_lifecycle_readiness_authorization_gate.py \
  src/printer_v1/operator_cli/pre_lifecycle_readiness_artifact.py \
  tests/test_v2_9_8b_pre_lifecycle_readiness_artifact_and_auth_gate.py \
  tests/test_v2_9_8b_remove_separate_readiness_prerequisite.py

git diff --check
```

| Check | Result |
| --- | --- |
| Auth prep without readiness artifact | PASS (`NOT_REQUIRED`) |
| Independent review without readiness artifact | PASS |
| Gate does not call readiness validator when artifact is absent | PASS (mock) |
| No provider / qualification call in gate module | PASS (AST) |
| Provenance / package / marker / one-use rules (existing suite) | PASS |
| Optional invalid supplied artifact still blocked | PASS |
| Python compile | PASS |
| `git diff --check` | PASS |

## Explicit non-changes

* No DexScreener / Lane K / campaign registration / quality-consistency reverts
* No liquidity floor change
* No wrapper one-use law change
* No readiness implementation deletion (dormant OK)
* No push
* Migration-050 package and `/private/tmp/mp-preclaim` untouched

## Next step authorized by operator

After this commit: one fresh one-use `WINDOW_15M` authorization (no readiness
artifact) and exactly one real wrapper application under that authorization.
