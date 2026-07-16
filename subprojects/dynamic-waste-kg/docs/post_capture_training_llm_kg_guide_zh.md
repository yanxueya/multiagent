# 补拍后模型训练、LLM 复核与动作前后知识图谱更新操作手册

本文档面向后续真实操作：你先用 Windows 或 Ubuntu 拍图，然后自己在 Roboflow 做 YOLO 分割标注并下载数据集，最后用本项目完成模型微调、LLM 复核、动作前后场景变化识别和知识图谱更新。

当前项目的安全边界要先说清楚：本仓库当前验证范围是“受控二维实例分割 -> 可审计知识状态原型”。下面的流程可以帮助你做图像识别、知识图谱状态更新和后续 ROS2 接入准备，但不能直接声称已经完成真实机械臂闭环抓取。

---

## 0. 先记住三个核心目录

后续大部分命令都在这个目录运行：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

项目里最重要的几个位置：

```text
subprojects/dynamic-waste-kg/
  datasets/                 # 数据集目录；大数据默认不提交 Git
  outputs/yolo_runs/         # YOLO 训练输出；默认不提交 Git
  artifacts/                 # 预测、图谱、临时实验输出；默认不提交 Git
  scripts/yolo/              # YOLO 训练和评估命令入口
  scripts/llm/               # LLM 配置检查命令入口
  scripts/graph/             # 图像识别写入 KG / Neo4j 的命令入口
  wastekg/                   # 核心 Python 代码
```

当前稳定视觉类别是 11 类：

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

不要在 Roboflow 里新增 `unknown` 类。`unknown` 是系统逻辑状态，不是 YOLO 训练类别。低置信度、LLM 冲突、人工无法判断时，代码会把实例送入复核，不需要把它训练成一个类别。

---

## 1. 总流程图

你后续要做的事情可以按这个顺序理解：

```text
拍摄补充图片
  -> Roboflow 中做实例分割标注
  -> 从 Roboflow 下载 YOLOv8/YOLO11 segmentation 格式数据集
  -> 放到 datasets/roboflow_lab_YYYYMMDD/
  -> 检查 data.yaml 的类别是否仍是 11 类
  -> 用 scripts/yolo/train_yolo_seg.py 训练
  -> 得到新的 best.pt
  -> 用同一批 holdout/comparison 图片对比旧模型和新模型
  -> 用新 best.pt 识别动作前/后图片
  -> 写入 KG graph_snapshot/events/change_summary
  -> 可选同步到 Neo4j 和 UI
```

一句话版：先把图标好，训练出新 `best.pt`，再用这个新模型跑动作前后图片，最后让项目代码把识别结果写进知识图谱。

---

## 2. 第一步：拍完图片后，如何在 Roboflow 标注

### 2.1 哪些图片适合进训练集

适合进入训练集的图片：

- 图像清晰，没有严重糊掉。
- 物体在画面里比较完整。
- 11 类里至少有一个类别能明确判断。
- 背景、光照、角度有变化，不是完全重复图。
- 对你的实验室真实物体有代表性。

不建议进入训练集的图片：

- 太暗，肉眼都难判断。
- 物体只露出一点点，无法标注完整 mask。
- 手、人脸、无关物体占据画面主体。
- 同一个画面连续按了很多次，几乎一模一样。
- 你准备用来做“训练前后对比”的 comparison/holdout 图片。

非常关键：用于比较旧模型和新模型的图片不要加入训练集。否则新模型相当于提前看过考试题，对比结果不可信。

### 2.2 Roboflow 项目类型

在 Roboflow 里创建或打开项目时，任务类型请选择：

```text
Instance Segmentation
```

不要选 Object Detection。因为你的当前模型是 YOLO 分割模型，训练需要 mask，不只是矩形框。

### 2.3 Roboflow 类别名称必须这样写

类别名称建议完全使用英文小写和下划线：

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

不要使用：

```text
未知
unknown
asbestos
asbestos_suspect
其他
misc
plastic
```

原因：

- `unknown` 不是 YOLO 类别。
- `asbestos_suspect` 目前不是当前主线视觉类别。
- `plastic` 太粗，会和 `soft_plastic`、`hard_plastic` 冲突。

### 2.4 每张图怎么标

