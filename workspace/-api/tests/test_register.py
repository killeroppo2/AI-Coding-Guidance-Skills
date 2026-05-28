import os
import tempfile

import pytest
from app.database import Base, get_db
from app.models import User
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REGISTER_URL = "/api/register"
LOGIN_URL = "/api/login"

# Use a temp file so the DB is shared across all connections in this module
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TEST_DB_PATH = _TMP.name
_TMP.close()
TEST_ENGINE = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
TEST_SESSION_LOCAL = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def override_get_db():
    db = TEST_SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(autouse=True, scope="session")
def cleanup():
    yield
    os.unlink(TEST_DB_PATH)


class TestRegister:
    def test_register_success(self):
        response = client.post(
            REGISTER_URL,
            json={"username": "newuser", "email": "new@test.com", "password": "secret123"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@test.com"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_username(self):
        client.post(
            REGISTER_URL,
            json={"username": "dupuser", "email": "dup1@test.com", "password": "secret123"},
        )
        response = client.post(
            REGISTER_URL,
            json={"username": "dupuser", "email": "dup2@test.com", "password": "secret456"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_register_duplicate_email(self):
        client.post(
            REGISTER_URL,
            json={"username": "user_a", "email": "dup@test.com", "password": "secret123"},
        )
        response = client.post(
            REGISTER_URL,
            json={"username": "user_b", "email": "dup@test.com", "password": "secret456"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_register_invalid_email(self):
        response = client.post(
            REGISTER_URL,
            json={"username": "bad_email_user", "email": "not-an-email", "password": "secret123"},
        )
        assert response.status_code == 422

    def test_register_missing_fields(self):
        response = client.post(
            REGISTER_URL,
            json={"username": "no_password"},
        )
        assert response.status_code == 422

    def test_register_empty_password(self):
        response = client.post(
            REGISTER_URL,
            json={"username": "empty_pw", "email": "empty_pw@test.com", "password": ""},
        )
        assert response.status_code == 201

    def test_register_password_not_stored_in_plaintext(self):
        client.post(
            REGISTER_URL,
            json={"username": "secure_user", "email": "secure@test.com", "password": "my_password"},
        )
        db = TEST_SESSION_LOCAL()
        user = db.query(User).filter(User.username == "secure_user").first()
        assert user is not None
        assert user.hashed_password != "my_password"
        assert user.hashed_password.startswith("$2b$")
        db.close()


class TestLogin:
    LOGIN_USER = {"username": "login_test", "email": "login@test.com", "password": "correct_pw"}

    @pytest.fixture(autouse=True)
    def _register_user(self):
        client.post(REGISTER_URL, json=self.LOGIN_USER)
        yield

    def test_login_success(self):
        response = client.post(
            LOGIN_URL,
            json={"username": "login_test", "password": "correct_pw"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self):
        response = client.post(
            LOGIN_URL,
            json={"username": "login_test", "password": "wrong_password"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self):
        response = client.post(
            LOGIN_URL,
            json={"username": "ghost_user", "password": "any_password"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_returns_jwt(self):
        response = client.post(
            LOGIN_URL,
            json={"username": "login_test", "password": "correct_pw"},
        )
        token = response.json()["access_token"]
        # JWT has 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

    def test_login_token_contains_username(self):
        from app.config import settings
        from jose import jwt

        response = client.post(
            LOGIN_URL,
            json={"username": "login_test", "password": "correct_pw"},
        )
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "login_test"

    def test_login_empty_password(self):
        response = client.post(
            LOGIN_URL,
            json={"username": "login_test", "password": ""},
        )
        assert response.status_code == 401

    def test_login_missing_fields(self):
        response = client.post(
            LOGIN_URL,
            json={"username": "login_test"},
        )
        assert response.status_code == 422
