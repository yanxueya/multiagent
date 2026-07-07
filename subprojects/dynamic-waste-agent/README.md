# dynamic-waste-agent

这是后续多智能体系统的占位子项目，目标是在 `dynamic-waste-kg` 已有知识图谱与感知结果之上，构建 LangChain/LangGraph 风格的任务编排层。

当前状态：结构占位，尚未接入真实 LLM、LangGraph、ROS2 或机器人执行器。

## 五个智能体

| 智能体 | 主要职责 | 上游输入 | 下游输出 |
| --- | --- | --- | --- |
| `perception_agent` | 汇总视觉检测、分割和场景状态 | 相机/YOLO/VLM/传感器结果 | 规范化感知事件 |
| `knowledge_agent` | 查询和更新动态废弃物知识图谱 | 感知事件、任务上下文 | 类型、属性、关系、处置约束 |
| `risk_agent` | 评估安全、环境和不确定性风险 | KG 结果、置信度、现场约束 | 风险等级与人工确认建议 |
| `planning_agent` | 生成分拣、搬运或避障计划 | 风险结果、任务目标、机器人能力 | 任务计划与动作候选 |
| `execution_agent` | 将计划转成 ROS2 可执行命令并跟踪反馈 | 任务计划、机器人状态 | 执行请求、状态反馈、异常事件 |

## 预期目录

```text
agent_system/
  agents/       # 5 个智能体的最小占位
  prompts/      # 各智能体提示词边界
  schemas/      # 跨智能体消息、动作、反馈结构
  tools/        # KG、ROS2、视觉工具适配器占位
  config.py     # 配置边界
  graph.py      # 编排图占位
  state.py      # 共享状态结构
```

## 运行

当前不提供业务运行入口。后续接入 LangGraph 后，建议提供：

```powershell
cd subprojects/dynamic-waste-agent
python -m agent_system.graph
```

## 测试

当前只做结构占位。后续应优先增加：

- 共享状态 schema 测试。
- 每个智能体的输入输出契约测试。
- KG 工具适配器的离线测试。
- ROS2 工具适配器的 mock 测试，避免在单元测试中启动真实机器人。