在 Roboflow 里对每个可见物体画一个 polygon mask。

简单理解：

```text
一个物体 = 一个 mask = 一个类别
```

例子：

- 一块砖：画砖的轮廓，类别选 `brick`。
- 一片木板：画木板轮廓，类别选 `wood`。
- 一个透明玻璃碎片：画玻璃轮廓，类别选 `glass`。
- 一个塑料袋：类别选 `soft_plastic`。
- 一个硬塑料瓶/硬塑料片：类别选 `hard_plastic`。

不要把多个物体合成一个 mask。比如画面里有三块砖，就标三个 `brick` mask。

### 2.5 数据集划分

Roboflow 里导出前，建议分成：

```text
train: 70% 到 80%
valid: 10% 到 20%
test: 10%
```

如果你补拍图片数量不多，比如只有 40 到 100 张，可以先这样：

```text
train: 80%
valid: 20%
test: 0%
```

但最好保留一批完全不训练的 comparison/holdout 图片，单独用于训练前后比较。

### 2.6 Roboflow 下载格式

Roboflow 下载时选择：

```text
YOLOv8
```

并确保是 segmentation 格式。下载后通常会得到类似结构：

```text
roboflow_export/
  data.yaml
  train/
    images/
    labels/
  valid/
    images/
    labels/
  test/
    images/
    labels/
```

也可能是：

```text
roboflow_export/
  data.yaml
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
```

这两种 Ultralytics 通常都能识别，关键是 `data.yaml` 写对路径。

---

## 3. 第二步：把 Roboflow 下载的数据放进项目

假设你下载后的压缩包解压在桌面，比如：

```text
C:\Users\12279\Desktop\roboflow_lab_export
```

建议复制到项目里：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\datasets\roboflow_lab_20260716
```

PowerShell 示例：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

New-Item -ItemType Directory -Force -Path datasets\roboflow_lab_20260716
Copy-Item -Recurse -Force C:\Users\12279\Desktop\roboflow_lab_export\* datasets\roboflow_lab_20260716\
```

然后检查：

```powershell
Get-ChildItem datasets\roboflow_lab_20260716
Get-Content datasets\roboflow_lab_20260716\data.yaml
```

`data.yaml` 里最重要的是 `names`。应该类似：

```yaml
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

如果 Roboflow 导出成列表形式，也可以：

```yaml
names:
  - concrete
  - brick
  - tile
  - wood
  - gypsum_board
  - foam
  - metal
  - soft_plastic
  - hard_plastic
  - paperboard
  - glass
```

检查重点：

- 必须是 11 类。
- 类名必须和上面一致。
- 不要出现 `unknown`。
- 不要出现 `asbestos_suspect`。
- 不要出现中文类别。

---

## 4. 第三步：训练前先检查电脑和环境

你的电脑是 8GB 显存独显，训练可以做，但不要一上来用太大模型、太大 batch。

先检查显卡：

```powershell
nvidia-smi
```

进入项目：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

确认 Python 环境能用：

```powershell
.\.venv\Scripts\python.exe --version
```

确认 ultralytics 能导入：

```powershell
.\.venv\Scripts\python.exe -c "import ultralytics; print(ultralytics.__version__)"
```

如果提示没有 ultralytics，再安装：

```powershell
.\.venv\Scripts\python.exe -m pip install ultralytics
```

如果 CUDA 版 PyTorch 有问题，不要盲目重装很多东西。先记录错误，再针对性修。

---

## 5. 第四步：开始 YOLO 分割训练

项目已有训练入口：

```text
scripts/yolo/train_yolo_seg.py
```

这个脚本本质上是对 Ultralytics YOLO 的封装。你只需要告诉它：

- 数据集 `data.yaml` 在哪里。
- 从哪个基础模型开始训练。
- 训练多少轮。
- 图片尺寸多大。
- batch 多大。
- 输出目录叫什么。

### 5.1 推荐第一次微调用 yolo11s-seg.pt

你的电脑 8GB 显存，建议先用：

```text
yolo11s-seg.pt
```

如果显存不够，再换：

```text
yolo11n-seg.pt
```

### 5.2 推荐训练命令

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\yolo\train_yolo_seg.py `
  --data datasets\roboflow_lab_20260716\data.yaml `
  --model yolo11s-seg.pt `
  --epochs 80 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --workers 4 `
  --project outputs\yolo_runs\lab_roboflow_20260716 `
  --name yolo11s_seg_lab_ft_v1 `
  --patience 30 `
  --close-mosaic 10
