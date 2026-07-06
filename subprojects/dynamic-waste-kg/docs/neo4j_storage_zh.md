# Neo4j 存储与可视化建议

如果你决定把当前知识图谱接到 Neo4j，我建议采用“**当前状态图 + 事件日志图**”的双层方式。

## 1. 为什么这样做

Neo4j 适合存储“当前状态”：

- 当前有哪些类别
- 当前有哪些实例
- 当前有哪些关系

但对于你的项目来说，只存当前状态还不够，因为你还需要：

- 记录每次观测
- 记录每次状态更新
- 记录每次执行动作
- 记录为什么发生变化

因此更稳的做法是：

1. Neo4j 保存当前状态图
2. 事件节点保存变化历史
3. 另外导出 JSONL 作为可追加的日志文件

## 2. 推荐的节点类型

### 2.1 `:Category`

表示长期知识层中的类别节点。

属性示例：

- `name`
- `category`
- `material`
- `risk_level`
- `fragility`
- `graspability`
- `pollution_level`
- `recyclability`
- `semantic_tags`
- `confidence_prior`

### 2.2 `:Instance`

表示当前场景中的具体对象实例。

属性示例：

- `instance_id`
- `class_name`
- `center_xyz`
- `orientation`
- `confidence`
- `priority`
- `task_status`
- `risk_level`
- `fragility_level`
- `graspability_level`
- `pollution_level`
- `blocked_by`
- `supports`

### 2.3 `:Event`

表示一次变化事件。

这是你最关心的部分。

属性示例：

- `event_id`
- `event_type`
- `subject_id`
- `relation`
- `timestamp`
- `source`
- `confidence_delta`
- `before_state_json`
- `after_state_json`
- `metadata_json`

### 2.4 为什么事件要用 JSON 字符串

Neo4j 节点属性适合存标量、字符串和列表，但不适合直接塞嵌套字典结构。为了让事件可持久、可检索、可迁移，建议把：

- `before_state`
- `after_state`
- `metadata`

统一转成 JSON 字符串保存到：

- `before_state_json`
- `after_state_json`
- `metadata_json`

这样做的好处是：

1. 可以直接落库，不会因为复杂嵌套结构报错；
2. 可以保留完整上下文，方便以后回放和调试；
3. 以后如果你想把事件导出到文件、消息队列或对象存储，也不用再做结构转换。

## 3. 推荐的关系类型

### 3.1 类别和实例

- `(:Instance)-[:OF_CATEGORY]->(:Category)`

### 3.2 实例和实例

- `(:Instance)-[:ON_TOP_OF]->(:Instance)`
- `(:Instance)-[:TOUCHING]->(:Instance)`
- `(:Instance)-[:NEAR]->(:Instance)`
- `(:Instance)-[:BLOCKED_BY]->(:Instance)`
- `(:Instance)-[:SUPPORTS]->(:Instance)`

### 3.3 事件和对象

- `(:Event)-[:ABOUT_INSTANCE]->(:Instance)`
- `(:Event)-[:ABOUT_CATEGORY]->(:Category)`

如果一个事件同时影响两个实例，也可以再加：

- `(:Event)-[:SOURCE_INSTANCE]->(:Instance)`
- `(:Event)-[:TARGET_INSTANCE]->(:Instance)`

## 4. 事件应该怎么存

我建议你把事件按“**追加写入**”来存，而不是覆盖写。

### 推荐写法

每次发生新事件时：

1. 创建一个新的 `:Event` 节点
2. 把本次事件的 `before_state` 和 `after_state` 序列化为 JSON 字符串
3. 用关系把事件连到相关实例或类别

如果这次事件是关系变化，还建议再连两条边：

- `(:Event)-[:SOURCE_INSTANCE]->(:Instance)`
- `(:Event)-[:TARGET_INSTANCE]->(:Instance)`

### 为什么要这样

- 便于追溯
- 便于调试
- 便于复现实验
- 便于后面做时间线分析

### 不建议的写法

不要把所有历史事件都直接写成当前实例的一堆属性，否则会失去变化过程。

## 5. 当前图谱和事件图怎么分

### 当前图谱

只表示“现在是什么样子”：

- 当前有哪些对象
- 当前对象在哪
- 当前对象之间是什么关系

### 事件图

只表示“它是怎么变成现在这样的”：

- 哪帧图像来了
- 哪次推理触发了更新
- 哪次机械臂动作导致状态变化

## 6. 可视化怎么做得更美观

我建议你至少保留两种可视化：

### 6.1 Mermaid 静态图

适合：

- 论文
- Markdown 文档
- 调试说明

当前项目里已经支持导出 Mermaid。
你可以把它理解成“论文友好版图谱截图”。
适合在图里同时呈现：

- 长期知识层
- 短期记忆层
- 事件日志层

这样读者一眼就能看出系统不是静态分类器，而是动态世界模型。

### 6.2 Neo4j Browser 交互图

适合：

- 现场查看
- 节点点击检查
- 关系过滤
- 事件链回放

建议你在 Neo4j 里把三类节点设成不同颜色：

- `Category` 用绿色系，表示长期知识；
- `Instance` 用蓝色系，表示当前场景；
- `Event` 用橙色系，表示时间演化。

这样你自己在调试时也更容易区分状态和历史。

## 7. 消息输入输出怎么设计

### 输入消息

建议统一成 `VisionPacket`：

- 一帧图像的检测结果
- YOLO 的初筛结果
- 大模型的复核结果
- 深度/位姿信息

### 输出消息

建议统一成：

- `Observation`
- `PlannerRequest`
- `Ros2ActionCommand`
- `ExecutionFeedback`

如果你要做跨模块通信，推荐的实际顺序是：

1. 视觉模块输出 `VisionPacket`
2. `vision_packet_to_observation()` 转成 `Observation`
3. `graph.apply_observation()` 写入图谱
4. `build_langgraph_state()` 生成规划器状态
5. `build_ros2_action_command()` 生成执行命令
6. `apply_execution_feedback()` 将执行结果回写图谱

这样感知、规划、执行就能分层处理。

这样感知、规划、执行就能分层处理。

## 8. 你现在这个项目里最合适的存储组合

我建议你用下面的组合：

- `graph_to_json_snapshot()`：保存当前状态快照
- `graph_events_to_jsonl()`：保存事件日志
- `graph_to_mermaid()`：生成文档和论文图
- `graph_to_neo4j_cypher()`：导入 Neo4j

如果你后面要正式接 Neo4j，建议再加一个习惯：

- 当前状态图放在 Neo4j
- 事件日志同时保留一份 JSONL 文件
- 每次实验结束把 JSON 快照也存一份

这样以后做对比实验会非常省事。

## 9. 实际建议

如果你现在还在开发阶段，建议先：

1. 继续用 Python 内存图做算法原型
2. 把事件导出成 JSONL
3. 把当前状态导出成 JSON
4. 等流程稳定后，再导入 Neo4j

这样你不会一开始就被数据库约束住。
