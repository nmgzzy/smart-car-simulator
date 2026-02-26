# 智能小车模拟系统

基于 Python + Pygame 的 2D 俯视图智能小车模拟器，用于控制算法的快速调试与验证，方便后续部署到真机运行。

## 功能特性

- **运动仿真** — 简化自行车运动模型，支持加减速、转向，含摩擦力和离道减速
- **摄像头模拟** — 透视变换生成模拟摄像头灰度图像，与真机输出格式一致
- **随机赛道生成** — 支持 7 种赛道元素的随机组合，生成闭合赛道
- **实时可视化** — 赛道俯视图 + 摄像头画面 + 状态面板
- **算法接口** — 统一的 `BaseController` 接口，算法代码可直接迁移到真机

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

依赖项：`pygame >= 2.5`、`opencv-python >= 4.8`、`numpy >= 1.24`

### 启动模拟器

```bash
# 默认赛道 + 键盘驾驶（首次运行会自动生成赛道）
python main.py

# 生成随机赛道后启动
python main.py --generate --seed 42

# 使用循线算法自动驾驶
python main.py --controller linefollow

# 使用快速小车配置
python main.py --car-config configs/fast.json

# 自定义赛道图片 + 灵活小车
python main.py --track path/to/track.png --car-config configs/agile.json
```

### 操作按键

| 按键 | 功能 |
|------|------|
| `↑` / `W` | 加速 |
| `↓` / `S` | 刹车 / 倒车 |
| `←` / `A` | 左转 |
| `→` / `D` | 右转 |
| `Space` | 暂停 / 继续 |
| `R` | 重置小车到起点 |
| `Tab` | 切换控制器（键盘 ↔ 循线） |
| `Esc` | 退出 |

## 赛道生成

`track_generator.py` 可独立运行，随机生成包含以下元素的闭合赛道：

| 元素 | 说明 |
|------|------|
| 直线 | 160–320 px 随机长度 |
| 大弯道 | 半径 300 px，50°–110° |
| 中弯道 | 半径 180 px，50°–110° |
| 小弯道 | 半径 100 px，50°–90° |
| S 弯道 | 两段反向弯道组合 |
| 十字路口 | 主路直行 + 垂直穿越道路 |
| 环岛 | 270° 圆环 + 额外出口臂 |

赛道格式：灰度 PNG 图片，**白色 (255) = 赛道**，**黑色 (0) = 背景**。

```bash
# 独立生成赛道
python track_generator.py --output assets/track.png --seed 42 --elements 15 --width 80
```

参数说明：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--output` | `assets/track_default.png` | 输出路径 |
| `--seed` | 随机 | 随机种子（相同种子生成相同赛道） |
| `--elements` | 12 | 赛道元素数量 |
| `--width` | 80 | 赛道宽度（像素） |

也可以使用任何图像编辑软件手绘赛道（白色道路、黑色背景），保存为 PNG 后直接加载。

## 项目结构

```
car/
├── main.py               # 程序入口，命令行参数解析
├── simulator.py           # Pygame 主循环与可视化渲染
├── car.py                 # 小车物理模型（自行车模型）
├── track.py               # 赛道加载与像素级查询
├── track_generator.py     # 随机赛道生成器（可独立运行）
├── sensor.py              # 摄像头模拟（透视变换）
├── controller.py          # 控制器接口与示例实现
├── config.py              # 小车配置加载模块
├── requirements.txt       # Python 依赖
├── assets/
│   └── track_default.png  # 默认赛道图片
└── configs/               # 小车配置文件目录
    ├── default.json       # 默认小车配置
    ├── fast.json          # 快速小车配置
    ├── stable.json        # 稳定小车配置
    ├── agile.json         # 灵活小车配置
    └── heavy.json         # 重型小车配置
