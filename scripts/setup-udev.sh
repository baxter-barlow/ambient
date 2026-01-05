#!/bin/bash
# Setup udev rules for TI IWR6843AOPEVM radar on the HOST system
# This script must be run on the host, not inside a container
#
# Usage: sudo ./scripts/setup-udev.sh

set -e

RULES_FILE="/etc/udev/rules.d/99-ti-radar.rules"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

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
