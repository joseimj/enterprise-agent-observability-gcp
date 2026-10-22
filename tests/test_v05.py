from pathlib import Path
import pytest
from app.enterprise_tools import read_tool, ALLOWLIST

def test_three_read_only_tools_registered():
    assert ALLOWLIST == {"salesforce.account.read", "jira.incidents.read", "servicenow.itsm.read"}

@pytest.mark.asyncio
async def test_unknown_tool_rejected():
    with pytest.raises(PermissionError):
        await read_tool("servicenow.incident.write", "ACME")

@pytest.mark.asyncio
async def test_invalid_account_rejected():
    with pytest.raises(ValueError):
        await read_tool("servicenow.itsm.read", "../../admin")

def test_graph_has_itsm_node():
    source = Path('app/agent.py').read_text()
    assert 'builder.add_node("itsm", itsm)' in source
    assert 'builder.add_edge("itsm", "assess")' in source

def test_service_now_scripts_present():
    assert Path('integrations/servicenow/script_includes/AgentRiskService.js').exists()
    assert Path('integrations/servicenow/scripted_rest/AgentRiskResource.js').exists()
