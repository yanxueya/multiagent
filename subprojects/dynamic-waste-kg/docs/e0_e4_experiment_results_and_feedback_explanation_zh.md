# E0-E4 补充实验结果、提示词、反馈机制与证据链说明

> 面向小论文写作的实验说明文档。本文档用于解释当前已经完成的补充实验、每个实验能支撑的论文问题、已有图片/表格/图谱证据，以及 E3/E4 与真实执行反馈之间的边界。

---

## 1. 总体定位

当前小论文的研究范围应表述为：

> 受控环境下的 11 类建筑废弃物二维实例分割、受约束视觉语言模型复核，以及分层动态知识状态构建与可审计路由验证。

当前不应表述为：

> 已完成真实机械臂抓取、真实 ROS2 闭环执行、真实危险废弃物处置或施工现场长期自主运行。

核心逻辑是：

```text
E0 数据可靠性
-> E1 YOLO 实例分割基线
-> E2 VLM 图像复核与保守回退
-> E3 长短期知识状态到任务路由
-> E4 事件回放与状态可追溯
```

这条证据链回答两个主要问题：

1. 实例分割结果如何转化为任务语义，而不只是类别、置信度和 mask；
2. 长期类别知识、短期实例状态和事件日志为何必须分层，否则系统无法解释状态变化来源。

---

## 2. 当前 VLM 提示词在哪里

提示词目前写在代码中：

```text
wastekg/llm_reviewer.py
```

### 2.1 System Prompt

```text
你是建筑废弃物分拣系统的安全复核器，任务是保守复核 YOLO 的分类结果。
```

### 2.2 Text-only Prompt

当没有图像证据时，使用文本复核提示词：

```text
请复核一个建筑废弃物目标的类别。
你只能从 allowed_classes 中选择 class_name，不能创造新类别。
如果存在疑似石棉、玻璃碎片、危险板材等安全风险，请保守标记 need_human_review=true。
请只返回 JSON，不要解释。

allowed_classes: ...
yolo_class_name: ...
yolo_confidence: ...
crop_or_image_ref: ...

返回 JSON 格式：
{"class_name": "...", "confidence": 0.0, "risk_hint": "low|medium|high|unknown", "need_human_review": true, "reason": "..."}
```

### 2.3 Visual Prompt

当存在原图、裁剪图或 mask overlay 图时，使用视觉复核提示词：

```text
请复核一个建筑废弃物目标的类别。你将收到同一实例的原始场景图、扩边裁剪图和 mask 高亮图。
你只能从 allowed_classes 中选择 proposed_class，不能创造新类别。
若图像证据不足或类别存在风险，请选择 uncertain 并要求人工复核。请只返回 JSON。

allowed_classes: concrete, brick, tile, wood, gypsum_board, foam, metal, soft_plastic, hard_plastic, paperboard, glass
yolo_class_name: ...
yolo_confidence: ...

返回 JSON 格式：
{"decision": "agree|change|uncertain", "proposed_class": "...", "confidence": 0.0, "requires_human_review": true, "reason": "..."}
```

### 2.4 三种决策的含义

| VLM 输出 | 含义 | 系统处理 |
|---|---|---|
| `agree` | VLM 同意 YOLO 类别 | 保留 YOLO 类别，可记录复核通过 |
| `change` | VLM 明确建议改为白名单内另一类别 | 只有类别在白名单内才允许改写 |
| `uncertain` | VLM 无法安全确认 | 保留 YOLO 类别，并升级为 `human_review_required` |
| `review_error` | API、限流、schema 或网络失败 | 保留 YOLO 类别，并升级为 `human_review_required` |

该设计的重点是保守性：VLM 不是开放式分类器，而是受约束复核器。

---

## 3. E0：数据集审计与冻结

### 3.1 目的

E0 用于证明数据集划分、类别范围和标注格式可复查，避免训练/测试混乱导致论文结果不可靠。

### 3.2 当前结果

固定视觉类别为 11 类：

```text
concrete, brick, tile, wood, gypsum_board, foam,
metal, soft_plastic, hard_plastic, paperboard, glass
```

`asbestos_suspect` 保留在长期知识层中，但不作为 YOLO/VLM 视觉输出类别。

### 3.3 证据文件

```text
datasets/waste11_grouped_v1
artifacts/e0_waste11_grouped_v1_r3
```

