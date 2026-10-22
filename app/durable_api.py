"""LOCAL LAB ONLY. Demo identity headers MUST NOT be exposed to the internet.

Production requires Entra JWT validation, authorization, durable audit/outbox,
separate non-owner DB roles, and action executor isolation.
"""
import os
from contextlib import contextmanager
from uuid import uuid4, UUID
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command
from app.durable_workflow import build_graph, scoped_thread_id

router = APIRouter(prefix="/durable", tags=["durable-lab"])

class StartRequest(BaseModel):
    account_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")

class DecisionRequest(BaseModel):
    approved: bool

@contextmanager
def graph_context():
    dsn = os.getenv("CHECKPOINT_DATABASE_URL")
    if not dsn:
        raise HTTPException(503, "CHECKPOINT_DATABASE_URL not configured")
    from langgraph.checkpoint.postgres import PostgresSaver
    # The saver manages its own connection lifecycle; setup is a one-time
    # administrative bootstrap, not performed on every request.
    with PostgresSaver.from_conn_string(dsn) as saver:
        yield build_graph(saver)

def require_lab_identity(tenant, actor, role):
    if os.getenv("ENABLE_DURABLE_LAB", "false").lower() != "true":
        raise HTTPException(404, "Durable lab disabled")
    if not tenant or not actor or not role:
        raise HTTPException(401, "Lab identity headers required")
    if not tenant.replace('-', '').replace('_','').isalnum() or len(tenant)>64:
        raise HTTPException(400, "Invalid tenant")

@router.post("/runs", status_code=202)
def start_run(body: StartRequest, x_tenant_id: str=Header(), x_actor_id: str=Header(), x_role: str=Header()):
    require_lab_identity(x_tenant_id,x_actor_id,x_role)
    if x_role != "agent": raise HTTPException(403, "Agent role required")
    run_id = str(uuid4())
    config = {"configurable": {"thread_id": scoped_thread_id(x_tenant_id,run_id)}}
    with graph_context() as graph:
        state = graph.invoke({"tenant_id":x_tenant_id,"run_id":run_id,"account_id":body.account_id}, config=config)
        snapshot = graph.get_state(config)
    return {"run_id":run_id,"status":"PENDING_APPROVAL", "interrupts": [str(i.value.get('type')) for i in snapshot.interrupts], "risk_score":state.get("risk_score")}

@router.post("/runs/{run_id}/decision")
def decide(run_id: UUID, body: DecisionRequest, x_tenant_id: str=Header(), x_actor_id: str=Header(), x_role: str=Header()):
    require_lab_identity(x_tenant_id,x_actor_id,x_role)
    if x_role != "approver": raise HTTPException(403,"Approver role required")
    config = {"configurable":{"thread_id":scoped_thread_id(x_tenant_id,str(run_id))}}
    with graph_context() as graph:
        snapshot = graph.get_state(config)
        if not snapshot.values or snapshot.values.get("tenant_id") != x_tenant_id:
            raise HTTPException(404,"Run not found")
        if not snapshot.interrupts:
            raise HTTPException(409,"Run is not awaiting approval")
        state = graph.invoke(Command(resume={"approved":body.approved,"approver_id":x_actor_id}), config=config)
    return {"run_id":str(run_id),"result":state.get("result"),"decision":state.get("decision")}

@router.get("/runs/{run_id}")
def get_run(run_id: UUID,x_tenant_id:str=Header(),x_actor_id:str=Header(),x_role:str=Header()):
    require_lab_identity(x_tenant_id,x_actor_id,x_role)
    if x_role not in ("auditor","approver"):raise HTTPException(403,"Auditor role required")
    config={"configurable":{"thread_id":scoped_thread_id(x_tenant_id,str(run_id))}}
    with graph_context() as graph:
        snapshot=graph.get_state(config)
    if not snapshot.values or snapshot.values.get("tenant_id") != x_tenant_id:
        raise HTTPException(404,"Run not found")
    return {"run_id":str(run_id),"state":snapshot.values,"awaiting_approval":bool(snapshot.interrupts)}
