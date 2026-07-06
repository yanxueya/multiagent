"""为受限环境准备 Ultralytics 的本地可写配置和绘图字体。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, Sequence


def prepare_ultralytics_runtime(project_root: Path, *, font_candidates: Sequence[Path] | None = None) -> dict[str, Path]:
    """避免 Ultralytics 在 AppData 中写配置或联网下载 Arial.ttf。"""

    project_root = project_root.resolve()
    config_root = project_root / ".ultralytics_runtime"
    config_dir = config_root / "Ultralytics"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(config_root)

    font_path = config_dir / "Arial.ttf"
    if not font_path.exists():
        source = next((path for path in (font_candidates or _default_font_candidates()) if path.is_file()), None)
        if source is None:
            raise FileNotFoundError("未找到可用 TTF 字体，无法离线准备 Ultralytics 运行目录。")
        shutil.copy2(source, font_path)
    return {"config_root": config_root, "config_dir": config_dir, "font_path": font_path}


def _default_font_candidates() -> Iterable[Path]:
    # Windows 优先使用系统 Arial；Linux 回退到常见的 DejaVu Sans。
    yield Path(r"C:\Windows\Fonts\arial.ttf")
    yield Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
