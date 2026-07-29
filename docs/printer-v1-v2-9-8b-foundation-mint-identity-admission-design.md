# Printer V1 V2-9.8B Foundation Mint-Identity Admission Repair Design

Date: 2026-07-29

Depends on:
`docs/printer-v1-v2-9-8b-foundation-mint-identity-admission-audit.md`

Gate: complete design before implementation

## Canonical evidence chain

```text
cohort mint identity
→ exact ordered RPC request target
→ exact returned response slot
→ optional response-address assertion when supplied by a frozen transport
→ account presence
→ adopted token-program owner
→ adopted mint-layout decoder
→ categorical mint-status observation
→ exact request-target/candidate merge-key guard
→ CHAIN_MINT_VALID categorical result
```

Transport completion remains separate from every evidence step. A completed
batch containing null, unsupported, malformed, mismatched, or unusable accounts
is a completed transport with failed candidate evidence.

## Repair ownership

The existing owners remain canonical:

- `LiveCandidateAcquisitionTransportOwner.mint_batch` owns request construction,
  positional response association, account-owner/layout validation, and mint
  observation creation;
- the finite integration owner continues to own Scheduler/Source Governor work,
  budgets, leases, operation accounting, cohort enforcement, persistence, and
  terminal reporting;
- the foundation continues to own exact candidate merge, categorical gates,
  certificates, reserve, exact-N manifest, and replay.

No new adapter, source loop, runner, table, schema, migration, retry, source
preference, score, rank, confidence, or weighting is introduced.

## Mint account decoder contract

For each exact requested target:

1. retain the requested address and zero-based response slot;
2. null/missing slot → `MINT_ACCOUNT_MISSING`;
3. if a frozen response supplies an explicit address assertion, associate by
   that address, preserve its original slot, reject duplicates/unknown/missing
   targets, and use `MINT_TARGET_MISMATCH`;
4. adopted SPL owner:
   - raw data must be exactly 82 bytes;
   - base Mint decoder must pass;
5. adopted Token-2022 owner:
   - raw data must be at least 166 bytes;
   - the pinned decoder validates base Mint, zero padding, AccountType=Mint,
     and complete TLV structure;
6. a non-adopted owner with structurally mint-shaped data is
   `MINT_UNSUPPORTED_TOKEN_PROGRAM`;
7. a non-adopted owner whose account is not mint-shaped (including pair/pool or
   infrastructure program accounts) is `MINT_WRONG_PROGRAM_OWNER`;
8. invalid encoding, invalid adopted layout, or truncated data is
   `MINT_ACCOUNT_DATA_MALFORMED`;
9. only an adopted owner plus a valid corresponding mint layout yields
   `mint_status=PASS` and `token_program_status=PASS`.

Authority safety remains an independent categorical gate. A structurally valid
mint may pass chain-mint validation and still fail safety; the repair does not
weaken authority checks.

Known infrastructure base mints remain excluded by the existing Dex/Gecko
nomination normalizers. Negative fixtures additionally prove that presenting a
known infrastructure, pair, pool, or other non-mint account as a target cannot
pass mint validation.

## Exact association and merge contract

Standard Solana `getMultipleAccounts` values are positional. The owner binds
slot `i` to requested target `i` and persists both facts. A null slot remains
bound to that target. A frozen test transport may add an address assertion to
each account object; the owner then safely handles reordered results by exact
address, retaining each returned slot. Partial/duplicate/unknown assertions
fail only the affected categorical evidence and can never slide an adjacent
account onto another candidate.

Every canonical mint observation carries an evidence-version marker, exact
request target, response slot, association mode, account-presence state,
owner/program state, layout state, and precise failure reason. At foundation
merge, the request target and any explicit response address must equal the
candidate mint group key. Otherwise `CHAIN_MINT_VALID` fails with
`MINT_EVIDENCE_MERGE_KEY_MISMATCH` or `MINT_TARGET_MISMATCH`; the evidence
cannot satisfy another candidate.

True identity/pool merge failure remains separate. Chain-mint failures take
their precise admission reason in the terminal family unless the chain-mint
reason itself is a merge-key failure. Thus `IDENTITY_MERGE_FAILURE` no longer
masks a decoder, missing-account, owner, program, layout, or target defect.

## Frozen proof design

Use disposable migration-049 DBs, the normal public N2/N7 CLI dispatch, and the
existing frozen one-shot transport boundary. No network is permitted.

The proof covers:

- initialized legacy SPL Token mint;
- valid extended adopted Token-2022 mint with structurally valid TLV;
- mixed SPL/Token-2022 cohorts;
- missing account and null positional slot;
- wrong owner and unsupported token program;
- malformed base64/SPL/Token-2022 data;
- pair, pool, and infrastructure accounts presented as mint targets;
- reordered address-asserted values and partially null positional values;
- exact request-target/response-slot association;
- merge-key mismatch with the exact reason;
- a sanitized four-Token-2022 live-shaped regression derived from the blocked
  execution's persisted shape, using only synthetic addresses/payloads;
- exact N2: two admitted certificates and one two-item manifest;
- exact N7: seven admitted certificates and one runtime-neutral seven-item
  manifest; legacy adapter rejection;
- deterministic DB-backed zero-source replay;
- Scheduler/Governor/underlying-operation reconciliation;
- zero active leases and Scheduler residue;
- zero protected-table deltas.

Focused tests and the directly affected source/decoder regressions run first.
Compilation, fresh and upgrade migration-049 compatibility, then one broad
affected suite run at closeout. The authoritative DB hash must remain byte
identical.

## Stop conditions

Stop BLOCKED instead of expanding scope if the repair requires a schema change,
new provider contract, live call, source budget change, Scheduler/Governor
bypass, runtime capacity above two, weakened admission/safety gate, or any
tracking/memory/retrieval/financial write.

## Design verdict

The repair is complete at design level and requires only narrow changes to the
canonical mint transport, foundation categorical reasoning, frozen fixtures,
tests, and closeout documentation. No migration is required.
