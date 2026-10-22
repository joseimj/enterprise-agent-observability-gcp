import pytest
from pydantic import ValidationError
from app.integration_contracts import SalesforceAccount, JiraIncidentResponse, ConnectorAudit

def test_salesforce_response():
    a = SalesforceAccount.model_validate({'account_id':'001000000000001AAA','name':'ACME'})
    assert a.name == 'ACME'

def test_salesforce_rejects_injection():
    with pytest.raises(ValidationError):
        SalesforceAccount.model_validate({'account_id':"' OR 1=1",'name':'ACME'})

def test_jira_response():
    j = JiraIncidentResponse.model_validate({'account_key':'ACME','incidents':[{'key':'OPS-42','summary':'Outage','status':'Open'}]})
    assert j.incidents[0].key == 'OPS-42'

def test_jira_rejects_invalid_key():
    with pytest.raises(ValidationError):
        JiraIncidentResponse.model_validate({'account_key':'ACME','incidents':[{'key':'invalid','summary':'Outage','status':'Open'}]})

def test_audit_rejects_unknown_tool():
    with pytest.raises(ValidationError):
        ConnectorAudit.model_validate({'run_id':'r1','tenant_id':'t1','tool_name':'admin.delete_all','outcome':'SUCCESS'})
