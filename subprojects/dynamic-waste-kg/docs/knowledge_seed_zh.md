# 长期知识层种子说明

本文档说明当前知识图谱长期知识层的稳定版本。它必须与代码中的 `wastekg/knowledge_base.py` 保持一致，是后续 YOLO、VLM 属性一致性校验、LangGraph 多智能体规划和 ROS2 执行约束共同使用的基础。

---

## 1. 当前结论

当前系统采用：

```text
11 个明确视觉类别 + 系统逻辑生成 unknown
```

其中 11 个明确类别用于 YOLO 训练、图谱长期知识和规划规则；`unknown` 不作为 YOLO 训练类别，而是系统在低置信度、证据冲突或无法可靠归类时生成的短期状态和人工复核入口。

这样做的原因是：未知物体没有稳定统一的视觉外观，强行把 `unknown` 当成 YOLO 类训练会污染分类边界。更合理的做法是让 YOLO 学习明确类别，让知识图谱和复核策略承接“不确定对象”。

---

## 2. 默认长期类别

当前默认长期知识层只保留 11 个明确类别：

```text
concrete
brick
tile
wood
gypsum_board
foam
metal
soft_plastic
hard_plastic
paperboard
glass
```

`asbestos_suspect` 不再作为默认训练类别或默认长期类别。原因是当前缺少可靠、可验证、可规模化复用的疑似石棉视觉标注数据；RGB 图像也不能可靠确认石棉。后续若确有石棉相关专业数据，应作为高风险人工复核分支或扩展类别单独设计，而不是在当前原型中默认声明可识别。

`unknown` 的定位如下：

```text
不是 YOLO 类别
不是稳定长期类别
是短期记忆层中的不确定对象状态
是人工复核和后续类别进化的入口
```

---

## 3. 标签映射原则

为了复用不同数据集，系统保留轻量别名映射，但不把别名作为独立实体。

| 外部标签 | 本项目类别 |
|---|---|
| `stone` | `concrete` |
| `aggregate` | `concrete` |
| `pipe` / `pipes` | `hard_plastic` |
| `plastic` | `hard_plastic` |
| `cardboard` | `paperboard` |
| `timber` | `wood` |
| `gypsum` | `gypsum_board` |
| `plasterboard` | `gypsum_board` |
| `steel` | `metal` |
| `asbestos` / `asbestos_suspect` | `unknown` |

这种映射的目的不是掩盖风险，而是避免在没有可靠训练数据和专业检测依据的情况下，让视觉模型“确认”高风险材料。疑似危险对象应进入 `unknown` 或人工复核队列。

---

## 4. 长期属性定义

长期知识层不是百科库，只保存会影响任务闭环的稳定先验。

每个类别保留以下核心属性：

| 字段 | 含义 | 取值 |
|---|---|---|
| `risk_level` | 处理风险 | `low / medium / high` |
| `fragility` | 易碎性 | `low / medium / high` |
| `graspability` | 夹爪可抓握性 | `low / medium / high` |
| `pollution_level` | 污染或残留风险 | `low / medium / high` |
| `recognition_difficulty` | 视觉识别难度 | `low / medium / high` |
| `needs_llm_review` | 是否建议 VLM 或人工复核 | `true / false` |
| `auto_processable` | 是否允许进入自动处理候选 | `true / false` |
| `handling_mode` | 推荐处理方式 | 见下文 |
| `grasp_difficulty` | 夹爪抓取难度 | `low / medium / high` |
| `visual_prototype` | 类别常见视觉特征范围 | 结构化字典 |

`handling_mode` 的取值：

| 取值 | 含义 |
|---|---|
| `robot_grasp` | 可作为机械臂夹取候选 |
| `robot_with_supervision` | 可由机械臂处理，但建议监督或确认 |
| `human_review` | 需要人工复核后再决定 |
| `human_only` | 只允许人工处理，不允许机械臂自动夹取 |

---

## 5. 视觉原型不是硬分类规则

`visual_prototype` 只表示“类别常见视觉特征范围”，不是硬规则。

例如，`concrete` 常见为灰色、粗糙、不透明、低光泽、不规则碎块；但不是所有灰色粗糙物体都是混凝土。`hard_plastic` 可能有各种颜色，也可能透明或半透明，因此颜色对该类不是强判别特征。

