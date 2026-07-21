# V2-9.7E.2 Pilot Re-readiness Audit

**Status:** READY  
**Lane:** V2-9.7E.2 — Pilot Re-readiness Audit  
**Boundary:** audit-only; no pilot, no source calls, no production repair  
**Date:** 2026-07-21  

## Final Verdict

`V2_9_7E_2_PILOT_REREADINESS_READY_FOR_ONE_REAUTHORIZED_RERUN`

This means only that **one separately authorized** V2-9.7E pilot may be attempted
safely after its own preflight. It does **not** predict two eligible live tokens,
authorize a rerun automatically, start V2-9.7F, or publish V2-9.8 commands.

## Todo / Checklist

- [x] Verify HEAD `7d6e27bb80645a2af3ea3b467e9912296efb44c6`.
- [x] Read D closeout, blocked 7E closeout, E.1 repair closeout, owners.
- [x] Confirm migration 035 terminal zero-slot behavior without two-or-none weaken.
- [x] Confirm insufficient-pool cleanup/report/replay owners from E.1 evidence.
- [x] Fresh disposable DB migrate through repository head.
- [x] Governor admissions + credential configuration presence (no secret print).
- [x] Lock / bypass / public-command scans.
- [x] Re-run E.1 + affected regressions (offline).
- [x] Write this audit; commit only if READY.

## 1. Exact Baseline

| Field | Value |
|---|---|
| Audit baseline HEAD | `7d6e27bb80645a2af3ea3b467e9912296efb44c6` |
| Baseline message | `Repair insufficient-pool campaign cleanup` |
| Prior blocked pilot baseline | `78978ea…` (D formal closeout) then pilot attempt |
| E.1 repair | committed at this HEAD |
| Prior pilot DB | `data/printer_v1_v2_9_7e_pilot.sqlite3` (exists; **not modified** this lane) |
| Prior pilot closeout (uncommitted artifact) | left untouched |

This audit made **no** production code changes and **no** network calls.

## 2. Repair Verification (E.1)

Committed evidence: `docs/printer-v1-v2-9-7e-1-insufficient-pool-terminal-cleanup-repair-closeout.md`  
Code/migration at HEAD:

### 2.1 Migration 035 — zero-slot terminalization

`migrations/035_insufficient_pool_cycle_terminal_trigger.sql`:

- Drops and recreates `printer_campaign_cycle_requires_two_slots`.
- Two-slot check applies only when leaving `PLANNED` to a **non-terminal** state.
- `TERMINAL_%` transitions may complete with **zero** slots.
- Non-terminal `PLANNED → DISCOVERING` (etc.) still requires exactly two slots.

**Two-or-none activation is not weakened:** activation still requires two eligible
candidates; 035 only allows honest zero-slot **terminal** cleanup.

### 2.2 Insufficient-pool cleanup terminalizes required surfaces

| Surface | Owner / behavior at HEAD |
|---|---|
| Discovery batch | Executor marks `TERMINAL_FAILED`; cleanup also terminalizes non-terminal batches |
| Discovery work | Executor fails open rows; cleanup terminalizes remaining open discovery work |
| Scheduler jobs | Cleanup cancels jobs linked via campaign work **or** discovery work |
| Supervision | Moves to `TERMINAL` with preserved first cause |
| Lease | Released on successful cleanup |
| Final report | Assemblable after zero-slot terminalization for this cause |

First cause remains `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` when that is the stop.

### 2.3 Zero-source replay after zero-slot termination

E.1 focused suite proves: report once, idempotent re-persist, read-only replay,
unchanged DB hash/counts, locked-capability zeros.

### 2.4 Idempotent vs conflicting cleanup

- Same-identity cleanup after terminal: **idempotent**, first-fault preserved.
- Ownership mismatch (wrong owner/id): **fails closed**.
- Same-identity different proposed cause: first-fault preserved (does not rewrite).

### 2.5 Offline verification this audit

```text
pytest tests/test_v2_9_7e_1_insufficient_pool_terminal_cleanup.py
      + 6B.5/6B.6/6B.7 + 7A + 4C + 4D + 4D.1 + 7B.5
→ 59 passed, 22 subtests passed
```

No defects found that require a new repair lane.

## 3. Fresh-Target Readiness

Disposable DB via `apply_migrations` on empty file:

| Check | Result |
|---|---|
| Integrity | `ok` |
| Foreign-key errors | 0 |
| Migration count | 35 |
| Head | `035_insufficient_pool_cycle_terminal_trigger.sql` |
| Ledger matches repository | **yes** |

A **new** pilot target (must not overwrite `data/printer_v1_v2_9_7e_pilot.sqlite3`)
can migrate through current head before a reauthorized rerun.

Prior pilot DB was inspected **read-only** only (`integrity ok`); not migrated or
resumed.

## 4. Cleanup / Report / Replay Readiness

