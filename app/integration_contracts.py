"""Versioned, provider-neutral read contracts for Salesforce Apex and Jira Groovy.

These adapters describe normalization only. No live connector or authentication is
implicitly enabled. Write actions remain behind the governed action API.
"""
from typing import Literal
from pydantic import BaseModel, Field

class SalesforceAccount(BaseModel):
    account_id: str = Field(pattern=r'^[A-Za-z0-9]{15,18}$')
    name: str
    industry: str | None = None
    type: str | None = None

class JiraIncident(BaseModel):
    key: str = Field(pattern=r'^[A-Z][A-Z0-9_]*-[0-9]+$')
    summary: str
    status: str
    priority: str | None = None

class JiraIncidentResponse(BaseModel):
    account_key: str = Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')
    incidents: list[JiraIncident]

class ConnectorAudit(BaseModel):
    run_id: str
    tenant_id: str
    tool_name: Literal['salesforce.account.read','jira.incidents.read']
    outcome: Literal['SUCCESS','ERROR','DENIED']
    trace_id: str | None = None
    external_request_id: str | None = None
