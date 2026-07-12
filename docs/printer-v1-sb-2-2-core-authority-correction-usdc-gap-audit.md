# SB-2.2 Core Authority Correction and USDC Implementation-Gap Audit

Status: STATIC INSPECTION AND DOCUMENTATION CORRECTION ONLY

## Executive Verdict

`CORE_AUTHORITY_CORRECTION_PASS_WITH_IMPLEMENTATION_GAP`

SB-2.2 verified primary official authorities for Solana core address and RPC claims and corrected the SB-2 core docs. The main result is a real implementation gap: Circle's current official USDC contract-address page lists a different Solana mainnet USDC mint than Printer's current GeckoTerminal infrastructure-mint filter.

No production repair was made in this lane.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-sb-1-solana-builder-source-stack-architecture.md`
- `docs/printer-v1-sb-2-solana-core-source-stack-authoring-report.md`
- `docs/solana-builder-source-of-truth/README.md`
- `docs/solana-builder-source-of-truth/solana-core-rpc-reference.md`
- `docs/solana-builder-source-of-truth/solana-transaction-instruction-parsing.md`
- `docs/solana-builder-source-of-truth/solana-mint-addresses.md`

## Official Authorities Verified

| Claim | Authority tier | URL or repository | Commit/tag | Verification date | Exact rule derived |
|---|---|---|---|---|---|
| Solana USDC mainnet mint | A4 | `https://developers.circle.com/stablecoins/usdc-contract-addresses.md` | Hosted docs; no commit | 2026-07-12 | Circle lists Solana mainnet USDC as `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| Solana USDt mint | A4 | `https://tether.to/en/supported-protocols` | Hosted docs; no commit | 2026-07-12 | Official Tether page contains `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` |
| WSOL repository authority | A1 | `https://github.com/solana-program/token` | `405c9172df3aeb508712142aae1caf0d31ada671` | 2026-07-12 | Wrapped SOL native mint belongs to the official token repository; exact file-path verification remains follow-up |
| Token-2022 repository authority | A1 | `https://github.com/solana-program/token-2022` | `27c359d1c7d38afdec293720dba4b768aa61aeb7` | 2026-07-12 | Token-2022 source repository pin recorded for future core verification |
| Solana public RPC endpoint and limits | A3 | `https://solana.com/docs/references/clusters` | Hosted docs; no commit | 2026-07-12 based on prior SB verification; current direct fetch failed | Public endpoint naming remains an unresolved compatibility question; numeric public-RPC limits remain `UNKNOWN_REQUIRES_RESEARCH` |
| `getSignaturesForAddress` `until` boundary | A3 | `https://solana.com/docs/rpc/http/getsignaturesforaddress` | Hosted docs; no commit | 2026-07-12 based on prior SB verification; current direct fetch failed | Newest-first and `before` pagination remain; `until` inclusivity is `UNKNOWN_REQUIRES_RESEARCH` |

## Official USDC Conclusion

Current Printer reference:

`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej`

Circle official current Solana USDC reference:

`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`

Outcome: Printer constant is incorrect relative to the current Circle official source and requires a later production repair/proof lane. SB-2.2 does not make that production repair.

## Complete Tracked Occurrence Map

Repository-wide tracked-file search was run for both USDC addresses.

| Address | File | Line | Classification | Use | Possible affected area |
|---|---|---:|---|---|---|
| `EPjF...CH8Ej` | `src/printer_v1/sources/geckoterminal.py` | 51 | code | `_SOLANA_NATIVE_QUOTE_MINTS` infrastructure quote/filter set | Discovery exclusion, base/quote-token interpretation, normalization, selection candidate input |
| `EPjF...CH8Ej` | `tests/test_post_rc_geckoterminal_discovery_adapter.py` | 435 | test | USDC fixture in native-quote leak-prevention tests | Tests must change in later repair |
| `EPjF...CH8Ej` | `docs/printer-v1-sb-0-solana-integration-upstream-documentation-inventory-audit.md` | 146 | documentation/report | Historical inventory table | Documentation only |
| `EPjF...CH8Ej` | `docs/printer-v1-sb-0-solana-integration-upstream-documentation-inventory-audit.md` | 411 | documentation/report | Historical code excerpt | Documentation only |
| `EPjF...CH8Ej` | `docs/solana-builder-source-of-truth/solana-mint-addresses.md` | previous SB-2.1 content | documentation | Current source-stack module before SB-2.2 | Corrected by SB-2.2 |
| `EPjF...TDt1v` | tracked repository before SB-2.2 | none | absent | Official Circle value not used by Printer | Confirms implementation gap |

