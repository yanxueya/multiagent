# 动态废弃物知识图谱新手指南

这份指南是给初学者看的，目标是让你一步一步理解这个知识图谱怎么用、每个部分是什么意思，以及以后怎么继续接入多智能体和 ROS2。

## 1. 这个项目是什么

这个项目是一个可运行的知识图谱原型，用来描述建筑废弃物和危险废弃物场景。

它有三层：

- 长期知识：物体“是什么”，比如类别、风险等级、材质
- 短期记忆：物体“现在是什么状态”，比如位置、姿态、优先级、关系
- 事件日志：什么变了、什么时候变的、为什么变

这个图谱后面要给多智能体规划和 ROS2 执行提供共享状态。

## 2. 先看哪些文件

建议你先看这几个文件：

- `wastekg/models.py`：定义数据结构
- `wastekg/store.py`：保存和更新图谱
- `wastekg/knowledge_base.py`：给长期知识层提供默认种子
- `wastekg/interfaces.py`：YOLO+大模型入口、LangGraph/ROS2 出口
- `wastekg/query.py`：给后续智能体生成规划上下文
- `wastekg/cli.py`：生成一个演示场景

## 3. 一步一步使用

### 第一步：创建图谱

```python
from wastekg.store import KnowledgeGraph

graph = KnowledgeGraph()
```

这时你得到的是一个空图谱，里面还没有类别、没有物体、也没有关系。

### 第二步：加入长期知识

```python
from wastekg.models import CategorySpec

graph.register_category(
    CategorySpec(
        name="paint_can",
        category="hazardous_waste",
        material="metal",
        risk_level="high",
        graspability="low",
        recyclability="low",
    )
)
```

这一步是在加长期知识。它不应该因为物体移动了就改变。

### 第三步：加入第一次观测

```python
from wastekg.models import DetectedObject, Observation

obs1 = Observation(
    frame_id="frame_001",
    source="realsense",
    objects=[
        DetectedObject(
            temp_id="t1",
            class_name="paint_can",
            confidence=0.93,
            center_xyz=(0.10, 0.12, 0.08),
            risk_level="high",
        )
    ],
)

summary1 = graph.apply_observation(obs1)
```

这一步会在短期记忆层里创建一个实例节点，比如 `paint_can_01`。

### 第四步：查看结果

```python
print(summary1)
print(graph.instances["paint_can_01"].to_dict())
```

你重点看这些字段：

- `instance_id`
- `class_name`
- `center_xyz`
- `priority`
- `risk_level`
- `task_status`

### 第五步：对同一个物体再观测一次

```python
obs2 = Observation(
    frame_id="frame_002",
    source="realsense",
    objects=[
        DetectedObject(
            temp_id="t1",
            class_name="paint_can",
            confidence=0.96,
            center_xyz=(0.14, 0.15, 0.08),
            risk_level="high",
        )
    ],
)

summary2 = graph.apply_observation(obs2)
```

这时图谱应该更新同一个实例，而不是新建一个对象。

你可以从这里学到：

- 短期记忆会跨帧保持“同一个对象”的身份
- 位置信息会变化
- 置信度会变化
- 事件日志会记录更新过程

### 第六步：加入两个对象之间的关系

```python
obs3 = Observation(
    frame_id="frame_003",
    source="realsense",
    objects=[
        DetectedObject(temp_id="a", class_name="brick", confidence=0.95, center_xyz=(0.0, 0.0, 0.0)),
        DetectedObject(temp_id="b", class_name="paint_can", confidence=0.94, center_xyz=(0.0, 0.0, 0.10), risk_level="high"),
    ],
)

graph.apply_observation(obs3)
```

因为 `paint_can` 在 `brick` 上面，图谱可以推断出类似 `on_top_of` 这样的关系。

这一步很重要，因为后续任务规划要依赖对象之间的关系。

### 第七步：查询规划上下文

