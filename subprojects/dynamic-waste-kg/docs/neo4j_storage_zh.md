# Neo4j 存储与导出规范

本文档定义 Neo4j 的标签、主键和关系存储规范。在线启动、Agent 联动和 UI 更新步骤见 [三层知识图谱运行与联动指南](knowledge_graph_runtime_zh.md)。节点、字段和关系必须与 [knowledge_seed_zh.md](knowledge_seed_zh.md) 一致。

## 1. 节点标签

```text
WasteCategory
Scene
ObjectInstance
UnknownSample
UnknownCluster
Event + 具体事件标签
```

具体事件标签只有：

```text
DetectionEvent
VLMReviewEvent
DepthUpdateEvent
HumanReviewEvent
PlanningEvent
ExecutionEvent
KnowledgeEvolutionEvent
```

事件节点同时带 `Event` 和具体事件类型两个标签，例如：

```cypher
(:Event:DetectionEvent)
```

## 2. 主键

| 标签 | 主键 |
| --- | --- |
| `WasteCategory` | `category_name` |
| `Scene` | `scene_id` |
| `ObjectInstance` | `instance_id` |
| `UnknownSample` | `sample_id` |
| `UnknownCluster` | `cluster_id` |
| `Event:*` | `event_id` |

`ObjectInstance` 不保存类别名。类别通过 `CANDIDATE_OF` 和 `CONFIRMED_AS` 表达。

## 3. 关系

关系没有独立属性，基础结构包括：

```text
(:Scene)-[:CONTAINS]->(:ObjectInstance)
(:ObjectInstance)-[:CANDIDATE_OF]->(:WasteCategory)
(:ObjectInstance)-[:CONFIRMED_AS]->(:WasteCategory)
(:ObjectInstance)-[:NEAR]->(:ObjectInstance)
(:ObjectInstance)-[:RECORDED_AS]->(:UnknownSample)
(:UnknownSample)-[:MEMBER_OF]->(:UnknownCluster)
```

事件关系由 `wastekg/graph/store.py` 的关系白名单生成，例如 `DETECTED`、`REVIEWS`、`UPDATES`、`CONFIRMS`、`SELECTS`、`EXECUTES`、`EVOLVES`、`IN_SCENE` 和 `PROPOSED`。

## 4. 导出

当前同时支持离线 Cypher 导出和在线事务镜像。在线入口是：

```text
wastekg/graph/neo4j_store.py::Neo4jGraphMirror
```

它只执行仓库内部从 `KnowledgeGraph` 生成的语句，不接受 Agent 自由 Cypher。

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\graph\export_demo_neo4j.py
```

代码入口是：

```text
wastekg/graph/exporters.py::graph_to_neo4j_cypher
```

JSON 或列表等复合值会以 `*_json` 字符串属性导出，避免依赖 Neo4j 嵌套属性。

## 5. 常用查询

查看三层节点：

```cypher
MATCH (c:WasteCategory) RETURN c;
MATCH (s:Scene)-[:CONTAINS]->(i:ObjectInstance) RETURN s, i;
MATCH (e:Event) RETURN e ORDER BY e.event_time DESC;
```

查看候选与确认类别：

```cypher
MATCH p=(i:ObjectInstance)-[:CANDIDATE_OF|CONFIRMED_AS]->(c:WasteCategory)
RETURN p;
```

查看未知样本：

```cypher
MATCH p=(i:ObjectInstance)-[:RECORDED_AS]->(u:UnknownSample)
OPTIONAL MATCH (u)-[:MEMBER_OF]->(cluster:UnknownCluster)
RETURN i, u, cluster;
```

查看当前实例状态：

```cypher
MATCH (i:ObjectInstance)
RETURN i.instance_id,
       i.recognition_status,
       i.current_handling_policy,
       i.task_status,
       i.attempt_count,
       i.depth_valid_ratio,
       i.occlusion_state;
```

## 6. 禁止写入

Neo4j 节点不得额外保存 `task_value`、`dynamic_priority_score`、动作顺序、失败恢复计划或 `safe_grasp_score`。这些属于规划期或 RGB-D 临时计算，不是当前 KG 属性。
