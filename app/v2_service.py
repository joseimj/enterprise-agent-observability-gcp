"""v2 orchestration: transactional decision before replay-safe graph resume.

No external write is performed in this module. A separate worker consumes the outbox.
"""
from uuid import UUID
from app.v1_audit import connect, record, history
from app.v11_governance import request_approval, decide_once
from app.v1_api import graph_context, config, existing
from langgraph.types import Command

TOOL = 'servicenow.incident.create'

def begin(tenant: str, actor: str, account_id: str, run_id: str):
    UUID(run_id)
    with graph_context() as graph:
        graph.invoke({'tenant_id': tenant, 'run_id': run_id, 'account_id': account_id}, config=config(tenant,run_id))
        snap = existing(graph,tenant,run_id)
        if not snap.interrupts or snap.values['action']['tool'] != TOOL:
            raise ValueError('Unexpected graph state or tool')
    # Both approval request and audit record commit atomically.
    with connect() as db:
        request_approval(db,tenant,run_id)
        record(db,tenant,run_id,'V2_APPROVAL_REQUESTED',actor,{'tool':TOOL})
    return {'run_id':run_id,'status':'PENDING_APPROVAL','risk_score':snap.values['risk_score']}

def decision(tenant: str, actor: str, run_id: str, approved: bool):
    UUID(run_id)
    with graph_context() as graph:
        snap = existing(graph,tenant,run_id)
        if not snap.interrupts:
            raise ValueError('Run is not awaiting approval')
        action = snap.values['action']
        if action['tool'] != TOOL:
            raise ValueError('Tool not allowlisted')
        # Decision, audit and outbox are one database transaction.
        with connect() as db:
            status=decide_once(db,tenant,run_id,actor,approved,TOOL,action)
            record(db,tenant,run_id,'V2_DECISION_COMMITTED',actor,
                   {'approved':approved,'tool':TOOL,'queued':approved})
        # Graph replay is advisory. If this fails, the approved outbox item
        # remains durable and can be reconciled without repeating the decision.
        try:
            state=graph.invoke(Command(resume={'approved':approved,'approver_id':actor}),
                               config=config(tenant,run_id))
        except Exception:
            return {'run_id':run_id,'decision':status,'graph':'RECONCILIATION_REQUIRED',
                    'outbox_queued':approved}
    return {'run_id':run_id,'decision':status,'graph':'RESUMED',
            'outbox_queued':approved,'result':state.get('result')}

def inspect(tenant: str, run_id: str):
    UUID(run_id)
    with graph_context() as graph:
        snap=existing(graph,tenant,run_id)
    with connect() as db:
        db.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
        approval=db.execute('SELECT status FROM v11_approvals WHERE tenant_id=%s AND run_id=%s',
                            (tenant,run_id)).fetchone()
        outbox=db.execute('SELECT status,attempts,action_key FROM v11_outbox WHERE tenant_id=%s AND run_id=%s',
                          (tenant,run_id)).fetchall()
        events=history(db,tenant,run_id)
    return {'run_id':run_id,'approval':approval[0] if approval else None,
            'awaiting_graph_approval':bool(snap.interrupts),
            'outbox':[{'status':r[0],'attempts':r[1],'action_key':r[2]} for r in outbox],
            'audit':events}