Occurrence counts before SB-2.2 correction:

- Code: 1
- Test: 1
- Historical documentation/report: 2
- Current source-stack documentation: 1
- Official Circle candidate address occurrences: 0

## Implementation-Impact Assessment

The active implementation impact is narrow but important:

- `geckoterminal.py` may fail to exclude the official current Circle USDC mint if it appears as a `base_token`.
- A USDC pool could therefore be normalized as a candidate when it should be filtered as infrastructure.
- The related test currently protects the old constant, so the later repair must update the test fixture.
- No current evidence shows this has created memory, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Later Repair Recommendation

Create a narrow production repair lane to:

1. Update `_SOLANA_NATIVE_QUOTE_MINTS` to include Circle's official current Solana USDC address.
2. Decide whether the old Printer constant should remain as a legacy alias only after official-source review.
3. Update GeckoTerminal leak-prevention tests.
4. Prove official USDC cannot enter discovery, normalization, selection, memory, or paper paths as a memecoin.
5. Preserve all V1 locks.

## WSOL and USDt Authority Pins

- WSOL: official repository `https://github.com/solana-program/token`, HEAD `405c9172df3aeb508712142aae1caf0d31ada671`; exact `native_mint` file path still needs final static verification.
- USDt: official Tether page `https://tether.to/en/supported-protocols` contains `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`.

## Corrected Public RPC Limits

The core RPC module now records:

- Public Solana RPC is shared public infrastructure.
- It is subject to limits and not suitable for production-scale use.
- Exact current numeric public-RPC limits remain `UNKNOWN_REQUIRES_RESEARCH`.
- Printer's Source Governor budgets remain stricter implementation limits and do not replace upstream limits.

## Endpoint-Policy Conclusion

SB-2.2 classifies `api.mainnet.solana.com` versus `api.mainnet-beta.solana.com` as:

`official documentation naming conflict / unresolved compatibility question`

No live endpoint test was run. SB-2.2 does not claim both endpoints resolve. Production code remains unchanged.

## `until` Boundary Conclusion

The docs preserve official newest-first ordering and `before` pagination. The `until` inclusivity claim has been removed from the core RPC module and replaced with:

`UNKNOWN_REQUIRES_RESEARCH`

## Corrected T3 Sequencing

SB-2.2 corrected the T3 sequence:

1. Complete source-stack modules.
2. SB-6 direct-signature T3 design.
3. Approved implementation and fixture proof.
4. Bounded live proof.
5. A3 readiness review.

Failure-provenance persistence is observability hardening. It does not block direct-signature T3 design or fixture proof. Before bounded live proof, the eight fields must be preserved either durably in the DB or explicitly in the proof artifact.

## Money-Usefulness Contribution

The USDC correction prevents infrastructure assets from leaking into Solana memecoin discovery and selection. That protects future memory growth from polluted candidate pools, bad quote-side interpretation, and fake learning examples.

## What Remains Locked

- Source-stack adoption.
- Production code repair.
- Live RPC/API calls.
- Discovery, scheduler, runtime, and memory generation.
- T3 redesign or resumption.
- A3.
- Staged/native 15m.
- V2-3.
- Retrieval.
- Paper decisions.
- BUY, SELL, HOLD.
- Positions, trades, audits, and PnL.

## Proof Needed Before Production Repair

- Official Circle page rechecked and pinned.
- Targeted code repair for `geckoterminal.py`.
- Targeted tests showing both official USDC and any approved legacy alias are excluded as infrastructure assets.
- No memory/retrieval/paper/trading row creation.
- Risky-language and lock-preservation scan.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Severity | Status |
|---|---|---|
| USDC infrastructure token leak into candidate universe | High | Confirmed implementation gap |
| Tests currently protect old USDC constant | Medium | Requires targeted repair |
| WSOL exact file path not fully pinned | Medium | Repository HEAD pinned; exact file path follow-up |
| Public RPC endpoint naming conflict | Medium | `UNKNOWN_REQUIRES_RESEARCH` |
| Numeric public RPC limits not pinned | Low | Printer budgets remain stricter |
| `until` inclusivity unsupported | Low | Corrected to unknown |

