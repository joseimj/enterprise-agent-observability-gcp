"""Read-only governed gateway for the demo agent; writes require separate approval API."""
import os
import httpx
from opentelemetry import trace
tracer = trace.get_tracer("enterprise-tool-gateway")
ALLOWLIST = {"salesforce.account.read", "jira.incidents.read", "servicenow.itsm.read"}
BASE_URLS = {"salesforce.account.read": ("SALESFORCE_URL", "http://salesforce:8001", "accounts"),
             "jira.incidents.read": ("JIRA_URL", "http://jira:8002", "incidents"),
             "servicenow.itsm.read": ("SERVICENOW_URL", "http://servicenow:8003", "itsm")}
async def read_tool(tool_name: str, account_id: str, scenario: str = "normal") -> dict:
    if tool_name not in ALLOWLIST:
        raise PermissionError("Tool is not on the read-only allowlist")
    if not account_id or len(account_id) > 32 or not all(c.isalnum() or c in '_-' for c in account_id):
        raise ValueError("Invalid account reference")
    env, default, resource = BASE_URLS[tool_name]
    params = {}
    if tool_name == "jira.incidents.read" and scenario == "jira_failure": params["fail"] = "true"
    if tool_name == "salesforce.account.read" and scenario == "slow_salesforce": params["delay_ms"] = 5000
    if tool_name == "servicenow.itsm.read" and scenario == "servicenow_failure": params["fail"] = "true"
    if tool_name == "servicenow.itsm.read" and scenario == "slow_servicenow": params["delay_ms"] = 5000
    with tracer.start_as_current_span("tool." + tool_name) as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.operation", "read")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{os.getenv(env, default)}/{resource}/{account_id}", params=params)
            response.raise_for_status()
            return response.json()
