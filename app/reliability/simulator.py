"""LOCAL-ONLY ServiceNow fault simulator with tenant-aware idempotency.

This is not an authentication boundary and is not an implementation of the
ServiceNow platform. Use only on an isolated Docker laboratory network.
"""
from __future__ import annotations

import os
from uuid import uuid4
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

class Incident(BaseModel):
    tenant_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    account_id: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=8, max_length=200)


def _ensure_table(db):
    # A v2 table avoids silently interpreting old tenant-less lab data as scoped.
    db.execute('''CREATE TABLE IF NOT EXISTS sim_incidents_v2 (
        tenant_id text NOT NULL,
        idempotency_key text NOT NULL,
        number text NOT NULL,
        account_id text NOT NULL,
        summary text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, idempotency_key),
        UNIQUE (number)
    )''')


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Bootstrap ONCE before readiness, avoiding concurrent request-time DDL.
    with psycopg.connect(os.environ['SIM_DATABASE_URL']) as db:
        _ensure_table(db)
    yield


app = FastAPI(title='Tenant-aware ServiceNow fault simulator', lifespan=lifespan)


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'servicenow-simulator'}


def _valid_key(key: str):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{8,128}', key):
        raise HTTPException(400, 'Invalid idempotency key')


@app.post('/sim/incidents')
def create_incident(body: Incident,
                    idempotency_key: str = Header(..., alias='Idempotency-Key'),
                    fault_mode: str = Header('none', alias='X-Fault-Mode')):
    _valid_key(idempotency_key)
    if fault_mode not in ('none', 'timeout_after_commit', 'before_commit'):
        raise HTTPException(400, 'Unknown fault mode')
    if fault_mode == 'before_commit':
        raise HTTPException(503, 'Simulated precommit failure')
    with psycopg.connect(os.environ['SIM_DATABASE_URL']) as db:
        row = db.execute('''INSERT INTO sim_incidents_v2
            (tenant_id, idempotency_key, number, account_id, summary)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (tenant_id,idempotency_key) DO NOTHING
            RETURNING number''',
            (body.tenant_id, idempotency_key, 'SIM-' + uuid4().hex[:20],
             body.account_id, body.summary)).fetchone()
        if row is None:
            existing = db.execute('''SELECT number, account_id, summary
                FROM sim_incidents_v2 WHERE tenant_id=%s AND idempotency_key=%s''',
                (body.tenant_id, idempotency_key)).fetchone()
            if existing is None:
                raise HTTPException(503, 'Indeterminate concurrent record')
            if (existing[1], existing[2]) != (body.account_id, body.summary):
                raise HTTPException(409, 'Idempotency key reused with different payload')
            number = existing[0]
        else:
            number = row[0]
    if fault_mode == 'timeout_after_commit':
        raise HTTPException(504, 'Simulated acknowledgement lost AFTER commit')
    return {'number': number, 'idempotency_key': idempotency_key,
            'tenant_id': body.tenant_id, 'simulated': True}


@app.get('/sim/incidents/by-key/{key}')
def find_incident(key: str, tenant_id: str = Query(..., pattern=r'^[A-Za-z0-9_-]{1,64}$')):
    _valid_key(key)
    with psycopg.connect(os.environ['SIM_DATABASE_URL']) as db:
        row = db.execute('''SELECT number FROM sim_incidents_v2
            WHERE tenant_id=%s AND idempotency_key=%s''',
            (tenant_id, key)).fetchone()
    if row is None:
        raise HTTPException(404, 'Not found')
    return {'number': row[0], 'idempotency_key': key,
            'tenant_id': tenant_id, 'simulated': True}
