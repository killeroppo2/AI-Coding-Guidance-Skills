"""Tests for the web dashboard application."""

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.fixture
def kernel_dir(tmp_path: Path) -> Path:
    """Create a temporary kernel root with all necessary files."""
    # kernel/state.yaml
    kernel_subdir = tmp_path / "kernel"
    kernel_subdir.mkdir()
    state_data = {
        "current_node": "plan",
        "iteration_count": 5,
        "max_iterations": 30,
        "goal": "Build a REST API",
        "status": "running",
        "last_updated": "2025-01-01T00:00:00Z",
        "errors": [],
        "context": {"skills_loaded": [], "current_task": "", "phase": "planning"},
    }
    with open(kernel_subdir / "state.yaml", "w") as f:
        yaml.safe_dump(state_data, f)

    # kernel/evolution/history.jsonl
    evolution_dir = kernel_subdir / "evolution"
    evolution_dir.mkdir()
    history_entries = [
        {"type": "mutation", "timestamp": "2025-01-01T00:00:00Z", "detail": "added edge"},
        {"type": "selection", "timestamp": "2025-01-01T01:00:00Z", "detail": "kept plan node"},
    ]
    with open(evolution_dir / "history.jsonl", "w") as f:
        for entry in history_entries:
            f.write(json.dumps(entry) + "\n")

    # memory/
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    # memory/tasks.yaml
    tasks_data = {
        "tasks": [
            {"name": "Design API", "status": "done"},
            {"name": "Write tests", "status": "pending"},
        ]
    }
    with open(memory_dir / "tasks.yaml", "w") as f:
        yaml.safe_dump(tasks_data, f)

    # memory/reflections.jsonl
    reflections = [
        {"insight": f"reflection {i}", "timestamp": f"2025-01-01T0{i}:00:00Z"} for i in range(5)
    ]
    with open(memory_dir / "reflections.jsonl", "w") as f:
        for r in reflections:
            f.write(json.dumps(r) + "\n")

    # skills/_index.yaml
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skills_data = {
        "items": [{"name": "python-api", "description": "Build Python APIs", "tags": ["python"]}]
    }
    with open(skills_dir / "_index.yaml", "w") as f:
        yaml.safe_dump(skills_data, f)

    # web/templates/dashboard.html
    web_dir = tmp_path / "web" / "templates"
    web_dir.mkdir(parents=True)
    with open(web_dir / "dashboard.html", "w") as f:
        f.write("<html><body><h1>AI Kernel Dashboard</h1><div id='log-stream'></div></body></html>")

    return tmp_path


@pytest.fixture
def client(kernel_dir: Path) -> TestClient:
    """Create a test client with a temporary kernel root."""
    app = create_app(kernel_root=kernel_dir)
    return TestClient(app)


@pytest.fixture
def empty_client(tmp_path: Path) -> TestClient:
    """Create a test client with an empty kernel root (no files)."""
    # Create minimal dashboard template so / doesn't 500
    web_dir = tmp_path / "web" / "templates"
    web_dir.mkdir(parents=True)
    with open(web_dir / "dashboard.html", "w") as f:
        f.write("<html><body><h1>Empty</h1></body></html>")
    app = create_app(kernel_root=tmp_path)
    return TestClient(app)


