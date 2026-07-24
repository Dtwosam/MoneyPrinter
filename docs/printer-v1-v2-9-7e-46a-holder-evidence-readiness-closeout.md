# Printer V1 — V2-9.7E.46A Holder-Evidence Readiness Closeout

**Verdict: `V2_9_7E_46A_BLOCKED_HOLDER_SOURCE`.**

E.46A added and offline-proved the missing canonical zero-transport holder-source
preflight plus the explicit `PILOT_INPUT_READINESS` mode. The one authorized live
readiness execution used the committed production runner and stopped honestly at
`PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED`. It did not create `PILOT_INPUT_READY`,
activate tokens, or start lifecycle. This verdict does not authorize an E.46 full
pilot and does not unlock V2-9.7F.

- **Starting commit:** `614f5541ee8e0e26a6d9be7e8a0195479544208b`.
- **Live execution HEAD:** `194de75907f983a0e226e5be7ba3daf76b0c5ec3`.
- **Ending commit:** the amended lane commit containing this document; exact SHA is
  reported by the committing task.
- **Live date:** 2026-07-24.
- **Implementation classification:** `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`.
- **Live blocker classification:** adopted holder-source transport unavailable;
  no product-code repair was justified after the live execution.

## Changes

- `two_token_operational_pilot_runner.py` now validates Git provenance and then
  immediately calls `assert_readiness_source_contract_preflight()` before mode/path
  resolution, DB preparation, supervision, lock creation, authorization
  consumption, owner invocation, or provider contact.
- Any missing secret, source-contract drift, or budget-contract drift is surfaced
  only as the generic `readiness source contract preflight blocked` terminal. The
  runner does not copy the secret, authenticated URL, environment mapping, or an
  upstream exception into its result.
- `PILOT_INPUT_READINESS` is a canonical mode on the existing authoritative owner.
  It invokes `run_operational(..., stop_before_lifecycle=True)` and uses the same
  graduated supply, front door, holder reserve, activation, readiness, replay, and
  cleanup owners as the full path.
- `FULL_PILOT` retains its previous call surface: it does not receive
  `stop_before_lifecycle`.
- Focused tests cover missing-key fail-closed behavior, independent source and
  budget drift, secret-bearing upstream exception redaction, fake-key progression,
  readiness-only containment, full-pilot preservation, two-holder readiness,
  zero-source replay, and cleanup/no-successor behavior.

No Helius adapter, endpoint, retry policy, evidence threshold, source budget,
continuation law, memory-quality rule, or permanent V1 lock was changed.

## Official contract recheck

No material contract drift was found before implementation or live execution.

- Python still defines an explicit subprocess `env` mapping as the child
  environment rather than an overlay; current handling therefore continues to
  preserve the inherited process environment and inject presence only in the
  fresh executor: <https://docs.python.org/3/library/subprocess.html>.
- Helius still documents query-parameter API-key authentication and a Free-plan RPC
  ceiling of 10 requests per second: <https://www.helius.dev/docs/api-reference/authentication>
  and <https://www.helius.dev/docs/billing/rate-limits>.
- Solana still documents finalized `getTokenLargestAccounts` returning the 20
  largest token accounts and finalized `getTokenSupply` returning amount/decimals
  supply data: <https://solana.com/docs/rpc/http/gettokenlargestaccounts> and
  <https://solana.com/docs/rpc/http/gettokensupply>.

The fixed public RPC primary and fixed Helius Free backup contract remains intact.
No endpoint rotation, provider racing, hidden retry, paid RPC, or arbitrary free
RPC endpoint was added.

## Offline proof

The final source/test state passed:

- E.14/E.22/E.24/E.28/E.44 and all five E.45 focused/regression files:
  **77 passed in 607.64 seconds**, stopped on first relevant failure (`-x`), no
  stderr.
- Direct E.44 readiness-owner path plus E.33 canonical-mode surface:
  **3 passed**.
- Final E.46A runner preflight/readiness slice after exact call-boundary placement:
  **5 passed, 2 subtests passed in 99.95 seconds**.
- Changed-file `py_compile`: PASS.
- Changed-module import smoke: PASS.
- `git diff --check` and cached diff check: PASS.

The tests prove that missing key or contract/budget drift creates no target DB,
backup, restore rehearsal, lock, owner call, or external request; fake-key presence
permits progression without persistence; the readiness mode cannot create windows,
memories, retrieval, decisions, positions, trades, audits, or PnL; the actual owner
writes `PILOT_INPUT_READY` only for two holder-valid candidates; replay is
zero-source; locks are released; and no restart/successor is created.

