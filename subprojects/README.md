# 子项目结构

本目录按系统边界拆分。知识图谱核心、LangGraph 编排和 UI 原型已经实现；ROS2 与仿真仍是待接入边界。

## 目录

- `dynamic-waste-kg/`：动态建筑废弃物知识图谱、数据集处理、感知流水线、论文实验。
- `dynamic-waste-agent/`：三模式 LangGraph 编排层，包含 4 个 Agent 和 2 个确定性节点。
- `dynamic-waste-ros2/`：ROS2 消息、桥接、执行器和启动包边界，占位中。
- `dynamic-waste-ui/`：已实现的 React 工作台原型，接入 KG JSON snapshot，并预览 Agent trace、人工复核和 ROS2 命令。
- `dynamic-waste-sim/`：仿真、数字孪生和离线回放边界，占位中。

## 关系

```text
dynamic-waste-ui
  -> dynamic-waste-agent
      -> supervisor_agent（条件路由）
      -> perception_agent / action_planning_agent / execution_agent
      -> kg_writer / human_review_interrupt
      -> dynamic-waste-kg（事实、状态、事件）
      -> dynamic-waste-ros2（结构化命令桥接）
          -> robot / sensors
      -> dynamic-waste-sim
```

## 维护原则

- 不把临时测试、论文草稿和中间实验文档放在根目录。
- 数据处理文档放到最接近数据资产的目录，例如 `dynamic-waste-kg/datasets/docs/`。
- 小论文补充实验文档放到 `dynamic-waste-kg/paper_experiments/docs/`。
- 占位目录必须说明职责、输入输出和当前状态，避免出现空目录或空 README。
