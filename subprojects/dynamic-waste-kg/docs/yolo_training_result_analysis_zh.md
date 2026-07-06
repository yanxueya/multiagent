# YOLO 分割训练结果解读与优化方案

记录日期：2026-06-12

本文件记录第一次 YOLO11n-seg 训练结果，并给出后续优化方向。

---

## 1. 本次训练配置

训练命令核心参数：

- 模型：`yolo11n-seg.pt`
- 任务：segmentation
- 数据集：`datasets/waste12_yolo/data.yaml`
- epoch：3
- image size：640
- batch：4
- device：0
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU
- PyTorch：`2.12.0.dev20260408+cu128`
- CUDA runtime：12.8

权重文件：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_baseline\weights\best.pt
```

训练结果图：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_baseline\results.png
```

---

## 2. 总体结果

第 3 个 epoch 的整体验证指标：

| 指标 | Box | Mask |
|---|---:|---:|
| Precision | 0.743 | 0.736 |
| Recall | 0.656 | 0.648 |
| mAP50 | 0.717 | 0.701 |
| mAP50-95 | 0.591 | 0.519 |

解释：

- `Precision` 表示模型预测出来的目标里有多少是真的。
- `Recall` 表示真实目标里有多少被模型找到了。
- `mAP50` 是宽松标准下的平均精度，适合判断“能不能大致识别出来”。
- `mAP50-95` 是更严格标准，适合判断定位和分割边界是否精细。
- 对本项目而言，Mask mAP50 比 Box mAP50 更重要，因为后续机械臂抓取需要更准确的目标区域。

当前结论：

- 3 个 epoch 已经能跑通完整训练流程。
- 指标在 3 个 epoch 内持续上升，说明模型还没有训练充分。
- 当前结果可以用于流程验证，但还不适合作为最终机械臂抓取模型。

---

## 3. 训练过程变化

| Epoch | Box mAP50 | Box mAP50-95 | Mask mAP50 | Mask mAP50-95 |
|---:|---:|---:|---:|---:|
| 1 | 0.438 | 0.342 | 0.424 | 0.284 |
| 2 | 0.652 | 0.524 | 0.639 | 0.463 |
| 3 | 0.717 | 0.591 | 0.701 | 0.519 |

解释：

- 从 epoch 1 到 epoch 3，mAP 提升很明显。
- loss 也在下降，说明模型还在有效学习。
- 只训练 3 个 epoch 明显不够，后续可以训练 30、50、80 个 epoch。

---

## 4. 各类别表现

验证集类别指标如下，重点看 Mask mAP50 和 Mask mAP50-95。

| 类别 | 实例数 | Mask Precision | Mask Recall | Mask mAP50 | Mask mAP50-95 | 评价 |
|---|---:|---:|---:|---:|---:|---|
| concrete | 9967 | 0.891 | 0.823 | 0.901 | 0.644 | 强 |
| brick | 372 | 0.918 | 0.872 | 0.934 | 0.772 | 很强 |
| tile | 346 | 0.782 | 0.880 | 0.883 | 0.750 | 很强 |
| wood | 2277 | 0.716 | 0.678 | 0.721 | 0.535 | 中等 |
| gypsum_board | 276 | 0.727 | 0.888 | 0.863 | 0.768 | 很强 |
| foam | 295 | 0.529 | 0.437 | 0.483 | 0.388 | 弱 |
| metal | 5744 | 0.704 | 0.417 | 0.504 | 0.234 | 弱 |
| soft_plastic | 1239 | 0.565 | 0.300 | 0.366 | 0.187 | 很弱 |
| hard_plastic | 6358 | 0.817 | 0.693 | 0.778 | 0.516 | 较强 |
| paperboard | 1508 | 0.718 | 0.487 | 0.575 | 0.358 | 偏弱 |

当前强类别：

- `brick`
- `tile`
- `gypsum_board`
- `concrete`
- `hard_plastic`

当前弱类别：

- `soft_plastic`
- `metal`
- `foam`
- `paperboard`

需要特别注意：

- 当前训练数据没有 `glass` 正样本。
- 当前训练数据没有 `asbestos_suspect` 正样本。
- 所以模型现在不能可靠识别 `glass` 和 `asbestos_suspect`。
- 这两个类别后续应通过补充数据、大模型复核或人工确认处理。

---

## 5. 为什么有些类别弱

