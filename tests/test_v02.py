from app.knowledge import retrieve
from app.inference import explain

def test_high_risk_retrieval():
    docs=retrieve({"level":"high"})
    assert docs and "POL-SLA-01" in [d["id"] for d in docs]

def test_offline_inference(monkeypatch):
    monkeypatch.setenv("INFERENCE_PROVIDER","offline")
    result=explain({"summary":"1 incident", "recommendation":"Escalate"}, [{"id":"POL-SLA-01","text":"policy"}])
    assert result["provider"]=="offline"
    assert result["citations"]==["POL-SLA-01"]
