# Neo4j 可视化知识图谱：从启动到查看

本文用于在 Windows 11 上用 Docker 启动 Neo4j，并把本项目的长期知识、短期记忆和事件日志导入 Neo4j Browser。

## 1. 图谱在 Neo4j 中怎么存

本项目在同一个 Neo4j 数据库中用三类节点表示三层知识：

```text
长期知识层：(:Category)
短期记忆层：(:Instance)
事件日志层：(:Event)
```

关系包括：

```text
(:Instance)-[:OF_CATEGORY]->(:Category)
(:Event)-[:ABOUT_CATEGORY]->(:Category)
(:Event)-[:ABOUT_INSTANCE]->(:Instance)
(:Instance)-[:NEAR|TOUCHING|ON_TOP_OF|BLOCKED_BY|SUPPORTS]->(:Instance)
```

## 2. 启动 Neo4j

打开 PowerShell，进入项目目录：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

启动 Neo4j：

```powershell
docker compose -f docker-compose.neo4j.yml up -d
```

查看容器是否启动：

```powershell
docker ps --filter "name=dynamic-waste-neo4j"
```

浏览器打开：

```text
http://localhost:7474/
```

登录信息：

```text
Connect URL: neo4j://localhost:7687
Username: neo4j
Password: wastekg123456
```

## 3. 导出本项目图谱 Cypher 文件

导出演示图谱：

```powershell
.\.venv\Scripts\python.exe scripts\export_demo_neo4j.py --out artifacts\demo_graph
```

或者导出单图识别后的图谱：

```powershell
.\.venv\Scripts\python.exe scripts\predict_image_to_graph.py --image "C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\datasets\waste12_yolo\images\val\cdw2026_2022_0345.jpg" --weights "C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\runs\segment\runs\waste12_seg\yolo11n_seg_cdw_glass_e50\weights\best.pt" --out artifacts\single_image_graph_demo --conf 0.25 --imgsz 640 --device 0
```

导出的 Neo4j 文件位置：

```text
artifacts\demo_graph\neo4j_import.cypher
artifacts\single_image_graph_demo\neo4j_import.cypher
```

本项目只维护一个 Neo4j 图谱导入文件。长期知识、短期记忆、事件日志都在同一张图里，查看时通过 Cypher 查询过滤不同层。

## 4. 导入 Neo4j

先清空数据库：

```powershell
docker exec dynamic-waste-neo4j cypher-shell -u neo4j -p wastekg123456 "MATCH (n) DETACH DELETE n"
```

导入演示图谱：

```powershell
.\.venv\Scripts\python.exe scripts\import_neo4j_cypher.py --cypher artifacts\demo_graph\neo4j_import.cypher --uri bolt://localhost:7687 --user neo4j --password wastekg123456
```

如果你想导入单张图片识别后的图谱，用：

```powershell
.\.venv\Scripts\python.exe scripts\import_neo4j_cypher.py --cypher artifacts\single_image_graph_demo\neo4j_import.cypher --uri bolt://localhost:7687 --user neo4j --password wastekg123456
```

## 5. 在 Neo4j Browser 中查看

查看长期知识层：

```cypher
MATCH (c:Category) RETURN c
```

查看类别属性表：

```cypher
MATCH (c:Category)
RETURN c.name, c.risk_level, c.fragility, c.graspability, c.pollution_level,
       c.handling_mode, c.grasp_difficulty, c.needs_llm_review, c.auto_processable
ORDER BY c.name
```

查看短期记忆层：

```cypher
MATCH (i:Instance) RETURN i
```

查看短期实例连接到长期类别：

```cypher
MATCH p=(i:Instance)-[:OF_CATEGORY]->(c:Category)
RETURN p
```

查看事件日志层：

```cypher
MATCH (e:Event)
RETURN e
ORDER BY e.timestamp DESC
LIMIT 30
```

查看事件与对象/类别的关联：

```cypher
MATCH p=(e:Event)-[]->()
RETURN p
LIMIT 100
```

查看完整图谱时可能会比较复杂，因为会同时显示类别、实例、事件和关系：

```cypher
MATCH p=()-->()
RETURN p
LIMIT 200
```

如果你想看清楚主结构，推荐直接看短期实例连接长期类别：

```cypher
MATCH p=(i:Instance)-[:OF_CATEGORY]->(c:Category)
RETURN p
```

查看核心规划关系：

```cypher
MATCH p=(a:Instance)-[r]->(b:Instance)
WHERE type(r) IN ["ON_TOP_OF", "BLOCKED_BY", "SUPPORTS", "TOUCHING", "REQUIRES_PRIOR_ACTION"]
RETURN p
```

如果要看事件日志，单独查事件，不要和主图混在一起：

```cypher
MATCH (e:Event)
RETURN e.event_type, e.subject_id, e.source, e.timestamp
ORDER BY e.timestamp DESC
LIMIT 30
```

## 6. 推荐在 Neo4j Browser 里设置颜色

在图上点一个 `Category` 节点，选择绿色。

在图上点一个 `Instance` 节点，选择蓝色。

在图上点一个 `Event` 节点，选择橙色。

这样你能直观看出：

```text
绿色：长期知识
蓝色：当前环境实例
橙色：事件日志
```

## 7. 停止 Neo4j

停止容器但保留数据：

```powershell
docker compose -f docker-compose.neo4j.yml down
```

重新启动后数据仍在：

```powershell
docker compose -f docker-compose.neo4j.yml up -d
```

如果未来想删除 Neo4j 数据，删除目录：

```text
artifacts\neo4j\data
```

不要随便删除，除非你确定不需要当前 Neo4j 数据。
