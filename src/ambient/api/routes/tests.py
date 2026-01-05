"""Test runner API routes."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter

from ..schemas import TestModule, TestRunRequest, TestResult

router = APIRouter(prefix="/api/tests", tags=["tests"])


def get_test_dir() -> Path:
	return Path(os.environ.get("AMBIENT_PROJECT_DIR", ".")) / "tests"


@router.get("/modules", response_model=list[TestModule])
async def list_modules():
	"""List available test modules."""
	test_dir = get_test_dir()
	modules = []

	if not test_dir.exists():
		return modules

	for path in test_dir.glob("test_*.py"):
		# Check if hardware marker is used
		content = path.read_text()
		hardware_required = "@pytest.mark.hardware" in content

		modules.append(TestModule(
			name=path.stem,
			path=str(path),
			hardware_required=hardware_required,
		))

	return modules


@router.post("/run")
async def run_tests(request: TestRunRequest):
	"""Run tests and stream results via WebSocket."""
	test_dir = get_test_dir()

	# Build pytest command
	cmd = ["python", "-m", "pytest", "-v"]

	if request.modules:
		for module in request.modules:
			cmd.append(str(test_dir / f"{module}.py"))
	else:
		cmd.append(str(test_dir))

	if not request.include_hardware:
		cmd.extend(["-m", "not hardware"])

	# Run tests (this would be better streamed via WebSocket)
	proc = await asyncio.create_subprocess_exec(
		*cmd,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.STDOUT,
		cwd=os.environ.get("AMBIENT_PROJECT_DIR", "."),
	)

	stdout, _ = await proc.communicate()

	return {
		"returncode": proc.returncode,
		"output": stdout.decode() if stdout else "",
	}
