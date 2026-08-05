# Printer V1 V2-9.8B WINDOW_15M Source-Specific Admission and Retained-Evidence Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_SPECIFIC_ADMISSION_RETAINED_EVIDENCE_REPAIR_PASS`

This is an implementation and disposable-proof closeout only. No authorization
was created, renewed, or reused. No provider, discovery, Source Governor,
Central Scheduler, campaign, or memory runtime was invoked. The authoritative
database and all evidence from failed execution
`20260805T225258Z-63f2d6d9da75` remain unchanged.

## Baseline and branch

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-fresh-one-use-authorization-after-index-restoration` |
| Required full starting HEAD | `be1197f19da318bde45688cb4f9b1bda688da458` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` |
| Failed execution | `20260805T225258Z-63f2d6d9da75` |
| Failed mint | `6a4TCQoCFXXNK8jUtjCMPqvoaLGx1oNLrciBiRafpump` |
| Terminal cause | `GraduatedSupplyError:SELECTED_MINT_NOT_IN_REGISTRY` |
| Repair branch | `agent/v2-9-8b-window-15m-source-specific-admission-retained-evidence-repair` |
| Commit subject | `Repair WINDOW_15M source-specific candidate admission` |

The starting tracked tree and index were clean. The existing untracked
Migration-050 and consumed-authorization evidence packages were preserved and
were not staged.

## Source-grounded failure confirmation

Read-only inspection traced source requests `1930–1939` and responses
`1722–1729` through the complete production call path.

1. Request `1930` was the governed DexScreener fresh-profile request. Clean
   response `1722` nominated the failed mint at `$.pairs[6]` with exact pool
   `GzDaHcmSzGjiWSphXvCzxv1N9jCcTHy3bm4LUkeH3JGQ`, Solana chain, PumpSwap venue,
   WSOL quote, current activity, and approximately USD 21,054.68 liquidity.
2. Request `1931` / response `1723` was the direct Pump migration-signature
   page and returned zero migration candidates. It did not establish Pump
   origin, migration, graduation, or registry membership for the failed mint.
3. Requests `1932–1938` / responses `1724–1728` supplied governed GeckoTerminal
   new-pool/batch coverage, including honest rate-limit outcomes where present.
4. Request `1939` / response `1729` provided exact Solana PumpSwap pool-account
   observation. Member 12 bound the failed mint to the same pool, the PumpSwap
   owner program, and the exact base mint. This is present-pool proof; it is not
   retroactively relabelled as Pump origin or Pump migration evidence.
5. Normalization, exact mint/pair admission, freshness/liquidity/activity gates,
   selectable-candidate construction, and frozen selection succeeded. The mint
   was absent from `printer_pumpswap_graduated_candidate_registry`, as expected
   for the market-nominated route.
6. `graduated_supply_front_door.build_graduated_supply` then performed the
   obsolete universal post-selection registry lookup and raised
   `SELECTED_MINT_NOT_IN_REGISTRY`.

The true nomination authority was DexScreener. Its supported authority was a
governed, fresh, exact Solana present-pool observation with exact transport and
request/response provenance. It did not claim Pump origin, migration,
graduation, or registry membership. The blocker was classified as a committed
code defect, not a source-data failure or a missing registry row.

## Obsolete universal assumptions found

- selected candidates were universally re-looked-up in the PumpSwap graduated
  registry after selection;
- all frozen candidates inherited a three-role Pump-specific retained-evidence
  matrix even when nominated directly by DexScreener or GeckoTerminal;
- generic memory-candidate reports described active permanent candidates as
  graduated or registry-backed;
- market nomination carriers lost factual nomination/admission provenance while
  moving through promotion and supply layers;
- retained projection created universal origin/PumpSwap projections instead of
  projecting only facts asserted by each candidate's admission authority;
- direct migration candidates did not consistently carry their own exact
  retained origin and PumpSwap request/response references into selection.

The Pump migration registry itself was not weakened or renamed. Its lookup
remains source-scoped to the direct migration supply/index owner and historical
locator diagnostics; it is no longer a universal selected-candidate authority.
No candidate admission performs a post-selection registry query.

## Source-specific admission matrix

