# YOLO11n-seg 50 Epoch 训练检查报告

记录日期：2026-06-14

本文件记录 `yolo11n_seg_e50` 这次训练的实际结果。

---

## 1. 重要结论

这次训练目录名称是 `yolo11n_seg_e50`，配置文件中目标 epoch 是 50，但 `results.csv` 实际只记录到 epoch 40。

因此当前不能严格称为“完整 50 epoch 训练完成”，更准确的说法是：

> 已完成并保存到第 40 轮，最佳模型出现在第 38 轮。

当前 GPU 中仍能看到一个从训练开始时间启动的 `python.exe` 进程占用显存，说明训练进程可能没有完全退出，或者卡在后处理/最终绘图/验证阶段。

---

## 2. 训练配置

训练目录：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_e50
```

权重文件：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_e50\weights\best.pt
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_e50\weights\last.pt
```

主要配置：

- 模型：`yolo11n-seg.pt`
- 数据集：`datasets/waste12_yolo/data.yaml`
- 目标 epoch：50
- 实际记录 epoch：40
- batch：4
- imgsz：640
- device：0
- AMP：开启

---

## 3. 当前最佳指标

按 Mask mAP50-95 选择，最佳 epoch 是第 38 轮。

| 指标 | 数值 |
|---|---:|
| Box Precision | 0.82252 |
| Box Recall | 0.75198 |
| Box mAP50 | 0.80376 |
| Box mAP50-95 | 0.68528 |
| Mask Precision | 0.82421 |
| Mask Recall | 0.74244 |
| Mask mAP50 | 0.79230 |
| Mask mAP50-95 | 0.59175 |

第 40 轮最后记录：

| 指标 | 数值 |
|---|---:|
| Box mAP50 | 0.79913 |
| Box mAP50-95 | 0.67908 |
| Mask mAP50 | 0.78673 |
| Mask mAP50-95 | 0.58282 |

说明：

- 第 38 轮略优于第 40 轮；
- `best.pt` 应优先使用；
- 模型在 30-40 轮附近进入平台期，但还不能确定是否完全收敛。

---

## 4. 与 3 Epoch 基线对比

| 指标 | 3 epoch | 当前最佳 epoch 38 | 提升 |
|---|---:|---:|---:|
| Box Precision | 0.74347 | 0.82252 | +0.07905 |
| Box Recall | 0.65551 | 0.75198 | +0.09647 |
| Box mAP50 | 0.71650 | 0.80376 | +0.08726 |
| Box mAP50-95 | 0.59076 | 0.68528 | +0.09452 |
| Mask Precision | 0.73623 | 0.82421 | +0.08798 |
| Mask Recall | 0.64799 | 0.74244 | +0.09445 |
| Mask mAP50 | 0.70089 | 0.79230 | +0.09141 |
| Mask mAP50-95 | 0.51876 | 0.59175 | +0.07299 |

结论：

- 继续训练明显提升了效果；
- 提升最明显的是召回率和严格定位精度；
- 当前模型比 3 epoch 基线更适合接入知识图谱做感知输入。

---

## 5. 当前异常

尝试重新验证 `best.pt` 时出现：

```text
WinError 1455 页面文件太小，无法完成操作。
Error loading cufft64_11.dll
```

同时 `nvidia-smi` 显示仍有训练相关 Python 进程占用 GPU：

```text
C:\Python314\python.exe
```

这说明当前系统内存、页面文件或残留训练进程会影响后续验证和训练。

---

## 6. 建议处理

第一步：回到你启动训练的 PowerShell 窗口，看它是否已经返回命令提示符。

如果没有返回，说明训练进程还在运行或卡住：

- 可以先等待几分钟；
- 如果长时间不动，可以按 `Ctrl + C` 停止；
- 停止后重新运行 `nvidia-smi`，确认 Python 进程消失。

第二步：关闭占用较大的软件：

- 浏览器大量标签页；
- QQ 音乐；
- 远控软件；
- Word/PowerPoint；
- 不必要的 Python 进程。

第三步：重新验证 `best.pt`：

```powershell
.\.venv\Scripts\python.exe -c "from ultralytics import YOLO; model=YOLO(r'runs\segment\runs\waste12_seg\yolo11n_seg_e50\weights\best.pt'); model.val(data=r'datasets\waste12_yolo\data.yaml', split='val', imgsz=640, batch=2, device=0, project=r'runs\waste12_val', name='e50_best_val', plots=True)"
```

这里建议用 `batch=2`，降低内存压力。

第四步：如果还报页面文件太小，应增加 Windows 虚拟内存。

建议虚拟内存：

- 初始大小：32768 MB
- 最大大小：65536 MB

---

## 7. 是否继续训练

当前不建议立刻继续训练到更大模型。

建议顺序：

1. 先处理残留 Python 进程和页面文件问题；
2. 用 `best.pt` 完整跑一次验证；
3. 如果验证正常，再从 `last.pt` resume 或重新训练一个完整 50 epoch；
4. 如果 `yolo11n` 平台期明显，再尝试 `yolo11s-seg.pt`。

当前最佳权重已经有使用价值，可作为知识图谱感知入口的第一个模型。

---

## 8. 按类别验证结果

2026-06-15 已使用 `best.pt` 重新完成验证，命令使用 `batch=1` 降低显存和页面文件压力。

验证权重：

```text
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_e50\weights\best.pt
```

