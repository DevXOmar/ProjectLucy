import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Tests never reset or write the developer's runtime database.
TEST_DIR = tempfile.TemporaryDirectory(prefix='lucy-tests-')
os.environ['DATABASE_URL'] = os.getenv('LUCY_TEST_DATABASE_URL', f'sqlite:///{Path(TEST_DIR.name) / "test.db"}')
os.environ['LUCY_DEMO_AUTH'] = 'true'
os.environ['LUCY_ALLOW_RESET'] = 'true'
os.environ['LUCY_RESET_TOKEN'] = 'test-reset-token'
os.environ['APP_ENV'] = 'test'
os.environ.pop('VERCEL', None)
from backend.app import app

@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post('/reset-demo', headers={'X-Reset-Token': 'test-reset-token'}).status_code == 200
        yield c
