# tests

测试优先覆盖：

- 4 个真正智能体的输入输出边界。
- 非智能体图节点：kg_writer、human_review_interrupt。
- KG 查询、资格校验、ROS2 bridge 和传感器均为工具或服务，不额外包装成 Agent/图节点。
- 编排图节点顺序和失败分支。
- KG 工具的离线 mock。
- ROS2 bridge 工具的 mock，不启动真实机器人。
