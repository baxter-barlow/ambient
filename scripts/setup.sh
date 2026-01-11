#!/bin/bash
# Ambient SDK Setup Script
# Installs Python dependencies, builds the dashboard, and configures the environment
# Supports Linux and macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Ambient SDK Setup ==="
echo "Project root: $PROJECT_ROOT"

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        *)          echo "unsupported";;
    esac
}

PLATFORM=$(detect_platform)
echo "Platform: $PLATFORM"

# Check for unsupported platform
if [ "$PLATFORM" = "unsupported" ]; then
    echo -e "${RED}Error: Unsupported platform.${NC}"
    echo "Ambient SDK supports Linux and macOS only."
    echo ""
    echo "For Windows users:"
    echo "  Use WSL2 (Windows Subsystem for Linux)"
    echo "  https://learn.microsoft.com/en-us/windows/wsl/install"
    exit 1
fi

# Check required tools
echo ""
echo "Checking required tools..."

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 is required but not installed.${NC}"
        echo "$2"
        exit 1
    fi
}

check_command "python3" "Install Python 3.10+ from https://python.org or your package manager"
check_command "pip" "pip should be installed with Python. Try: python3 -m ensurepip"
check_command "git" "Install git from https://git-scm.com or your package manager"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo -e "${RED}Error: Python 3.10+ required (found $PYTHON_VERSION)${NC}"
    echo "Install a newer Python version:"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  brew install python@3.11"
    else
        echo "  sudo apt install python3.11 python3.11-venv"
    fi
    exit 1
fi
echo -e "${GREEN}Python version: $PYTHON_VERSION${NC}"

# Install Python package in development mode
echo ""
echo "Installing Python package..."
cd "$PROJECT_ROOT"
if pip install -e ".[all]" --quiet 2>&1; then
    echo -e "${GREEN}Python package installed successfully${NC}"
else
    echo -e "${RED}Failed to install Python package${NC}"
    echo "Try running: pip install -e '.[all]' manually to see errors"
    exit 1
fi

# Check Node.js for dashboard (optional)
DASHBOARD_AVAILABLE=false
echo ""
echo "Checking Node.js for dashboard..."

if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d'.' -f1)

    if [ "$NODE_MAJOR" -lt 18 ]; then
        echo -e "${YELLOW}Warning: Node.js 18+ recommended (found v$NODE_VERSION)${NC}"
        echo "Dashboard may not work correctly with older versions."
    else
        echo -e "${GREEN}Node.js version: v$NODE_VERSION${NC}"
    fi

    # Install dashboard dependencies
    echo ""
    echo "Installing dashboard dependencies..."
    cd "$PROJECT_ROOT/dashboard"
    if npm install --silent 2>&1; then
        echo -e "${GREEN}Dashboard dependencies installed${NC}"
        DASHBOARD_AVAILABLE=true
    else
        echo -e "${YELLOW}Warning: Failed to install dashboard dependencies${NC}"
    fi

    # Build dashboard for production
    if [ "$DASHBOARD_AVAILABLE" = true ]; then
        echo ""
        echo "Building dashboard..."
        if npm run build --silent 2>&1; then
            echo -e "${GREEN}Dashboard built successfully${NC}"
        else
            echo -e "${YELLOW}Warning: Dashboard build failed${NC}"
            DASHBOARD_AVAILABLE=false
        fi
    fi
else
    echo -e "${YELLOW}Node.js not found - dashboard will not be available${NC}"
    echo "To install Node.js:"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  brew install node"
    else
        echo "  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
        echo "  sudo apt-get install -y nodejs"
    fi
fi

# Check serial port access (platform-specific)
echo ""
echo "Checking serial port access..."

case "$PLATFORM" in
    linux)
        if groups | grep -q dialout; then
            echo -e "${GREEN}User is in 'dialout' group - serial access OK${NC}"
        else
            echo -e "${YELLOW}Warning: User not in 'dialout' group${NC}"
            echo "Run the following command, then log out and back in:"
            echo "  sudo usermod -aG dialout \$USER"
        fi
        ;;
    macos)
        echo "macOS serial ports should be accessible automatically."
        echo "If you encounter permission issues:"
        echo "  1. Check System Settings > Privacy & Security"
        echo "  2. Try unplugging and reconnecting the USB cable"
        echo "  3. Run: ls /dev/cu.usb* to verify device is detected"
        ;;
esac

# Create required directories
mkdir -p "$PROJECT_ROOT/data"
mkdir -p "$PROJECT_ROOT/logs"

# Verify installation
echo ""
echo "Verifying installation..."
cd "$PROJECT_ROOT"

VERIFY_FAILED=false

# Check CLI is accessible
if python3 -c "import ambient" 2>/dev/null; then
    echo -e "${GREEN}ambient package importable${NC}"
else
    echo -e "${RED}Failed to import ambient package${NC}"
    VERIFY_FAILED=true
fi

# Check CLI command
if command -v ambient &> /dev/null || python3 -m ambient --help &> /dev/null; then
    echo -e "${GREEN}ambient CLI accessible${NC}"
else
    echo -e "${YELLOW}ambient CLI not in PATH (use 'python3 -m ambient' instead)${NC}"
fi

# Summary
echo ""
echo "=== Setup Complete ==="
echo ""

if [ "$VERIFY_FAILED" = true ]; then
    echo -e "${YELLOW}Setup completed with warnings. Check messages above.${NC}"
else
    echo -e "${GREEN}All components installed successfully!${NC}"
fi

echo ""
echo "Quick start:"
echo "  ambient detect              # Check sensor connection"
echo "  ambient config list         # List available configurations"
if [ "$DASHBOARD_AVAILABLE" = true ]; then
    echo "  make dashboard              # Start dashboard (dev mode)"
else
    echo "  (Dashboard not available - install Node.js 18+)"
fi
echo ""
echo "Mock mode (no hardware required):"
echo "  AMBIENT_MOCK_RADAR=true ambient capture"
echo "  AMBIENT_MOCK_RADAR=true make dashboard"
echo ""
echo "For troubleshooting, see: docs/TROUBLESHOOTING.md"
echo ""

if [ "$PLATFORM" = "macos" ]; then
    echo "macOS notes:"
    echo "  - Serial ports appear as /dev/cu.usbserial-* or /dev/cu.usbmodem-*"
    echo "  - Auto-detection will find TI devices automatically"
    echo ""
fi
