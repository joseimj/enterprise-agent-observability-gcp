import asyncio
from fastapi import FastAPI, HTTPException, Query
from app.telemetry import setup
app = FastAPI(title="Salesforce mock")
tracer = setup(app, "salesforce-mock")
@app.get("/accounts/{account_id}")
async def account(account_id: str, delay_ms: int = Query(0, ge=0, le=15000), fail: bool = False):
    with tracer.start_as_current_span("salesforce.account.lookup"):
        await asyncio.sleep(delay_ms / 1000)
        if fail:
            raise HTTPException(503, "Simulated Salesforce outage")
        if account_id != "ACME":
            raise HTTPException(404, "Account not found")
        return {"id": account_id, "name": "ACME Manufacturing", "tier": "strategic", "annual_revenue_usd": 1200000, "health": "watch"}
