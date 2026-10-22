"""Offline tests exercise exact access grants and safe non-authoritative adapters.
Requires pytest+fastapi already installed; no GCP credentials or network needed.
"""
import json
import pytest
from fastapi import HTTPException
from gcp_edition.security import resolve_principal, require_role, authorize_approval
from gcp_edition.gemini import build_safe_context, explain_run
from gcp_edition.pubsub import signal_action

GRANTS={'alice-sub':{'tenant':'acme','roles':['Agent.Operator','Agent.Auditor']},
        'bob-sub':{'tenant':'acme','roles':['Agent.Approver']},
        'carol-sub':{'tenant':'another','roles':['Agent.Approver']}}

def test_exact_signed_subject_lookup():
    p=resolve_principal({'sub':'alice-sub','email':'a@test.invalid'},GRANTS)
    assert p.tenant=='acme'
    assert p.roles==frozenset({'Agent.Operator','Agent.Auditor'})

def test_subject_missing_denied():
    with pytest.raises(PermissionError):
        resolve_principal({'sub':'unknown','email':'a@test.invalid'},GRANTS)

def test_subject_not_taken_from_email():
    with pytest.raises(PermissionError):
        resolve_principal({'sub':'mallory','email':'alice-sub'},GRANTS)

def test_cannot_inject_tenant_from_claims():
    p=resolve_principal({'sub':'bob-sub','tenant':'another','roles':['Agent.Operator']},GRANTS)
    assert p.tenant=='acme'
    assert p.roles==frozenset({'Agent.Approver'})

def test_roles_validated():
    with pytest.raises(PermissionError):
        resolve_principal({'sub':'x'},{'x':{'tenant':'acme','roles':['*']}})
    with pytest.raises(PermissionError):
        resolve_principal({'sub':'x'},{'x':{'tenant':'../admin','roles':['Agent.Operator']}})

def test_role_enforcement():
    p=resolve_principal({'sub':'bob-sub'},GRANTS)
    with pytest.raises(HTTPException) as exc:
        require_role(p,'Agent.Operator')
    assert exc.value.status_code==403

def test_separation_of_duties():
    with pytest.raises(HTTPException) as exc:
        authorize_approval('alice-sub','alice-sub')
    assert exc.value.status_code==403
    authorize_approval('alice-sub','bob-sub')

def test_sanitization_excludes_audit_business_data(monkeypatch):
    run={'approval':'PENDING','outbox':[{'status':'PENDING','payload':'SECRET-PII'}],
         'audit':[{'actor_id':'user-sensitive','payload':{'token':'secret'}}],
         'awaiting_graph_approval':True}
    context=build_safe_context(run)
    assert 'SECRET-PII' not in context and 'user-sensitive' not in context and 'secret' not in context
    monkeypatch.setenv('GCP_INFERENCE_PROVIDER','offline')
    result=explain_run(run)
    assert not result['model_used']

def test_pubsub_optional_and_non_authoritative(monkeypatch):
    monkeypatch.delenv('GCP_PUBSUB_TOPIC',raising=False)
    assert signal_action('acme','00000000-0000-0000-0000-000000000001') is False
