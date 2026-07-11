# 建筑废弃物知识图谱权威设计

本文档同步自用户提供的《知识图谱.docx》，是当前代码、测试、UI 快照和多智能体接口的知识图谱依据。历史论文稿或实验记录与本文冲突时，以当前代码、测试和本文为准。

## 1. 系统边界

知识图谱服务于以下闭环：

```text
YOLO 候选检测
  -> VLM 属性复核
  -> RealSense 三维状态补充
  -> 知识图谱更新
  -> LangGraph 规划
  -> ROS2 / PiPER 执行
  -> 事件回写与重新观测
```

当前固定为 11 个长期视觉类别：

```text
concrete, brick, tile, wood, gypsum_board, foam,
metal, soft_plastic, hard_plastic, paperboard, glass
```

`unknown` 不是 YOLO 类别，也不是 `WasteCategory`。它是短期识别状态，并通过 `UnknownSample` 和 `UnknownCluster` 进入人工复核与知识演化流程。

## 2. 三层结构

| 层级 | 节点 | 职责 |
| --- | --- | --- |
| 长期知识层 | `WasteCategory` | 保存稳定类别先验和默认处理策略 |
| 短期记忆层 | `Scene`、`ObjectInstance`、`UnknownSample`、`UnknownCluster` | 保存当前场景、实例、未知样本和复核状态 |
| 事件日志层 | 七类 Event | 追加记录检测、复核、深度、规划、执行和知识演化原因 |

长期知识不被单次观测直接修改；短期状态随观测和执行更新；事件只追加，不覆盖历史。

## 3. 长期知识层

### 3.1 WasteCategory 字段

```text
category_name
risk_level
fragility
graspability_prior
vlm_review_policy
default_handling_policy
visual_prototype
```

枚举约束：

- `risk_level`、`fragility`、`graspability_prior`：`low / medium / high`
- `vlm_review_policy`：`threshold_based / always`
- `default_handling_policy`：`auto_allowed / human_confirmation_required`

`visual_prototype` 只包含：

```text
dominant_color
transparency
glossiness
surface_texture
edge_fracture
shape_form
```

视觉原型用于 VLM 与 YOLO 假设的一致性校验，不是硬分类规则。

### 3.2 11 类长期种子

| 类别 | 风险 | 易碎性 | 抓取先验 | VLM 策略 | 默认处理策略 |
| --- | --- | --- | --- | --- | --- |
| `concrete` | medium | low | low | threshold_based | human_confirmation_required |
| `brick` | medium | low | medium | threshold_based | auto_allowed |
| `tile` | medium | high | medium | threshold_based | human_confirmation_required |
| `wood` | low | low | medium | threshold_based | auto_allowed |
| `gypsum_board` | medium | high | low | always | human_confirmation_required |
| `foam` | low | low | medium | threshold_based | human_confirmation_required |
| `metal` | medium | low | medium | threshold_based | human_confirmation_required |
| `soft_plastic` | low | low | medium | threshold_based | human_confirmation_required |
| `hard_plastic` | low | low | medium | threshold_based | auto_allowed |
| `paperboard` | low | medium | medium | threshold_based | auto_allowed |
| `glass` | high | high | low | always | human_confirmation_required |

完整视觉原型值以 `wastekg/core/knowledge_base.py` 为单一代码来源。

### 3.3 明确禁止的长期属性

知识图谱不保存以下规划期信息：

```text
task_value
priority_tier
dynamic_priority_score
动作顺序
失败恢复计划
```

处理优先级只由 `action_planning_agent` 在规划时计算，不回写为长期或短期属性。

## 4. 短期记忆层

### 4.1 Scene

```text
scene_id
captured_at
rgb_ref
depth_ref
```

执行后或重新观测时创建新 `Scene`，不得覆盖旧场景。

### 4.2 ObjectInstance

```text
instance_id
yolo_confidence
recognition_status
bbox_2d
mask_ref
crop_ref
center_xyz_camera
depth_valid_ratio
observed_extent_3d
occlusion_state
vlm_consistency
current_handling_policy
task_status
attempt_count
```

关键枚举：

- `recognition_status`：`accepted / review_required / unknown`
- `vlm_consistency`：`support / conflict / not_checked`
- `current_handling_policy`：`auto_allowed / human_confirmation_required / human_review_required / robot_forbidden`
- `task_status`：`pending / processing / completed / failed`

类别不能作为 `ObjectInstance` 节点属性持久化。YOLO 候选类别使用 `CANDIDATE_OF`，确认类别使用 `CONFIRMED_AS`。

`safe_grasp_score` 可以作为 RGB-D 几何模块的临时计算结果，但不是当前知识图谱节点属性。

### 4.3 UnknownSample

```text
sample_id
crop_ref
mask_ref
yolo_topk
vlm_attributes
review_status
human_label
```

### 4.4 UnknownCluster

```text
cluster_id
member_count
prototype_attributes
representative_crop_ref
review_status
candidate_category_name
```

未知样本不得自动进入训练集、自动新增长期类别或依据单次 VLM 判断更新类别体系。

