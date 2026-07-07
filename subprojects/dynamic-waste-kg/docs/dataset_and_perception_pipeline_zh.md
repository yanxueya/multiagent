# 数据集处理与感知流水线

这份文档说明如何把两个已有建筑垃圾数据集转换成本研究可用的 YOLO 分割数据集，并说明 YOLO 和轻量复核模型如何接入知识图谱。

## 1. 输出目录

转换后的数据集默认放在：

```text
subprojects/dynamic-waste-kg/datasets/waste12_yolo
```

目录结构：

```text
datasets/waste12_yolo/
  data.yaml
  dataset_summary.json
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
```

`data.yaml` 可以直接给 Ultralytics YOLO 训练使用。

## 2. 当前 11 类

训练类别和长期知识层保持一致：

```text
concrete
brick
tile
wood
gypsum_board
foam
metal
soft_plastic
hard_plastic
paperboard
glass
```

`unknown` 不是训练类别，而是系统在低置信度、证据冲突或无法可靠归类时生成的人工复核状态。

`asbestos` / `asbestos_suspect` 不进入当前 YOLO 训练类别；如外部数据或人工记录中出现相关标记，应映射为 `unknown` 或人工复核事件。

## 3. 标签映射

为了复用你已有的两个数据集，转换过程会自动做轻量映射：

- `stone` / `aggregate` -> `concrete`
- `pipe` / `pipes` -> `hard_plastic`
- `plastic` -> `hard_plastic`
- `cardboard` -> `paperboard`
- `timber` -> `wood`
- `gypsum` -> `gypsum_board`
- `asbestos` / `asbestos_suspect` -> `unknown` 或人工复核事件，不写入 YOLO 标签

没有可靠语料支撑的类别不会强行加入默认训练类别，例如 `asphalt`、`waste_paint_can`、`mixed_general_waste`。

## 4. 生成数据集

在 `subprojects/dynamic-waste-kg` 目录下运行：

```powershell
python scripts\data\build_grouped_dataset.py `
  --source datasets\waste12_yolo `
  --out datasets\waste12_grouped_candidate_v1 `
  --seed 0
```

运行后会生成：

- 训练图片；
- 验证图片；
- 测试图片；
- YOLO 分割标注；
- `data.yaml`；
- `dataset_summary.json`。

## 5. 为什么用 YOLO 分割

你的后续任务涉及夹爪抓取，普通检测框只能告诉系统“物体大概在哪”。实例分割可以给出更接近物体真实轮廓的 `mask_polygon`，后续更容易结合 RealSense 深度图提取目标点云和三维中心。

当前两个数据集都没有真实深度图或点云，因此它们只用于训练 RGB 识别和分割。三维位置、堆叠关系、支撑关系和抓取置信度应由 RealSense D435i 在线生成，并写入短期记忆层。

## 6. YOLO 和轻量复核模型怎么接图谱

推荐链路：

```text
YOLO/YOLO-seg
  -> yolo_records
  -> 轻量复核模型或多模态模型
  -> VisionPacket
  -> Observation
  -> KnowledgeGraph
  -> LangGraph planning state
  -> ROS2 action command
```

当前项目中对应代码是：

- `wastekg.data.grouping`：把数据集整理为 YOLO 可训练格式；
- `wastekg.perception.pipeline`：把 YOLO 结果和复核结果写入知识图谱；
- `wastekg.perception.vision_bridge`：把字典/JSON 结果转成 `VisionPacket`；
- `wastekg.interfaces.contracts`：提供 LangGraph 和 ROS2 出口。

## 7. 训练 YOLO 分割模型

项目里提供了一个可选训练脚本：

```text
scripts/yolo/train_yolo_seg.py
```

安装好 Ultralytics 后，可以在 `subprojects/dynamic-waste-kg` 下运行下列命令。涉及模型训练时，AI 代理只应输出操作指令，不应在沙盒中直接启动训练；请由用户在本机确认显存后自行运行：

```powershell
python scripts/yolo/train_yolo_seg.py `
  --data datasets/waste12_yolo/data.yaml `
  --model yolo11n-seg.pt `
  --epochs 80 `
  --imgsz 640 `
  --device 0
```

你当前显卡 8GB，建议先用 `yolo11n-seg.pt` 或 `yolo11s-seg.pt`，不要一开始就用大模型。

## 8. 轻量复核模型应该放在哪里

轻量复核模型不建议直接塞进数据集转换脚本里。推荐结构是：

- 数据集转换：只负责整理图片和标签；
- YOLO：负责快速检测和实例分割；
- 轻量复核模型：只复核低置信度、高风险或易混淆对象；
- 知识图谱：保存长期类别先验和短期场景状态。

当前代码中，复核模型只需要实现一个 `review()` 方法，返回 `ReviewResult`。
这样以后你可以先用规则或小模型占位，再替换成多模态模型，不需要改知识图谱核心代码。

## 9. 最小接入示例

```python
from wastekg import KnowledgeGraph, apply_perception_records_to_graph, seed_default_categories

graph = KnowledgeGraph()
seed_default_categories(graph)

packet, result = apply_perception_records_to_graph(
    graph,
    frame_id="frame_001",
    source="yolo_seg",
    yolo_records=[
        {
            "temp_id": "d1",
            "yolo_class_name": "brick",
            "yolo_confidence": 0.92,
            "center_xyz": [0.10, 0.20, 0.05],
        }
    ],
)
```

如果后续接入轻量复核模型，只需要实现一个带有 `review()` 方法的对象，返回 `ReviewResult` 即可。
