"""Tests for vitals extraction."""

import numpy as np
import pytest

from ambient.vitals.extractor import VitalsExtractor, VitalSigns
from ambient.vitals.filters import BandpassFilter, ExponentialSmoother, MedianFilter
from ambient.vitals.heart_rate import HeartRateEstimator
from ambient.vitals.respiratory import RespiratoryRateEstimator


class TestBandpassFilter:
	def test_init(self):
		f = BandpassFilter(sample_rate_hz=20.0, low_freq_hz=0.8, high_freq_hz=3.0)
		assert f.order == 4

	def test_process(self, sample_phase_signal):
		f = BandpassFilter(sample_rate_hz=20.0, low_freq_hz=0.8, high_freq_hz=3.0)
		out = f.process(sample_phase_signal)
		assert len(out) == len(sample_phase_signal)
		assert out.dtype == np.float32

	def test_invalid_freq_range(self):
		with pytest.raises(ValueError):
			BandpassFilter(sample_rate_hz=20.0, low_freq_hz=5.0, high_freq_hz=3.0)


class TestMedianFilter:
	def test_removes_spike(self):
		f = MedianFilter(window_size=5)
		signal = np.array([1.0, 1.0, 100.0, 1.0, 1.0])
		out = f.process(signal)
		assert out[2] < 50


class TestExponentialSmoother:
	def test_converges(self):
		s = ExponentialSmoother(alpha=0.3)
		for _ in range(20):
			v = s.update(60.0)
		assert abs(v - 60.0) < 1.0

	def test_first_value(self):
		s = ExponentialSmoother(alpha=0.5)
		assert s.update(100.0) == 100.0


class TestHeartRateEstimator:
	def test_detects_60bpm(self, sample_phase_signal):
		# signal has 60 BPM HR component
		f = BandpassFilter(sample_rate_hz=20.0, low_freq_hz=0.8, high_freq_hz=3.0)
		filtered = f.process(sample_phase_signal)
		est = HeartRateEstimator(sample_rate_hz=20.0)
		hr, conf = est.estimate(filtered)
		assert hr is not None
		assert 50 <= hr <= 70  # expect ~60 BPM

	def test_returns_none_for_short_signal(self):
		est = HeartRateEstimator()
		hr, conf = est.estimate(np.zeros(10))
		assert hr is None


class TestRespiratoryRateEstimator:
	def test_detects_15bpm(self, sample_phase_signal):
		# signal has 15 BPM RR component
		f = BandpassFilter(sample_rate_hz=20.0, low_freq_hz=0.1, high_freq_hz=0.6)
		filtered = f.process(sample_phase_signal)
		est = RespiratoryRateEstimator(sample_rate_hz=20.0)
		rr, conf = est.estimate(filtered)
		assert rr is not None
		assert 10 <= rr <= 20  # expect ~15 BPM


class TestVitalSigns:
	def test_is_valid(self):
		valid = VitalSigns(heart_rate_bpm=72.0, respiratory_rate_bpm=15.0, heart_rate_confidence=0.8, respiratory_rate_confidence=0.8)
		assert valid.is_valid()

	def test_is_invalid_when_none(self):
		invalid = VitalSigns()
		assert not invalid.is_valid()

	def test_is_invalid_low_confidence(self):
		low = VitalSigns(heart_rate_bpm=72.0, respiratory_rate_bpm=15.0, heart_rate_confidence=0.2, respiratory_rate_confidence=0.2)
		assert not low.is_valid()

	def test_quality_summary_excellent(self):
		v = VitalSigns(signal_quality=0.9)
		assert "excellent" in v.quality_summary()

	def test_quality_summary_good(self):
		v = VitalSigns(signal_quality=0.7)
		assert "good" in v.quality_summary()

	def test_quality_summary_fair(self):
		v = VitalSigns(signal_quality=0.5)
		assert "fair" in v.quality_summary()

	def test_quality_summary_poor(self):
		v = VitalSigns(signal_quality=0.2)
		assert "poor" in v.quality_summary()


class TestVitalsExtractor:
	def test_needs_warmup(self):
		ext = VitalsExtractor()
		v = ext.process(0.5, timestamp=1.0)
		assert v.heart_rate_bpm is None  # not enough samples

	def test_buffer_fullness(self):
		ext = VitalsExtractor()
		ext.process(0.5, timestamp=1.0)
		assert 0 < ext.buffer_fullness < 0.1
