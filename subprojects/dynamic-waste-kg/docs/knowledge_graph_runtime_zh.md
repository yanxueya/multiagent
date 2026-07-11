# 三层知识图谱运行与联动指南

本文说明当前知识图谱已经实现的结构、Neo4j 启动方式、事件写入路径，以及它与 LangGraph 智能体和 UI 的联动边界。属性定义以 [knowledge_seed_zh.md](knowledge_seed_zh.md) 和当前代码为准，本文不另造字段。

## 1. 当前完成状态

| 能力 | 状态 | 入口 |
| --- | --- | --- |
| 11 类长期知识种子 | 已实现 | `wastekg/core/knowledge_base.py` |
| Scene、ObjectInstance、Unknown 短期记忆 | 已实现 | `wastekg/graph/store.py` |
| 七类追加式事件 | 已实现 | `wastekg/core/models.py` |
| JSON、Mermaid、Cypher 导出 | 已实现 | `wastekg/graph/exporters.py` |
| Neo4j 在线事务镜像 | 已实现 | `wastekg/graph/neo4j_store.py` |
| Agent 唯一写入口 | 已实现 | `dynamic-waste-agent/agent_system/components/kg_writer.py` |
| 每次 Agent 写入后刷新 Neo4j/UI | 已实现，可按运行时启用 | `WasteKgRuntimeAdapter` |
| UI 三层浏览和事件更新流 | 已实现为快照轮询 | `dynamic-waste-ui` |
| 真实 ROS2/PiPER 闭环 | 尚未验证 | 后续工作 |

## 2. 三层结构

```text
长期知识层
  WasteCategory：11 个稳定类别、风险、易碎性、抓取先验、VLM 策略、处理策略、视觉原型

短期记忆层
  Scene：一次不可覆盖的场景观测
  ObjectInstance：当前对象识别、深度、遮挡、处理与任务状态
  UnknownSample / UnknownCluster：未知对象复核和受控知识演化入口

事件日志层
  DetectionEvent / VLMReviewEvent / DepthUpdateEvent
  HumanReviewEvent / PlanningEvent / ExecutionEvent / KnowledgeEvolutionEvent
```

长期知识不会被单次观测修改；短期状态会随新 Scene 和人工复核更新；事件只追加，不覆盖历史。`unknown` 是短期状态，不是第 12 个长期类别。

## 3. 完整信息流

```text
相机 / YOLO / VLM / D435i
  -> Perception Agent 组织结构化 Observation
  -> kg_writer 校验 write_type 和字段白名单
  -> 内存 KnowledgeGraph 提交 Scene、Instance、关系和 Event
  -> Neo4jGraphMirror 先确保 Schema，再在单个数据事务中执行受控 MERGE
  -> 原子刷新 UI kg-snapshot.json
  -> Supervisor 只接收 KG 引用、待复核 ID 和可执行 ID
  -> Action Planning Agent 读取当前 Scene 的候选快照并生成一个动作
  -> PlanningEvent 写回 KG
  -> Execution Agent 调用结构化 ROS2 工具
  -> ExecutionEvent 写回 KG，并令 scene_is_fresh=false
  -> 重新采集新 Scene，再感知和重规划
```

Neo4j、资格校验器和 `kg_writer` 都不是智能体。四个智能体仍然只有 Supervisor、Perception、Action Planning 和 Execution。

## 4. 事件如何触发智能体联动

| 已发生事件 | KG 变化 | Supervisor 下一步 |
| --- | --- | --- |
| `DetectionEvent` | 新增/更新实例和候选类别关系 | 检查复核队列和可执行队列 |
| `VLMReviewEvent` | 更新一致性证据 | 冲突或证据不足进入人工复核 |
| `DepthUpdateEvent` | 更新三维中心、深度有效率、尺寸和遮挡 | 重新执行确定性资格校验 |
| `HumanReviewEvent` | 确认类别、标记 unknown、允许或禁止机器人 | 回到 Supervisor，再决定规划或继续复核 |
| `PlanningEvent` | 记录单步计划及理由 | 校验通过后转 Execution |
| `ExecutionEvent` | 更新任务状态和 attempt_count | 强制新 Scene，禁止直接重试旧状态 |
| `KnowledgeEvolutionEvent` | 记录人工审核后的长期知识演化 | 重新加载经审核的长期种子 |

