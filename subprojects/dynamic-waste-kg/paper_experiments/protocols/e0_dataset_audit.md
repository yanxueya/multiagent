# E0 数据集审计与冻结

## 目的

证明本文使用的数据集划分、类别范围和标注格式是可复查的，避免把未验证数据直接用于投稿结论。

## 冻结范围

- 视觉类别：11 类，即 `concrete, brick, tile, wood, gypsum_board, foam, metal, soft_plastic, hard_plastic, paperboard, glass`。
- `asbestos_suspect` 只保留在长期知识层和人工风险标签中，不作为 YOLO/VLM 视觉输出类别。
- 冻结数据目录：`datasets/waste11_grouped_v1`
- 审计结果目录：`artifacts/e0_waste11_grouped_v1_r3`

## 论文写法

可以写作“11 类建筑废弃物二维实例分割数据集”；不能写作“12 类视觉识别数据集”，因为 `asbestos_suspect` 当前没有视觉标注实例。
