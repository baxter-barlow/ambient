"""Chirp configuration for TI IWR6843AOPEVM."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ProfileConfig:
	profile_id: int = 0
	start_freq_ghz: float = 60.0
	idle_time_us: float = 10.0
	adc_start_time_us: float = 7.0
	ramp_end_time_us: float = 57.14
	tx_out_power: int = 0
	tx_phase_shifter: int = 0
	freq_slope_mhz_us: float = 70.0
	tx_start_time_us: float = 1.0
	num_adc_samples: int = 256
	dig_out_sample_rate_ksps: int = 10000
	hpf_corner_freq1: int = 0
	hpf_corner_freq2: int = 0
	rx_gain_db: int = 30


@dataclass
class FrameConfig:
	chirp_start_idx: int = 0
	chirp_end_idx: int = 2
	num_loops: int = 64
	num_frames: int = 0  # 0 = infinite
	frame_period_ms: float = 100.0
	trigger_select: int = 1
	frame_trigger_delay: float = 0.0


@dataclass
class ChirpConfig:
	rx_channel_mask: int = 15  # all 4 RX
	tx_channel_mask: int = 7   # all 3 TX
	adc_bits: int = 16
	adc_format: int = 1  # complex
	profile: ProfileConfig = field(default_factory=ProfileConfig)
	frame: FrameConfig = field(default_factory=FrameConfig)
	range_fft_size: int = 256
	doppler_fft_size: int = 64
	clutter_removal: bool = True

	@property
	def range_resolution_m(self) -> float:
		c = 3e8
		bandwidth = self.profile.freq_slope_mhz_us * 1e6 * self.profile.ramp_end_time_us
		return c / (2 * bandwidth)

	@property
	def max_range_m(self) -> float:
		return self.range_resolution_m * self.profile.num_adc_samples / 2

	@property
	def velocity_resolution_mps(self) -> float:
		c = 3e8
		wavelength = c / (self.profile.start_freq_ghz * 1e9)
		chirp_time = (self.profile.idle_time_us + self.profile.ramp_end_time_us) * 1e-6
		chirp_time *= bin(self.tx_channel_mask).count("1")
		return wavelength / (2 * self.frame.num_loops * chirp_time)

	@property
	def max_velocity_mps(self) -> float:
		return self.velocity_resolution_mps * self.frame.num_loops / 2

	def to_commands(self) -> list[str]:
		p = self.profile
		f = self.frame
		return [
			"sensorStop",
			"flushCfg",
			"dfeDataOutputMode 1",
			f"channelCfg {self.rx_channel_mask} {self.tx_channel_mask} 0",
			f"adcCfg {self.adc_bits // 8} {self.adc_format}",
			"adcbufCfg -1 0 1 1 1",
			f"profileCfg {p.profile_id} {p.start_freq_ghz} {p.idle_time_us} "
			f"{p.adc_start_time_us} {p.ramp_end_time_us} {p.tx_out_power} "
			f"{p.tx_phase_shifter} {p.freq_slope_mhz_us} {p.tx_start_time_us} "
			f"{p.num_adc_samples} {p.dig_out_sample_rate_ksps} {p.hpf_corner_freq1} "
			f"{p.hpf_corner_freq2} {p.rx_gain_db}",
			"chirpCfg 0 0 0 0 0 0 0 1",
			"chirpCfg 1 1 0 0 0 0 0 2",
			"chirpCfg 2 2 0 0 0 0 0 4",
			f"frameCfg {f.chirp_start_idx} {f.chirp_end_idx} {f.num_loops} "
			f"{f.num_frames} {f.frame_period_ms} {f.trigger_select} {f.frame_trigger_delay}",
			"lowPower 0 0",
			"guiMonitor -1 1 0 0 0 0 0",
			"cfarCfg -1 0 2 8 4 3 0 15 0",
			"cfarCfg -1 1 0 4 2 3 1 15 1",
			"multiObjBeamForming -1 1 0.5",
			f"clutterRemoval -1 {1 if self.clutter_removal else 0}",
			"calibDcRangeSig -1 0 -5 8 256",
			"extendedMaxVelocity -1 0",
			"lvdsStreamCfg -1 0 0 0",
			"compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
			"measureRangeBiasAndRxChanPhase 0 1.5 0.2",
			"CQRxSatMonitor 0 3 5 121 0",
			"CQSigImgMonitor 0 123 8",
			"analogMonitor 0 0",
			"aoaFovCfg -1 -90 90 -90 90",
			"cfarFovCfg -1 0 0 17.30",
			"cfarFovCfg -1 1 -6.2 6.20",
			"calibData 0 0 0",
			"sensorStart",
		]


def load_config(path: str | Path) -> list[str]:
	"""Load CLI commands from .cfg file."""
	path = Path(path)
	if not path.exists():
		raise FileNotFoundError(f"Config not found: {path}")

	commands = []
	with open(path) as f:
		for line in f:
			line = line.strip()
			if line and not line.startswith("%") and not line.startswith("#"):
				commands.append(line)

	logger.info("config_loaded", path=str(path), commands=len(commands))
	return commands


def create_vital_signs_config(
	frame_rate_hz: float = 20.0,
	max_range_m: float = 2.0,
	clutter_removal: bool = True,
) -> ChirpConfig:
	"""Create config optimized for vital signs detection."""
	config = ChirpConfig(
		profile=ProfileConfig(
			start_freq_ghz=60.0,
			idle_time_us=10.0,
			adc_start_time_us=7.0,
			ramp_end_time_us=57.14,
			freq_slope_mhz_us=70.0,
			num_adc_samples=256,
			dig_out_sample_rate_ksps=10000,
			rx_gain_db=158,
		),
		frame=FrameConfig(
			num_loops=64,
			frame_period_ms=1000.0 / frame_rate_hz,
		),
		clutter_removal=clutter_removal,
	)
	logger.info("vital_signs_config", frame_rate=frame_rate_hz, range_res=config.range_resolution_m)
	return config
