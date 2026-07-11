# 实验室域适配数据与 E4 动作前后验证处理协议

## 1. 目标

本协议把两类数据严格分开：

```text
实验室域适配训练候选：用于改善模型对本实验室背景、光照和相机成像的适应性
E4 before/after holdout：只用于动作前后重新感知验证，永久禁止进入训练
```

原始数据保持只读：

```text
E:\博论相关\test_my\My First Project.yolov11
```

初次审计输出：

```text
artifacts/paper/e0_lab_adaptation_raw
```

## 2. 2026-07-11 初次审计结论

- 图像共 19 张：train=18、val=1、test=0。
- 有效实例共 153 个：train=145、val=8。
- 包含 9 类：brick、concrete、foam、glass、hard_plastic、paperboard、soft_plastic、tile、wood。
- 缺少当前 11 类体系中的 gypsum_board 和 metal。
- 未发现缺失标签、非法坐标、退化 polygon、不可读图像或跨 split 完全重复图。
- `image_1-before` 位于 train，而同场景 `image_1-after1` 位于 val，构成场景级泄漏，不能作为独立验证划分。
- `image_1-before` 有一个完全相同的 polygon 同时标为 concrete 和 glass，必须回到标注平台修正。
- 数据同时混有高分辨率手机图和低分辨率 D435i 场景图，成像域不一致。

19 张图不足以单独训练新模型。它们只能作为基于现有 waste11 模型的域适配候选数据。

## 3. 类别 ID 必须重映射

Roboflow 导出 ID 与项目 11 类 ID 不一致，禁止直接复制标签或直接合并目录。

| Roboflow ID | 类别 | 项目 ID |
| ---: | --- | ---: |
| 0 | brick | 1 |
| 1 | concrete | 0 |
| 2 | foam | 5 |
| 3 | glass | 10 |
| 4 | hard_plastic | 8 |
| 5 | paperboard | 9 |
| 6 | soft_plastic | 7 |
| 7 | tile | 2 |
| 8 | wood | 3 |

项目完整顺序保持：

```text
0 concrete
1 brick
2 tile
3 wood
4 gypsum_board
5 foam
6 metal
7 soft_plastic
8 hard_plastic
9 paperboard
10 glass
```

重映射必须通过脚本按类别名称完成，并在输出后再次运行数据审计；不得手工批量替换单个数字。

## 4. 永久 E4 holdout

凡属于动作前后序列的图片及其相邻帧，都不得进入训练、微调或超参数选择：

```text
image_1-*
image_2-*
image_3-*
paper_experiments/e4_image_sequences/**
```

现有 `image_1-before` / `image_1-after1` 存在视角、尺度和物体像素位置变化，只能用于流程调试，暂不作为论文最终严格证据。

最终 E4 图片必须满足：

1. D435i 使用刚性支架固定，before/after 期间不触碰相机和桌面；
2. 锁定分辨率、曝光、白平衡和补光；
3. 使用中性托盘，不使用 paperboard、wood 或 foam 目标物作为支撑背景；
4. 每一步只移除一个对象，其他对象不得移动；
5. 同时保存 RGB、depth、相机内参、时间戳和移除对象真值；
6. before 和 after 都单独做人工 mask 真值；
7. 至少保留 5 组独立场景，每组 2 至 4 个连续移除步骤；
8. 整组序列只用于 E4 holdout，不参与训练。

## 5. 域适配数据如何补拍

训练候选应优先使用最终部署相机 D435i，而不是主要依赖手机照片。

建议补充到：

- 总图像数 100 至 200 张；
- 每类至少 30 至 60 个清晰实例；
- 每类至少覆盖 20 个独立摆放或场景，不把视频相邻帧当成独立场景；
- tile、hard_plastic、glass 等当前不足或易混类别优先补足；
- 增加 15% 至 25% 纯背景负样本，包含黑布、桌面、托盘和机械臂但不含目标；
- 同时覆盖单物体、轻度遮挡、混合摆放、边缘截断和不同距离。

背景应以真实实验环境为主，但要避免所有类别总出现在固定位置，否则模型会学习位置和背景捷径。

## 6. 推荐训练与验证边界

```text
原 waste11 train
  + 清洗并重映射后的实验室训练候选
  -> 域适配训练集

原 waste11 val/test
  -> 保持冻结，用于检查是否发生灾难性遗忘

独立实验室普通场景 holdout
  -> 评估实验室域识别效果

E4 before/after holdout
  -> 只评估对象持续、消失、新增和事件更新
```

所有划分按拍摄 session 或完整序列分组，不按单张图片随机划分。

## 7. 执行顺序

1. 在 Roboflow 修复 `image_1-before` 的 concrete/glass 重复冲突 mask。
2. 补齐新的实验室普通场景和纯背景图。
3. 重新导出无 augmentation 的原始标注版本。
4. 用类别名称重映射到项目 11 类 ID。
5. 将 E4 序列从训练候选中物理隔离。
6. 再次运行 E0 审计，检查标注、类别分布、重复图和场景泄漏。
7. 由用户在本机显式检查显存后执行训练；AI 代理不在沙盒中启动训练。
8. 同时报告原 waste11 test、实验室普通 holdout 和 E4 序列结果。

完成标注修复并重新导出后，规范化命令为：

```powershell
.\.venv\Scripts\python.exe scripts\data\prepare_lab_adaptation_dataset.py `
  --source "E:\博论相关\test_my\My First Project.yolov11" `
  --out datasets\lab_adaptation_v1 `
  --holdout-prefix "image_1-" `
  --holdout-prefix "image_2-" `
  --holdout-prefix "image_3-"
```

脚本检测到冲突 mask 时会拒绝导入；输出只包含 `train_pool`、`e4_holdout` 和审计 manifest，不直接生成可训练 `data.yaml`，避免误把 E4 图片用于训练。

## 8. E4 论文证据

E4 不应只展示两张预测图。建议最终证据包含：

```text
before RGB + 真值/预测 mask
after RGB + 真值/预测 mask
匹配实例、removed 实例和新增误检列表
Scene_before -> ExecutionEvent/HumanRemovalEvent -> Scene_after
ObjectInstance 状态变化和事件日志
```

在机械臂和 ROS2 尚未真实接入时，应表述为“受控人工移除后的图像再感知和状态更新验证”，不能写成机械臂自主抓取验证。

## 9. 当前模型基线

使用冻结的 `yolo11n_seg_waste11_grouped_e50_v1` 权重，以 `conf=0.05`、CPU 在 `seq001` 上运行：

```text
before detections = 4
after detections = 4
persisted = 0
removed candidates = 4
appeared candidates = 4
```

输出：

```text
artifacts/paper/e4_seq001_lab_baseline_conf005
```

前帧主要被预测为 tile/hard_plastic，后帧主要被预测为 soft_plastic/hard_plastic/paperboard。同一持续对象发生类别翻转，导致同类 IoU 匹配完全失败。该结果证明当前模型不能支撑 E4 正式结论，但可以作为域适配前 baseline。后续必须同时报告：逐帧检测与 mask 质量、持续对象类别一致性、removed 识别正确性以及状态事件更新结果。
