"""Governed, checkpointed customer-risk workflow; all write operations are simulations."""
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from opentelemetry import trace
from app.action_policy import *  # legacy policies are retained; new gateway validates separately

class State(TypedDict, total=False):
    tenant_id: str
    run_id: str
    account_id: str
    evidence: dict[str, Any]
    risk_score: int
    action: dict[str, Any]
    decision: dict[str, Any]
    result: dict[str, Any]

def assess(state:State):
    # Deterministic fixture until production read connectors are authenticated.
    with trace.get_tracer('v1.agent').start_as_current_span('agent.assess') as span:
        span.set_attribute('agent.run_id',state['run_id'])
        evidence={'salesforce':{'account_id':state['account_id'],'status':'active'},
                  'jira':{'critical_incidents':2},'servicenow':{'open_incidents':3}}
        return {'evidence':evidence,'risk_score':85,
                'action':{'tool':'servicenow.incident.create',
                          'account_id':state['account_id'],
                          'short_description':'Investigate customer risk'}}

def request_approval(state:State):
    answer=interrupt({'type':'approval','run_id':state['run_id'],
                      'tool':state['action']['tool'],'account_id':state['account_id']})
    if not isinstance(answer,dict) or type(answer.get('approved')) is not bool:
        raise ValueError('Explicit approval decision required')
    return {'decision':answer}

def governed_execute(state:State):
    if not state['decision']['approved']:
        return {'result':{'status':'DENIED','external_write':False}}
    if state['action']['tool'] not in {'servicenow.incident.create'}:
        raise ValueError('Tool not allowlisted')
    # IMPORTANT: Never perform an external write in this node. Replay after crash
    # can re-run a node; use an outbox dispatcher and idempotency before enabling it.
    return {'result':{'status':'SIMULATED','external_write':False,
                      'tool':state['action']['tool']}}

def build_graph(saver):
    g=StateGraph(State)
    g.add_node('assess',assess)
    g.add_node('approval',request_approval)
    g.add_node('execute',governed_execute)
    g.add_edge(START,'assess');g.add_edge('assess','approval');g.add_edge('approval','execute');g.add_edge('execute',END)
    return g.compile(checkpointer=saver)
