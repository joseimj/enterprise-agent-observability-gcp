from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from app.v1_workflow import build_graph
from app.v1_api import config
import os

def test_checkpoint_survives_graph_recreation(tenant,run_id):
    dsn=os.environ['CHECKPOINT_DATABASE_URL']
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()  # idempotent initialization for local isolated lab
        graph=build_graph(saver)
        graph.invoke({'tenant_id':tenant,'run_id':run_id,'account_id':'ACME'},config=config(tenant,run_id))
        assert graph.get_state(config(tenant,run_id)).interrupts
    # A fresh graph instance simulates application process restart.
    with PostgresSaver.from_conn_string(dsn) as saver:
        graph=build_graph(saver)
        assert graph.get_state(config(tenant,run_id)).interrupts
        completed=graph.invoke(Command(resume={'approved':False,'approver_id':'test'}),config=config(tenant,run_id))
        assert completed['result']['status']=='DENIED'
