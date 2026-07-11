# outputs

本目录用于本地运行产物，不提交大文件。

## 子目录约定

- `yolo_runs/`：YOLO/Ultralytics 训练、验证、预测输出，替代旧的 `runs/`。
- `evaluations/`：结构化评估输出。
- `figures/`：论文或报告用生成图。
- `debug/`：临时调试产物。
- `legacy_root_runs/`：从仓库根目录迁入的旧训练/预测产物，仅用于追溯，不作为新命令输出位置。

## 规则

- 除本 README 外，本目录内容默认被 Git 忽略。
- 旧的 `runs/` 不再作为推荐输出目录；如历史命令生成了 `runs/`，应迁移到 `outputs/yolo_runs/`。
- 涉及模型训练时，由用户在本机确认显存后手动运行。
