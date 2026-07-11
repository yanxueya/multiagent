# 眼在手上场景的最小数据采集与标注方案

## 1. 夹爪是否可以出现在图片中

最终系统计划采用 eye-in-hand，因此正式域适配数据应尽早使用接近最终安装位置的 D435i 和夹爪构型。

夹爪可以出现在图像中，并且不应增加 `gripper` 类：

- 夹爪、机械臂、黑布、桌面和托盘都是未标注背景；
- 不要为了训练统一裁掉夹爪，否则部署时会产生新的域偏移；
- 不要给夹爪画废弃物 mask；
- 夹爪不应遮挡目标主体超过约 20%；
- 建议让夹爪占画面面积低于约 15% 至 20%；
- 同时采集夹爪张开、半开和不同安全姿态，避免模型只记住一种轮廓。

如果当前相机支架与最终结构差异较大，这一轮只能算 pilot。最终支架、相机朝向和夹爪外观确定后，仍需补一小轮正式图片。

建议数据比例：

```text
约 70%：最终 eye-in-hand 视角，夹爪正常可见
约 15%：夹爪仅部分可见或位于不同安全姿态
约 15%：无目标背景图，覆盖夹爪可见和不可见情况
```

## 2. 最小可行采集量

以下是基于已有大数据模型做实验室域适配的最低 pilot 方案，不是从零训练方案：

| 用途 | session × 每组帧数 | 图像数 | 是否标注目标 |
| --- | ---: | ---: | --- |
| 域适配 train pool | 6 × 5 | 30 | 是 |
| 纯背景负样本 | 2 × 4 | 8 | 空标签 |
| 普通实验室 holdout | 2 × 5 | 10 | 是，禁止训练 |
| E4 before/after | 5 × 3 | 15 | 是，禁止训练 |
| 合计 |  | 63 |  |

每张 train pool 放 3 至 6 个对象，通过混合摆放使每个重点类别至少出现 15 至 20 次。优先补充当前不足或不稳定的 tile、hard_plastic、glass，以及 E4 正式场景实际使用的类别。

如果这 63 张仍不能稳定识别，应继续增加真实 D435i 场景，而不是继续放大增强强度。

## 3. 单个 session 怎么拍

同一 session 中固定相机支架、分辨率、光源位置、背景/托盘和一个安全机械臂姿态范围。

每保存一帧后，只改变一到两项：

- 旋转一个物体约 15 至 45 度；
- 改变一个物体的位置；
- 调整轻度遮挡；
- 改变夹爪开合或安全视角；
- 对光照做小幅变化。

不要从静止视频中连续抽取几十帧。相邻帧不等于独立样本，必须按整个 session 分组划分 train/val/test。

## 4. 自动采集命令

建议在 Ubuntu 22.04、D435i 已连接并安装 `pyrealsense2` 的环境运行。

手动触发模式最适合标注数据。每调整一次物体后按 Enter：

```bash
python scripts/rgbd/capture_realsense_dataset.py \
  --session-id lab_mix_001 \
  --out datasets/raw_lab_captures \
  --count 5 \
  --mode manual \
  --camera-mount eye_in_hand \
  --gripper-visibility visible \
  --scene-note "brick tile glass mixed scene"
```

定时间隔模式：

```bash
python scripts/rgbd/capture_realsense_dataset.py \
  --session-id lab_mix_002 \
  --out datasets/raw_lab_captures \
  --count 5 \
  --mode interval \
  --interval 5 \
  --start-delay 5
```

每个 session 输出：

```text
images/*.png
depth/*.png
metadata/*.json
camera_intrinsics.json
capture_meta.json
session_manifest.json
```

上传 Roboflow 时只上传 `images/`；depth、内参和 manifest 留在本地，供 E4、RGB-D 和复现实验使用。

## 5. 背景怎么标注

YOLO segmentation 不需要 `background` 类。所有没有被目标 mask 覆盖的像素都会自动作为背景参与训练。

标注规则：

- 只标 11 类目标废弃物；
- 夹爪、机械臂、黑布、桌面、托盘、阴影和反光不标；
- 纯背景图片保留空标注，不创建 background polygon；
- 如果 paperboard、wood 或 foam 只是支撑台，不要用它们充当背景，改用中性塑料托盘；
- 如果某块 paperboard 本身就是待分拣目标，则必须完整标注，不能一会儿当背景、一会儿当目标。

禁止新增 `background` 类，否则模型会尝试分割一个外观无限变化的大类，反而破坏 11 类边界。

## 6. 最小增强方案

增强只在训练阶段在线执行，val、test 和 E4 holdout 禁止增强。

推荐轻量范围：

```text
rotation: -8° 到 +8°
translation: 不超过 8%
scale: 0.85 到 1.15
brightness/contrast: 小幅变化
blur/noise: 低概率、低强度
horizontal flip: 关闭或极低概率
vertical flip: 关闭
90°/180° rotation: 关闭
mosaic/mixup/copy-paste: 当前最小实验先关闭
```

原因：eye-in-hand 的夹爪位置、重力方向和相机姿态具有物理意义。强翻转、大旋转和重度拼接会制造部署中不存在的画面。

数据增强不能解决新背景缺失、夹爪遮挡缺失、类别标错、mask 冲突、before/after 视角移动或同一物体前后类别翻转。

## 7. E4 特殊要求

E4 序列必须与训练池物理隔离。固定相机、曝光和背景后：

```text
frame_000: before
frame_001: 只移除对象 A
frame_002: 再只移除对象 B
```

三帧都要保存 RGB、depth 和人工 mask 真值。E4 评估应同时检查持续对象、消失对象、类别一致性和事件更新，不能只比较检测数量。
