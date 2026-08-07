# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-52 Terminal Campaign Run Identity Audit

Date: 2026-08-07

Linear: `DTW-52`

Parent: `DTW-34`

Baseline HEAD:

`479dfee0c06fb634caab0e510036b363e6641584`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW52_TERMINAL_CAMPAIGN_RUN_IDENTITY_AUDIT_PROVEN`

## Audit scope

Read-only proof of why Checkpoint 8 packaging fails with:

`CHECKPOINT8_TERMINAL_IDENTITY_MISSING`

after a real `run_operational_campaign()` terminal return, before `report_only()` and frozen-summary creation.

No implementation, no controlling proof, no provider/network work.

## Controlling harness packaging sequence

`scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
`execute_checkpoint8_public_sequence()`:

1. `terminal = run_operational_campaign(...)`
2. `campaign_id, run_id = extract_checkpoint8_terminal_identity(terminal)`
3. `report_only(campaign_id=..., run_id=..., db_path=..., artifact_root=...)`
4. freeze summary

The extractor requires **exactly one** non-empty campaign ID and **exactly one** non-empty campaign **run ID** from:

```text
terminal / report / cleanup / reconciliation scopes / exhaustion certificate
```

Cardinality conflict fails closed as `CHECKPOINT8_TERMINAL_IDENTITY_CONFLICT`.
Missing either identity fails closed as `CHECKPOINT8_TERMINAL_IDENTITY_MISSING`.

## Authoritative campaign run identity source

In `operational_memory_factory_command.py` public campaign construction:

```text
campaign_id = f"{execution_id}-campaign"
run_id      = f"{execution_id}-campaign-run"   # campaign run identity
```

That `run_id` is:

- stored as `AbstractCampaignCommand.run_id`;
- written into durable campaign graph / supervision / configuration ownership;
- used throughout cleanup, reconciliation, and report payload construction as the campaign run identity.

It is **not** the factory UUID.

## Factory-run identity is a different object

The coordinator pre-generates:

```text
initialized_factory_run_id = str(uuid.uuid4())
```

Factory identity is retained only after genuine lifecycle entry
(`factory_identity_retained`). Helpers such as
`_extract_returned_factory_run_id()` and `_is_campaign_run_identity()` exist
specifically so campaign-run shaped values (`*-campaign-run`) are never treated
as factory UUIDs.

Therefore:

- campaign `run_id` = command / campaign graph ownership identity;
- factory `run_id` / `factory_run_id` = optional inner factory execution identity;
- **factory identity must never substitute for campaign run identity** in the C8 extractor.

## Terminal assembly surface (proven gap)

Successful public terminal assembly in `run_operational_campaign()` builds:

```text
terminal = {
  "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
  "execution_id": execution_id,
  "campaign_id": command.campaign_id,
  # NO top-level "run_id"
  "report": report,   # write_campaign_terminal_report return surface
  ...
}
```

`write_campaign_terminal_report()` return packaging surface includes:

```text
report_id, campaign_id, configuration_id, report_hash, artifact_*,
campaign_source_calls, campaign_scheduler_calls, ...
```

It does **not** include `run_id`.

The durable campaign-report **body** payload does contain:

```text
payload["identity"]["run_id"] == command.run_id
```

but that body is not the packaging surface nested at `terminal["report"]`, and
the extractor does **not** read `report["identity"]["run_id"]`.

Failure / pre-lifecycle terminal assemblies similarly expose `campaign_id` without
top-level campaign `run_id`.

## Why the extractor cannot resolve the campaign run ID

Resolved sources for run ID at baseline:

| Surface | Has campaign run_id? |
|---------|----------------------|
| `terminal["run_id"]` | **No** |
| `terminal["report"]["run_id"]` | **No** (packaging return) |
| `terminal["cleanup"]["run_id"]` | Only if cleanup dict present and populated; success path often has no top-level cleanup |
| reconciliation scopes | Not present on success terminal packaging dict |
| exhaustion certificate | Not guaranteed / not the canonical packaging owner |

For the post-DTW50 success/blocked packaging path:

- campaign values = `{command.campaign_id}` → cardinality 1 OK
- run values = `{}` → cardinality 0 → `CHECKPOINT8_TERMINAL_IDENTITY_MISSING`

This matches the consumed attempt: campaign terminalized and wrote artifacts, but
harness packaging stopped before report-only replay and frozen summary.

## What is not the root cause

- DTW-50 holder scope (already repaired)
- DTW-51 disposable binding factory preflight (already repaired)
- Source Governor / Scheduler / budgets / six-unit accounting
- Provider/network
- Extractor conflict checks (those remain correct and must stay strict)

## Classification

`DTW52_TERMINAL_CAMPAIGN_RUN_IDENTITY_NOT_PROJECTED`

The authoritative campaign run ID exists at terminal assembly time as
`command.run_id` but is not projected onto the terminal packaging surface
required by the C8 extractor.

## Minimum repair implication (audit only)

Canonical owner of the packaging terminal dict is
`operational_memory_factory_command.py` terminal assembly (success and fail
closed paths that already know `command.run_id`).

Prefer projecting:

```text
"run_id": command.run_id
```

onto those terminal packaging dicts.

Do not invent run IDs from factory UUID, execution_id alone, or guesswork.
Do not weaken extractor conflict/cardinality law.

## Verdict

DTW-52 is justified as a required offline packaging/identity projection repair
before another one-shot C8 proof.

## Locks preserved

No C8 re-proof, no operational memory activation, no provider/network work, and
no production corpus mutation are authorized by this audit.
