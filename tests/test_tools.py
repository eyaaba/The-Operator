from agent import tools
from sandbox.reset import reset
from sandbox.db import connect
import agent.config as config
import sandbox.db as dbmod


def test_tools_end_to_end(tmp_path, monkeypatch):
    path=tmp_path/'test.db'
    reset(path=path)
    monkeypatch.setattr(dbmod, 'SANDBOX_DB', str(path))
    # config path loaded at import time in sandbox.db; replace directly
    assert len(tools.list_emails().data['emails'])==8
    assert tools.read_email('em_001').data['email']['sender']=='manager@acme.example'
    label=tools.apply_label('em_001','urgent')
    assert label.ok
    assert tools.apply_label('em_001','urgent').idempotent_replay
    assert tools.archive_email('em_002').ok
    draft=tools.draft_reply('em_001','Thanks, confirmed.')
    assert draft.ok
    assert tools.draft_reply('em_001','Thanks, confirmed.').idempotent_replay
    sent=tools.send_reply(draft.data['draft_id'])
    assert sent.ok and sent.data['to']=='manager@acme.example'
    assert tools.send_reply(draft.data['draft_id']).idempotent_replay
    assert tools.finish('Completed').ok
    conn=connect(path)
    assert conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]>=9
    assert conn.execute('SELECT COUNT(*) FROM sent').fetchone()[0]==1
    conn.close()


def test_faults_and_invalid_input(tmp_path, monkeypatch):
    path=tmp_path/'test.db';reset(path=path)
    monkeypatch.setattr(dbmod,'SANDBOX_DB',str(path))
    tools.set_faults([{'tool':'list_emails','error':'TOOL_UNAVAILABLE','times':1}])
    assert tools.list_emails().error_code.value=='TOOL_UNAVAILABLE'
    assert tools.list_emails().ok
    assert tools.read_email('bad_id').error_code.value=='INVALID_ARGUMENT'
    tools.set_faults([])
