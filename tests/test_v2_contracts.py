"""Offline contract tests; database integration tests require a live PostgreSQL server."""
import ast
from pathlib import Path
from uuid import uuid4
import pytest
from app.v11_governance import action_key

def test_deterministic_action_key():
    run=str(uuid4())
    assert action_key(run,'servicenow.incident.create') == action_key(run,'servicenow.incident.create')

def test_reject_unlisted_tool():
    with pytest.raises(ValueError):action_key(str(uuid4()),'salesforce.account.delete')

def test_worker_fencing_query():
    source=Path('app/v2_worker.py').read_text()
    assert 'AND attempts=%s' in source and 'leased_until > now()' in source

def test_decision_transaction_has_outbox_and_audit():
    source=Path('app/v2_service.py').read_text()
    ast.parse(source)
    assert 'decide_once(db,' in source and "record(db,tenant,run_id,'V2_DECISION_COMMITTED'" in source

def test_v2_endpoints_are_authenticated():
    source=Path('app/v2_api.py').read_text()
    assert source.count('Depends(require_principal)')==3

def test_external_write_is_mock_only():
    source=Path('app/v2_worker.py').read_text()
    assert 'requests.post(' not in source and 'httpx.post(' not in source
