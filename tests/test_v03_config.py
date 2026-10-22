from pathlib import Path

def test_dual_export_and_local_export():
    root = Path(__file__).resolve().parents[1]
    local = (root/'observability/collector.yaml').read_text()
    dual = (root/'observability/collector-dual.yaml').read_text()
    assert 'otlp/tempo' in local and 'otlphttp/loki' in local
    assert 'otlphttp/dynatrace' not in local
    assert 'otlphttp/dynatrace' in dual
    assert 'DT_API_TOKEN' in dual and 'DT_OTLP_ENDPOINT' in dual

def test_fault_scenarios_and_alert():
    root = Path(__file__).resolve().parents[1]
    assert 'jira_failure' in (root/'scripts/fault_injection.py').read_text()
    assert 'risk_requests_total' in (root/'observability/grafana/provisioning/alerting/rules.yaml').read_text()
