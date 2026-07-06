# Dynamic Waste Knowledge Graph

本子项目是“复杂动态建筑环境中的建筑废弃物认知与人机协同决策”项目的知识图谱与世界模型层。

当前稳定设计：

```text
11 个明确视觉类别 + 系统逻辑生成 unknown
```

YOLO 负责检测和实例分割明确类别；VLM 不直接自由识别物体，而是提取结构化视觉属性并检查这些属性是否支持 YOLO 的类别假设；知识图谱负责长期类别先验、短期实例状态、unknown 记忆入口、事件日志和规划接口。

---

## 快速入口

第一次阅读建议按顺序看：

1. [文档导航](docs/README.md)
2. [长期知识层种子说明](docs/knowledge_seed_zh.md)
3. [论文方法与系统设计沉淀文档](docs/paper_method_system_design_zh.md)
4. [从零开始运行完整流程](docs/full_beginner_pipeline_zh.md)
5. [Neo4j 存储与可视化建议](docs/neo4j_storage_zh.md)
6. [RealSense RGB-D 接入教程](docs/realsense_rgbd_pipeline_zh.md)

---

## 当前职责边界

`dynamic-waste-kg` 只负责知识图谱与世界模型，不直接控制机械臂，也不承担最终 UI。

它应该负责：

- 长期类别知识；
- 短期对象记忆；
- unknown 对象记忆入口；
- 事件日志；
- YOLO/RealSense/VLM 到图谱的输入适配；
- Neo4j 导出和可视化；
- 给 LangGraph 与 ROS2 输出规划状态。

后续推荐整体项目结构：

```text
multiagent/
  subprojects/
    dynamic-waste-kg/       # 知识图谱与世界模型
    dynamic-waste-agent/    # LangGraph 多智能体规划
    dynamic-waste-ros2/     # Ubuntu/ROS2 机械臂执行层
    dynamic-waste-ui/       # 人工复核与监控界面
    dynamic-waste-sim/      # 可选仿真环境
```

核心数据流：

```text
YOLO/RealSense/VLM -> dynamic-waste-kg -> LangGraph planner -> ROS2 executor -> dynamic-waste-kg event feedback
```

---

## 当前类别体系

YOLO 和长期知识层默认使用 11 个明确类别：

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

`unknown` 不是 YOLO 训练类别，而是以下情况触发的系统状态：

- YOLO 置信度极低；
- VLM 属性与 YOLO 假设冲突；
- 证据不足；
- 物体疑似危险或无法可靠归类；
- 人工复核前不宜进入自动处理。

---

## 运行测试

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

---

## 主要模块

- `wastekg.models`: 图谱数据模型；
- `wastekg.knowledge_base`: 11 类长期知识种子；
- `wastekg.taxonomy`: 类别常量、别名映射和 unknown 边界；
- `wastekg.perception_pipeline`: YOLO/VLM 记录到图谱的转换；
- `wastekg.llm_reviewer`: OpenAI-compatible VLM 复核器；
- `wastekg.store`: 内存图谱与增量更新；
- `wastekg.interfaces`: LangGraph/ROS2 状态接口；
- `wastekg.rgbd_geometry`: RealSense RGB-D 几何补全；
- `wastekg.exporters`: JSON、Mermaid、Neo4j 导出；
- `paper_experiments/`: 小论文 E0-E4 补充实验。

