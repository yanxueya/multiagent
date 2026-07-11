"""初始化当前 Python 包。"""

from .geometry import CameraIntrinsics, deproject_pixel_to_point, enrich_record_with_rgbd, enrich_records_with_rgbd
from .realsense_bridge import (
    RealSenseCaptureConfig,
    RealSenseDatasetCaptureConfig,
    capture_aligned_rgbd_frame,
    capture_rgbd_dataset_session,
    write_capture_metadata,
)

__all__ = [
    "CameraIntrinsics",
    "RealSenseCaptureConfig",
    "RealSenseDatasetCaptureConfig",
    "capture_aligned_rgbd_frame",
    "capture_rgbd_dataset_session",
    "deproject_pixel_to_point",
    "enrich_record_with_rgbd",
    "enrich_records_with_rgbd",
    "write_capture_metadata",
]
