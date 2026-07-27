# Printer V1 V2-9.8B.13A — Failed-Selection Residue Audit

## Verdict

```text
V2_9_8B_13A_FAILED_SELECTION_RESIDUE_AUDIT_PASS_NO_DEFECT
```

Read-only SQLite inspection proves that the failed first production selection
left durable pre-lifecycle evidence, but none of that residue made either mint
ineligible for the second attempt. Their exclusion was solely the deterministic
six-candidate refresh-batch boundary. No code repair is justified or made.

This audit did not run production, call a live source, mutate the authoritative
database, retry either campaign, or unlock any downstream capability.

## Baseline and scope

| Item | Value |
|---|---|
| Repository HEAD | `91da8238c5b02eb7ab87354ac24f45b36fcf8471` |
| Tracked tree at gate | clean |
| First attempt | `20260727T001520Z-d513e21260b5` |
| Second attempt | `20260727T010656Z-0a54a31b6f2d` |
| Audited mints | `UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump`; `7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump` |
| Inspection mode | SQLite `-readonly` / URI `mode=ro` only |

## Per-mint durable trace

| Surface | `UUdf…pump` | `7tKKxa…pump` | Eligibility effect |
|---|---|---|---|
| Graduated registry | `PUMPSWAP_GRADUATED_CONFIRMED`, `LATEST_GRADUATED`, observation count 1 | same | eligible registry identity retained |
| Exact PumpSwap pool | `7PZL3Fo1bHSkKiSymZsRHjhX4swn1n9WHvupQ4qQcnFR` | `GocsVH4qcQfPsHqgCDiZPWRmq1Q1FBZn2Qv7BVKbgEix` | exact identities unchanged |
| Market-floor state | `LIQUIDITY_PROVEN`, `$23,959.78` | `LIQUIDITY_PROVEN`, `$8,132.78` | neither below-floor nor unproven |
| Market-floor cooldown | `NULL` | `NULL` | no market cooldown exclusion |
| Token / pair | token 18 / pair 22, `TRACK_NORMAL` | token 19 / pair 23, `TRACK_NORMAL` | identities remain usable |
| First discovery eligibility | `first_failed_eligibility_gate = NULL` | same | no failed gate recorded |
| First selection rows | two `SELECTED` rows: discovery selection + origin activation | same | successful selection evidence, not rejection |
| STNP classification | `same_token_new_pair = 0`; classification `NULL` | same | no STNP exclusion |
| Selection rotation state | no row | no row | no selection cooldown exists |
| Explicit token/pair cooldown check at second batch sequence | `(True, '')` | `(True, '')` | both pass |
| Tracking queue | row 16 `QUEUED`, `TRACK_NORMAL`, `CLEAN_DATA` | row 17, same | retained handoff; not consulted by front-door eligibility |
| Lifecycle events | no row | no row | no cooldown/archive event |
| First campaign token slot | slot 1 `SELECTED` | slot 2 `SELECTED` | pre-lifecycle residue only |
| First campaign factory/window state | no factory run; no campaign windows | same | first attempt failed before lifecycle |
| Second campaign token slot | none | none | neither mint entered second selection |

The immutable retained readiness bundle is
`20260727T001520Z-d513e21260b5-campaign-run:20260727T001520Z-d513e21260b5-cycle:pilot-input`.
It records both exact mints/pools, valid holder evidence, source ledger
`18 / 45`, and `PILOT_INPUT_READY`. Its expiry is historical evidence and is not
used to authorize a new production lifecycle.

## Second-attempt deterministic refresh boundary

The production front door reads the graduated registry, partitions rows into
this-cycle `LATEST` and durable `PERSISTED`, applies seed-specific Fisher-Yates
ordering within each category, and admits at most
`front_door_max_candidates = 6`. Replaying that committed function read-only
against the eight-row registry with seed
`20260727T010656Z-0a54a31b6f2d` produced:

| Order | Mint | Category | Second-attempt disposition |
|---:|---|---|---|
| 1 | `ASmoyDqsuLedJHfUePWokcmitFmRGfx8gaNfT2dtpump` | LATEST | fresh market check; unproven |
| 2 | `Be9m9rwTrWLGFuwP7oKaShEBCL6reyg44hCCHMk9pump` | LATEST | fresh market check; unproven |
| 3 | `4G5y3xjDB5F8QCcAuCkqMXiWjCjuuRPnUoqm9y9bpump` | PERSISTED | below-floor cooldown skip |
| 4 | `EgjSyM3uYPW6kSxKHqFPW68qE2hE5n3mqCguNQBApump` | PERSISTED | below-floor cooldown skip |
| 5 | `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump` | PERSISTED | below-floor cooldown skip |
| 6 | `4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump` | PERSISTED | below-floor cooldown skip |

The two audited mints were the two remaining persisted rows and therefore fell
outside the bounded batch before market enrichment, STNP, or rotation/cooldown
eligibility was evaluated. The second attempt's two DexScreener market requests
and four cooldown skips exactly match the six rows above.

## Residue causality finding

```text
failed first campaign
  -> retained selection/slot/tracking evidence
  -> no rotation row, no lifecycle cooldown, no market cooldown
  -> both explicit token/pair cooldown gates pass
  -> second deterministic six-row refresh omits both mints
  -> no second-attempt eligibility decision exists for either mint
```

Accordingly:

1. Residue was present as honest durable evidence.
2. Residue did not alter STNP, rotation, cooldown, registry, or market-floor
   eligibility.
3. Exclusion occurred one stage earlier, solely at bounded refresh composition.
4. The second attempt's `BLOCKED_INSUFFICIENT_GRADUATED_POOL` terminal remains
   honest for the batch it evaluated.
5. No cleanup mutation, eligibility repair, or code change is warranted.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Classification |
|---|---|
| Seeded six-row batch can omit previously proven-liquidity rows | bounded refresh efficiency limitation; not a residue defect |
| First failed campaign retains `SELECTED` slots and queued tracking rows | historical pre-lifecycle evidence; harmless to current front-door eligibility |
| Retained readiness bundle is expired | evidence-only; must not be reused as fresh production authorization |
| Market liquidity observations are point-in-time | fixture proof may exercise mechanics, not assert current live eligibility |

## Locks preserved

No retrieval, paper decision, BUY/SELL/HOLD, position, trade event, paper audit,
PnL, wallet, signing, real-fund movement, paid API, scoring, ranking,
confidence/weighted logic, embedding/vector, long-window production, retry,
restart, or successor capability is enabled by this audit.
