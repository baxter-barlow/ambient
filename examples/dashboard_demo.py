#!/usr/bin/env python3
"""Launch the full Ambient dashboard stack.

Starts the API server and opens the dashboard in a browser.
Usage: python examples/dashboard_demo.py [--no-browser]
"""
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

API_PORT = int(os.environ.get("AMBIENT_API_PORT", 8000))
DASHBOARD_URL = f"http://localhost:{API_PORT}"


def main():
    no_browser = "--no-browser" in sys.argv

    print("=" * 50)
    print("   Ambient Dashboard Demo")
    print("=" * 50)
    print()

    # Check if dashboard is built
    dist_dir = PROJECT_ROOT / "dashboard" / "dist"
    if not dist_dir.exists():
        print("Building dashboard (first run)...")
        subprocess.run(
            ["npm", "run", "build"],
            cwd=PROJECT_ROOT / "dashboard",
            check=True,
            capture_output=True,
        )
        print("Dashboard built successfully")
        print()

    print(f"Starting API server on port {API_PORT}...")

    # Start API server
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "ambient.api", "--port", str(API_PORT)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for server to start
    time.sleep(2)

    if api_proc.poll() is not None:
        print("Error: API server failed to start")
        sys.exit(1)

    print(f"Dashboard available at: {DASHBOARD_URL}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Open browser
    if not no_browser:
        webbrowser.open(DASHBOARD_URL)

    try:
        api_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api_proc.terminate()
        api_proc.wait(timeout=5)
        print("Done")


if __name__ == "__main__":
    main()
