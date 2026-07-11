# YOLO + 大模型接入指南

这份文档告诉你，如何把你现有的图片/标签项目接到本知识图谱上。

## 1. 总体思路

整个链路建议分成四层：

1. 数据集训练层：用你的建筑垃圾图片和标签训练 YOLO
2. 感知筛选层：YOLO 先做快速检测
3. VLM 属性校验层：对中置信度、类别歧义、未知对象进行视觉属性抽取和一致性校验
4. 图谱写入层：把结果转成 `Observation` 再写入知识图谱

核心原则：

- YOLO 负责提出明确类别假设；
- VLM 负责提取结构化视觉属性并检查证据是否支持 YOLO 假设；
- 图谱负责保存长期先验、短期状态、unknown 记忆入口和规划约束。

## 2. 数据集怎么准备

如果你现在手里已经有图片和标签，第一步是确认它们是不是 YOLO 格式。

YOLO 检测任务通常需要：

- `images/train`
- `images/val`
- `labels/train`
- `labels/val`
- 一个数据集配置文件 `data.yaml`

### `data.yaml` 示例

```yaml
path: /your/dataset/root
train: images/train
val: images/val
names:
  0: concrete
  1: brick
  2: tile
  3: wood
  4: gypsum_board
  5: foam
  6: metal
  7: soft_plastic
  8: hard_plastic
  9: paperboard
  10: glass
```

如果你的标签不是这套类名，可以先做一个映射表，再统一到当前图谱的长期知识层。

当前项目已经内置了以下轻量映射：

- `stone` 和 `aggregate` 会进入 `concrete`
- `pipe` 和 `pipes` 会进入 `hard_plastic`
- `cardboard` 会进入 `paperboard`
- `timber` 会进入 `wood`
- `gypsum` 会进入 `gypsum_board`

### 额外建议

你后面最好把数据整理成三份：

- `train`：训练集
- `val`：验证集
- `test`：最终测试集

这样你才能区分“模型学会了”还是“只是对验证集记住了”。

## 3. 先训练 YOLO，再接大模型

建议顺序是：

1. 先训练一个基础 YOLO 模型
2. 先让它在你的建筑垃圾数据上达到可用精度
3. 再加大模型做低置信度复核

不要一开始就把 YOLO 和大模型同时做得太复杂，否则很难定位问题。

### 训练示例

Ultralytics 的训练模式支持自定义数据集，也支持通过 `model.train(data=..., epochs=..., imgsz=...)` 方式训练；如果在 Windows 上直接运行脚本，要注意加 `if __name__ == "__main__":`，否则可能遇到多进程启动问题。具体参数和示例可参考官方训练文档。  
参考：<https://docs.ultralytics.com/modes/train/>

```python
from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolo11n.pt")
    results = model.train(
        data="data.yaml",
        epochs=100,
        imgsz=640,
        device=0,
    )
```

### 资源建议

你这台机器是 16GB 内存、8GB 显存，建议先从以下配置开始：

- 模型：`yolo11n` 或 `yolo11s`
- 输入尺寸：`640`
- batch：先用小 batch，或者让框架自动调节
- 先训练少类目版本，再扩展到全部类目

如果你在 Windows 上训练，建议把训练脚本放在单独的 Python 虚拟环境里，避免不同项目之间的依赖冲突。
训练过程中最重要的不是先上复杂方案，而是先把数据、类别和输出格式统一。

Ultralytics 文档说明，训练时可以用单 GPU、CPU，或者让系统自动选择设备，也支持自动 batch 策略。  
参考：<https://docs.ultralytics.com/modes/train/>

## 4. YOLO 输出怎么接 VLM

YOLO 先给出：

- 类别
- 置信度
- 框位置
- 可能的实例 id
- mask 或 crop 图像

然后按照以下规则决定是否调用 VLM：

- `conf >= 0.75` 且类别为低风险、非强复核类：作为已知候选，但仍由知识图谱检查是否允许处理；
- `0.30 <= conf < 0.75`：调用 VLM 提取视觉属性并做一致性校验；
- `0.05 <= conf < 0.30`：保留为低置信候选，不接受类别，设置 `recognition_status=review_required` 并等待人工复核；
- `conf < 0.05`：不进入候选池；
- 类别之间容易混淆时，调用 VLM；
- VLM 与 YOLO 冲突时，不自动改类，令 `recognition_status=unknown` 和 `current_handling_policy=robot_forbidden`。

### 推荐阈值

- `proposal_conf = 0.05`：仅用于 YOLO 候选生成，尽量避免漏检；
- `review_conf = 0.30`：低于该值的候选不接受类别，令 `recognition_status=review_required` 并进入人工复核；
- `accept_conf = 0.75`：高于该值且非强复核类，才可作为已知候选；
- `0.30 <= conf < 0.75`：进入 VLM 属性一致性校验；
- `conf=0.05` 不是类别接受阈值，更不是自动抓取阈值。

## 5. VLM 应该做什么

VLM 不建议直接负责“整张图实时检测”，也不建议直接自由回答“这是什么物体”。它更适合做下面几件事：

- 提取当前实例的结构化视觉属性；
- 判断属性是否支持 YOLO 的类别假设；
- 标记证据不足、属性冲突或需要人工复核；
- 把不确定目标转入 `unknown` 记忆入口；
- 保留可审计的文字理由和 JSON 证据。

### 推荐输入方式

给大模型输入时，优先传：

- 目标裁剪图
- YOLO 初筛类别
- 置信度
- 场景上下文
- 你允许的大类列表

### 推荐输出格式

大模型输出尽量结构化，比如：

