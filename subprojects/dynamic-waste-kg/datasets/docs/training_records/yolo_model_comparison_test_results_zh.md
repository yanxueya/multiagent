# YOLO 实例分割模型对比测试结果说明

> 用途：记录当前 11 类建筑废弃物实例分割模型在正式 test split 上的对比结果，并解释为什么当前小论文推荐使用 YOLO11s-seg 作为主模型。

---

## 1. 为什么会看起来“有问题”

这里的问题不是训练失败，而是评价目标不同导致的判断差异。

如果只看二维边界框，YOLOv9c-seg 的 Box mAP50-95 最高；如果看后续知识图谱和机械臂抓取更需要的实例掩膜，YOLO11s-seg 的 Mask mAP50-95 最高。与此同时，YOLOv9c-seg 的推理耗时明显更高，计算复杂度也更大。因此，不能简单说“最大的模型就是最适合的模型”。

当前论文目标不是单纯刷榜，而是构建一个能接入 VLM 复核、分层知识图谱和后续机器人任务规划的受控原型。对这个目标而言，主模型应同时考虑：

- 掩膜质量：影响对象轮廓、局部区域裁剪和后续深度点云提取；
- 推理成本：影响实时性和 8 GB 显存笔记本上的可运行性；
- 类别稳定性：影响是否需要 VLM 或人工复核；
- 工程可复现性：影响后续 RealSense、ROS2 和 LangGraph 接入。

因此，当前结论是：YOLO11s-seg 作为主模型，YOLO11n-seg 作为轻量基线，YOLOv9c-seg 作为高容量对比模型。

---

## 2. 测试数据与环境

测试数据：

```text
datasets/waste11_grouped_v1/data.yaml
split: test
test images: 890
effective instances: 19,475
classes: 11
```

11 个明确视觉类别：

```text
concrete, brick, tile, wood, gypsum_board, foam,
metal, soft_plastic, hard_plastic, paperboard, glass
```

`unknown` 不作为训练类别。它是系统在低置信度、证据冲突或人工复核前生成的任务状态，不是一个稳定视觉类别。

运行环境：

```text
Windows 11 x64
NVIDIA GeForce RTX 5060 Laptop GPU
显存约 8 GB
PyTorch 2.12.0.dev20260408+cu128
Ultralytics 8.4.66
```

---

## 3. 整体测试结果

| 模型 | 训练轮数 | Box mAP50-95 | Mask mAP50 | Mask mAP50-95 | Mask P | Mask R | 推理耗时/ms | 定位 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| YOLO11n-seg | 50 | 0.8437 | 0.9363 | 0.7397 | 0.9428 | 0.8908 | 5.2 | 轻量基线 |
| YOLO11n-seg | 100 | 0.8528 | 0.9411 | 0.7493 | 0.9524 | 0.8946 | 5.2 | 轻量模型延长训练 |
| YOLO11s-seg | 50 | 0.8736 | 0.9476 | 0.7651 | 0.9483 | 0.9053 | 5.4 | 当前推荐主模型 |
| YOLOv9c-seg | 50 | 0.8837 | 0.9469 | 0.7645 | 0.9485 | 0.9077 | 14.1 | 高容量对比模型 |

解释：

- YOLO11n 100 轮比 YOLO11n 50 轮更好，说明增加训练轮数有帮助。
- YOLO11s 50 轮明显优于 YOLO11n 100 轮，说明适当提高模型容量比单纯延长轻量模型训练更有效。
- YOLOv9c 的 Box mAP50-95 最高，但 Mask mAP50-95 没有超过 YOLO11s。
- YOLOv9c 推理耗时约 14.1 ms，YOLO11s 约 5.4 ms；在当前 RTX 5060 Laptop GPU 和后续实时原型需求下，YOLO11s 更平衡。

---

## 4. YOLO11s-seg 类别级结果

