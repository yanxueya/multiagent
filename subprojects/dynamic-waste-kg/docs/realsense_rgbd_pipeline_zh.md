# RealSense RGB-D 接入知识图谱教程

本文档说明如何把 Intel RealSense D435i 接入当前知识图谱子项目。当前阶段目标不是直接抓取，而是先完成：

```text
RealSense 拍一帧 RGB-D
  -> YOLO 分割识别
  -> aligned depth 补充三维坐标
  -> 写入知识图谱短期记忆
  -> 导出 Neo4j 可视化文件
```

## 1. 推荐运行位置

RealSense 和 ROS2 后续建议在 Ubuntu 22.04 双系统中运行。

Windows 仍然适合：

- YOLO 训练；
- 数据集整理；
- Neo4j 查看；
- 图谱逻辑测试。

Ubuntu 22.04 更适合：

- RealSense D435i 采集；
- ROS2 Humble；
- 机械臂和夹爪控制；
- 手眼标定。

## 2. 当前已实现的文件

```text
wastekg/rgbd_geometry.py
  根据 mask/bbox + aligned depth + 相机内参计算 center_xyz、bbox_3d、visible_area_ratio、safe_grasp_score。

wastekg/rgbd_io.py
  读取 aligned_depth.png 和 camera_intrinsics.json。

wastekg/realsense_bridge.py
  可选 RealSense 采集接口。只有真正采集时才需要 pyrealsense2。

scripts/capture_realsense_frame.py
  从 RealSense 保存 color.png、aligned_depth.png、camera_intrinsics.json。

scripts/predict_rgbd_to_graph.py
  读取 RGB-D 文件，运行 YOLO，并导出知识图谱。
```

## 3. Ubuntu 中先验证相机

打开终端，输入：

```bash
rs-enumerate-devices
```

如果能看到 D435i 设备信息，说明系统识别到了相机。

再打开 RealSense Viewer：

```bash
realsense-viewer
```

需要确认：

- RGB 画面正常；
- Depth 画面正常；
- 相机插在 USB 3.0 口；
- 物体距离相机 40 cm 到 100 cm 时深度稳定；
- 没有明显大面积空洞。

## 4. 安装 Python 依赖

进入项目目录：

```bash
cd ~/Documents/multiagent/subprojects/dynamic-waste-kg
```

创建虚拟环境：

```bash
python3 -m venv .venv
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

安装基础依赖：

```bash
python -m pip install --upgrade pip
python -m pip install pillow ultralytics neo4j
```

安装 RealSense Python 包：

```bash
python -m pip install pyrealsense2
```

如果 `pyrealsense2` 安装失败，先不要继续接图谱，要先解决 RealSense SDK 或系统源问题。

## 5. 采集一帧 RGB-D

确认虚拟环境已激活后运行：

```bash
python scripts/capture_realsense_frame.py \
  --out artifacts/captures/frame_001 \
  --width 640 \
  --height 480 \
  --fps 30 \
  --warmup-frames 15
```

成功后应看到：

```text
artifacts/captures/frame_001/
  color.png
  aligned_depth.png
  camera_intrinsics.json
  capture_meta.json
```

这些文件含义：

- `color.png`：给 YOLO 分割识别；
- `aligned_depth.png`：与彩色图对齐的深度图；
- `camera_intrinsics.json`：相机内参；
- `capture_meta.json`：采集参数和设备信息。

## 6. 运行 RGB-D 到知识图谱

命令示例：

```bash
python scripts/predict_rgbd_to_graph.py \
  --image artifacts/captures/frame_001/color.png \
  --depth artifacts/captures/frame_001/aligned_depth.png \
  --intrinsics artifacts/captures/frame_001/camera_intrinsics.json \
  --weights runs/segment/runs/waste12_seg/yolo11n_seg_cdw_glass_e50/weights/best.pt \
  --out artifacts/rgbd_graph_frame_001 \
  --conf 0.5 \
  --imgsz 640 \
  --device 0 \
  --max-det 20
```

如果 Ubuntu 中没有 GPU 版 PyTorch，可以先用 CPU 验证：

```bash
python scripts/predict_rgbd_to_graph.py \
  --image artifacts/captures/frame_001/color.png \
  --depth artifacts/captures/frame_001/aligned_depth.png \
  --intrinsics artifacts/captures/frame_001/camera_intrinsics.json \
  --weights runs/segment/runs/waste12_seg/yolo11n_seg_cdw_glass_e50/weights/best.pt \
  --out artifacts/rgbd_graph_frame_001 \
  --conf 0.5 \
  --imgsz 640 \
  --device cpu \
  --max-det 20
```

成功后应生成：

```text
artifacts/rgbd_graph_frame_001/
  yolo_records.json
  rgbd_records.json
  camera_intrinsics.json
  vision_packet.json
  graph_snapshot.json
  events.jsonl
  graph.mmd
  neo4j_import.cypher
  prediction/
```

重点检查 `rgbd_records.json`：

```text
center_xyz
bbox_3d
visible_area_ratio
occlusion_state
grasp_candidates
safe_grasp_score
```

如果 `center_xyz` 的 Z 值明显不合理，例如全部为 0 或远大于实际距离，说明深度图或内参没有正确接入。

## 7. 导入 Neo4j

如果 Neo4j 已经在本机运行，Windows 或 Ubuntu 都可以导入。

命令示例：

```bash
python scripts/import_neo4j_cypher.py \
  --cypher artifacts/rgbd_graph_frame_001/neo4j_import.cypher \
  --uri bolt://localhost:7687 \
  --user neo4j \
  --password wastekg123456
```

然后在 Neo4j Browser 中查看：

```cypher
MATCH (i:Instance) RETURN i
```

查看实例与长期类别：

```cypher
MATCH p=(i:Instance)-[:OF_CATEGORY]->(c:Category) RETURN p LIMIT 80
```

查看 RGB-D 几何字段：

```cypher
MATCH (i:Instance)
RETURN i.instance_id, i.class_name, i.center_xyz, i.bbox_3d_json, i.visible_area_ratio, i.safe_grasp_score
ORDER BY i.safe_grasp_score DESC
```

## 8. 真实抓取前必须验证

当前输出的 `center_xyz` 是相机坐标系下的位置，不是机械臂基座坐标。

真实抓取前必须完成：

```text
camera_color_optical_frame -> robot_base
```

也就是求出 `T_base_camera`。

未完成手眼标定前，只能做：

- 图谱可视化；
- 目标排序；
- 算法验证；
- ROS2 空跑到目标上方。

不能直接闭合夹爪抓取。

## 9. 初步验收标准

第一阶段只要满足以下条件，就说明 RealSense 到知识图谱链路可用：

- `color.png` 和 `aligned_depth.png` 能正常保存；
- YOLO 能识别出多个目标；
- `rgbd_records.json` 中每个目标有合理 `center_xyz`；
- `visible_area_ratio` 大部分不是 0；
- Neo4j 中能看到 `Instance` 节点带三维字段；
- 同一个静止物体连续采集 30 帧，Z 方向波动最好小于 2 到 3 cm。

如果达不到这些标准，不要进入机械臂抓取阶段。
