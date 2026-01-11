"""Tests for TI mmWave config parser module."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from ambient.sensor.config_parser import (
    ADCConfig,
    AoaFovCfg,
    BpmCfg,
    CfarCfg,
    CfarFovCfg,
    ChannelConfig,
    ChirpCfg,
    ClutterRemovalCfg,
    CompRangeBiasCfg,
    ConfigParser,
    ExtendedMaxVelocityCfg,
    FrameCfg,
    GuiMonitorCfg,
    LvdsStreamCfg,
    MultiObjBeamFormingCfg,
    ParsedConfig,
    ProfileCfg,
    VitalSignsCfg,
    parse_config_content,
    parse_config_file,
)


class TestChannelConfig:
    """Tests for ChannelConfig dataclass."""

    def test_default_values(self):
        cfg = ChannelConfig()
        assert cfg.rx_channel_en == 15
        assert cfg.tx_channel_en == 7
        assert cfg.cascading == 0

    def test_from_args(self):
        cfg = ChannelConfig.from_args(["12", "5", "1"])
        assert cfg.rx_channel_en == 12
        assert cfg.tx_channel_en == 5
        assert cfg.cascading == 1

    def test_from_args_partial(self):
        cfg = ChannelConfig.from_args(["12"])
        assert cfg.rx_channel_en == 12
        assert cfg.tx_channel_en == 7  # Default

    def test_to_command(self):
        cfg = ChannelConfig(rx_channel_en=15, tx_channel_en=7, cascading=0)
        assert cfg.to_command() == "channelCfg 15 7 0"

    def test_num_rx_channels(self):
        # 15 = 0b1111 = 4 channels
        cfg = ChannelConfig(rx_channel_en=15)
        assert cfg.num_rx_channels == 4

        # 5 = 0b0101 = 2 channels
        cfg = ChannelConfig(rx_channel_en=5)
        assert cfg.num_rx_channels == 2

    def test_num_tx_channels(self):
        # 7 = 0b111 = 3 channels
        cfg = ChannelConfig(tx_channel_en=7)
        assert cfg.num_tx_channels == 3

        # 1 = 0b001 = 1 channel
        cfg = ChannelConfig(tx_channel_en=1)
        assert cfg.num_tx_channels == 1


class TestADCConfig:
    """Tests for ADCConfig dataclass."""

    def test_default_values(self):
        cfg = ADCConfig()
        assert cfg.num_adc_bits == 2
        assert cfg.adc_output_fmt == 1

    def test_from_args(self):
        cfg = ADCConfig.from_args(["1", "2"])
        assert cfg.num_adc_bits == 1
        assert cfg.adc_output_fmt == 2

    def test_to_command(self):
        cfg = ADCConfig(num_adc_bits=2, adc_output_fmt=1)
        assert cfg.to_command() == "adcCfg 2 1"


class TestProfileCfg:
    """Tests for ProfileCfg dataclass."""

    def test_default_values(self):
        cfg = ProfileCfg()
        assert cfg.profile_id == 0
        assert cfg.start_freq_ghz == 60.0
        assert cfg.adc_samples == 256
        assert cfg.sample_rate_ksps == 7200

    def test_from_args(self):
        args = [
            "0", "60.5", "7.0", "3.0", "40.0", "0", "0",
            "99.97", "1.0", "256", "7200", "0", "0", "30"
        ]
        cfg = ProfileCfg.from_args(args)
        assert cfg.profile_id == 0
        assert cfg.start_freq_ghz == 60.5
        assert cfg.freq_slope_mhz_us == 99.97
        assert cfg.adc_samples == 256

    def test_to_command(self):
        cfg = ProfileCfg()
        cmd = cfg.to_command()
        assert cmd.startswith("profileCfg 0 60.0")

    def test_bandwidth_mhz(self):
        cfg = ProfileCfg(freq_slope_mhz_us=100.0, ramp_end_time_us=40.0)
        assert cfg.bandwidth_mhz == 4000.0  # 100 * 40

    def test_wavelength_m(self):
        cfg = ProfileCfg(start_freq_ghz=60.0)
        expected = 3e8 / (60e9)
        assert np.isclose(cfg.wavelength_m, expected)


class TestChirpCfg:
    """Tests for ChirpCfg dataclass."""

    def test_default_values(self):
        cfg = ChirpCfg()
        assert cfg.chirp_start_idx == 0
        assert cfg.chirp_end_idx == 0
        assert cfg.tx_enable_mask == 1

    def test_from_args(self):
        cfg = ChirpCfg.from_args(["0", "0", "0", "0", "0", "0", "0", "1"])
        assert cfg.chirp_start_idx == 0
        assert cfg.chirp_end_idx == 0
        assert cfg.tx_enable_mask == 1

    def test_to_command(self):
        cfg = ChirpCfg()
        cmd = cfg.to_command()
        assert "chirpCfg" in cmd


class TestFrameCfg:
    """Tests for FrameCfg dataclass."""

    def test_default_values(self):
        cfg = FrameCfg()
        assert cfg.chirp_start_idx == 0
        assert cfg.chirp_end_idx == 2
        assert cfg.num_loops == 32
        assert cfg.frame_period_ms == 50.0

    def test_from_args(self):
        cfg = FrameCfg.from_args(["0", "2", "32", "0", "50.0", "1", "0"])
        assert cfg.chirp_start_idx == 0
        assert cfg.chirp_end_idx == 2
        assert cfg.num_loops == 32
        assert cfg.num_frames == 0
        assert cfg.frame_period_ms == 50.0

    def test_to_command(self):
        cfg = FrameCfg()
        cmd = cfg.to_command()
        assert cmd.startswith("frameCfg")

    def test_num_chirps_per_frame(self):
        cfg = FrameCfg(chirp_start_idx=0, chirp_end_idx=2, num_loops=32)
        # (2 - 0 + 1) * 32 = 3 * 32 = 96
        assert cfg.num_chirps_per_frame == 96

    def test_frame_rate_hz(self):
        cfg = FrameCfg(frame_period_ms=50.0)
        assert cfg.frame_rate_hz == 20.0

        cfg = FrameCfg(frame_period_ms=100.0)
        assert cfg.frame_rate_hz == 10.0

    def test_frame_rate_hz_zero_period(self):
        cfg = FrameCfg(frame_period_ms=0.0)
        assert cfg.frame_rate_hz == 0


class TestGuiMonitorCfg:
    """Tests for GuiMonitorCfg dataclass."""

    def test_default_values(self):
        cfg = GuiMonitorCfg()
        assert cfg.subframe_idx == -1
        assert cfg.detected_objects == 1
        assert cfg.range_doppler_heatmap == 0

    def test_from_args(self):
        cfg = GuiMonitorCfg.from_args(["-1", "1", "1", "1", "1", "1", "1"])
        assert cfg.range_azimuth_heatmap == 1
        assert cfg.range_doppler_heatmap == 1

    def test_to_command(self):
        cfg = GuiMonitorCfg()
        cmd = cfg.to_command()
        assert "guiMonitor" in cmd


class TestCfarCfg:
    """Tests for CfarCfg dataclass."""

    def test_default_values(self):
        cfg = CfarCfg()
        assert cfg.subframe_idx == -1
        assert cfg.proc_direction == 0
        assert cfg.mode == 2
        assert cfg.threshold_scale_db == 15.0

    def test_from_args(self):
        cfg = CfarCfg.from_args(["-1", "0", "2", "8", "4", "3", "0", "15.0", "0"])
        assert cfg.noise_win == 8
        assert cfg.guard_len == 4
        assert cfg.threshold_scale_db == 15.0

    def test_to_command(self):
        cfg = CfarCfg()
        cmd = cfg.to_command()
        assert "cfarCfg" in cmd


class TestAoaFovCfg:
    """Tests for AoaFovCfg dataclass."""

    def test_default_values(self):
        cfg = AoaFovCfg()
        assert cfg.min_azimuth_deg == -90.0
        assert cfg.max_azimuth_deg == 90.0
        assert cfg.min_elevation_deg == -90.0
        assert cfg.max_elevation_deg == 90.0

    def test_from_args(self):
        cfg = AoaFovCfg.from_args(["-1", "-45", "45", "-30", "30"])
        assert cfg.min_azimuth_deg == -45.0
        assert cfg.max_azimuth_deg == 45.0
        assert cfg.min_elevation_deg == -30.0
        assert cfg.max_elevation_deg == 30.0

    def test_to_command(self):
        cfg = AoaFovCfg()
        cmd = cfg.to_command()
        assert "aoaFovCfg" in cmd


class TestCfarFovCfg:
    """Tests for CfarFovCfg dataclass."""

    def test_default_values(self):
        cfg = CfarFovCfg()
        assert cfg.min_value == 0.25
        assert cfg.max_value == 15.0

    def test_from_args(self):
        cfg = CfarFovCfg.from_args(["-1", "0", "0.5", "10.0"])
        assert cfg.min_value == 0.5
        assert cfg.max_value == 10.0

    def test_to_command(self):
        cfg = CfarFovCfg()
        cmd = cfg.to_command()
        assert "cfarFovCfg" in cmd


class TestClutterRemovalCfg:
    """Tests for ClutterRemovalCfg dataclass."""

    def test_default_values(self):
        cfg = ClutterRemovalCfg()
        assert cfg.enabled == 0

    def test_from_args(self):
        cfg = ClutterRemovalCfg.from_args(["-1", "1"])
        assert cfg.enabled == 1

    def test_to_command(self):
        cfg = ClutterRemovalCfg(subframe_idx=-1, enabled=1)
        assert cfg.to_command() == "clutterRemoval -1 1"


class TestMultiObjBeamFormingCfg:
    """Tests for MultiObjBeamFormingCfg dataclass."""

    def test_default_values(self):
        cfg = MultiObjBeamFormingCfg()
        assert cfg.enabled == 1
        assert cfg.threshold == 0.5

    def test_from_args(self):
        cfg = MultiObjBeamFormingCfg.from_args(["-1", "1", "0.3"])
        assert cfg.enabled == 1
        assert cfg.threshold == 0.3


class TestExtendedMaxVelocityCfg:
    """Tests for ExtendedMaxVelocityCfg dataclass."""

    def test_default_values(self):
        cfg = ExtendedMaxVelocityCfg()
        assert cfg.enabled == 0

    def test_from_args(self):
        cfg = ExtendedMaxVelocityCfg.from_args(["-1", "1"])
        assert cfg.enabled == 1


class TestBpmCfg:
    """Tests for BpmCfg dataclass."""

    def test_default_values(self):
        cfg = BpmCfg()
        assert cfg.enabled == 0
        assert cfg.chirp0_idx == 0
        assert cfg.chirp1_idx == 1

    def test_from_args(self):
        cfg = BpmCfg.from_args(["-1", "1", "0", "2"])
        assert cfg.enabled == 1
        assert cfg.chirp1_idx == 2


class TestLvdsStreamCfg:
    """Tests for LvdsStreamCfg dataclass."""

    def test_default_values(self):
        cfg = LvdsStreamCfg()
        assert cfg.enable_header == 0
        assert cfg.data_fmt == 0

    def test_from_args(self):
        cfg = LvdsStreamCfg.from_args(["-1", "1", "1", "1"])
        assert cfg.enable_header == 1
        assert cfg.data_fmt == 1


class TestCompRangeBiasCfg:
    """Tests for CompRangeBiasCfg dataclass."""

    def test_default_values(self):
        cfg = CompRangeBiasCfg()
        assert cfg.range_bias == 0.0
        assert len(cfg.rx_phase_comp) == 24  # 12 * 2

    def test_from_args(self):
        args = ["0.5", "1", "0", "1", "0", "1", "0"]
        cfg = CompRangeBiasCfg.from_args(args)
        assert cfg.range_bias == 0.5
        assert cfg.rx_phase_comp[0] == 1

    def test_to_command(self):
        cfg = CompRangeBiasCfg(range_bias=0.1, rx_phase_comp=[1.0, 0.0])
        cmd = cfg.to_command()
        assert "compRangeBiasAndRxChanPhase 0.1" in cmd


class TestVitalSignsCfg:
    """Tests for VitalSignsCfg dataclass."""

    def test_default_values(self):
        cfg = VitalSignsCfg()
        assert cfg.range_start_m == 0.3
        assert cfg.range_end_m == 1.5
        assert cfg.enabled == 1

    def test_from_args(self):
        cfg = VitalSignsCfg.from_args(["0.5", "2.0", "25", "25", "1"])
        assert cfg.range_start_m == 0.5
        assert cfg.range_end_m == 2.0
        assert cfg.win_len_breath == 25

    def test_to_command(self):
        cfg = VitalSignsCfg()
        cmd = cfg.to_command()
        assert "vitalSignsCfg" in cmd


class TestParsedConfig:
    """Tests for ParsedConfig dataclass."""

    def test_default_values(self):
        cfg = ParsedConfig()
        assert isinstance(cfg.channel, ChannelConfig)
        assert isinstance(cfg.adc, ADCConfig)
        assert isinstance(cfg.profile, ProfileCfg)
        assert cfg.chirps == []
        assert cfg.dfe_output_mode == 1

    def test_range_resolution_m(self):
        cfg = ParsedConfig()
        cfg.profile.freq_slope_mhz_us = 100.0
        cfg.profile.ramp_end_time_us = 40.0
        # Bandwidth = 100 * 40 = 4000 MHz = 4e9 Hz
        # Range res = c / (2 * BW) = 3e8 / 8e9 = 0.0375 m
        assert np.isclose(cfg.range_resolution_m, 0.0375)

    def test_range_resolution_m_zero_bandwidth(self):
        cfg = ParsedConfig()
        cfg.profile.freq_slope_mhz_us = 0.0
        assert cfg.range_resolution_m == 0

    def test_max_range_m(self):
        cfg = ParsedConfig()
        cfg.profile.sample_rate_ksps = 10000
        cfg.profile.freq_slope_mhz_us = 50.0
        # Sample rate = 10e6 Hz
        # Slope = 50e12 Hz/s
        # Max range = (10e6 * 3e8) / (2 * 50e12) = 30 m
        expected = (10e6 * 3e8) / (2 * 50e12)
        assert np.isclose(cfg.max_range_m, expected)

    def test_max_range_m_zero_slope(self):
        cfg = ParsedConfig()
        cfg.profile.freq_slope_mhz_us = 0.0
        assert cfg.max_range_m == 0

    def test_velocity_resolution(self):
        cfg = ParsedConfig()
        cfg.profile.start_freq_ghz = 60.0
        cfg.profile.idle_time_us = 7.0
        cfg.profile.ramp_end_time_us = 40.0
        cfg.frame.chirp_start_idx = 0
        cfg.frame.chirp_end_idx = 2
        cfg.frame.num_loops = 32

        # Wavelength = c / (60e9) = 0.005 m
        # Chirp time = (7 + 40) * 1e-6 = 47e-6 s
        # num_chirps = 3 * 32 = 96
        # Frame time = 47e-6 * 96 = 4.512e-3 s
        # Vel res = wavelength / (2 * frame_time)
        wavelength = 3e8 / 60e9
        chirp_time = 47e-6
        frame_time = chirp_time * 96
        expected = wavelength / (2 * frame_time)
        assert np.isclose(cfg.velocity_resolution_mps, expected)

    def test_max_velocity(self):
        cfg = ParsedConfig()
        cfg.profile.start_freq_ghz = 60.0
        cfg.profile.idle_time_us = 7.0
        cfg.profile.ramp_end_time_us = 40.0
        cfg.channel.tx_channel_en = 7  # 3 TX channels

        # Max velocity = wavelength / (4 * chirp_time * num_tx)
        wavelength = 3e8 / 60e9
        chirp_time = 47e-6
        num_tx = 3
        expected = wavelength / (4 * chirp_time * num_tx)
        assert np.isclose(cfg.max_velocity_mps, expected)

    def test_frame_rate_hz(self):
        cfg = ParsedConfig()
        cfg.frame.frame_period_ms = 50.0
        assert cfg.frame_rate_hz == 20.0

    def test_num_range_bins(self):
        cfg = ParsedConfig()
        cfg.profile.adc_samples = 256
        assert cfg.num_range_bins == 256

    def test_num_doppler_bins(self):
        cfg = ParsedConfig()
        cfg.frame.num_loops = 32
        assert cfg.num_doppler_bins == 32

    def test_num_virtual_antennas(self):
        cfg = ParsedConfig()
        cfg.channel.rx_channel_en = 15  # 4 RX
        cfg.channel.tx_channel_en = 7   # 3 TX
        assert cfg.num_virtual_antennas == 12  # 4 * 3

    def test_to_commands(self):
        cfg = ParsedConfig()
        cfg.chirps.append(ChirpCfg())
        commands = cfg.to_commands()

        assert isinstance(commands, list)
        assert "sensorStop" in commands
        assert "flushCfg" in commands
        assert any("channelCfg" in cmd for cmd in commands)
        assert any("profileCfg" in cmd for cmd in commands)
        assert any("chirpCfg" in cmd for cmd in commands)
        assert any("frameCfg" in cmd for cmd in commands)

    def test_to_dict(self):
        cfg = ParsedConfig()
        d = cfg.to_dict()

        assert "range_resolution_m" in d
        assert "max_range_m" in d
        assert "velocity_resolution_mps" in d
        assert "frame_rate_hz" in d
        assert "num_range_bins" in d
        assert "bandwidth_mhz" in d


class TestConfigParser:
    """Tests for ConfigParser class."""

    def test_initialization(self):
        parser = ConfigParser()
        assert isinstance(parser.config, ParsedConfig)

    def test_parse_empty_content(self):
        parser = ConfigParser()
        cfg = parser.parse_content("")
        assert isinstance(cfg, ParsedConfig)
        assert cfg.raw_commands == []

    def test_parse_comments(self):
        content = """
        % This is a comment
        # This is also a comment
        """
        parser = ConfigParser()
        cfg = parser.parse_content(content)
        assert cfg.raw_commands == []

    def test_parse_channel_cfg(self):
        content = "channelCfg 15 7 0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.channel.rx_channel_en == 15
        assert cfg.channel.tx_channel_en == 7
        assert cfg.channel.cascading == 0

    def test_parse_adc_cfg(self):
        content = "adcCfg 2 1"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.adc.num_adc_bits == 2
        assert cfg.adc.adc_output_fmt == 1

    def test_parse_profile_cfg(self):
        content = "profileCfg 0 60.5 7.0 3.0 39.0 0 0 99.97 1.0 256 7200 0 0 30"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.profile.profile_id == 0
        assert cfg.profile.start_freq_ghz == 60.5
        assert cfg.profile.freq_slope_mhz_us == 99.97
        assert cfg.profile.adc_samples == 256

    def test_parse_chirp_cfg(self):
        content = """
        chirpCfg 0 0 0 0 0 0 0 1
        chirpCfg 1 1 0 0 0 0 0 2
        chirpCfg 2 2 0 0 0 0 0 4
        """
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert len(cfg.chirps) == 3
        assert cfg.chirps[0].tx_enable_mask == 1
        assert cfg.chirps[1].tx_enable_mask == 2
        assert cfg.chirps[2].tx_enable_mask == 4

    def test_parse_frame_cfg(self):
        content = "frameCfg 0 2 32 0 50.0 1 0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.frame.chirp_start_idx == 0
        assert cfg.frame.chirp_end_idx == 2
        assert cfg.frame.num_loops == 32
        assert cfg.frame.frame_period_ms == 50.0

    def test_parse_gui_monitor(self):
        content = "guiMonitor -1 1 1 1 1 1 1"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.gui_monitor.detected_objects == 1
        assert cfg.gui_monitor.range_azimuth_heatmap == 1
        assert cfg.gui_monitor.range_doppler_heatmap == 1

    def test_parse_cfar_range(self):
        content = "cfarCfg -1 0 2 8 4 3 0 15.0 0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.cfar_range.proc_direction == 0
        assert cfg.cfar_range.threshold_scale_db == 15.0

    def test_parse_cfar_doppler(self):
        content = "cfarCfg -1 1 2 4 2 3 1 12.0 0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.cfar_doppler is not None
        assert cfg.cfar_doppler.proc_direction == 1
        assert cfg.cfar_doppler.threshold_scale_db == 12.0

    def test_parse_aoa_fov_cfg(self):
        content = "aoaFovCfg -1 -45 45 -30 30"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.aoa_fov.min_azimuth_deg == -45.0
        assert cfg.aoa_fov.max_azimuth_deg == 45.0

    def test_parse_cfar_fov_range(self):
        content = "cfarFovCfg -1 0 0.5 10.0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.cfar_fov_range is not None
        assert cfg.cfar_fov_range.min_value == 0.5
        assert cfg.cfar_fov_range.max_value == 10.0

    def test_parse_cfar_fov_doppler(self):
        content = "cfarFovCfg -1 1 -3.0 3.0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.cfar_fov_doppler is not None
        assert cfg.cfar_fov_doppler.proc_direction == 1

    def test_parse_clutter_removal(self):
        content = "clutterRemoval -1 1"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.clutter_removal.enabled == 1

    def test_parse_multi_obj_beam_forming(self):
        content = "multiObjBeamForming -1 1 0.3"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.multi_obj_beam_forming.enabled == 1
        assert cfg.multi_obj_beam_forming.threshold == 0.3

    def test_parse_extended_max_velocity(self):
        content = "extendedMaxVelocity -1 1"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.extended_max_velocity.enabled == 1

    def test_parse_bpm_cfg(self):
        content = "bpmCfg -1 1 0 1"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.bpm.enabled == 1

    def test_parse_lvds_stream_cfg(self):
        content = "lvdsStreamCfg -1 1 1 0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.lvds_stream.enable_header == 1
        assert cfg.lvds_stream.data_fmt == 1

    def test_parse_comp_range_bias(self):
        content = "compRangeBiasAndRxChanPhase 0.5 1 0 1 0 1 0 1 0"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.comp_range_bias.range_bias == 0.5

    def test_parse_vital_signs_cfg(self):
        content = "vitalSignsCfg 0.5 2.0 25 25 1"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.vital_signs is not None
        assert cfg.vital_signs.range_start_m == 0.5
        assert cfg.vital_signs.range_end_m == 2.0

    def test_parse_dfe_output_mode(self):
        content = "dfeDataOutputMode 3"
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.dfe_output_mode == 3

    def test_raw_commands_stored(self):
        content = """
        channelCfg 15 7 0
        adcCfg 2 1
        """
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert len(cfg.raw_commands) == 2
        assert "channelCfg 15 7 0" in cfg.raw_commands

    def test_parse_complete_config(self):
        content = """
        % TI mmWave Config
        sensorStop
        flushCfg
        dfeDataOutputMode 1
        channelCfg 15 7 0
        adcCfg 2 1
        profileCfg 0 60.0 7.0 3.0 39.0 0 0 99.97 1.0 256 7200 0 0 30
        chirpCfg 0 0 0 0 0 0 0 1
        chirpCfg 1 1 0 0 0 0 0 2
        chirpCfg 2 2 0 0 0 0 0 4
        frameCfg 0 2 32 0 50.0 1 0
        guiMonitor -1 1 1 0 0 0 1
        cfarCfg -1 0 2 8 4 3 0 15.0 0
        cfarCfg -1 1 2 4 2 3 1 12.0 0
        clutterRemoval -1 1
        """
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.channel.rx_channel_en == 15
        assert len(cfg.chirps) == 3
        assert cfg.frame.frame_rate_hz == 20.0
        assert cfg.clutter_removal.enabled == 1
        assert cfg.cfar_doppler is not None


class TestParseConfigFile:
    """Tests for parse_config_file function."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_config_file("/nonexistent/path/config.cfg")

    def test_parse_from_file(self):
        content = """
        channelCfg 15 7 0
        profileCfg 0 60.0 7.0 3.0 39.0 0 0 99.97 1.0 256 7200 0 0 30
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            cfg = parse_config_file(temp_path)
            assert cfg.channel.rx_channel_en == 15
            assert cfg.profile.adc_samples == 256
        finally:
            Path(temp_path).unlink()

    def test_parse_from_pathlib_path(self):
        content = "channelCfg 12 5 0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            cfg = parse_config_file(temp_path)
            assert cfg.channel.rx_channel_en == 12
        finally:
            temp_path.unlink()


class TestParseConfigContent:
    """Tests for parse_config_content function."""

    def test_parse_simple(self):
        cfg = parse_config_content("channelCfg 15 7 0")
        assert cfg.channel.rx_channel_en == 15

    def test_parse_with_newlines(self):
        content = "channelCfg 15 7 0\nadcCfg 2 1\n"
        cfg = parse_config_content(content)
        assert cfg.channel.rx_channel_en == 15
        assert cfg.adc.num_adc_bits == 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unknown_command_ignored(self):
        content = """
        channelCfg 15 7 0
        unknownCommand 1 2 3
        adcCfg 2 1
        """
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        # Should parse known commands without error
        assert cfg.channel.rx_channel_en == 15
        assert cfg.adc.num_adc_bits == 2

    def test_empty_line_handling(self):
        content = """

        channelCfg 15 7 0

        adcCfg 2 1

        """
        parser = ConfigParser()
        cfg = parser.parse_content(content)

        assert cfg.channel.rx_channel_en == 15
        assert cfg.adc.num_adc_bits == 2

    def test_tabs_in_content(self):
        content = "channelCfg\t15\t7\t0"
        cfg = parse_config_content(content)
        assert cfg.channel.rx_channel_en == 15

    def test_extra_whitespace(self):
        content = "  channelCfg   15   7   0  "
        cfg = parse_config_content(content)
        assert cfg.channel.rx_channel_en == 15

    def test_partial_args_use_defaults(self):
        # Test that partial args fall back to defaults
        content = "profileCfg 0"  # Only profile_id
        cfg = parse_config_content(content)
        assert cfg.profile.profile_id == 0
        assert cfg.profile.start_freq_ghz == 60.0  # Default

    def test_config_reset_on_new_parse(self):
        parser = ConfigParser()

        # Parse first config
        cfg1 = parser.parse_content("channelCfg 15 7 0")
        assert cfg1.channel.rx_channel_en == 15

        # Parse second config - should reset
        cfg2 = parser.parse_content("channelCfg 12 5 0")
        assert cfg2.channel.rx_channel_en == 12

    def test_vital_signs_optional(self):
        cfg = parse_config_content("channelCfg 15 7 0")
        assert cfg.vital_signs is None

    def test_cfar_doppler_optional(self):
        content = "cfarCfg -1 0 2 8 4 3 0 15.0 0"  # Only range CFAR
        cfg = parse_config_content(content)
        assert cfg.cfar_doppler is None
        assert cfg.cfar_range is not None