```

参数解释，用最直白的话说：

```text
--data       你的 Roboflow 数据说明书 data.yaml
--model      从哪个模型开始学
--epochs     学多少轮
--imgsz      每张图缩放到多大后训练
--batch      一次喂给显卡几张图
--device     0 表示用第 0 块 NVIDIA 显卡；cpu 表示不用显卡
--workers    读取数据的并行数量
--project    输出放在哪个大目录
--name       本次训练名字
--patience   很久没提升就提前停
```

如果显存报错，先把 batch 从 4 降到 2：

```powershell
--batch 2
```

还不行再用 `yolo11n-seg.pt`。

### 5.3 训练输出在哪里

训练完成后，通常会生成：

```text
outputs/yolo_runs/lab_roboflow_20260716/yolo11s_seg_lab_ft_v1/
  weights/
    best.pt
    last.pt
  results.csv
  results.png
  confusion_matrix.png
  val_batch*_pred.jpg
```

最重要的是：

```text
outputs/yolo_runs/lab_roboflow_20260716/yolo11s_seg_lab_ft_v1/weights/best.pt
```

这个就是新训练好的模型。

建议复制一份到本地模型目录，命名清楚：

```powershell
New-Item -ItemType Directory -Force -Path local_models

Copy-Item `
  outputs\yolo_runs\lab_roboflow_20260716\yolo11s_seg_lab_ft_v1\weights\best.pt `
  local_models\waste11_lab_yolo11s_seg_20260716_best.pt
```

以后命令里就用这个新权重：

```text
local_models\waste11_lab_yolo11s_seg_20260716_best.pt
```

注意：`best.pt` 是模型权重，不建议提交 Git。

---

## 6. 第五步：训练前后对比怎么做

你需要准备一批“固定考试题”图片。比如：

```text
artifacts/windows_e4_capture/comparison_scene_001/rgb/C0_fixed_scene.jpg
artifacts/windows_e4_capture/comparison_scene_001/rgb/C1_variant_scene.jpg
```

这些图片不要参与训练。

### 6.1 用旧模型跑 comparison 图片

假设旧模型是：

```text
local_models/waste11_yolo11s_seg_best.pt
```

运行：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image artifacts\windows_e4_capture\comparison_scene_001\rgb\C0_fixed_scene.jpg `
  --weights local_models\waste11_yolo11s_seg_best.pt `
  --out artifacts\comparison_old_model\C0 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0
```

再跑 C1：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image artifacts\windows_e4_capture\comparison_scene_001\rgb\C1_variant_scene.jpg `
  --weights local_models\waste11_yolo11s_seg_best.pt `
  --out artifacts\comparison_old_model\C1 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0
```

输出里看几个文件：

```text
artifacts/comparison_old_model/C0/
  yolo_records.json
  vision_packet.json
  graph_snapshot.json
  events.jsonl
  graph.mmd
  prediction/
```

其中 `prediction/` 里是 YOLO 可视化结果。

### 6.2 用新模型跑同一批 comparison 图片

把 `--weights` 换成新模型：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image artifacts\windows_e4_capture\comparison_scene_001\rgb\C0_fixed_scene.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\comparison_new_model\C0 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0
```

C1 同理：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image artifacts\windows_e4_capture\comparison_scene_001\rgb\C1_variant_scene.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\comparison_new_model\C1 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0
```

你要比较：

- 旧模型漏检了几个，新模型是否少漏检。
- 旧模型错分类了几个，新模型是否改对。
- mask 边界是否更贴合物体。
- 置信度是否更稳定。
- 是否出现更多误检。

不要只看置信度高不高。置信度高但类别错、mask 错，也不是好结果。

---

## 7. 第六步：LLM 如何加入

### 7.1 LLM 在这里负责什么

LLM 不是用来替代 YOLO 的。

当前项目里的逻辑是：

```text
YOLO 先检测和分割物体
  -> 得到类别、置信度、mask、bbox
  -> 对低置信度或高风险类别，准备视觉证据
  -> LLM 只做复核：支持 / 证据不足 / 冲突
  -> 冲突或证据不足时进入人工复核
  -> KG 记录最终状态和复核原因
