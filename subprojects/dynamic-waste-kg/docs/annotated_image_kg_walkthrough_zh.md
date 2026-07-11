# 三张人工标注图片的知识图谱构建与事件流示例

本文使用用户已完成的 YOLO 分割标注构建可复现知识图谱示例。脚本不运行 YOLO 推理、不训练模型，也不把假定置信度伪装成模型实测结果。

## 1. 输入与证据边界

数据集类别映射来自：

```text
E:\博论相关\test_my\My First Project.yolov11\data.yaml
```

示例使用：

```text
动作前：image_3-after_jpg.rf.7dUJB3BVukxkUS2Qgye8.jpg
动作后：image_2-after1_jpg.rf.ytuqfrBe5Um00sPjnTJd.jpg
低置信复核：259650ef49ebae050d60dd52614b5c02_jpg.rf.uPUYawnIXxEblhooyu00.jpg
```

证据等级：

| 内容 | 来源 | 能否作为实测结果 |
| --- | --- | --- |
| 类别、polygon、bbox | 人工 YOLO 标注 | 可以作为人工标注事实 |
| 高置信实例 `0.90` | 用户指定的演示假设 | 不可以作为模型置信度结果 |
| 纸板 `0.50` | 用户指定的低置信演示假设 | 不可以作为模型置信度结果 |
| `ExecutionEvent` | 未来机器人闭环的说明性夹具 | 不可以证明真实机械臂执行成功 |
| 深度、遮挡、NEAR | 三张图没有 D435i 深度 | 本示例不生成 `DepthUpdateEvent` 或 `NEAR` |

## 2. 长期知识层

构建开始时只导入 11 个 `WasteCategory` 种子。`unknown` 不导入长期类别。每个类别包含：

```text
category_name
risk_level
fragility
graspability_prior
vlm_review_policy
default_handling_policy
visual_prototype
```

`graspability_prior` 的 schema 为 `low / medium / high`；当前 11 类没有使用 `high`。

## 3. 动作前场景 image_3

标注包含 8 个实例：

```text
glass=2
hard_plastic=1
paperboard=3
soft_plastic=1
wood=1
```

创建 `Scene(scene_id=scn_action_before)`。每行标注创建或更新一个 `ObjectInstance`，并生成：

```text
Scene -[:CONTAINS]-> ObjectInstance
ObjectInstance -[:CANDIDATE_OF]-> WasteCategory
ObjectInstance -[:CONFIRMED_AS]-> WasteCategory
DetectionEvent -[:IN_SCENE]-> Scene
DetectionEvent -[:DETECTED]-> ObjectInstance
DetectionEvent -[:PROPOSED]-> WasteCategory
```

由于这些标签在本示例中被明确视为已审核标注，实例设为 `recognition_status=accepted`。这不是 YOLO 在 `0.90` 时自动获得人工真值的通用规则。

## 4. 单步动作和动作后场景

严格按当前 LangGraph 单步规划规则，示例只把硬塑料实例 `ins_labexample_06` 归因给一次动作：

```text
PlanningEvent(robot_grasp)
  -[:IN_SCENE]-> scn_action_before
  -[:SELECTS]-> ins_labexample_06
  -> task_status=processing

ExecutionEvent(success)
  -[:IN_SCENE]-> scn_action_before
  -[:EXECUTES_ON]-> ins_labexample_06
  -> attempt_count += 1
  -> task_status=completed
  -> 强制重新采集场景
```

随后创建 `Scene(scene_id=scn_action_after)`，从 `image_2` 的 5 个标注重新生成检测事件：

```text
glass=1
hard_plastic=0
paperboard=2
soft_plastic=1
wood=1
```

其中 5 个持续出现对象使用相同 track id 映射到原实例。硬塑料目标不再出现，与说明性执行结果一致。

同时还有一个玻璃实例和一个 paperboard 标注未继续出现。由于系统每次只能执行一个物理动作，而且两张图之间缺少中间 Scene，这两个变化只能记录为“动作后未继续观测”，不能标记为机器人成功处理。要证明硬塑料和玻璃分别经过两次动作，必须补拍：

```text
Scene 0：两者都存在
-> 动作 1
Scene 1：仅第一个目标消失
-> 动作 2
Scene 2：第二个目标消失
```

## 5. 低置信纸板人工复核

第三张图的人工标注为：

```text
paperboard=1，演示置信度 0.50
foam=1，演示置信度 0.90
```

纸板满足 `review_threshold <= 0.50 < accept_threshold`。本示例按用户指定直接进入人工复核：

```text
DetectionEvent
-> ObjectInstance.recognition_status=review_required
-> ObjectInstance.vlm_consistency=not_checked
-> ObjectInstance.current_handling_policy=human_review_required

HumanReviewEvent(confirm_existing, paperboard)
  -[:REVIEWS]-> ObjectInstance
  -[:CONFIRMS]-> WasteCategory(paperboard)
-> recognition_status=accepted
-> 创建 CONFIRMED_AS
-> current_handling_policy=auto_allowed
```

这里没有创建 `VLMReviewEvent`，因为示例明确选择人工复核且没有调用 VLM。真实运行中，`0.30–0.75` 候选通常先按策略调用 VLM；VLM 不可用、人工强制介入或策略要求时进入人工审核。

## 6. 当前夹具实际产生的事件

```text
DetectionEvent  15
PlanningEvent    1
ExecutionEvent   1
HumanReviewEvent 1
总计             18
```

七类事件的 schema 仍全部存在。没有真实触发的 `VLMReviewEvent`、`DepthUpdateEvent` 和 `KnowledgeEvolutionEvent` 不生成占位业务事件。

## 7. 运行和导入

只生成 JSON、JSONL 和 Cypher：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\graph\build_annotated_kg_examples.py `
  --dataset-root "E:\博论相关\test_my\My First Project.yolov11" `
  --output-dir "paper_experiments\results\annotated_kg_examples"
```

同步到当前 Neo4j：

```powershell
$env:WASTEKG_NEO4J_PASSWORD="<你的密码>"
.\.venv\Scripts\python.exe scripts\graph\build_annotated_kg_examples.py `
  --dataset-root "E:\博论相关\test_my\My First Project.yolov11" `
  --output-dir "paper_experiments\results\annotated_kg_examples" `
  --sync-neo4j
```

输出目录中的 `manifest.json` 明确记录所有假设和不能归因的场景变化；`kg_snapshot.json` 包含三层业务数据和完整 schema；`events.jsonl` 是事件追加流；`neo4j_import.cypher` 用于离线检查。

## 8. 后续补拍与模型更新流程

1. 固定相机位姿、工作台和光照，先拍动作前 RGB-D。
2. 保存 RGB、深度、标注和 Scene id；不要只保留裁剪图。
3. 每次只移动一个实例，立即补拍一张新 Scene。
4. 对新图完成 polygon 和类别标注；保留同一对象的 track id 对应关系。
5. 将新增图按采集序列分组后再划分 train/val/test，禁止相邻帧跨集合泄漏。
6. 训练前显式检查 8 GB 显存；训练命令由用户在本机执行，代理不在沙盒启动训练。
7. 用独立实验室验证集重新确定各类别 `accept_threshold`，不要默认所有类别都使用统一 0.75。
8. 新模型通过验证后，再用真实 YOLO 输出替换本示例中的 `0.90/0.50` 假设值。
9. 接入 D435i 后才写入 `DepthUpdateEvent`、三维中心、可见尺寸、遮挡和 `NEAR`。
10. 接入 ROS2/PiPER 后，只有真实物理动作开始才能创建可作为执行证据的 `ExecutionEvent`。
