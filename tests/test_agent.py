from app.agent import assess

def test_high_risk():
    state = {"incidents": [{"key": "OPS-101", "severity": "critical", "status": "open", "sla_breached": True}]}
    risk = assess(state)["risk"]
    assert risk["level"] == "high"
    assert risk["score"] == 90
    assert risk["evidence"] == ["OPS-101"]

def test_low_risk():
    assert assess({"incidents": []})["risk"]["level"] == "low"
