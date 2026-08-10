from pathlib import Path

path = Path('src/printer_v1/operator_cli/one_command_15m_factory.py')
text = path.read_text()

result_failure = '''                    if str(pending["step_kind"]) in {
                        "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                    }:
                        _terminalize_owned_continuation_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause=error,
                        )
                    conn.commit()
'''
result_failure_new = '''                    if str(pending["step_kind"]) in {
                        "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                    }:
                        _terminalize_owned_continuation_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause=error,
                        )
                    elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                        _terminalize_owned_long_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause=error,
                        )
                    conn.commit()
'''
if text.count(result_failure) != 1:
    raise SystemExit(f'result failure branch count={text.count(result_failure)}')
text = text.replace(result_failure, result_failure_new, 1)

exception_failure = '''                if str(pending["step_kind"]) in {
                    "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                }:
                    _terminalize_owned_continuation_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
                conn.commit()
'''
exception_failure_new = '''                if str(pending["step_kind"]) in {
                    "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                }:
                    _terminalize_owned_continuation_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
                elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                    _terminalize_owned_long_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
                conn.commit()
'''
if text.count(exception_failure) != 1:
    raise SystemExit(f'exception failure branch count={text.count(exception_failure)}')
text = text.replace(exception_failure, exception_failure_new, 1)

path.write_text(text)