### 5.1 soft_plastic

可能原因：

- 外观变化大；
- 边界不规则；
- 容易和 hard_plastic、paperboard、foam 混淆；
- 分割边界难学。

处理策略：

- 增加 soft_plastic 样本；
- 检查标注是否一致；
- 训练时延长 epoch；
- 后续接大模型复核。

### 5.2 metal

可能原因：

- 金属类别内部差异很大；
- 管件、片状物、杆状物、反光表面可能差异明显；
- 与 hard_plastic、concrete 边界混淆。

处理策略：

- 检查 metal 标签是否过宽；
- 若后续研究需要，可把 metal 保持为一个大类，但通过图谱属性补充风险和抓取难度；
- 不建议现在把 metal 继续细分，否则数据量和标注成本会上升。

### 5.3 foam

可能原因：

- 样本量较少；
- 外观可能接近 gypsum_board 或 soft_plastic；
- 目标可能小且边界不稳定。

处理策略：

- 增加样本；
- 训练更久；
- 必要时提高图片尺寸到 768，但显存压力会增加。

### 5.4 paperboard

可能原因：

- 与 wood、soft_plastic、hard_plastic 在脏污环境中容易混淆；
- 折叠、遮挡、变形多。

处理策略：

- 增加脏污纸板样本；
- 使用低置信度复核机制；
- 后续图谱中保持 `need_human_review` 字段。

---

## 6. 下一轮训练建议

### 6.1 小步验证训练

先跑 10 个 epoch，确认训练稳定：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11n-seg.pt `
  --epochs 10 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_e10
```

如果显存不够：

```powershell
--batch 2
```

### 6.2 正式基线训练

如果 10 个 epoch 稳定，再跑 50 个 epoch：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11n-seg.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_e50
```

### 6.3 更高精度训练

如果 `yolo11n-seg.pt` 收敛后仍然不够，再尝试 `yolo11s-seg.pt`：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11s-seg.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 2 `
  --device 0 `
  --name yolo11s_seg_e50
```

说明：

- `yolo11n` 更快，适合流程验证。
- `yolo11s` 更准，但更吃显存。
- 你的显存约 8 GB，`yolo11s-seg` 建议先用 `batch 2`。

---

## 7. 和知识图谱的衔接策略

当前模型输出不能直接全信任，需要按置信度进入图谱：

| 情况 | 图谱处理 |
|---|---|
| 高置信度且非危险类别 | 直接创建或更新实例节点 |
| 低置信度类别 | 写入图谱，但标记 `need_human_review=True` |
| `soft_plastic`、`foam`、`metal`、`paperboard` | 降低自动决策权重，优先复核 |
| `glass`、`asbestos_suspect` | 当前不依赖 YOLO 自动确认，必须复核或人工确认 |
| 位置和深度可靠 | 可用于规划候选 |
| 类别不可靠但空间可靠 | 可作为未知物体进入短期记忆 |

建议阈值：

- `confidence >= 0.75`：可自动写入图谱；
- `0.45 <= confidence < 0.75`：写入图谱，但需要复核；
- `confidence < 0.45`：只作为候选观测，不进入自动规划；
- 危险类别或未知类别：无论置信度多少，都进入复核流程。

---

## 8. 当前最重要的优化方向

优先级从高到低：

1. 先训练 10 个 epoch，确认指标继续上升；
2. 再训练 50 个 epoch，形成第一个可用基线；
3. 对弱类别检查数据标注，特别是 `soft_plastic`、`metal`、`foam`、`paperboard`；
4. 补充 `glass` 数据；
5. `asbestos_suspect` 不建议依赖普通视觉数据直接判断，应作为疑似危险类别，优先人工确认；
6. 把 `best.pt` 接入 `perception_pipeline`，让 YOLO 结果写入知识图谱；
7. 后续再加入轻量多模态复核模型。

---

## 9. 结论

本次训练是成功的流程验证。模型已经能学习到建筑垃圾目标的检测和分割特征，但由于只训练 3 个 epoch，不能作为最终模型。

当前可用结论：

- 训练环境可用；
- RTX 5060 GPU 可用；
- YOLO11n-seg 可正常训练；
- 数据集格式可用；
- 10 类已有正样本可以训练；
- `glass` 和 `asbestos_suspect` 需要后续补数据或复核；
- 下一步应训练 10-50 个 epoch，并重点关注弱类别。
