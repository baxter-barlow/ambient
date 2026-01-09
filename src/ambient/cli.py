"""Command-line interface."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import click
import structlog
from rich.console import Console
from rich.live import Live
from rich.table import Table

structlog.configure(
	processors=[
		structlog.stdlib.add_log_level,
		structlog.processors.TimeStamper(fmt="iso"),
		structlog.dev.ConsoleRenderer(),
	],
	wrapper_class=structlog.stdlib.BoundLogger,
	context_class=dict,
	logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)
console = Console()

# Default paths - resolve relative to package installation
def _get_configs_dir() -> Path:
	"""Find the configs directory."""
	# Check common locations
	candidates = [
		Path.cwd() / "configs",  # Current working directory
		Path(__file__).parent.parent.parent.parent / "configs",  # Relative to package
		Path.home() / ".ambient" / "configs",  # User home
	]
	for p in candidates:
		if p.exists():
			return p
	# Default to cwd/configs even if it doesn't exist
	return Path.cwd() / "configs"


CONFIGS_DIR = _get_configs_dir()
PROFILES_FILE = CONFIGS_DIR / "profiles.json"


@click.group()
@click.version_option()
def main() -> None:
	"""Ambient - Sleep biometrics monitoring with mmWave radar."""
	pass


@main.command()
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
@click.option("--data-port", default="/dev/ttyUSB1", help="Data serial port")
@click.option("--config", type=click.Path(exists=True), help="Chirp config file")
@click.option("-o", "--output", type=click.Path(), help="Output file (.h5 or .parquet)")
@click.option("-d", "--duration", type=float, default=0, help="Recording duration (0=unlimited)")
def capture(cli_port: str, data_port: str, config: str | None, output: str | None, duration: float) -> None:
	"""Capture radar data and vital signs."""
	from ambient.processing import ProcessingPipeline
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig
	from ambient.storage import HDF5Writer, ParquetWriter
	from ambient.vitals import VitalsExtractor

	console.print("[bold green]Ambient[/] - Starting capture...")

	sensor = RadarSensor(SerialConfig(cli_port=cli_port, data_port=data_port))
	pipeline = ProcessingPipeline()
	extractor = VitalsExtractor()

	writer = None
	if output:
		p = Path(output)
		writer = ParquetWriter(p) if p.suffix in [".parquet", ".pq"] else HDF5Writer(p)
		console.print(f"Writing to: {p}")

	try:
		sensor.connect()
		if config:
			sensor.configure(config)
		else:
			from ambient.sensor.config import create_vital_signs_config
			sensor.configure(create_vital_signs_config().to_commands())
		sensor.start()

		console.print("[green]Sensor connected[/]")
		console.print("Press Ctrl+C to stop...")

		start = time.time()
		count = 0

		def make_table() -> Table:
			t = Table(title="Vital Signs Monitor")
			t.add_column("Metric", style="cyan")
			t.add_column("Value", style="green")
			t.add_column("Confidence", style="yellow")
			return t

		with Live(make_table(), refresh_per_second=2) as live:
			for frame in sensor.stream():
				count += 1
				if duration > 0 and time.time() - start >= duration:
					break

				processed = pipeline.process(frame)
				vitals = extractor.process_frame(processed)

				if writer:
					writer.write_frame(frame)
					writer.write_vitals(vitals)

				t = make_table()
				t.add_row("Heart Rate", f"{vitals.heart_rate_bpm:.0f} BPM" if vitals.heart_rate_bpm else "---", f"{vitals.heart_rate_confidence:.1%}")
				t.add_row("Respiratory Rate", f"{vitals.respiratory_rate_bpm:.0f} BPM" if vitals.respiratory_rate_bpm else "---", f"{vitals.respiratory_rate_confidence:.1%}")
				t.add_row("Signal Quality", f"{vitals.signal_quality:.1%}", "---")
				t.add_row("Frames", str(count), "---")
				live.update(t)

	except KeyboardInterrupt:
		console.print("\n[yellow]Stopped[/]")
	except Exception as e:
		console.print(f"[red]Error: {e}[/]")
		logger.exception("capture_error")
		sys.exit(1)
	finally:
		sensor.stop()
		sensor.disconnect()
		if writer:
			writer.close()

	elapsed = time.time() - start
	console.print(f"\n[green]Done![/] {count} frames, {elapsed:.1f}s, {count / elapsed:.1f} fps")


@main.command()
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
@click.option("--data-port", default="/dev/ttyUSB1", help="Data serial port")
@click.option("--config", type=click.Path(exists=True), help="Chirp config file")
def monitor(cli_port: str, data_port: str, config: str | None) -> None:
	"""Live monitoring with visualization."""
	from ambient.processing import ProcessingPipeline
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig
	from ambient.vitals import VitalsExtractor
	from ambient.viz import VitalsPlotter

	console.print("[bold green]Ambient[/] - Starting monitor...")

	sensor = RadarSensor(SerialConfig(cli_port=cli_port, data_port=data_port))
	pipeline = ProcessingPipeline()
	extractor = VitalsExtractor()
	plotter = VitalsPlotter()

	try:
		sensor.connect()
		if config:
			sensor.configure(config)
		else:
			from ambient.sensor.config import create_vital_signs_config
			sensor.configure(create_vital_signs_config().to_commands())
		sensor.start()

		console.print("[green]Connected[/] - Close plot window to stop")
		plotter.setup()

		import matplotlib.pyplot as plt
		plt.ion()

		for frame in sensor.stream():
			processed = pipeline.process(frame)
			vitals = extractor.process_frame(processed)
			plotter.update(vitals)
			plt.pause(0.01)

	except KeyboardInterrupt:
		console.print("\n[yellow]Stopped[/]")
	finally:
		sensor.stop()
		sensor.disconnect()
		plotter.close()


@main.command()
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
@click.option("--data-port", default="/dev/ttyUSB1", help="Data serial port")
def info(cli_port: str, data_port: str) -> None:
	"""Show sensor information."""
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig

	sensor = RadarSensor(SerialConfig(cli_port=cli_port, data_port=data_port))

	try:
		sensor.connect()
		version = sensor.get_version()
		status = sensor.query_status()

		t = Table(title="Sensor Info")
		t.add_column("Property", style="cyan")
		t.add_column("Value", style="green")

		t.add_row("Firmware Version", version.strip() if version else "N/A")
		t.add_row("Status", status.strip() if status else "N/A")

		console.print(t)
	except Exception as e:
		console.print(f"[red]Error: {e}[/]")
		sys.exit(1)
	finally:
		sensor.disconnect()


@main.group()
def config() -> None:
	"""Manage radar configuration files."""
	pass


@config.command("list")
def config_list() -> None:
	"""List available configuration files."""
	if not CONFIGS_DIR.exists():
		console.print(f"[yellow]Config directory not found: {CONFIGS_DIR}[/]")
		return

	configs = sorted(CONFIGS_DIR.glob("*.cfg"))
	if not configs:
		console.print("[yellow]No configuration files found[/]")
		return

	t = Table(title="Available Configurations")
	t.add_column("Name", style="cyan")
	t.add_column("Size", style="dim")
	t.add_column("Modified", style="dim")

	for cfg in configs:
		stat = cfg.stat()
		modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
		t.add_row(cfg.stem, f"{stat.st_size} bytes", modified)

	console.print(t)


@config.command("show")
@click.argument("name")
def config_show(name: str) -> None:
	"""Show contents of a configuration file."""
	cfg_path = CONFIGS_DIR / f"{name}.cfg"
	if not cfg_path.exists():
		console.print(f"[red]Config not found: {name}[/]")
		console.print(f"Available: {', '.join(c.stem for c in CONFIGS_DIR.glob('*.cfg'))}")
		sys.exit(1)

	console.print(f"[bold cyan]Configuration: {name}[/]\n")
	with open(cfg_path) as f:
		for i, line in enumerate(f, 1):
			line = line.rstrip()
			if line.startswith("%"):
				console.print(f"[dim]{i:3}  {line}[/]")
			elif line:
				console.print(f"[green]{i:3}[/]  {line}")
			else:
				console.print(f"{i:3}")


@config.command("validate")
@click.argument("name")
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
def config_validate(name: str, cli_port: str) -> None:
	"""Validate a configuration by sending to sensor (dry run)."""
	from ambient.sensor.config import load_config_file

	cfg_path = CONFIGS_DIR / f"{name}.cfg"
	if not cfg_path.exists():
		console.print(f"[red]Config not found: {name}[/]")
		sys.exit(1)

	try:
		commands = load_config_file(cfg_path)
		console.print(f"[green]Valid configuration with {len(commands)} commands[/]")

		# Show key parameters
		for cmd in commands:
			if cmd.startswith("profileCfg"):
				parts = cmd.split()
				if len(parts) >= 3:
					console.print(f"  Start freq: {parts[2]} GHz")
			elif cmd.startswith("frameCfg"):
				parts = cmd.split()
				if len(parts) >= 6:
					# frameCfg: start_chirp, end_chirp, num_loops, num_frames, frame_period, ...
					console.print(f"  Loops: {parts[3]}, Period: {parts[5]} ms")
			elif cmd.startswith("guiMonitor"):
				console.print(f"  Output: {cmd}")

	except Exception as e:
		console.print(f"[red]Invalid config: {e}[/]")
		sys.exit(1)


@main.group()
def profile() -> None:
	"""Manage sensor configuration profiles."""
	pass


def _load_profiles() -> dict:
	"""Load profiles from JSON file."""
	if not PROFILES_FILE.exists():
		return {}
	try:
		with open(PROFILES_FILE) as f:
			return json.load(f)
	except (json.JSONDecodeError, OSError):
		return {}


def _save_profiles(profiles: dict) -> None:
	"""Save profiles to JSON file."""
	PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
	with open(PROFILES_FILE, "w") as f:
		json.dump(profiles, f, indent=2)


@profile.command("list")
def profile_list() -> None:
	"""List saved profiles."""
	profiles = _load_profiles()
	if not profiles:
		console.print("[yellow]No profiles saved[/]")
		console.print("Create one with: ambient profile save <name> --config <config>")
		return

	t = Table(title="Saved Profiles")
	t.add_column("Name", style="cyan")
	t.add_column("Config", style="green")
	t.add_column("Description")
	t.add_column("Created", style="dim")

	for name, data in profiles.items():
		t.add_row(
			name,
			data.get("config", "-"),
			data.get("description", "-"),
			data.get("created", "-"),
		)

	console.print(t)


@profile.command("save")
@click.argument("name")
@click.option("--config", "config_name", required=True, help="Config file name")
@click.option("--description", "-d", default="", help="Profile description")
def profile_save(name: str, config_name: str, description: str) -> None:
	"""Save a new profile."""
	# Verify config exists
	cfg_path = CONFIGS_DIR / f"{config_name}.cfg"
	if not cfg_path.exists():
		console.print(f"[red]Config not found: {config_name}[/]")
		sys.exit(1)

	profiles = _load_profiles()
	profiles[name] = {
		"config": config_name,
		"description": description,
		"created": datetime.now().isoformat(),
	}
	_save_profiles(profiles)
	console.print(f"[green]Profile '{name}' saved[/]")


@profile.command("delete")
@click.argument("name")
def profile_delete(name: str) -> None:
	"""Delete a saved profile."""
	profiles = _load_profiles()
	if name not in profiles:
		console.print(f"[red]Profile not found: {name}[/]")
		sys.exit(1)

	del profiles[name]
	_save_profiles(profiles)
	console.print(f"[yellow]Profile '{name}' deleted[/]")


@profile.command("apply")
@click.argument("name")
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
@click.option("--data-port", default="/dev/ttyUSB1", help="Data serial port")
def profile_apply(name: str, cli_port: str, data_port: str) -> None:
	"""Apply a saved profile to the sensor."""
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig

	profiles = _load_profiles()
	if name not in profiles:
		console.print(f"[red]Profile not found: {name}[/]")
		sys.exit(1)

	config_name = profiles[name]["config"]
	cfg_path = CONFIGS_DIR / f"{config_name}.cfg"

	console.print(f"[cyan]Applying profile '{name}' (config: {config_name})[/]")

	try:
		sensor = RadarSensor(SerialConfig(cli_port=cli_port, data_port=data_port))
		sensor.connect()
		sensor.configure(cfg_path)
		console.print("[green]Profile applied successfully[/]")
	except Exception as e:
		console.print(f"[red]Failed to apply profile: {e}[/]")
		sys.exit(1)
	finally:
		sensor.disconnect()


@main.command()
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
@click.option("--data-port", default="/dev/ttyUSB1", help="Data serial port")
def detect(cli_port: str, data_port: str) -> None:
	"""Detect and identify connected radar firmware."""
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig

	console.print("[cyan]Detecting radar firmware...[/]")

	try:
		sensor = RadarSensor(SerialConfig(cli_port=cli_port, data_port=data_port))
		sensor.connect()
		info = sensor.detect_firmware()

		t = Table(title="Detected Firmware")
		t.add_column("Property", style="cyan")
		t.add_column("Value", style="green")

		t.add_row("Type", info.get("type", "unknown"))
		t.add_row("Version", info.get("version") or "N/A")
		t.add_row("Raw Response", info.get("raw", "")[:60] + "..." if len(info.get("raw", "")) > 60 else info.get("raw", ""))

		console.print(t)

		# Recommend config based on firmware type
		if info["type"] == "vital_signs":
			console.print("\n[green]Recommended config: vital_signs.cfg[/]")
		elif info["type"] == "oob_demo":
			console.print("\n[green]Recommended config: working.cfg[/]")

	except Exception as e:
		console.print(f"[red]Detection failed: {e}[/]")
		sys.exit(1)
	finally:
		sensor.disconnect()


@main.command()
@click.option("--cli-port", default="/dev/ttyUSB0", help="CLI serial port")
def reset(cli_port: str) -> None:
	"""Send sensor stop and flush commands (soft reset)."""
	import serial

	console.print("[yellow]Sending soft reset commands...[/]")

	try:
		with serial.Serial(cli_port, 115200, timeout=1.0) as cli:
			cli.write(b"sensorStop\n")
			time.sleep(0.2)
			response = cli.read(cli.in_waiting).decode("utf-8", errors="ignore")
			console.print(f"[dim]sensorStop: {response.strip()}[/]")

			cli.write(b"flushCfg\n")
			time.sleep(0.2)
			response = cli.read(cli.in_waiting).decode("utf-8", errors="ignore")
			console.print(f"[dim]flushCfg: {response.strip()}[/]")

		console.print("[green]Sensor reset complete[/]")

	except Exception as e:
		console.print(f"[red]Reset failed: {e}[/]")
		sys.exit(1)


if __name__ == "__main__":
	main()
