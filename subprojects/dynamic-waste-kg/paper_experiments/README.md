# 小论文补充实验目录

本目录用于组织投稿前的补充实验，不替代 `wastekg/` 核心代码，也不移动已有训练数据、模型权重或知识图谱实现。

## 目录职责

- `protocols/`：每个实验阶段的目的、输入、输出、验收标准。
- `scripts/`：论文实验专用运行脚本，只调用 `wastekg/` 中的可复用能力。
- `results/`：面向论文写作的结果索引和结论摘要。
- `docs/`：小论文补充实验说明、论文草稿、实验指令和历史稿。
- `../artifacts/paper/`：脚本生成的 CSV、JSON、Markdown 结果文件。

实验室增量数据与 E4 holdout 的处理依据见：

- [`protocols/lab_domain_adaptation_and_e4_holdout.md`](protocols/lab_domain_adaptation_and_e4_holdout.md)

## 实验状态

| 阶段 | 内容 | 当前状态 |
|---|---|---|
| E0 | 数据集审计与冻结 | 已完成，结果见 `artifacts/e0_waste11_grouped_v1_r3` |
| E1 | YOLO11n-seg 独立 test 集评估 | 已完成，结果见 `artifacts/e1_test_evaluation_r2` |
| E2 | 受约束 VLM 图像复核 | 代码路径具备，模型选择阻塞 |
| E3 | 分层知识状态与保守路由 | 可由 `scripts/run_e3_policy_routing.py` 生成 |
| E4 | 受控事件回放与可追溯状态更新 | 可由 `scripts/run_e4_event_replay.py` 生成 |

## 推荐运行顺序

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e3_policy_routing.py
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e4_event_replay.py
```

## E2 重要说明

E2 必须使用真正支持图像输入的视觉语言模型。文本模型即使很强，也不能看见 `crop.jpg` 和 `mask_overlay.jpg`，因此不能作为 VLM 复核实验结果。
