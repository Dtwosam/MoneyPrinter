from pathlib import Path


PATH = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
text = PATH.read_text(encoding="utf-8")

old_opening = '''            _plan_opening_jobs(
                conn,
                run_id,
                targets,
                _now(),
'''
new_opening = '''            planning_targets = targets
            if four_token_proof_controller is not None:
                if campaign_id is None or campaign_run_id is None or cycle_id is None:
                    raise ValueError(
                        "four-token Cycle-1 planning requires campaign/run/cycle identity"
                    )
                planning_targets = _cycle_targets_for_factory(
                    conn,
                    campaign_id=str(campaign_id),
                    campaign_run_id=str(campaign_run_id),
                    cycle_id=str(cycle_id),
                )
            _plan_opening_jobs(
                conn,
                run_id,
                planning_targets,
                _now(),
'''
if text.count(old_opening) != 1:
    raise SystemExit(f"opening patch anchor count={text.count(old_opening)}")
text = text.replace(old_opening, new_opening, 1)

old_exception = '''    except Exception as exc:
        if getattr(exc, "post_handoff_proof_fault", False):
            proof_fault = exc
'''
new_exception = '''    except Exception as exc:
        if conn.in_transaction:
            conn.rollback()
        if getattr(exc, "post_handoff_proof_fault", False):
            proof_fault = exc
'''
if text.count(old_exception) != 1:
    raise SystemExit(f"outer exception patch anchor count={text.count(old_exception)}")
text = text.replace(old_exception, new_exception, 1)

PATH.write_text(text, encoding="utf-8")
