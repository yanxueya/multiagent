from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wastekg.realsense_bridge import RealSenseCaptureConfig, capture_aligned_rgbd_frame


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture one aligned RGB-D frame from Intel RealSense D435i.")
    parser.add_argument("--out", type=Path, default=Path("artifacts/captures/frame_001"), help="Output folder.")
    parser.add_argument("--width", type=int, default=640, help="Color/depth stream width.")
    parser.add_argument("--height", type=int, default=480, help="Color/depth stream height.")
    parser.add_argument("--fps", type=int, default=30, help="Camera FPS.")
    parser.add_argument("--warmup-frames", type=int, default=15, help="Frames to skip before saving.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    result = capture_aligned_rgbd_frame(
        args.out.resolve(),
        RealSenseCaptureConfig(
            width=args.width,
            height=args.height,
            fps=args.fps,
            warmup_frames=args.warmup_frames,
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
