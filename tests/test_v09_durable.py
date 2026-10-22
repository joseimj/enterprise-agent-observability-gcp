"""Graph-level tests use in-memory saver only; PostgreSQL requires integration environment."""
from uuid import uuid4
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from app.durable_workflow import build_graph, scoped_thread_id

def test_approval_resume():
    graph=build_graph(MemorySaver())
    run_id=str(uuid4()); config={"configurable":{"thread_id":scoped_thread_id("tenant_a",run_id)}}
    graph.invoke({"tenant_id":"tenant_a","run_id":run_id,"account_id":"ACME"},config)
    assert graph.get_state(config).interrupts
    result=graph.invoke(Command(resume={"approved":True,"approver_id":"human-1"}),config)
    assert result["result"]["status"] == "SIMULATED"
    assert result["result"]["external_write"] is False
    assert not graph.get_state(config).interrupts

def test_rejected_action():
    graph=build_graph(MemorySaver()); rid=str(uuid4())
    cfg={"configurable":{"thread_id":scoped_thread_id("tenant_b",rid)}}
    graph.invoke({"tenant_id":"tenant_b","run_id":rid,"account_id":"ACME"},cfg)
    result=graph.invoke(Command(resume={"approved":False,"approver_id":"human-2"}),cfg)
    assert result["result"]["status"] == "DENIED"

def test_thread_namespaced():
    rid=str(uuid4())
    assert scoped_thread_id("tenant_a",rid) != scoped_thread_id("tenant_b",rid)
    with pytest.raises(ValueError): scoped_thread_id("../../evil",rid)