| Contract | Market-nominated: DexScreener / GeckoTerminal | Direct Pump / PumpSwap |
| --- | --- | --- |
| Exact Solana mint | required | required |
| Exact present pool/pair | required | required |
| Exact mint/pool consistency through freeze | required | required |
| Solana-chain confirmation | required | required by direct proof |
| Infrastructure-mint exclusion | required | required |
| Governed accepted request/response provenance | required | required |
| Non-empty exact owned transport identity | required | required |
| Observation time and freshness | required | required |
| Existing liquidity/activity/holder/tracking gates | unchanged and required | unchanged and required |
| Pump origin | unknown/not claimed unless independently proven | required when claimed |
| Pump migration | not required or synthesized | required by direct route |
| PumpSwap confirmation | not required or synthesized | exact carried proof required |
| PumpSwap registry membership | not required | supplied by direct registry route, not re-looked-up after selection |
| Admission authority | `MARKET_PRESENT_POOL` | `DIRECT_PUMP_PUMPSWAP` |

No source quota, preference, score, rank, confidence, weighting, or slot-based
authority was introduced.

## Conditional retained-role matrix

| Role | Market-nominated candidate | Direct Pump / PumpSwap candidate |
| --- | --- | --- |
| `MARKET_OBSERVATION` | mandatory | mandatory |
| `ORIGIN_LINEAGE` | absent unless independently asserted; absence does not block | mandatory when direct authority asserts Pump origin |
| `PUMPSWAP_CONFIRMATION` | absent unless independently asserted; absence does not block | mandatory when direct authority asserts PumpSwap confirmation |

Every required role retains exact request ID, response ID, response hash, owned
transport keys, source name, request kind, observation time, mint, pool/pair,
and campaign/run/cycle stage. Validation still rejects empty identities,
same-kind fallback, cross-request key borrowing, wrong stage ownership,
mint/pool mismatch, and any non-zero new source-row delta.

Market candidates project only retained market evidence. Direct candidates
project the exact Pump-specific roles carried by their direct route. No origin,
migration, PumpSwap, registry, source-request, source-response, or source-failure
row is fabricated.

## Mixed two-slot behavior

Frozen activation now derives the role matrix independently for each candidate,
not from slot ordinal. Disposable proofs cover and preserve frozen order for:

- two market-nominated candidates;
- two direct Pump/PumpSwap candidates;
- one market-nominated candidate and one direct Pump/PumpSwap candidate.

Tracking assessment and holder-safety evidence remain separate. Legacy
non-memory selection retains its historical selector and reporting contract.

## Files changed

Implementation:

- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/discovery/graduated_liquidity_front_door.py`
- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`

Tests:

- `tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py` (new)
- `tests/test_v2_9_8b_campaign_manifest_evidence_repair.py`
- `tests/test_v2_9_8b_holder_manifest_composition_repair.py`

Documents:

- this closeout

No schema migration was required or added.

## Focused checks and results

All runtime tests used disposable temporary databases and fixture transports.
No provider was contacted.

| Proof area | Result |
| --- | --- |
| DexScreener present-pool candidate absent from registry selectable | PASS |
| GeckoTerminal present-pool candidate absent from registry selectable | PASS |
| Market routes claim/create no Pump facts or registry row | PASS |
| Missing pool and mint/pool mismatch fail closed | PASS |
| Missing governed request/response/transport evidence fails closed | PASS |
| Market role matrix requires only `MARKET_OBSERVATION` | PASS |
| Direct role matrix retains exact Pump-specific requirements | PASS |
| Direct mint/pool mismatch fails closed | PASS |
| No post-selection registry lookup | PASS |
| No registry or source row synthesized | PASS |
| Market/market, Pump/Pump, and mixed two-slot frozen order | PASS |
| Exact per-request transport and zero-new-source-row reconciliation | PASS |
| Tracking/holder separation unchanged | PASS |
| Legacy non-memory selection unchanged | PASS |
| Retrieval and financial capability locks remain zero | PASS |

Commands/results:

- source-specific + retained-evidence exactness + clean-object integrity:
  `48 passed in 9.72s` on the final tree;
- nearest direct migration/front-door/locator/eligible-supply/selection tests:
  `98 passed, 1 deselected in 16.29s`;
