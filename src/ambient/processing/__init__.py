"""Signal processing for radar data."""

from ambient.processing.clutter import ClutterRemoval
from ambient.processing.fall_detection import (
	FallDetectionConfig,
	FallDetectionResult,
	FallDetector,
	FallEvent,
	FallState,
)
from ambient.processing.fft import DopplerFFT, RangeFFT
from ambient.processing.pipeline import ProcessingPipeline
from ambient.processing.point_cloud import (
	Point3D,
	PointCloudAccumulator,
	PointCloudConfig,
	age_to_opacity,
	doppler_to_color,
	height_to_color,
	snr_to_color,
)

__all__ = [
	"ProcessingPipeline",
	"RangeFFT",
	"DopplerFFT",
	"ClutterRemoval",
	# Point cloud
	"Point3D",
	"PointCloudConfig",
	"PointCloudAccumulator",
	"snr_to_color",
	"height_to_color",
	"doppler_to_color",
	"age_to_opacity",
	# Fall detection
	"FallDetector",
	"FallDetectionConfig",
	"FallDetectionResult",
	"FallEvent",
	"FallState",
]
