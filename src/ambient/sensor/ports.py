"""Cross-platform serial port detection for TI mmWave radar devices.

Supports:
- Linux: /dev/ttyUSB*, /dev/ttyACM*
- macOS: /dev/cu.usbserial-*, /dev/cu.usbmodem-*

Note: Windows is not officially supported. Use WSL2 for Windows development.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo

logger = logging.getLogger(__name__)

# TI vendor IDs
TI_VENDOR_IDS = [0x0451, 0x0403]  # Texas Instruments, FTDI (common for TI eval boards)

# XDS110 debug probe identifiers
XDS110_IDENTIFIERS = ["XDS110", "XDS", "JTAG"]


@dataclass
class PortInfo:
    """Information about a detected serial port."""
    device: str
    description: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    is_ti_device: bool = False


def get_platform() -> str:
    """Get the current platform identifier.

    Returns:
        'linux', 'macos', or 'unsupported'
    """
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform.startswith("linux"):
        return "linux"
    else:
        return "unsupported"


def list_serial_ports() -> list[PortInfo]:
    """List all available serial ports with metadata.

    Returns a list of PortInfo objects with device path, description,
    and vendor/product IDs where available.
    """
    ports = []
    platform = get_platform()

    for port in serial.tools.list_ports.comports():
        # Skip Bluetooth ports on macOS
        if platform == "macos" and "Bluetooth" in (port.description or ""):
            continue

        # Check if this is a TI device
        is_ti = False
        if port.vid in TI_VENDOR_IDS:
            is_ti = True
        elif any(ident in (port.description or "") for ident in XDS110_IDENTIFIERS):
            is_ti = True

        ports.append(PortInfo(
            device=port.device,
            description=port.description or port.device,
            vid=port.vid,
            pid=port.pid,
            serial_number=port.serial_number,
            is_ti_device=is_ti,
        ))

    return sorted(ports, key=lambda p: p.device)


def find_ti_radar_ports() -> dict[str, str]:
    """Find TI mmWave radar CLI and Data ports.

    Returns:
        Dictionary with 'cli' and 'data' keys containing device paths,
        or empty dict if ports cannot be found.

    Detection strategy:
    1. Look for TI devices by vendor ID (0x0451)
    2. Look for XDS110 debug probe identifiers
    3. Platform-specific fallbacks
    """
    platform = get_platform()

    if platform == "unsupported":
        logger.warning("Unsupported platform. Use Linux or macOS, or WSL2 on Windows.")
        return {}

    ports = list(serial.tools.list_ports.comports())
    logger.debug(f"Searching for radar ports on {platform}, found {len(ports)} serial ports")

    if not ports:
        logger.warning("No serial ports found. Check USB connection.")
        return {}

    # Strategy 1: Find by TI vendor ID
    ti_ports = [p for p in ports if p.vid in TI_VENDOR_IDS]
    if len(ti_ports) >= 2:
        ti_ports.sort(key=lambda p: p.device)
        logger.info(f"Found TI devices by VID: {[p.device for p in ti_ports]}")
        return {"cli": ti_ports[0].device, "data": ti_ports[1].device}

    # Strategy 2: Find by XDS110 identifiers in description
    xds_ports = [p for p in ports if any(ident in (p.description or "") for ident in XDS110_IDENTIFIERS)]
    if len(xds_ports) >= 2:
        xds_ports.sort(key=lambda p: p.device)
        logger.info(f"Found XDS devices: {[p.device for p in xds_ports]}")
        return {"cli": xds_ports[0].device, "data": xds_ports[1].device}

    # Strategy 3: Platform-specific fallbacks
    if platform == "linux":
        return _find_ports_linux(ports)
    elif platform == "macos":
        return _find_ports_macos(ports)

    return {}


def _find_ports_linux(ports: list[ListPortInfo]) -> dict[str, str]:
    """Linux-specific port detection fallback."""
    # Try ttyACM devices first (common for TI eval boards)
    acm_ports = [p for p in ports if "ttyACM" in p.device]
    if len(acm_ports) >= 2:
        acm_ports.sort(key=lambda p: p.device)
        logger.info(f"Found ACM ports: {[p.device for p in acm_ports]}")
        return {"cli": acm_ports[0].device, "data": acm_ports[1].device}

    # Fallback to ttyUSB devices
    usb_ports = [p for p in ports if "ttyUSB" in p.device]
    if len(usb_ports) >= 2:
        usb_ports.sort(key=lambda p: p.device)
        logger.info(f"Found USB ports: {[p.device for p in usb_ports]}")
        return {"cli": usb_ports[0].device, "data": usb_ports[1].device}

    # Log what we did find for debugging
    if ports:
        logger.debug(f"Found ports but couldn't identify CLI/Data pair: {[p.device for p in ports]}")

    return {}


def _find_ports_macos(ports: list[ListPortInfo]) -> dict[str, str]:
    """macOS-specific port detection fallback."""
    # Filter to cu.* ports (preferred for outgoing connections)
    # Exclude Bluetooth ports
    cu_ports = [
        p for p in ports
        if p.device.startswith("/dev/cu.")
        and "Bluetooth" not in (p.description or "")
        and "Bluetooth" not in p.device
    ]

    # Look for usbserial or usbmodem devices
    usb_ports = [p for p in cu_ports if "usbserial" in p.device.lower() or "usbmodem" in p.device.lower()]
    if len(usb_ports) >= 2:
        usb_ports.sort(key=lambda p: p.device)
        logger.info(f"Found macOS USB ports: {[p.device for p in usb_ports]}")
        return {"cli": usb_ports[0].device, "data": usb_ports[1].device}

    # Fallback: any cu.* ports that aren't Bluetooth
    if len(cu_ports) >= 2:
        cu_ports.sort(key=lambda p: p.device)
        logger.info(f"Found macOS cu.* ports: {[p.device for p in cu_ports]}")
        return {"cli": cu_ports[0].device, "data": cu_ports[1].device}

    # Log what we did find for debugging
    if ports:
        logger.debug(f"Found ports but couldn't identify CLI/Data pair: {[p.device for p in ports]}")

    return {}


def get_default_ports() -> tuple[str, str]:
    """Get platform-appropriate default port paths.

    Returns:
        Tuple of (cli_port, data_port) with sensible defaults for the platform.
        These are fallbacks - prefer find_ti_radar_ports() for auto-detection.
    """
    platform = get_platform()

    if platform == "macos":
        return ("/dev/cu.usbserial-0001", "/dev/cu.usbserial-0002")
    else:  # Linux
        return ("/dev/ttyUSB0", "/dev/ttyUSB1")


def get_permission_help() -> str:
    """Get platform-specific help for serial port permissions.

    Returns detailed, actionable guidance for resolving permission issues.
    """
    platform = get_platform()

    if platform == "linux":
        return """Serial port access denied on Linux. To fix:

  1. Add your user to the 'dialout' group:
     sudo usermod -aG dialout $USER

  2. Log out and back in (or reboot) for the change to take effect

  3. Verify with: groups | grep dialout

  Alternative: Install udev rules for persistent access:
     sudo ./scripts/setup-udev.sh

  See docs/TROUBLESHOOTING.md for more details."""

    elif platform == "macos":
        return """Serial port issues on macOS. To fix:

  1. Ensure the USB cable is properly connected
     - Try unplugging and reconnecting
     - Try a different USB port (avoid hubs)

  2. Check for driver issues:
     - Open System Preferences > Security & Privacy
     - Look for any blocked kernel extensions
     - Some FTDI chips need drivers from ftdichip.com

  3. Verify the device is recognized:
     ls /dev/cu.usb*

  4. If using Apple Silicon (M1/M2/M3):
     - Rosetta may be needed for some drivers
     - Check that Terminal has full disk access

  See docs/TROUBLESHOOTING.md for more details."""

    else:
        return """Unsupported platform detected.

  Ambient SDK officially supports Linux and macOS only.

  For Windows users:
    - Use WSL2 (Windows Subsystem for Linux)
    - Install Ubuntu 22.04 from the Microsoft Store
    - USB device passthrough requires usbipd-win

  See: https://learn.microsoft.com/en-us/windows/wsl/connect-usb"""


