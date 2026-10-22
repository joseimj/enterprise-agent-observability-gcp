from fastapi import HTTPException
from app.v1_identity import Principal, require_role, verify_token
from app.v1_workflow import assess, governed_execute
import pytest

def test_assess_proposes_only_allowlisted_action():
    result=assess({'tenant_id':'t','run_id':'r','account_id':'ACME'})
    assert result['action']['tool']=='servicenow.incident.create'
    assert result['risk_score']==85

def test_rejection_does_not_write():
    result=governed_execute({'decision':{'approved':False},'action':{'tool':'servicenow.incident.create'}})
    assert result['result']['external_write'] is False

def test_approval_still_simulates():
    result=governed_execute({'decision':{'approved':True},'action':{'tool':'servicenow.incident.create'}})
    assert result['result']['status']=='SIMULATED'

def test_non_allowlisted_tool_rejected():
    with pytest.raises(ValueError):
        governed_execute({'decision':{'approved':True},'action':{'tool':'salesforce.account.delete'}})

def test_missing_role():
    with pytest.raises(HTTPException) as e:
        require_role(Principal('u','t',frozenset()),'Agent.Approver')
    assert e.value.status_code==403

def test_unconfigured_identity_fails_closed(monkeypatch):
    monkeypatch.delenv('ENTRA_TENANT_ID',raising=False)
    monkeypatch.delenv('ENTRA_API_AUDIENCE',raising=False)
    with pytest.raises(HTTPException) as e: verify_token('x.y.z')
    assert e.value.status_code==503
