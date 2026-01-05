"""Real-time plotting for radar and vital signs."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

if TYPE_CHECKING:
	from matplotlib.axes import Axes
	from matplotlib.figure import Figure
	from ambient.vitals.extractor import VitalSigns
	from ambient.sensor.frame import RadarFrame

logger = structlog.get_logger(__name__)


@dataclass
class PlotConfig:
	vitals_window_seconds: float = 60.0
	waveform_window_seconds: float = 10.0
	update_interval_ms: int = 100
	hr_min_bpm: float = 40.0
	hr_max_bpm: float = 120.0
	rr_min_bpm: float = 6.0
	rr_max_bpm: float = 30.0
	hr_color: str = "#e74c3c"
	rr_color: str = "#3498db"
	phase_color: str = "#2ecc71"


class RealtimePlotter:
	"""Live radar data visualization: range profile, scatter, range-Doppler."""

	def __init__(self, config: PlotConfig | None = None) -> None:
		self.config = config or PlotConfig()
		self._fig: Figure | None = None
		self._axes: dict[str, Axes] = {}
		self._lines: dict[str, Any] = {}
		self._initialized = False

	def setup(self, figsize: tuple[int, int] = (12, 8)) -> None:
		import matplotlib.pyplot as plt

		self._fig, axes = plt.subplots(2, 2, figsize=figsize)
		self._fig.suptitle("Radar Monitor")

		self._axes["range"] = axes[0, 0]
		self._axes["range"].set_title("Range Profile")
		self._axes["range"].set_xlabel("Range Bin")
		self._axes["range"].set_ylabel("Magnitude")
		self._lines["range"], = self._axes["range"].plot([], [], "b-")

		self._axes["scatter"] = axes[0, 1]
		self._axes["scatter"].set_title("Detected Points")
		self._axes["scatter"].set_xlabel("X (m)")
		self._axes["scatter"].set_ylabel("Y (m)")
		self._axes["scatter"].set_xlim(-3, 3)
		self._axes["scatter"].set_ylim(0, 5)
		self._axes["scatter"].set_aspect("equal")
		self._lines["scatter"] = self._axes["scatter"].scatter([], [], c="r", s=50)

		self._axes["phase"] = axes[1, 0]
		self._axes["phase"].set_title("Phase")
		self._axes["phase"].set_xlabel("Sample")
		self._axes["phase"].set_ylabel("Phase (rad)")
		self._lines["phase"], = self._axes["phase"].plot([], [], self.config.phase_color)

		self._axes["rd"] = axes[1, 1]
		self._axes["rd"].set_title("Range-Doppler")
		self._axes["rd"].set_xlabel("Doppler Bin")
		self._axes["rd"].set_ylabel("Range Bin")
		self._lines["rd"] = self._axes["rd"].imshow(np.zeros((64, 64)), aspect="auto", cmap="viridis", origin="lower")

		plt.tight_layout()
		self._initialized = True
		logger.info("realtime_plotter_setup")

	def update(self, frame: RadarFrame) -> None:
		if not self._initialized:
			self.setup()
		import matplotlib.pyplot as plt

		if frame.range_profile is not None:
			self._lines["range"].set_data(np.arange(len(frame.range_profile)), frame.range_profile)
			self._axes["range"].relim()
			self._axes["range"].autoscale_view()

		if frame.detected_points:
			x = [p.x for p in frame.detected_points]
			y = [p.y for p in frame.detected_points]
			self._lines["scatter"].set_offsets(np.column_stack([x, y]))

		if frame.range_doppler_heatmap is not None:
			rd = frame.range_doppler_heatmap
			if rd.ndim == 1:
				size = int(np.sqrt(len(rd)))
				rd = rd[:size * size].reshape(size, size)
			self._lines["rd"].set_data(rd)
			self._lines["rd"].set_clim(rd.min(), rd.max())

		self._fig.canvas.draw_idle()
		self._fig.canvas.flush_events()

	def show(self) -> None:
		import matplotlib.pyplot as plt
		if self._fig:
			plt.show()

	def close(self) -> None:
		import matplotlib.pyplot as plt
		if self._fig:
			plt.close(self._fig)
			self._fig = None
			self._initialized = False


class VitalsPlotter:
	"""Live vital signs visualization: HR, RR, phase waveform."""

	def __init__(self, config: PlotConfig | None = None) -> None:
		self.config = config or PlotConfig()
		self._fig: Figure | None = None
		self._axes: dict[str, Axes] = {}
		self._lines: dict[str, Any] = {}

		buf_size = int(self.config.vitals_window_seconds * 10)
		self._hr_buffer: deque[float] = deque(maxlen=buf_size)
		self._rr_buffer: deque[float] = deque(maxlen=buf_size)
		self._time_buffer: deque[float] = deque(maxlen=buf_size)

		wave_size = int(self.config.waveform_window_seconds * 20)
		self._phase_buffer: deque[float] = deque(maxlen=wave_size)

		self._initialized = False
		self._start_time: float | None = None

	def setup(self, figsize: tuple[int, int] = (12, 8)) -> None:
		import matplotlib.pyplot as plt

		self._fig, axes = plt.subplots(3, 1, figsize=figsize)
		self._fig.suptitle("Vital Signs")

		self._axes["hr"] = axes[0]
		self._axes["hr"].set_title("Heart Rate")
		self._axes["hr"].set_ylabel("BPM")
		self._axes["hr"].set_ylim(self.config.hr_min_bpm, self.config.hr_max_bpm)
		self._lines["hr"], = self._axes["hr"].plot([], [], self.config.hr_color, lw=2)
		self._axes["hr"].grid(True, alpha=0.3)

		self._axes["rr"] = axes[1]
		self._axes["rr"].set_title("Respiratory Rate")
		self._axes["rr"].set_ylabel("Breaths/min")
		self._axes["rr"].set_ylim(self.config.rr_min_bpm, self.config.rr_max_bpm)
		self._lines["rr"], = self._axes["rr"].plot([], [], self.config.rr_color, lw=2)
		self._axes["rr"].grid(True, alpha=0.3)

		self._axes["phase"] = axes[2]
		self._axes["phase"].set_title("Phase Signal")
		self._axes["phase"].set_xlabel("Time (s)")
		self._axes["phase"].set_ylabel("Phase (rad)")
		self._lines["phase"], = self._axes["phase"].plot([], [], self.config.phase_color, lw=1)
		self._axes["phase"].grid(True, alpha=0.3)

		plt.tight_layout()
		self._initialized = True
		logger.info("vitals_plotter_setup")

	def update(self, vitals: VitalSigns) -> None:
		if not self._initialized:
			self.setup()

		if self._start_time is None:
			self._start_time = vitals.timestamp

		t = vitals.timestamp - self._start_time
		self._time_buffer.append(t)
		self._hr_buffer.append(vitals.heart_rate_bpm if vitals.heart_rate_bpm else np.nan)
		self._rr_buffer.append(vitals.respiratory_rate_bpm if vitals.respiratory_rate_bpm else np.nan)

		if vitals.phase_signal is not None:
			for p in vitals.phase_signal[-10:]:
				self._phase_buffer.append(p)

		times = list(self._time_buffer)
		self._lines["hr"].set_data(times, list(self._hr_buffer))
		self._axes["hr"].set_xlim(max(0, t - self.config.vitals_window_seconds), t)

		self._lines["rr"].set_data(times, list(self._rr_buffer))
		self._axes["rr"].set_xlim(max(0, t - self.config.vitals_window_seconds), t)

		if self._phase_buffer:
			pt = np.linspace(t - len(self._phase_buffer) / 20, t, len(self._phase_buffer))
			self._lines["phase"].set_data(pt, list(self._phase_buffer))
			self._axes["phase"].relim()
			self._axes["phase"].autoscale_view()

		if vitals.heart_rate_bpm:
			self._axes["hr"].set_title(f"Heart Rate: {vitals.heart_rate_bpm:.0f} BPM")
		if vitals.respiratory_rate_bpm:
			self._axes["rr"].set_title(f"Respiratory Rate: {vitals.respiratory_rate_bpm:.0f} BPM")

		self._fig.canvas.draw_idle()
		self._fig.canvas.flush_events()

	def show(self) -> None:
		import matplotlib.pyplot as plt
		if self._fig:
			plt.show()

	def close(self) -> None:
		import matplotlib.pyplot as plt
		if self._fig:
			plt.close(self._fig)
			self._fig = None
			self._initialized = False

	def reset(self) -> None:
		self._hr_buffer.clear()
		self._rr_buffer.clear()
		self._time_buffer.clear()
		self._phase_buffer.clear()
		self._start_time = None
