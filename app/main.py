from contextlib import asynccontextmanager
from pathlib import Path
import secrets
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import Session, Event, Job, Alert, init_db, asdict
from .schemas import Batch, Feedback
from .rules import detect, RANK, redact

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title='Ops Guard MVP', lifespan=lifespan)
static = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=static), name='static')

def auth(authorization: str = Header(default='')):
    if not secrets.compare_digest(authorization, f'Bearer {settings.api_token}'):
        raise HTTPException(401, 'Invalid API token')

@app.get('/')
def index():
    return FileResponse(static / 'index.html')

@app.get('/health')
def health():
    with Session() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok', 'llm_mode': settings.llm_mode}

@app.post('/api/v1/events/batch', status_code=202, dependencies=[Depends(auth)])
def ingest(batch: Batch):
    accepted = duplicates = 0
    with Session.begin() as db:
        for item in batch.events:
            try:
                with db.begin_nested():
                    data = item.model_dump()
                    data['event_time'] = item.event_time.isoformat()
                    # Store only redacted commands in the MVP.
                    data['command'] = redact(item.command)
                    event = Event(**data)
                    db.add(event)
                    db.flush()
                    db.add(Job(event_pk=event.id))
                    hits = detect(item.command)
                    if hits:
                        top = max(hits, key=lambda h: RANK[h['severity']])
                        db.add(Alert(event_pk=event.id, severity=top['severity'], title=top['title'], evidence=[event.id]))
                accepted += 1
            except IntegrityError:
                duplicates += 1
    return {'accepted': accepted, 'duplicates': duplicates}

@app.get('/api/v1/events', dependencies=[Depends(auth)])
def events(session_id: str | None = None):
    with Session() as db:
        query = select(Event)
        if session_id:
            query = query.where(Event.session_id == session_id)
        return [asdict(e) for e in db.scalars(query.order_by(Event.id.desc()).limit(200))]

@app.get('/api/v1/alerts', dependencies=[Depends(auth)])
def alerts():
    with Session() as db:
        return [asdict(a) for a in db.scalars(select(Alert).order_by(Alert.id.desc()).limit(200))]

@app.get('/api/v1/jobs', dependencies=[Depends(auth)])
def jobs():
    with Session() as db:
        return [asdict(j) for j in db.scalars(select(Job).order_by(Job.id.desc()).limit(200))]

@app.get('/api/v1/alerts/{alert_id}', dependencies=[Depends(auth)])
def alert_detail(alert_id: int):
    with Session() as db:
        alert = db.get(Alert, alert_id)
        if not alert:
            raise HTTPException(404, 'Alert not found')
        return {**asdict(alert), 'events': [asdict(e) for e in db.scalars(select(Event).where(Event.id.in_(alert.evidence)).order_by(Event.id))]}

@app.post('/api/v1/alerts/{alert_id}/feedback', dependencies=[Depends(auth)])
def feedback(alert_id: int, payload: Feedback):
    with Session.begin() as db:
        alert = db.get(Alert, alert_id)
        if not alert:
            raise HTTPException(404, 'Alert not found')
        alert.status, alert.feedback = payload.status, payload.comment
        return asdict(alert)
