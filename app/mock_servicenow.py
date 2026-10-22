"""Deterministic ServiceNow ITSM/CMDB mock with injectable failures."""
import asyncio
from fastapi import FastAPI, HTTPException, Query
from app.telemetry import setup
app = FastAPI(title="ServiceNow ITSM mock")
tracer = setup(app, "servicenow-mock")
@app.get("/itsm/{account_id}")
async def itsm(account_id: str, delay_ms: int = Query(0, ge=0, le=15000), fail: bool = False):
    with tracer.start_as_current_span("servicenow.itsm.lookup") as span:
        span.set_attribute("itsm.account_reference", account_id)
        await asyncio.sleep(delay_ms / 1000)
        if fail:
            raise HTTPException(503, "Simulated ServiceNow outage")
        return {"account_id": account_id, "incidents": [
            {"number":"INC0010042", "severity":"critical", "status":"open", "sla_breached":True,
             "configuration_item":"Payments API", "source":"servicenow"},
            {"number":"INC0010043", "severity":"low", "status":"resolved", "sla_breached":False,
             "configuration_item":"CRM Sync", "source":"servicenow"}]}


from pydantic import BaseModel, Field
class MockIncident(BaseModel):
    account_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    summary: str = Field(min_length=8,max_length=200)
    priority: str = Field(pattern=r"^[1-4]$")

@app.post('/mock/incidents',status_code=201)
async def create_mock_incident(body: MockIncident):
    # Only for isolated demo testing. Never connect this endpoint to a real ServiceNow tenant.
    with tracer.start_as_current_span('servicenow.mock.incident.create'):
        return {'number':'MOCK-INC-0001','simulated':True,'account_id':body.account_id,'priority':body.priority}
