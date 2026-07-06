# 文档导航

本文档用于解决 `docs/` 目录文件较多、不易定位的问题。当前不大规模移动旧文件，避免破坏已有链接；先用导航方式建立清晰入口。

---

## 1. 核心架构与方法

优先阅读：

- [长期知识层种子说明](knowledge_seed_zh.md)
- [论文方法与系统设计沉淀文档](paper_method_system_design_zh.md)
- [YOLO + 大模型接入指南](yolo_llm_integration_zh.md)
- [通用大模型复核器配置说明](llm_reviewer_config_zh.md)
- [RealSense RGB-D 接入知识图谱教程](realsense_rgbd_pipeline_zh.md)
- [Neo4j 存储与可视化建议](neo4j_storage_zh.md)

当前核心逻辑：

```text
11 个明确视觉类别
  + YOLO 实例分割
  + VLM 属性一致性校验
  + unknown 人工复核入口
  + 长期知识层 / 短期记忆层 / 事件日志层
```

---

## 2. 新手教程

适合从零开始操作：

- [新手指南](beginner_guide.md)
- [从零开始运行完整流程](full_beginner_pipeline_zh.md)
- [Neo4j 新手可视化教程](neo4j_beginner_visualization_zh.md)
- [DeepSeek/通用大模型和虚拟环境说明](deepseek_reviewer_and_venv_zh.md)
- [本机开发环境画像](local_environment_profile_zh.md)

---

## 3. 数据集与 YOLO 训练

用于理解训练数据、合并过程和模型结果：

- [数据集处理与感知流水线](dataset_and_perception_pipeline_zh.md)
- [Glass Debris 数据合并记录](glass_debris_dataset_merge_zh.md)
- [2026.6.15 建筑垃圾数据合并与高风险材料策略](cdw2026_dataset_merge_and_asbestos_strategy_zh.md)
- [YOLO 训练结果解读与优化方案](yolo_training_result_analysis_zh.md)
- [YOLO11n-seg 50 Epoch 训练检查报告](yolo_e50_training_check_zh.md)
- [E1 YOLO11n waste11 测试结果](e1_yolo11n_waste11_test_result_zh.md)
- [YOLO11n/YOLO11s/YOLOv9c 实例分割模型对比测试结果](yolo_model_comparison_test_results_zh.md)

注意：部分旧文档标题中仍可能出现 `asbestos` 或 `waste12`，它们代表历史实验记录。当前稳定设计以 11 个明确视觉类别和系统逻辑 `unknown` 为准。

---

## 4. 小论文实验与结果

用于论文实验组织和结果沉淀：

- [小论文实验执行指令](小论文实验执行指令.md)
- [小论文实验完善指令完整修订版](小论文实验完善指令_完整修订版.md)
- [E0-E4 实验结果与反馈解释](e0_e4_experiment_results_and_feedback_explanation_zh.md)
- [YOLO 实例分割模型对比测试结果说明](yolo_model_comparison_test_results_zh.md)
- [E4 严格移除审核总结](e4_strict_removal_audit_summary_zh.md)
- [小论文进一步完善稿 v5：当前推荐主稿](小论文进一步完善稿_任务状态构建_YOLO_VLM_DKG_unknown_2026-07-01.md)
- [小论文完善稿 v4：历史稿](小论文完善稿_策略感知任务状态构建_DKG_VLM_2026-06-25.md)

更结构化的实验协议、脚本和结果索引在：

```text
paper_experiments/
  protocols/
  scripts/
  results/
  e4_image_sequences/
```

---

## 5. 论文草稿

用于后续投稿写作：

- [期刊论文格式中文草稿](journal_manuscript_draft_zh.md)
- [小论文进一步完善稿 v5：当前推荐主稿](小论文进一步完善稿_任务状态构建_YOLO_VLM_DKG_unknown_2026-07-01.md)
- [论文方法与系统设计沉淀文档](paper_method_system_design_zh.md)

---

## 6. 历史与工作区文件

以下目录保留历史计划和工作稿，不建议作为当前方法依据：

```text
docs/superpowers/
docs/working/
```

如果文档之间出现冲突，优先级建议为：

```text
knowledge_seed_zh.md
  > paper_method_system_design_zh.md
  > paper_experiments/protocols/
  > 其他历史记录
```
