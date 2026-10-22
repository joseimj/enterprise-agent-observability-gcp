"""IAP-signed identity + explicit subject-to-tenant grant resolution.

Never trust X-Goog-Authenticated-User-Email, custom tenant headers or model output.
The JSON mapping is a demonstrative authorization registry. Production systems
should use a maintained identity/entitlement service with audited change control.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet
from fastapi import Header, HTTPException

IAP_CERTS = 'https://www.gstatic.com/iap/verify/public_key'
IAP_ISSUER = 'https://cloud.google.com/iap'
ROLES = frozenset({'Agent.Operator','Agent.Approver','Agent.Auditor'})

@dataclass(frozen=True)
class Principal:
    subject: str
    email: str
    tenant: str
    roles: FrozenSet[str]


def verify_iap(token: str, audience: str) -> dict:
    if not token or not audience:
        raise ValueError('IAP signed token and exact audience required')
    # Import lazily so local policy tests do not require cloud dependencies.
    import jwt
    header = jwt.get_unverified_header(token)
    if header.get('alg') != 'ES256' or not header.get('kid'):
        raise ValueError('IAP header algorithm or key missing')
    from google.auth.transport import requests
    from google.oauth2 import id_token
    decoded = id_token.verify_token(token, requests.Request(), audience=audience,
                                   certs_url=IAP_CERTS)
    if decoded.get('iss') != IAP_ISSUER:
        raise ValueError('Unexpected IAP issuer')
    if not decoded.get('sub') or not decoded.get('email'):
        raise ValueError('Missing signed IAP identity')
    # The google-auth verifier checks signature, expiration and audience.
    return decoded


def resolve_principal(claims: dict, registry: dict) -> Principal:
    """Registry keys are immutable signed Google-subject IDs, never user headers."""
    subject = claims.get('sub')
    if not isinstance(subject,str) or not subject:
        raise PermissionError('Signed subject required')
    grant = registry.get(subject)
    if not isinstance(grant,dict):
        raise PermissionError('Subject has no explicit tenant grant')
    tenant = grant.get('tenant')
    roles = grant.get('roles')
    if not isinstance(tenant,str) or not 1 <= len(tenant) <= 64 or not all(c.isalnum() or c in '_-' for c in tenant):
        raise PermissionError('Invalid tenant grant')
    if not isinstance(roles,list) or any(r not in ROLES for r in roles):
        raise PermissionError('Invalid role grant')
    if not roles:
        raise PermissionError('No granted permissions')
    email = claims.get('email')
    return Principal(subject=subject, email=email if isinstance(email,str) else '',
                     tenant=tenant, roles=frozenset(roles))


def require_role(p: Principal, role: str):
    if role not in p.roles:
        raise HTTPException(403,'Insufficient role')


def authorize_approval(requester_subject: str, approver_subject: str):
    if not requester_subject or requester_subject == approver_subject:
        raise HTTPException(403,'Requester cannot approve their own action')


def get_principal(x_goog_iap_jwt_assertion: str | None = Header(default=None)) -> Principal:
    audience = os.getenv('GCP_IAP_AUDIENCE','')
    if not audience:
        raise HTTPException(503,'IAP audience not configured')
    if not x_goog_iap_jwt_assertion:
        raise HTTPException(401,'IAP signed assertion required')
    try:
        claims = verify_iap(x_goog_iap_jwt_assertion,audience)
    except Exception as exc:
        raise HTTPException(401,'Invalid IAP token') from exc
    grant_path = os.getenv('GCP_AUTHZ_REGISTRY_PATH','')
    if not grant_path:
        raise HTTPException(503,'Authorization registry not configured')
    try:
        registry = json.loads(Path(grant_path).read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc:
        raise HTTPException(503,'Authorization registry unavailable') from exc
    try:
        return resolve_principal(claims,registry)
    except PermissionError as exc:
        raise HTTPException(403,str(exc)) from exc
