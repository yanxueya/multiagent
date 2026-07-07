# dynamic-waste-ros2

这是后续 ROS2 接入的占位子项目，目标是在 Ubuntu 22.04/ROS2 环境中承接机器人消息、桥接、执行器、感知订阅和 bringup。

当前状态：结构占位，尚未创建可编译 ROS2 package。

## 预期结构

```text
ros2_ws/src/
  waste_robot_msgs/        # 自定义 msg/srv/action 边界
  waste_robot_bridge/      # agent_system 与 ROS2 的桥接节点
  waste_robot_executor/    # 机械臂/移动平台执行适配器
  waste_robot_perception/  # 相机、点云、检测结果订阅适配器
  waste_robot_bringup/     # launch、参数、组合启动入口
```

## 与其他子项目的关系

- 上游：`dynamic-waste-agent` 的 `execution_agent` 只调用桥接接口，不直接控制硬件。
- 下游：真实机器人、仿真器或离线回放环境。
- 旁路：`dynamic-waste-sim` 可替代真实硬件用于验证。

## 运行

当前没有可编译包。后续在 Ubuntu 22.04 中建议使用：

```bash
cd subprojects/dynamic-waste-ros2/ros2_ws
colcon build
source install/setup.bash
ros2 launch waste_robot_bringup demo.launch.py
```
