"""Radar configuration management."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SerialConfig:
	"""Serial port configuration."""
	cli_port: str = "/dev/ttyUSB0"
	data_port: str = "/dev/ttyUSB1"
	cli_baud: int = 115200
	data_baud: int = 921600
	timeout: float = 1.0


@dataclass
class ProfileConfig:
	"""Chirp profile configuration."""
	profile_id: int = 0
	start_freq_ghz: float = 60.0
	idle_time_us: float = 7.0
	adc_start_time_us: float = 6.0
	ramp_end_time_us: float = 60.0
	tx_power: int = 0
	tx_phase_shift: int = 0
	freq_slope_mhz_us: float = 66.67
	tx_start_time_us: float = 0.0
	adc_samples: int = 256
	sample_rate_ksps: int = 10000
	hp_corner_freq1: int = 0
	hp_corner_freq2: int = 0
	rx_gain_db: int = 30


@dataclass
class FrameConfig:
	"""Frame timing configuration."""
	chirp_start_idx: int = 0
	chirp_end_idx: int = 0
	num_loops: int = 64
	num_frames: int = 0
	frame_period_ms: float = 50.0
	trigger_select: int = 1
	trigger_delay_us: float = 0.0


@dataclass
class ChirpConfig:
	"""Complete radar configuration."""
	profile: ProfileConfig = field(default_factory=ProfileConfig)
	frame: FrameConfig = field(default_factory=FrameConfig)

	@property
	def range_resolution(self) -> float:
		c = 3e8
		bandwidth = self.profile.freq_slope_mhz_us * self.profile.ramp_end_time_us * 1e6
		return c / (2 * bandwidth) if bandwidth > 0 else 0

	@property
	def max_range(self) -> float:
		c = 3e8
		sample_rate = self.profile.sample_rate_ksps * 1e3
		bandwidth = self.profile.freq_slope_mhz_us * 1e12
		return (sample_rate * c) / (2 * bandwidth) if bandwidth > 0 else 0

	@property
	def velocity_resolution(self) -> float:
		c = 3e8
		freq = self.profile.start_freq_ghz * 1e9
		frame_time = self.frame.frame_period_ms * 1e-3
		num_chirps = self.frame.num_loops
		return c / (2 * freq * frame_time * num_chirps) if freq > 0 and num_chirps > 0 else 0

	def to_commands(self) -> list[str]:
		"""Generate CLI commands for this configuration.

		Does NOT include sensorStart - caller should use sensor.start() after configure().
		"""
		p = self.profile
		f = self.frame

		commands = [
			"sensorStop",
			"flushCfg",
			"dfeDataOutputMode 1",
			"channelCfg 15 7 0",
			"adcCfg 2 1",
			"adcbufCfg -1 0 1 1 1",
			"lowPower 0 0",
			f"profileCfg {p.profile_id} {p.start_freq_ghz} {p.idle_time_us} {p.adc_start_time_us} "
			f"{p.ramp_end_time_us} {p.tx_power} {p.tx_phase_shift} {p.freq_slope_mhz_us} "
			f"{p.tx_start_time_us} {p.adc_samples} {p.sample_rate_ksps} {p.hp_corner_freq1} "
			f"{p.hp_corner_freq2} {p.rx_gain_db}",
			# 3 chirp configs for TX antennas (IWR6843 has 3 TX)
			"chirpCfg 0 0 0 0 0 0 0 1",
			"chirpCfg 1 1 0 0 0 0 0 2",
			"chirpCfg 2 2 0 0 0 0 0 4",
			f"frameCfg 0 2 {f.num_loops} {f.num_frames} "
			f"{f.frame_period_ms} {f.trigger_select} {f.trigger_delay_us}",
			"guiMonitor -1 1 1 1 0 0 1",
			"cfarCfg -1 0 2 8 4 3 0 15.0 0",
			"cfarCfg -1 1 0 4 2 3 1 15.0 0",
			"multiObjBeamForming -1 1 0.5",
			"calibDcRangeSig -1 0 -5 8 256",
			"clutterRemoval -1 0",
			"compRangeBiasAndRxChanPhase 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
			"measureRangeBiasAndRxChanPhase 0 1. 0.2",
			"aoaFovCfg -1 -90 90 -90 90",
			"cfarFovCfg -1 0 0.25 15",
			"cfarFovCfg -1 1 -7.06 12",
			"extendedMaxVelocity -1 0",
			"CQRxSatMonitor 0 3 11 121 0",
			"CQSigImgMonitor 0 127 8",
			"analogMonitor 0 0",
			"lvdsStreamCfg -1 0 0 0",
			"bpmCfg -1 0 0 1",
			"calibData 0 0 0",
		]
		return commands


def create_vital_signs_config() -> ChirpConfig:
	"""Create configuration optimized for vital signs detection."""
	return ChirpConfig(
		profile=ProfileConfig(
			start_freq_ghz=60.0,
			idle_time_us=7.0,
			ramp_end_time_us=60.0,
			freq_slope_mhz_us=66.67,
			adc_samples=256,
			sample_rate_ksps=10000,
			rx_gain_db=30,
		),
		frame=FrameConfig(
			num_loops=64,
			frame_period_ms=50.0,
		),
	)


def load_config_file(path: Path | str) -> list[str]:
	"""Load configuration commands from a .cfg file."""
	path = Path(path)
	if not path.exists():
		raise FileNotFoundError(f"Config file not found: {path}")

	commands = []
	with open(path) as f:
		for line in f:
			line = line.strip()
			if line and not line.startswith("%"):
				commands.append(line)
	return commands
