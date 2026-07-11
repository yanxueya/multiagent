"""按 session 自动或手动采集少量 D435i RGB-D 标注候选。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.rgbd.realsense_bridge import RealSenseDatasetCaptureConfig, capture_rgbd_dataset_session


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture a small, grouped eye-in-hand D435i dataset session.")
    parser.add_argument("--session-id", required=True, help="Stable group id, for example lab_mix_001.")
    parser.add_argument("--out", type=Path, default=Path("datasets/raw_lab_captures"))
    parser.add_argument("--count", type=int, default=6, help="Frames in this session; 4-8 is usually enough.")
    parser.add_argument("--mode", choices=("manual", "interval"), default="manual")
    parser.add_argument("--interval", type=float, default=4.0, help="Seconds between frames in interval mode.")
    parser.add_argument("--start-delay", type=float, default=3.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--rgb-only", action="store_true", help="Do not save aligned depth PNGs.")
    parser.add_argument("--camera-mount", choices=("eye_in_hand", "fixed_external"), default="eye_in_hand")
    parser.add_argument("--gripper-visibility", choices=("visible", "partial", "absent"), default="visible")
    parser.add_argument("--scene-note", default="")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    output_dir = args.out.resolve() / args.session_id

    def manual_trigger(index: int, total: int) -> bool:
        answer = input(f"[{index}/{total}] Adjust objects/arm, then press Enter to capture; type q to stop: ").strip().lower()
        return answer != "q"

    config = RealSenseDatasetCaptureConfig(
        session_id=args.session_id,
        count=args.count,
        interval_seconds=args.interval if args.mode == "interval" else 0.0,
        start_delay_seconds=args.start_delay,
        width=args.width,
        height=args.height,
        fps=args.fps,
        warmup_frames=args.warmup_frames,
        save_depth=not args.rgb_only,
        camera_mount=args.camera_mount,
        gripper_visibility=args.gripper_visibility,
        scene_note=args.scene_note,
    )
    manifest = capture_rgbd_dataset_session(
        output_dir,
        config,
        before_capture=manual_trigger if args.mode == "manual" else None,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
