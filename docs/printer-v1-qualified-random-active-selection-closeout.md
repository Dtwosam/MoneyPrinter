# Qualified Random Active-Token Selection Closeout

## Verdict

`QUALIFIED_RANDOM_ACTIVE_SELECTION_PASS`

V2-3 remains paused.

## Audit And Adoption

At commit `88f73e1`, production cooldown ran before a hard category-composition
gate. That gate required A2/A3/A4, decay, D1, and WATCH_ONLY outcomes at initial
selection time. The active V2 build order and Source Governor evidence rules
now adopt seeded uniform selection from qualified active tokens; old quota
measurements remain diagnostic only.

## Implementation

`QUALIFIED_RANDOM_ACTIVE_V1`:

- keeps Source Governor, exact mint/pair identity, quality, active-lane,
  deduplication, STNP, persistence, cooldown, and rotation gates;
- excludes WATCH_ONLY, D1, inactive, untraced, stale, failed, and dirty rows;
- sorts exact mint/pair identities before a uniform seeded shuffle;
- persists the seed, eligible pool size, requested/effective target, policy,
  selection reason, and diagnostic category composition;
- updates rotation only for a final assembled selection;
- exposes read-only exact-pair trajectory coverage without runtime work.

No score, rank, confidence, weight, or category preference is used.

## Deterministic Proof

Focused tests prove reproducibility for the same universe and seed, different
valid samples for different seeds, manual bucket-marker rejection, unsafe and
inactive exclusion, empty-pool safe stop, cooldown before selection, STNP and
dedup preservation, audit-only isolation, old quota diagnostics without a hard
gate, rotation persistence, and read-only trajectory reporting.

## One Unassisted Live Proof

Proof DB: `data/printer_v1_qualified_random_live_proof.sqlite3` (not committed).

The production command ran once with operator approval, Solana-only
GeckoTerminal discovery, both READY GeckoTerminal channels, max ten selected
candidates, max two source requests, and five-second request timeout. No mint
list, fixture, manual candidate choice, enrichment, retry, scheduler execution,
or post-start code change was used. A first CLI invocation failed argument
parsing on `--output` before any network or DB operation; the corrected
`--format json` invocation was the only live call.

Source Governor result:

- request 1 / response 1: `geckoterminal_new_pool_discovery`, COMPLETE/CLEAN;
- request 2 / response 2: `geckoterminal_trending_pool_reference`, COMPLETE/CLEAN;
- failures: 0;
- candidates seen: 40 (20 per channel);
- qualified active pool: 29;
- WATCH_ONLY audit pool: 8;
- unresolved STNP rejections: 3;
- cooldown rejections: 0;
- seed: `0a7d49083204803add71f59d77d2f244`;
- selected: 10; random non-selected active: 19.

## Selected Sample

| Mint | Pair | Channel | Lane | Bucket | Reason |
|---|---|---|---|---|---|
| `6AVAUKa9uxQpruHZUinFECpXEh1usRVtzQWK8N2wpump` | `B5K3qfft5ALRJBskL7qJPDzbbW76TXLkfKSd1mP4MtgN` | trending | TRACK_FAST | A1 | qualified random |
| `5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2` | `4w2cysotX6czaUGmmWg13hDpY4QEMG2CzeKYEQyK9Ama` | trending | TRACK_NORMAL | B2 | qualified random |
| `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump` | `6e7V9eegCHw997T72MxgwwJipZ6GJyZF8NvjkzT1rvpN` | trending | TRACK_FAST | A1 | qualified random |
| `9qyKjBj5PVKJfnh5aDW4wdwMngwQ2TvFQ2R9EAebpump` | `6Yj44iKTL7ybWA7MuR7j4hu9WfWukb1u9QR21tHWqCVA` | new pool | TRACK_NORMAL | B5 | qualified random |
| `4YpANZ4urF4DW2QtCMP54kZQkhsisypsstJbasQapump` | `6wLSrSbJQdJqYoxQqujVCg2qLKx4HYC6wb3GAh5o3zEb` | trending | TRACK_NORMAL | C1 | qualified random |
| `D4pi5eJNqT5mCzQcxAGfMavgVYLspfYkAQKKvQ8Xpump` | `7p1LD2vWkRCDBXNHWAk3fKDJ7fcAKUbSZmeAuCgivNgQ` | trending | TRACK_NORMAL | C2 | qualified random |
| `BCdwQBAn8dYB5YjTsoB6TdHAWokxv28k2oZUodERpump` | `2DVbU5h8JCd37gaXAJUZ4t77HsjJW22LLduTZk7GSa43` | trending | TRACK_FAST | A1 | qualified random |
| `DUYw2p3NC6zDdsSrazV4JdDFKtRk2K4mw764EWs2pump` | `AoXFMDQMaevMEJgKuMTHbptoeoCjW8bDYKniXMhkNDpc` | trending | TRACK_FAST | A1 | qualified random |
| `gsoZaYPVioFi9GRaehCnvNqUSNWYNZNVKT9oyoJpump` | `34hC1UWpc1gTnM9W3zvhesimRE1GpQxq9CWWFohB31Rd` | trending | TRACK_FAST | A1 | qualified random |
| `22rcvLaeRTMDxKPMWo6R6FXmLk26VyGvPLNBZ7Adpump` | `BHDodeU9mvVgXE3hmx7gtqXHvoyyXEjMcgwBgJN9HUgo` | new pool | TRACK_NORMAL | B1 | qualified random |

