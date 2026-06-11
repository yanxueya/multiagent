# Dynamic Waste Knowledge Graph

这是一个用于复杂建筑环境中危险废弃物认知与人机协同决策的动态知识图谱原型。

如果你是第一次接触这个项目，建议先从下面两个文件开始：

- [新手指南](docs/beginner_guide.md)
- [长期知识种子说明](docs/knowledge_seed_zh.md)
- [能够帮助理解图谱的测试](tests/)

## 它能做什么

- 保存长期类别知识和短期场景记忆
- 跟踪对象实例和空间关系
- 记录观测事件和动作事件
- 为后续多智能体系统提供规划查询接口
- 提供一个可以直接运行的 CLI 演示

## 运行测试

```bash
python -m unittest discover -s tests
```

## 运行演示

```bash
python -m wastekg.cli
python -m wastekg.cli --json
```

## 主要模块

- `wastekg.models`: graph data model
- `wastekg.store`: in-memory dynamic graph store and update engine
- `wastekg.knowledge_base`: default long-term knowledge seed
- `wastekg.interfaces`: perception input and LangGraph/ROS2 output adapters
- `wastekg.query`: planning-context extraction
- `wastekg.cli`: demo graph builder and CLI entrypoint

## 学习目标

- 理解长期知识和短期记忆的区别
- 理解对象关系是怎么存储和更新的
- 理解属性如何影响任务规划
- 理解后面如何衔接多智能体和 ROS2