```json
{
  "decision": "agree",
  "confidence": 0.88,
  "visual_attributes": {
    "color": "clear",
    "transparency": "transparent",
    "gloss": "high",
    "surface_texture": "smooth",
    "edge_shape": "sharp",
    "shape_cue": "fragment"
  },
  "consistency": "support",
  "requires_human_review": false,
  "reason": "The visual attributes support the YOLO glass hypothesis."
}
```

## 6. 接到图谱时怎么写

我们这个项目已经准备好了接口层：

- `VisionDetection`：表示 YOLO + 大模型联合识别结果
- `VisionPacket`：表示一帧图像的全部检测结果
- `build_vision_packet_from_records()`：把 YOLO/LLM 导出的 JSON 记录快速整理成 `VisionPacket`
- `vision_packet_to_observation()`：把视觉结果转成图谱可以写入的观测
- `graph.apply_observation()`：把观测写入知识图谱

### 示例代码

```python
from wastekg import KnowledgeGraph, VisionDetection, VisionPacket, seed_default_categories, vision_packet_to_observation

graph = KnowledgeGraph()
seed_default_categories(graph)

packet = VisionPacket(
    frame_id="frame_001",
    source="camera",
    detections=[
        VisionDetection(
            temp_id="d1",
            yolo_class_name="brick",
            yolo_confidence=0.72,
            llm_class_name="glass",
            llm_confidence=0.88,
            center_xyz=(0.1, 0.1, 0.0),
            risk_hint="medium",
        )
    ],
)

observation = vision_packet_to_observation(packet)
graph.apply_observation(observation)
```

### 推荐的真实写法

如果你的 YOLO 结果和 LLM 结果本来就是 JSON 或字典，建议这样接：

```python
from wastekg import build_vision_packet_from_records, vision_packet_to_observation

packet = build_vision_packet_from_records(
    frame_id="frame_001",
    source="realsense_d435i",
    detections=[
        {
            "temp_id": "d1",
            "yolo_class_name": "brick",
            "yolo_confidence": 0.72,
            "llm_class_name": "glass",
            "llm_confidence": 0.88,
            "center_xyz": [0.12, 0.04, 0.00],
            "risk_hint": "medium",
            "metadata": {"reason": "low confidence, needs review"},
        }
    ],
)

observation = vision_packet_to_observation(packet)
graph.apply_observation(observation)
```

这比你手写每个 dataclass 更适合后续接真实工程，因为前端、推理服务和消息队列都更容易先输出 JSON。

## 7. 你自己的建筑垃圾识别项目怎么接

你已经有图片和标签，这说明你至少已经具备：

- 训练集
- 标注文件
- 类别定义

下一步应该这样做：

### 第一步：统一类别名

把你原来标签里的类别，统一映射到图谱的长期知识层名字。

例如：

- 原始标签 `glass碎片` -> 图谱类别 `glass`
- 原始标签 `石头` -> 图谱类别 `concrete`
- 原始标签 `管道` -> 图谱类别 `hard_plastic`
- 原始标签 `油漆桶` -> 当前不进入 11 个明确类别；如果后续找到可靠数据，再作为扩展类别或人工确认对象处理。

### 第二步：先训练 baseline

先只训练 YOLO，不要加大模型。

目标是先搞清楚：

- 哪些类容易混淆
- 哪些类样本太少
- 哪些类需要大模型复核

### 第三步：定义复核规则

例如：

- `glass`、`gypsum_board` 这类易碎或易混淆对象优先触发 VLM 属性校验
- `brick`、`concrete` 这类大类可以更依赖 YOLO
- `paperboard`、`soft_plastic` 这类形态变化大的类，可以多走 VLM 校验
- `0.05 <= conf < 0.30` 的低置信度候选进入 `review_required`，不直接变成 `unknown`

### 第四步：把结果写回图谱

你的感知模块每次只做一件事：

1. 输出 `VisionPacket`
2. 转成 `Observation`
3. 调 `apply_observation`

这样图谱就会自动维护长期知识、短期记忆和事件历史。

### 第五步：给 VLM 明确职责

VLM 不要直接替代 YOLO，它更适合做这些事：

- 提取颜色、透明度、光泽、纹理、边缘和形状线索；
- 判断这些属性是否支持 YOLO 的类别假设；
- 证据不足时输出 `uncertain`；
- 需要人工复核时输出 `requires_human_review=true`。

建议你给大模型的返回格式固定成结构化 JSON，例如：

```json
{
  "temp_id": "d1",
  "decision": "uncertain",
  "confidence": 0.0,
  "visual_attributes": {
    "color": "gray",
    "transparency": "opaque",
    "gloss": "low",
    "surface_texture": "powdery",
    "edge_shape": "broken",
    "shape_cue": "board"
  },
  "consistency": "insufficient",
  "requires_human_review": true,
  "reason": "The evidence is insufficient to safely confirm the YOLO class."
}
```

这样后面进入 `VisionDetection` 时就不会乱。

## 8. 推荐的下一步

如果你接下来要继续推进，我建议按这个顺序做：

1. 把你的数据集整理成 YOLO 格式
2. 先训练一个 baseline YOLO
3. 跑验证集，找出高混淆类别
4. 为高混淆类别增加 VLM 属性一致性校验
5. 输出 `VisionPacket`
6. 写入图谱
7. 再接 LangGraph 和 ROS2

如果你愿意，我下一步可以继续帮你补两份东西：

1. 一个更完整的 YOLO 训练脚本模板
2. 一个“YOLO 结果 -> LLM 复核 -> 图谱写入”的最小可运行示例