### 3.4 能支撑的论文表述

可以写：

> 本文在冻结的 11 类二维实例分割数据集上进行训练与测试，并将 `asbestos_suspect` 作为知识状态中的人工复核风险标签，而非视觉模型类别。

不能写：

> 本文训练了 12 类视觉模型并能识别石棉。

---

## 4. E1：YOLO11n-seg 实例分割基线

### 4.1 目的

E1 回答：轻量 YOLO11n-seg 能否为后续知识图谱提供可用的二维实例分割输入。

### 4.2 当前结果

```text
test images = 890
test effective instances = 19,475
Box mAP50-95 = 0.8437
Mask mAP50-95 = 0.7397
```

### 4.3 证据文件

```text
artifacts/e1_test_evaluation_r2/overall_metrics.json
artifacts/e1_test_evaluation_r2/per_class_metrics.csv
artifacts/e1_test_evaluation_r2/ultralytics/metrics/
artifacts/e1_qualitative_samples_r1/
```

### 4.4 能支撑的论文表述

可以写：

> YOLO11n-seg 在独立 test split 上形成了可用的二维分割基线，为后续图谱实例节点提供类别、置信度、bbox 和 mask 信息。

不能写：

> 当前 mask 精度已经足以直接证明机械臂抓取成功。

---

## 5. E2：GLM-4.5V 视觉复核

### 5.1 目的

E2 回答：当 YOLO 结果存在低置信度、类别敏感或边界不确定时，视觉语言模型能否作为受约束复核器，并在不确定或失败时触发人工复核。

### 5.2 当前配置

```env
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=zai-org/GLM-4.5V
LLM_RESPONSE_FORMAT_JSON=false
```

`LLM_RESPONSE_FORMAT_JSON=false` 的原因是：GLM-4.5V 支持视觉输入，但硅基流动接口返回过 `Json mode is not supported for this model`，所以不能强制使用 `response_format={"type":"json_object"}`。

### 5.3 单图冒烟测试结果

```text
artifacts/e2_glm45v_single_image_smoke_r3
```

结果：

```text
YOLO class = hard_plastic
YOLO confidence = 0.9547
VLM decision = uncertain
final class = hard_plastic
review_status = human_review_required
```

解释：GLM-4.5V 成功读取图像证据并返回结构化结果。当模型不确定时，系统没有静默改写类别，而是保留 YOLO 并触发人工复核。

### 5.4 20 图小批量结果

推荐采用第三轮轻量证据结果：

```text
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused
```

主要结果：

```text
image_count = 20
detection_count = 18
reviewed_count = 17
valid_vlm_response_count = 13
valid_vlm_response_rate = 0.7647
human_review_required_count = 9
human_review_required_rate = 0.5000
mean_latency_seconds = 8.4690
agree = 8
change = 0
uncertain = 5
review_error = 4
not_reviewed = 1
```

4 个 `review_error` 均来自：

```text
HTTP 429 TPM limit reached
```

这说明当前 E2 的主要限制是硅基流动账号/模型服务的每分钟 token 配额，而不是本地图谱、YOLO 或 JSON 解析失败。

### 5.5 能支撑的论文表述

可以写：

> 小批量实验表明，受约束 VLM 复核链路可以处理 crop 与 mask overlay 图像证据，并在不确定或 API 限流时保守升级为人工复核。

不能写：

> VLM 已经在全测试集上显著提高分类准确率。

---

## 6. E3：分层知识状态与保守任务路由

### 6.1 目的

E3 回答：视觉输出能否被转换为任务语义，例如自动候选、监督候选或人工复核。

### 6.2 路由标签

```text
AUTO_CANDIDATE
SUPERVISED_CANDIDATE
HUMAN_REVIEW_REQUIRED
```

### 6.3 当前结果

```text
case_count = 15
Policy Consistency Rate = 1.0000
Restriction Recall = 1.0000
Unsafe Automation Rate = 0.0000
Human Escalation Rate = 0.5333
```

证据文件：

```text
artifacts/paper/e3_policy_routing/policy_cases.csv
artifacts/paper/e3_policy_routing/policy_metrics.json
artifacts/paper/e3_policy_routing/policy_report.md
```

### 6.4 如何体现“动作前决策”

E3 并不执行机械臂动作，而是生成动作前的任务语义：