| Capability | Ready for reauthorized pilot? |
|---|---|
| Zero-slot insufficient-pool cleanup without IntegrityError | **Yes** (E.1) |
| Final report after that stop | **Yes** (E.1) |
| Zero-source report-only replay | **Yes** (E.1) |
| Dual-token 15m/1h/4h/5m lifecycle | Unchanged latent dependency: only after **two** eligible activations |
| Full multi-window live `execute_campaign` after handoff | Still not a single monorepo live orchestrator beyond discovery handoff |

Conclusion: another pilot can **safely terminate and report** even if it again
returns `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`. That is not a yield guarantee.

## 5. Source and Scheduler Ownership

| Check | Result |
|---|---|
| Source Governor admissions (RPC/Dex/Gecko/Tracker kinds) | all **allowed** |
| Central Scheduler owner string | `CENTRAL_SCHEDULER` |
| Abstract command mode | `BOUNDED_CAMPAIGN` with injected OwnerPorts |
| Combined executor | Governor before request; Scheduler-owned discovery work |
| Public PowerShell / operational campaign CLI publication | **not** present for 7E |
| `restart_created` / successor true paths in supervision/abstract/executor | **not** set true |

Internal DI path remains: lease + Governor/Scheduler ports + combined discovery
executor + cleanup + final report + optional report-only replay.

## 6. Remaining Live-Yield Risks (not eligibility weakeners)

From the blocked V2-9.7E pilot (historical evidence, not re-run):

| Fact | Implication |
|---|---|
| Direct Pump `GAPPED`, **zero** decoded creates | Origin-eligible pool may be empty |
| Tracker free auth worked; **empty after row freshness** | Secondary pumpfun contribution may be zero |
| Combined `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` | Correct two-or-none refusal |
| Zero partial activation | Safety held |

**Do not** weaken origin, freshness, cooldown, or two-slot rules to force yield.

This audit **does not claim** two eligible live tokens are likely.

## 7. Exact Rerun Preconditions

A separately authorized V2-9.7E rerun must still complete **its own** preflight:

1. Explicit operator reauthorization for **one** pilot only.  
2. **New** pilot target path (do not overwrite prior pilot DB).  
3. Migrate through repository head including **035**.  
4. Integrity + FK PASS.  
5. Verified backup + disposable restore rehearsal.  
6. Clean launch Git provenance; tracked tree clean.  
7. Exact two-slot capacity, non-empty seed, finite ceilings.  
8. Source Governor + Central Scheduler ports available.  
9. Free credentials present if required (e.g. Tracker) — never print/commit secrets.  
10. Report directory writable and outside DB path.  
11. Internal DI only — no public PowerShell.  
12. Accept honest `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` with safe terminal report.  
13. No successor, no automatic restart, no second pilot in the same authorization.  
14. All financial/retrieval/12h/24h/5m-authority locks remain.

## 8. Money-Usefulness Contribution

Re-readiness means the factory can attempt another bounded live discovery cycle
without leaving ACTIVE leases or open discovery jobs when yield is zero. That
keeps empty outcomes **auditable** and protects corpus honesty better than
forcing two fake activations.

## 9. What Remains Locked

| Lock | Status |
|---|---|
| Automatic pilot rerun | locked (needs separate authorization) |
| V2-9.7F activation closeout | not started |
| V2-9.8 public operational command | locked |
| Retrieval / paper decisions / BUY–SELL–HOLD / WAIT / AVOID / NO_ACTION | locked |
| Positions / trades / audits / PnL | locked |
| Wallet / keys / signing / real funds / live execution | locked |
| Paid APIs | locked |
| Scoring / confidence / weighting / embeddings | locked |
| 12h / 24h work | locked |
| 5m as main outcome / independent continuation | locked |
| Dirty memory as clean | locked |
| Weakening origin / freshness / cooldown / two-or-none | forbidden |

## 10. Functionality Risks / Setbacks / Efficiency Blockers

- Live origin-create sparsity and Tracker empty-after-filter remain the dominant
  yield risks; terminal safety is fixed, not candidate supply.
- Dual-token full lifecycle PASS (15m audits, continuation split, 4h, clean
  promotion, 5m trigger/no-capture) still requires dual activation **and**
  multi-window orchestration after handoff.
- INITIAL abstract-command preflight still expects two pre-existing slots while
  INITIAL discovery creates slots on handoff; reauthorized pilot may continue to
  compose lease+executor+cleanup for INITIAL (as before) unless a later lane
  aligns 7A.
- Prior pilot residual ACTIVE state on the old pilot file is historical; do not
  resume it — use a fresh target.
- Unrelated untracked files remain out of scope.

## 11. What This Audit Did Not Do

- No pilot execution  
- No source/network calls  
- No production repair  
- No mutation of prior pilot DB or backups  
- No V2-9.7F / V2-9.8  

## Stop Boundary

V2-9.7E.2 ends at READY for **one reauthorized rerun**.  
Do **not** rerun V2-9.7E or begin V2-9.7F from this audit alone.
