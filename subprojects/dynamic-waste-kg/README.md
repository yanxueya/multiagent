# Dynamic Waste Knowledge Graph

本子项目是动态建筑废弃物系统的知识图谱状态层。它负责数据处理、感知结果接入、知识状态维护、VLM/LLM 复核、RGB-D 辅助、图谱导出和面向多智能体/ROS2 的结构化接口。

当前稳定设计：

```text
11 个明确视觉类别 + 系统逻辑生成 unknown
```

YOLO 负责检测和实例分割明确类别；VLM/LLM 只做结构化视觉属性复核和一致性判断；知识图谱负责长期类别先验、短期实例状态、`unknown` 复核入口、事件日志和规划接口。

知识图谱的只读规划接口临时输出候选快照，包括 `recognition_status`、`current_handling_policy`、`task_status`、`attempt_count`、深度、遮挡、NEAR 数量和类别先验。完整候选不复制进 LangGraph State；State 只保存 Scene、待复核/可执行 ID 和 KG 引用。第一阶段规划器只做硬过滤与无权重字典序。

## 快速入口

1. [文档导航](docs/README.md)
2. [长期知识层种子说明](docs/knowledge_seed_zh.md)
3. [数据集处理与感知流水线](docs/dataset_and_perception_pipeline_zh.md)
4. [YOLO + 大模型接入指南](docs/yolo_llm_integration_zh.md)
5. [RealSense RGB-D 接入教程](docs/realsense_rgbd_pipeline_zh.md)
6. [Neo4j 存储与可视化建议](docs/neo4j_storage_zh.md)

## 当前结构

```text
dynamic-waste-kg/
  wastekg/
    core/          # 类别体系、数据模型、长期知识种子
    data/          # 数据集审计、合并、冻结、分组
    yolo/          # YOLO runtime、图像预测、分割评估
    llm/           # OpenAI-compatible/DeepSeek 复核器
    perception/    # 感知流水线与 VisionPacket 适配
    rgbd/          # RealSense、RGB-D IO、几何补全
    graph/         # 内存图谱、查询、JSON/Mermaid/Neo4j 导出
    interfaces/    # LangGraph/ROS2 对接契约
    paper/         # 小论文实验可复用逻辑
  scripts/
    data/          # 数据处理命令行入口
    yolo/          # YOLO 训练、评估、样本筛选入口
    llm/           # LLM 配置检查入口
    rgbd/          # RGB-D 采集和接入入口
    graph/         # 图谱预测、Neo4j 导入导出入口
    paper/         # 论文实验样本导出入口
    tools/         # 可复用小工具
  docs/            # 当前主线关键文档
  datasets/docs/   # 数据来源、合并、清洗、审计和中间数据处理说明
  paper_experiments/
  tests/
```

旧的根目录扁平兼容包装已移除。新代码必须导入领域子包，例如 `wastekg.core.models`、`wastekg.data.audit`、`wastekg.llm.reviewer`。

## 职责边界

`dynamic-waste-kg` 负责：

- 长期类别知识。
- 短期对象记忆。
- `unknown` 对象记忆入口。
- 事件日志。
- YOLO/RealSense/VLM 到图谱的输入适配。
- Neo4j 导出和可视化。
- 给 LangGraph 输出只读候选快照和 `graph_state`，供确定性资格校验与单步行动规划使用。

`dynamic-waste-kg` 不负责：

- LangGraph 多智能体编排。
- ROS2 机械臂控制节点。
- MoveIt 运动规划实现。
- 最终 UI。
- 完整机器人安全系统。

当前 `dynamic-waste-agent` 已提供 `WasteKgRuntimeAdapter`，可将 Agent 的只读候选查询和四类受控写入接到本子项目的内存 `KnowledgeGraph`。Neo4j 在线事务适配器仍未实现；现有 Neo4j 能力是导出/导入与可视化边界。


## 导出到 UI

`dynamic-waste-ui` 当前通过 JSON snapshot 接入知识图谱状态。刷新 UI 数据时运行：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\graph\export_ui_snapshot.py --output ..\dynamic-waste-ui\public\data\kg-snapshot.json
```

若已有真实 `KnowledgeGraph.to_dict()` 快照，可使用：

```powershell
.\.venv\Scripts\python.exe scripts\graph\export_ui_snapshot.py --input artifacts\graph_snapshot.json --output ..\dynamic-waste-ui\public\data\kg-snapshot.json
```

该导出会压缩为 UI 需要的关键字段，并确保 `unknown` 只作为短期实例状态，不作为长期类别知识。

## 运行测试

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 训练入口

涉及训练时，AI 代理只给出命令和参数建议，不在沙盒里直接启动训练。用户应先确认显存，再在本机运行：

```powershell
.\.venv\Scripts\python.exe scripts\yolo\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11n-seg.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_next
```

## 产物边界

- `datasets/`：本地数据集，不进入 Git；`datasets/docs/` 例外，允许提交数据说明文档。
- `outputs/yolo_runs/`：YOLO/Ultralytics 训练、验证或预测产物，不进入 Git。
- `artifacts/`：临时导出、图像样本和分析产物，不进入 Git。
- `paper_experiments/`：小论文实验协议、脚本、结果索引和补充文档。