```text
实例类别 + 置信度 + 复核状态 + 长期类别知识
-> 是否可自动处理
-> 是否需监督
-> 是否必须人工复核
```

例如：

```text
brick + high confidence + robot_grasp -> AUTO_CANDIDATE
glass + uncertain -> HUMAN_REVIEW_REQUIRED
asbestos_suspect -> HUMAN_REVIEW_REQUIRED / human_only
```

因此，E3 支撑的是“任务规划输入”，不是“真实动作执行结果”。

---

## 7. E4：事件回放、严格图片序列审查与状态可追溯

### 7.1 目的

E4 回答：当对象被观测、复核、路由、移除或重新出现时，图谱能否记录连续状态链。根据当前小论文边界，E4 不强调机械臂真实抓取。严格的图片序列证据必须满足“固定视角、固定背景、前图只比后图多出一个被移除物体、其他物体基本不变”。

### 7.2 当前受控事件链

当前每个案例使用四步事件链：

```text
OBSERVED
-> REVIEWED
-> POLICY_PROJECTED
-> ROUTED
```

当前覆盖场景包括：

```text
normal_confirmation
vlm_correction
vlm_uncertain_fallback
low_confidence_human_review
sensitive_class_review
object_removed
object_reappeared
api_schema_error_fallback
```

### 7.3 软件事件回放结果

```text
case_count = 32
Instance Update Success Rate = 1.0000
Event Chain Completeness = 1.0000
State Version Consistency = 1.0000
Temporal Policy Consistency = 1.0000
```

证据文件：

```text
artifacts/paper/e4_event_replay/event_replay_cases.csv
artifacts/paper/e4_event_replay/event_replay_metrics.json
artifacts/paper/e4_event_replay/event_replay_report.md
```

### 7.4 严格图片序列审查结果

为了避免 E4 只依赖手写 JSON，本项目新增了图片序列再感知脚本。该脚本可以对同一背景下前后两张图片分别执行 YOLO 实例分割，再用同类 IoU 匹配判断实例是否持续存在、消失或新增。

但经过重新核实，当前已有数据中的候选图片不能作为严格“移除前/移除后”论文证据。原因是：候选对虽然在标注数量上存在减少，但肉眼检查后多数属于物体替换、摆放变化、视角变化或物体形态变化，不满足“只移除一个物体且其他物体保持不变”的严格条件。

候选审查输出：

```text
artifacts/paper/e4_image_sequence_candidates/label_subset_strict_candidates.jpg
artifacts/paper/e4_image_sequence_candidates/top_label_strict_candidates_large.jpg
artifacts/paper/e4_image_sequence_candidates/strict_removal_candidate_pairs_contact_sheet.jpg
```

当前结论：

```text
strict_before_after_removal_pair_found = false
status = needs_controlled_recapture
```

因此，当前论文中不应使用这些候选图作为 E4 的正式图片证据。E4 图片序列部分应标记为“待补拍严格 before/after 样本”。脚本和指标流程可以保留，但结果不能写成已完成。

### 7.5 如何体现“执行动作后的进一步反馈”

当前 E4 的“执行反馈”只保留受控软件回放证据。图片序列再感知脚本已经具备，但严格 before/after 图片尚未获得，因此不能作为当前已完成证据。

它模拟的是：

```text
t1: 系统观测到对象，创建短期实例
t2: VLM 或人工复核改变复核状态
t3: 策略层根据长期知识投影任务路由
t4: 系统记录最终路由或移除/重新出现事件
```

如果未来接入 ROS2，真实反馈应变为：

```text
Action Planner 输出动作
-> Executor 执行 ROS2 / MoveIt 命令
-> 机械臂动作结束后返回 success / failed / blocked
-> RealSense 重新观测局部场景
-> 图谱更新 instance 状态、位置、关系和事件日志
-> 若失败或状态不一致，重新规划或人工介入
```

当前 E4 可以证明软件状态链设计合理，但还不能证明严格图片再感知闭环或真实执行闭环已经完成。

---

## 8. 图片、表格、图谱与事件证据链（重点）

本节是论文写作时最重要的证据索引。建议把证据分成四类：视觉证据、表格证据、图谱证据、事件证据。

### 8.1 E1 可直接用于论文插图的视觉证据

E1 有真实图片支撑，适合放入论文。