```

LLM 不应该随便新增类别。它只能在 11 类范围内检查 YOLO 结果是否可信。

### 7.2 LLM 配置文件在哪里

项目支持两种配置方式。

方式 A：写环境变量。适合临时运行。

方式 B：写本地配置文件。适合你自己电脑长期使用。

本地配置模板是：

```text
wastekg/local_llm_config.example.py
```

你可以复制一份：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

Copy-Item wastekg\local_llm_config.example.py wastekg\local_llm_config.py
```

然后打开：

```text
wastekg/local_llm_config.py
```

填写：

```python
API_KEY = "你的 API key"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-ai/DeepSeek-V4-Pro"
TIMEOUT = 30
TEMPERATURE = 0.0
MAX_TOKENS = 400
```

注意：

- `wastekg/local_llm_config.py` 不要提交 Git。
- 不要把 API key 发给别人。
- 如果你用的是中转站，`BASE_URL` 必须填中转站地址。
- 如果你用的是官方 key，`BASE_URL` 必须填官方地址。

### 7.3 检查 LLM 配置

先做不联网检查：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py
```

它会显示：

```text
base_url
model
api_key 的脱敏形式
timeout
temperature
max_tokens
```

如果要真正调用一次 API：

```powershell
.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py --live
```

成功会显示 `Live API check succeeded`。

### 7.4 单张图预测时加入 LLM

普通 YOLO + KG：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image artifacts\windows_e4_capture\comparison_scene_001\rgb\C0_fixed_scene.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\single_image_with_new_model\C0 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0
```

加入 LLM 复核，只多加一个参数：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image artifacts\windows_e4_capture\comparison_scene_001\rgb\C0_fixed_scene.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\single_image_with_new_model_llm\C0 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0 `
  --llm-review
```

代码层面发生了什么：

```text
scripts/graph/predict_image_to_graph.py
  -> YOLO.predict()
  -> wastekg.yolo.image_pipeline.records_from_yolo_result()
  -> wastekg.yolo.visual_review_evidence.attach_visual_evidence_to_records()
  -> wastekg.llm.reviewer.OpenAICompatibleReviewer.review()
  -> wastekg.perception.pipeline.apply_perception_records_to_graph()
  -> KnowledgeGraph.apply_observation()
  -> graph_snapshot.json / events.jsonl / graph.mmd / neo4j_import.cypher
```

再直白一点：

```text
1. 脚本拿图片。
2. YOLO 在图上找物体。
3. 对需要复核的物体，脚本裁出小图和 mask 证据。
4. LLM 看这些证据，判断 YOLO 的说法是否可靠。
5. 可靠就 accepted。
6. 不可靠或证据不足就 review_required / unknown。
7. 最后写入知识图谱。
```

---

## 8. 第七步：动作前后场景变化怎么加入知识图谱

你会补充“动作前”和“动作后”两张图片。例如：

```text
artifacts/action_change_inputs/scene001_before.jpg
artifacts/action_change_inputs/scene001_after.jpg
```

要求：

- 两张图最好固定相机视角。
- 光照尽量一致。
- 背景不要变化太大。
- 如果是机械臂动作，动作前后至少有一个物体位置、出现或消失发生变化。

### 8.1 使用哪个代码

使用这个新脚本：

```text
scripts/graph/predict_before_after_to_graph.py
```

它做四件事：

```text
1. 用你的新 YOLO best.pt 识别 before 图。
2. 用同一个 best.pt 识别 after 图。
3. 把 before 和 after 两帧都写入同一个 KnowledgeGraph。
4. 用同类别 IoU 匹配推断 persisted / removed_candidate / appeared_candidate。
```

### 8.2 不加 LLM 的运行命令

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\graph\predict_before_after_to_graph.py `
  --before artifacts\action_change_inputs\scene001_before.jpg `
  --after artifacts\action_change_inputs\scene001_after.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\before_after_graph\scene001 `
  --scene-id scene001 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0 `
  --iou-threshold 0.30
