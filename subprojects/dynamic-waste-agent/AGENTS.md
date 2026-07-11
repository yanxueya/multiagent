# dynamic-waste-agent 开发约束

本目录只负责 LangGraph 风格的多智能体编排，不直接维护数据集、训练脚本、论文草稿或 ROS2 包。

## 架构边界

当前只把以下 4 个角色视为真正智能体：

- `supervisor_agent`：总体规划与调度。
- `perception_agent`：感知结果组织与标准化。
- `action_planning_agent`：操作序列规划与失败恢复策略。
- `execution_agent`：结构化 ROS2 bridge 请求封装与反馈整理。

图中只有两个非智能体节点：

- `kg_writer`：严格校验结构化载荷后统一写 KG，不调用 LLM。
- `human_review_interrupt`：使用 `interrupt()` 暂停并等待 `Command(resume=...)`。

KG 查询、资格校验、ROS2 bridge、相机和模型运行时属于工具或服务，不额外包装成图节点。

## 决策边界

- 知识图谱不保存 `task_value`、规划优先级、评分或动作顺序。
- LangGraph State 只保存控制信息和 KG 引用，不复制完整 `graph_state`。
- `action_planning_agent` 通过只读 loader 临时读取候选，先做硬过滤，再按字典序只选择一个动作。
- 第一阶段禁止人工加权和历史统计评分；`rank_candidates` 只保留接口。
- `failed` 对象必须先形成新 Scene，重新观测后恢复为 `pending` 才能再次规划。
- `execution_agent` 只能发送结构化 ROS2 bridge 请求，不得把 LLM 自由文本发给机器人。
- 只有真实物理动作开始后才增加 `attempt_count`；同一 `action_id` 必须幂等。

## 运行约束

- 不在本目录直接运行模型训练。
- 涉及模型训练时，只输出用户可执行的操作指令，不要在沙盒里代跑训练。
- GPU 训练要合理：进行显式检查显存，并结合 8 GB 显存限制设计 batch size、输入尺寸和模型规模。

## 文档

- 架构说明放在本目录 README 或 `agent_system/prompts/README.md`。
- 中间实验记录不得放入本目录。
- 小论文相关补充实验仍放在 `dynamic-waste-kg/paper_experiments/docs/`。
