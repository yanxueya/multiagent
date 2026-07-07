# dynamic-waste-sim

这是后续仿真、数字孪生和离线回放的占位子项目。

当前状态：结构占位，尚未选择 Gazebo、Isaac Sim、PyBullet 或自定义回放方案。

## 预期功能

- 在没有真实硬件时验证任务计划。
- 回放感知事件、KG 查询、风险判断和执行反馈。
- 为 ROS2 接入提供 dry-run 环境。

## 边界

- 不维护主数据集。
- 不承载小论文草稿。
- 与 `dynamic-waste-ros2` 通过仿真 topic/service/action 或日志回放接口连接。
