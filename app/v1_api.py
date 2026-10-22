"""Authenticated durable workflow API. Requires Entra, PostgreSQL and initialized schemas."""
import os
from contextlib import contextmanager
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command
from app.v1_identity import Principal, require_principal, require_role
from app.v1_audit import connect, record, history
from app.v1_workflow import build_graph

router=APIRouter(prefix='/v1',tags=['v1-governed-agent'])
class Start(BaseModel):
    account_id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')
class Decision(BaseModel):
    approved:bool

@contextmanager
def graph_context():
    from langgraph.checkpoint.postgres import PostgresSaver
    dsn=os.getenv('CHECKPOINT_DATABASE_URL')
    if not dsn:raise HTTPException(503,'Checkpointer not configured')
    with PostgresSaver.from_conn_string(dsn) as saver:
        yield build_graph(saver)

def config(tenant,run):
    return {'configurable':{'thread_id':f'v1:{tenant}:{run}'}}

def existing(graph,tenant,run):
    snap=graph.get_state(config(tenant,run))
    if not snap.values or snap.values.get('tenant_id')!=tenant:
        raise HTTPException(404,'Run not found')
    return snap

@router.post('/runs',status_code=202)
def start(body:Start,p:Principal=Depends(require_principal)):
    require_role(p,'Agent.Operator')
    run=str(uuid4())
    # Write audit event before starting the graph, so attempted execution is visible.
    with connect() as db:
        record(db,p.tenant,run,'RUN_REQUESTED',p.subject,{'account_id':body.account_id})
    with graph_context() as graph:
        graph.invoke({'tenant_id':p.tenant,'run_id':run,'account_id':body.account_id},config=config(p.tenant,run))
        snap=existing(graph,p.tenant,run)
    with connect() as db:
        record(db,p.tenant,run,'APPROVAL_REQUESTED',p.subject,{'tool':snap.values['action']['tool']})
    return {'run_id':run,'status':'PENDING_APPROVAL','risk_score':snap.values['risk_score']}

@router.post('/runs/{run_id}/decision')
def decide(run_id:UUID,body:Decision,p:Principal=Depends(require_principal)):
    require_role(p,'Agent.Approver')
    run=str(run_id)
    with graph_context() as graph:
        snap=existing(graph,p.tenant,run)
        if not snap.interrupts:raise HTTPException(409,'Run is not awaiting approval')
        # Record the decision first. A production implementation must additionally
        # enforce one-time approvals with a transactional state machine.
        with connect() as db:
            record(db,p.tenant,run,'APPROVAL_DECISION',p.subject,{'approved':body.approved})
        state=graph.invoke(Command(resume={'approved':body.approved,'approver_id':p.subject}),
                           config=config(p.tenant,run))
    with connect() as db:
        record(db,p.tenant,run,'ACTION_RESULT',p.subject,state['result'])
    return {'run_id':run,'result':state['result']}

@router.get('/runs/{run_id}')
def get_run(run_id:UUID,p:Principal=Depends(require_principal)):
    require_role(p,'Agent.Auditor')
    run=str(run_id)
    with graph_context() as graph:
        snap=existing(graph,p.tenant,run)
    with connect() as db:
        events=history(db,p.tenant,run)
    return {'run_id':run,'state':snap.values,'awaiting_approval':bool(snap.interrupts),'audit':events}
