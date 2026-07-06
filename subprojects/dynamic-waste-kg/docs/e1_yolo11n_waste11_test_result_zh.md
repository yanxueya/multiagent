# E1：YOLO11n-seg 11 类建筑废弃物独立测试集结果

> **实验定位：** 受控环境下的二维实例分割基线。本文档只报告冻结的 `best.pt` 在独立 `test` 切分上的一次结构化评估，不将训练过程中的 validation 指标作为论文结果。

## 1. 冻结对象与可复现信息

| 项目 | 值 |
|---|---|
| 视觉类别 | `concrete`、`brick`、`tile`、`wood`、`gypsum_board`、`foam`、`metal`、`soft_plastic`、`hard_plastic`、`paperboard`、`glass` |
| 数据视图 | `datasets/waste11_grouped_v1` |
| 数据配置 SHA-256 | `1affb2168cfbd409818a7ef2b423817e89fe2776ae4b65d365ff1a801390a0dd` |
| 训练模型 | `yolo11n-seg.pt` 初始化后训练 50 epochs |
| 训练输入 | `640` px，batch `4`，device `0`，workers `2`，optimizer `auto`，close_mosaic `10` |
| 设备 | NVIDIA GeForce RTX 5060 Laptop GPU，约 8 GiB 显存 |
| 权重 | `runs/paper_e1/yolo11n_seg_waste11_grouped_e50_v1/weights/best.pt` |
| 权重 SHA-256 | `bdb643ec1b1b72a29f1f1e998c4ab8c4940c23116e8f36de366b2fdfcc1d167f` |
| 软件 | Python 3.14.4，PyTorch `2.12.0.dev20260408+cu128`，Ultralytics `8.4.66` |

完整的环境、数据和权重溯源见 [model_environment.json](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e0_waste11_grouped_v1_r3/model_environment.json)。

## 2. 数据加载口径

原始标签中 train/val/test 分别有 `92,417`、`20,744`、`19,484` 条有效 polygon 行。Ultralytics 8.4.66 对分割标签先转换为 `class + xywh`，然后按该五元组去重；它实际使用的实例数为 `92,399`、`20,733`、`19,475`。

- 审计发现 `4` 条完全相同的 polygon 行；
- 以 Ultralytics 加载规则计，`38` 条标签会在缓存构建时移除；该数包含完全相同行，二者不可相加；
- 训练与 test 的报告均采用 `ultralytics_effective_instances`，保证训练、评估和论文表格口径一致；
- 跨 split 的 SHA-256 完全重复图像组与相同 8x8 感知哈希候选组均为 `0`。

审计细节见 [annotation_validation_report.md](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e0_waste11_grouped_v1_r3/annotation_validation_report.md) 和 [split_leakage_report.md](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e0_waste11_grouped_v1_r3/split_leakage_report.md)。

## 3. 独立 Test 结果

测试集包含 `890` 张图像和 `19,475` 个 Ultralytics 实际有效实例。

| 指标 | Box | Mask |
|---|---:|---:|
| Precision | 0.9426 | 0.9428 |
| Recall | 0.8964 | 0.8908 |
| mAP50 | 0.9434 | 0.9363 |
| mAP50-95 | 0.8437 | 0.7397 |

逐类 Mask mAP50-95：

| 类别 | 测试实例数 | Mask mAP50 | Mask mAP50-95 |
|---|---:|---:|---:|
| concrete | 6,893 | 0.9633 | 0.7340 |
| brick | 257 | 0.9939 | 0.8392 |
| tile | 235 | 0.9872 | 0.8305 |
| wood | 2,205 | 0.9345 | 0.7502 |
| gypsum_board | 218 | 0.9113 | 0.8054 |
| foam | 142 | 0.9319 | 0.8482 |
| metal | 3,666 | 0.8897 | 0.5239 |
| soft_plastic | 872 | 0.8536 | 0.6380 |
| hard_plastic | 3,594 | 0.9409 | 0.6954 |
| paperboard | 980 | 0.9020 | 0.7454 |
| glass | 413 | 0.9909 | 0.7264 |

原始机器可读结果：

- [overall_metrics.json](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_test_evaluation_r2/overall_metrics.json)
- [per_class_metrics.csv](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_test_evaluation_r2/per_class_metrics.csv)
- [evaluation_manifest.json](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_test_evaluation_r2/evaluation_manifest.json)

