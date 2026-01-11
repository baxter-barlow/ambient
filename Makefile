.PHONY: install dev lint format test clean dashboard dashboard-backend dashboard-frontend dashboard-install dashboard-build docker-dev docker-prod docker-build docker-stop check test-mock

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

test-mock:
	AMBIENT_MOCK_RADAR=true pytest tests/ -v -m "not hardware"

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

# Verify installation and environment
check:
	@echo "=== Ambient SDK Environment Check ==="
	@echo ""
	@echo "Python:"
	@python3 --version
	@echo ""
	@echo "Package import:"
	@python3 -c "import ambient; print('  ambient:', ambient.__file__)" || echo "  ERROR: ambient not importable"
	@python3 -c "import ambient.sensor; print('  sensor module: OK')" || echo "  ERROR: sensor module failed"
	@python3 -c "import ambient.api; print('  api module: OK')" || echo "  ERROR: api module failed"
	@echo ""
	@echo "CLI:"
	@which ambient 2>/dev/null && echo "  ambient CLI: $(shell which ambient)" || echo "  ambient CLI: not in PATH (use 'python3 -m ambient')"
	@echo ""
	@echo "Serial ports:"
	@python3 -c "from ambient.sensor.ports import diagnose_ports; print(diagnose_ports())"
	@echo ""
	@echo "Directories:"
	@test -d configs && echo "  configs/: OK" || echo "  configs/: MISSING"
	@test -d data && echo "  data/: OK" || echo "  data/: MISSING (run: mkdir data)"
	@test -d dashboard && echo "  dashboard/: OK" || echo "  dashboard/: MISSING"
	@echo ""
	@echo "Node.js (optional):"
	@which node 2>/dev/null && node --version || echo "  not installed (dashboard unavailable)"
	@echo ""
	@echo "Mock mode test:"
	@AMBIENT_MOCK_RADAR=true python3 -c "from ambient.sensor import get_sensor; s = get_sensor(); s.connect(); print('  MockRadarSensor: OK'); s.disconnect()" || echo "  ERROR: mock mode failed"
	@echo ""
	@echo "=== Check Complete ==="

# Dashboard targets (native)
dashboard:
	./scripts/dev.sh

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
