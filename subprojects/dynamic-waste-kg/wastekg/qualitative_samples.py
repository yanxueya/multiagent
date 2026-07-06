"""为论文定性分析选择稀疏样例并渲染 YOLO 分割真值。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_COLORS = (
    (31, 119, 180),
    (255, 127, 14),
    (44, 160, 44),
    (214, 39, 40),
    (148, 103, 189),
    (140, 86, 75),
    (227, 119, 194),
    (127, 127, 127),
    (188, 189, 34),
    (23, 190, 207),
    (230, 90, 40),
)


def select_sparse_examples(
    *,
    image_dir: Path,
    label_dir: Path,
    class_names: Sequence[str],
    target_classes: Sequence[str],
) -> list[dict[str, Any]]:
    """每个目标类选出一个总实例数最少的图像，减少定性图的视觉遮挡。"""

    class_to_id = {name: index for index, name in enumerate(class_names)}
    unknown = sorted(set(target_classes) - set(class_to_id))
    if unknown:
        raise ValueError(f"目标类别不在数据集类别表中：{unknown}")

    labels_by_stem = {path.stem: path for path in label_dir.glob("*.txt")}
    samples: list[dict[str, Any]] = []
    for target_class in target_classes:
        target_id = class_to_id[target_class]
        candidates = []
        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in _IMAGE_EXTENSIONS:
                continue
            label_path = labels_by_stem.get(image_path.stem)
            if label_path is None:
                continue
            annotations = _read_segmentation_labels(label_path)
            target_count = sum(1 for annotation in annotations if annotation["class_id"] == target_id)
            if target_count:
                candidates.append((len(annotations), target_count, image_path.name, image_path, label_path))
        if not candidates:
            raise ValueError(f"未找到类别 {target_class} 的可用样例。")
        total_instances, target_instances, _, image_path, label_path = min(candidates)
        samples.append(
            {
                "target_class": target_class,
                "image_path": image_path,
                "label_path": label_path,
                "target_instances": target_instances,
                "total_instances": total_instances,
            }
        )
    return samples


def render_ground_truth_overlay(
    *,
    image_path: Path,
    label_path: Path,
    class_names: Sequence[str],
    output_path: Path,
) -> None:
    """将所有真值 polygon 半透明叠加到原图，便于与 YOLO 预测图并列比较。"""

    with Image.open(image_path) as source:
        base = source.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size
    for annotation in _read_segmentation_labels(label_path):
        class_id = annotation["class_id"]
        if class_id < 0 or class_id >= len(class_names):
            continue
        coordinates = annotation["coordinates"]
        points = [(coordinates[index] * width, coordinates[index + 1] * height) for index in range(0, len(coordinates), 2)]
        color = _COLORS[class_id % len(_COLORS)]
        draw.polygon(points, fill=(*color, 90), outline=(*color, 255), width=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(base, overlay).convert("RGB").save(output_path, quality=95)


def _read_segmentation_labels(label_path: Path) -> list[dict[str, Any]]:
    annotations = []
    for raw_line in label_path.read_text(encoding="utf-8").splitlines():
        tokens = raw_line.split()
        if len(tokens) < 7:
            continue
        try:
            class_id = int(tokens[0])
            coordinates = [float(value) for value in tokens[1:]]
        except ValueError:
            continue
        if len(coordinates) % 2:
            continue
        annotations.append({"class_id": class_id, "coordinates": coordinates})
    return annotations
