# RealSense RGB-D KG Minimal Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal RealSense/RGB-D pathway that turns YOLO segmentation results plus aligned depth into 3D knowledge-graph instances.

**Architecture:** Keep `dynamic-waste-kg` as the world-model subproject. Add small RGB-D geometry and RealSense adapter modules here, but leave ROS2 control, MoveIt2, simulation, and UI for later sibling subprojects. The first working loop is `RGB image + aligned depth + intrinsics -> YOLO records -> 3D-enriched records -> KnowledgeGraph -> Neo4j export`.

**Tech Stack:** Python, Ultralytics YOLO, optional Intel RealSense `pyrealsense2`, Pillow for image IO, standard `unittest`.

---

### Task 1: Document Project Boundary

**Files:**
- Modify: `README.md`
- Modify: `docs/knowledge_seed_zh.md`

- [x] **Step 1: Add system-level boundary to README**

Record that `dynamic-waste-kg` owns the world model and that ROS2/UI/simulation should become sibling subprojects later.

- [x] **Step 2: Add RealSense responsibility to knowledge seed**

Record that RealSense updates short-term instance geometry, not long-term category semantics.

### Task 2: RGB-D Geometry Core

**Files:**
- Create: `wastekg/rgbd_geometry.py`
- Test: `tests/test_rgbd_geometry.py`

- [x] **Step 1: Write tests for depth-to-3D enrichment**

Tests must cover:
- centered mask with valid depth produces `center_xyz` in meters;
- bbox fallback works when mask is missing;
- invalid depth pixels reduce `visible_area_ratio`;
- enriched records preserve original YOLO class and confidence.

- [x] **Step 2: Implement minimal geometry**

Create:
- `CameraIntrinsics`;
- `deproject_pixel_to_point`;
- `enrich_record_with_rgbd`;
- `enrich_records_with_rgbd`.

The implementation should use mask polygons or bbox pixels, filter invalid depth, compute robust median center, compute `bbox_3d`, and add one conservative top-down grasp candidate.

- [x] **Step 3: Run geometry tests**

Run:

```powershell
$env:PYTHONPATH="C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg"
.\subprojects\dynamic-waste-kg\.venv\Scripts\python.exe -m unittest C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\tests\test_rgbd_geometry.py
```

Expected: all geometry tests pass.

### Task 3: Optional RealSense Capture Adapter

**Files:**
- Create: `wastekg/realsense_bridge.py`
- Create: `scripts/rgbd/capture_realsense_frame.py`

- [x] **Step 1: Implement optional import boundary**

`wastekg/realsense_bridge.py` must not require `pyrealsense2` at package import time. Import it only inside capture functions so Windows development and tests still work without the camera SDK.

- [x] **Step 2: Save one aligned RGB-D frame**

Create a capture function that saves:

```text
color.png
aligned_depth.png
camera_intrinsics.json
capture_meta.json
```

- [x] **Step 3: Provide a beginner script**

`scripts/rgbd/capture_realsense_frame.py` should expose:

```powershell
python scripts\rgbd\capture_realsense_frame.py --out artifacts\captures\frame_001
```

### Task 4: RGB-D Image to Graph Script

**Files:**
- Create: `scripts/rgbd/predict_rgbd_to_graph.py`

- [x] **Step 1: Load color image, aligned depth image, and intrinsics**

The script should accept:

```powershell
python scripts\rgbd\predict_rgbd_to_graph.py `
  --image artifacts\captures\frame_001\color.png `
  --depth artifacts\captures\frame_001\aligned_depth.png `
  --intrinsics artifacts\captures\frame_001\camera_intrinsics.json `
  --weights outputs\yolo_runs\segment\runs\waste12_seg\yolo11n_seg_cdw_glass_e50\weights\best.pt `
  --out artifacts\rgbd_graph_demo `
  --conf 0.5 `
  --device 0 `
  --max-det 20
```

- [x] **Step 2: Export graph artifacts**

The script should write:

```text
yolo_records.json
rgbd_records.json
vision_packet.json
graph_snapshot.json
events.jsonl
graph.mmd
neo4j_import.cypher
```

### Task 5: Verification

**Files:**
- Test: all tests

- [x] **Step 1: Run unit tests**

```powershell
$env:PYTHONPATH="C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg"
.\subprojects\dynamic-waste-kg\.venv\Scripts\python.exe -m unittest discover -s C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\tests
```

Expected: all tests pass.

- [x] **Step 2: Explain hardware limitation**

If RealSense is not connected in the current Windows session, do not claim camera capture was verified. Only claim import-safety and offline RGB-D geometry tests passed.