## Final Conclusion

SB-2.2 passes as a documentation correction and authority audit with a confirmed implementation gap. The next safe step is independent verification of this correction or a separate narrow USDC production repair lane if the operator chooses to prioritize the implementation gap.


---

# SB-2.3 Independent Verification Record

## Lane Result

- Lane: `SB-2.3 ? Independent Core Authority Correction Verification`
- Executor: manual operator verification
- Date: 2026-07-12
- Anchor commit: `248eae9`
- Verdict: `CORE_AUTHORITY_VERIFICATION_PASS_WITH_IMPLEMENTATION_GAP`

## USDC Verification

Circle official Solana USDC:

`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`

Current Printer production constant:

`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEt67tw2CH8Ej`

The SB-2.2 implementation-gap conclusion is independently confirmed.

## Verified Tracked Occurrences

Old Printer address:

- production code: 1;
- test: 1;
- current SB documentation: 4;
- historical SB-0 documentation: 2;
- total: 8.

Official Circle address:

- documentation: 6;
- production code: 0;
- tests: 0.

The demonstrated impact is limited to GeckoTerminal infrastructure-token
exclusion and its targeted test.

## Authority Pins

- WSOL:
  - repository `solana-program/token`;
  - commit `405c9172df3aeb508712142aae1caf0d31ada671`;
  - path `interface/src/native_mint.rs`;
  - canonical address present.
- Token-2022:
  - repository `solana-program/token-2022`;
  - commit `27c359d1c7d38afdec293720dba4b768aa61aeb7`;
  - path `interface/src/extension/mod.rs`;
  - required base-layout constants present.
- USDt:
  - official Tether authority and Solana address confirmed.

## RPC Conclusions

The official cluster reference publishes:

- 100 requests per 10 seconds per IP;
- 40 requests per 10 seconds per IP for one RPC method;
- 40 concurrent connections per IP;
- 40 connection attempts per 10 seconds per IP;
- 100 MB transferred per 30 seconds per IP.

These values are subject to change. Printer's stricter Source Governor budgets
remain separate.

Endpoint classification remains:

`OFFICIAL_DOCUMENTATION_NAMING_CONFLICT`

No live endpoint compatibility test was run.

## Signature-Boundary Conclusion

- newest-first order: confirmed;
- `before`: confirmed for backward pagination;
- `until` inclusivity/exclusivity: `UNKNOWN_REQUIRES_RESEARCH`.

## T3 Sequencing Conclusion

1. Complete source-stack modules.
2. SB-6 direct-signature T3 design.
3. Approved implementation.
4. Fixture proof.
5. Bounded live proof.
6. A3 readiness review.

Failure-provenance persistence is observability and proof-readiness hardening.
It does not block documentation lanes, SB-6 design, implementation design, or
fixture proof. Before bounded live proof, the fields must be DB-durable or
explicitly preserved in its proof artifact.

## Money-Usefulness Contribution

The verification helps prevent an infrastructure asset from entering the
Solana memecoin candidate path and protects future discovery, memory, and
paper-realism data from avoidable contamination.

## What Remains Locked

All existing V1 and V2 locks remain unchanged. No production code, tests,
migrations, fixtures, DBs, live sources, T3 runtime, A3, retrieval, paper
decisions, positions, trades, audits, or PnL were changed or activated.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Severity | Status |
|---|---|---|
| Official USDC absent from active infrastructure filter | High | Confirmed implementation gap |
| Current test protects the incorrect constant | Medium | Requires later targeted repair |
| Endpoint naming differs across official Solana documents | Medium | No live compatibility claim |
| Public RPC limits can change | Low | Values documented; Printer budgets remain stricter |
| `until` boundary is not explicitly established | Low | Preserved as unknown |
| Failure provenance is not DB-durable | Proof readiness | DB durability or explicit proof-artifact capture required before bounded live proof |

## Next Lane

`SB-2.4 ? USDC Infrastructure-Mint Repair Design`

SB-2.4 must define legacy-address treatment, targeted tests, non-leak proof,
and lock-preservation requirements before implementation.
