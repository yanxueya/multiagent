# 全项目架构审计与图件说明

本目录基于当前代码、测试和权威知识种子，对动态建筑废弃物工作区进行架构复核。图件参考了用户提供示例的分层、流水线和纵向智能体布局，但所有内容均按本项目实际实现重绘。

## 图件

1. [三层动态知识图谱架构](figures/fig1_three_layer_knowledge_graph.svg)
2. [低置信度与人工复核信息流](figures/fig2_low_confidence_human_review_flow.svg)
3. [LangGraph 多智能体架构](figures/fig3_multi_agent_architecture.svg)
4. [全项目 Framework](figures/fig4_full_project_framework.svg)

每张图同时提供 SVG 和 2400×1350 PNG。SVG 可在 Inkscape、Illustrator、PowerPoint 或浏览器中继续编辑；PNG 用于快速预览。生成入口：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\tools\render_architecture_figures.py
```

## 审计结论

### 已确认一致

- 长期层固定为 11 个 `WasteCategory`；`unknown` 仅为短期状态。
- 类别通过 `CANDIDATE_OF` / `CONFIRMED_AS` 表达，不作为 Neo4j `ObjectInstance` 属性持久化。
- 七类事件具有固定来源、字段枚举和追加式语义。
- KG 保存领域事实；LangGraph State 保存线程控制字段和 KG 引用。
- 规划器先做确定性硬过滤，再以无权重字典序选择唯一下一步动作。
- Agent 不能提交任意 Cypher；`kg_writer` 是唯一受控写入口。
- 只有真实物理动作已开始才记录 `ExecutionEvent` 并增加 `attempt_count`。
- UI 读取结构化 snapshot，不承担核心推理。

### 需要在论文中降级表述

- 四个 Agent 已作为 LangGraph 角色节点和契约实现，但当前代码中没有可见的 LLM runtime 调用；准确表述是“LangGraph multi-agent workflow prototype”，不能仅凭节点命名声称四个大模型智能体已经在线自主推理。
- `vision_tool`、`ros2_tool` 仍为 placeholder；真实 RealSense、ROS2、MoveIt 和 PiPER 尚未接通。
- UI 的 Agent trace、仿真和 ROS2 页面仍主要是预览/占位数据。
- Neo4j 单元测试使用模拟 driver；本轮 Docker daemon 未运行，未完成在线数据库连通性和真实事务验收。

### 高优先级问题

1. `Neo4jGraphMirror.sync_graph()` 只执行 `MERGE`，不会清理内存图中已经删除的节点和关系。`discard_detection` 或其他状态移除后，Neo4j 可能保留 stale state。运行时适配器目前调用的正是 `sync_graph()`，因此在将 Neo4j 作为在线镜像前需要增加精确同步/受控替换策略及回归测试。
2. 内存 KG 提交后，Neo4j 失败会返回显式失败状态；UI snapshot 写入失败则会直接抛出异常。调用方可能误以为 KG 未提交而重试。应将 UI 发布也隔离为 `failed` 状态并测试原子写入失败路径。
3. 真实执行契约还没有确认令牌、急停状态、工作区/关节限位、碰撞检查结果等完整字段。当前 `requires_confirmation` 只是布尔字段，执行 validator 也未校验真实确认凭证。接真机前必须在 ROS2 action/bridge 层补齐。

### 中优先级问题

1. 跨帧实例匹配只有有效深度时才按同类别三维中心匹配；纯 RGB 固定视角动态序列会频繁创建新实例。这与现有 E4 `persisted=0` 失败相符。需要在独立开发序列上增加显式 track ID 或受控 2D IoU/appearance fallback，再冻结参数验证 holdout。
2. `VisionDetection` 仍保留 `llm_class_name`、`llm_confidence` 和 `safe_grasp_score` 等历史兼容字段。虽然当前逻辑不允许 VLM 直接覆盖类别，且综合分数不进入 KG，但接口命名容易误导。后续应迁移为 `vlm_consistency`、结构化视觉属性和临时几何可行性字段。
3. PlanningEvent 复用了 `action_id` 作为 `event_id`，与文档中 `evt_...` 的统一事件 ID 约定不完全一致。应明确这是有意的一对一关联，或拆分 `event_id` 与 `action_id`。
4. 当前默认 `InMemorySaver` 不适合长任务恢复；真实 UI/ROS2 接入前需要持久化 checkpointer。

## 图形语义

- 实线框/实线箭头：当前代码中已有实现或受控契约。
- 虚线框/虚线箭头：外部服务、硬件或后续接入。
- 绿色：知识状态与存储。
- 蓝色：感知或 Agent 角色节点。
- 橙色：人工复核与 unknown 路径。
- 紫色：外部工具、ROS2 和硬件。
- 红色：安全或证据边界。

## 当前验证结果

```text
dynamic-waste-kg:    124 tests passed
dynamic-waste-agent: 20 tests passed
dynamic-waste-ui:     9 tests passed
UI production build: passed
Neo4j live database:  not verified in this audit
ROS2/PiPER hardware:  not implemented / not verified
```
