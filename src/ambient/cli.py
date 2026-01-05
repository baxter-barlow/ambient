"""Command-line interface."""

from __future__ import annotations

import sys
import time
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
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig
	from ambient.processing import ProcessingPipeline
	from ambient.vitals import VitalsExtractor
	from ambient.storage import HDF5Writer, ParquetWriter

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
	from ambient.sensor import RadarSensor
	from ambient.sensor.config import SerialConfig
	from ambient.processing import ProcessingPipeline
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

		for k, v in {**version, **status}.items():
			if v:
				t.add_row(k, str(v))

		console.print(t)
	except Exception as e:
		console.print(f"[red]Error: {e}[/]")
		sys.exit(1)
	finally:
		sensor.disconnect()


if __name__ == "__main__":
	main()
