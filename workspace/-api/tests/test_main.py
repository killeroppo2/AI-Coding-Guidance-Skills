from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Login API is running"


def test_app_imports():
    from app.config import settings
    assert settings.PROJECT_NAME == "Login API"
    assert settings.ALGORITHM == "HS256"


def test_app_startup_creates_tables():
    """Verify app startup (lifespan) creates database tables."""
    from app.database import engine as eng
    from app.database import init_db
    from sqlalchemy import inspect
    init_db()
    inspector = inspect(eng)
    assert "users" in inspector.get_table_names()


def test_lifespan_runs_init_db():
    """Verify the lifespan async context manager runs init_db without error."""
    import asyncio

    from main import lifespan
    async def run_lifespan():
        async with lifespan(app):
            pass
    asyncio.run(run_lifespan())
    from app.database import engine as eng
    from sqlalchemy import inspect
    inspector = inspect(eng)
    assert "users" in inspector.get_table_names()
