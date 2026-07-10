# 提示词与组件说明索引

本目录明确区分“智能体 prompt”和“非智能体系统组件说明”。

## 真正的智能体

```text
agents/supervisor.md         # 总体规划与调度
agents/perception.md         # 感知组织
agents/action_planning.md    # 行动规划
agents/execution.md          # 执行封装
```

## 非智能体组件

```text
components/world_model_adapter.md  # KG 状态适配；文件名保留为内部兼容名
components/risk_gate.md            # 风险与安全门控
components/human_control_gate.md   # 人工控制门控
```

## 核心边界

```text
KG：保存长期类别知识、短期实例状态、关系和事件日志，不保存规划评分。
action_planning_agent：先按 graph_state 过滤不可执行对象，再动态计算优先级并生成操作顺序和失败恢复。
human_control_gate：处理人工确认，不是 LLM agent。
execution_agent：只封装经过批准的 ROS2 bridge 结构化请求。
```

`unknown` 是短期状态，不是长期类别。`priority_tier` 和 `dynamic_priority_score` 只属于规划输出，不写入 KG。
