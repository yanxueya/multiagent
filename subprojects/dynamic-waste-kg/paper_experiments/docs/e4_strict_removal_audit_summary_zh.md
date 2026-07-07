# E4 严格移除前后图片补充实验整理

## 1. 实验目的

本次补充实验的目标是为小论文 E4 寻找一组严格的“移除前/移除后”图片证据，用于证明：

```text
同一场景中人工移除一个物体后，系统能够重新执行 YOLO 实例分割，并将前后状态变化写入事件链。
```

严格可用的图片对必须满足：

1. 相机视角固定；
2. 背景基本不变；
3. 前图只比后图多一个被移除物体；
4. 其他物体位置、姿态、形态基本不变；
5. 后图不能出现新增物体；
6. 不能把物体替换、重新摆放、视角变化解释为移除。

## 2. 已执行的工作

### 2.1 初始 E4 图片序列脚本

新增了图片序列实验脚本，用于对 before/after 两张图片分别运行 YOLO，并生成检测结果、事件记录和对比图。

脚本位置：

```text
paper_experiments/scripts/run_e4_image_sequence.py
```

核心逻辑：

```text
before image
-> YOLO segmentation
-> before detections
-> after image
-> YOLO segmentation
-> after detections
-> 同类 IoU 匹配
-> persisted / removed_candidate / appeared_candidate events
```

相关测试：

```text
tests/test_paper_e4_image_sequence.py
```

### 2.2 初始候选图片验证

曾用以下图片作为初始候选：

```text
datasets/waste12_yolo/images/test/codd_other-1897.jpg
datasets/waste12_yolo/images/train/codd_other-1898.jpg
```

输出目录：

```text
artifacts/paper/e4_image_sequence_demo_iou50
```

但重新核实后，该图片对更像物体替换或物体形态变化，不满足严格“只移除一个物体”的要求。因此，该输出已经被降级为调试记录，不作为论文正式证据。

### 2.3 重新筛选严格候选

之后进一步执行了更严格的筛选：

- 文件名前缀和相邻编号筛选；
- 图像尺寸一致性筛选；
- 标签数量减少筛选；
- 类别集合约束；
- 标注多边形 bbox IoU 匹配；
- 人工目视复核。

其中最严格的筛选要求是：

```text
后图中的每个标注对象，都必须能在前图中找到同类、同位置匹配；
前图只能多出 1 个未匹配物体。
```

生成的候选审查图：

```text
artifacts/paper/e4_image_sequence_candidates/label_subset_strict_candidates.jpg
artifacts/paper/e4_image_sequence_candidates/top_label_strict_candidates_large.jpg
artifacts/paper/e4_image_sequence_candidates/strict_removal_candidate_pairs_contact_sheet.jpg
artifacts/paper/e4_image_sequence_candidates/selected_possible_removal_pairs_large.jpg
```

### 2.4 审查结论

重新核实后，当前已有数据中没有找到可直接用于论文的严格 before/after 移除图片对。

主要原因：

- 部分候选只是标注数量减少，但图像中存在物体替换；
- 部分候选中剩余物体位置、姿态或形态明显变化；
- 部分自然场景候选存在视角变化；
- 部分候选被移除物体太小，难以作为可靠证据；
- 部分候选不能排除重新摆放或重新组合。

因此，当前 E4 图片序列实验不能写成“已完成严格移除前后再感知验证”。

## 3. 当前可保留的结果

### 3.1 E4 软件事件回放结果保留

E4 的软件事件回放仍然有效，可以用于证明状态组织和事件链逻辑。

结果位置：

```text
artifacts/paper/e4_event_replay
```

核心指标：

```text
case_count = 32
Instance Update Success Rate = 1.0000
Event Chain Completeness = 1.0000
State Version Consistency = 1.0000
Temporal Policy Consistency = 1.0000
```

这些结果可以写入论文，但必须明确它是受控软件事件回放，不是真实图片移除证据，也不是真实机械臂执行证据。

### 3.2 E4 图片序列脚本保留

虽然当前数据中没有找到严格图片对，但图片序列脚本本身可以保留。后续你补拍 before/after 图片后，可以直接使用该脚本重新生成证据。

脚本位置：

```text
paper_experiments/scripts/run_e4_image_sequence.py
```

## 4. 已更新的文档

本次核实后，以下文档已经更新，避免继续把不严谨候选图写成正式证据：

```text
paper_experiments/docs/e0_e4_experiment_results_and_feedback_explanation_zh.md
paper_experiments/results/README.md
paper_experiments/protocols/e4_event_replay.md
artifacts/paper/e4_image_sequence_candidates/strict_removal_candidate_audit.md
```

其中，正式结论已改为：

```text
E3 已验证受控策略路由；
E4 已验证软件事件追踪；
严格图片序列再感知仍需补拍 before/after 样本。
```

## 5. 后续你需要补充的图片

建议新建如下目录：

```text
paper_experiments/e4_image_sequences/seq001/
  before.jpg
  after.jpg
  README.md
```

拍摄规则：

1. 固定相机，尽量使用三脚架或固定支架；
2. 光照保持不变；
3. 场景中放 3 到 6 个建筑废弃物；
4. 拍摄 `before.jpg`；
5. 只移除一个物体，其他物体不要移动；
6. 拍摄 `after.jpg`；
7. 在 `README.md` 中记录被移除物体的类别、位置和拍摄说明。

补拍后运行：

```powershell
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e4_image_sequence.py `
  --before paper_experiments\e4_image_sequences\seq001\before.jpg `
  --after paper_experiments\e4_image_sequences\seq001\after.jpg `
  --weights outputs\yolo_runs\segment\outputs\yolo_runs\waste12_seg\yolo11n_seg_cdw_glass_e50\weights\best.pt `
  --out artifacts\paper\e4_image_sequence_seq001 `
  --conf 0.25 `
  --device 0 `
  --max-det 20 `
  --iou-threshold 0.5 `
  --note "Manually removed one object under fixed camera view."
```

## 6. 本次实验最终结论

本次补充实验没有获得可用于论文正文的严格移除前后图片证据。

当前可写入论文的是：

```text
E4 软件事件回放证明系统具备状态追踪和事件可追溯能力。
```

当前不能写入论文的是：

```text
系统已经完成基于真实图片的人工移除后再感知验证。
```

该部分需要你后续补拍严格 before/after 图片后再完成。

