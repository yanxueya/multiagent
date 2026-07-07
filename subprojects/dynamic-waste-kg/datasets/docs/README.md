# 数据文档目录

本目录用于保存可进入 git 的数据说明文档，不保存真实数据集、图片、标注大文件或训练产物。

适合放在这里的内容：

- 数据来源说明；
- 数据清洗和合并记录；
- 类别映射说明；
- 数据审计结论；
- 中间数据处理过程说明；
- 数据集版本和冻结口径说明。

不适合放在这里的内容：

- 原始图片；
- YOLO 标签大批量文件；
- 模型权重；
- 训练输出；
- 论文补充实验说明；
- 知识图谱主线架构说明。

目录边界：

```text
data_docs/          # 可追踪的数据说明文档
datasets/           # 本地真实数据集，不进入 git
docs/               # 当前主线关键文档
paper_experiments/  # 小论文补充实验协议、脚本、结果和实验文档
```

当前已归入本目录的文档包括：

```text
data_docs/glass_debris_dataset_merge_zh.md
data_docs/cdw2026_dataset_merge_and_asbestos_strategy_zh.md
data_docs/training_records/yolo_training_result_analysis_zh.md
data_docs/training_records/yolo_e50_training_check_zh.md
data_docs/training_records/yolo_model_comparison_test_results_zh.md
```

后续继续迁移数据文档时，必须同步更新 `docs/README.md`、根 `README.md` 和所有相对链接。