```

## 模块说明

### `car.py` — 小车物理模型

采用简化的自行车运动模型（Bicycle Model）：

```
speed  += (throttle × acceleration − friction × speed) × dt
heading += (speed / wheelbase) × tan(steer × max_steer_angle) × dt
x      += speed × cos(heading) × dt
y      += speed × sin(heading) × dt
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_speed` | 200 px/s | 最大速度 |
| `acceleration` | 160 px/s² | 加速度 |
| `friction` | 2.0 | 摩擦系数（离开赛道 ×3） |
| `wheelbase` | 30 px | 轴距 |
| `max_steer_angle` | 35° | 最大转向角 |

**配置文件加载**：小车参数可以从 JSON 配置文件加载，方便切换不同的小车模型。

### `config.py` — 配置加载模块

支持从 JSON 文件加载小车配置参数。内置了 5 种预设配置：

| 配置文件 | 说明 | 特点 |
|---------|------|------|
| `configs/default.json` | 默认小车 | 平衡的性能，适合一般场景 |
| `configs/fast.json` | 快速小车 | 高速度和加速度，低摩擦 |
| `configs/stable.json` | 稳定小车 | 低速平稳，适合复杂赛道 |
| `configs/agile.json` | 灵活小车 | 小轴距，大转向角，灵活转弯 |
| `configs/heavy.json` | 重型小车 | 低速大惯性，适合模拟重载车辆 |

**自定义配置**：创建 JSON 文件，包含以下字段：

```json
{
  "name": "我的小车",
  "max_speed": 200.0,
  "acceleration": 160.0,
  "friction": 2.0,
  "wheelbase": 30.0,
  "max_steer_angle": 35.0
}
```

使用自定义配置启动：

```bash
python main.py --car-config my_car.json
```

### `sensor.py` — 摄像头模拟

根据小车位置与朝向，从赛道图中裁剪前方梯形区域，经 `cv2.getPerspectiveTransform` 透视变换为矩形图像，模拟真实下视摄像头视角。

- 输出分辨率：160 × 120（可配置）
- 输出格式：灰度 `np.ndarray (H, W), uint8`
- 图像下方 = 近处道路，上方 = 远处道路

### `controller.py` — 控制器接口

```python
class BaseController:
    def control(self, camera_image: np.ndarray) -> tuple:
        """输入灰度摄像头图像，返回 (throttle, steer)"""
        raise NotImplementedError
```

- `throttle`：-1.0（刹车/倒车）~ 1.0（全速加速）
- `steer`：-1.0（左转）~ 1.0（右转）

内置两个实现：

| 控制器 | 说明 |
|--------|------|
| `KeyboardController` | 方向键 / WASD 手动驾驶 |
| `LineFollowController` | 二值化 → 白色区域重心检测 → 比例控制转向 |

## 编写自定义控制算法

继承 `BaseController`，实现 `control` 方法即可：

```python
from controller import BaseController
import numpy as np

class MyController(BaseController):
    def control(self, camera_image: np.ndarray) -> tuple:
        # camera_image: 灰度图 (120, 160), uint8
        # 白色=赛道, 黑色=背景

        # ... 你的算法逻辑 ...

        throttle = 0.5   # 油门
        steer = 0.0       # 转向
        return throttle, steer
```

在 `main.py` 中注册后即可使用。

## 迁移到真机

控制器的 `control()` 方法仅依赖一个灰度 numpy 数组作为输入，与模拟器完全解耦。部署到真机时：

1. 将摄像头数据源从 `CameraSensor.capture()` 替换为真实摄像头采集
2. 将 `(throttle, steer)` 输出映射到电机驱动的 PWM 信号
3. 控制算法代码无需任何修改

```python
# 真机伪代码
from controller import MyController
import cv2

ctrl = MyController()
camera = cv2.VideoCapture(0)

while True:
    ret, frame = camera.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    throttle, steer = ctrl.control(gray)
    motor_drive(throttle, steer)  # 驱动电机
```
