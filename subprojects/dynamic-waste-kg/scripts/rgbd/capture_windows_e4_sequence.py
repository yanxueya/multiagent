"""Capture fixed-view RGB data on Windows through OpenCV.

This is a Windows fallback for the pre-submission image reshoot and lab
supplementary data collection. It does not depend on pyrealsense2, so it saves
RGB frames only. Depth capture should be done later through the RealSense SDK
or ROS2 when aligned RGB-D is required.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
E4_STEPS = ("T0_initial", "T1_removed", "T2_moved", "T3_reappeared")
COMPARISON_STEPS = ("C0_fixed_scene", "C1_variant_scene")
CAPTURE_KEYS = {13, 10, 32, ord("s"), ord("S")}
QUIT_KEYS = {27, ord("q"), ord("Q")}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture fixed-view RGB data with live OpenCV preview on Windows.")
    parser.add_argument("--scene-id", required=True, help="Stable scene id, for example lab_train_001 or holdout_scene_001.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/windows_e4_capture"), help="Output root.")
    parser.add_argument(
        "--protocol",
        choices=("e4", "dataset", "comparison"),
        default="e4",
        help=(
            "e4: four-frame dynamic sequence; dataset: repeated lab training images; "
            "comparison: fixed-scene images for before/after model comparison."
        ),
    )
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--warmup-frames", type=int, default=12)
    parser.add_argument("--countdown", type=float, default=5.0, help="Seconds before each capture.")
    parser.add_argument("--interval", type=float, default=0.0, help="Extra seconds between steps in timed mode.")
    parser.add_argument("--mode", choices=("manual", "timed"), default="manual")
    parser.add_argument("--frames", type=int, default=20, help="Number of frames to save in dataset protocol.")
    parser.add_argument("--start-index", type=int, default=1, help="First frame index in dataset protocol.")
    parser.add_argument("--class-hint", default="", help="Optional visible class hint, e.g. brick, wood, mixed.")
    parser.add_argument("--split", default="dev", choices=("dev", "train", "val", "test", "holdout"))
    parser.add_argument("--preview", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files in an existing scene directory. Default is safe: create a timestamped run directory.",
    )
    parser.add_argument("--note", default="")
    parser.add_argument("--operator", default="user")
    return parser


def _open_camera(index: int, width: int, height: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {index}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def _read_stable_frame(cap: cv2.VideoCapture, warmup_frames: int) -> Any:
    frame = None
    for _ in range(max(1, warmup_frames)):
        ok, current = cap.read()
        if ok:
            frame = current
        time.sleep(0.03)
    if frame is None:
        raise RuntimeError("Camera opened but did not return a frame")
    return frame


def _countdown(seconds: float, step: str) -> None:
    if seconds <= 0:
        return
    remaining = int(seconds)
    print(f"Prepare {step}. Capturing in {remaining} seconds...")
    while remaining > 0:
        print(f"  {remaining}")
        time.sleep(1.0)
        remaining -= 1
    rest = seconds - int(seconds)
    if rest > 0:
        time.sleep(rest)


def _steps_for_protocol(args: argparse.Namespace) -> tuple[str, ...]:
    if args.protocol == "e4":
        return E4_STEPS
    if args.protocol == "comparison":
        return COMPARISON_STEPS
    return tuple(f"D{index:04d}" for index in range(args.start_index, args.start_index + max(1, args.frames)))


def _resolve_scene_dir(out_root: Path, scene_id: str, overwrite: bool) -> tuple[Path, str]:
    base_dir = (out_root / scene_id).resolve()
    if overwrite or not base_dir.exists():
        return base_dir, scene_id

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate_id = f"{scene_id}_{timestamp}"
    candidate_dir = (out_root / candidate_id).resolve()
    suffix = 2
    while candidate_dir.exists():
        candidate_id = f"{scene_id}_{timestamp}_{suffix:02d}"
        candidate_dir = (out_root / candidate_id).resolve()
        suffix += 1
    print(f"Scene directory already exists; using safe new run directory: {candidate_dir}")
    return candidate_dir, candidate_id


def _write_ground_truth_template(path: Path, scene_id: str, steps: tuple[str, ...]) -> None:
    if path.exists():
        return
    rows = []
    for step in steps:
        rows.append(
            {
                "scene_id": scene_id,
                "frame_id": step,
                "object_id": "",
                "class_name": "",
                "present": "",
                "operation": "",
                "bbox_xyxy": "",
                "mask_ref": "",
                "notes": "",
            }
        )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _overlay(frame: Any, lines: list[str]) -> Any:
    display = frame.copy()
    height = display.shape[0]
    cv2.rectangle(display, (0, 0), (display.shape[1], min(height, 104)), (0, 0, 0), -1)
    for row, line in enumerate(lines):
        cv2.putText(
            display,
            line,
            (12, 26 + row * 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return display


def _capture_preview_frame(
    cap: cv2.VideoCapture,
    window_name: str,
    step: str,
    warmup_frames: int,
) -> Any | None:
    for _ in range(max(1, warmup_frames)):
        cap.read()
        cv2.waitKey(1)

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.03)
            continue
        display = _overlay(
            frame,
            [
                f"Step: {step}",
                "Enter / Space / S = save current frame",
                "Q / Esc = stop capture",
            ],
        )
        cv2.imshow(window_name, display)
        key = cv2.waitKey(20) & 0xFF
        if key in CAPTURE_KEYS:
            return frame
        if key in QUIT_KEYS:
            return None


def _capture_timed_frame(
    cap: cv2.VideoCapture,
    window_name: str,
    step: str,
    warmup_frames: int,
    countdown: float,
    preview: bool,
) -> Any:
    deadline = time.time() + max(0.0, countdown)
    while preview and time.time() < deadline:
        ok, frame = cap.read()
        if ok:
            remaining = max(0.0, deadline - time.time())
            display = _overlay(frame, [f"Step: {step}", f"Timed capture in {remaining:0.1f}s", "Q / Esc = stop capture"])
            cv2.imshow(window_name, display)
            key = cv2.waitKey(20) & 0xFF
            if key in QUIT_KEYS:
                raise KeyboardInterrupt("Timed capture stopped by user")
        else:
            time.sleep(0.03)
    if not preview:
        _countdown(countdown, step)
    return _read_stable_frame(cap, warmup_frames)


def capture_sequence(args: argparse.Namespace) -> dict[str, Any]:
    scene_dir, output_scene_id = _resolve_scene_dir(args.out, args.scene_id, args.overwrite)
    rgb_dir = scene_dir / "rgb"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    cap = _open_camera(args.camera_index, args.width, args.height)
    steps = _steps_for_protocol(args)
    window_name = f"Windows capture - camera {args.camera_index} - {args.scene_id}"
    manifest: dict[str, Any] = {
        "scene_id": args.scene_id,
        "output_scene_id": output_scene_id,
        "output_dir": str(scene_dir),
        "protocol": args.protocol,
        "capture_type": "windows_opencv_rgb_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operator": args.operator,
        "camera_index": args.camera_index,
        "requested_width": args.width,
        "requested_height": args.height,
        "actual_width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "actual_height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "split": args.split,
        "class_hint": args.class_hint,
        "preview_enabled": args.preview,
        "note": args.note,
        "steps": [],
        "limitations": [
            "RGB only; no aligned depth was saved.",
            "Ground truth CSV must be filled manually after capture.",
            "Formal holdout sequences should be captured only after camera pose and lighting are frozen.",
        ],
    }
    try:
        if args.preview:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        for step in steps:
            if args.mode == "manual":
                if args.preview:
                    print(f"\nPreviewing {step}. Focus the preview window, then press Enter/Space/S to save or Q to stop.")
                    frame = _capture_preview_frame(cap, window_name, step, args.warmup_frames)
                    if frame is None:
                        manifest["stopped_at"] = step
                        break
                else:
                    answer = input(f"\nArrange {step}, then press Enter to capture; type q to stop: ").strip().lower()
                    if answer == "q":
                        manifest["stopped_at"] = step
                        break
                    _countdown(args.countdown, step)
                    frame = _read_stable_frame(cap, args.warmup_frames)
            else:
                frame = _capture_timed_frame(cap, window_name, step, args.warmup_frames, args.countdown, args.preview)
            frame_path = rgb_dir / f"{step}.jpg"
            if frame_path.exists() and not args.overwrite:
                raise RuntimeError(f"Refusing to overwrite existing frame without --overwrite: {frame_path}")
            if not cv2.imwrite(str(frame_path), frame):
                raise RuntimeError(f"Failed to write {frame_path}")
            manifest["steps"].append(
                {
                    "frame_id": step,
                    "rgb_ref": str(frame_path.relative_to(scene_dir)),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "height": int(frame.shape[0]),
                    "width": int(frame.shape[1]),
                }
            )
            print(f"Saved {frame_path}")
            if args.mode == "timed" and args.interval > 0:
                time.sleep(args.interval)
    except KeyboardInterrupt as exc:
        manifest["stopped_reason"] = str(exc)
    finally:
        cap.release()
        if args.preview:
            cv2.destroyWindow(window_name)

    manifest_path = scene_dir / "manifest.json"
    if manifest_path.exists() and not args.overwrite:
        raise RuntimeError(f"Refusing to overwrite existing manifest without --overwrite: {manifest_path}")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_ground_truth_template(scene_dir / "ground_truth_template.csv", output_scene_id, steps)
    return manifest


def main() -> int:
    args = _build_parser().parse_args()
    manifest = capture_sequence(args)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
