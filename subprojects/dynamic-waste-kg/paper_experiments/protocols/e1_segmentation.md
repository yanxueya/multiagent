# E1 YOLO11n-seg 独立测试集评估

## 目的

回答 RQ1：轻量级 YOLO11n-seg 是否能在受控建筑废弃物数据集上提供可用的二维实例分割基线。

## 冻结配置

- 数据：`datasets/waste11_grouped_v1/data.yaml`
- 权重：`runs/paper_e1/yolo11n_seg_waste11_grouped_e50_v1/weights/best.pt`
- 测试输出：`artifacts/e1_test_evaluation_r2`
- 设备：RTX 5060 Laptop GPU，PyTorch nightly cu128

## 已有结果

- Test 图像数：890
- Test 有效实例数：19,475
- Box mAP50-95：0.8437
- Mask mAP50-95：0.7397

## 论文写法

E1 只能证明二维实例分割能力，不能证明三维定位、夹爪抓取成功率或 ROS2 执行能力。
