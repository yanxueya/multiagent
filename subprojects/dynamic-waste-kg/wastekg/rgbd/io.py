"""读取和写入 RGB-D 帧数据。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from PIL import Image

from wastekg.rgbd.geometry import CameraIntrinsics


def load_intrinsics(path: Path) -> CameraIntrinsics:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return CameraIntrinsics.from_mapping(data)


def load_depth_image(path: Path) -> List[List[int]]:
    image = Image.open(path)
    width, height = image.size
    if hasattr(image, "get_flattened_data"):
        values = list(image.get_flattened_data())
    else:
        values = list(image.getdata())
    return [
        [int(values[y * width + x]) for x in range(width)]
        for y in range(height)
    ]
