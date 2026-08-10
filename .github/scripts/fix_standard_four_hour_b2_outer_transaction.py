from pathlib import Path

path = Path('src/printer_v1/operator_cli/one_token_4h_runtime.py')
text = path.read_text()

old_open = '''    planned_by_slot: dict[str, int] = {}
    timestamp = now or datetime.now(timezone.utc).isoformat()
    with connection:
        handoff = campaign_ownership.persist_standard_four_hour_handoff_set(
'''
new_open = '''    if connection.in_transaction:
        raise ValueError(
            "standard four-hour campaign planning requires a clean transaction boundary"
        )
    planned_by_slot: dict[str, int] = {}
    timestamp = now or datetime.now(timezone.utc).isoformat()
    connection.execute("BEGIN")
    try:
        handoff = campaign_ownership.persist_standard_four_hour_handoff_set(
'''
if text.count(old_open) != 1:
    raise SystemExit('B2 outer transaction opening marker missing or ambiguous')
text = text.replace(old_open, new_open, 1)

old_close = '''        if verified["planned_by_slot"] != planned_by_slot:
            raise ValueError("standard four-hour planned-slot read-back mismatch")
    return {
        "planned": True,
'''
new_close = '''        if verified["planned_by_slot"] != planned_by_slot:
            raise ValueError("standard four-hour planned-slot read-back mismatch")
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    return {
        "planned": True,
'''
if text.count(old_close) != 1:
    raise SystemExit('B2 outer transaction closing marker missing or ambiguous')
text = text.replace(old_close, new_close, 1)

path.write_text(text)
