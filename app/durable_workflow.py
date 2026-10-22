"""Durable, explicitly approved mock ServiceNow action (no external writes).

The graph is compiled with a caller-supplied checkpointer. This module never
constructs a global in-memory checkpointer for production use.
"""
from typing import Any, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

class DurableState(TypedDict, total=False):
    tenant_id: str
    run_id: str
    account_id: str
    risk_score: int
    proposed_action: dict[str, Any]
    decision: dict[str, Any]
    result: dict[str, Any]

def evaluate(state: DurableState) -> dict:
    # Deterministic lab scenario. Real integrations must pass through the governed gateway.
    return {"risk_score": 85, "proposed_action": {
        "tool": "servicenow.incident.create", "account_id": state["account_id"],
        "short_description": f"Investigate high risk account {state['account_id']}"}}

def approval(state: DurableState) -> dict:
    decision = interrupt({"type": "human_approval", "run_id": state["run_id"],
                          "tenant_id": state["tenant_id"], "action": state["proposed_action"]})
    if not isinstance(decision, dict) or type(decision.get("approved")) is not bool:
        raise ValueError("Approval must explicitly include approved: boolean")
    if not decision.get("approver_id") or not isinstance(decision["approver_id"], str):
        raise ValueError("A verified approver identity is required")
    return {"decision": {"approved": decision["approved"], "approver_id": decision["approver_id"]}}

def mock_execute(state: DurableState) -> dict:
    if not state["decision"]["approved"]:
        return {"result": {"status": "DENIED", "external_write": False}}
    # Only a simulation: do not replace this with a real connector without
    # idempotency, outbox, policy evaluation, and reconciliation.
    return {"result": {"status": "SIMULATED", "external_write": False,
                       "tool": state["proposed_action"]["tool"]}}

def build_graph(checkpointer):
    builder = StateGraph(DurableState)
    builder.add_node("evaluate", evaluate)
    builder.add_node("approval", approval)
    builder.add_node("execute", mock_execute)
    builder.add_edge(START, "evaluate")
    builder.add_edge("evaluate", "approval")
    builder.add_edge("approval", "execute")
    builder.add_edge("execute", END)
    return builder.compile(checkpointer=checkpointer)

def scoped_thread_id(tenant_id: str, run_id: str) -> str:
    from uuid import UUID
    if not tenant_id or not tenant_id.replace('-', '').replace('_','').isalnum() or len(tenant_id)>64:
        raise ValueError("Invalid tenant identifier")
    return f"{tenant_id}:{UUID(run_id)}"
