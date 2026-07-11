# Knowledge Graph Writer Contract

`kg_writer` 是确定性图节点，不调用 LLM，也没有自由文本 Prompt。

## 唯一职责

```text
Agent 结构化输出
  -> schema validator
  -> KG Writer
  -> KnowledgeGraph/Neo4j 事务
  -> KG summary reference
```

只接受四种写入信封：

```text
perception
planning
human_review
execution
```

每种 payload 都使用代码中的字段白名单。发现未知字段、未知关系、未知事件属性或任意 Cypher 时必须拒绝整次事务。

## 边界

- 不解释自然语言。
- 不推断类别、风险、优先级或动作。
- 不创建 schema 外节点、属性、关系或事件。
- PlanningEvent 只记录单步动作类型、理由和 SELECTS/IN_SCENE 关系。
- ExecutionEvent 只在真实物理动作开始后写入。
- 写入成功后只向 LangGraph 返回控制摘要和 KG 引用，不复制完整图谱。
