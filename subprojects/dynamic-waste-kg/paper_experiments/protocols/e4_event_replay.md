# E4 状态更新、事件追踪与严格图片序列补拍协议

## 目的

E4 用于回答：当场景中的对象在前后两次观测中发生变化时，系统能否把视觉变化转化为短期记忆更新和可追溯事件。

当前 E4 分为两部分：

- 软件事件回放：验证状态版本、事件链和策略一致性；
- 图片序列再感知：脚本已具备，但严格 before/after 移除样本尚未获得。

## 当前边界

当前阶段不声明机械臂真实抓取成功，也不声明 ROS2 闭环已经完成。

2026-07-11 对新补拍并标注的 19 张实验室图片完成审计。当前 before/after 对仍存在视角或尺度变化，且图片被混入 train/val，因此只可用于流程调试。正式 E4 holdout 的隔离、补拍和标注要求见 `lab_domain_adaptation_and_e4_holdout.md`。

更严谨的论文表述应为：

```text
The prototype validates image-based re-observation and event-level state updating under a controlled setting.
```

不建议写成：

```text
The robotic arm removed the object successfully.
```

## 已完成的软件事件回放

覆盖场景：

- normal_confirmation
- vlm_correction
- vlm_uncertain_fallback
- low_confidence_human_review
- sensitive_class_review
- object_removed
- object_reappeared
- api_schema_error_fallback

运行命令：

```powershell
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e4_event_replay.py
```

输出目录：

```text
artifacts/paper/e4_event_replay
```

## 图片序列候选审查结论

已对现有数据进行候选筛选，包括：

- 整图相似度筛选；
- 同前缀相邻编号筛选；
- 标签数量减少筛选；
- 标注多边形位置匹配筛选。

审查输出：

```text
artifacts/paper/e4_image_sequence_candidates/label_subset_strict_candidates.jpg
artifacts/paper/e4_image_sequence_candidates/top_label_strict_candidates_large.jpg
artifacts/paper/e4_image_sequence_candidates/strict_removal_candidate_pairs_contact_sheet.jpg
```

结论：现有候选图不能作为严格论文证据。多数候选存在物体替换、摆放变化、视角变化或形态变化，不满足“只移除一个物体，其他物体不变”的条件。

## 投稿前必须补充的严格 E4 图片

为了让 E4 从软件事件回放升级为“人工移除后再感知证据”，需要补拍一组固定视角图片：

1. 固定相机位置，光照尽量不变；
2. 场景中放 3 到 6 个建筑废弃物；
3. 拍摄 `before.jpg`；
4. 手动移除其中一个物体，不移动其他物体；
5. 拍摄 `after.jpg`；
6. 在 `README.md` 中记录：移除的物体类别、位置、拍摄时间；
7. 用 `run_e4_image_sequence.py` 重新运行；
8. 将输出的 `before_after_prediction_comparison.jpg` 放入论文图。

推荐目录结构：

```text
paper_experiments/e4_image_sequences/seq001/
  before.jpg
  after.jpg
  README.md
```

如果这组图片来自 RealSense，后续还可以补充深度图和相机位姿，从而进一步支持抓取规划。

补拍完成后的运行命令模板：

```powershell
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e4_image_sequence.py `
  --before paper_experiments\e4_image_sequences\seq001\before.jpg `
  --after paper_experiments\e4_image_sequences\seq001\after.jpg `
  --weights outputs\yolo_runs\segment\runs\waste12_seg\yolo11n_seg_cdw_glass_e50\weights\best.pt `
  --out artifacts\paper\e4_image_sequence_seq001 `
  --conf 0.25 `
  --device 0 `
  --max-det 20 `
  --iou-threshold 0.5 `
  --note "Manually removed one object under fixed camera view."
```
