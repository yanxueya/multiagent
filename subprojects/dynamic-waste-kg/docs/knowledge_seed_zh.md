# 长期知识层种子说明

这份文档说明当前知识图谱里“长期知识层”是怎么预先构建的。

## 1. 设计原则

长期知识层表示“一个物体本质上是什么”，因此它应该尽量稳定，不随单次观测变化。

这里的等级标签 `low / medium / high` 是为了后续机器人处理方便而做的**工程化离散**，不是法规分类。

也就是说：

- `risk_level` 表示处理风险
- `fragility` 表示易碎程度
- `graspability` 表示可抓握程度
- `pollution_level` 表示污染/残留风险

这些标签结合真实废弃物材料属性、处理常识和研究任务需求得到。

## 2. 主要来源

本项目的长期知识种子主要参考了以下官方来源：

- [EPA: Sustainable Management of Construction and Demolition Materials](https://www.epa.gov/smm/sustainable-management-construction-and-demolition-materials)
- [OSHA: Asbestos](https://www.osha.gov/asbestos)

其中 EPA 页面说明了建筑拆除和施工废弃物中常见的材料类别，如混凝土、砖、木材、金属、石膏板、玻璃、沥青等；OSHA 页面说明了石棉的严重健康危害。

## 3. 当前种子类别

当前默认种子包括：

- `soft_plastic`
- `hard_plastic`
- `concrete`
- `brick`
- `paperboard`
- `asphalt`
- `wood`
- `metal`
- `gypsum`
- `glass`
- `asbestos`
- `waste_paint_can`

## 4. 典型等级解释

### 玻璃

- `risk_level = medium`
- `fragility = high`
- `pollution_level = low`
- `graspability = low`

理由：

- 玻璃易碎，破裂后有割伤风险
- 通常不属于高毒污染物，但碎片危险明显
- 对机器人来说不适合直接用粗暴抓取方式处理

### 石棉

- `risk_level = high`
- `fragility = high`
- `pollution_level = high`
- `graspability = low`

理由：

- OSHA 明确将石棉视为严重健康危害
- 对机器人系统应默认高风险处理
- 应优先隔离和人工确认

### 废油漆桶

- `risk_level = high`
- `fragility = low`
- `pollution_level = medium`
- `graspability = low`

理由：

- 如果容器内存在残留油漆、溶剂或未知污染物，应按高风险处理
- 这里是面向机器人分拣的工程判定，强调“未知残留”风险

## 5. 如何扩展

如果你以后要新增一种材料，建议按下面步骤做：

1. 判断它属于哪一大类：建筑废弃物、可回收物、危险废弃物
2. 给它填 `risk_level / fragility / graspability / pollution_level`
3. 写一段中文说明，说明为什么这样定级
4. 如果有可靠官方来源，把链接写进 `source_refs`
5. 在测试里加一个断言，确保新类别进入图谱后属性正确

## 6. 代码入口

长期知识种子由下面这个函数写入图谱：

```python
from wastekg import KnowledgeGraph, seed_default_categories

graph = KnowledgeGraph()
seed_default_categories(graph)
```