## One bounded live readiness execution

| Field | Evidence |
|---|---|
| Authorization / execution | `e46a-readiness-20260724-194de75` |
| Campaign | `e46a-readiness-20260724-194de75-campaign` |
| Run | `e46a-readiness-20260724-194de75-campaign-run` |
| Cycle | `e46a-readiness-20260724-194de75-cycle` |
| Mode | `PILOT_INPUT_READINESS` |
| HEAD | `194de75907f983a0e226e5be7ba3daf76b0c5ec3` |
| Isolated artifacts | `operator-runs/v2-9-7e-46a/readiness-1-20260724-194de75/` |
| Immutable export | `pilot-export:readiness-1-20260724-194de75:attempt.sqlite3`; 10 rows; provenance hash `f41671d85a8c333ada041c397d323cc8e5de196de405d16b2d9c33e7dcd82469` |
| Zero-source preflight | `READY`; issues 0; external requests 0; secret material recorded false |
| Wall clock | 875.3 seconds shell wall time; approximately 850.7 seconds supervised execution |
| First terminal cause | `PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED` |
| Terminal | `GOVERNED_SAFE_STOP`; lifecycle not started |

Exactly one readiness execution was invoked. There was no retry, rotation, race,
restart, successor, automatic continuation, or sustained lifecycle launch.

## Complete candidate and rejection ledger

The frozen exact-pool front-door set contained four candidates. “LATEST” means
confirmed by this execution's bounded migration refresh; “PERSISTED” means exported
from the durable registry before that refresh.

| Partition | Mint | Exact PumpSwap pool | Fresh liquidity | Result |
|---|---|---|---:|---|
| LATEST | `3Q4kstfxFuLmw5HK64hZzjhYQeRCWJVjLwMTNmUWpump` | `exnjVx9nwRNXUdooL8X2pFYTuUGijT9MWFuYHeGUoxQ` | `$11,420.16` | Front-door eligible; holder source blocked |
| LATEST | `GStYV2g29fETx4FyrbdyiTenwnfVTYGa1B9CUANPpump` | `6Jgr2pgFEXGLcHBjo2Lc2CTiCccX3qGFTzY1jBm14NHf` | `$10,402.98` | Front-door eligible; holder source blocked |
| PERSISTED | `Gds9MSe4H8SMcPwd5sqMx1n8ak1nkQRCWnQftKyHpump` | `HSoMcpnQLnC6h4HvXVfhKZqqYhGPRrvYegCdDBv3sSMJ` | `$40.41` | Rejected below `$3,000` |
| PERSISTED | `9XuWt4W2WxfJMEL8pkB5bEavhoyBjAMoL7cDEkspump` | `PKztZQTMFRFA6ERj51ggDT764k1bnT32hd6ovDZDddE` | `$2,002.31` | Rejected below `$3,000` |

The live migration rounds added four confirmed exact PumpSwap registry rows and the
attempt registry ended with 14 rows. The eligible universe was therefore two real
LATEST candidates and zero `$3,000+` PERSISTED candidates. In addition to the
first terminal holder-source block, this attempt could not have satisfied the
required mixed LATEST/PERSISTED pair. No candidate or rejection was silently
promoted.

## Holder funnel

Both front-door-eligible candidates were evaluated in deterministic order. Each
used exactly the fixed order GoPlus → public Solana RPC → Helius Free backup:

| Candidate | GoPlus | Public RPC | Helius Free | Holder result |
|---|---|---|---|---|
| `3Q4kst…pump` | transport failure | `getTokenLargestAccounts(finalized)` transport failure | authenticated fixed-backup transport failure | `MISSING_CRITICAL_DATA`; exact target false; concentration unknown |
| `GStYV2…pump` | transport failure | `getTokenLargestAccounts(finalized)` transport failure | authenticated fixed-backup transport failure | `MISSING_CRITICAL_DATA`; exact target false; concentration unknown |

The persisted reserves were already below the exact-pool liquidity floor, so no
lawful same-partition `$3,000+` replacement remained. The source owner failed
closed. It did not label either token holder-eligible and did not weaken the gate.

Holder-operation ledger:

- ceiling 45;
- governed requests 19;
- underlying transport operations 19;
- zero-transport operations 9;
- reserved snapshot operations 2;
- reserved snapshot-completion operations 4.

