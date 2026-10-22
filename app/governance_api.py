"""Demo governance API. Identity headers are NOT secure authentication."""
import uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from app import governance as g

router=APIRouter(prefix='/governance',tags=['governance'])

def identity(tenant:str,actor:str,role:str):
    if not tenant or not actor or not role: raise HTTPException(401,'Demo identity headers required')
    return tenant,actor,role

class ActionRequest(BaseModel):
    run_id: uuid.UUID
    tool_name: str
    arguments: dict[str,str]
    idempotency_key: str=Field(min_length=8,max_length=128)
class Decision(BaseModel):
    approve: bool

@router.post('/actions',status_code=202)
def create_action(body:ActionRequest,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    identity(x_tenant_id,x_actor_id,x_role)
    if x_role!='agent': raise HTTPException(403,'Agent role required')
    try:
        row=g.request_action(run_id=str(body.run_id),tenant_id=x_tenant_id,actor_id=x_actor_id,tool_name=body.tool_name,arguments=body.arguments,idempotency_key=body.idempotency_key)
        return {'action_id':str(row['action_id']),'status':row['status']}
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc

@router.post('/actions/{action_id}/decision')
def decision(action_id:uuid.UUID,body:Decision,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    identity(x_tenant_id,x_actor_id,x_role)
    if x_role!='approver': raise HTTPException(403,'Approver role required')
    try: status=g.decide(action_id=str(action_id),tenant_id=x_tenant_id,approver_id=x_actor_id,approve=body.approve)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    if status is None: raise HTTPException(404,'Action not found')
    return {'action_id':str(action_id),'status':status}

@router.post('/actions/{action_id}/execute')
def execute(action_id:uuid.UUID,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    identity(x_tenant_id,x_actor_id,x_role)
    if x_role!='executor': raise HTTPException(403,'Executor role required')
    try: status=g.execute(action_id=str(action_id),tenant_id=x_tenant_id,actor_id=x_actor_id)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    if status is None: raise HTTPException(404,'Action not found')
    return {'action_id':str(action_id),'status':status,'external_write':False}

@router.get('/runs/{run_id}/events')
def events(run_id:uuid.UUID,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    identity(x_tenant_id,x_actor_id,x_role)
    if x_role not in ('auditor','approver'): raise HTTPException(403,'Audit access required')
    return {'events':g.timeline(run_id=str(run_id),tenant_id=x_tenant_id)}


@router.get('/runs/{run_id}/explorer')
def explorer(run_id:uuid.UUID,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    identity(x_tenant_id,x_actor_id,x_role)
    if x_role not in ('auditor','approver'): raise HTTPException(403,'Audit access required')
    return {'run_id':str(run_id),'actions':g.list_actions(run_id=str(run_id),tenant_id=x_tenant_id),'events':g.timeline(run_id=str(run_id),tenant_id=x_tenant_id)}

@router.get('/actions/{action_id}')
def action_details(action_id:uuid.UUID,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    identity(x_tenant_id,x_actor_id,x_role)
    if x_role not in ('auditor','approver','executor'): raise HTTPException(403,'Audit access required')
    row=g.get_action(action_id=str(action_id),tenant_id=x_tenant_id)
    if row is None: raise HTTPException(404,'Action not found')
    return row
