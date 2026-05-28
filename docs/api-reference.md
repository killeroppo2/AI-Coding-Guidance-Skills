# Web API Reference

The kernel provides a FastAPI-based web dashboard with REST, SSE, and WebSocket
endpoints for real-time monitoring and control.

## Base URL

Default: `http://localhost:8000`

Configurable via environment variables (see `.env.example`).

---

## Dashboard

### GET /

**Description:** Serves the HTML dashboard with Chart.js visualizations.

**Response:** `text/html` - Full dashboard page with real-time charts.

---

## State & Monitoring

### GET /api/state

**Description:** Returns the current kernel execution state.

**Response:**
```json
{
  "current_node": "code",
  "iteration_count": 5,
  "max_iterations": 30,
  "goal": "Build a REST API",
  "workspace_path": "./workspace/build-a-rest-api/",
  "status": "running",
  "last_updated": "2025-01-27T12:00:00+00:00",
  "errors": [],
  "context": {
    "skills_loaded": ["python-flask", "rest-api"],
    "current_task": "",
    "phase": "coding"
  },
  "node_visits": {"init": 1, "plan": 1, "code": 3},
  "progress_history": [0, 1, 2],
  "execution_mode": "kernel"
}
```

### GET /api/tasks

**Description:** Returns the current task list from memory/tasks.yaml.

**Response:**
```json
{
  "tasks": [
    {"id": 1, "description": "Set up Flask app", "status": "done"},
    {"id": 2, "description": "Create database schema", "status": "in_progress"},
    {"id": 3, "description": "Implement CRUD endpoints", "status": "pending"}
  ]
}
```

### GET /api/history

**Description:** Returns evolution history from evolution/history.jsonl.

**Response:**
```json
{
  "entries": [
    {
      "id": "uuid-1",
      "type": "modify_prompt",
      "details": {"node_id": "code", "prompt_file": "prompts/code.md"},
      "reason": "Node 'code' has failed 3 times",
      "timestamp": "2025-01-27T12:00:00+00:00",
      "status": "applied"
    }
  ],
  "total": 1
}
```

### GET /api/reflections

**Description:** Returns the 20 most recent reflections.

**Response:**
```json
{
  "reflections": [
    {
      "iteration": 5,
      "node": "test",
      "success": false,
      "learnings": [],
      "issues": ["Error: tests failed"],
      "timestamp": "2025-01-27T12:00:00+00:00"
    }
  ]
}
```

### GET /api/skills

**Description:** Returns the skill inventory from knowledge/skills/.

**Response:**
```json
{
  "skills": [
    {
      "name": "python-flask",
      "description": "Flask web framework patterns",
      "tags": ["python", "web", "flask"]
    }
  ]
}
```

---

## Metrics

### GET /api/metrics

**Description:** Returns current system health and per-node metrics.

**Response:**
```json
{
  "overall_health": 0.85,
  "per_node_success_rates": {
    "init": 1.0,
    "plan": 0.9,
    "code": 0.7,
    "test": 0.6
  },
  "evolution_velocity": 0.3,
  "iteration_distribution": {
    "init": 2,
    "plan": 3,
    "code": 8,
    "test": 5
  },
  "skill_usage_frequency": {}
}
```

### GET /api/metrics/history

**Description:** Returns time-series metrics data for chart rendering.

**Response:**
```json
{
  "success_rate_over_time": [
    {"window": 1, "rate": 0.8},
    {"window": 2, "rate": 0.7},
    {"window": 3, "rate": 0.9}
  ]
}
```

---

## Control

### POST /api/goal

**Description:** Set a new development goal.

**Request Body:**
```json
{
  "goal": "Build a Python Flask todo app"
}
```

**Validation:**
- Goal must not be empty
- Maximum 500 characters
- HTML tags are stripped

**Response (200):**
```json
{
  "status": "ok",
  "goal": "Build a Python Flask todo app"
}
```

**Response (400):**
```json
{
  "error": "Goal must not be empty"
}
```

### POST /api/start

**Description:** Start kernel execution with current goal.

**Response:**
```json
{
  "status": "started"
}
```

### POST /api/stop

**Description:** Stop kernel execution gracefully.

**Response:**
```json
{
  "status": "stopped"
}
```

---

## Real-time Streams

### GET /api/logs

**Description:** Server-Sent Events stream for real-time log output.

**Content-Type:** `text/event-stream`

**Event Format:**
```
data: {"timestamp": "2025-01-27T12:00:00", "level": "info", "message": "Iteration 5 completed"}

data: {"timestamp": "2025-01-27T12:00:01", "level": "error", "message": "Test failed"}
```

### WS /ws

**Description:** WebSocket endpoint for bidirectional real-time updates.

**Messages from server:**
```json
{
  "type": "state_update",
  "data": {
    "current_node": "test",
    "iteration_count": 6,
    "status": "running"
  }
}
```

```json
{
  "type": "reflection",
  "data": {
    "node": "code",
    "success": true,
    "learnings": ["Code compiled successfully"]
  }
}
```

---

## Security

- **CORS**: Configurable allowed origins (default: localhost:8000, 127.0.0.1:8000)
- **Rate Limiting**: 60 requests/minute per IP (configurable). Returns HTTP 429.
- **Input Sanitization**: HTML stripped from goal input, length limited to 500 chars.
- **Path Validation**: All file-reading endpoints validate paths stay within project root. Returns HTTP 400/403 for traversal attempts.

---

## Error Responses

All error responses follow this format:
```json
{
  "error": "Human-readable error message"
}
```

Common status codes:
- 400: Bad request (invalid input, path traversal)
- 403: Forbidden (path outside workspace)
- 429: Rate limit exceeded
- 500: Internal server error
