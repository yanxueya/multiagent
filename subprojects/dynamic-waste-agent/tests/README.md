# tests

测试优先覆盖：

- 4 个真正智能体的输入输出边界。
- 非智能体组件：world_model_adapter、risk_gate、human_control_gate、ros2_bridge。
- 编排图节点顺序和失败分支。
- KG 工具的离线 mock。
- ROS2 bridge 工具的 mock，不启动真实机器人。