| 类别 | instances | Box P | Box R | Box mAP50-95 | Mask P | Mask R | Mask mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| concrete | 6,893 | 0.9603 | 0.9435 | 0.8850 | 0.9587 | 0.9388 | 0.7598 |
| brick | 257 | 0.9807 | 0.9877 | 0.9776 | 0.9807 | 0.9871 | 0.8530 |
| tile | 235 | 0.9469 | 0.9447 | 0.9639 | 0.9481 | 0.9447 | 0.8363 |
| wood | 2,205 | 0.9610 | 0.8853 | 0.8753 | 0.9600 | 0.8825 | 0.7742 |
| gypsum_board | 218 | 0.9429 | 0.8991 | 0.9075 | 0.9463 | 0.8991 | 0.8417 |
| foam | 142 | 0.9343 | 0.9012 | 0.9124 | 0.9341 | 0.8991 | 0.8783 |
| metal | 3,666 | 0.9339 | 0.8713 | 0.7878 | 0.9234 | 0.8546 | 0.5669 |
| soft_plastic | 872 | 0.9261 | 0.7903 | 0.7509 | 0.9268 | 0.7840 | 0.6744 |
| hard_plastic | 3,594 | 0.9518 | 0.9122 | 0.8702 | 0.9506 | 0.9085 | 0.7235 |
| paperboard | 980 | 0.9066 | 0.8811 | 0.8488 | 0.9124 | 0.8827 | 0.7730 |
| glass | 413 | 1.0000 | 0.9913 | 0.8299 | 0.9902 | 0.9772 | 0.7353 |

类别级判断：

- `brick`、`tile`、`gypsum_board`、`foam` 的掩膜结果较好，可作为自动候选或监督候选的核心测试对象。
- `concrete` 数量多且总体稳定，但形态碎片化，抓取时仍需要深度点云和候选抓取区域验证。
- `wood` 结果可用，但长条形和遮挡会影响抓取姿态。
- `metal`、`soft_plastic`、`hard_plastic` 的 Mask mAP50-95 相对较低，应更多触发 VLM 属性校验、监督处理或人工复核。
- `glass` 的视觉识别精度较高，但由于易碎和割伤风险，不应仅根据高置信度进入无监督自动处理。

---

## 5. 对知识图谱和任务规划的意义

模型输出不能直接等同于任务决策。当前流程应按以下逻辑使用模型结果：

```text
YOLO 输出类别、置信度、bbox、mask
  -> 低置信度或弱类别触发 VLM 属性一致性校验
  -> 长期知识层提供风险、易碎性、抓取难度和处理模式
  -> 短期实例层保存当前图像中的对象状态
  -> 事件日志层记录识别、复核、路由和状态更新
  -> 任务路由输出 AUTO / SUPERVISED / HUMAN_REVIEW
```

对后续机械臂抓取而言，当前二维结果只能说明“这个对象在图像上分割得是否可靠”。真正抓取还需要：

- RealSense D435i 深度图对齐；
- mask 区域内点云提取；
- 相机到机械臂坐标系标定；
- 候选抓取点生成；
- 抓取前碰撞与安全检查；
- 执行后重新感知和图谱事件回写。

因此，论文中应避免写“当前模型已经可以完成机械臂抓取”。更准确的表述是：当前模型能够为分层动态知识图谱提供可用的二维对象级视觉输入，并为后续 RGB-D 定位和任务规划提供基础。

---

## 6. 结果文件位置

```text
artifacts/model_comparison_test/yolo11n_e50
artifacts/model_comparison_test/yolo11n_e100
artifacts/model_comparison_test/yolo11s_e50
artifacts/model_comparison_test/yolov9c_e50
```

主模型证据：

```text
artifacts/model_comparison_test/yolo11s_e50/overall_metrics.json
artifacts/model_comparison_test/yolo11s_e50/per_class_metrics.csv
artifacts/model_comparison_test/yolo11s_e50/evaluation_manifest.json
artifacts/model_comparison_test/yolo11s_e50/ultralytics/metrics
```

高容量对比模型证据：

```text
artifacts/model_comparison_test/yolov9c_e50/overall_metrics.json
artifacts/model_comparison_test/yolov9c_e50/per_class_metrics.csv
artifacts/model_comparison_test/yolov9c_e50/evaluation_manifest.json
```

---

## 7. 论文写作建议

建议写法：

```text
The YOLO-family comparison indicates that YOLO11s-seg provides the best mask-level performance under the current test split, while YOLOv9c-seg achieves a slightly higher box-level mAP at a substantially higher inference cost. Therefore, YOLO11s-seg was selected as the perception backbone for task-state construction.
```

不建议写法：

```text
YOLOv9c is the best model.
```

原因是这句话忽略了掩膜指标、推理成本和机器人任务状态构建的实际需求。

