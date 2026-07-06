# 2026.6.15 建筑垃圾分割数据合并与疑似石棉策略

记录日期：2026-06-15

本文记录本次对 `D:\可能有用的data\2026.6.15` 数据集的检查、合并方式、合并结果，以及图谱属性更新和疑似石棉处理策略。

---

## 1. 三组数据如何选择

原始目录包含三组数据：

```text
D:\可能有用的data\2026.6.15\Ground_Truths_COCO_Format
D:\可能有用的data\2026.6.15\Ground_Truths_VOC_Format
D:\可能有用的data\2026.6.15\Original_Images_and_Annotation_Files
```

本项目当前训练目标是 YOLO segmentation，因此优先采用 `Ground_Truths_COCO_Format`：

- 它包含 `annotations.json`；
- 标注中包含 polygon segmentation；
- 可稳定转换为 YOLO segmentation 标签；
- 与当前 `datasets/waste12_yolo` 的训练格式一致。

`Ground_Truths_VOC_Format` 更适合传统 XML 检测框流程，不是本次主选。`Original_Images_and_Annotation_Files` 可作为原始留档，不直接进入当前训练集。

---

## 2. 类别映射

原数据集类别为：

```text
concrete, fill dirt, timber, hard plastic, soft plastic,
steel, fabric, cardboard, plasterboard, skip bin
```

COCO 文件中的类别缩写为：

| COCO 类别 | 含义 | 本项目处理 |
|---|---|---|
| `CB` | concrete | 映射为 `concrete` |
| `WT` | timber | 映射为 `wood` |
| `HP` | hard plastic | 映射为 `hard_plastic` |
| `SP` | soft plastic | 映射为 `soft_plastic` |
| `ST` | steel | 映射为 `metal` |
| `CP` | cardboard | 映射为 `paperboard` |
| `PB` | plasterboard | 映射为 `gypsum_board` |
| `BIN` | skip bin | 忽略 |
| `FD` | fill dirt | 忽略 |
| `FB` | fabric | 忽略 |
| `_background_` | 背景 | 忽略 |

忽略 `BIN/FD/FB` 的原因是当前知识图谱没有这些实体类别。强行映射会污染训练集，影响后续机械臂任务规划。

---

## 3. 合并脚本

脚本位置：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\scripts\merge_cdw_coco_seg.py
```

执行命令：

```powershell
.\.venv\Scripts\python.exe scripts\merge_cdw_coco_seg.py `
  --coco-zip "D:\可能有用的data\2026.6.15\Ground_Truths_COCO_Format" `
  --target-root datasets\waste12_yolo
```

说明：参数名仍叫 `--coco-zip`，但脚本已经兼容 zip 文件和已解压目录。

---

## 4. 本次合并结果

新增数据：

| split | 新增图片 | 新增标签文件 | 新增对象 |
|---|---:|---:|---:|
| train | 336 | 336 | 3597 |
| val | 42 | 42 | 267 |
| test | 43 | 43 | 288 |

新增类别分布：

| split | concrete | wood | gypsum_board | metal | soft_plastic | hard_plastic | paperboard |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 286 | 689 | 133 | 608 | 665 | 413 | 803 |
| val | 1 | 109 | 3 | 34 | 54 | 40 | 26 |
| test | 19 | 55 | 25 | 53 | 44 | 29 | 63 |

合并后当前总数据：

| split | 图片数 | 对象数 | 说明 |
|---|---:|---:|---|
| train | 4109 | 87324 | 含原始数据、玻璃数据、2026.6.15 数据 |
| val | 1054 | 28874 | 含原始数据、玻璃数据、2026.6.15 数据 |
| test | 772 | 16447 | 含原始数据、玻璃数据、2026.6.15 数据 |

一致性检查结果：

```text
total_objects: 132645
cdw2026_objects: 4152
glassdebris_v5_objects: 2660
bad_rows: 0
```

`bad_rows: 0` 表示：

- 没有类别 ID 越界；
- 没有 bbox-only 标签混入；
- 所有合并标签均符合 YOLO segmentation polygon 格式。

---

## 5. 图谱属性更新

本次短期记忆层新增字段：

| 字段 | 含义 | 后续用途 |
|---|---|---|
| `mask_polygon` | 物体分割掩膜轮廓点 | 支撑精细定位与分割可视化 |
| `boundary_points` | 物体边界点 | 支撑边界引导抓取 |
| `visible_area_ratio` | 可见面积比例 | 判断遮挡程度 |
| `occlusion_state` | 遮挡状态 | 规划是否需要先移除遮挡物 |
| `grasp_candidates` | 候选抓取点列表 | 接入抓取检测或启发式抓取 |
| `safe_grasp_score` | 安全抓取得分 | 规划器排序和人机确认 |

长期知识层新增字段：

| 字段 | 含义 | 取值 |
|---|---|---|
| `handling_mode` | 处理方式策略 | `robot_grasp`, `robot_with_supervision`, `human_review`, `human_only` |
| `grasp_difficulty` | 夹爪抓取难度 | `low`, `medium`, `high` |

这些字段已经贯通：

```text
YOLO/大模型 JSON 记录
  -> VisionDetection
  -> DetectedObject
  -> ObjectInstance 短期记忆
  -> LangGraph/ROS2 规划出口
