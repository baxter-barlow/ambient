#!/bin/bash
# Ambient SDK Setup Script
# Installs Python dependencies, builds the dashboard, and configures the environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Ambient SDK Setup ==="
echo "Project root: $PROJECT_ROOT"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ "$(echo "$PYTHON_VERSION < 3.10" | bc)" -eq 1 ]]; then
    echo "Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "Python version: $PYTHON_VERSION"

# Install Python package in development mode
echo ""
echo "Installing Python package..."
cd "$PROJECT_ROOT"
pip install -e ".[all]" --quiet

# Check Node.js for dashboard
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Node.js version: $NODE_VERSION"

    # Install dashboard dependencies
    echo ""
    echo "Installing dashboard dependencies..."
    cd "$PROJECT_ROOT/dashboard"
    npm install --silent

    # Build dashboard for production
    echo ""
    echo "Building dashboard..."
    npm run build --silent
else
    echo "Warning: Node.js not found. Dashboard will not be available."
    echo "Install Node.js 18+ to use the dashboard."
fi

# Check serial port access
echo ""
echo "Checking serial port access..."
if groups | grep -q dialout; then
    echo "User is in 'dialout' group"
else
    echo "Warning: User not in 'dialout' group. Run:"
    echo "  sudo usermod -aG dialout $USER"
    echo "  (then log out and back in)"
fi

# Create data directory
mkdir -p "$PROJECT_ROOT/data"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Quick start:"
echo "  ./scripts/run.sh          # Start full stack"
echo "  ambient --help            # CLI commands"
echo "  ambient detect            # Check sensor connection"
echo ""
