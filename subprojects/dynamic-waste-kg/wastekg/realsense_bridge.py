from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping


@dataclass(frozen=True, slots=True)
class RealSenseCaptureConfig:
    width: int = 640
    height: int = 480
    fps: int = 30
    warmup_frames: int = 15
    depth_preset: str = "default"


def write_capture_metadata(output_dir: Path, *, intrinsics: Mapping[str, Any], metadata: Mapping[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "camera_intrinsics.json").write_text(
        json.dumps(dict(intrinsics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "capture_meta.json").write_text(
        json.dumps(dict(metadata), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def capture_aligned_rgbd_frame(output_dir: Path, config: RealSenseCaptureConfig | None = None) -> Dict[str, Any]:
    """Capture one RealSense aligned RGB-D frame and save it to disk.

    This function imports pyrealsense2 lazily so normal Windows-side graph tests do
    not require the RealSense SDK. Use it on Ubuntu 22.04 when the D435i is plugged in.
    """

    config = config or RealSenseCaptureConfig()
    try:
        import numpy as np
        from PIL import Image
        import pyrealsense2 as rs
    except ImportError as exc:
        raise RuntimeError(
            "RealSense capture requires pyrealsense2, numpy and pillow. "
            "Run this part on Ubuntu 22.04 with the D435i connected."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = rs.pipeline()
    rs_config = rs.config()
    rs_config.enable_stream(rs.stream.color, config.width, config.height, rs.format.rgb8, config.fps)
    rs_config.enable_stream(rs.stream.depth, config.width, config.height, rs.format.z16, config.fps)
    align = rs.align(rs.stream.color)

    profile = pipeline.start(rs_config)
    try:
        for _ in range(max(0, config.warmup_frames)):
            pipeline.wait_for_frames()
        frames = align.process(pipeline.wait_for_frames())
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if not color_frame or not depth_frame:
            raise RuntimeError("RealSense did not return both color and aligned depth frames.")

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())
        color_profile = color_frame.profile.as_video_stream_profile()
        color_intrinsics = color_profile.intrinsics
        depth_sensor = profile.get_device().first_depth_sensor()
        depth_scale = float(depth_sensor.get_depth_scale())
        intrinsics = {
            "width": int(color_intrinsics.width),
            "height": int(color_intrinsics.height),
            "fx": float(color_intrinsics.fx),
            "fy": float(color_intrinsics.fy),
            "ppx": float(color_intrinsics.ppx),
            "ppy": float(color_intrinsics.ppy),
            "depth_scale": depth_scale,
            "frame_id": "camera_color_optical_frame",
        }

        Image.fromarray(color_image).save(output_dir / "color.png")
        Image.fromarray(depth_image.astype("uint16")).save(output_dir / "aligned_depth.png")
        write_capture_metadata(
            output_dir,
            intrinsics=intrinsics,
            metadata={
                "device_name": str(profile.get_device().get_info(rs.camera_info.name)),
                "serial_number": str(profile.get_device().get_info(rs.camera_info.serial_number)),
                "width": config.width,
                "height": config.height,
                "fps": config.fps,
                "warmup_frames": config.warmup_frames,
                "color_path": "color.png",
                "aligned_depth_path": "aligned_depth.png",
            },
        )
    finally:
        pipeline.stop()

    return {
        "output_dir": str(output_dir),
        "color_path": str(output_dir / "color.png"),
        "aligned_depth_path": str(output_dir / "aligned_depth.png"),
        "intrinsics_path": str(output_dir / "camera_intrinsics.json"),
        "intrinsics": intrinsics,
    }
