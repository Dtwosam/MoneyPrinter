# Printer V1 V2-9.8B Four-Token Final Integration Implementation Closeout

## Verdict

`V2_9_8B_FOUR_TOKEN_FINAL_INTEGRATION_IMPLEMENTATION_PASS_READY_FOR_INDEPENDENT_REVIEW`

This closeout covers only the proof-only, bounded four-token factory integration.
It does not authorize migration application, a proof run, an authorization, live
sources, Scheduler runtime, or any financial capability.

## Identity and scope

- Starting commit: `16982ae7f7f15a270741384b563ff4b4b374bc06`
- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Runtime token capacity remains `2`; four-token capacity is two admitted
  two-token cycles, never one widened runtime cycle.
- Migration 055 is used only by disposable test databases. The authoritative
  operational database was not migrated or written.

## TDD gates and commits

| Gate | RED | GREEN / proof |
|---|---|---|
| A1 neutral identity persistence | `5f5d6ce` | `001a0b4` |
| A2 permanent later-cycle GraduatedSupply | `b828b25` | `4e07703` |
| B cycle namespace and derived capacity | `e845b72` | `3ee7990` |
| C exact pre-created 15m ownership | `6cce53d` | `8691566` |
| D one-loop admission boundary | `d151326` | `2261690` |
| E Scheduler-owned cycle barriers | `027290b` | `c8c3393` |
| F per-cycle accounting | `4169e1e` | `967355f` |
| G two-phase terminal law | `be47ab7` | `2987b64` |
| H integrated disposable proof | — | `f6a9e04` |

Gate H is an integration-proof test over the already-GREEN A-G owners; it made
no additional production change.

## Implemented authority

### Real supply and neutral identities

The later-cycle adapter calls the permanent `build_graduated_supply` owner and
retains one unique cycle-2 request scope with exact request/response/failure
lineage. The shared neutral token/pair identity owner creates or validates only
the canonical token and pair rows. A newly created token keeps `token_status`
NULL. It creates no queue row, lifecycle state, Scheduler work, campaign cycle,
window, or memory. The existing combined discovery handoff reuses that same
owner before its existing activation transition.

### One factory and fresh admission health

The existing canonical factory loop owns admission. Its order remains stop
conditions, due lifecycle work, proof deadline, due admission, then the earliest
authoritative future boundary. Equal-time lifecycle work wins. Admission uses:

1. an authoritative 12-field health projection;
2. the existing disposition owner;
3. the durable one-shot later-cycle callback;
4. a fresh authoritative post-discovery health projection;
5. atomic attempt consumption only with that second health value;
6. frozen-pair materialization; and
7. opening jobs in the same factory run.

A post-discovery block leaves `PAIR_READY` unconsumed and creates no retry or
successor. Once cycle 2 exists, fresh-cycle admission projection stops.

### Namespace, ownership, and barriers

- Cycle 1 retains `t1_` / `t2_` step keys.
- Cycle 2 uses `t1_c0002_` / `t2_c0002_`.
- Request accounting parses the full cycle-aware prefix, so cycle 1 cannot
  count cycle-2 requests.
- The proof Scheduler ceiling is derived from
  `scaled_standard_four_hour_capacity_contract(4)`.
- Each proof slot receives one deterministic pre-created `WINDOW_15M` campaign
  window. Real close materialization binds its memory row to that same window.
- Every proof lifecycle job has one exact `V2_STAGE_SCOPED` /
  `WINDOW_LIFECYCLE` owner and resolves its cycle through
  `resolve_owned_cycle_for_scheduler_job`.
- Natural/selective 15m and standard 1h/4h barriers receive the owning cycle;
  the public two-token path retains its legacy behavior.

### Accounting

Each cycle keeps `expected_token_capacity=2` and builds its standard package
from `cycle_scoped_factory_step_ids`. Aggregate acceptance requires exactly two
packages, disjoint owned step ids, four distinct token/pair targets, at least
300 seconds admission spacing, and actual source/Scheduler totals no greater
than the derived four-token envelope. Memory quality is reported honestly and
is not a pass quota.

### Two-phase terminal law

Phase A cancels only exact cycle-owned Scheduler jobs and factory steps, then
uses the existing campaign ownership transition owner for cycle-owned work,
windows, slots, and the cycle. It does not mutate the shared campaign, campaign
run, factory run, or lease.

Phase B refuses to run until both exact cycles are terminal and the existing
active-work owner proves zero active/orphan work. It composes one supplied
existing shared terminal/cleanup owner and requires both clean-terminal and
lease-release evidence. A repeated call observes the already-terminal shared
run and does not invoke cleanup again. First terminal causes remain immutable.

## Verification

Focused A-G tests were run after their gates. Final directly affected closeout:

- four-token contracts and gates;
- pre-admission schema, scheduling, persistence, callback, atomic consumption,
  frozen materialization, and parity;
- callback -> consumption -> materialization integration;
- operational selective 1h;
- standard-four-hour planning, activation, accounting, handoff, terminal, and
  public wiring;
- combined discovery executor and isolated combined-discovery proof.

Result: `266 passed, 43 subtests passed`.

The Gate H disposable proof passed: `1 passed`. It established one campaign,
one campaign run, one factory run, four distinct targets, 300-second spacing,
two health projections, one discovery attempt, cycle-aware work/request
identity, exact Scheduler-to-cycle ownership, two accounting packages, derived
aggregate acceptance, both cycles terminal before one shared cleanup, and no
retry/restart/resume/successor.

The legacy public factory file produced `15 passed, 1 failed`. The one failure,
`test_continuous_first_hour_path_terminally_safe_blocks_compressed_time`,
reproduced identically at starting commit `16982ae`: its 10-second compressed
harness conflicts with the existing fixed 2700-second 1h-close authority. The
proof-disabled signature remains optional (`four_token_proof_controller=None`),
and all directly affected public standard-four-hour tests passed. This lane did
not alter the unrelated timing contract.

All touched production Python modules compile. `git diff --check` passes.

## Hard-lock confirmation

No live source request, real Scheduler runtime, operational database mutation,
proof execution, proof authorization, 12h/24h activation, retrieval, paper
decision, BUY/SELL/HOLD, position, trade, audit, or PnL action occurred. Provider
ceilings and `TOKEN_CAPACITY` were not changed. No migration was added and
migration 055 was not applied to the authoritative database.

## Functionality Risks / Setbacks / Efficiency Blockers

- The shared Phase B coordinator intentionally accepts the existing terminal
  and lease-cleanup composition as a callable; independent review should verify
  the eventual proof wrapper supplies the canonical existing composition once.
- The historical compressed-time public test remains a baseline failure as
  described above; correcting it would be a separate public timing-law task.
- This implementation is disposable/offline proven only. No migration or live
  readiness, authorization, or runtime work is implied.

## Next permitted action

Independent code and safety review only. Do not begin migration application,
proof readiness, authorization, or runtime from this closeout.
