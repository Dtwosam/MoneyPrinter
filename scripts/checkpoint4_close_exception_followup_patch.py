from pathlib import Path

path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
text = path.read_text(encoding="utf-8")
old = '''                if str(pending["step_kind"]) == "CONTINUATION_SNAPSHOT":
                    _terminalize_owned_continuation_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
'''
new = '''                if str(pending["step_kind"]) in {
                    "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                }:
                    _terminalize_owned_continuation_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one exception-path anchor, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