| 证据 | 路径 | 论文用途 |
|---|---|---|
| 训练/验证预测图 | `artifacts/e1_test_evaluation_r2/ultralytics/metrics/val_batch0_pred.jpg` | 展示 YOLO 分割预测效果 |
| 标签对照图 | `artifacts/e1_test_evaluation_r2/ultralytics/metrics/val_batch0_labels.jpg` | 与预测图对照 |
| 混淆矩阵 | `artifacts/e1_test_evaluation_r2/ultralytics/metrics/confusion_matrix.png` | 展示类别混淆 |
| 归一化混淆矩阵 | `artifacts/e1_test_evaluation_r2/ultralytics/metrics/confusion_matrix_normalized.png` | 展示类别级误差比例 |
| Mask PR 曲线 | `artifacts/e1_test_evaluation_r2/ultralytics/metrics/MaskPR_curve.png` | 展示分割性能 |
| Box PR 曲线 | `artifacts/e1_test_evaluation_r2/ultralytics/metrics/BoxPR_curve.png` | 展示检测性能 |
| foam 定性样例 | `artifacts/e1_qualitative_samples_r1/foam__codd_2916__prediction.jpg` | 展示困难类别预测 |
| glass 定性样例 | `artifacts/e1_qualitative_samples_r1/glass__glassdebris_v5_test_video3_mp4-0009_jpg.rf.eff64b7ee6dc8287a878e5118ffbec97__prediction.jpg` | 展示玻璃类预测 |
| metal 定性样例 | `artifacts/e1_qualitative_samples_r1/metal__cdw2026_2022_0158__prediction.jpg` | 展示金属类预测 |
| soft_plastic 定性样例 | `artifacts/e1_qualitative_samples_r1/soft_plastic__cdw2026_2022_0163__prediction.jpg` | 展示软塑料类预测 |

推荐论文图：

```text
Fig. 4: YOLO11n-seg test performance
Fig. 5: qualitative segmentation examples for foam, glass, metal, soft_plastic
```

#### E1 图像证据预览

图 E1-1 展示验证集预测结果，适合用于说明 YOLO11n-seg 对混合建筑废弃物的二维实例分割输出形式。

![E1 YOLO validation prediction](../artifacts/e1_test_evaluation_r2/ultralytics/metrics/val_batch0_pred.jpg)

图 E1-2 是同一批样本的标签对照图，可与预测图并列展示模型输出和标注之间的差异。

![E1 YOLO validation labels](../artifacts/e1_test_evaluation_r2/ultralytics/metrics/val_batch0_labels.jpg)

图 E1-3 展示归一化混淆矩阵，适合用于讨论类别混淆和弱类别。

![E1 normalized confusion matrix](../artifacts/e1_test_evaluation_r2/ultralytics/metrics/confusion_matrix_normalized.png)

图 E1-4 展示 Mask PR 曲线，适合用于报告实例分割性能，而不是只看检测框性能。

![E1 Mask PR curve](../artifacts/e1_test_evaluation_r2/ultralytics/metrics/MaskPR_curve.png)

图 E1-5 至图 E1-8 是典型类别定性样例，可放入论文附图或补充材料。

![E1 foam qualitative prediction](../artifacts/e1_qualitative_samples_r1/foam__codd_2916__prediction.jpg)

![E1 glass qualitative prediction](../artifacts/e1_qualitative_samples_r1/glass__glassdebris_v5_test_video3_mp4-0009_jpg.rf.eff64b7ee6dc8287a878e5118ffbec97__prediction.jpg)

![E1 metal qualitative prediction](../artifacts/e1_qualitative_samples_r1/metal__cdw2026_2022_0158__prediction.jpg)

![E1 soft plastic qualitative prediction](../artifacts/e1_qualitative_samples_r1/soft_plastic__cdw2026_2022_0163__prediction.jpg)

### 8.2 E2 可直接用于论文插图的视觉证据

E2 有真实图片支撑，适合展示“YOLO 输出 -> VLM 复核证据”。

推荐样例路径：

```text
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/images/001_cdw2026_2022_0345/prediction/cdw2026_2022_0345.jpg
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/images/001_cdw2026_2022_0345/visual_evidence/det_001__crop.jpg
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/images/001_cdw2026_2022_0345/visual_evidence/det_001__mask_overlay.jpg
```

这些图可以组成一个三联图：

```text
左：YOLO 原图预测
中：VLM 输入 crop
右：VLM 输入 mask overlay
```

推荐论文图：

