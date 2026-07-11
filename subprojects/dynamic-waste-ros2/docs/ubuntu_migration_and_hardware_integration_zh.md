# Ubuntu 22.04 相机采集与 ROS2/机械臂接入指南

本文用于把 `multiagent` 迁移到 Ubuntu 22.04，并逐步接入 RealSense 相机、ROS2 2、Piper 机械臂。目标不是直接复用旧实验工程，而是保留其中已验证的设备经验，在当前职责边界和安全门控下重新接入。

## 1. 当前结论

- 当前 Git 的 `HEAD` 与 `origin/master` 均为 `5ab673a`，但 Windows 工作区仍有大量未提交和未跟踪修改；这些修改尚未上传。
- `dynamic-waste-kg`、`dynamic-waste-agent` 和 `dynamic-waste-ui` 的现有测试及 UI 构建已通过，但不能据此声称 ROS2 或真实机械臂闭环已验证。
- 旧目录 `E:\博论相关\piper_qudong（ubuntu尝试）\piper_qudong\1` 可作为设备探索记录，不应整目录迁移。其 `build/`、`install/`、`log/`、`__pycache__/`、模型权重和临时测试脚本均不应进入 Git。
- 旧 launch 文件含硬编码 API Key。若该 Key 曾有效，应立即撤销并重新生成；新系统只能从环境变量或未跟踪的本机配置读取密钥。

## 2. 不变的系统边界

```text
RealSense / YOLO / depth
  -> waste_robot_perception（结构化观测）
  -> perception_agent
  -> dynamic-waste-kg（事实和事件）
  -> supervisor/action_planning_agent（单步计划）
  -> waste_robot_bridge（契约转换和门控）
  -> waste_robot_executor（设备适配）
  -> Piper / 仿真
  -> 结构化执行反馈和新 Scene
```

- ROS2 不接收 LLM 自由文本，只接收经过 schema 校验的结构化命令。
- KG 不保存计划优先级、动作顺序或失败策略。
- 每次只执行一个物理动作；成功或失败后当前 Scene 都失效，必须重新采集再规划。
- `unknown`、低置信度、VLM 冲突和高风险对象必须进入人工复核。
- 真机自动使能、自动回零和自动抓取默认全部关闭。

## 3. 推荐 ROS2 工作区结构

```text
dynamic-waste-ros2/ros2_ws/src/
  waste_robot_msgs/          # msg/srv/action；无业务推理
  waste_robot_perception/    # RealSense 订阅、同步、观测适配
  waste_robot_bridge/        # Agent 命令到 ROS2 action 的受控桥接
  waste_robot_executor/      # Piper SDK/CAN 设备适配和状态机
  waste_robot_bringup/       # launch、参数、udev/CAN 文档
```

旧 `waste_sorting` 包混合了视觉、LLM、标定和机械臂控制，建议只抽取参数和算法片段，不直接复制节点。旧自定义消息需要与 `wastekg.interfaces.contracts` 对齐后重新定义，避免形成第二套协议。

## 4. Ubuntu 基线与仓库迁移

在 Windows 完成提交和推送后，Ubuntu 侧执行：

```bash
git clone https://github.com/yanxueya/multiagent.git
cd multiagent
git status --short --branch
git rev-parse HEAD
git rev-parse origin/master
```

仅当工作区干净且两个提交号一致时，才认为迁移内容完整。不要复制 Windows 的 `.venv`、`node_modules`、ROS2 `build/install/log`、数据集或权重。

Ubuntu 22.04 推荐 ROS 2 Humble。安装后固定每个终端的基础环境：

```bash
source /opt/ros/humble/setup.bash
cd ~/multiagent/subprojects/dynamic-waste-ros2/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

依赖必须优先写入各 package 的 `package.xml`；不要依赖一次性的全局 `pip install`。Python 非 ROS 依赖使用独立虚拟环境或明确的 requirements/lock 文件。

## 5. 阶段 A：只验证相机驱动

先不启动 YOLO、Agent、KG 或机械臂。

```bash
lsusb
rs-enumerate-devices
ros2 launch realsense2_camera rs_launch.py \
  align_depth.enable:=true \
  enable_color:=true \
  enable_depth:=true \
  enable_gyro:=false \
  enable_accel:=false
```

验收项：

- 彩色图、深度图、相机内参话题持续发布。
- 彩色和深度时间戳单调，帧率稳定，无持续 USB reset。
- 明确使用 `camera_color_optical_frame`、`camera_depth_optical_frame` 等真实 frame，不手工猜测 frame 名。
- 深度单位、无效值比例和对齐方向经过实测。
- 15 FPS 和 30 FPS 参数必须统一；旧工程 launch 使用 15 FPS，而 YAML 使用 30 FPS，不能保留双重真源。

## 6. 阶段 B：可复现的数据采集

第一轮只录原始 ROS bag，不把推理结果写回 KG：

```bash
mkdir -p ~/waste_data/bags
ros2 bag record -o ~/waste_data/bags/scene_001 \
  /camera/camera/color/image_raw \
  /camera/camera/aligned_depth_to_color/image_raw \
  /camera/camera/color/camera_info \
  /tf /tf_static