联动不是通过“监听 Neo4j 后让 LLM 自由反应”实现，而是由 LangGraph 的确定性边完成：`kg_writer -> supervisor_agent`。Neo4j 保存可追溯事实，LangGraph State 保存线程控制状态和 KG 引用。

## 5. 启动 Neo4j

先进入知识图谱子项目：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
Copy-Item .env.neo4j.example .env.neo4j
notepad .env.neo4j
```

把 `change-this-local-password` 改为本机专用密码，然后启动：

```powershell
docker compose --env-file .env.neo4j -f docker-compose.neo4j.yml up -d
docker compose --env-file .env.neo4j -f docker-compose.neo4j.yml ps
```

Ubuntu 命令只需把复制命令改为：

```bash
cp .env.neo4j.example .env.neo4j
nano .env.neo4j
docker compose --env-file .env.neo4j -f docker-compose.neo4j.yml up -d
```

浏览器打开 `http://localhost:7474`，连接地址使用 `bolt://localhost:7687`。用户名默认是 `neo4j`，密码使用 `.env.neo4j` 中设置的值。

## 6. 初始化和检查 Neo4j

安装当前包及驱动：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts\graph\sync_neo4j.py
```

脚本会交互式询问密码，不把密码写入命令历史。它会创建唯一约束，并同步一个包含三层节点和关系的示例图。

Neo4j Browser 验证：

```cypher
MATCH (n) RETURN labels(n) AS labels, count(*) AS count ORDER BY labels;
MATCH (c:WasteCategory) RETURN c.category_name, c.risk_level, c.default_handling_policy ORDER BY c.category_name;
MATCH (s:Scene)-[:CONTAINS]->(i:ObjectInstance) RETURN s, i;
MATCH (e:Event)-[r]->(target) RETURN e, type(r), target ORDER BY e.event_time DESC;
```

## 7. 在 LangGraph 运行时启用持续同步

运行进程通过环境变量取得密码，不把密钥写进代码：

```python
from agent_system.graph import GraphRuntime
from agent_system.integrations import WasteKgRuntimeAdapter
from wastekg.graph.neo4j_store import Neo4jGraphMirror

runtime = GraphRuntime()
mirror = Neo4jGraphMirror.from_env()
adapter = WasteKgRuntimeAdapter(
    graph,
    runtime.transient_objects,
    neo4j_mirror=mirror,
    ui_snapshot_path="../dynamic-waste-ui/public/data/kg-snapshot.json",
)
runtime.kg_writer_backend = adapter.write_backend
```

需要设置：

```text
WASTEKG_NEO4J_URI=bolt://localhost:7687
WASTEKG_NEO4J_USER=neo4j
WASTEKG_NEO4J_PASSWORD=<本机密码>
WASTEKG_NEO4J_DATABASE=neo4j
```

每次 `perception / planning / human_review / execution` 写入完成后，适配器都会同步 Neo4j 并原子刷新 UI 快照。Neo4j 故障会以 `neo4j_sync.status=failed` 显式返回；已经提交的内存事实不会被伪装成未发生。

## 8. 后续如何添加知识

新增场景或对象必须走 `Observation -> kg_writer`；人工结论必须走 `HumanReviewEvent`；执行结果必须走 `ExecutionEvent`。Agent 不允许传入自由 Cypher。

修改长期类别时必须同时修改并复核：

```text
wastekg/core/knowledge_base.py
wastekg/core/taxonomy.py
docs/knowledge_seed_zh.md
对应测试
```

只有人工审核、数据审计、重新训练和独立验证完成后，才允许通过 `KnowledgeEvolutionEvent` 更新长期知识。不能把单次 VLM 判断直接写成新类别或长期属性。

## 9. UI 启动和更新

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-ui
npm ci
npm run dev
```

知识图谱页每 5 秒重新读取 `public/data/kg-snapshot.json`，展示：

- 长期知识层：11 类目录、风险、处理策略和其他权威属性。
- 短期记忆层：Scene、实例、UnknownSample 和 UnknownCluster。
- 事件日志层：事件来源、事件到对象/场景/类别的关系和更新顺序。
- 局部关系图：选中节点的一跳关系和真实关系名，避免完整图谱溢出画布。

当前 UI 是只读监控和人工复核原型，不直接连接 Bolt，也不允许浏览器写 Neo4j。生产接入时应在 Python 服务层提供只读查询和受控复核 API，浏览器不得持有 Neo4j 密码。