```

输出目录：

```text
artifacts/before_after_graph/scene001/
  before_yolo_records.json
  after_yolo_records.json
  vision_packets.json
  change_events.json
  change_summary.json
  graph_snapshot.json
  events.jsonl
  graph.mmd
  neo4j_import.cypher
  before_prediction/
  after_prediction/
```

你先看：

```text
change_summary.json
change_events.json
```

`change_summary.json` 会告诉你：

```text
before_detection_count
after_detection_count
persisted_count
removed_candidate_count
appeared_candidate_count
event_count
```

`change_events.json` 会列出类似：

```text
FRAME_OBSERVED
INSTANCE_PERSISTED
INSTANCE_REMOVED_CANDIDATE
INSTANCE_APPEARED_CANDIDATE
```

### 8.3 加入 LLM 复核的运行命令

前提是你已经配置好 LLM。

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\graph\predict_before_after_to_graph.py `
  --before artifacts\action_change_inputs\scene001_before.jpg `
  --after artifacts\action_change_inputs\scene001_after.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\before_after_graph\scene001_llm `
  --scene-id scene001 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0 `
  --iou-threshold 0.30 `
  --llm-review
```

这时脚本会在输出目录里生成：

```text
visual_evidence/
  before/
  after/
```

里面是给 LLM 看的裁剪图和 mask 证据。

### 8.4 它怎么实现 KG 更新

代码层面的流程是：

```text
scripts/graph/predict_before_after_to_graph.py
  -> before 图 YOLO predict
  -> after 图 YOLO predict
  -> records_from_yolo_result()
  -> 可选 attach_visual_evidence_to_records()
  -> 可选 OpenAICompatibleReviewer()
  -> apply_perception_records_to_graph(before)
  -> apply_perception_records_to_graph(after)
  -> match_image_sequence_detections()
  -> build_image_sequence_events()
  -> 导出 graph_snapshot.json / events.jsonl / change_events.json
```

从知识图谱角度看：

```text
before 图 = 一次观察 Observation
after 图  = 第二次观察 Observation

每次 Observation 会把当前画面里的对象实例写入 KG。
如果置信度低、类别有风险或 LLM 冲突，就记录 review_required / unknown。
然后脚本额外计算 before 和 after 的变化事件。
```

### 8.5 变化事件怎么理解

`INSTANCE_PERSISTED`：

```text
动作前后都看到了类似位置、类似类别的物体。
```

`INSTANCE_REMOVED_CANDIDATE`：

```text
动作前有，动作后没有匹配上。
可能是真的被拿走，也可能是被遮挡、漏检、光照变化导致没识别。
所以叫 candidate，需要人工或后续深度/多视角确认。
```

`INSTANCE_APPEARED_CANDIDATE`：

```text
动作后出现了动作前没匹配上的物体。
可能是新出现，也可能是位置变化太大、之前漏检。
```

当前固定 RGB 视角下，不要把 candidate 写成 100% 事实。论文或报告里应写“候选变化事件”或“系统检测到的变化线索”。

---

## 9. 第八步：同步到 Neo4j

### 9.1 先确认 Neo4j 可连接

Neo4j 密码通过环境变量传入：

```powershell
$env:WASTEKG_NEO4J_PASSWORD="你的Neo4j密码"
```

只检查连接：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\graph\sync_neo4j.py --check-only
```

### 9.2 动作前后图谱同步到 Neo4j

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_before_after_to_graph.py `
  --before artifacts\action_change_inputs\scene001_before.jpg `
  --after artifacts\action_change_inputs\scene001_after.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\before_after_graph\scene001_neo4j `
  --scene-id scene001 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0 `
  --llm-review `
  --sync-neo4j
```

脚本会把最终 KG 镜像同步到 Neo4j。

注意：当前 Neo4j 同步是“镜像写入”原型，不要把它当作长期数据库迁移工具。正式实验前建议每次用独立 `scene-id` 和独立输出目录，避免旧图谱状态混淆。

---

## 10. 第九步：输出给 UI

如果你要让 UI 看到最新 KG snapshot，可以加：

```powershell
--ui-snapshot ..\dynamic-waste-ui\public\kg-snapshot.json
```

完整命令示例：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

