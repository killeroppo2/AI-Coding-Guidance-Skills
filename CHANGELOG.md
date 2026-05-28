# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT LICENSE file with proper copyright attribution
- Dockerfile for containerized deployment (python:3.12-slim, port 8000)
- .dockerignore for clean Docker builds
- Makefile with standard development targets (init, install, test, lint, typecheck, format, run, clean, docker-build, docker-run, release)
- Structured logging via `kernel/logging_config.py` with LOG_LEVEL and LOG_FORMAT environment variables
- AI Provider abstraction layer (`kernel/providers/`) supporting CLI, OpenAI, and Anthropic backends
- `--provider` and `--model` CLI flags for provider selection
- Optional dependencies for openai and anthropic SDKs
- CHANGELOG.md following Keep a Changelog format
- GitHub Actions release workflow for automated releases on tag push

### Changed
- Replaced print statements in kernel package with Python logging module
- Updated README.md license section to reference LICENSE file
