"""初始化当前 Python 包。"""

from .geometry import CameraIntrinsics, deproject_pixel_to_point, enrich_record_with_rgbd, enrich_records_with_rgbd
from .realsense_bridge import RealSenseCaptureConfig, capture_aligned_rgbd_frame, write_capture_metadata

__all__ = [
    "CameraIntrinsics",
    "RealSenseCaptureConfig",
    "capture_aligned_rgbd_frame",
    "deproject_pixel_to_point",
    "enrich_record_with_rgbd",
    "enrich_records_with_rgbd",
    "write_capture_metadata",
]
