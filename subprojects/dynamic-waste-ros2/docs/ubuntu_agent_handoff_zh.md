# 给 Ubuntu 22.04 配置代理的任务交接书

> 使用方式：把本文件和整个 `0711try` 目录复制到 Ubuntu，然后把本文件完整交给 Ubuntu 系统上的编码代理。代理应先阅读仓库 `AGENTS.md`，再严格按本文分阶段工作。

## 一、任务目标

请在 Ubuntu 22.04 上配置本仓库，优先完成：

1. 验证仓库、Python、GPU、ROS 2 和 RealSense 环境；
2. 运行知识图谱、LangGraph 和 UI 的非硬件测试；
3. 驱动 RealSense D435i，验证彩色、深度、内参和 TF；
4. 完成可复现的 rosbag 数据采集与回放；
5. 使用已有自训练 YOLO11s-seg 权重进行离线和实时推理；
6. 设计并逐步实现 ROS 2 感知适配层；
7. 只有在前述步骤全部通过后，才准备 Piper 机械臂的 dry-run 接入。

本次不要重新训练 YOLO。先验证已有权重在 RealSense 新数据上的效果，再由用户决定是否微调。

## 二、仓库和模型基线

预期仓库提交：

```text
5be033403e6814c0d9bbf95a5be87d126c3a9ac2
```

自训练主模型在迁移目录中的相对路径：

```text
local_models/waste11_yolo11s_seg_best.pt
```

预期模型信息：

```text
模型：YOLO11s-seg
任务：11 类建筑废弃物二维实例分割
大小：20498980 bytes
SHA-256：C41C92EC01D63F15FEE5C1B9DCB8BBEE026F65E7281514F4F2F444E449C87C69
```

11 个明确视觉类别必须保持为：

```text
concrete
brick
tile
wood
gypsum_board
foam
metal
soft_plastic
hard_plastic
paperboard
glass
```

`unknown` 不是 YOLO 训练类别；它只能由系统逻辑、VLM 冲突或人工复核产生。`asbestos_suspect` 也不是当前 YOLO 类别。

## 三、必须遵守的边界

- 先读根目录 `AGENTS.md` 和 `subprojects/dynamic-waste-ros2/AGENTS.md`。
- 不得推翻 KG、LangGraph、UI 已确认设计。
- 不得启动模型训练，除非用户之后明确授权。
- 不得把数据集、rosbag、模型权重、`.env`、密钥、`build/`、`install/`、`log/`、虚拟环境或生成产物提交到 Git。
- 不得让 LLM 自由文本直接控制 ROS 2 或机械臂。
- 不得默认自动使能、自动回零或自动抓取机械臂。
- 不得在没有物理急停、人工确认、工作区限制和失败处理时发送真机动作。
- 不得声称当前系统已验证真实机械臂闭环或施工现场自主运行。
- 不要通过 ROS 节点运行 `sudo`；CAN、udev 和系统权限应由独立运维步骤配置。
- 发现密钥时只报告文件和风险，不打印密钥内容。

## 四、第一阶段：只读环境审计

先定位仓库根目录，例如：

```bash
cd ~/0711try
pwd
git status --short --branch
git rev-parse HEAD
git remote -v
```

要求：`HEAD` 与上述提交一致。若工作区有未知修改，先报告，不要覆盖。

采集环境信息：

```bash
uname -a
lsb_release -a
python3 --version
git --version
nvidia-smi
nvcc --version || true
docker --version || true
ros2 --help >/dev/null && ros2 doctor --report
lsusb
```

注意：`nvidia-smi` 显示的 CUDA Version 是驱动支持上限，不要求 PyTorch wheel 使用完全相同的 CUDA 标签。不要为了追求“CUDA 版本数字一致”盲目替换驱动。

检查模型：

```bash
test -f local_models/waste11_yolo11s_seg_best.pt
stat -c '%n %s bytes' local_models/waste11_yolo11s_seg_best.pt
sha256sum local_models/waste11_yolo11s_seg_best.pt
```

