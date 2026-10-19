import logging
import time
import uuid
from sqlalchemy import select, update, and_, or_
from .db import Session, Event, Job, Alert, asdict, now
from .analysis import graph
from .rules import RANK

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def run_once():
    token = str(uuid.uuid4())
    with Session.begin() as db:
        db.execute(update(Job).where(Job.status == 'running', Job.lease_until < now(), Job.attempts >= 3).values(status='failed', error='LeaseExpired: retry limit reached'))
        available = and_(Job.attempts < 3, or_(Job.status == 'pending', and_(Job.status == 'running', Job.lease_until < now())))
        job_id = db.scalar(select(Job.id).where(available).order_by(Job.id).limit(1))
        if job_id is None:
            return False
        claimed = db.execute(update(Job).where(Job.id == job_id, available).values(status='running', claim_token=token, lease_until=now()+120, attempts=Job.attempts+1))
        if not claimed.rowcount:
            return True
        job = db.get(Job, job_id)
        event = db.get(Event, job.event_pk)
        # No future received events, no unrelated actor/asset in the same source session.
        rows = list(db.scalars(select(Event).where(Event.source_id == event.source_id, Event.session_id == event.session_id, Event.actor_id == event.actor_id, Event.asset_id == event.asset_id, Event.id <= event.id).order_by(Event.id.desc()).limit(30)))
        payload = [{k: asdict(e)[k] for k in ('id', 'command', 'event_time', 'exit_code', 'actor_id', 'asset_id')} for e in reversed(rows)]
    try:
        result = graph.invoke({'events': payload})['result']
        with Session.begin() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.claim_token != token:
                return True
            alert = db.scalar(select(Alert).where(Alert.event_pk == job.event_pk))
            if result['assessment'] == 'suspicious' and alert is None:
                alert = Alert(event_pk=job.event_pk, severity=result['severity'], title=result['summary'], evidence=result['evidence_ids'])
                db.add(alert)
            if alert:
                alert.analysis = result
                if RANK[result['severity']] > RANK[alert.severity]:
                    alert.severity = result['severity']
                alert.evidence = sorted(set(alert.evidence + result['evidence_ids']))
            job.status, job.result, job.error = 'done', result, None
    except Exception as exc:
        # Do not persist provider errors that may echo credentials or full prompts.
        with Session.begin() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.claim_token == token:
                job.status = 'failed' if job.attempts >= 3 else 'pending'
                job.error = type(exc).__name__ + ': analysis failed; inspect model configuration'
        log.warning('Analysis job %s failed (%s)', job_id, type(exc).__name__)
    return True

def main():
    # Tables are initialized by the API before this container starts.
    while True:
        try:
            active = run_once()
        except Exception:
            log.exception('Worker database operation failed')
            active = False
        time.sleep(0.2 if active else 1)

if __name__ == '__main__':
    main()
