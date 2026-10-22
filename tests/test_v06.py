import pytest
from pydantic import ValidationError
from app.action_policy import ActionPolicy

def test_servicenow_contract():
    result=ActionPolicy.validate('servicenow.create_incident',{'account_id':'ACME','summary':'Payment service unavailable','priority':'2'})
    assert result['priority']=='2'

def test_reject_unapproved_tool():
    with pytest.raises(ValueError): ActionPolicy.validate('servicenow.delete_all',{})

def test_reject_extra_fields():
    with pytest.raises(ValidationError): ActionPolicy.validate('servicenow.create_incident',{'account_id':'ACME','summary':'Payment service unavailable','admin':True})

def test_jira_legacy_contract():
    assert ActionPolicy.validate('jira.create_followup',{'account_id':'ACME','summary':'Follow up'})['account_id']=='ACME'
