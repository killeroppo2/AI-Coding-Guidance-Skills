# Plan: Build a REST API

## Overview

Build a **Task Manager REST API** using **FastAPI** (Python), **SQLAlchemy** (SQLite), and **Pydantic** validation. This is a standard CRUD API demonstrating RESTful design principles.

## Tasks (6 total)

| ID | Title | Complexity | Depends On |
|----|-------|-----------|------------|
| T-001 | Project scaffold | low | — |
| T-002 | Data models and database setup | medium | T-001 |
| T-003 | Pydantic schemas | low | T-002 |
| T-004 | CRUD API endpoints | high | T-003 |
| T-005 | Error handling and middleware | medium | T-004 |
| T-006 | Comprehensive test suite | medium | T-005 |

## Resources

- `/api/tasks` — List, create, update, delete tasks
- `/health` — Health check endpoint
- `/docs` — Auto-generated OpenAPI docs

## Key Design Decisions

- **Framework**: FastAPI (async, auto-docs, Pydantic integration)
- **Database**: SQLite with SQLAlchemy (zero setup, portable)
- **Pagination**: Offset-based (?page=1&page_size=20)
- **Error format**: Consistent JSON with code, message, details
- **API version**: v1 via URL prefix /api/v1
