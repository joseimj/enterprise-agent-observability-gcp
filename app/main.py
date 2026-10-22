import os
import time
import uuid
import logging
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from app.telemetry import setup
from app.agent import graph
from app.v1_identity import Principal, require_principal, require_role

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("risk-api")
app = FastAPI(title="Enterprise Agent Observability", version="1.0")
tracer = setup(app, "risk-api")
REQUESTS = Counter("risk_requests_total", "Risk workflow requests", ["outcome", "scenario"])
DURATION = Histogram("risk_request_duration_seconds", "Risk workflow duration")

class AnalyzeRequest(BaseModel):
    account_id: str = Field(default="ACME", pattern=r"^[A-Za-z0-9_-]{1,32}$")
    scenario: str = Field(default="normal", pattern=r"^(normal|slow_salesforce|jira_failure|slow_jira|bedrock_failure|servicenow_failure|slow_servicenow)$")

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/metrics")
async def metrics(principal: Principal = Depends(require_principal)):
    require_role(principal, 'Agent.Auditor')
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/risk/analyze")
async def analyze(payload: AnalyzeRequest, request: Request,
                  principal: Principal = Depends(require_principal)):
    require_role(principal, 'Agent.Operator')
    start = time.monotonic()
    request_id = str(uuid.uuid4())
    with tracer.start_as_current_span("risk.analyze") as span:
        span.set_attribute("workflow.name", "customer-risk")
        span.set_attribute("workflow.scenario", payload.scenario)
        span.set_attribute("workflow.request_id", request_id)
        try:
            result = await graph.ainvoke({"account_id": payload.account_id, "scenario": payload.scenario})
            REQUESTS.labels("success", payload.scenario).inc()
            logger.info("workflow_success request_id=%s trace_id=%032x", request_id, span.get_span_context().trace_id)
            return {"request_id": request_id, "trace_id": f"{span.get_span_context().trace_id:032x}", "account": result["customer"], "risk": result["risk"], "explanation": result["explanation"]}
        except Exception as exc:
            REQUESTS.labels("error", payload.scenario).inc()
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            logger.exception("workflow_failure request_id=%s", request_id)
            return JSONResponse(status_code=502, content={"request_id": request_id, "error": "Upstream workflow failed", "trace_id": f"{span.get_span_context().trace_id:032x}"})
        finally:
            DURATION.observe(time.monotonic() - start)

# Header-based identities in historic labs are forgeable.  Remove routes from
# OpenAPI and routing completely unless the operator explicitly opts in to a
# local-only, insecure development deployment. Never set these in Azure.
INSECURE_LOCAL_LABS = (os.getenv('DEPLOYMENT_ENV', '').lower() == 'local' and
                       os.getenv('ENABLE_INSECURE_DEMO_ROUTES', '').lower() == 'true')
if INSECURE_LOCAL_LABS:
    from app.governance_api import router as governance_router
    from app.durable_api import router as durable_router
    from app.v1_api import router as v1_router
    app.include_router(governance_router)
    app.include_router(durable_router)
    app.include_router(v1_router)

from app.salesforce_router import router as salesforce_router
app.include_router(salesforce_router)

from app.v2_api import router as v2_router
app.include_router(v2_router)