若哈希不一致，停止模型接入并报告，不要继续使用损坏权重。

第一阶段只输出审计结论和缺失项；不要立即大规模安装或升级系统。

## 五、第二阶段：配置非硬件软件环境

Ubuntu 22.04 优先使用 ROS 2 Humble。先确认系统已有 ROS 2 发行版，不要同时混用多个发行版。

知识图谱建议独立虚拟环境：

```bash
cd ~/0711try/subprojects/dynamic-waste-kg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests
```

若 GPU PyTorch/Ultralytics 尚未安装：

- 先查项目 `pyproject.toml` 和现有依赖；
- 根据当前 Ubuntu 驱动选择官方支持的 PyTorch wheel；
- 安装后验证 `torch.cuda.is_available()`、GPU 名称和一次小型推理；
- 不启动训练；
- 不擅自全局升级 NVIDIA 驱动。

LangGraph 子项目：

```bash
cd ~/0711try/subprojects/dynamic-waste-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ../dynamic-waste-kg
python -m unittest discover -s tests
```

UI：

```bash
cd ~/0711try/subprojects/dynamic-waste-ui
npm install
npm test -- --run
npm run build
```

如果 lock 文件存在，优先使用与项目一致的确定性安装命令。不要因为测试失败就删除或重写现有设计；先定位依赖差异并报告。

## 六、第三阶段：RealSense 驱动验证

先确认相机型号、序列号、USB 连接速率和已有 librealsense/realsense2_camera 状态。安装或修复驱动时优先遵循 Intel RealSense 与 ROS 2 驱动的官方说明，并记录实际版本。

只启动相机，不启动 YOLO、Agent、KG 或机械臂：

```bash
rs-enumerate-devices
source /opt/ros/humble/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  align_depth.enable:=true \
  enable_color:=true \
  enable_depth:=true \
  enable_gyro:=false \
  enable_accel:=false
```

在另一个终端检查：

```bash
source /opt/ros/humble/setup.bash
ros2 node list
ros2 topic list
ros2 topic hz /camera/camera/color/image_raw
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
ros2 topic echo --once /camera/camera/color/camera_info
ros2 run tf2_tools view_frames
```

实际话题名可能因驱动版本或 camera namespace 不同而变化。代理必须以 `ros2 topic list` 的真实输出为准，不得硬编码猜测。

验收：

- 彩色、深度和 CameraInfo 都持续发布；
- 彩色与深度分辨率一致或明确记录对齐策略；
- 时间戳正常、帧率稳定；
- TF 中 frame 名真实存在；
- 深度单位和无效深度比例得到验证；
- 没有持续 USB reset 或掉帧。

第一轮建议从 640×480、15 FPS 开始以降低 USB 和计算负载，稳定后再测试 30 FPS。只保留一套权威参数文件，避免 launch 与 YAML 参数冲突。

## 七、第四阶段：数据采集和回放

数据放在仓库外，例如：

```bash
mkdir -p ~/waste_data/bags
```

根据真实话题名录制：

```bash
ros2 bag record -o ~/waste_data/bags/scene_001 \
  /camera/camera/color/image_raw \
  /camera/camera/aligned_depth_to_color/image_raw \
  /camera/camera/color/camera_info \
  /tf /tf_static
```

每个 bag 保存配套元数据：

- scene_id；
- 日期和相机序列号；
- 分辨率、FPS、曝光设置；
- 相机安装方式；
- 标定版本；
- 物体类别和场景说明；
- 相机驱动版本；
- Git 提交号和模型 SHA-256。

验证：

```bash
ros2 bag info ~/waste_data/bags/scene_001
ros2 bag play ~/waste_data/bags/scene_001 --clock
```

只有 bag 可稳定回放，才进入感知接入。

## 八、第五阶段：已有 YOLO 权重推理

先用仓库已有的单图推理入口确认模型可加载。代理应检查脚本 `--help` 获取准确参数，不要凭记忆拼命令：

