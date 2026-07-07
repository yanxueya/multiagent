# dynamic-waste-agent 开发约束

本目录只负责多智能体编排，不直接维护数据集、训练脚本、论文草稿或 ROS2 包。

## 边界

- 通过 `dynamic-waste-kg` 获取知识图谱、类别、属性和感知流水线结果。
- 通过 `dynamic-waste-ros2` 的桥接接口发送机器人动作或订阅机器人反馈。
- 不在本目录直接运行模型训练。
- 涉及模型训练时，只输出用户可执行的操作指令，不要在沙盒里代跑训练。
- GPU 训练要合理：进行显式检查显存，并结合 8 GB 显存限制设计 batch size、输入尺寸和模型规模。

## 智能体职责

- `perception_agent`：只做感知结果汇总与语义标准化。
- `knowledge_agent`：只做 KG 查询、更新建议和证据组织。
- `risk_agent`：只做风险判断、置信度解释和人工确认建议。
- `planning_agent`：只做任务计划，不直接控制硬件。
- `execution_agent`：只做执行命令封装、状态跟踪和异常上报。

## 文档

- 架构说明放在本目录 README 或 `docs/`。
- 中间实验记录不得放入本目录。
- 小论文相关补充实验仍放在 `dynamic-waste-kg/paper_experiments/docs/`。
