"""采集 RealSense 对齐 RGB-D 帧。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping


@dataclass(frozen=True, slots=True)
class RealSenseCaptureConfig:
    width: int = 640
    height: int = 480
    fps: int = 30
    warmup_frames: int = 15
    depth_preset: str = "default"


@dataclass(frozen=True, slots=True)
class RealSenseDatasetCaptureConfig:
    """定义一次实验室数据采集 session，避免连续视频帧被当成独立场景。"""

    session_id: str
    count: int = 6
    interval_seconds: float = 4.0
    start_delay_seconds: float = 3.0
    width: int = 640
    height: int = 480
    fps: int = 30
    warmup_frames: int = 30
    save_depth: bool = True
    camera_mount: str = "eye_in_hand"
    gripper_visibility: str = "visible"
    scene_note: str = ""


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


def capture_rgbd_dataset_session(
    output_dir: Path,
    config: RealSenseDatasetCaptureConfig,
    *,
    before_capture: Callable[[int, int], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """单次启动 D435i 并采集少量分组帧；默认按固定间隔保存。"""

    if not config.session_id.strip():
        raise ValueError("session_id 不能为空")
    if config.count <= 0:
        raise ValueError("count 必须大于 0")
    if config.interval_seconds < 0 or config.start_delay_seconds < 0:
        raise ValueError("采集等待时间不能为负数")
    try:
        import numpy as np
        from PIL import Image, ImageFilter, ImageStat
        import pyrealsense2 as rs
    except ImportError as exc:
        raise RuntimeError(
            "RealSense dataset capture requires pyrealsense2, numpy and pillow. "
            "Use Ubuntu 22.04 with the D435i connected."
        ) from exc

    output_dir = output_dir.resolve()
    images_dir = output_dir / "images"
    depth_dir = output_dir / "depth"
    metadata_dir = output_dir / "metadata"
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    if config.save_depth:
        depth_dir.mkdir(parents=True, exist_ok=True)

    pipeline = rs.pipeline()
    rs_config = rs.config()
    rs_config.enable_stream(rs.stream.color, config.width, config.height, rs.format.rgb8, config.fps)
    rs_config.enable_stream(rs.stream.depth, config.width, config.height, rs.format.z16, config.fps)
    align = rs.align(rs.stream.color)
    profile = pipeline.start(rs_config)
    records: list[dict[str, Any]] = []
    try:
        for _ in range(max(0, config.warmup_frames)):
            pipeline.wait_for_frames()
        if config.start_delay_seconds:
            sleep(config.start_delay_seconds)

        intrinsics = _realsense_intrinsics(profile, rs.stream.color)
        write_capture_metadata(
            output_dir,
            intrinsics=intrinsics,
            metadata={
                "session_id": config.session_id,
                "camera_mount": config.camera_mount,
                "gripper_visibility": config.gripper_visibility,
                "scene_note": config.scene_note,
                "requested_count": config.count,
                "interval_seconds": config.interval_seconds,
                "save_depth": config.save_depth,
            },
        )
        for index in range(1, config.count + 1):
            if before_capture is not None and not before_capture(index, config.count):
                break
            frames = align.process(pipeline.wait_for_frames())
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                raise RuntimeError("RealSense did not return both color and aligned depth frames.")

            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())
            frame_id = f"{config.session_id}_{index:03d}"
            color_path = images_dir / f"{frame_id}.png"
            depth_path = depth_dir / f"{frame_id}.png"
            metadata_path = metadata_dir / f"{frame_id}.json"
            color_pil = Image.fromarray(color_image)
            color_pil.save(color_path)
            if config.save_depth:
                Image.fromarray(depth_image.astype("uint16")).save(depth_path)

            gray = color_pil.convert("L")
            quality = {
                "mean_brightness": round(float(ImageStat.Stat(gray).mean[0]), 3),
                "edge_variance": round(float(np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32).var()), 3),
                "depth_valid_ratio": round(float(np.count_nonzero(depth_image) / depth_image.size), 6),
            }
            record = {
                "frame_id": frame_id,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "rgb_path": color_path.relative_to(output_dir).as_posix(),
                "depth_path": depth_path.relative_to(output_dir).as_posix() if config.save_depth else "",
                "metadata_path": metadata_path.relative_to(output_dir).as_posix(),
                "quality": quality,
            }
            metadata_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append(record)
            if index < config.count and config.interval_seconds:
                sleep(config.interval_seconds)
    finally:
        pipeline.stop()

    manifest = {
        "session_id": config.session_id,
        "camera_mount": config.camera_mount,
        "gripper_visibility": config.gripper_visibility,
        "scene_note": config.scene_note,
        "frame_count": len(records),
        "frames": records,
    }
    (output_dir / "session_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _realsense_intrinsics(profile: Any, color_stream: Any) -> Dict[str, Any]:
    color_profile = profile.get_stream(color_stream).as_video_stream_profile()
    color_intrinsics = color_profile.intrinsics
    depth_scale = float(profile.get_device().first_depth_sensor().get_depth_scale())
    return {
        "width": int(color_intrinsics.width),
        "height": int(color_intrinsics.height),
        "fx": float(color_intrinsics.fx),
        "fy": float(color_intrinsics.fy),
        "ppx": float(color_intrinsics.ppx),
        "ppy": float(color_intrinsics.ppy),
        "depth_scale": depth_scale,
        "frame_id": "camera_color_optical_frame",
    }
