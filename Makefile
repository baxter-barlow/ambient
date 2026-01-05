.PHONY: install dev lint format test clean dashboard dashboard-backend dashboard-frontend dashboard-install dashboard-build docker-dev docker-prod docker-build docker-stop

install:
	pip install -e .

dev:
	pip install -e ".[dev,viz,dashboard]"
	pre-commit install

lint:
	ruff check src/ tests/
	black --check src/ tests/

format:
	ruff check --fix src/ tests/
	black src/ tests/

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -m "not hardware and not slow"

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

# Dashboard targets (native)
dashboard:
	$(MAKE) -j2 dashboard-backend dashboard-frontend

dashboard-backend:
	cd $(CURDIR) && uvicorn ambient.api.main:app --reload --port 8000

dashboard-frontend:
	cd dashboard && npm run dev

dashboard-install:
	pip install -e ".[dashboard]"
	cd dashboard && npm install

dashboard-build:
	cd dashboard && npm run build

# Docker targets
docker-dev:
	docker compose --profile dev up --build

docker-prod:
	docker compose --profile prod up --build -d

docker-build:
	docker compose build

docker-stop:
	docker compose --profile dev --profile prod down

docker-logs:
	docker compose logs -f

docker-shell:
	docker compose --profile dev exec dev bash
