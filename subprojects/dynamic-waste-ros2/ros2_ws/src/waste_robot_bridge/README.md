# waste_robot_bridge

预留给多智能体系统与 ROS2 的桥接节点。

职责：

- 接收 `execution_agent` 的动作请求。
- 发布 ROS2 topic/service/action。
- 收集执行反馈并返回给 `dynamic-waste-agent`。