本机推理速度记录为：预处理 `0.60 ms/image`、模型推理 `2.79 ms/image`、后处理 `1.19 ms/image`。这些数值仅对应本机、当前图像尺寸、batch、软件版本和 GPU，不应被概括为云端 VLM 或端到端系统实时性。

## 4. 错误模式与解释边界

1. **金属是当前最弱的 mask 类别。** `metal` 的 Mask mAP50-95 为 `0.5239`，显著低于其 Mask mAP50 `0.8897`。这表明模型可在较宽松 IoU 下发现许多金属目标，但在严格边界下难以稳定贴合复杂金属堆、容器和网格结构。
2. **软塑料仍存在材质混淆。** `soft_plastic` 的 Mask mAP50-95 为 `0.6380`；定性样例中一个软塑料目标被预测为 `metal`。这说明后续 VLM 复核应优先从该类低置信度或策略敏感实例开始，而非假设所有塑料类可自动处理。
3. **玻璃的类别发现较好，但边界精度仍有限。** `glass` 的 Mask mAP50 为 `0.9909`，而 mAP50-95 为 `0.7264`。小碎片在 IoU=0.5 下可被识别，但轮廓和面积的高 IoU 匹配更困难；这不等同于玻璃可安全抓取。
4. **单目标泡沫样例表现良好，不可外推为杂乱场景抓取能力。** `foam` 的 Mask mAP50-95 为 `0.8482`，但测试样例数量为 `142`，且本文不评估三维姿态、厚度、遮挡背面或夹爪接触稳定性。

这些观察是类别级 test 指标和确定性样例的解释，不是材料物理性质、抓取安全性或施工现场泛化的结论。

## 5. 定性案例

样例选择规则为：对 `metal`、`soft_plastic`、`glass`、`foam`，各自从 test 集选择总标注实例数最少的可用图像；该规则用于降低图像拥挤度，不代表随机抽样或性能统计。

| 类别 | 观察 | 真值 / 预测图 |
|---|---|---|
| metal | 复杂金属容器及内部构件产生大范围、碎片化预测，适合作为严格 mask 边界失稳的解释案例。 | [GT](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/metal__cdw2026_2022_0158__ground_truth.jpg) / [Pred](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/metal__cdw2026_2022_0158__prediction.jpg) |
| soft_plastic | 此样例中软塑料真值被预测为金属，说明视觉材质相近时需要保守复核。 | [GT](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/soft_plastic__cdw2026_2022_0163__ground_truth.jpg) / [Pred](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/soft_plastic__cdw2026_2022_0163__prediction.jpg) |
| glass | 七块玻璃碎片均被检出，但轮廓误差需结合 mAP50-95 解读。 | [GT](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/glass__glassdebris_v5_test_video3_mp4-0009_jpg.rf.eff64b7ee6dc8287a878e5118ffbec97__ground_truth.jpg) / [Pred](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/glass__glassdebris_v5_test_video3_mp4-0009_jpg.rf.eff64b7ee6dc8287a878e5118ffbec97__prediction.jpg) |
| foam | 单个泡沫目标的预测 mask 与真值形状接近，构成受控成功案例。 | [GT](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/foam__codd_2916__ground_truth.jpg) / [Pred](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/foam__codd_2916__prediction.jpg) |

定性样例的完整来源、选择规则和图像显示阈值见 [qualitative_manifest.json](/C:/Users/12279/Documents/multiagent/subprojects/dynamic-waste-kg/artifacts/e1_qualitative_samples_r1/qualitative_manifest.json)。预测图显示阈值为 `0.25`，它不参与 AP 计算。

## 6. 评估运行记录

首次 test 推理已在 `artifacts/e1_test_evaluation` 保存原始 Ultralytics 图表，但结构化导出脚本把 `nt_per_class` 误读为 `metrics.box` 属性而在写入 JSON/CSV 前退出。修复后，使用**相同数据哈希、相同 `best.pt` 哈希、相同 test 切分和相同评估参数**再次推理，并将完整、可引用结果写入 `artifacts/e1_test_evaluation_r2`。本次重复不用于选择模型、阈值、类别或策略；保留第一次原始输出是为了完整溯源。

## 7. E1 结论

E1 已完成 11 类二维实例分割的独立 test 评估、逐类 Box/Mask 指标、混淆矩阵/PR 曲线导出和四个定性对照案例。可用于论文的边界表述为：在本冻结数据视图和受控评价设置下，YOLO11n-seg 能将 11 类建筑废弃物图像转化为具有类别、置信度和二维 mask 的感知记录；该证据不验证 RGB-D 几何、物理抓取、ROS2 执行或现场部署。