验证输出：

```text
C:\Users\12279\Documents\multiagent\runs\segment\runs\waste12_val\e50_best_val_b1
```

整体指标：

| 指标 | Box | Mask |
|---|---:|---:|
| Precision | 0.825 | 0.824 |
| Recall | 0.752 | 0.742 |
| mAP50 | 0.804 | 0.792 |
| mAP50-95 | 0.686 | 0.588 |

按类别指标：

| 类别 | Images | Instances | Box mAP50 | Box mAP50-95 | Mask mAP50 | Mask mAP50-95 | 评价 |
|---|---:|---:|---:|---:|---:|---:|---|
| concrete | 624 | 9967 | 0.933 | 0.782 | 0.922 | 0.677 | 强 |
| brick | 86 | 372 | 0.948 | 0.907 | 0.948 | 0.798 | 很强 |
| tile | 84 | 346 | 0.958 | 0.924 | 0.954 | 0.822 | 很强 |
| wood | 653 | 2277 | 0.792 | 0.665 | 0.792 | 0.598 | 中等偏强 |
| gypsum_board | 30 | 276 | 0.908 | 0.880 | 0.908 | 0.816 | 很强，但样本图像少 |
| foam | 49 | 295 | 0.723 | 0.648 | 0.719 | 0.566 | 中等，明显提升 |
| metal | 500 | 5744 | 0.703 | 0.501 | 0.661 | 0.336 | 偏弱，分割边界差 |
| soft_plastic | 469 | 1239 | 0.549 | 0.344 | 0.520 | 0.304 | 弱 |
| hard_plastic | 623 | 6358 | 0.838 | 0.683 | 0.823 | 0.531 | 较强 |
| paperboard | 496 | 1508 | 0.688 | 0.527 | 0.672 | 0.429 | 中等偏弱 |

结论：

- 最可靠类别：`tile`、`brick`、`gypsum_board`、`concrete`。
- 可用但仍需改进：`hard_plastic`、`wood`、`foam`、`paperboard`。
- 当前弱类别：`soft_plastic`、`metal`。
- `glass` 和 `asbestos_suspect` 当前没有正样本，因此不应宣称模型能识别这两类。

---

## 9. 缺失类别处理策略

### 9.1 glass

`glass` 建议先补数据，再让在线大模型复核。

理由：

- 玻璃是可见类别，普通 RGB 图像中可以通过透明、反光、破碎边缘、形状等视觉线索学习；
- TACO、ZeroWaste 等废弃物数据集方向中包含玻璃、金属、纸、塑料等废弃物类别或相关场景；
- 直接只用在线大模型会导致结果不可复现，论文实验也难以量化；
- 更好的做法是先收集和筛选可训练数据，把 `glass` 做成 YOLO 可检测类别，再让大模型处理低置信度和疑难样本。

建议路线：

1. 先找 `glass bottle`、`broken glass`、`glass waste`、`construction glass debris` 相关数据；
2. 只保留与建筑废弃物或混合废弃物场景相近的图片；
3. 如果数据只有检测框，可以先训练 detection；如果有 mask，再训练 segmentation；
4. 加入数据后重新统计类别分布，避免 `glass` 样本过少；
5. 训练后仍将玻璃设置为中风险、低可抓握，规划时优先复核。

### 9.2 asbestos_suspect

`asbestos_suspect` 不建议直接作为普通 YOLO 确定类别训练。

理由：

- 石棉是否存在通常不能只靠 RGB 图像可靠确认；
- 外观上可能与石膏板、保温材料、纤维水泥板、旧瓦片等混淆；
- 如果模型把普通材料误判为石棉，会影响任务效率；
- 如果模型漏判真实疑似石棉，会带来安全风险；
- 对机器人系统来说，它更适合表示为“疑似危险物”，不是“确定石棉”。

建议路线：

1. 保留图谱实体 `asbestos_suspect`，但定义为疑似类别；
2. YOLO 只负责检测可能相关的候选物，如板材、纤维状材料、破损旧建材；
3. 在线多模态大模型或人工复核负责判断是否进入 `asbestos_suspect`；
4. 一旦进入 `asbestos_suspect`，任务规划默认不让机械臂自动夹取；
5. 图谱中设置 `risk_level=high`、`needs_llm_review=True`、`auto_processable=False`、`handling_mode=human_only`。

---

## 10. 外部数据源初步判断

已初步检索到的方向：

- TACO：面向 litter/waste 的检测与分割数据集，包含废弃物上下文，适合补充普通废弃物视觉特征；
- ZeroWaste：面向复杂混杂废弃物流的检测/分割数据集，适合参考玻璃、塑料、纸、金属等混杂场景；
- GDD / glass detection 方向：更偏玻璃表面检测，不一定等同于建筑垃圾中的破碎玻璃，但可作为补充参考；
- SODA：施工现场目标检测数据集，更适合施工场景对象，不一定直接覆盖建筑垃圾十二分类；
- Roboflow Universe：可能有 glass waste、construction debris 等公开项目，但需要逐个检查许可、类别、标注格式和数据质量。

最终建议：

- `glass`：先找数据，筛选后加入训练集，再用大模型复核低置信度样本；
- `asbestos_suspect`：不要急着训练成确定类别，先做“疑似危险物复核机制”；
- 在线大模型不应替代训练集，而应作为低置信度和高风险类别的复核器。