.\.venv\Scripts\python.exe scripts\graph\predict_before_after_to_graph.py `
  --before artifacts\action_change_inputs\scene001_before.jpg `
  --after artifacts\action_change_inputs\scene001_after.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\before_after_graph\scene001_ui `
  --scene-id scene001 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0 `
  --llm-review `
  --ui-snapshot ..\dynamic-waste-ui\public\kg-snapshot.json
```

然后进入 UI：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-ui
npm install
npm run dev
```

浏览器打开 UI 提示的本地地址。

---

## 11. 常见错误和处理

### 11.1 data.yaml 类别不对

表现：

```text
训练能跑，但预测类别乱。
```

原因：

```text
Roboflow 的类别顺序或类别名和项目 11 类不一致。
```

处理：

```text
回到 Roboflow 检查类别，重新导出。
不要手工硬改成看起来像 11 类但标签实际错位。
```

### 11.2 CUDA out of memory

表现：

```text
CUDA out of memory
```

处理顺序：

```text
1. batch 从 4 改 2。
2. imgsz 暂时保持 640，不要先改太大。
3. 模型从 yolo11s-seg.pt 改 yolo11n-seg.pt。
4. 关闭其他占 GPU 的程序。
```

### 11.3 LLM 401 或认证失败

常见原因：

```text
API key 错。
BASE_URL 和 API key 不匹配。
中转站 token 却用了官方 base_url。
官方 key 却用了中转站 base_url。
```

先运行：

```powershell
.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py
```

再运行：

```powershell
.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py --live
```

### 11.4 动作前后变化结果不准

可能原因：

```text
相机动了。
光照变化太大。
物体移动太远，IoU 匹配不上。
YOLO 漏检。
遮挡严重。
```

处理：

```text
1. 固定相机。
2. 固定光照。
3. 调低 --conf 到 0.10 或 0.15 看是否漏检减少。
4. 适当调低 --iou-threshold，例如 0.20。
5. 加 LLM 复核，但不要指望 LLM 修复所有检测漏检。
```

---

## 12. 推荐的一次完整实验命名

建议你每次都按日期命名，避免覆盖和混淆：

```text
datasets/roboflow_lab_20260716/
outputs/yolo_runs/lab_roboflow_20260716/yolo11s_seg_lab_ft_v1/
local_models/waste11_lab_yolo11s_seg_20260716_best.pt
artifacts/comparison_old_model_20260716/
artifacts/comparison_new_model_20260716/
artifacts/before_after_graph/scene001_20260716/
```

不要反复把不同实验都叫：

```text
test
new
final
best
```

这些名字后面一定会混。

---

## 13. 最小可执行清单

如果只保留最短操作，你按这个做：

1. Roboflow 标注实例分割，导出 YOLOv8 segmentation。
2. 放到：

```text
datasets/roboflow_lab_20260716/
```

3. 训练：

```powershell
.\.venv\Scripts\python.exe scripts\yolo\train_yolo_seg.py `
  --data datasets\roboflow_lab_20260716\data.yaml `
  --model yolo11s-seg.pt `
  --epochs 80 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --workers 4 `
  --project outputs\yolo_runs\lab_roboflow_20260716 `
  --name yolo11s_seg_lab_ft_v1
```

4. 复制新模型：

```powershell
Copy-Item `
  outputs\yolo_runs\lab_roboflow_20260716\yolo11s_seg_lab_ft_v1\weights\best.pt `
  local_models\waste11_lab_yolo11s_seg_20260716_best.pt
```

5. 检查 LLM：

```powershell
.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py --live
```

6. 跑动作前后 KG：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_before_after_to_graph.py `
  --before artifacts\action_change_inputs\scene001_before.jpg `
  --after artifacts\action_change_inputs\scene001_after.jpg `
  --weights local_models\waste11_lab_yolo11s_seg_20260716_best.pt `
  --out artifacts\before_after_graph\scene001 `
  --scene-id scene001 `
  --conf 0.25 `
  --imgsz 640 `
  --device 0 `
  --llm-review
```

7. 看结果：

```text
artifacts/before_after_graph/scene001/change_summary.json
artifacts/before_after_graph/scene001/change_events.json
artifacts/before_after_graph/scene001/graph_snapshot.json
artifacts/before_after_graph/scene001/events.jsonl
```

