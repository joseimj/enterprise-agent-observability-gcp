"""Explicit opt-in read-only Salesforce integration; no write endpoints."""
import os
from fastapi import APIRouter, HTTPException, Depends
from app.v1_identity import Principal, require_principal, require_role
from app.salesforce_azure import SalesforceConfig, SalesforceReadClient
router=APIRouter(prefix='/integrations/salesforce', tags=['Salesforce Azure adapter'])

@router.get('/accounts/{account_id}')
async def account(account_id: str, principal: Principal = Depends(require_principal)):
    require_role(principal, 'Agent.Operator')
    # Intentionally disabled unless an identity-aware gateway is deployed.
    if os.getenv('ENABLE_SALESFORCE_READ_API') != 'true':
        raise HTTPException(404, 'Salesforce adapter disabled')
    try:
        return await SalesforceReadClient(SalesforceConfig.from_env()).get_account(account_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
