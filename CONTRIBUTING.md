# Contributing

## Setup

```bash
git clone https://github.com/baxter/ambient.git
cd ambient
make dev
```

## Workflow

1. Create branch from `main`
2. Make changes
3. Run `make lint && make test`
4. Submit PR

## Code Style

- Black for formatting
- Ruff for linting
- Type hints for public APIs
- Google-style docstrings

## Tests

```bash
make test       # all tests
make test-fast  # skip hardware tests
```

Mark hardware-dependent tests with `@pytest.mark.hardware`.
