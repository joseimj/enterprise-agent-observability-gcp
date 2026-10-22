import os
import uuid
import pytest
import psycopg

@pytest.fixture(autouse=True)
def require_db():
    if os.getenv('RUN_DATABASE_INTEGRATION')!='1':
        pytest.skip('Run with Docker Compose integration profile and real PostgreSQL')

@pytest.fixture
def tenant():
    return 'test-'+uuid.uuid4().hex[:18]

@pytest.fixture
def db_url():return os.environ['AUDIT_DATABASE_URL']

@pytest.fixture
def run_id():return str(uuid.uuid4())
