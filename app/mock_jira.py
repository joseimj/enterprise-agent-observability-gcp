import asyncio
from fastapi import FastAPI, HTTPException, Query
from app.telemetry import setup
app = FastAPI(title="Jira mock")
tracer = setup(app, "jira-mock")
@app.get("/incidents/{account_id}")
async def incidents(account_id: str, delay_ms: int = Query(0, ge=0, le=15000), fail: bool = False):
    with tracer.start_as_current_span("jira.incidents.lookup"):
        await asyncio.sleep(delay_ms / 1000)
        if fail:
            raise HTTPException(503, "Simulated Jira outage")
        return {"account_id": account_id, "incidents": [
            {"key": "OPS-101", "severity": "critical", "status": "open", "sla_breached": True},
            {"key": "OPS-102", "severity": "medium", "status": "in_progress", "sla_breached": False}]}