```bash
cd ~/0711try/subprojects/dynamic-waste-kg
source .venv/bin/activate
python scripts/graph/predict_image_to_graph.py --help
```

权重绝对路径示例：

```bash
WEIGHTS=~/0711try/local_models/waste11_yolo11s_seg_best.pt
```

选择从 RealSense bag 导出的一张彩色图进行推理，输出写到被 Git 忽略的 `artifacts/`。检查：

- 模型任务确实是 segmentation；
- 模型 names 恰好对应 11 类且顺序正确；
- 输出包含 bbox、mask、类别和置信度；
- `0.05 <= conf < 0.30` 的候选进入 `review_required`，不自动变成 unknown；
- 低置信度、高风险和冲突对象不直接进入机器人执行。

先人工审核至少一批 RealSense 新图的误检、漏检和 mask 边界。只有出现明显域偏移时才建议用户后续微调；本任务不训练。

## 九、第六阶段：ROS 2 感知适配设计

目标目录：

```text
subprojects/dynamic-waste-ros2/ros2_ws/src/
  waste_robot_msgs/
  waste_robot_perception/
  waste_robot_bridge/
  waste_robot_executor/
  waste_robot_bringup/
```

先实现最小 `waste_robot_perception`：

- 订阅彩色图、对齐深度和 CameraInfo；
- 使用时间同步机制；
- 校验 frame、时间戳和单位；
- 调用 `dynamic-waste-kg` 已有 YOLO/RGB-D/Observation 逻辑；
- 发布或传递结构化 Observation；
- 不复制第二套业务逻辑；
- 不控制机械臂。

接口必须与 `wastekg.interfaces.contracts` 对齐。不要直接复制旧 `waste_sorting_interfaces` 形成另一套协议。

完成 package 后运行：

```bash
cd ~/0711try/subprojects/dynamic-waste-ros2/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
colcon test
colcon test-result --verbose
```

先用 rosbag 回放测试，再接实时相机。

## 十、机械臂阶段的暂停点

在相机、回放、YOLO、Observation schema 和 ROS 2 感知适配全部通过后，先暂停并向用户汇报，不要自动进入 Piper 真机控制。

继续机械臂工作前必须确认：

- Piper 型号、官方 SDK/ROS 2 驱动版本；
- CAN 适配器型号和 `can0` 状态；
- 物理急停可用；
- 工作区清空并设置软限位；
- `auto_enable=false`、`auto_home=false`；
- 有 mock/dry-run executor；
- 有人工确认令牌；
- 有 `action_id` 幂等保护；
- 有超时、通信中断、目标不可达和受控停止处理；
- 动作完成基于设备反馈，不使用固定 `sleep` 作为唯一依据；
- 动作成功或失败后强制 Scene 失效并重新观测。

标定必须明确是 eye-to-hand 还是 eye-in-hand，统一米/毫米、度/弧度和 optical/robot frame。不要在没有定义的情况下叠加标定矩阵、TCP offset 和人工 offset。

## 十一、代理完成每阶段后的回报格式

每阶段请报告：

```text
阶段：
结论：通过 / 部分通过 / 阻塞
实际版本：
执行的关键命令：
通过的验证：
失败或缺失证据：
修改的文件：
未执行的高风险操作：
下一步建议：
```

不得用“应该可用”替代实测证据。无法获得的数据要明确写“未验证”。涉及真机前必须停下来请求用户确认。

## 十二、最终成功标准

本轮 Ubuntu 配置成功不等于真实抓取成功。建议把本轮成功标准限定为：

```text
仓库与依赖可复现
+ RealSense 彩色/深度/内参/TF 可用
+ rosbag 可采集和回放
+ 自训练 YOLO11s-seg 可对 RealSense 图片推理
+ 11 类与 unknown 边界正确
+ 结构化 Observation 可进入感知/KG 接口
+ ROS 2 感知包可构建和测试
```

Piper 真机、手眼标定、MoveIt 规划和抓取闭环属于后续独立验收阶段。
