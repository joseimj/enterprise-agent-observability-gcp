"""Job entrypoint; one tenant comes from trusted job configuration, never Pub/Sub."""
import asyncio
import json
import os
from app.reliability.governed_worker import dispatch_once

async def main():
    tenant=os.environ['WORKER_BUSINESS_TENANT_ID']
    # Refuse live provider writes. Extension can only dispatch into a simulator.
    if os.getenv('SERVICENOW_PROVIDER_MODE','simulator')!='simulator':
        raise PermissionError('GCP v3 worker is simulator-only')
    max_items=int(os.getenv('GCP_WORKER_MAX_ITEMS','25'))
    if not 1 <= max_items <= 100:
        raise ValueError('GCP_WORKER_MAX_ITEMS must be 1..100')
    counts={}
    for _ in range(max_items):
        result=await dispatch_once(tenant)
        status=result['status'];counts[status]=counts.get(status,0)+1
        if status=='EMPTY':break
    print(json.dumps({'tenant':tenant,'results':counts}))

if __name__=='__main__':
    asyncio.run(main())
