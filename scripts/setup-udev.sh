#!/bin/bash
# Setup device permissions for TI IWR6843AOPEVM radar
# Platform-aware: installs udev rules on Linux, provides guidance on macOS
#
# Usage:
#   Linux: sudo ./scripts/setup-udev.sh
#   macOS: ./scripts/setup-udev.sh (no sudo needed, just shows guidance)

set -e

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        *)          echo "unsupported";;
    esac
}

PLATFORM=$(detect_platform)

# Platform-specific setup
case "$PLATFORM" in
    macos)
        echo "=== macOS Serial Port Setup ==="
        echo ""
        echo "Good news: macOS doesn't require special permissions for USB serial devices."
        echo "The TI radar should work automatically when connected."
        echo ""
        echo "Device names on macOS:"
        echo "  - /dev/cu.usbserial-*  (FTDI-based adapters)"
        echo "  - /dev/cu.usbmodem*    (USB CDC devices)"
        echo ""
        echo "Troubleshooting:"
        echo "  1. If the device doesn't appear, try unplugging and reconnecting"
        echo "  2. Check System Settings > Privacy & Security for any blocked drivers"
        echo "  3. Some FTDI drivers may need to be installed from ftdichip.com"
        echo "  4. For Apple Silicon Macs, ensure Rosetta is installed if using older drivers"
        echo ""
        echo "List available ports:"
        echo "  python3 -c \"import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])\""
        echo ""
        exit 0
        ;;
    unsupported)
        echo "=== Unsupported Platform ==="
        echo ""
        echo "Ambient SDK officially supports Linux and macOS only."
        echo ""
        echo "For Windows users, please use WSL2 (Windows Subsystem for Linux):"
        echo "  1. Install WSL2: https://learn.microsoft.com/en-us/windows/wsl/install"
        echo "  2. Install Ubuntu 22.04 from Microsoft Store"
        echo "  3. For USB device access, use usbipd-win:"
        echo "     https://learn.microsoft.com/en-us/windows/wsl/connect-usb"
        echo ""
        exit 1
        ;;
esac

# Linux-specific udev setup below
RULES_FILE="/etc/udev/rules.d/99-ti-radar.rules"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

echo "=== Linux udev Rules Setup ==="
echo ""
echo "Installing udev rules for TI IWR6843AOPEVM..."

# Create udev rules
cat > "$RULES_FILE" << 'EOF'
# TI XDS110 Debug Probe (IWR6843AOPEVM)
# VID:PID for TI XDS110
SUBSYSTEM=="tty", ATTRS{idVendor}=="0451", ATTRS{idProduct}=="bef3", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0451", ATTRS{idProduct}=="bef3", MODE="0666", GROUP="dialout"

# TI IWR6843 direct USB (some firmware versions)
SUBSYSTEM=="tty", ATTRS{idVendor}=="0451", ATTRS{idProduct}=="bef4", MODE="0666", GROUP="dialout"

# Fallback: any TI device on ttyACM*
KERNEL=="ttyACM[0-9]*", ATTRS{idVendor}=="0451", MODE="0666", GROUP="dialout"

# Fallback: any TI device on ttyUSB*
KERNEL=="ttyUSB[0-9]*", ATTRS{idVendor}=="0451", MODE="0666", GROUP="dialout"

# Generic USB serial adapters (FTDI, CP210x, etc.)
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0666", GROUP="dialout"

# Symlinks for easy identification
SUBSYSTEM=="tty", ATTRS{idVendor}=="0451", ATTRS{idProduct}=="bef3", SYMLINK+="ti_radar_%n"
EOF

echo "Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger

echo ""
echo "udev rules installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Add your user to the dialout group:"
echo "     sudo usermod -a -G dialout \$USER"
echo ""
echo "  2. Log out and back in for group changes to take effect"
echo ""
echo "  3. Verify device permissions after connecting radar:"
echo "     ls -la /dev/ttyUSB* /dev/ttyACM*"
echo ""
echo "  4. Test with: python -c \"import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])\""