```

每个 bag 旁保存一份不含密钥的元数据：场景 ID、日期、相机序列号、分辨率、FPS、曝光设置、安装方式、标定版本、对象清单和备注。采集文件、bag、图像和点云默认不进 Git，只提交采集协议与小型脱敏样例。

验收项：bag 可被 `ros2 bag play --clock` 回放；感知节点在回放上产生确定格式的 Observation；真实相机与回放走相同接口。

## 7. 阶段 C：感知接入但不控制机械臂

- `waste_robot_perception` 只负责 ROS 消息适配、时间同步、frame/单位校验和 Observation 构造。
- YOLO 与 RGB-D 业务逻辑继续复用 `dynamic-waste-kg/wastekg/yolo`、`perception`、`rgbd`，不要在 ROS2 包中复制一套。
- 视觉类别严格保持 11 类；`unknown` 不进入 YOLO 类别表。
- 使用 `message_filters` 或等价策略同步彩色、对齐深度和 CameraInfo，并记录允许的最大时间差。
- 每个观测携带 `scene_id`、时间戳、frame_id、模型/权重版本、置信度、mask/crop 引用和深度质量。

验收顺序：静态图片单测 → bag 回放 → 实时相机 → KG 写入。每一步都检查类别、单位、坐标系和重复帧幂等性。

## 8. 阶段 D：标定与坐标链

先确定相机是 eye-to-hand 还是 eye-in-hand；旧代码和文件名不能代替真实安装方式。推荐用 TF2 表达：

```text
camera_color_optical_frame
  -> camera_link
  -> robot_base_link（eye-to-hand）

或

camera_color_optical_frame
  -> tool0 / end_effector（eye-in-hand）
  -> robot_base_link
```

标定产物必须包含：方法、样本数、时间、相机序列号、机械臂序列号、安装方式、4x4 变换矩阵、单位、坐标约定、重投影/位置误差和验证点误差。不要同时叠加“标定矩阵 + manual offset + TCP offset”而没有清晰定义，否则容易重复补偿。

至少用未参与拟合的检查点验证，并分别报告平移误差和姿态误差。误差超出抓取容差时不得进入真机抓取阶段。

## 9. 阶段 E：机械臂独立 bringup 与 dry-run

先确认 Piper 官方 SDK/ROS2 驱动版本及 CAN 设备名，再配置 `can0`。CAN 初始化命令应写成独立运维脚本或 systemd/udev 配置，不要由 ROS 节点执行 `sudo`。

机械臂执行器至少需要以下状态：

```text
DISCONNECTED -> DISABLED -> READY -> EXECUTING
                         -> STOPPING -> FAULT
```

必须具备：

- 启动时默认 `auto_enable=false`、`auto_home=false`。
- 显式人工确认、物理急停可达、低速和安全工作区限制。
- 关节限位、笛卡尔工作区、速度、加速度、夹爪力和超时校验。
- 命令 ID 幂等；同一 `action_id` 不能重复触发物理动作。
- 反馈基于设备状态/位置容差，而非固定 `sleep` 猜测完成。
- 超时、CAN 断开、状态异常、目标不可达时进入 FAULT，并禁止自动重试。
- 节点退出或通信丢失时执行受控停止，而不是继续上一次命令。

测试顺序：不连接硬件的 mock executor → 连接但不使能 → 只读状态 → 人工使能 → 单关节极小位移 → 安全 home → 空载笛卡尔动作。任何阶段失败都回退，不直接进入抓取。

## 10. 阶段 F：Agent/ROS2 闭环

建议用 ROS2 Action 表达物理动作，Goal/Feedback/Result 至少包含：

- Goal：`action_id`、`scene_id`、`target_instance_id`、结构化动作类型、目标姿态、速度/力限制、确认令牌。
- Feedback：执行状态、设备状态、当前位姿、进度和安全状态。
- Result：`succeeded/failed/aborted/rejected`、是否开始物理尝试、失败原因和时间戳。

桥接层在发送 Goal 前再次检查：Scene 新鲜、计划已校验、目标仍存在、人工确认有效、设备 READY、急停未触发。动作结束后无论成功失败都发布执行事件，并强制重新采集 Scene。

## 11. 旧工程复核清单

可复用：Piper SDK 调用经验、CAN 端口、RealSense 话题选择、标定采样思路、关节/末端姿态试验数据。

需要重做或隔离：

- launch 中硬编码密钥和模型路径。
- 启动即自动使能、自动回零。
- 将视觉、LLM、机械臂和业务编排塞入同一包或节点。
- 固定 `sleep` 驱动动作时序。
- 重复存在的独立测试脚本和交互式脚本。
- `build/install/log/__pycache__` 与 `yolov8n.pt` 等生成物。
- 旧类别体系、LLM 直接分类结论及任何自由文本控制路径。
- 未明确的角度/弧度、毫米/米和 optical frame/robot frame 转换。

## 12. 每阶段放行门槛

| 阶段 | 放行证据 |
| --- | --- |
| Git 迁移 | Ubuntu `HEAD == origin/master`，工作区干净 |
| 相机 | 话题、帧率、时间戳、frame、深度单位验证通过 |
| 采集 | bag 可回放，元数据和标定版本齐全 |
| 感知 | 11 类契约、低置信度复核和 Observation schema 测试通过 |
| 标定 | 独立验证点误差满足抓取容差 |
| 执行器 | mock、只读、低速单步、停止和故障注入通过 |
| 闭环 | 单动作、幂等、人工确认、Scene 失效与重采集通过 |

在完成最后一项前，系统的准确表述仍是“受控二维实例分割到可审计知识状态，并进行 ROS2/硬件接入验证”，不能表述为已证明真实自主抓取闭环。
