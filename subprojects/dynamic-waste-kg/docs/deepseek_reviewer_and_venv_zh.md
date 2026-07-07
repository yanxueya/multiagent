# DeepSeek 复核器与虚拟环境使用说明

## 1. 复核器在本项目中的位置

本项目的数据流仍然保持：

```text
YOLO 检测/分割 -> DeepSeek 复核 -> VisionPacket -> Observation -> KnowledgeGraph -> LangGraph/ROS2
```

DeepSeek 不直接修改知识图谱。它只作为 `LightweightReviewer` 的一个实现，在 YOLO 输出进入图谱之前，给出复核结果：

- `class_name`：复核类别，必须属于本项目 11 个明确视觉类别；无法可靠归类时应返回 `unknown` 或触发人工复核；
- `confidence`：复核置信度；
- `risk_hint`：风险提示；
- `need_human_review`：是否需要人工复核；
- `reason`：复核理由。

随后 `apply_perception_records_to_graph()` 会把复核结果写入图谱实例节点的：

- `llm_confidence`
- `final_confidence`
- `review_status`
- `task_status`
- `handling_mode`

## 2. 模型与 API Key

代码默认使用：

```text
base_url = https://api.deepseek.com
model = deepseek-ai/DeepSeek-V4-Pro
```

在 PowerShell 中设置 API Key：

```powershell
$env:DEEPSEEK_API_KEY="你的APIKEY"
```

本项目代码里已经按你的设定默认写入：

```text
model = deepseek-ai/DeepSeek-V4-Pro
```

如果你使用的服务商要求短模型名，例如 `deepseek-v4-pro`，可以覆盖默认模型名：

```powershell
$env:DEEPSEEK_MODEL="deepseek-v4-pro"
```

如果你使用第三方 OpenAI 兼容服务商，也可以覆盖地址：

```powershell
$env:DEEPSEEK_BASE_URL="https://你的服务商地址"
```

注意：当前官方 DeepSeek Chat Completion 接口按文本消息工作。本项目这版先把 YOLO 类别、置信度和图片引用路径交给 DeepSeek 做文本复核。如果后续需要把裁剪图片本身发给大模型，需要选择支持图像输入的视觉大模型或支持多模态的 OpenAI 兼容接口。

## 3. 在代码中使用

```python
from wastekg import DeepSeekReviewer, KnowledgeGraph, apply_perception_records_to_graph, seed_default_categories

graph = KnowledgeGraph()
seed_default_categories(graph)

reviewer = DeepSeekReviewer()

packet, result = apply_perception_records_to_graph(
    graph,
    frame_id="frame_001",
    source="yolo_deepseek",
    yolo_records=[
        {
            "temp_id": "obj_001",
            "yolo_class_name": "gypsum_board",
            "yolo_confidence": 0.72,
            "center_xyz": [0.1, 0.2, 0.3],
            "image_ref": "crops/obj_001.jpg",
        }
    ],
    reviewer=reviewer,
)
```

如果 DeepSeek 或其他复核器认为对象无法可靠归类、存在危险疑点或需要人工确认，应返回 `unknown` 并触发保守策略：

- `review_status = hazard_review_required`
- `task_status = needs_review`
- `handling_mode = human_only`
- `processable = False`

这意味着后续 LangGraph/ROS2 不能直接让机械臂自动抓取。

## 4. PowerShell 虚拟环境激活

你当前的 `.venv` 是存在的，激活失败的根因通常是 PowerShell 默认禁止运行脚本。

进入项目目录：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

只在当前 PowerShell 窗口临时允许脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

确认是否激活成功：

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix)"
```

如果输出路径包含：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\.venv
```

说明激活成功。

## 5. 不激活也能运行

如果你暂时不想处理 PowerShell 执行策略，也可以不激活，直接用虚拟环境里的 Python：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

训练 YOLO 时也可以这样。涉及模型训练时，AI 代理只应输出操作指令，不应在沙盒中直接启动训练；请由用户在本机确认显存后自行运行：

```powershell
.\.venv\Scripts\python.exe scripts\yolo\train_yolo_seg.py --data datasets\waste12_yolo\data.yaml --model yolo11n-seg.pt --epochs 50 --imgsz 640 --device 0
```
