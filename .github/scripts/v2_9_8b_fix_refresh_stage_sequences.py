from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


# Existing campaign-start owners retain sequence 1. Delayed refresh ordinal N
# receives sequence N+1 so source-evidence identities cannot collide with startup.
path = Path("src/printer_v1/discovery/permanent_discovery_availability.py")
text = path.read_text()

old = '''def run_geckoterminal_fresh_nomination(
    connection: sqlite3.Connection,
    *,
    request_key: str,
    now: str,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
    transport: Any | None = None,
    stage_evidence_sink: Any | None = None,
    transport_identity_observer: Any | None = None,
) -> dict[str, Any]:
'''
new = '''def run_geckoterminal_fresh_nomination(
    connection: sqlite3.Connection,
    *,
    request_key: str,
    now: str,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
    transport: Any | None = None,
    stage_evidence_sink: Any | None = None,
    transport_identity_observer: Any | None = None,
    stage_sequence: int = 1,
) -> dict[str, Any]:
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "geckoterminal signature")

old = '''            f"{campaign_id}|{run_id}|{cycle_id}|FRESH_POOL_NOMINATION|1"
            if campaign_id and run_id and cycle_id
            else f"FRESH_POOL_NOMINATION|1|{request_key}"
'''
new = '''            f"{campaign_id}|{run_id}|{cycle_id}|FRESH_POOL_NOMINATION|{int(stage_sequence)}"
            if campaign_id and run_id and cycle_id
            else f"FRESH_POOL_NOMINATION|{int(stage_sequence)}|{request_key}"
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "geckoterminal coverage sequence")

old = '''                    stage_kind="FRESH_POOL_NOMINATION", stage_sequence=1,
                ),
                stage_kind="FRESH_POOL_NOMINATION",
                stage_sequence=1,
'''
new = '''                    stage_kind="FRESH_POOL_NOMINATION", stage_sequence=int(stage_sequence),
                ),
                stage_kind="FRESH_POOL_NOMINATION",
                stage_sequence=int(stage_sequence),
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "geckoterminal sealed sequence")

old = '''def run_bounded_unknown_liquidity_backup(
    connection: sqlite3.Connection,
    *,
    stage_budget: StageBudget,
    now: str,
    campaign_id: str | None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    request_key_prefix: str = "unknown-liq-backup",
    dexscreener_transport_factory: Any | None = None,
    geckoterminal_transport_factory: Any | None = None,
    transport_identity_observer: Any | None = None,
    stage_evidence_sink: Any | None = None,
    max_backups: int | None = None,
) -> dict[str, Any]:
'''
new = '''def run_bounded_unknown_liquidity_backup(
    connection: sqlite3.Connection,
    *,
    stage_budget: StageBudget,
    now: str,
    campaign_id: str | None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    request_key_prefix: str = "unknown-liq-backup",
    dexscreener_transport_factory: Any | None = None,
    geckoterminal_transport_factory: Any | None = None,
    transport_identity_observer: Any | None = None,
    stage_evidence_sink: Any | None = None,
    max_backups: int | None = None,
    stage_sequence_base: int = 0,
) -> dict[str, Any]:
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "backup signature")

old = '''                f"{campaign_id}|{run_id}|{cycle_id}|UNKNOWN_LIQUIDITY_BACKUP|{attempted}"
                if campaign_id and run_id and cycle_id
                else f"UNKNOWN_LIQUIDITY_BACKUP|{attempted}"
'''
new = '''                f"{campaign_id}|{run_id}|{cycle_id}|UNKNOWN_LIQUIDITY_BACKUP|{int(stage_sequence_base) + attempted}"
                if campaign_id and run_id and cycle_id
                else f"UNKNOWN_LIQUIDITY_BACKUP|{int(stage_sequence_base) + attempted}"
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "backup coverage sequence")

old = '''            stage_sequence=attempted,
            terminal_status=str(coverage["terminal_status"]),
'''
new = '''            stage_sequence=int(stage_sequence_base) + attempted,
            terminal_status=str(coverage["terminal_status"]),
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "backup sealed sequence")

path.write_text(text)

