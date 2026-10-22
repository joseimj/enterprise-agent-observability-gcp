import os
from typing import TypedDict, Any
import httpx
from langgraph.graph import StateGraph, START, END
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("customer-risk-agent")
class State(TypedDict, total=False):
    account_id: str
    scenario: str
    customer: dict[str, Any]
    incidents: list[dict[str, Any]]
    itsm_incidents: list[dict[str, Any]]
    risk: dict[str, Any]
    documents: list[dict[str, Any]]
    explanation: dict[str, Any]

async def fetch(url, params=None):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def customer(state: State):
    from app.enterprise_tools import read_tool
    data = await read_tool("salesforce.account.read", state["account_id"], state.get("scenario", "normal"))
    return {"customer": data}

async def incidents(state: State):
    from app.enterprise_tools import read_tool
    data = await read_tool("jira.incidents.read", state["account_id"], state.get("scenario", "normal"))
    return {"incidents": data["incidents"]}

async def itsm(state: State):
    from app.enterprise_tools import read_tool
    data = await read_tool("servicenow.itsm.read", state["account_id"], state.get("scenario", "normal"))
    return {"itsm_incidents": data["incidents"]}

def assess(state: State):
    with tracer.start_as_current_span("agent.risk_assessment") as span:
        issues = state["incidents"] + [{**i, "key": i["number"]} for i in state["itsm_incidents"]]
        critical = sum(i["severity"] == "critical" and i["status"] == "open" for i in issues)
        breaches = sum(i["sla_breached"] for i in issues)
        score = min(100, 20 + 40 * critical + 25 * breaches + 5 * len(issues))
        span.set_attribute("risk.score", score)
        return {"risk": {"score": score, "level": "high" if score >= 70 else "medium" if score >= 40 else "low", "evidence": [i["key"] for i in issues], "summary": f"{len(issues)} incidents, {critical} open critical, {breaches} SLA breaches", "recommendation": "Escalate critical incident and review SLA remediation" if score >= 70 else "Continue monitoring"}}

def knowledge(state: State):
    from app.knowledge import retrieve
    return {"documents": retrieve(state["risk"])}

def explain_risk(state: State):
    from app.inference import explain
    return {"explanation": explain(state["risk"],state["documents"])}

builder = StateGraph(State)
builder.add_node("customer", customer)
builder.add_node("incidents", incidents)
builder.add_node("assess", assess)
builder.add_edge(START, "customer")
builder.add_edge("customer", "incidents")
builder.add_node("itsm", itsm)
builder.add_edge("incidents", "itsm")
builder.add_edge("itsm", "assess")
builder.add_node("knowledge", knowledge)
builder.add_node("explain", explain_risk)
builder.add_edge("assess", "knowledge")
builder.add_edge("knowledge", "explain")
builder.add_edge("explain", END)
graph = builder.compile()
