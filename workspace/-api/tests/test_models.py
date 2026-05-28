from datetime import datetime, timezone

from app.database import Base, engine, init_db
from app.models import User


def test_user_model_columns():
    """Verify User model has expected columns and types."""
    init_db()
    columns = {c.name: c.type.python_type for c in User.__table__.columns}
    assert columns["id"] == int
    assert columns["username"] == str
    assert columns["email"] == str
    assert columns["hashed_password"] == str
    assert columns["created_at"] == datetime


def test_user_model_constraints():
    """Verify User model constraints."""
    assert User.__tablename__ == "users"
    assert User.username.property.columns[0].unique is True
    assert User.email.property.columns[0].unique is True


def test_database_table_creation():
    """Verify database creates tables correctly."""
    from sqlalchemy import inspect
    init_db()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "users" in tables
    assert len(tables) == 1


def test_user_created_at_default():
    """Verify created_at column has a default value configured."""
    from sqlalchemy import inspect
    col = inspect(User).c.created_at
    assert col.default is not None


def test_get_db_yields_session():
    """Verify get_db yields a working database session."""
    from app.database import get_db
    gen = get_db()
    db = next(gen)
    assert db is not None
    from sqlalchemy.orm import Session
    assert isinstance(db, Session)
    try:
        next(gen)
    except StopIteration:
        pass
