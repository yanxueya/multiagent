# Glass Debris 数据合并记录

记录日期：2026-06-15

本文件记录外部玻璃碎片数据集如何合并到当前 `waste12_yolo` 训练集。

---

## 1. 外部数据来源

源数据路径：

```text
D:\可能有用的data\有用_Glass Debris Detection.v5-not_glass-dataset.yolov11
```

Roboflow 元数据：

- workspace：`fypgik`
- project：`glass-debris-detection`
- version：5
- license：CC BY 4.0
- classes：`Glass`、`Not Glass`
- format：YOLOv11 segmentation
- images：351
- preprocessing：640x640 stretch
- augmentation：水平翻转、曝光扰动、高斯模糊

---

## 2. 为什么选择这组数据

相比之前检查过的玻璃数据，这组更适合当前研究：

- 有 `train`、`valid`、`test` 三个划分；
- 是 YOLO segmentation polygon，不是普通检测框；
- 图片中包含玻璃碎片和非玻璃干扰物；
- 场景比白底玻璃器皿、完整玻璃杯更接近废弃物识别；
- 许可证为 CC BY 4.0，后续论文可说明来源。

需要注意：

- 它仍然不是严格的建筑垃圾现场数据；
- 它包含 `Not Glass` 类，不能直接并入当前 11 类视觉体系；
- 合并时只保留 `Glass`，丢弃 `Not Glass` 标注。

---

## 3. 类别映射

外部数据：

| 原 class id | 原类别 |
|---:|---|
| 0 | Glass |
| 1 | Not Glass |

当前 `waste12_yolo`：

| 当前 class id | 当前类别 |
|---:|---|
| 10 | glass |

合并规则：

```text
外部 class 0 Glass -> 当前 class 10 glass
外部 class 1 Not Glass -> 过滤，不写入标签
```

这样做的原因：

- 当前知识图谱和 YOLO 数据集只有 12 个研究类别；
- `Not Glass` 不是研究实体；
- 如果把 `Not Glass` 当成新类，会破坏当前类别体系；
- 如果保留为其他类别，会引入错误监督。

---

## 4. 合并结果

合并脚本：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\scripts\merge_external_glass_seg.py
```

执行命令：

```powershell
.\.venv\Scripts\python.exe scripts\merge_external_glass_seg.py `
  --source-root "D:\可能有用的data\有用_Glass Debris Detection.v5-not_glass-dataset.yolov11" `
  --target-root datasets\waste12_yolo `
  --source-glass-class 0 `
  --target-glass-class 10 `
  --prefix glassdebris_v5
```

合并后新增：

| split | 新增图片 | 新增 glass 对象 |
|---|---:|---:|
| train | 309 | 2331 |
| val | 28 | 220 |
| test | 14 | 109 |

合并后总数据：

| split | 图片数 | 对象数 | glass 对象数 |
|---|---:|---:|---:|
| train | 3773 | 83727 | 2331 |
| val | 1012 | 28607 | 220 |
| test | 729 | 16159 | 109 |

合并检查：

```text
train glass_files 309 glass_objs 2331 bad 0
val glass_files 28 glass_objs 220 bad 0
test glass_files 14 glass_objs 109 bad 0
```

其中 `bad 0` 表示：

- 没有残留外部 class 1；
- 没有 bbox-only 标签；
- 所有合并标签均为 YOLO segmentation polygon；
- 所有合并标签均已映射为 class 10。

---

## 5. 文件命名

为避免和原数据重名，所有外部 glass 数据都加了前缀：

```text
glassdebris_v5_train_...
glassdebris_v5_valid_...
glassdebris_v5_test_...
```

例如：

```text
datasets\waste12_yolo\images\train\glassdebris_v5_train_extra_image_11_jpeg...
datasets\waste12_yolo\labels\train\glassdebris_v5_train_extra_image_11_jpeg...
```

---

## 6. 后续训练建议

现在 `glass` 已经有正样本，可以重新训练 YOLO segmentation。

建议优先从当前已有的较好权重继续微调：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model outputs\yolo_runs\segment\outputs\yolo_runs\waste12_seg\yolo11n_seg_e50\weights\best.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_glass_e50
```

如果显存或页面文件压力较大：

```powershell
--batch 2
```

训练后重点观察：

- `glass` 的 Mask mAP50；
- `glass` 的 Mask mAP50-95；
- `glass` 是否和 `hard_plastic`、`soft_plastic`、`gypsum_board` 混淆；
- 原有强类别是否下降，例如 `brick`、`tile`、`concrete`。

---

## 7. 图谱使用策略

即使加入 glass 训练，图谱中仍不应把 glass 当作普通安全抓取物。

建议策略：

```text
class_name = glass
risk_level = medium
fragility = high
graspability = low
need_human_review = True
handling_mode = robot_with_supervision
```

规划时：

- 可以识别并写入图谱；
- 可以作为危险/易碎对象提高处理优先级；
- 不建议直接自动夹取；
- 需要结合深度、边界、抓取点和人工确认。

---

## 8. 结论

这组 `Glass Debris Detection` 数据已经可以作为当前 `glass` 类的第一批可训练 segmentation 数据。

它的价值：

- 补上当前 `glass` 无正样本的问题；
- 支持 YOLO segmentation 而不是只有检测框；
- 让图谱可以从“玻璃只能人工复核”过渡到“玻璃候选可被模型发现，再复核”。

它的限制：

- 仍然不是完整建筑垃圾域数据；
- 样本数量相对其他大类仍少；
- 不能取消 glass 的人工复核和安全约束。
