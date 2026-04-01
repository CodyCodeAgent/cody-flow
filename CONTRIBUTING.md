# Contributing to CodyFlow

Thank you for your interest in contributing to CodyFlow! This document provides guidelines and instructions for contributing.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/codycodeagent/cody-flow.git
cd cody-flow

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Verify setup
make test
```

## Development Workflow

1. **Fork** the repository and create a feature branch from `main`
2. **Make** your changes
3. **Test** your changes: `make test`
4. **Lint** your code: `make lint`
5. **Format** your code: `make fmt`
6. **Commit** with a clear, descriptive message
7. **Push** and open a Pull Request

## Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Target Python version: 3.10+
- Line length: 100 characters
- Run `make fmt` before committing

## Project Structure

```
codyflow/
  __main__.py          # Entry point (web server)
  storage.py           # SQLite flow storage
  engine/
    flow.py            # Core flow engine (LangGraph)
    logger.py          # Execution logger
  nodes/
    base.py            # Node base classes, FlowState
    builtin.py         # Built-in node types
    registry.py        # Node type registry
  runners/
    base.py            # Runner abstract base
    cody_runner.py     # Cody SDK runner
    claude_runner.py   # Claude Agent SDK runner
    registry.py        # Runner registry
  web/
    api.py             # FastAPI backend
    templates/         # HTML templates
    static/            # CSS, JS, components
examples/              # YAML flow templates
tests/                 # Unit tests
```

## Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_nodes.py -v

# Run with output
pytest -s
```

### Writing Tests

- Place tests in `tests/` with the `test_` prefix
- Use `pytest` fixtures for setup/teardown
- Use `unittest.mock` for mocking external dependencies (runners, SDKs)
- Use `pytest.mark.asyncio` for async tests
- Aim for clear, focused test cases — one assertion per test when practical

## Adding a New Node Type

1. Create your node class in `codyflow/nodes/builtin.py` (or a new file)
2. Inherit from `SimpleNode` (or `Node` for custom execute logic)
3. Set `node_type` and `default_prompt` class attributes
4. Register it: `register_node_type("my_type", MyNode)`
5. Add tests in `tests/`

```python
class MyNode(SimpleNode):
    node_type = "my_type"
    default_prompt = "You are a custom node. Do X."

register_node_type("my_type", MyNode)
```

## Adding a New Runner

1. Create a new file in `codyflow/runners/`
2. Inherit from `Runner` and implement `async run()`
3. Register it: `register_runner("my_runner", MyRunner)`
4. Add tests

## Commit Messages

Use clear, descriptive commit messages:

- `feat: add new node type for testing`
- `fix: prevent checkpoint from overwriting user input`
- `docs: update README with WebSocket details`
- `test: add unit tests for flow engine`
- `refactor: extract YAML parsing helper`

## Reporting Issues

When reporting a bug, please include:

- Python version (`python --version`)
- CodyFlow version (`pip show codyflow`)
- Steps to reproduce
- Expected vs actual behavior
- Error messages / tracebacks

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
