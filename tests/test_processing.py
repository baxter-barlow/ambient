"""Tests for processing module."""

import numpy as np
import pytest

from ambient.processing.fft import RangeFFT, DopplerFFT, RangeFFTConfig, DopplerFFTConfig
from ambient.processing.clutter import ClutterRemoval, MTIFilter, MovingAverageClutter


class TestRangeFFT:
	def test_output_shape(self):
		fft = RangeFFT(RangeFFTConfig(fft_size=256))
		data = np.random.randn(64, 256) + 1j * np.random.randn(64, 256)
		out = fft.process(data)
		assert out.shape[1] == 128  # half due to rfft

	def test_magnitude_output(self):
		fft = RangeFFT(RangeFFTConfig(output_type="magnitude"))
		data = np.random.randn(1, 64) + 1j * np.random.randn(1, 64)
		out = fft.process(data)
		assert np.all(out >= 0)


class TestDopplerFFT:
	def test_detects_motion(self):
		fft = DopplerFFT(DopplerFFTConfig(fft_size=64))
		# stationary target
		data = np.ones((64, 32), dtype=complex)
		out = fft.process(data)
		# peak should be at center (zero Doppler)
		center = out.shape[0] // 2
		assert out[center, 0] == out[:, 0].max()


class TestMTIFilter:
	def test_removes_static(self):
		mti = MTIFilter()
		static = np.ones((32, 16)) * 100

		mti.process(static)
		out = mti.process(static)
		assert np.allclose(out, 0)

	def test_detects_change(self):
		mti = MTIFilter()
		mti.process(np.zeros((32, 16)))
		out = mti.process(np.ones((32, 16)) * 100)
		assert np.mean(np.abs(out)) > 50


class TestMovingAverageClutter:
	def test_removes_background(self):
		ma = MovingAverageClutter()
		static = np.ones((32, 16)) * 100

		# warmup
		for _ in range(15):
			ma.process(static)

		out = ma.process(static)
		assert np.mean(np.abs(out)) < 20


class TestClutterRemoval:
	def test_mti_method(self):
		cr = ClutterRemoval(method="mti")
		assert cr.method == "mti"

	def test_moving_average_method(self):
		cr = ClutterRemoval(method="moving_average")
		assert cr.method == "moving_average"

	def test_invalid_method(self):
		with pytest.raises(ValueError):
			ClutterRemoval(method="invalid")

	def test_process(self):
		cr = ClutterRemoval(method="mti")
		data = np.random.rand(32, 16)
		out = cr.process(data)
		assert out.shape == data.shape
