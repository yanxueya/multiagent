# multiagent 工作区说明

这个目录是你的多智能体与知识图谱研究工作区。当前核心子项目是：

```text
subprojects/dynamic-waste-kg
```

---

## 推荐阅读顺序

如果你要继续做“复杂动态建筑环境中的危险废弃物认知与人机协同自治决策”，建议按下面顺序看：

1. [知识图谱项目总入口](subprojects/dynamic-waste-kg/README.md)
2. [长期知识层种子说明](subprojects/dynamic-waste-kg/docs/knowledge_seed_zh.md)
3. [数据集处理与感知流水线](subprojects/dynamic-waste-kg/docs/dataset_and_perception_pipeline_zh.md)
4. [YOLO + 大模型接入指南](subprojects/dynamic-waste-kg/docs/yolo_llm_integration_zh.md)
5. [2026.6.15 建筑垃圾数据合并与疑似石棉策略](subprojects/dynamic-waste-kg/docs/cdw2026_dataset_merge_and_asbestos_strategy_zh.md)
6. [Neo4j 存储与可视化建议](subprojects/dynamic-waste-kg/docs/neo4j_storage_zh.md)

---

## 目录分工

```text
multiagent/
  README.md                         # 当前工作区说明
  .gitignore                        # 忽略训练数据、模型权重、运行产物
  subprojects/
    dynamic-waste-kg/               # 当前核心研究子项目
      wastekg/                      # 知识图谱 Python 源码
      tests/                        # 学习与验证用测试
      scripts/                      # 数据合并、训练、Neo4j 导入等脚本
      docs/                         # 中文教程与设计说明
      datasets/                     # 本地训练数据，体积大，不进入 git
      runs/                         # YOLO 训练/验证输出，不进入 git
      artifacts/                    # 临时导出、留档和整理后的产物
```

---

## 重要规则

- 源码优先放在 `subprojects/dynamic-waste-kg/wastekg/`。
- 教程和研究说明放在 `subprojects/dynamic-waste-kg/docs/`。
- 数据集放在 `subprojects/dynamic-waste-kg/datasets/`。
- 训练结果放在 `subprojects/dynamic-waste-kg/runs/`。
- 不建议在 `multiagent/` 根目录直接运行 YOLO 训练，否则容易生成顶层 `runs/`。
- 不建议在根目录新建零散 `docs/`，项目文档统一放到子项目 `docs/`。

---

## 常用命令

进入项目：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

继续训练 YOLO-seg：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model runs\segment\runs\waste12_seg\yolo11n_seg_e50\weights\best.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_next
```

