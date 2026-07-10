# dynamic-waste-agent

本子项目负责建筑废弃物分拣系统的 LangGraph 多智能体编排，不直接维护知识图谱事实、不训练模型、不直接控制 ROS2 硬件。

## 当前架构

```text
4 个真正智能体 + KG 状态底座 + 确定性门控与桥接组件
```

| 类型 | 名称 | 职责 |
| --- | --- | --- |
| Agent | `supervisor_agent` | 目标分解、流程调度、状态回收与重规划触发 |
| Agent | `perception_agent` | 组织 YOLO、VLM、RealSense 和人工输入的结构化感知事件 |
| Agent | `action_planning_agent` | 读取 KG 状态和风险门控，生成动作顺序与失败恢复 |
| Agent | `execution_agent` | 把已批准计划封装为结构化 ROS2 bridge 请求 |
| Component | `world_model_adapter` | 从 `dynamic-waste-kg` 投影长期类别属性、实例状态和事件引用 |
| Gate | `risk_gate` | 检查风险、复核要求、失败次数和当前可执行性 |
| Gate | `human_control_gate` | 接收人工确认、拒绝或保持未知的操作 |
| Bridge | `ros2_bridge` | 对接 ROS2/PiPER 的结构化接口 |
| Component | `feedback_update` | 把人工与执行反馈整理为 KG 事件回写 |

## 决策逻辑

知识图谱不保存规划优先级或评分。KG 适配层只把长期类别先验、当前实例状态和可行性投影为 `graph_state`；优先级仅由 `action_planning_agent` 在规划时动态计算。

```text
perception_agent
  -> world_model_adapter / KG graph_state
  -> risk_gate
  -> action_planning_agent
  -> human_control_gate 或 execution_agent
  -> ros2_bridge
  -> feedback_update / KG EventLog
```

规划器必须先排除 `can_attempt_now=false`、需要人工复核或被风险门控阻止的对象，再根据任务目标、YOLO 置信度、识别状态、当前处理策略和 `attempt_count` 计算 `dynamic_priority_score`。该评分只存在于规划结果，不回写知识图谱。

## 目录结构

```text
agent_system/
  agents/       # 4 个真正智能体描述
  components/   # KG 适配、风险门控等非智能体组件
  prompts/      # 智能体 prompt 与组件边界
  schemas/      # graph_state、计划和消息契约
  graph.py      # LangGraph 编排图
  planner.py    # 操作序列规划器
  state.py      # 共享状态
```

## 运行与测试

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-agent
.\.venv\Scripts\python.exe -m agent_system.graph
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

当前不声称已验证真实 ROS2 或机械臂闭环。`unknown` 是短期状态，不是 YOLO 类别或长期类别。