def diagnose_ports() -> str:
    """Run port diagnostics and return a human-readable report.

    Useful for troubleshooting connection issues.
    """
    platform = get_platform()
    all_ports = list(serial.tools.list_ports.comports())
    ti_ports = find_ti_radar_ports()

    lines = [
        "=== Serial Port Diagnostics ===",
        f"Platform: {platform}",
        f"Total ports found: {len(all_ports)}",
        "",
    ]

    if not all_ports:
        lines.extend([
            "No serial ports detected!",
            "",
            "Possible causes:",
            "  - USB cable not connected",
            "  - Device not powered on",
            "  - Missing USB drivers",
            "",
            get_permission_help(),
        ])
    else:
        lines.append("Available ports:")
        for port in all_ports:
            vid_pid = f"VID={port.vid:04X} PID={port.pid:04X}" if port.vid else "No VID/PID"
            ti_marker = " [TI Device]" if port.vid in TI_VENDOR_IDS else ""
            lines.append(f"  {port.device}: {port.description} ({vid_pid}){ti_marker}")

        lines.append("")

        if ti_ports:
            lines.extend([
                "TI Radar ports detected:",
                f"  CLI:  {ti_ports['cli']}",
                f"  Data: {ti_ports['data']}",
            ])
        else:
            lines.extend([
                "Could not identify TI radar ports.",
                "",
                "Expected: Two ports from Texas Instruments (VID 0x0451)",
                "          or FTDI (VID 0x0403) with XDS110 in description.",
                "",
                "If the device is connected but not detected:",
                get_permission_help(),
            ])

    return "\n".join(lines)