## Activation, readiness, and forbidden capabilities

- Atomic activation: not attempted.
- `PILOT_INPUT_READY`: zero rows; no immutable bundle was created.
- Lifecycle: not started; zero factory runs, windows, or fingerprints.
- Continuation and 5m support: not evaluated.
- Clean/dirty/blocked memories and promotion: zero.
- Retrieval queries/matches: zero.
- Paper decisions and decision audits: zero.
- Paper positions, trade events, trade audits, paper audit reports, and PnL: zero.

The terminal result's forbidden-delta map was empty because the lifecycle owner
never started; direct SQLite reconciliation independently proved every forbidden
row count above was zero.

## Source and scheduler accounting

| Source | Requests | Responses | Failures |
|---|---:|---:|---:|
| DexScreener | 5 | 5 | 0 |
| PumpPortal | 3 | 3 | 0 |
| PumpSwap verification | 4 | 4 | 0 |
| GoPlus | 2 | 0 | 2 |
| Public Solana RPC | 2 | 0 | 2 |
| Helius Free | 2 | 0 | 2 |
| **Total** | **18** | **12** | **6** |

All successful supply/front-door evidence was fresh and exact-target. All six
holder-context failures were durably recorded without secret material. Scheduler
jobs and campaign-scheduler work were both zero because lifecycle never launched.
No retrieval or financial scheduler work existed.

## Replay, cleanup, integrity, and redaction

- Deterministic pre-lifecycle replay: true; new source calls 0.
- Proof lock: released and absent.
- Pending/running lifecycle run steps: 0.
- Running scheduler jobs: 0.
- Restart/successor: false/false.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 violations.
- Candidate source DB remained unchanged; preparation backup was byte-identical
  and restore rehearsal passed.
- Five retained attempt files were scanned in memory: secret-value hits 0,
  authenticated-URL marker hits 0, environment-name hits 0.
- No stdout/stderr file containing provider material was created.

Residual cleanup observation: the pre-lifecycle campaign shell remains recorded as
campaign `RUNNING`, campaign-run `RUNNING`, and cycle `PLANNED`, while authoritative
proof supervision is terminal `GOVERNED_SAFE_STOP`, its lock is released, and all
actual scheduler/lifecycle work is zero. This metadata does not create a restart or
successor, but it should be reconciled before calling a later full-pilot cleanup
proof complete.

## Money-usefulness contribution

The lane closes a real operator-safety gap: a fresh executor now proves its adopted
holder-source secret/budget contract before consuming authorization or touching an
attempt DB, and the canonical readiness mode can exercise the entire live input
funnel without risking accidental lifecycle launch. The live block also prevented
fake money-usefulness: liquid tokens were not promoted without exact holder
evidence. No memory, paper result, trade, or profit claim is made.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk:** authenticated Helius backup presence passed preflight,
  but the fresh executor could not reach GoPlus, public RPC, or Helius during the
  holder funnel. Holder-valid readiness remains live-unproven in this lane.
- **Setback:** neither persisted reserve remained above `$3,000`, so this execution
  lacked the required mixed LATEST/PERSISTED eligible pair independently of the
  holder-source outage.
- **Cleanup risk:** the non-lifecycle campaign shell retains RUNNING/PLANNED metadata
  after proof supervision terminates. It has no active lock, scheduler work, or
  lifecycle run, but later terminal reconciliation should make this state explicit.
- **Efficiency blocker:** the one honest attempt consumed about 14.6 minutes of
  bounded migration/front-door/holder wall time before the common holder transport
  outage was known. This is not permission to cache stale evidence, race providers,
  or add retries/endpoints.

## Remaining locks and next lane

All permanent Printer V1 locks remain in force: Solana memecoin only, paper only,
no wallets/private keys/funds/live execution, no paid APIs, no scoring/ranking/
confidence/weighted logic, no Source Governor or Central Scheduler bypass, no dirty
memory for decisions, and no BUY/SELL/HOLD, positions, trade, audit, or PnL unlock.

A separate E.46 full-pilot retry is **not ready**. It requires a fresh executor in
which the adopted holder sources actually return valid exact-target evidence, a
fresh mixed LATEST/PERSISTED `$3,000+` pair, fresh identities/evidence, and explicit
reconciliation of the residual pre-lifecycle campaign metadata. This closeout does
not authorize that retry. V2-9.7E remains active; V2-9.7F is not ready and was not
started.