```text
Fig. 6: constrained VLM review evidence
```

#### E2 图像证据预览

图 E2-1 展示 YOLO 对单张图片的初始分割输出。

![E2 YOLO prediction](../artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/images/001_cdw2026_2022_0345/prediction/cdw2026_2022_0345.jpg)

图 E2-2 是 VLM 复核使用的局部裁剪图。

![E2 VLM crop evidence](../artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/images/001_cdw2026_2022_0345/visual_evidence/det_001__crop.jpg)

图 E2-3 是 VLM 复核使用的 mask overlay 证据图。它比单纯 crop 更能说明被复核对象的空间范围。

![E2 VLM mask overlay evidence](../artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/images/001_cdw2026_2022_0345/visual_evidence/det_001__mask_overlay.jpg)

注意：第三轮小批量实验为了降低 TPM，只向 VLM 发送 crop 和 mask overlay，不发送整张原图。但原图仍保存到本地，便于论文展示。

### 8.3 E2 可用于论文表格的证据

| 证据 | 路径 | 用途 |
|---|---|---|
| 小批量汇总 | `artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/e2_vlm_batch_summary.json` | 报告 VLM 响应率、人工复核率、延迟 |
| 小批量明细 | `artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/e2_vlm_batch_details.csv` | 展示每个样本的 YOLO 类别、VLM 决策和错误类型 |
| 小批量报告 | `artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/e2_vlm_batch_report.md` | 快速写入论文结果段落 |

可作为论文表：

```text
Table 5: VLM review outcomes and fallback statistics
```

### 8.4 E3 的证据类型：表格证据，不是图片证据

E3 当前没有真实图片支撑，因为 E3 验证的是策略路由，而不是视觉识别本身。

E3 可用于论文的证据是：

```text
artifacts/paper/e3_policy_routing/policy_cases.csv
artifacts/paper/e3_policy_routing/policy_metrics.json
artifacts/paper/e3_policy_routing/policy_report.md
```

可以做成论文表：

```text
Table 6: conservative policy routing results
```

也可以画成流程图：

```text
YOLO/VLM output
-> short-term instance state
-> long-term class prior
-> task route
```

但必须说明：这不是物理执行图像，而是任务语义投影证据。

### 8.5 E4 的证据类型：事件链证据 + 待补拍图片序列

E4 当前仍没有真实机械臂执行图片，也没有可直接用于论文的严格 before/after 移除图片。之前筛选出的候选图经人工复核后不够严谨，不能作为正式图片证据。

当前只能作为候选审查记录的图片：

```text
artifacts/paper/e4_image_sequence_candidates/label_subset_strict_candidates.jpg
artifacts/paper/e4_image_sequence_candidates/top_label_strict_candidates_large.jpg
artifacts/paper/e4_image_sequence_candidates/strict_removal_candidate_pairs_contact_sheet.jpg
```

软件事件回放证据：

```text
artifacts/paper/e4_event_replay/event_replay_cases.csv
artifacts/paper/e4_event_replay/event_replay_metrics.json
artifacts/paper/e4_event_replay/event_replay_report.md
```

当前可做成论文图的是软件事件链，而不是图片移除链：

```text
Fig. 7: controlled event replay and auditable state updating
```

建议画法：

```text
OBSERVED(v1)
-> REVIEWED(v2)
-> POLICY_PROJECTED(v3)
-> ROUTED(v4)
-> EVENT_LOGGED(v5)
```

并在图注中明确：

> This is a controlled event-replay validation rather than physical robotic execution or image-confirmed removal.

#### E4 候选图片审查记录

以下图片只作为候选审查记录，不能直接放入论文正文作为“移除前后”证据。

![E4 strict candidate audit](../artifacts/paper/e4_image_sequence_candidates/top_label_strict_candidates_large.jpg)

### 8.6 知识图谱可视化证据

当前可用图谱文件包括：

```text
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/graph_snapshot.json
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused/events.jsonl
artifacts/e2_glm45v_single_image_smoke_r3/graph.mmd
artifacts/e2_glm45v_single_image_smoke_r3/neo4j_import.cypher
```

其中：

- `graph_snapshot.json` 适合证明长期类别、短期实例和事件日志被保存；
- `events.jsonl` 适合证明事件可追溯；
- `graph.mmd` 适合画 Mermaid 图；
- `neo4j_import.cypher` 适合导入 Neo4j 做可视化。