## Non-Selected Active Candidates

All were rejected only as `QUALIFIED_RANDOM_NOT_SELECTED` and retained source
trace in selection-batch audit rows:

`2xpX...cZ22` B5, `47Rh...pump` B2, `4Mrs...pump` A1,
`4ko5...pump` A1, `6MJE...pump` A1, `6Nwar...pump` A1,
`6epC...pump` C1, `7Adi...fvQa` C2, `7Ct9...8Lz4` B1,
`95Dk...pump` A1, `ACES...Dmsj` B5, `CARDS...KxYjp` A1,
`CTdV...pump` A1, `DpqG...pump` A1, `EZvG...pump` B5,
`Frtb...pump` A1, `GwZv...pump` A1, `Tqj8...pump` A1, and
`h3c8...pump` B1.

## Audit-Only And Integrity Decisions

Eight WATCH_ONLY candidates remained outside active selection and created no
active handoff: `9yBib...Hmdb`, `AWNn...ig8Y`, `GWFAY...AzAm`,
`GfpB...pump`, `3wjU...pump`, `3U4i...sXVt`, `9KoE...pump`, and
`8TeH...pump`.

Three exact same-token/new-pair conflicts were rejected before persistence:
`2xpX...cZ22` / `2AjK...uWQV`, `3U4i...sXVt` / `AigT...w7X2`, and
`9cRC...pump` / `FnzK...L3CC`. No unresolved STNP candidate entered the pool.

## Historical Composition Diagnostic

The selected category composition was `{A1: 5, B1: 1, B2: 1, B5: 1,
C1: 1, C2: 1}`. It fails historical Group A, A2/A3/A4, D1, and WATCH_ONLY
composition rules, but those rules correctly did not block handoff.

The compatibility diagnostic also reported duplicate mint/pair violations
even though the selected identities and batch rows are unique. Static review
shows its reduced compatibility input omitted identity fields. This is a
diagnostic reporting defect only; frozen live-run code was not changed after
the run. A later narrow reporting repair should remove these two false labels.

## Trajectory Coverage

The read-only report saw ten exact selected mint/pair observations and zero
repeated pairs, so every trajectory category was zero. This is expected for a
fresh one-observation proof and does not manufacture outcomes. Later approved
observation lanes must accumulate repeated governed observations before
continuation, failure, decay, death, revival, consolidation, or liquidity
removal coverage can appear.

## DB Deltas And Locks

Proof DB deltas: source requests/responses/failures `+2/+2/0`; selection
batches/items `+1/+29`; tokens/pairs/discovery rows `+10/+10/+10`; tracking
queue/scheduler jobs `+10/+10`; rotation state `+10`. Scheduler jobs were
queued by the existing handoff and not executed.

Snapshots, memory windows/fingerprints, retrieval queries/matches, paper
decisions/positions, trade events, paper audits/reports, and PnL remained zero.
The persistent DB SHA-256 stayed
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`, and
all inspected persistent counts were unchanged.

## Remaining Risks

- The old quota compatibility view has the false duplicate diagnostic above.
- A single fresh run cannot prove trajectory coverage; repeated observations
  remain a later explicitly approved lane.
- The live proof sampled both READY GeckoTerminal channels. It did not expand
  providers or prove a unified cross-provider production invocation.
- Token age and native/staged 15m evidence gaps remain outside this lane.

No V2-3 work began. All financial and memory locks remain unchanged.
