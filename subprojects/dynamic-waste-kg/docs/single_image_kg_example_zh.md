# 单张实验室图片接入 KG 与 Neo4j 示例

本文以以下自采图片为例，说明“人工标注审计、旧模型推理、KG 状态生成、Neo4j 同步和 UI 查看”的完整顺序：

```text
E:\博论相关\test_my\My First Project.yolov11\train\images\
image_3-after_jpg.rf.7dUJB3BVukxkUS2Qgye8.jpg
```

## 1. 人工标注事实

对应 `data.yaml` 包含 9 类，当前图片的 8 个 mask 为：

| 类别 | 实例数 |
| --- | ---: |
| `glass` | 2 |
| `hard_plastic` | 1 |
| `paperboard` | 3 |
| `soft_plastic` | 1 |
| `wood` | 1 |

这些类别都属于 KG 的 11 类长期体系，但该数据集缺少 `gypsum_board` 和 `metal`，所以它只能作为实验室域适配数据，不能替代全局 11 类定义。

## 2. 旧模型实测结果

使用 `yolo11n_seg_waste11_grouped_e100_v1`、`conf=0.05` 推理后：

```text
人工标注实例：8
YOLO 候选：1
候选类别：paperboard
置信度：0.0551269
```

该 mask 覆盖了纸板和多个相邻物体，属于明显欠分割。正确 KG 状态是：

```text
Scene: image_3-after_jpg.rf.7dUJB3BVukxkUS2Qgye8
ObjectInstance: paperboard_01
yolo_confidence: 0.0551269
recognition_status: review_required
depth_valid_ratio: 0.0
occlusion_state: unknown
```

它只能生成低置信候选和 `DetectionEvent`，不能进入自动抓取。单张 RGB 图没有 D435i 深度，像素中心只保存在感知 metadata；`center_xyz_camera` 保持未知零值，不生成 `DepthUpdateEvent`，也不得用于机械臂动作。

## 3. 为什么不能直接把 8 个人工标签写成 YOLO 检测

人工标签是离线真值，YOLO 只检测到一个候选。把另外 7 个标签伪装为 `DetectionEvent` 会破坏事件来源和论文评估真实性。

正确用途是：

```text
人工标签 -> 计算漏检、错分和 mask 质量 -> 数据适配与后续训练
YOLO 输出 -> 当前运行时 KG 候选
人工复核当前候选 -> HumanReviewEvent
```

只有 YOLO/VLM/人工复核实际产生的运行时结论才能进入在线 KG。漏检对象应记录为模型误差，等待新模型重新推理后再进入 KG。

## 4. 当前已生成产物

```text
artifacts/single_image_graph/image_3_after_old_model/
  prediction/                 # 可视化预测
  yolo_records.json           # YOLO 原始候选
  vision_packet.json          # 感知契约摘要
  graph_snapshot.json         # 三层 KG 快照
  events.jsonl                # 事件流
  graph.mmd                   # Mermaid 图
  neo4j_import.cypher         # 离线 Cypher
```

## 5. 同步示例图到 Neo4j

首先导入 11 类、4 个备用实例、8 个事件和 38 条关系：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg

$authLine = Get-Content .env.neo4j | Where-Object { $_ -match '^NEO4J_AUTH=' } | Select-Object -First 1
$auth = $authLine.Substring('NEO4J_AUTH='.Length).Split('/', 2)
$env:WASTEKG_NEO4J_PASSWORD = $auth[1]

.\.venv\Scripts\python.exe scripts\graph\sync_neo4j.py --user $auth[0]

Remove-Item Env:WASTEKG_NEO4J_PASSWORD
```

脚本会输出内存同步计数和 Neo4j 在线计数。密码只进入当前 PowerShell 进程，不会被输出。

## 6. 把单图推理结果同步到 Neo4j 和 UI

```powershell
$image = 'E:\博论相关\test_my\My First Project.yolov11\train\images\image_3-after_jpg.rf.7dUJB3BVukxkUS2Qgye8.jpg'
$weights = 'outputs\yolo_runs\paper_e1\yolo11n_seg_waste11_grouped_e100_v1\weights\best.pt'

.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image $image `
  --weights $weights `
  --out artifacts\single_image_graph\image_3_after_old_model `
  --conf 0.05 `
  --imgsz 640 `
  --device 0 `
  --sync-neo4j `
  --ui-snapshot ..\dynamic-waste-ui\public\data\kg-snapshot.json

Remove-Item Env:WASTEKG_NEO4J_PASSWORD
```

注意：第二次同步采用 `MERGE`，11 个长期类别不会重复创建；图片 Scene、`paperboard_01`、事件和关系会加入数据库。当前脚本以单张图片构建独立内存图，因此相同 `instance_id` 只适用于这个独立 Scene 示例。正式连续运行必须由长期进程中的 `KnowledgeGraph` 负责跨帧跟踪。

## 7. 查看结果

Neo4j Browser：

```text
http://localhost:7474
```

```cypher
MATCH p=(s:Scene)-[:CONTAINS]->(i:ObjectInstance)-[:CANDIDATE_OF]->(c:WasteCategory)
RETURN p;

MATCH p=(e:Event)-[r]->(target)
RETURN p ORDER BY e.event_time DESC;
```

UI：

```powershell
cd ..\dynamic-waste-ui
npm.cmd run dev
```

打开 `http://127.0.0.1:5173/?view=kg`。长期知识层显示 11 类，短期记忆层显示当前 Scene 和实例，事件层显示候选如何写入和关联。

## 8. 后续实验顺序

这张图后续属于训练域数据，不能再用于新模型的独立测试。建议保留另外一组从未进入训练的实验室图片作为验证/测试集。

```text
补拍和标注实验室图片
  -> 按物体/拍摄序列分组切分，避免相邻帧泄漏
  -> 用户自行执行增量训练
  -> 在独立 holdout 上比较召回率和 mask 质量
  -> 重新运行本文件第 6 节命令
  -> 新模型候选进入 KG
  -> 人工复核后再允许规划器读取
```