因此，系统不能使用：

```text
颜色是灰色 -> concrete
```

而应使用：

```text
YOLO 提出 concrete 假设
VLM 提取当前实例属性
KG 检查这些属性是否支持或冲突
证据不足时进入 uncertain/unknown
```

---

## 6. 当前长期知识表

| 类别 | 风险 | 易碎性 | 可抓握性 | 污染性 | 识别难度 | VLM 复核 | 自动处理候选 | 处理方式 | 抓取难度 |
|---|---|---|---|---|---|---|---|---|---|
| `concrete` | medium | low | low | low | medium | 否 | 否 | `robot_with_supervision` | high |
| `brick` | medium | low | medium | low | low | 否 | 是 | `robot_grasp` | medium |
| `tile` | medium | medium | medium | low | medium | 否 | 是 | `robot_with_supervision` | medium |
| `wood` | low | low | medium | low | low | 否 | 是 | `robot_grasp` | medium |
| `gypsum_board` | medium | high | low | medium | medium | 是 | 否 | `human_review` | high |
| `foam` | low | low | medium | medium | medium | 是 | 是 | `robot_with_supervision` | medium |
| `metal` | medium | low | medium | low | medium | 是 | 是 | `robot_with_supervision` | medium |
| `soft_plastic` | low | low | medium | medium | medium | 是 | 是 | `robot_with_supervision` | medium |
| `hard_plastic` | low | low | medium | medium | medium | 是 | 是 | `robot_grasp` | medium |
| `paperboard` | low | medium | medium | low | medium | 是 | 是 | `robot_with_supervision` | medium |
| `glass` | medium | high | low | low | high | 是 | 否 | `robot_with_supervision` | high |

注意：`auto_processable = false` 的类别不会被规划器直接当作自动夹取目标。即使 `handling_mode` 是 `robot_with_supervision`，也必须经过监督或人工确认逻辑。

---

## 7. VLM 的正确使用方式

当前设计不让 VLM 自由回答“这是什么物体”。VLM 的角色是：

```text
结构化视觉属性抽取器 + YOLO 假设一致性校验器
```

VLM 应返回类似结构：

```json
{
  "visual_attributes": {
    "color": "gray",
    "transparency": "opaque",
    "gloss": "low",
    "surface_texture": "rough",
    "edge_shape": "irregular",
    "shape_cue": "fragment"
  },
  "consistency": "support",
  "decision": "agree",
  "requires_human_review": false,
  "reason": "The extracted attributes are consistent with the YOLO concrete hypothesis."
}
```

如果 VLM 特征与 YOLO 类别冲突，或多个类别都能解释当前特征，则不能强行改类，应进入人工复核：

```json
{
  "visual_attributes": {
    "color": "gray",
    "transparency": "opaque",
    "gloss": "low",
    "surface_texture": "powdery",
    "edge_shape": "flat_broken",
    "shape_cue": "board"
  },
  "consistency": "insufficient",
  "decision": "uncertain",
  "requires_human_review": true,
  "reason": "The object may be gypsum board or another board-like material; the image is insufficient for safe automatic handling."
}
```

---

## 8. 置信度分流规则

当前建议采用三档分流：

| 条件 | 系统动作 | 图谱状态 |
|---|---|---|
| `YOLO conf >= 0.85` 且类别规则允许 | 采用 YOLO 结果，写入已知实例 | known |
| `0.40 <= YOLO conf < 0.85` | 调用 VLM 提取属性并做一致性校验 | known 或 uncertain |
| `YOLO conf < 0.40` 或类别冲突 | 不强行分类，进入人工复核 | unknown |

高置信度不等于可以直接抓取。规划器还必须检查：

```text
risk_level
handling_mode
auto_processable
mask quality
safe_grasp_score
occlusion_state
blocked_by/supports
```

例如 `glass` 即使 YOLO 置信度很高，也不应进入无监督自动夹取。

---

## 9. unknown 的记忆与进化

`unknown` 对象应保存：

```text
unknown_id
image_crop_path
mask_path
yolo_topk
vlm_feature_json
first_seen_time
last_seen_time
appearance_count
human_review_status
human_review_result
suggested_new_category
```

推荐进化流程：