path = Path("src/printer_v1/operator_cli/graduated_supply_front_door.py")
text = path.read_text()
old = '''                f"{campaign_id}|{run_id}|{cycle_id}|DEXSCREENER_FRESH_LOCATOR|1"
                if campaign_id and run_id and cycle_id
                else f"DEXSCREENER_FRESH_LOCATOR|{request_key}"
'''
new = '''                f"{campaign_id}|{run_id}|{cycle_id}|DEXSCREENER_FRESH_LOCATOR|{int(stage_sequence)}"
                if campaign_id and run_id and cycle_id
                else f"DEXSCREENER_FRESH_LOCATOR|{int(stage_sequence)}|{request_key}"
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "dex coverage sequence")
path.write_text(text)

path = Path("src/printer_v1/discovery/pre_lifecycle_refresh_composition.py")
text = path.read_text()
old = '''        source_operations = 0
        provider_failures = 0
'''
new = '''        refresh_stage_sequence = int(refresh_ordinal) + 1
        source_operations = 0
        provider_failures = 0
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "refresh stage sequence derivation")

text = text.replace(
    "stage_sequence=int(refresh_ordinal),",
    "stage_sequence=refresh_stage_sequence,",
)
old = '''                        transport_identity_observer=transport_identity_observer,
                    )
'''
new = '''                        transport_identity_observer=transport_identity_observer,
                        stage_sequence=refresh_stage_sequence,
                    )
'''
# This exact call shape occurs once in the GeckoTerminal refresh branch.
if new.strip() not in text:
    text = replace_once(text, old, new, "geckoterminal refresh sequence")

old = '''                    stage_evidence_sink=stage_evidence_sink,
                    max_backups=1,
                )
'''
new = '''                    stage_evidence_sink=stage_evidence_sink,
                    max_backups=1,
                    stage_sequence_base=int(refresh_ordinal),
                )
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "backup refresh sequence base")
path.write_text(text)

# Extend focused tests to prove startup sequence 1 is not reused by delayed rounds.
test_path = Path("tests/test_v2_9_8b_persistent_multisource_refresh.py")
tests = test_path.read_text()
if "test_delayed_refresh_stage_sequences_start_after_campaign_start" not in tests:
    tests += '''


def test_delayed_refresh_stage_sequences_start_after_campaign_start(tmp_path, monkeypatch):
    seen = {"pump": [], "dex": [], "gt": [], "backup_base": [], "protocol": []}

    def fake_pump(*args, **kwargs):
        seen["pump"].append(kwargs["stage_sequence"])
        return {"status": "COMPLETE", "source_request_ids": [1], "verifications": []}

    def fake_dex(*args, **kwargs):
        seen["dex"].append(kwargs["stage_sequence"])
        return {
            "status": "empty", "source_requests": 1, "request_id": 2,
            "response_id": 3, "pool_observations": [],
        }

    def fake_gt(*args, **kwargs):
        seen["gt"].append(kwargs["stage_sequence"])
        return {"status": "COMPLETE", "failure_type": None, "source_requests": 1, "nominations": []}

    def fake_backup(*args, **kwargs):
        seen["backup_base"].append(kwargs["stage_sequence_base"])
        return {"source_requests": 0, "accounting_blocker": False}

    def fake_protocol(*args, **kwargs):
        seen["protocol"].append(kwargs["stage_sequence"])
        return {"source_requests": 0, "shared_source_failures": 0, "promoted_observation_eligible": []}

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        fake_pump,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_dex,
    )
    monkeypatch.setattr(composition, "run_geckoterminal_fresh_nomination", fake_gt)
    monkeypatch.setattr(composition, "run_bounded_unknown_liquidity_backup", fake_backup)
    monkeypatch.setattr(composition, "process_protocol_confirmation_queue", fake_protocol)

    stage = composition.build_pre_lifecycle_refresh_stage(
        db_path=tmp_path / "proof.sqlite3",
        request_key_prefix="proof",
        migration_transport=lambda _ctx: {},
        locator_transport=lambda _ctx: {},
    )
    for ordinal in (1, 2, 3):
        _run(stage, remaining=30, ordinal=ordinal)

    assert seen["pump"] == [2, 3, 4]
    assert seen["dex"] == [2, 3, 4]
    assert seen["gt"] == [2, 3, 4]
    assert seen["backup_base"] == [1, 2, 3]
    assert seen["protocol"] == [2, 3, 4]
'''
    test_path.write_text(tests)
