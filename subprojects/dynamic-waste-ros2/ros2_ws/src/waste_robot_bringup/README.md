# waste_robot_bringup

预留给 ROS2 launch、参数和组合启动入口。

职责：

- 管理仿真和真实机器人启动配置。
- 区分 dry-run、simulation 和 real-hardware 模式。
- 避免把个人机器路径写死到 launch 文件。