```text
未知物体出现
  -> 存入 UnknownObjectMemory
  -> 相似未知物体聚类
  -> 多次出现后提示人工复核
  -> 人工确认是否新增类别
  -> 人工补充类别属性
  -> 人工审核标注质量
  -> 加入 training_candidates
  -> 下一轮 YOLO 训练
  -> 新模型评估通过后更新长期知识层
```

不能直接把未知物体自动加入训练集。否则背景阴影、反光、误检区域都可能污染训练数据。

---

## 10. 短期记忆层字段

公网数据集主要用于训练 RGB 检测或实例分割模型，不能直接提供机械臂需要的真实三维状态。后续系统应使用 Intel RealSense D435i 在线生成短期记忆。

短期记忆层建议保留以下核心字段：

```text
instance_id
class_name
confidence
yolo_confidence
llm_confidence
final_confidence
review_status
center_xyz
bbox_3d
mask_polygon
boundary_points
visible_area_ratio
occlusion_state
contact_state
support_state
blocked_by
supports
grasp_candidates
safe_grasp_score
task_status
last_action
metadata
```

其中：

- `mask_polygon` 来自 YOLO-seg 或其他分割模型；
- `boundary_points` 可用于边界引导抓取；
- `visible_area_ratio` 用于判断遮挡程度；
- `grasp_candidates` 可来自抓取检测模型或启发式算法；
- `safe_grasp_score` 用于规划器排序；
- `metadata` 可保存 VLM 属性、unknown 原因、人工复核结果。

---

## 11. 与 RealSense、YOLO 和 VLM 的关系

推荐流程：

```text
YOLO-seg 输出类别、置信度、mask
  -> 高置信度已知类进入图谱候选状态
  -> 中置信度目标进入 VLM 属性一致性校验
  -> 低置信度或冲突目标进入 unknown/人工复核
  -> RealSense 深度补充 center_xyz、bbox_3d、空间关系
  -> 写入短期记忆层
  -> 长期知识层投影 risk/handling/grasp 先验
  -> LangGraph 规划器读取图谱状态
  -> ROS2 执行后回写事件日志和短期状态
```

长期知识层只提供稳定先验，不应被单次观测覆盖。短期记忆层反映当前场景，会随感知和机械臂动作持续变化。

---

## 12. 数据来源说明

当前长期知识中常见建筑拆除材料参考 EPA 对 C&D materials 的分类说明：

- <https://www.epa.gov/smm/sustainable-management-construction-and-demolition-materials>

Roboflow Universe 可以继续作为补充训练数据来源，尤其是玻璃类数据。但每个数据集都必须单独核查类别、许可证、标注质量和是否适合建筑垃圾场景。

---

## 13. RealSense 接入后的知识图谱职责边界

RealSense D435i 不负责定义新的长期类别，也不应该直接修改 `risk_level`、`handling_mode` 等长期先验。它的作用是把当前场景中的实例状态补充完整，使短期记忆层从“二维识别结果”升级为“可规划的三维世界状态”。

接入 RealSense 后，推荐的数据流为：

```text
RGB 图像
  -> YOLO-seg 输出类别、置信度、bbox、mask
  -> aligned depth 图补充每个 mask 内的深度点
  -> 计算 center_xyz、bbox_3d、visible_area_ratio、grasp_candidates、safe_grasp_score
  -> 写入 Instance 短期记忆节点
  -> 由长期 Category 投影风险、易碎性、处理方式等先验
  -> 规划器读取可抓取目标和需人工介入目标
```

需要保持以下边界：

- `Category` 长期知识层：稳定类别和处理先验，不因单帧观测改变；
- `Instance` 短期记忆层：由 YOLO、RealSense、VLM、执行反馈持续更新；
- `UnknownObjectMemory`：保存无法可靠归类的对象档案；
- `Event` 事件日志层：记录每次观测、识别复核、坐标更新、执行反馈；
- ROS2 执行层：只读取图谱筛选后的目标，不直接读取原始 YOLO 输出；
- UI 层：只负责展示、人工确认和任务审查，不直接控制机械臂。

第一阶段 RealSense 验证只要求输出相机坐标系下的 `center_xyz`。在真实抓取前，必须完成相机坐标系到机械臂基座坐标系的外参标定，即 `T_base_camera`。未完成该标定前，图谱中的三维坐标只能用于可视化、排序和空跑验证，不能直接作为真实夹爪闭合目标。