```python
from wastekg.query import build_planning_context

context = build_planning_context(graph)
print(context["candidates"])
print(context["blocked"])
print(context["risky"])
```

这就是后面多智能体应该使用的接口。

### 第八步：标记对象已经处理完

```python
graph.mark_processed("paint_can_01", action="picked_and_removed")
```

这一步会修改短期记忆状态，并写入一条事件。

## 4. 先种长期知识，再接感知和执行

如果你想把项目当成完整系统来学，推荐顺序是：

### 先种长期知识

```python
from wastekg import KnowledgeGraph, seed_default_categories

graph = KnowledgeGraph()
seed_default_categories(graph)
print(graph.categories["glass"].to_dict())
```

这样你就能先得到一套稳定的类别知识。

### 再接 YOLO + 大模型输入

```python
from wastekg import VisionDetection, VisionPacket, vision_packet_to_observation

packet = VisionPacket(
    frame_id="frame_001",
    source="camera",
    detections=[
        VisionDetection(
            temp_id="d1",
            yolo_class_name="brick",
            yolo_confidence=0.72,
            llm_class_name="glass",
            llm_confidence=0.88,
            center_xyz=(0.1, 0.1, 0.0),
            risk_hint="medium",
        )
    ],
)

obs = vision_packet_to_observation(packet)
graph.apply_observation(obs)
```

这里的意思是：

- YOLO 先给一个初筛结果
- 大模型可以复核并覆盖
- 最后统一变成图谱可用的 `Observation`

### 最后接 LangGraph / ROS2 输出

```python
from wastekg import PlannerRequest, build_langgraph_state, build_ros2_action_command

state = build_langgraph_state(
    graph,
    PlannerRequest(task_id="task_001", objective="sort_glass", target_categories=["glass"]),
)

action = build_ros2_action_command("pick", "glass_01", {"gripper": "close"}, requires_confirmation=True)
print(state["planning_context"]["candidates"])
print(action)
```

这一步的意思是：

- LangGraph 读取图谱，生成规划状态
- ROS2 只接收结构化动作命令
- 执行后再把反馈写回图谱

## 5. 长期知识和短期记忆有什么区别

### 长期知识

保存在 `graph.categories` 里。

例如：

- `paint_can` 是危险物
- `brick` 风险低
- `metal` 风险中等

这类知识应该保持稳定，除非你的领域知识本身发生变化。

### 短期记忆

保存在 `graph.instances` 里。

例如：

- `paint_can_01` 从一个位置移动到了另一个位置
- `paint_can_01` 可能被 `brick_01` 挡住
- `paint_can_01` 可能已经处理完，也可能还在等待

这类信息会随着每次观测和操作持续变化。

## 6. 交互关系怎么理解

交互关系表示一个物体会影响另一个物体。

常见关系有：

- `on_top_of`
- `touching`
- `near`
- `blocked_by`
- `supports`

这些关系很重要，因为规划器不能把所有物体都当成互相独立的。

## 7. 属性怎么理解

属性就是节点和边上保存的信息。

### 实例属性

- `center_xyz`
- `priority`
- `risk_level`
- `processable`
- `graspable`
- `blocked_by`

### 类别属性

- `material`
- `risk_level`
- `graspability`
- `recyclability`

## 8. 后面怎么继续

当你理解这个原型以后，下一步就是把下面这些东西接进来：

1. RealSense D435i 输入
2. YOLOv11 目标检测
3. 多模态复核
4. LangGraph 多智能体
5. ROS2 执行

图谱应该一直作为这些模块之间的共享状态中心。

## 9. 建议的学习顺序

1. 先跑测试
2. 看新手指南
3. 看演示 CLI
4. 改一个类别
5. 新增一个物体
6. 新增一个关系
7. 查询规划上下文
8. 标记一个对象为已处理

## 10. 常用命令

在 `subprojects/dynamic-waste-kg` 目录下运行：

```bash
python -m unittest discover -s tests
python -m wastekg.cli
python -m wastekg.cli --json
```
