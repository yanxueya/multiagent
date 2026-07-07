# 子项目结构

本目录按系统边界拆分。当前只有 `dynamic-waste-kg` 是已实现的核心子项目，其余目录为后续接入多智能体、ROS2、前端和仿真时的结构占位。

## 目录

- `dynamic-waste-kg/`：动态建筑废弃物知识图谱、数据集处理、感知流水线、论文实验。
- `dynamic-waste-agent/`：LangChain/LangGraph 风格的 5 智能体编排层，占位中。
- `dynamic-waste-ros2/`：ROS2 消息、桥接、执行器和启动包边界，占位中。
- `dynamic-waste-ui/`：前端或可视化控制台边界，占位中。
- `dynamic-waste-sim/`：仿真、数字孪生和离线回放边界，占位中。

## 关系

```text
dynamic-waste-ui
  -> dynamic-waste-agent
      -> dynamic-waste-kg
      -> dynamic-waste-ros2
          -> robot / sensors
      -> dynamic-waste-sim
```

## 维护原则

- 不把临时测试、论文草稿和中间实验文档放在根目录。
- 数据处理文档放到最接近数据资产的目录，例如 `dynamic-waste-kg/datasets/docs/`。
- 小论文补充实验文档放到 `dynamic-waste-kg/paper_experiments/docs/`。
- 占位目录必须说明职责、输入输出和当前状态，避免出现空目录或空 README。
