# Windows fixed-view RGB capture guide

This guide records the Windows fallback workflow for fixed-view RGB capture.
It covers three immediate tasks before the full Ubuntu RealSense RGB-D workflow
is ready:

1. E4 dynamic sequence reshooting.
2. Lab-scene supplementary images for YOLO fine-tuning.
3. Fixed-scene images for before/after training comparison.

## Current camera status

- OpenCV can read the laptop camera at index `0`.
- OpenCV can read the external/table-facing camera at index `2` with `640x480`.
- `pyrealsense2` is not installed in the current Python 3.14 virtual environment.
- RealSense command line tools such as `rs-enumerate-devices` are not on PATH.
- Therefore, this Windows workflow captures RGB only through OpenCV preview.
  Aligned depth should be collected later through RealSense SDK or ROS2 on
  Ubuntu when geometry, pose, grasping or 3D tracking is evaluated.

## Should depth be collected now?

Depth is useful for the later research pipeline, but it is not mandatory for
the immediate RGB data collection.

Use RGB-only now for:

- Increasing training data for the 11 YOLO visual classes.
- Creating fixed-view before/after model comparison scenes.
- E4-style state change evidence under controlled camera pose.

Add aligned depth later for:

- Estimating object size, distance, occlusion and reachability.
- Supporting mechanical-arm grasp planning and ROS2 execution.
- Improving cross-frame object identity when RGB-only matching is ambiguous.
- Reporting RGB-D/RealSense contribution as an additional experiment.

Decision: do not block the current补拍 on depth. Capture clean RGB first, keep
camera pose and scene metadata, and reserve a second Ubuntu/RealSense RGB-D
round for robotics and geometry-related claims.

## Output location

The capture script writes to:

```text
subprojects/dynamic-waste-kg/artifacts/windows_e4_capture/
```

This folder is ignored by Git. Each scene contains:

```text
scene_id/
  rgb/
    T0_initial.jpg
    T1_removed.jpg
    T2_moved.jpg
    T3_reappeared.jpg
  manifest.json
  ground_truth_template.csv
```

Overwrite protection:

- By default, the script will not overwrite an existing scene directory.
- If `--scene-id lab_train_mixed_001` already exists, a new directory such as
  `lab_train_mixed_001_20260715_143000` will be created automatically.
- Use `--overwrite` only when you intentionally want to replace an old run.
- Recommended practice: use a fresh scene id for each real capture session,
  for example `lab_train_mixed_20260715_001`.

## Capture script

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\rgbd\capture_windows_e4_sequence.py `
  --scene-id dev_scene_001 `
  --protocol e4 `
  --camera-index 2 `
  --width 640 `
  --height 480 `
  --mode manual `
  --note "development sequence, not formal holdout"
```

The default mode opens a live preview window. Focus the preview window and use:

```text
Enter / Space / S = save current frame
Q / Esc           = stop capture
```

For formal holdout, use scene ids like:

```text
holdout_scene_001
holdout_scene_002
...
holdout_scene_010
```

## Protocol 1: E4 dynamic sequence

Each scene must follow exactly four frames:

```text
T0_initial:    initial scene
T1_removed:    remove exactly one object
T2_moved:      move exactly one object, without changing its class
T3_reappeared: put the removed object back
```

Rules:

- Keep the camera fixed.
- Keep lighting fixed.
- Keep exposure and resolution fixed.
- Do not touch non-operated objects.
- Do not change the background between T0 and T3.
- Use 3 to 6 visible objects per scene.
- Use visually distinct objects in early development scenes.
- Fill `ground_truth_template.csv` after capture.

## Minimum quality gate

Before formal holdout capture:

- The table or cloth should be clearly visible, not dark or noisy.
- Objects should occupy the central 60 percent of the image.
- No face, hand, or unrelated background should dominate the frame.
- At least one development sequence should be visually checked as a contact sheet.
- Formal sequences should not be used for parameter tuning.

## Protocol 2: lab-scene supplementary training images

Use this when collecting more images of your own objects to improve YOLO
recognition in the laboratory environment.

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\rgbd\capture_windows_e4_sequence.py `
  --scene-id lab_train_mixed_001 `
  --protocol dataset `
  --camera-index 2 `
  --width 640 `
  --height 480 `
  --mode manual `
  --frames 40 `
  --split train `
  --class-hint mixed `
  --note "lab supplementary YOLO training images"
```

Recommended capture rules:

- Capture 20 to 50 images per session, not hundreds of near-duplicates.
- Change only one factor every few frames: lighting, object rotation, object
  distance, background, partial occlusion, or object combination.
- Keep the 11-class taxonomy unchanged:
  `concrete`, `brick`, `tile`, `wood`, `gypsum_board`, `foam`, `metal`,
  `soft_plastic`, `hard_plastic`, `paperboard`, `glass`.
- Do not create a YOLO `unknown` class. Low-confidence or ambiguous examples
  should be handled by review logic, not as a training category.
- After capture, annotate the images with segmentation masks before adding them
  to training. Unlabeled images alone do not improve YOLO training.

## Protocol 3: fixed-scene before/after training comparison

Use this to create a small, stable evaluation scene. The same captured images
should be used to compare the old model and the fine-tuned model.

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\rgbd\capture_windows_e4_sequence.py `
  --scene-id comparison_scene_001 `
  --protocol comparison `
  --camera-index 2 `
  --width 640 `
  --height 480 `
  --mode manual `
  --split holdout `
  --class-hint mixed `
  --note "fixed scene for before/after model comparison"
```

Recommended comparison design:

- Do not train on these comparison images.
- Run the current `best.pt` on them and save predictions as the pre-training
  baseline.
- Fine-tune with separately collected and annotated lab training images.
- Run the new model on the exact same comparison images.
- Compare class correctness, missed objects, false positives, mask boundaries,
  and confidence changes.

## Current recommendation

The current external camera view is usable for testing the pipeline but too dark
for formal evidence. Turn on a stronger light, point the camera directly at the
capture surface, and place the objects before starting `holdout_scene_001`.