## 5. 图关系

关系只保存 `source_id / relation / target_id`，不附加置信度、时间或其他属性。当前关系包括：

```text
Scene -[CONTAINS]-> ObjectInstance
ObjectInstance -[CANDIDATE_OF]-> WasteCategory
ObjectInstance -[CONFIRMED_AS]-> WasteCategory
ObjectInstance -[NEAR]-> ObjectInstance
ObjectInstance -[RECORDED_AS]-> UnknownSample
UnknownSample -[MEMBER_OF]-> UnknownCluster
```

事件可通过 `DETECTED`、`REVIEWS`、`UPDATES`、`CONFIRMS`、`SELECTS`、`EXECUTES`、`EVOLVES`、`IN_SCENE`、`PROPOSED` 等关系关联对象、类别和场景。关系类型由 `wastekg/graph/store.py` 的白名单约束。

## 6. 事件日志层

所有事件包含：

```text
event_id
event_type
event_time
event_source
```

七类事件及固定来源：

| 事件 | event_source | 专属字段 |
| --- | --- | --- |
| `DetectionEvent` | `yolo_detector` | `yolo_confidence, bbox_2d, mask_ref, crop_ref` |
| `VLMReviewEvent` | `vlm_service` | `image_quality, visual_attributes, consistency, reason` |
| `DepthUpdateEvent` | `depth_processor` | `center_xyz_camera, depth_valid_ratio, observed_extent_3d, occlusion_state` |
| `HumanReviewEvent` | `human_reviewer` | `review_action, reason` |
| `PlanningEvent` | `task_planner` | `planned_action, reason` |
| `ExecutionEvent` | `robot_controller` | `action_id, physical_attempt_started, execution_result, failure_reason` |
| `KnowledgeEvolutionEvent` | `knowledge_updater` | `evolution_action, reason` |

事件字段和来源由 `wastekg/core/models.py` 强校验，未定义字段不能写入。

## 7. YOLO、VLM 与状态分流

YOLO 只生成候选，不输出最终真值：

```text
proposal_conf = 0.05
review_conf = 0.30
accept_conf = 0.75
```

- `conf < 0.05`：不进入候选池。
- `0.05 <= conf < 0.30`：保留原 YOLO 假设，设置 `recognition_status=review_required`，等待人工判断为已有类别、未知对象或背景误检。
- `0.30 <= conf < 0.75`：进入 VLM 复核。
- `conf >= 0.75`：仅满足类别策略时可接受。
- `glass`、`gypsum_board`：无论置信度高低均执行 VLM 复核。

后续按实验室自采验证集为各类别标定独立接受阈值，不能把全局初始阈值当作最终结论。

VLM 只提取颜色、透明度、光泽、表面纹理、边缘断裂和形状等可见属性，并判断这些证据是否支持 YOLO 假设。VLM 与 YOLO 冲突时进入复核或未知状态，不自动把类别 A 改成类别 B。

## 8. 规划与执行边界

知识图谱输出 `graph_state`，包括当前类别关系、识别状态、处理策略、任务状态、尝试次数、深度、遮挡和类别风险先验。派生可行性至少检查：

```text
recognition_status == accepted
current_handling_policy == auto_allowed
depth_valid_ratio >= 0.30
occlusion_state != partial
attempt_count < 2
```

资格校验是确定性函数，不是智能体或独立图节点。`action_planning_agent` 先做硬过滤，再以 depth、graspability、NEAR 数量、运动距离和 attempt_count 做无权重字典序，并且每次只选择一个动作。`execution_agent` 只调用允许的结构化相机/ROS2/MoveIt 工具，不发送自由文本命令。

只有 `physical_attempt_started=true` 的真实机械执行才增加 `attempt_count`，执行成功和失败都增加一次。MoveIt 仅规划失败或动作被拒绝时不创建 `ExecutionEvent`。`action_id` 用于防止 LangGraph 恢复时重复执行同一物理动作。执行后必须重新观测新场景；当前仓库尚未证明真实 ROS2/PiPER 闭环已经完成。

## 9. 知识演化

```text
UnknownSample 累积
  -> 可选 UnknownCluster 聚类
  -> 人工确认
  -> 类别定义与视觉原型审核
  -> 数据审计和人工标注
  -> YOLO 重新训练
  -> 独立验证
  -> KnowledgeEvolutionEvent
  -> 更新长期知识
```

任何单次 YOLO、VLM 或聚类结果都不能直接修改 11 类长期知识。

## 10. 当前代码映射

```text
wastekg/core/models.py             # 节点、关系和事件结构
wastekg/core/knowledge_base.py     # 11 类长期种子
wastekg/graph/store.py             # 状态更新、关系和事件写入
wastekg/graph/query.py             # graph_state 可行性投影
wastekg/graph/exporters.py         # JSON/Mermaid/Neo4j 导出
wastekg/interfaces/contracts.py    # LangGraph/ROS2 输入输出契约
```

验证命令：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\graph\export_ui_snapshot.py
```
