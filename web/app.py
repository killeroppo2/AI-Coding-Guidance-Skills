"""FastAPI web dashboard for the self-evolving AI kernel.

Provides a single-page dashboard with real-time monitoring,
SSE log streaming, and WebSocket state broadcasts.
"""

import asyncio
import contextlib
import io
import json
import os
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import kernel.orchestrator as orchestrator

KERNEL_ROOT = Path(__file__).resolve().parent.parent


def _validate_path(path: Path, root: Path) -> bool:
    """Validate that a path does not escape the root directory.

    Args:
        path: The path to validate (will be resolved).
        root: The root directory boundary.

    Returns:
        True if path is within root, False otherwise.
    """
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return str(resolved).startswith(str(root_resolved))
    except (OSError, ValueError):
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter using a sliding window."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._request_count = 0

    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Clean old entries for this IP
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if now - t < self.window_seconds
        ]
        if len(self.requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
            )
        self.requests[client_ip].append(now)

        # Periodic cleanup: every 100 requests, purge the dict if it grows too large
        self._request_count += 1
        if self._request_count % 100 == 0:
            if len(self.requests) > 10000:
                self.requests.clear()

        return await call_next(request)


def create_app(kernel_root: Path | None = None, rate_limit: int = 60) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        kernel_root: Path to the project root. Defaults to parent of web/.
        rate_limit: Maximum requests per minute per IP. Defaults to 60.

    Returns:
        Configured FastAPI app instance.
    """
    if kernel_root is None:
        kernel_root = KERNEL_ROOT

    kernel_root = Path(kernel_root)

    app = FastAPI(title="AI Kernel Dashboard")

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit, window_seconds=60)

    # Shared state for execution control
    app.state.kernel_root = kernel_root
    app.state.stop_flag = threading.Event()
    app.state.running = False
    app.state.log_subscribers: list[asyncio.Queue] = []
    app.state.ws_connections: list[WebSocket] = []

    class GoalRequest(BaseModel):
        goal: str

    class StartRequest(BaseModel):
        goal: str = ""
        max_iterations: int = 30

    def _read_yaml(path: Path) -> Any:
        """Read a YAML file, return empty dict/list on failure."""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return data if data is not None else {}
        except (OSError, yaml.YAMLError):
            pass
        return {}

    def _read_jsonl(path: Path, limit: int | None = None) -> list[dict]:
        """Read a JSONL file, return list of dicts. Optionally limit to last N."""
        items: list[dict] = []
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                items.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
        except OSError:
            pass
        if limit is not None:
            return items[-limit:]
        return items

    # Startup validation: confirm kernel_root is sane
    if not _validate_path(kernel_root, kernel_root):
        raise ValueError(f"kernel_root path validation failed: {kernel_root}")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the dashboard HTML page."""
        template_path = kernel_root / "web" / "templates" / "dashboard.html"
        if not _validate_path(template_path, kernel_root):
            return HTMLResponse(content="<h1>Invalid template path</h1>", status_code=403)
        try:
            content = template_path.read_text(encoding="utf-8")
            return HTMLResponse(content=content)
        except (OSError, FileNotFoundError):
            return HTMLResponse(content="<h1>Dashboard template not found</h1>", status_code=500)

    @app.get("/api/state")
    async def get_state():
        """Return current kernel state from kernel/state.yaml."""
        state_path = kernel_root / "kernel" / "state.yaml"
        data = _read_yaml(state_path)
        return data

    @app.get("/api/tasks")
    async def get_tasks():
        """Return tasks from memory/tasks.yaml."""
        tasks_path = kernel_root / "memory" / "tasks.yaml"
        data = _read_yaml(tasks_path)
        if isinstance(data, dict):
            return data.get("tasks", [])
        if isinstance(data, list):
            return data
        return []

    @app.get("/api/history")
    async def get_history():
        """Return evolution history from kernel/evolution/history.jsonl."""
        history_path = kernel_root / "kernel" / "evolution" / "history.jsonl"
        return _read_jsonl(history_path)

    @app.get("/api/reflections")
    async def get_reflections():
        """Return recent reflections from memory/reflections.jsonl (last 50)."""
        reflections_path = kernel_root / "memory" / "reflections.jsonl"
        return _read_jsonl(reflections_path, limit=50)

    @app.get("/api/skills")
    async def get_skills():
        """Return skill list from skills/_index.yaml."""
        skills_path = kernel_root / "skills" / "_index.yaml"
        data = _read_yaml(skills_path)
        if isinstance(data, dict):
            items = data.get("items", [])
            if not items:
                items = data.get("core_items", []) + data.get("community_items", [])
            return items
        return []

    @app.get("/api/metrics")
    async def get_metrics():
        """Return aggregated system metrics."""
        reflections_path = kernel_root / "memory" / "reflections.jsonl"
        history_path = kernel_root / "kernel" / "evolution" / "history.jsonl"
        metrics_path = kernel_root / "skills" / "_metrics.yaml"

        reflections = _read_jsonl(reflections_path)
        history = _read_jsonl(history_path)

        # Compute per_node_success_rates and iteration_distribution
        node_counts: dict[str, int] = defaultdict(int)
        node_successes: dict[str, int] = defaultdict(int)
        for r in reflections:
            node = r.get("node", "unknown")
            node_counts[node] += 1
            if r.get("success", False):
                node_successes[node] += 1

        per_node_success_rates = {}
        for node, count in node_counts.items():
            per_node_success_rates[node] = node_successes[node] / count if count > 0 else 0.0

        iteration_distribution = dict(node_counts)

        # Compute overall_health from per_node rates (weighted by count)
        total_weight = sum(node_counts.values())
        if total_weight > 0:
            overall_health = (
                sum(per_node_success_rates[n] * node_counts[n] for n in node_counts) / total_weight
            )
        else:
            overall_health = 1.0

        # Compute evolution_velocity: total changes / max(1, total_iterations / 10)
        total_changes = len(history)
        total_iterations = len(reflections)
        evolution_velocity = total_changes / max(1, total_iterations / 10)

        # Read skill usage from _metrics.yaml
        skill_usage_frequency: dict[str, int] = {}
        metrics_data = _read_yaml(metrics_path)
        if isinstance(metrics_data, dict):
            for skill_name, skill_info in metrics_data.items():
                if isinstance(skill_info, dict):
                    skill_usage_frequency[skill_name] = skill_info.get("times_used", 0)

        return {
            "overall_health": round(overall_health, 4),
            "per_node_success_rates": per_node_success_rates,
            "evolution_velocity": round(evolution_velocity, 4),
            "iteration_distribution": iteration_distribution,
            "skill_usage_frequency": skill_usage_frequency,
        }

    @app.get("/api/metrics/history")
    async def get_metrics_history():
        """Return time-series data for charts."""
        reflections_path = kernel_root / "memory" / "reflections.jsonl"
        reflections = _read_jsonl(reflections_path)

        # Bucket reflections into windows of 10 iterations
        window_size = 10
        success_rate_over_time = []
        for i in range(0, len(reflections), window_size):
            window = reflections[i : i + window_size]
            successes = sum(1 for r in window if r.get("success", False))
            rate = successes / len(window) if window else 0.0
            success_rate_over_time.append(
                {
                    "window": i // window_size,
                    "rate": round(rate, 4),
                }
            )

        # Node activity counts
        node_counts: dict[str, int] = defaultdict(int)
        for r in reflections:
            node = r.get("node", "unknown")
            node_counts[node] += 1

        node_activity = [{"node": n, "count": c} for n, c in node_counts.items()]

        return {
            "success_rate_over_time": success_rate_over_time,
            "node_activity": node_activity,
        }

    @app.post("/api/goal")
    async def set_goal(request: GoalRequest):
        """Set a new goal - writes to state and memory/current_goal.md."""
        # Input sanitization: strip HTML tags
        goal = re.sub(r"<[^>]+>", "", request.goal)
        goal = goal.strip()

        if not goal:
            return JSONResponse(
                status_code=400,
                content={"error": "Goal cannot be empty"},
            )

        if len(goal) > 500:
            return JSONResponse(
                status_code=400,
                content={"error": "Goal must be 500 characters or fewer"},
            )

        # Update state.yaml
        state_path = kernel_root / "kernel" / "state.yaml"
        state_data = _read_yaml(state_path)
        if not isinstance(state_data, dict):
            state_data = {}
        state_data["goal"] = goal

        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(state_data, f, default_flow_style=False, allow_unicode=True)

        # Write current_goal.md
        memory_dir = kernel_root / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        goal_path = memory_dir / "current_goal.md"
        with open(goal_path, "w", encoding="utf-8") as f:
            f.write(f"# Current Goal\n\n{goal}\n")

        # Broadcast via WebSocket
        await _broadcast_ws({"type": "goal_updated", "goal": goal})

        return {"status": "ok", "goal": goal}

    @app.post("/api/start")
    async def start_execution(request: StartRequest):
        """Start kernel execution in a background thread.

        NOTE: No authentication is enforced on this endpoint. This is a
        development dashboard intended for localhost access. For production
        deployments, configure an auth proxy or middleware. See .env.example.

        The stop flag is checked once before orchestrator.main() begins.
        Once running, the kernel manages its own iteration lifecycle and
        the stop flag has no further effect.
        """
        # Serialization point: prevents concurrent orchestrator calls which
        # would race on the module-level KERNEL_ROOT global.
        if app.state.running:
            return {"status": "already_running"}

        app.state.stop_flag.clear()
        app.state.running = True

        # Apply the same sanitization as /api/goal
        goal = re.sub(r"<[^>]+>", "", request.goal)
        goal = goal.strip()
        if len(goal) > 500:
            goal = goal[:500]
        max_iterations = request.max_iterations

        def _run_kernel():
            try:
                _emit_log(f"Starting kernel with goal: {goal}, max_iterations: {max_iterations}")

                if app.state.stop_flag.is_set():
                    _emit_log("Execution cancelled before start")
                    return

                argv = ["--goal", goal, "--max-iterations", str(max_iterations)]
                ai_command = os.environ.get("AI_COMMAND")
                if ai_command:
                    argv.extend(["--ai-command", ai_command])
                else:
                    argv.append("--dry-run")

                stdout_buf = io.StringIO()
                stderr_buf = io.StringIO()
                # redirect_stdout/stderr is safe here because app.state.running
                # guarantees only one execution thread at a time.
                with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(
                    stderr_buf
                ):
                    orchestrator.main(argv=argv, kernel_root=kernel_root)

                for line in stdout_buf.getvalue().splitlines():
                    if line.strip():
                        _emit_log(line)

                for line in stderr_buf.getvalue().splitlines():
                    if line.strip():
                        _emit_log(f"[stderr] {line}")

                _emit_log("Kernel execution completed")
            except SystemExit:
                stderr_output = stderr_buf.getvalue().strip()
                if stderr_output:
                    _emit_log(f"Kernel exited: {stderr_output.splitlines()[0]}")
                else:
                    _emit_log("Kernel execution exited")
            except Exception as e:
                _emit_log(f"Error: {e}")
            finally:
                app.state.running = False

        thread = threading.Thread(target=_run_kernel, daemon=True)
        thread.start()

        return {"status": "started", "goal": goal, "max_iterations": max_iterations}

    @app.post("/api/stop")
    async def stop_execution():
        """Stop kernel execution.

        NOTE: No authentication is enforced on this endpoint. This is a
        development dashboard intended for localhost access. For production
        deployments, configure an auth proxy or middleware. See .env.example.
        """
        if not app.state.running:
            return {"status": "not_running"}
        app.state.stop_flag.set()
        return {"status": "stopping"}

    @app.get("/api/logs")
    async def stream_logs():
        """SSE endpoint streaming execution logs."""
        queue: asyncio.Queue = asyncio.Queue()
        app.state.log_subscribers.append(queue)

        async def event_generator():
            try:
                # Send initial connection event
                yield "event: connected\ndata: {}\n\n"
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(message)}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield ": keepalive\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                if queue in app.state.log_subscribers:
                    app.state.log_subscribers.remove(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time state change broadcasts."""
        await websocket.accept()
        app.state.ws_connections.append(websocket)
        try:
            # Send current state on connection
            state_path = kernel_root / "kernel" / "state.yaml"
            state_data = _read_yaml(state_path)
            await websocket.send_json({"type": "state", "data": state_data})

            while True:
                # Keep connection alive, listen for client messages
                data = await websocket.receive_text()
                # Echo back as acknowledgment
                await websocket.send_json({"type": "ack", "data": data})
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in app.state.ws_connections:
                app.state.ws_connections.remove(websocket)

    def _emit_log(message: str):
        """Emit a log message to all SSE subscribers."""
        log_entry = {"message": message}
        for queue in list(app.state.log_subscribers):
            try:
                queue.put_nowait(log_entry)
            except asyncio.QueueFull:
                pass

    async def _broadcast_ws(data: dict):
        """Broadcast a message to all connected WebSocket clients."""
        disconnected = []
        for ws in list(app.state.ws_connections):
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in app.state.ws_connections:
                app.state.ws_connections.remove(ws)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