- nearest active permanent discovery/conversion/freeze/campaign composition:
  `91 passed in 12.00s`;
- legacy pilot regressions excluding two confirmed baseline failures:
  `6 passed, 2 deselected in 8.03s`;
- Python compilation of all changed production modules: PASS;
- `git diff --check`: PASS;
- search for `SELECTED_MINT_NOT_IN_REGISTRY` under production/tests: zero
  matches.

The broader diagnostic sweep exposed pre-existing failures. Representative
failures were reproduced against an exact archive of baseline HEAD
`be1197f19da318bde45688cb4f9b1bda688da458`, including the migration-head
expectation, deferred N7 state, legacy stage-evidence/readiness expectations,
and fresh-profile locator provider-order assertion. They were not caused by this
repair, did not affect the active source-specific contract, and were not used to
expand scope or weaken tests. Per the risk-based verification policy, the full
suite was not run.

## Authoritative database and failed evidence

The authoritative database was checked by filesystem identity and approved
read-only inspection only:

| Field | Before and after |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | `68366336` |
| SHA-256 | `5612556ce62074327524533ee8932203be129f19843afe4052da7dbb2f756e64` |
| Inode | `1230526` |
| mtime_ns | `1785970388921155893` |

No WAL, SHM, or journal was created. No active Printer process or database
writer was observed. Active Scheduler work and active campaigns were zero, and
the failed campaign lease was released.

The consumed authorization package, external application marker, manifest,
wrapper terminal evidence, terminal campaign evidence, and all failed campaign
rows were left unchanged. Existing untracked operational evidence was not
staged or committed.

## Money-usefulness contribution

The repair prevents clean-memory growth from discarding lawful, currently
tradeable Solana candidates merely because they were discovered by a market
source instead of the direct Pump migration route. At the same time, it prevents
false Pump history from entering memory: market observations remain market
observations, while direct Pump claims must retain their exact origin,
migration, and PumpSwap evidence. This increases useful clean candidate coverage
without manufacturing lineage, weakening exit realism, or contaminating later
historical comparison.

## What the repair improves

- aligns active candidate admission with the adopted multi-source foundation;
- removes the failed run's obsolete universal registry dependency;
- carries factual source authority and exact pool identity through selection and
  freeze;
- makes retained roles conditional on facts actually asserted by the candidate;
- supports homogeneous and mixed two-slot activation without ordinal-derived
  provenance;
- keeps direct Pump/PumpSwap claims fail-closed and exact;
- makes active permanent-memory reporting candidate/present-pool neutral.

## What remains locked

- no reusable or new `WINDOW_15M` authorization;
- no campaign, provider contact, discovery, Scheduler execution, or memory run;
- no source fetching outside governed approved commands;
- no 1h/4h/12h/24h production expansion;
- no retrieval activation or dirty-memory use;
- no paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- no wallet, private key, signing, funding, live execution, or paid API;
- no score, rank, confidence, weighting, embedding, or vector system;
- Source Governor and Central Scheduler ownership remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Direct Pump/PumpSwap candidates now fail closed if their current carrier lacks
  exact retained origin or PumpSwap request/response references. Historical
  identity alone is not promoted into missing evidence.
- The existing persistence schema has a historical constrained channel
  vocabulary. Market admission stores factual `UNKNOWN_ORIGIN` in retained
  authority/provenance while using the compatible legacy channel value where
  that column requires it. No schema migration was justified for this repair.
- Historical direct-Pump and non-memory identifiers remain in their source-owned
  paths for compatibility. They are not used as generic permanent-memory
  admission authority.
- The source-scoped fresh-profile locator may still report registry intersection
  for the direct migration supply owner. That diagnostic does not reject market
  nominees and is not queried after selection.
- Exact evidence requirements intentionally reject older/disposable carriers
  that cannot prove request, response, transport, stage, mint, and pool
  ownership; the repair does not synthesize replacements.
- Pre-existing baseline regression failures remain outside this lane and should
  be handled only under their own approved scope.

## Exact next step

After operator review of this branch, commit, and closeout, the next permitted
step on PASS is a **fresh one-use `WINDOW_15M` authorization** bound to the new
full HEAD and the then-current authoritative database identity.

This closeout does not create that authorization and does not authorize or run
memory.