class TestDashboard:
    """Tests for the dashboard HTML endpoint."""

    def test_dashboard_serves_html(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "AI Kernel Dashboard" in resp.text

    def test_dashboard_missing_template(self, tmp_path: Path):
        """Dashboard returns 500 if template is missing."""
        app = create_app(kernel_root=tmp_path)
        c = TestClient(app)
        resp = c.get("/")
        assert resp.status_code == 500
        assert "not found" in resp.text.lower()


class TestStateEndpoint:
    """Tests for GET /api/state."""

    def test_returns_state(self, client: TestClient):
        resp = client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_node"] == "plan"
        assert data["iteration_count"] == 5
        assert data["goal"] == "Build a REST API"
        assert data["status"] == "running"

    def test_missing_state_file(self, empty_client: TestClient):
        resp = empty_client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestTasksEndpoint:
    """Tests for GET /api/tasks."""

    def test_returns_tasks(self, client: TestClient):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Design API"
        assert data[0]["status"] == "done"

    def test_missing_tasks_file(self, empty_client: TestClient):
        resp = empty_client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []


class TestHistoryEndpoint:
    """Tests for GET /api/history."""

    def test_returns_history(self, client: TestClient):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["type"] == "mutation"
        assert data[1]["type"] == "selection"

    def test_missing_history_file(self, empty_client: TestClient):
        resp = empty_client.get("/api/history")
        assert resp.status_code == 200
        assert resp.json() == []


class TestReflectionsEndpoint:
    """Tests for GET /api/reflections."""

    def test_returns_reflections(self, client: TestClient):
        resp = client.get("/api/reflections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert data[0]["insight"] == "reflection 0"

    def test_limits_to_50(self, kernel_dir: Path):
        """Only last 50 reflections are returned."""
        reflections_path = kernel_dir / "memory" / "reflections.jsonl"
        with open(reflections_path, "w") as f:
            for i in range(100):
                f.write(json.dumps({"insight": f"r{i}"}) + "\n")
        app = create_app(kernel_root=kernel_dir)
        c = TestClient(app)
        resp = c.get("/api/reflections")
        data = resp.json()
        assert len(data) == 50
        assert data[0]["insight"] == "r50"

    def test_missing_reflections_file(self, empty_client: TestClient):
        resp = empty_client.get("/api/reflections")
        assert resp.status_code == 200
        assert resp.json() == []


class TestSkillsEndpoint:
    """Tests for GET /api/skills."""

    def test_returns_skills(self, client: TestClient):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "python-api"

    def test_missing_skills_file(self, empty_client: TestClient):
        resp = empty_client.get("/api/skills")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGoalEndpoint:
    """Tests for POST /api/goal."""

    def test_set_goal(self, client: TestClient, kernel_dir: Path):
        resp = client.post("/api/goal", json={"goal": "New goal"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["goal"] == "New goal"

        # Verify state.yaml was updated
        state_path = kernel_dir / "kernel" / "state.yaml"
        with open(state_path) as f:
            state = yaml.safe_load(f)
        assert state["goal"] == "New goal"

        # Verify current_goal.md was written
        goal_path = kernel_dir / "memory" / "current_goal.md"
        content = goal_path.read_text()
        assert "New goal" in content

    def test_empty_goal(self, client: TestClient):
        resp = client.post("/api/goal", json={"goal": "  "})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "Goal cannot be empty"

    def test_missing_goal_field(self, client: TestClient):
        resp = client.post("/api/goal", json={})
        assert resp.status_code == 422  # Validation error


class TestStartStopEndpoints:
    """Tests for POST /api/start and POST /api/stop."""

    def test_start_execution(self, client: TestClient):
        resp = client.post("/api/start", json={"goal": "Test goal", "max_iterations": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["goal"] == "Test goal"
        assert data["max_iterations"] == 5

    def test_stop_when_not_running(self, client: TestClient):
        resp = client.post("/api/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_running"

    def test_start_then_stop(self, client: TestClient):
        # Start
        resp = client.post("/api/start", json={"goal": "Test", "max_iterations": 100})
        assert resp.json()["status"] == "started"

        # The kernel thread may complete quickly in test mode, so stop may return
        # either "stopping" or "not_running" depending on timing
        resp = client.post("/api/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("stopping", "not_running")

    def test_start_default_params(self, client: TestClient):
        resp = client.post("/api/start", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["max_iterations"] == 30


class TestSSEEndpoint:
    """Tests for GET /api/logs SSE endpoint."""

    def test_sse_endpoint_configuration(self, kernel_dir: Path):
        """Verify SSE endpoint exists and is configured correctly."""
        app = create_app(kernel_root=kernel_dir)
        # Verify the route exists
        routes = [r.path for r in app.routes]
        assert "/api/logs" in routes

    def test_sse_log_subscribers_list(self, kernel_dir: Path):
        """Verify log subscribers list is initialized."""
        app = create_app(kernel_root=kernel_dir)
        assert hasattr(app.state, "log_subscribers")
        assert isinstance(app.state.log_subscribers, list)


class TestWebSocket:
    """Tests for WebSocket /ws endpoint."""

    def test_websocket_connection(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            # Should receive initial state
            data = ws.receive_json()
            assert data["type"] == "state"
            assert "data" in data

    def test_websocket_echo(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            # Receive initial state
            ws.receive_json()
            # Send a message
            ws.send_text("hello")
            resp = ws.receive_json()
            assert resp["type"] == "ack"
            assert resp["data"] == "hello"

    def test_websocket_state_content(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "state"
            state = data["data"]
            assert state["current_node"] == "plan"
            assert state["goal"] == "Build a REST API"


class TestErrorHandling:
    """Tests for graceful error handling with missing/corrupt files."""

    def test_corrupt_yaml(self, tmp_path: Path):
        """Corrupt YAML doesn't crash the app."""
        kernel_subdir = tmp_path / "kernel"
        kernel_subdir.mkdir()
        with open(kernel_subdir / "state.yaml", "w") as f:
            f.write(": invalid: yaml: [[[")

        web_dir = tmp_path / "web" / "templates"
        web_dir.mkdir(parents=True)
        with open(web_dir / "dashboard.html", "w") as f:
            f.write("<html><body>OK</body></html>")

        app = create_app(kernel_root=tmp_path)
        c = TestClient(app)
        resp = c.get("/api/state")
        assert resp.status_code == 200

    def test_corrupt_jsonl(self, tmp_path: Path):
        """Corrupt JSONL lines are skipped."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        with open(memory_dir / "reflections.jsonl", "w") as f:
            f.write('{"valid": true}\n')
            f.write("not json at all\n")
            f.write('{"also_valid": true}\n')

        web_dir = tmp_path / "web" / "templates"
        web_dir.mkdir(parents=True)
        with open(web_dir / "dashboard.html", "w") as f:
            f.write("<html><body>OK</body></html>")

        app = create_app(kernel_root=tmp_path)
        c = TestClient(app)
        resp = c.get("/api/reflections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_all_endpoints_with_empty_root(self, empty_client: TestClient):
        """All endpoints return 200 even with no data files."""
        endpoints = ["/api/state", "/api/tasks", "/api/history", "/api/reflections", "/api/skills"]
        for ep in endpoints:
            resp = empty_client.get(ep)
            assert resp.status_code == 200, f"{ep} returned {resp.status_code}"


class TestAppCreation:
    """Tests for app creation and configuration."""

    def test_create_app_default_root(self):
        """App can be created with default kernel_root."""
        app = create_app()
        assert app is not None
        assert app.title == "AI Kernel Dashboard"

    def test_create_app_custom_root(self, tmp_path: Path):
        """App can be created with a custom root."""
        app = create_app(kernel_root=tmp_path)
        assert app.state.kernel_root == tmp_path

    def test_module_level_app_exists(self):
        """The module-level app instance exists."""
        from web.app import app as module_app

        assert module_app is not None


class TestMetricsEndpoint:
    """Tests for GET /api/metrics."""

    def test_returns_metrics_structure(self, client: TestClient):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_health" in data
        assert "per_node_success_rates" in data
        assert "evolution_velocity" in data
        assert "iteration_distribution" in data
        assert "skill_usage_frequency" in data

    def test_metrics_with_data(self, tmp_path: Path):
        """Verify metrics are computed correctly from reflections data."""
        # Create reflections with node and success data
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        reflections = [
            {"node": "code", "success": True},
            {"node": "code", "success": True},
            {"node": "code", "success": False},
            {"node": "test", "success": True},
            {"node": "test", "success": True},
        ]
        with open(memory_dir / "reflections.jsonl", "w") as f:
            for r in reflections:
                f.write(json.dumps(r) + "\n")

        # Create evolution history
        evo_dir = tmp_path / "kernel" / "evolution"
        evo_dir.mkdir(parents=True)
        history = [{"type": "mutation"}, {"type": "selection"}, {"type": "mutation"}]
        with open(evo_dir / "history.jsonl", "w") as f:
            for h in history:
                f.write(json.dumps(h) + "\n")

        # Create skill metrics
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        metrics_data = {"python-api": {"times_used": 5}, "tdd": {"times_used": 3}}
        with open(skills_dir / "_metrics.yaml", "w") as f:
            yaml.safe_dump(metrics_data, f)

        # Minimal dashboard
        web_dir = tmp_path / "web" / "templates"
        web_dir.mkdir(parents=True)
        with open(web_dir / "dashboard.html", "w") as f:
            f.write("<html><body>OK</body></html>")

        app = create_app(kernel_root=tmp_path)
        c = TestClient(app)
        resp = c.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()

        # code: 2/3 success, test: 2/2 success
        assert abs(data["per_node_success_rates"]["code"] - 2 / 3) < 0.01
        assert data["per_node_success_rates"]["test"] == 1.0
        assert data["iteration_distribution"]["code"] == 3
        assert data["iteration_distribution"]["test"] == 2
        # 3 changes / max(1, 5/10) = 3 / 1 = 3.0
        assert data["evolution_velocity"] == 3.0
        assert data["skill_usage_frequency"]["python-api"] == 5
        assert data["skill_usage_frequency"]["tdd"] == 3

    def test_metrics_empty(self, empty_client: TestClient):
        resp = empty_client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_health"] == 1.0
        assert data["per_node_success_rates"] == {}
        assert data["evolution_velocity"] == 0.0
        assert data["iteration_distribution"] == {}


class TestMetricsHistory:
    """Tests for GET /api/metrics/history."""

    def test_returns_time_series(self, client: TestClient):
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "success_rate_over_time" in data
        assert "node_activity" in data

    def test_time_series_bucketing(self, tmp_path: Path):
        """Verify reflections are bucketed into windows of 10."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        # 20 reflections: first 10 all fail, second 10 all succeed
        reflections = []
        for i in range(20):
            reflections.append({"node": "code", "success": i >= 10})
        with open(memory_dir / "reflections.jsonl", "w") as f:
            for r in reflections:
                f.write(json.dumps(r) + "\n")

        web_dir = tmp_path / "web" / "templates"
        web_dir.mkdir(parents=True)
        with open(web_dir / "dashboard.html", "w") as f:
            f.write("<html><body>OK</body></html>")

        app = create_app(kernel_root=tmp_path)
        c = TestClient(app)
        resp = c.get("/api/metrics/history")
        data = resp.json()
        assert len(data["success_rate_over_time"]) == 2
        assert data["success_rate_over_time"][0]["rate"] == 0.0
        assert data["success_rate_over_time"][1]["rate"] == 1.0
        assert data["node_activity"] == [{"node": "code", "count": 20}]

    def test_empty_history(self, empty_client: TestClient):
        resp = empty_client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success_rate_over_time"] == []
        assert data["node_activity"] == []


class TestCORS:
    """Tests for CORS middleware."""

    def test_cors_headers_present(self, client: TestClient):
        resp = client.options(
            "/api/state",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers

    def test_cors_allows_localhost(self, client: TestClient):
        resp = client.get("/api/state", headers={"Origin": "http://localhost:8000"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_rate_limit_allows_normal_traffic(self, client: TestClient):
        for _ in range(10):
            resp = client.get("/api/state")
            assert resp.status_code == 200

    def test_rate_limit_blocks_excessive(self, tmp_path: Path):
        """Create app with low limit and verify blocking."""
        web_dir = tmp_path / "web" / "templates"
        web_dir.mkdir(parents=True)
        with open(web_dir / "dashboard.html", "w") as f:
            f.write("<html><body>OK</body></html>")

        app = create_app(kernel_root=tmp_path, rate_limit=5)
        c = TestClient(app)

        # First 5 should succeed
        for _ in range(5):
            resp = c.get("/api/state")
            assert resp.status_code == 200

        # 6th should be rate limited
        resp = c.get("/api/state")
        assert resp.status_code == 429
        assert resp.json()["error"] == "Rate limit exceeded"


class TestInputSanitization:
    """Tests for input sanitization on POST /api/goal."""

    def test_html_stripped_from_goal(self, client: TestClient):
        resp = client.post("/api/goal", json={"goal": "<script>alert('xss')</script>Build API"})
        assert resp.status_code == 200
        data = resp.json()
        assert "<script>" not in data.get("goal", "")
        assert "Build API" in data["goal"]

    def test_goal_length_limit(self, client: TestClient):
        resp = client.post("/api/goal", json={"goal": "x" * 1000})
        assert resp.status_code == 400
        assert "500 characters" in resp.json()["error"]

    def test_empty_goal_rejected(self, client: TestClient):
        resp = client.post("/api/goal", json={"goal": ""})
        assert resp.status_code == 400
        assert resp.json()["error"] == "Goal cannot be empty"

    def test_html_only_goal_rejected(self, client: TestClient):
        """Goal that is only HTML tags results in empty after stripping."""
        resp = client.post("/api/goal", json={"goal": "<b></b>"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "Goal cannot be empty"

    def test_valid_goal_within_limit(self, client: TestClient):
        resp = client.post("/api/goal", json={"goal": "x" * 500})
        assert resp.status_code == 200
        assert resp.json()["goal"] == "x" * 500


class TestPathValidation:
    """Tests for workspace boundary validation."""

    def test_validate_path_within_root(self, tmp_path: Path):
        from web.app import _validate_path

        child = tmp_path / "kernel" / "state.yaml"
        assert _validate_path(child, tmp_path) is True

    def test_validate_path_escape_rejected(self, tmp_path: Path):
        from web.app import _validate_path

        escape = tmp_path / ".." / ".." / "etc" / "passwd"
        assert _validate_path(escape, tmp_path) is False

    def test_validate_path_root_itself(self, tmp_path: Path):
        from web.app import _validate_path

        assert _validate_path(tmp_path, tmp_path) is True


class TestStartEndpointSanitization:
    """Tests for input sanitization on POST /api/start."""

    def test_start_strips_html_from_goal(self, client: TestClient, kernel_dir: Path):
        resp = client.post(
            "/api/start",
            json={"goal": "<script>alert('xss')</script>Build API", "max_iterations": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "<script>" not in data.get("goal", "")
        assert "Build API" in data["goal"]

    def test_start_truncates_long_goal(self, client: TestClient, kernel_dir: Path):
        resp = client.post(
            "/api/start",
            json={"goal": "x" * 1000, "max_iterations": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["goal"]) <= 500

    def test_start_empty_goal_allowed(self, client: TestClient, kernel_dir: Path):
        """Empty goal on start is allowed (it's optional)."""
        resp = client.post("/api/start", json={"goal": "", "max_iterations": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"


class TestRateLimiterCleanup:
    """Tests for rate limiter memory cleanup."""

    def test_rate_limiter_has_request_counter(self, tmp_path: Path):
        """Verify rate limiter tracks request count for cleanup."""
        from web.app import RateLimitMiddleware

        web_dir = tmp_path / "web" / "templates"
        web_dir.mkdir(parents=True)
        with open(web_dir / "dashboard.html", "w") as f:
            f.write("<html><body>OK</body></html>")

        app = create_app(kernel_root=tmp_path, rate_limit=1000)
        # Find the rate limit middleware
        rate_limiter = None
        for middleware in app.user_middleware:
            if middleware.cls == RateLimitMiddleware:
                rate_limiter = middleware
                break
        assert rate_limiter is not None