推荐论文图：

```text
Fig. 8: layered knowledge graph snapshot and event links
```

### 8.7 当前缺失但后续必须补的真实执行图片

如果论文要进一步声称“执行反馈”或“机械臂闭环”，必须补充以下图片或截图：

| 证据 | 当前状态 | 后续获取方式 |
|---|---|---|
| RealSense 原始 RGB 图 | 未完成真实在线采集 | 接入 D435i 后保存 |
| RealSense 深度图 | 未完成真实在线采集 | 保存 depth PNG 或 NPY |
| 手眼标定结果截图 | 未完成 | Ubuntu 22.04 + ROS2 标定 |
| 人工移除前场景 | 未完成严格样本 | 固定相机拍摄 `before.jpg` |
| 人工移除后场景 | 未完成严格样本 | 手动移除一个物体后拍摄 `after.jpg` |
| 机械臂抓取前场景 | 未完成 | 后续接入机械臂后拍摄 |
| 机械臂抓取后场景 | 未完成 | 后续接入机械臂后重新拍摄 |
| 执行前图谱状态 | 部分已有软件状态 | 真实执行前导出 |
| 执行后图谱状态 | 目前为受控回放 | 真实执行后导出 |
| ROS2 / MoveIt 执行日志 | 未完成 | ROS2 节点记录 |

人工移除 before/after 图片属于当前小论文可以补强的内容，但需要重新补拍；机械臂执行图片、ROS2 日志和手眼标定结果建议放到后续大论文或扩展实验。

### 8.8 建议的论文图表组合

最稳妥的图表组合如下：

```text
Fig. 1  系统总体框架：YOLO -> VLM -> 分层知识图谱 -> 路由/规划接口
Fig. 2  长期知识层、短期记忆层、事件日志层结构
Fig. 3  VLM 受约束复核提示词与 conservative fallback 机制
Fig. 4  YOLO11n-seg test performance 曲线与混淆矩阵
Fig. 5  典型类别分割可视化样例
Fig. 6  E2 的 crop + mask overlay 视觉复核证据
Fig. 7  E3 任务路由流程和指标表
Fig. 8  E4 事件回放链：OBSERVED -> REVIEWED -> POLICY_PROJECTED -> ROUTED -> EVENT_LOGGED
```

表格建议：

```text
Table 1  数据集类别与 split 统计
Table 2  YOLO 训练与测试环境
Table 3  长期知识层类别策略表
Table 4  E1 test set overall/per-class metrics
Table 5  E2 VLM review outcomes
Table 6  E3 conservative routing metrics
Table 7  E4 controlled event replay metrics
Table 8  当前已验证能力与尚未验证能力边界
```

---

## 9. E3/E4 与未来真实执行闭环的衔接

当前 E3/E4 是为了给后续真实执行打基础。

未来真实闭环应该这样接：

```text
1. Perceptor 从 RealSense + YOLO/VLM 得到对象实例
2. KnowledgeGraph 写入短期实例和长期类别先验
3. Retriever 查询对象状态、风险、阻塞关系
4. Action Planner 根据 E3 路由结果生成动作候选
5. Executor 通过 ROS2 / MoveIt 执行动作
6. 执行器返回 success / failed / blocked / human_intervention
7. Perceptor 重新观察局部场景
8. KnowledgeGraph 写入 state_change / observation / relation_update 事件
9. 若对象未移除或关系变化，重新规划
```

因此，E3/E4 当前的价值是：

```text
在真实机器人接入前，先验证状态表示、路由规则和事件链是否清晰。
```

---

## 10. 当前结论边界

当前可以稳妥声明：

1. 11 类建筑废弃物二维实例分割基线已完成；
2. GLM-4.5V 已能作为视觉复核器接收 crop 与 mask overlay；
3. VLM 不确定、API 限流或 schema 异常时，系统能保守回退到人工复核；
4. 长期知识、短期实例和事件日志已能组织为可查询状态；
5. E3 已验证受控策略路由，E4 已验证软件事件追踪；严格图片序列再感知仍需补拍 before/after 样本。

当前不能声明：

1. 已完成真实机械臂抓取；
2. 已完成 ROS2 闭环执行；
3. 已完成 RealSense 三维定位验证；
4. 已能视觉确认石棉；
5. VLM 已在完整 test set 上显著提升识别准确率。
