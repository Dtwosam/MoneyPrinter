"""Disposable packages only; network guard is installed before collection."""
from datetime import timedelta
import json
from pathlib import Path

import pytest

from printer_v1.operator_cli import failed_run_cleanup_authorization_preparation as auth
from printer_v1.operator_cli import failed_run_cleanup_one_shot_wrapper as wrapper
from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
from tests.test_factory_step_terminal_closure import seed_step_closure_graph, _rows
from tests.test_v2_9_8b_reconcile_already_terminal_factory_persist_repair import (
    CAMPAIGN, RUN, CYCLE, FACTORY, CONFIG, NOW, _open,
)


@pytest.fixture
def package(tmp_path,monkeypatch):
    tmp_path=tmp_path.resolve()
    db=seed_step_closure_graph(tmp_path)
    root=tmp_path/'historical';root.mkdir()
    scope=dict(execution_id='historical-execution',campaign_id=CAMPAIGN,run_id=RUN,
        cycle_id=CYCLE,factory_run_id=FACTORY,configuration_id=CONFIG,
        supervision_id='supervision',owner_id='owner')
    lease=root/'campaign.lease.lock'
    acquire_campaign_supervision(db,lock_path=lease,**{k:scope[k] for k in ('supervision_id','campaign_id','configuration_id','run_id','owner_id')},now=NOW,lease_seconds=90)
    c=_open(db)
    with c:
        for job in (1,2):
            c.execute('''INSERT INTO printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id,ownership_contract_version,campaign_id,run_id,cycle_id,token_slot_id,window_id,
                work_intent,deadline_at,work_state,scheduler_job_id,created_at,updated_at)
                VALUES (?,'V1_WINDOW_BOUND',?,?,?,'slot','window','SNAPSHOT',?,'PENDING',?,?,?)''',
                (f'work-{job}',CAMPAIGN,RUN,CYCLE,NOW.isoformat(),job,NOW.isoformat(),NOW.isoformat()))
        c.execute("""INSERT INTO printer_discovery_batches(
            discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,cycle_cutoff,
            policy_version,provider_contract_versions_json,git_provenance_identity,
            campaign_selection_seed_identity,cycle_seed_hash,pump_continuity_state,
            batch_state,canonical_hash,created_at)
            VALUES ('batch',?,?,?,?,?,'fixture','{}','git','seed',?,'NONE','DISCOVERING',?,?)""",
            (CAMPAIGN,CONFIG,RUN,CYCLE,NOW.isoformat(),'a'*64,'b'*64,NOW.isoformat()))
        c.execute("""INSERT INTO printer_scheduler_jobs(id,job_name,job_kind,status,scheduled_for)
            VALUES (9,'discovery-fixture','DISCOVERY','SUCCEEDED',?)""", (NOW.isoformat(),))
        c.execute("""INSERT INTO printer_discovery_work(discovery_work_id,discovery_batch_id,
            campaign_id,run_id,cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
            first_terminal_cause,terminal_at,created_at,updated_at)
            VALUES ('discovery-work','batch',?,?,?,9,'DISCOVERY_IDENTITY_MERGE','SUCCEEDED',?,
            'COMPLETED',?,?,?)""", (CAMPAIGN,RUN,CYCLE,*([NOW.isoformat()]*4)))
        def clone(table, changes):
            row=dict(c.execute('SELECT * FROM '+table+' LIMIT 1').fetchone());row.update(changes)
            c.execute('INSERT INTO '+table+' ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
        clone('printer_tokens',dict(id=2,token_mint='mint-2'))
        clone('printer_pairs',dict(id=2,token_id=2,pair_address='pair-2'))
        clone('printer_tracking_queue',dict(id=2,token_id=2,pair_id=2))
        clone('printer_memory_factory_campaign_token_slots',dict(token_slot_id='slot-2',slot_ordinal=2,
            token_row_id=2,pair_row_id=2,tracking_queue_id=2,token_identity='token-2',mint_identity='mint-2',pair_identity='pair-2'))
        clone('printer_memory_factory_campaign_windows',dict(window_id='window-2',token_slot_id='slot-2',token_row_id=2,pair_row_id=2))
    c.close()
    summary=root/'terminal-summary.json'
    summary.write_bytes(auth.canonical(dict(execution_id=scope['execution_id'],campaign_id=CAMPAIGN,
        run_id=RUN,configuration_id=CONFIG,first_terminal_cause=auth.CAUSE,
        accounting_status='NOT_FINALIZED_CLEANUP_UNPROVEN',report_written=False,
        report_block_reason='TERMINAL_CLEANUP_UNPROVEN')))
    monkeypatch.setattr(auth,'APPLICATION_ROOT',tmp_path/'applications')
    monkeypatch.setattr(auth,'_live_git_facts',lambda _:dict(branch='fixture',head='a'*40,remote_head='a'*40,tracked_clean=True))
    monkeypatch.setattr(auth,'runtime_processes',lambda _:())
    now=NOW+timedelta(minutes=5)
    arguments=dict(repository_root=str(tmp_path),database_path=str(db),scope=scope,
                   summary_path=str(summary),artifact_roots=[str(root)],now=now)
    facts=auth.inspect_cleanup(**arguments)
    authorization=tmp_path/'authorization.json'
    prepared=auth.prepare_cleanup_authorization(authorization_id='fixture-cleanup',repository_root=str(tmp_path),
        summary_path=str(summary),artifact_roots=[str(root)],expected_facts=facts,
        prior_authorizations_non_reusable=['consumed-standard-4h'],destination=str(authorization),now=now)
    return dict(db=db,scope=scope,summary=summary,root=root,lease=lease,now=now,facts=facts,
                args=arguments,authorization=authorization,prepared=prepared,
                application=auth.APPLICATION_ROOT/'fixture-cleanup')


def apply(p):
    return wrapper.apply_cleanup_authorization(authorization_file=str(p['authorization']),
        expected_sha256=p['prepared']['sha256'],operator_approved=True,now=p['now'])


def test_success_marker_before_owners_and_no_report(package,monkeypatch):
    p=package;before=_rows(p['db']);historical=p['summary'].read_bytes();order=[]
    for name in ('cleanup_campaign_supervision','reconcile_campaign_terminal','verify_zero_state'):
        real=getattr(wrapper,name)
        def observe(*args,_real=real,_name=name,**kwargs):
            assert (p['application']/wrapper.MARKER).is_file()
            order.append(_name)
            return _real(*args,**kwargs)
        monkeypatch.setattr(wrapper,name,observe)
    assert not p['application'].exists()
    result=apply(p)
    assert order==['cleanup_campaign_supervision','reconcile_campaign_terminal','verify_zero_state']
    assert result['status']=='FAILED_RUN_CLEANUP_COMPLETE'
    assert result['active_work']['clean_terminal'] is True
    assert result['report_written'] is False
    assert result['accounting_status']=='SIX_UNIT_ACCOUNTING_BLOCKED'
    assert result['report_block_reason']=='SIX_UNIT_EVIDENCE_MISSING'
    assert p['summary'].read_bytes()==historical and not p['lease'].exists()
    after=_rows(p['db'])
    assert after['printer_memory_factory_campaign_reports']==before['printer_memory_factory_campaign_reports']==[]
    assert after['printer_memory_factory_runs'][0]['final_report_json'] is None
    assert after['printer_memory_factory_run_steps'][0]==before['printer_memory_factory_run_steps'][0]
    assert after['printer_memory_factory_runs'][1]==before['printer_memory_factory_runs'][1]
    assert after['printer_token_snapshots']==before['printer_token_snapshots']
    assert not (p['root']/'reports').exists()
    resolution=p['application']/wrapper.RESOLUTION
    assert json.loads(resolution.read_bytes())==result
    wrapper.write_campaign_terminal_summary(resolution,summary=result)
    with pytest.raises(Exception,match='differs'):
        wrapper.write_campaign_terminal_summary(resolution,summary={**result,'first_terminal_cause':'WRONG'})
    with pytest.raises(auth.CleanupAuthorizationError,match='consumed'):
        apply(p)
    assert _rows(p['db'])==after and len(order)==3


@pytest.mark.parametrize('gate', ['git','sha','physical','migration','integrity','fk','process','sidecar',
    'jobs','steps','window','slot','queue','lifecycle','cause','historical_hash','report','factory_report','evidence','lease'])
def test_preconsumption_drift_is_unconsumed(package,monkeypatch,gate):
    p=package
    if gate=='git':monkeypatch.setattr(auth,'_live_git_facts',lambda _:dict(branch='fixture',head='b'*40,remote_head='b'*40,tracked_clean=True))
    elif gate=='process':monkeypatch.setattr(auth,'runtime_processes',lambda _:(123,))
    elif gate in ('integrity','fk'):
        monkeypatch.setattr(auth,'health',lambda _:auth.require(False,gate+' failed'))
    elif gate=='sidecar':Path(str(p['db'])+'-wal').write_bytes(b'blocked')
    elif gate=='physical':
        content=p['db'].read_bytes();replacement=p['db'].with_suffix('.replacement');replacement.write_bytes(content);replacement.replace(p['db'])
    elif gate in ('window','slot'):
        document=json.loads(p['authorization'].read_bytes())
        table,key=('printer_memory_factory_campaign_windows','window_id') if gate=='window' else ('printer_memory_factory_campaign_token_slots','token_slot_id')
        document['facts']['residue'][table][0][key]='wrong-identity'
        p['authorization'].chmod(0o600);p['authorization'].write_bytes(auth.canonical(document))
        p['prepared']['sha256']=auth.file_identity(str(p['authorization']))['sha256']
    elif gate in ('cause','historical_hash','evidence'):
        data=json.loads(p['summary'].read_bytes())
        if gate=='cause':data['first_terminal_cause']='WRONG'
        elif gate=='evidence':data['six_unit_evidence']={'evidence_kind':'CAMPAIGN_SIX_UNIT_EVIDENCE_V2'}
        else:data['extra']='drift'
        p['summary'].write_bytes(auth.canonical(data))
    elif gate=='lease':
        data=json.loads(p['lease'].read_bytes());data['owner_id']='different';p['lease'].write_bytes(auth.canonical(data))
    else:
        c=_open(p['db'])
        with c:
            queries={
                'sha':"UPDATE printer_tokens SET symbol='drift' WHERE id=1",
                'migration':"DELETE FROM printer_schema_migrations WHERE version LIKE '064%'",
                'jobs':"UPDATE printer_scheduler_jobs SET job_name='changed' WHERE id=1",
                'steps':"UPDATE printer_memory_factory_run_steps SET step_key='changed' WHERE step_key='mixed-1'",
                'window':"UPDATE printer_memory_factory_campaign_windows SET root_15m_lifecycle_identity='changed'",
                'slot':"UPDATE printer_memory_factory_campaign_token_slots SET token_identity='changed'",
                'queue':"UPDATE printer_tracking_queue SET priority_reason='changed'",
                'lifecycle':"UPDATE printer_memory_factory_run_steps SET snapshot_id=NULL",
                'factory_report':"UPDATE printer_memory_factory_runs SET final_report_json='{}'",
                'report':"INSERT INTO printer_memory_factory_campaign_reports(report_id,campaign_id,configuration_id,report_kind,report_state) VALUES ('unexpected','campaign-1','configuration-1','TERMINAL','REPORT_PENDING')",
            }
            c.execute(queries[gate])
        c.close()
    before=p['db'].read_bytes()
    with pytest.raises(Exception):apply(p)
    assert not p['application'].exists()
    assert p['db'].read_bytes()==before


@pytest.mark.parametrize('failure',['cleanup_campaign_supervision','reconcile_campaign_terminal','verify_zero_state','resolution'])
def test_consumed_failure_never_retries(package,monkeypatch,failure):
    p=package;calls=[]
    def fail(*args,**kwargs):
        assert (p['application']/wrapper.MARKER).exists();calls.append(failure);raise RuntimeError('injected '+failure)
    if failure=='resolution':
        real=wrapper.write_campaign_terminal_summary
        def write(path,**kwargs):
            if path.name==wrapper.RESOLUTION:return fail()
            return real(path,**kwargs)
        monkeypatch.setattr(wrapper,'write_campaign_terminal_summary',write)
    else:monkeypatch.setattr(wrapper,failure,fail)
    with pytest.raises(RuntimeError,match='injected'):apply(p)
    assert (p['application']/wrapper.MARKER).exists()
    result=json.loads((p['application']/wrapper.TERMINAL).read_text())
    assert result['consumed'] is True and result['first_terminal_cause']==auth.CAUSE
    assert result['status']=='FAILED_RUN_CLEANUP_APPLICATION_FAILED'
    assert result['restart_created'] is result['successor_created'] is False
    before=p['db'].read_bytes()
    with pytest.raises(auth.CleanupAuthorizationError,match='consumed'):apply(p)
    assert p['db'].read_bytes()==before and calls==[failure]


@pytest.mark.parametrize('change',['schema','mode','policy','sequence','expiry','hash','approval','prior'])
def test_authorization_contract(package,change):
    p=package;doc=json.loads(p['authorization'].read_bytes())
    if change=='schema':doc['unexpected']=True
    if change=='mode':doc['facts']['mode']='REPORT_ELIGIBLE'
    if change=='policy':doc['one_shot_policy']['resume_allowed']=True
    if change=='sequence':doc['owner_sequence'].reverse()
    if change=='expiry':doc['expires_at']=(p['now']-timedelta(seconds=1)).isoformat()
    if change=='prior':doc['prior_authorizations_non_reusable']=['fixture-cleanup']
    p['authorization'].chmod(0o600);p['authorization'].write_bytes(auth.canonical(doc))
    sha=auth.file_identity(str(p['authorization']))['sha256']
    with pytest.raises(Exception):
        wrapper.apply_cleanup_authorization(authorization_file=str(p['authorization']),
            expected_sha256='0'*64 if change=='hash' else sha,
            operator_approved=change!='approval',now=p['now'])
    assert not p['application'].exists()


def test_preparation_rejects_drift_without_publishing(package):
    p=package;facts=json.loads(json.dumps(p['facts']));facts['database']['sha256']='0'*64
    destination=p['authorization'].parent/'never-created.json';before=p['db'].read_bytes()
    with pytest.raises(auth.CleanupAuthorizationError,match='drift'):
        auth.prepare_cleanup_authorization(authorization_id='new-fixture',
            repository_root=p['args']['repository_root'],summary_path=str(p['summary']),
            artifact_roots=[str(p['root'])],expected_facts=facts,
            prior_authorizations_non_reusable=[],destination=str(destination),now=p['now'])
    assert not destination.exists() and not p['application'].exists()
    assert p['db'].read_bytes()==before


@pytest.mark.parametrize('tamper',['marker','provenance','authorization'])
def test_consumed_package_is_validated_before_mutation(package,monkeypatch,tamper):
    p=package;before=p['db'].read_bytes();real=wrapper.validate_consumed_package
    def corrupt(directory,*args):
        filename={'marker':wrapper.MARKER,'provenance':'provenance.json','authorization':'authorization.json'}[tamper]
        path=directory/filename;path.chmod(0o600);path.write_bytes(b'{}')
        return real(directory,*args)
    monkeypatch.setattr(wrapper,'validate_consumed_package',corrupt)
    with pytest.raises(Exception):apply(p)
    assert p['db'].read_bytes()==before
    assert (p['application']/wrapper.MARKER).exists()
    with pytest.raises(auth.CleanupAuthorizationError,match='consumed'):apply(p)


@pytest.mark.parametrize('tamper',['active_step','unrelated_row'])
def test_independent_reader_rejects_false_owner_success(package,monkeypatch,tamper):
    p=package;real=wrapper.reconcile_campaign_terminal
    def corrupt(*args,**kwargs):
        result=real(*args,**kwargs)
        c=_open(p['db'])
        with c:
            c.execute("UPDATE printer_memory_factory_run_steps SET step_status='PENDING' WHERE step_key='mixed-1'" if tamper=='active_step'
                      else "UPDATE printer_tokens SET symbol='unexpected-write' WHERE id=1")
        c.close();return result
    monkeypatch.setattr(wrapper,'reconcile_campaign_terminal',corrupt)
    with pytest.raises(auth.CleanupAuthorizationError):apply(p)
    assert not (p['application']/wrapper.RESOLUTION).exists()
    assert (p['application']/wrapper.MARKER).exists()


def test_prior_cleanup_inventory_uses_canonical_nonreuse_law(package):
    p=package;old=auth.APPLICATION_ROOT/'previous-cleanup';old.mkdir(parents=True)
    (old/wrapper.MARKER).write_bytes(b'permanently consumed')
    with pytest.raises(auth.CleanupAuthorizationError,match='non-reuse'):
        apply(p)
    assert not p['application'].exists()
    document=json.loads(p['authorization'].read_bytes())
    document['prior_authorizations_non_reusable'].append('previous-cleanup')
    auth.validate_prior_inventory(document)
    assert (old/wrapper.MARKER).read_bytes()==b'permanently consumed'


def test_runtime_probe_covers_governor_scheduler(monkeypatch):
    monkeypatch.setattr(auth,'active_printer_runtime_processes',lambda _:(71,))
    monkeypatch.setattr(auth,'host_process_inventory',lambda:[(72,'python source_governor'),(73,'python central_scheduler'),(74,'unrelated')])
    assert auth.runtime_processes('unused')==[71,72,73]
