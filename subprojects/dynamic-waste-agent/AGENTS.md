# dynamic-waste-agent 开发约束

本目录只负责 LangGraph 风格的多智能体编排，不直接维护数据集、训练脚本、论文草稿或 ROS2 包。

## 架构边界

当前只把以下 4 个角色视为真正智能体：

- `supervisor_agent`：总体规划与调度。
- `perception_agent`：感知结果组织与标准化。
- `action_planning_agent`：操作序列规划与失败恢复策略。
- `execution_agent`：结构化 ROS2 bridge 请求封装与反馈整理。

以下不是 agent，而是被 agent 调用或读取的系统组件：

- `dynamic-waste-kg` / `world_model_adapter`：知识图谱状态适配层，不是独立智能体。
- `risk_gate`：风险、复核和自动执行门控。
- `human_control_gate`：人工确认入口。
- `ros2_bridge`：ROS2/PiPER 结构化接口适配层。
- `feedback_update`：执行反馈和人工确认结果的 KG 回写入口。

## 决策边界

- 知识图谱不保存 `task_value`、规划优先级、评分或动作顺序。
- `graph_state` 只携带长期类别先验、当前实例状态、约束和可行性。
- `action_planning_agent` 必须先读取 `graph_state` 和 `risk_assessments` 做硬过滤，再在规划期动态计算 `priority_tier` 与 `dynamic_priority_score`。
- `can_attempt_now=false` 的对象只能延后、复核、解除阻塞或等待反馈更新，不能直接执行。
- `execution_agent` 只能发送结构化 ROS2 bridge 请求，不得把 LLM 自由文本发给机器人。

## 运行约束

- 不在本目录直接运行模型训练。
- 涉及模型训练时，只输出用户可执行的操作指令，不要在沙盒里代跑训练。
- GPU 训练要合理：进行显式检查显存，并结合 8 GB 显存限制设计 batch size、输入尺寸和模型规模。

## 文档

- 架构说明放在本目录 README 或 `agent_system/prompts/README.md`。
- 中间实验记录不得放入本目录。
- 小论文相关补充实验仍放在 `dynamic-waste-kg/paper_experiments/docs/`。
