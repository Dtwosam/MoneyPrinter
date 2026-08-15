from pathlib import Path

path = Path('.github/scripts/apply_v2_9_8b_historical_lease_alias_repair.py')
text = path.read_text(encoding='utf-8')
old = '''replace_once(
    supervision,
    \'\'\'        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] == "TERMINAL":
\'\'\',
    \'\'\'        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        recorded_lease_path = Path(str(row["lease_lock_path"])).resolve()
        selected_release_path = recorded_lease_path
        if lease_release_path is not None:
            selected_release_path = Path(lease_release_path).resolve()
            if selected_release_path == recorded_lease_path:
                raise CampaignSupervisionError(
                    "disposable lease alias must differ from recorded lease path"
                )
            try:
                recorded_lease_bytes = recorded_lease_path.read_bytes()
                alias_lease_bytes = selected_release_path.read_bytes()
            except OSError as exc:
                raise CampaignSupervisionError(
                    "disposable lease alias evidence is unreadable"
                ) from exc
            if alias_lease_bytes != recorded_lease_bytes:
                raise CampaignSupervisionError(
                    "disposable lease alias is not byte-identical to recorded lease"
                )
            _exact_lock(_lock_payload(recorded_lease_path), row)
            _exact_lock(_lock_payload(selected_release_path), row)
        if row["supervision_state"] == "TERMINAL":
\'\'\',
    "pre-mutation alias validation",
)
'''
new = '''replace_once(
    supervision,
    \'\'\'    selected_release_path: Path | None = None
    try:
        _begin_immediate(connection)
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] == "TERMINAL":
\'\'\',
    \'\'\'    selected_release_path: Path | None = None
    try:
        _begin_immediate(connection)
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        recorded_lease_path = Path(str(row["lease_lock_path"])).resolve()
        selected_release_path = recorded_lease_path
        if lease_release_path is not None:
            selected_release_path = Path(lease_release_path).resolve()
            if selected_release_path == recorded_lease_path:
                raise CampaignSupervisionError(
                    "disposable lease alias must differ from recorded lease path"
                )
            try:
                recorded_lease_bytes = recorded_lease_path.read_bytes()
                alias_lease_bytes = selected_release_path.read_bytes()
            except OSError as exc:
                raise CampaignSupervisionError(
                    "disposable lease alias evidence is unreadable"
                ) from exc
            if alias_lease_bytes != recorded_lease_bytes:
                raise CampaignSupervisionError(
                    "disposable lease alias is not byte-identical to recorded lease"
                )
            _exact_lock(_lock_payload(recorded_lease_path), row)
            _exact_lock(_lock_payload(selected_release_path), row)
        if row["supervision_state"] == "TERMINAL":
\'\'\',
    "pre-mutation alias validation",
)
'''
if text.count(old) != 1:
    raise SystemExit(f'patch-script anchor block: expected 1, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
