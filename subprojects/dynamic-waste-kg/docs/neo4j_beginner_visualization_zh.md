# Neo4j 新手可视化教程

本教程只使用当前导出标签和关系。先阅读 [Neo4j 存储与导出规范](neo4j_storage_zh.md) 可了解字段边界。

## 1. 生成 Cypher

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\graph\export_demo_neo4j.py
```

也可以从真实图谱快照调用 `wastekg.graph.exporters.graph_to_neo4j_cypher()` 生成导入语句。

## 2. 导入

在 Neo4j Browser 中逐条执行生成的 `MERGE` 和 `MATCH ... MERGE` 语句，或使用项目已有导入脚本执行 Cypher 文件。导入前确认数据库地址、用户名和密码来自本机配置，不要把密码写入 Git。

## 3. 从长期类别开始

```cypher
MATCH (c:WasteCategory)
RETURN c
ORDER BY c.category_name;
```

预期只有 11 个 `WasteCategory`，不应出现 `unknown`。

## 4. 查看场景和对象

```cypher
MATCH p=(s:Scene)-[:CONTAINS]->(i:ObjectInstance)
RETURN p;
```

对象节点只显示实例状态，类别需要通过关系查询：

```cypher
MATCH p=(i:ObjectInstance)-[:CANDIDATE_OF|CONFIRMED_AS]->(c:WasteCategory)
RETURN p;
```

## 5. 查看未知对象

```cypher
MATCH p=(i:ObjectInstance)-[:RECORDED_AS]->(u:UnknownSample)
OPTIONAL MATCH q=(u)-[:MEMBER_OF]->(cluster:UnknownCluster)
RETURN p, q;
```

`UnknownSample` 是短期记忆入口，不是长期类别。

## 6. 查看事件链

```cypher
MATCH (e:Event)
OPTIONAL MATCH p=(e)-[]->()
RETURN e, p
ORDER BY e.event_time DESC;
```

按类型过滤：

```cypher
MATCH (e:ExecutionEvent)
RETURN e
ORDER BY e.event_time DESC;
```

## 7. 推荐样式

- `WasteCategory`：绿色。
- `Scene`：紫色。
- `ObjectInstance`：蓝色。
- `UnknownSample`、`UnknownCluster`：黄色。
- `Event`：红色。

颜色只用于识别节点层级，不改变任何知识语义。

## 8. 常见问题

查询不到 `Category` 或 `Instance`：当前标签已改为 `WasteCategory` 和 `ObjectInstance`。

查询不到 `OF_CATEGORY`：当前类别关系已拆分为 `CANDIDATE_OF` 与 `CONFIRMED_AS`。

看到 `task_value` 或 `safe_grasp_score`：说明导入了旧快照，应重新用当前 exporter 生成并清理旧测试数据库。