```

---

## 6. 疑似石棉不应作为普通 YOLO 类别处理

严谨结论：YOLO 不应该被设计为“确认石棉”的模型。

原因：

- 石棉本质上需要材料检测或专业判断，RGB 图像不能可靠确认；
- 它与 `gypsum_board`、fiber cement、旧瓦片、保温板、旧纤维板高度相似；
- 如果模型误判为可抓取普通建筑垃圾，会带来实际安全风险。

因此当前策略是：

1. YOLO 先识别普通视觉类别，例如 `gypsum_board`、`tile`、`foam`、`hard_plastic`；
2. 若类别属于高混淆集合，或置信度处于中间区间，则进入大模型复核；
3. 大模型只能输出“疑似石棉风险”或“需要人工确认”，不能作为最终安全鉴定；
4. 一旦进入 `asbestos_suspect`，图谱中设置：

```text
risk_level = high
pollution_level = high
handling_mode = human_only
grasp_difficulty = high
auto_processable = False
task_status = needs_review
```

规划器看到这些字段后，不应生成机械臂夹取动作，而应生成隔离、标记、等待人工处理的计划。

---

## 7. 什么时候交给大模型

当前代码中复核入口位于：

```text
wastekg/perception_pipeline.py
```

触发条件：

- 类别是 `glass`、`asbestos_suspect`、`gypsum_board`、`tile`、`metal`、`soft_plastic`、`hard_plastic`、`paperboard`、`foam`；
- 或 YOLO 置信度处于 `0.50 <= confidence < 0.85`。

后续接入真实多模态大模型时，只需要实现 `LightweightReviewer.review(...)` 接口，让它读取 YOLO crop 或原图局部区域，并返回：

```python
ReviewResult(
    class_name="asbestos_suspect",
    confidence=0.75,
    risk_hint="high",
    reason="外观呈灰白纤维状旧板材，与石膏板/纤维水泥板混淆，需人工确认",
    need_human_review=True,
)
```

这样记录会自动进入图谱，成为短期记忆和后续规划约束。

---

## 8. 推荐下一步训练

合并完成后，建议从当前较好的权重继续训练，而不是从头训练：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model runs\segment\runs\waste12_seg\yolo11n_seg_e50\weights\best.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_cdw_glass_e50
```

如果显存压力大：

```powershell
--batch 2
```

训练后重点观察：

- `glass` 是否明显提升；
- `gypsum_board` 是否提升；
- `metal`、`soft_plastic`、`paperboard` 是否改善；
- 原本强类如 `concrete/brick/tile` 是否下降；
- 是否出现 `gypsum_board` 与 `asbestos_suspect` 策略混乱。注意：当前不建议直接训练 `asbestos_suspect`，除非有可靠标注数据。

