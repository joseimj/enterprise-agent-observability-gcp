"""Authenticated v2 API: approvals are one-time, external writes are outbox-only."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.v1_identity import Principal, require_principal, require_role
from app import v2_service

router=APIRouter(prefix='/v2',tags=['v2-governed-agent'])
class Start(BaseModel):
    account_id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')
class Decision(BaseModel):
    approved:bool

@router.post('/runs',status_code=202)
def start(body:Start,p:Principal=Depends(require_principal)):
    require_role(p,'Agent.Operator')
    try:
        return v2_service.begin(p.tenant,p.subject,body.account_id,str(uuid4()))
    except RuntimeError:
        raise HTTPException(503,'Persistence unavailable')

@router.post('/runs/{run_id}/decision')
def decide(run_id:UUID,body:Decision,p:Principal=Depends(require_principal)):
    require_role(p,'Agent.Approver')
    try:
        return v2_service.decision(p.tenant,p.subject,str(run_id),body.approved)
    except ValueError as exc:
        raise HTTPException(409,str(exc))

@router.get('/runs/{run_id}')
def get_run(run_id:UUID,p:Principal=Depends(require_principal)):
    require_role(p,'Agent.Auditor')
    return v2_service.inspect(p.tenant,str(run_id))
