"""Full TI mmWave config file parser with structured dataclasses.

Parses TI Visualizer-compatible .cfg files into structured Python objects.
Supports all standard TI CLI commands for IWR6843/xWR6843 devices.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChannelConfig:
	"""Channel configuration (channelCfg)."""
	rx_channel_en: int = 15  # Bitmask for RX channels (15 = all 4)
	tx_channel_en: int = 7   # Bitmask for TX channels (7 = all 3)
	cascading: int = 0

	@classmethod
	def from_args(cls, args: list[str]) -> ChannelConfig:
		return cls(
			rx_channel_en=int(args[0]) if len(args) > 0 else 15,
			tx_channel_en=int(args[1]) if len(args) > 1 else 7,
			cascading=int(args[2]) if len(args) > 2 else 0,
		)

	def to_command(self) -> str:
		return f"channelCfg {self.rx_channel_en} {self.tx_channel_en} {self.cascading}"

	@property
	def num_rx_channels(self) -> int:
		return bin(self.rx_channel_en).count("1")

	@property
	def num_tx_channels(self) -> int:
		return bin(self.tx_channel_en).count("1")


@dataclass
class ADCConfig:
	"""ADC configuration (adcCfg)."""
	num_adc_bits: int = 2      # 0=12-bit, 1=14-bit, 2=16-bit
	adc_output_fmt: int = 1    # 0=real, 1=complex 1x, 2=complex 2x

	@classmethod
	def from_args(cls, args: list[str]) -> ADCConfig:
		return cls(
			num_adc_bits=int(args[0]) if len(args) > 0 else 2,
			adc_output_fmt=int(args[1]) if len(args) > 1 else 1,
		)

	def to_command(self) -> str:
		return f"adcCfg {self.num_adc_bits} {self.adc_output_fmt}"


@dataclass
class ProfileCfg:
	"""Chirp profile configuration (profileCfg)."""
	profile_id: int = 0
	start_freq_ghz: float = 60.0
	idle_time_us: float = 7.0
	adc_start_time_us: float = 3.0
	ramp_end_time_us: float = 39.0
	tx_output_power: int = 0
	tx_phase_shifter: int = 0
	freq_slope_mhz_us: float = 100.0
	tx_start_time_us: float = 1.0
	adc_samples: int = 256
	sample_rate_ksps: int = 7200
	hp_filter_corner_freq1: int = 0
	hp_filter_corner_freq2: int = 0
	rx_gain_db: int = 30

	@classmethod
	def from_args(cls, args: list[str]) -> ProfileCfg:
		return cls(
			profile_id=int(args[0]) if len(args) > 0 else 0,
			start_freq_ghz=float(args[1]) if len(args) > 1 else 60.0,
			idle_time_us=float(args[2]) if len(args) > 2 else 7.0,
			adc_start_time_us=float(args[3]) if len(args) > 3 else 3.0,
			ramp_end_time_us=float(args[4]) if len(args) > 4 else 39.0,
			tx_output_power=int(args[5]) if len(args) > 5 else 0,
			tx_phase_shifter=int(args[6]) if len(args) > 6 else 0,
			freq_slope_mhz_us=float(args[7]) if len(args) > 7 else 100.0,
			tx_start_time_us=float(args[8]) if len(args) > 8 else 1.0,
			adc_samples=int(args[9]) if len(args) > 9 else 256,
			sample_rate_ksps=int(args[10]) if len(args) > 10 else 7200,
			hp_filter_corner_freq1=int(args[11]) if len(args) > 11 else 0,
			hp_filter_corner_freq2=int(args[12]) if len(args) > 12 else 0,
			rx_gain_db=int(args[13]) if len(args) > 13 else 30,
		)

	def to_command(self) -> str:
		return (
			f"profileCfg {self.profile_id} {self.start_freq_ghz} {self.idle_time_us} "
			f"{self.adc_start_time_us} {self.ramp_end_time_us} {self.tx_output_power} "
			f"{self.tx_phase_shifter} {self.freq_slope_mhz_us} {self.tx_start_time_us} "
			f"{self.adc_samples} {self.sample_rate_ksps} {self.hp_filter_corner_freq1} "
			f"{self.hp_filter_corner_freq2} {self.rx_gain_db}"
		)

	@property
	def bandwidth_mhz(self) -> float:
		"""Total chirp bandwidth in MHz."""
		return self.freq_slope_mhz_us * self.ramp_end_time_us

	@property
	def wavelength_m(self) -> float:
		"""Wavelength at start frequency in meters."""
		c = 3e8
		return c / (self.start_freq_ghz * 1e9)


@dataclass
class ChirpCfg:
	"""Individual chirp configuration (chirpCfg)."""
	chirp_start_idx: int = 0
	chirp_end_idx: int = 0
	profile_id: int = 0
	start_freq_var_hz: int = 0
	freq_slope_var_khz_us: int = 0
	idle_time_var_us: int = 0
	adc_start_time_var_us: int = 0
	tx_enable_mask: int = 1

	@classmethod
	def from_args(cls, args: list[str]) -> ChirpCfg:
		return cls(
			chirp_start_idx=int(args[0]) if len(args) > 0 else 0,
			chirp_end_idx=int(args[1]) if len(args) > 1 else 0,
			profile_id=int(args[2]) if len(args) > 2 else 0,
			start_freq_var_hz=int(args[3]) if len(args) > 3 else 0,
			freq_slope_var_khz_us=int(args[4]) if len(args) > 4 else 0,
			idle_time_var_us=int(args[5]) if len(args) > 5 else 0,
			adc_start_time_var_us=int(args[6]) if len(args) > 6 else 0,
			tx_enable_mask=int(args[7]) if len(args) > 7 else 1,
		)

	def to_command(self) -> str:
		return (
			f"chirpCfg {self.chirp_start_idx} {self.chirp_end_idx} {self.profile_id} "
			f"{self.start_freq_var_hz} {self.freq_slope_var_khz_us} {self.idle_time_var_us} "
			f"{self.adc_start_time_var_us} {self.tx_enable_mask}"
		)


@dataclass
class FrameCfg:
	"""Frame configuration (frameCfg)."""
	chirp_start_idx: int = 0
	chirp_end_idx: int = 2
	num_loops: int = 32
	num_frames: int = 0          # 0 = infinite
	frame_period_ms: float = 50.0
	trigger_select: int = 1      # 1 = software trigger
	trigger_delay_us: float = 0.0

	@classmethod
	def from_args(cls, args: list[str]) -> FrameCfg:
		return cls(
			chirp_start_idx=int(args[0]) if len(args) > 0 else 0,
			chirp_end_idx=int(args[1]) if len(args) > 1 else 2,
			num_loops=int(args[2]) if len(args) > 2 else 32,
			num_frames=int(args[3]) if len(args) > 3 else 0,
			frame_period_ms=float(args[4]) if len(args) > 4 else 50.0,
			trigger_select=int(args[5]) if len(args) > 5 else 1,
			trigger_delay_us=float(args[6]) if len(args) > 6 else 0.0,
		)

	def to_command(self) -> str:
		return (
			f"frameCfg {self.chirp_start_idx} {self.chirp_end_idx} {self.num_loops} "
			f"{self.num_frames} {self.frame_period_ms} {self.trigger_select} {self.trigger_delay_us}"
		)

	@property
	def num_chirps_per_frame(self) -> int:
		"""Number of chirps per frame."""
		return (self.chirp_end_idx - self.chirp_start_idx + 1) * self.num_loops

	@property
	def frame_rate_hz(self) -> float:
		"""Frame rate in Hz."""
		return 1000.0 / self.frame_period_ms if self.frame_period_ms > 0 else 0


@dataclass
class GuiMonitorCfg:
	"""GUI monitor configuration (guiMonitor)."""
	subframe_idx: int = -1
	detected_objects: int = 1
	log_mag_range: int = 1
	noise_profile: int = 1
	range_azimuth_heatmap: int = 0
	range_doppler_heatmap: int = 0
	stats_info: int = 1

	@classmethod
	def from_args(cls, args: list[str]) -> GuiMonitorCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			detected_objects=int(args[1]) if len(args) > 1 else 1,
			log_mag_range=int(args[2]) if len(args) > 2 else 1,
			noise_profile=int(args[3]) if len(args) > 3 else 1,
			range_azimuth_heatmap=int(args[4]) if len(args) > 4 else 0,
			range_doppler_heatmap=int(args[5]) if len(args) > 5 else 0,
			stats_info=int(args[6]) if len(args) > 6 else 1,
		)

	def to_command(self) -> str:
		return (
			f"guiMonitor {self.subframe_idx} {self.detected_objects} {self.log_mag_range} "
			f"{self.noise_profile} {self.range_azimuth_heatmap} {self.range_doppler_heatmap} "
			f"{self.stats_info}"
		)


@dataclass
class CfarCfg:
	"""CFAR configuration (cfarCfg)."""
	subframe_idx: int = -1
	proc_direction: int = 0      # 0=range, 1=Doppler
	mode: int = 2                # 0=CA, 1=CAGO, 2=CASO
	noise_win: int = 8
	guard_len: int = 4
	div_shift: int = 3
	cyclic_mode: int = 0
	threshold_scale_db: float = 15.0
	peak_grouping: int = 0

	@classmethod
	def from_args(cls, args: list[str]) -> CfarCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			proc_direction=int(args[1]) if len(args) > 1 else 0,
			mode=int(args[2]) if len(args) > 2 else 2,
			noise_win=int(args[3]) if len(args) > 3 else 8,
			guard_len=int(args[4]) if len(args) > 4 else 4,
			div_shift=int(args[5]) if len(args) > 5 else 3,
			cyclic_mode=int(args[6]) if len(args) > 6 else 0,
			threshold_scale_db=float(args[7]) if len(args) > 7 else 15.0,
			peak_grouping=int(args[8]) if len(args) > 8 else 0,
		)

	def to_command(self) -> str:
		return (
			f"cfarCfg {self.subframe_idx} {self.proc_direction} {self.mode} {self.noise_win} "
			f"{self.guard_len} {self.div_shift} {self.cyclic_mode} {self.threshold_scale_db} "
			f"{self.peak_grouping}"
		)


@dataclass
class AoaFovCfg:
	"""Angle of arrival field of view configuration (aoaFovCfg)."""
	subframe_idx: int = -1
	min_azimuth_deg: float = -90.0
	max_azimuth_deg: float = 90.0
	min_elevation_deg: float = -90.0
	max_elevation_deg: float = 90.0

	@classmethod
	def from_args(cls, args: list[str]) -> AoaFovCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			min_azimuth_deg=float(args[1]) if len(args) > 1 else -90.0,
			max_azimuth_deg=float(args[2]) if len(args) > 2 else 90.0,
			min_elevation_deg=float(args[3]) if len(args) > 3 else -90.0,
			max_elevation_deg=float(args[4]) if len(args) > 4 else 90.0,
		)

	def to_command(self) -> str:
		return (
			f"aoaFovCfg {self.subframe_idx} {self.min_azimuth_deg} {self.max_azimuth_deg} "
			f"{self.min_elevation_deg} {self.max_elevation_deg}"
		)


@dataclass
class CfarFovCfg:
	"""CFAR field of view configuration (cfarFovCfg)."""
	subframe_idx: int = -1
	proc_direction: int = 0      # 0=range, 1=Doppler
	min_value: float = 0.25
	max_value: float = 15.0

	@classmethod
	def from_args(cls, args: list[str]) -> CfarFovCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			proc_direction=int(args[1]) if len(args) > 1 else 0,
			min_value=float(args[2]) if len(args) > 2 else 0.25,
			max_value=float(args[3]) if len(args) > 3 else 15.0,
		)

	def to_command(self) -> str:
		return f"cfarFovCfg {self.subframe_idx} {self.proc_direction} {self.min_value} {self.max_value}"


@dataclass
class ClutterRemovalCfg:
	"""Clutter removal configuration (clutterRemoval)."""
	subframe_idx: int = -1
	enabled: int = 0

	@classmethod
	def from_args(cls, args: list[str]) -> ClutterRemovalCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			enabled=int(args[1]) if len(args) > 1 else 0,
		)

	def to_command(self) -> str:
		return f"clutterRemoval {self.subframe_idx} {self.enabled}"


@dataclass
class MultiObjBeamFormingCfg:
	"""Multi-object beam forming configuration."""
	subframe_idx: int = -1
	enabled: int = 1
	threshold: float = 0.5

	@classmethod
	def from_args(cls, args: list[str]) -> MultiObjBeamFormingCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			enabled=int(args[1]) if len(args) > 1 else 1,
			threshold=float(args[2]) if len(args) > 2 else 0.5,
		)

	def to_command(self) -> str:
		return f"multiObjBeamForming {self.subframe_idx} {self.enabled} {self.threshold}"


@dataclass
class ExtendedMaxVelocityCfg:
	"""Extended max velocity configuration."""
	subframe_idx: int = -1
	enabled: int = 0

	@classmethod
	def from_args(cls, args: list[str]) -> ExtendedMaxVelocityCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			enabled=int(args[1]) if len(args) > 1 else 0,
		)

	def to_command(self) -> str:
		return f"extendedMaxVelocity {self.subframe_idx} {self.enabled}"


@dataclass
class BpmCfg:
	"""BPM (Binary Phase Modulation) configuration."""
	subframe_idx: int = -1
	enabled: int = 0
	chirp0_idx: int = 0
	chirp1_idx: int = 1

	@classmethod
	def from_args(cls, args: list[str]) -> BpmCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			enabled=int(args[1]) if len(args) > 1 else 0,
			chirp0_idx=int(args[2]) if len(args) > 2 else 0,
			chirp1_idx=int(args[3]) if len(args) > 3 else 1,
		)

	def to_command(self) -> str:
		return f"bpmCfg {self.subframe_idx} {self.enabled} {self.chirp0_idx} {self.chirp1_idx}"


@dataclass
class LvdsStreamCfg:
	"""LVDS streaming configuration."""
	subframe_idx: int = -1
	enable_header: int = 0
	data_fmt: int = 0
	enable_sw: int = 0

	@classmethod
	def from_args(cls, args: list[str]) -> LvdsStreamCfg:
		return cls(
			subframe_idx=int(args[0]) if len(args) > 0 else -1,
			enable_header=int(args[1]) if len(args) > 1 else 0,
			data_fmt=int(args[2]) if len(args) > 2 else 0,
			enable_sw=int(args[3]) if len(args) > 3 else 0,
		)

	def to_command(self) -> str:
		return f"lvdsStreamCfg {self.subframe_idx} {self.enable_header} {self.data_fmt} {self.enable_sw}"


@dataclass
class CompRangeBiasCfg:
	"""Range bias and RX channel phase compensation."""
	range_bias: float = 0.0
	rx_phase_comp: list[float] = field(default_factory=lambda: [1.0, 0.0] * 12)

	@classmethod
	def from_args(cls, args: list[str]) -> CompRangeBiasCfg:
		range_bias = float(args[0]) if len(args) > 0 else 0.0
		rx_phase_comp = [float(x) for x in args[1:]] if len(args) > 1 else [1.0, 0.0] * 12
		return cls(range_bias=range_bias, rx_phase_comp=rx_phase_comp)

	def to_command(self) -> str:
		phase_str = " ".join(str(x) for x in self.rx_phase_comp)
		return f"compRangeBiasAndRxChanPhase {self.range_bias} {phase_str}"


@dataclass
class VitalSignsCfg:
	"""Vital signs specific configuration (vitalSignsCfg)."""
	range_start_m: float = 0.3
	range_end_m: float = 1.5
	win_len_breath: int = 20
	win_len_heart: int = 20
	enabled: int = 1

	@classmethod
	def from_args(cls, args: list[str]) -> VitalSignsCfg:
		return cls(
			range_start_m=float(args[0]) if len(args) > 0 else 0.3,
			range_end_m=float(args[1]) if len(args) > 1 else 1.5,
			win_len_breath=int(args[2]) if len(args) > 2 else 20,
			win_len_heart=int(args[3]) if len(args) > 3 else 20,
			enabled=int(args[4]) if len(args) > 4 else 1,
		)

	def to_command(self) -> str:
		return (
			f"vitalSignsCfg {self.range_start_m} {self.range_end_m} "
			f"{self.win_len_breath} {self.win_len_heart} {self.enabled}"
		)


@dataclass
class ParsedConfig:
	"""Complete parsed radar configuration."""
	channel: ChannelConfig = field(default_factory=ChannelConfig)
	adc: ADCConfig = field(default_factory=ADCConfig)
	profile: ProfileCfg = field(default_factory=ProfileCfg)
	chirps: list[ChirpCfg] = field(default_factory=list)
	frame: FrameCfg = field(default_factory=FrameCfg)
	gui_monitor: GuiMonitorCfg = field(default_factory=GuiMonitorCfg)
	cfar_range: CfarCfg = field(default_factory=CfarCfg)
	cfar_doppler: CfarCfg | None = None
	aoa_fov: AoaFovCfg = field(default_factory=AoaFovCfg)
	cfar_fov_range: CfarFovCfg | None = None
	cfar_fov_doppler: CfarFovCfg | None = None
	clutter_removal: ClutterRemovalCfg = field(default_factory=ClutterRemovalCfg)
	multi_obj_beam_forming: MultiObjBeamFormingCfg = field(default_factory=MultiObjBeamFormingCfg)
	extended_max_velocity: ExtendedMaxVelocityCfg = field(default_factory=ExtendedMaxVelocityCfg)
	bpm: BpmCfg = field(default_factory=BpmCfg)
	lvds_stream: LvdsStreamCfg = field(default_factory=LvdsStreamCfg)
	comp_range_bias: CompRangeBiasCfg = field(default_factory=CompRangeBiasCfg)
	vital_signs: VitalSignsCfg | None = None
	dfe_output_mode: int = 1
	raw_commands: list[str] = field(default_factory=list)

	# Computed properties
	@property
	def range_resolution_m(self) -> float:
		"""Range resolution in meters."""
		c = 3e8
		bandwidth = self.profile.bandwidth_mhz * 1e6
		return c / (2 * bandwidth) if bandwidth > 0 else 0

	@property
	def max_range_m(self) -> float:
		"""Maximum unambiguous range in meters."""
		c = 3e8
		sample_rate = self.profile.sample_rate_ksps * 1e3
		slope = self.profile.freq_slope_mhz_us * 1e12  # Hz/s
		return (sample_rate * c) / (2 * slope) if slope > 0 else 0

	@property
	def velocity_resolution_mps(self) -> float:
		"""Velocity resolution in m/s."""
		wavelength = self.profile.wavelength_m
		num_chirps = self.frame.num_chirps_per_frame
		chirp_time = (self.profile.idle_time_us + self.profile.ramp_end_time_us) * 1e-6
		frame_time = chirp_time * num_chirps
		return wavelength / (2 * frame_time) if frame_time > 0 else 0

	@property
	def max_velocity_mps(self) -> float:
		"""Maximum unambiguous velocity in m/s."""
		wavelength = self.profile.wavelength_m
		chirp_time = (self.profile.idle_time_us + self.profile.ramp_end_time_us) * 1e-6
		num_tx = self.channel.num_tx_channels
		return wavelength / (4 * chirp_time * num_tx) if chirp_time > 0 and num_tx > 0 else 0

	@property
	def frame_rate_hz(self) -> float:
		"""Frame rate in Hz."""
		return self.frame.frame_rate_hz

	@property
	def num_range_bins(self) -> int:
		"""Number of range bins."""
		return self.profile.adc_samples

	@property
	def num_doppler_bins(self) -> int:
		"""Number of Doppler bins."""
		return self.frame.num_loops

	@property
	def num_virtual_antennas(self) -> int:
		"""Number of virtual antennas (MIMO)."""
		return self.channel.num_rx_channels * self.channel.num_tx_channels

	def to_commands(self) -> list[str]:
		"""Generate CLI commands from this configuration."""
		commands = [
			"sensorStop",
			"flushCfg",
			f"dfeDataOutputMode {self.dfe_output_mode}",
			self.channel.to_command(),
			self.adc.to_command(),
			"adcbufCfg -1 0 1 1 1",
			"lowPower 0 0",
			self.profile.to_command(),
		]

		for chirp in self.chirps:
			commands.append(chirp.to_command())

		commands.append(self.frame.to_command())
		commands.append(self.gui_monitor.to_command())
		commands.append(self.cfar_range.to_command())

		if self.cfar_doppler:
			commands.append(self.cfar_doppler.to_command())

		commands.append(self.multi_obj_beam_forming.to_command())
		commands.append("calibDcRangeSig -1 0 -5 8 256")
		commands.append(self.clutter_removal.to_command())
		commands.append(self.comp_range_bias.to_command())
		commands.append("measureRangeBiasAndRxChanPhase 0 1. 0.2")
		commands.append(self.aoa_fov.to_command())

		if self.cfar_fov_range:
			commands.append(self.cfar_fov_range.to_command())
		if self.cfar_fov_doppler:
			commands.append(self.cfar_fov_doppler.to_command())

		commands.append(self.extended_max_velocity.to_command())
		commands.append("CQRxSatMonitor 0 3 11 121 0")
		commands.append("CQSigImgMonitor 0 127 8")
		commands.append("analogMonitor 0 0")
		commands.append(self.lvds_stream.to_command())
		commands.append(self.bpm.to_command())
		commands.append("calibData 0 0 0")

		if self.vital_signs:
			commands.append(self.vital_signs.to_command())

		return commands

	def to_dict(self) -> dict[str, Any]:
		"""Convert to dictionary for JSON serialization."""
		return {
			"range_resolution_m": self.range_resolution_m,
			"max_range_m": self.max_range_m,
			"velocity_resolution_mps": self.velocity_resolution_mps,
			"max_velocity_mps": self.max_velocity_mps,
			"frame_rate_hz": self.frame_rate_hz,
			"num_range_bins": self.num_range_bins,
			"num_doppler_bins": self.num_doppler_bins,
			"num_virtual_antennas": self.num_virtual_antennas,
			"bandwidth_mhz": self.profile.bandwidth_mhz,
			"start_freq_ghz": self.profile.start_freq_ghz,
			"adc_samples": self.profile.adc_samples,
			"chirps_per_frame": self.frame.num_chirps_per_frame,
			"frame_period_ms": self.frame.frame_period_ms,
			"clutter_removal_enabled": bool(self.clutter_removal.enabled),
			"range_doppler_heatmap_enabled": bool(self.gui_monitor.range_doppler_heatmap),
			"range_azimuth_heatmap_enabled": bool(self.gui_monitor.range_azimuth_heatmap),
		}


class ConfigParser:
	"""Parser for TI mmWave .cfg files."""

	def __init__(self) -> None:
		self.config = ParsedConfig()

	def parse_file(self, path: Path | str) -> ParsedConfig:
		"""Parse a .cfg file and return structured configuration."""
		path = Path(path)
		if not path.exists():
			raise FileNotFoundError(f"Config file not found: {path}")

		with open(path) as f:
			content = f.read()

		return self.parse_content(content)

	def parse_content(self, content: str) -> ParsedConfig:
		"""Parse config file content and return structured configuration."""
		self.config = ParsedConfig()

		for line in content.splitlines():
			line = line.strip()
			# Skip empty lines and comments
			if not line or line.startswith("%") or line.startswith("#"):
				continue

			self.config.raw_commands.append(line)
			self._parse_command(line)

		return self.config

	def _parse_command(self, line: str) -> None:
		"""Parse a single CLI command."""
		parts = line.split()
		if not parts:
			return

		cmd = parts[0]
		args = parts[1:]

		if cmd == "channelCfg":
			self.config.channel = ChannelConfig.from_args(args)
		elif cmd == "adcCfg":
			self.config.adc = ADCConfig.from_args(args)
		elif cmd == "profileCfg":
			self.config.profile = ProfileCfg.from_args(args)
		elif cmd == "chirpCfg":
			self.config.chirps.append(ChirpCfg.from_args(args))
		elif cmd == "frameCfg":
			self.config.frame = FrameCfg.from_args(args)
		elif cmd == "guiMonitor":
			self.config.gui_monitor = GuiMonitorCfg.from_args(args)
		elif cmd == "cfarCfg":
			cfar = CfarCfg.from_args(args)
			if cfar.proc_direction == 0:
				self.config.cfar_range = cfar
			else:
				self.config.cfar_doppler = cfar
		elif cmd == "aoaFovCfg":
			self.config.aoa_fov = AoaFovCfg.from_args(args)
		elif cmd == "cfarFovCfg":
			cfar_fov = CfarFovCfg.from_args(args)
			if cfar_fov.proc_direction == 0:
				self.config.cfar_fov_range = cfar_fov
			else:
				self.config.cfar_fov_doppler = cfar_fov
		elif cmd == "clutterRemoval":
			self.config.clutter_removal = ClutterRemovalCfg.from_args(args)
		elif cmd == "multiObjBeamForming":
			self.config.multi_obj_beam_forming = MultiObjBeamFormingCfg.from_args(args)
		elif cmd == "extendedMaxVelocity":
			self.config.extended_max_velocity = ExtendedMaxVelocityCfg.from_args(args)
		elif cmd == "bpmCfg":
			self.config.bpm = BpmCfg.from_args(args)
		elif cmd == "lvdsStreamCfg":
			self.config.lvds_stream = LvdsStreamCfg.from_args(args)
		elif cmd == "compRangeBiasAndRxChanPhase":
			self.config.comp_range_bias = CompRangeBiasCfg.from_args(args)
		elif cmd == "vitalSignsCfg":
			self.config.vital_signs = VitalSignsCfg.from_args(args)
		elif cmd == "dfeDataOutputMode":
			self.config.dfe_output_mode = int(args[0]) if args else 1


def parse_config_file(path: Path | str) -> ParsedConfig:
	"""Parse a TI mmWave .cfg file.

	Args:
		path: Path to the .cfg file

	Returns:
		ParsedConfig with all extracted parameters
	"""
	parser = ConfigParser()
	return parser.parse_file(path)


def parse_config_content(content: str) -> ParsedConfig:
	"""Parse TI mmWave config content from a string.

	Args:
		content: Config file content as string

	Returns:
		ParsedConfig with all extracted parameters
	"""
	parser = ConfigParser()
	return parser.parse_content(content)
