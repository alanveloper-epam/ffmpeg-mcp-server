# Contributing to `ffmpeg-mcp-server`

Thank you for your interest in contributing to `ffmpeg-mcp-server`! Contributions of bug fixes, new deterministic FFmpeg filter builders, documentation improvements, and tests are welcome.

## Development Setup

```bash
git clone https://github.com/alanveloper-epam/ffmpeg-mcp-server.git
cd ffmpeg-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Checks

Before opening a pull request, ensure all unit tests and linter checks pass:

```bash
pytest -q
ruff check .
```

## Pull Request Guidelines

- Follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- Maintain the security invariants in [SECURITY.md](SECURITY.md): never use `shell=True`, and always resolve paths through `resolve_workspace_path()`.
- Add offline unit tests in `tests/` for every new tool or filter builder.
