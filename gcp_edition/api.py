"""GCP v3 API. Reuses proven v2 PostgreSQL LangGraph approval/outbox core."""
import logging
from uuid import UUID,uuid4
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from app import v2_service
from app.v1_audit import connect, history
from gcp_edition.security import Principal, get_principal,require_role,authorize_approval
from gcp_edition.gemini import explain_run
from gcp_edition.pubsub import signal_action
from gcp_edition.telemetry import setup

logger = logging.getLogger(__name__)
app = FastAPI(title='Enterprise Agent Observability — GCP v3',version='3.0.0')
setup(app)

class Start(BaseModel):
    account_id: str=Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')

class Decision(BaseModel):
    approved: bool

@app.get('/healthz')
def healthz():
    return {'status':'ok','version':'3.0','durable_dependencies_checked':False}

@app.post('/gcp/v3/runs',status_code=202)
def start(body:Start,p:Principal=Depends(get_principal)):
    require_role(p,'Agent.Operator')
    try:
        return v2_service.begin(p.tenant,p.subject,body.account_id,str(uuid4()))
    except (RuntimeError,KeyError) as exc:
        logger.exception('Persistence unavailable')
        raise HTTPException(503,'Durable workflow unavailable') from exc

@app.post('/gcp/v3/runs/{run_id}/decision')
def decide(run_id:UUID,body:Decision,p:Principal=Depends(get_principal)):
    require_role(p,'Agent.Approver')
    run = str(run_id)
    try:
        with connect() as db:
            events=history(db,p.tenant,run)
        initiators=[e['actor_id'] for e in events if e['event_type']=='V2_APPROVAL_REQUESTED']
        if not initiators:
            raise HTTPException(404,'Run not found')
        authorize_approval(initiators[0],p.subject)
        result=v2_service.decision(p.tenant,p.subject,run,body.approved)
        # Advisory signal only; publisher failures never roll back approved work.
        if result.get('outbox_queued'):
            result['pubsub_signal_sent']=signal_action(p.tenant,run)
        return result
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503,'Persistence unavailable') from exc

@app.get('/gcp/v3/runs/{run_id}')
def inspect(run_id:UUID,p:Principal=Depends(get_principal)):
    require_role(p,'Agent.Auditor')
    return v2_service.inspect(p.tenant,str(run_id))

@app.get('/gcp/v3/runs/{run_id}/explanation')
def explain(run_id:UUID,p:Principal=Depends(get_principal)):
    require_role(p,'Agent.Auditor')
    # Only a fixed, safe projection reaches the model; no event payloads.
    run=v2_service.inspect(p.tenant,str(run_id))
    try:
        return explain_run(run)
    except Exception as exc:
        logger.exception('Inference error')
        raise HTTPException(503,'Inference unavailable') from exc
