# waste_robot_perception

预留给 ROS2 感知订阅与发布节点。

职责：

- 订阅相机、深度、点云或检测结果。
- 将感知数据整理为 `dynamic-waste-agent` 可消费的事件。
- 不在 ROS2 节点中直接训练模型。
