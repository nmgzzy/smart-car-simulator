# 智能小车模拟系统

基于 Python + Pygame 的 2D 俯视图智能小车模拟器，用于控制算法的快速调试与验证，方便后续部署到真机运行。

## 功能特性

- **运动仿真** — 简化自行车运动模型，支持加减速、转向，包含纵向摩擦与高速弯道侧滑
- **摄像头模拟** — 透视变换生成模拟摄像头灰度图像，与真机输出格式一致
- **赛道指令编辑器（实时预览）** — 文本指令逐步构建赛道，Pygame 实时渲染预览，支持保存 / 加载
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
# 默认赛道 + 键盘驾驶
python main.py

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

赛道格式：灰度 PNG 图片，**白色 (255) = 赛道**，**黑色 (0) = 背景**。

提供两种方式创建赛道：

### 方式一：指令编辑器（推荐，支持实时预览）

`track_editor.py` 提供 Pygame 实时预览的交互式编辑器，通过文本指令逐步构建赛道：

```bash
python track_editor.py                                   # 空白开始
python track_editor.py --load assets/my_track_instr.txt  # 加载已有指令
python track_editor.py --output assets/my_track.png      # 指定输出路径
```

**指令集：**

| 指令 | 说明 | 示例 |
|------|------|------|
| `F<距离>` | 前进直线 | `F200` |
| `R<半径>-<角度>` | 右转弯道 | `R100-90` |
| `L<半径>-<角度>` | 左转弯道 | `L80-45` |
| `SL<半径>-<角度>-<次数>` | S 弯道（先左后右交替） | `SL60-45-4` |
| `SR<半径>-<角度>-<次数>` | S 弯道（先右后左交替） | `SR60-45-4` |
| `FINISH` | 闭合回起点（Hermite 曲线平滑连接） | `FINISH` |

**编辑器快捷键：**

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 添加当前指令 |
| `Ctrl+Z` | 撤销上一条指令 |
| `Ctrl+S` | 保存赛道（PNG + 起点信息 + 指令文件） |
| `Ctrl+F` | 自动适配视图 |
| `Ctrl+E` | 加载内置示例指令 |
| 鼠标拖拽 | 平移视图 |
| 滚轮 | 缩放视图 |
| `Esc` | 退出 |

保存时自动生成三个文件：
- `xxx.png` — 灰度赛道图（可直接被模拟器加载）
- `xxx_info.txt` — 起点坐标和朝向
- `xxx_instr.txt` — 指令文本（可通过 `--load` 重新加载编辑）

**示例指令（Ctrl+E 可快速加载）：**

```text
F200
R100-90
F300
L120-60
F200
SL70-40-4
F150
F200
R80-90
F250
SR100-35-3
F180
L100-45
F200
FINISH
```

### 方式二：手绘赛道

使用任何图像编辑软件手绘赛道（白色道路、黑色背景），保存为 PNG 后直接加载。

## 项目结构

```
car/
├── main.py               # 程序入口，命令行参数解析
├── simulator.py           # Pygame 主循环与可视化渲染
├── car.py                 # 小车物理模型（自行车模型）
├── track.py               # 赛道加载与像素级查询
├── track_editor.py        # 赛道指令编辑器（实时预览 + 保存）
├── sensor.py              # 摄像头模拟（透视变换）
├── controller.py          # 控制器接口与示例实现
├── config.py              # 小车配置加载模块
├── requirements.txt       # Python 依赖
├── assets/
│   └── track.png          # 默认赛道图片
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
speed      += (throttle × acceleration − longitudinal_friction × speed) × dt
turn_rate   = (speed / wheelbase) × tan(steer × max_steer_angle)
lateral_acc = |speed × turn_rate|
if lateral_acc > lateral_grip_limit:   # 高速弯道侧滑
    turn_rate 会按抓地极限衰减
heading    += turn_rate × dt
x, y       += speed × moving_heading × dt
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_speed` | 200 px/s | 最大速度 |
| `acceleration` | 160 px/s² | 加速度 |
| `longitudinal_friction` | 2.0 | 纵向摩擦（影响收油减速） |
| `lateral_grip` | 2.0 | 横向抓地（越大越不易侧滑） |
| `wheelbase` | 30 px | 轴距 |
| `max_steer_angle` | 35° | 最大转向角 |

**配置文件加载**：小车参数可以从 JSON 配置文件加载，方便切换不同的小车模型。

### `config.py` — 配置加载模块

支持从 JSON 文件加载小车配置参数。内置了 5 种预设配置：

| 配置文件 | 说明 | 特点 |
|---------|------|------|
| `configs/default.json` | 默认小车 | 平衡的性能，适合一般场景 |
| `configs/fast.json` | 快速小车 | 高速度和加速度，偏低摩擦/抓地 |
| `configs/stable.json` | 稳定小车 | 低速平稳，适合复杂赛道 |
| `configs/agile.json` | 灵活小车 | 小轴距，大转向角，灵活转弯 |
| `configs/heavy.json` | 重型小车 | 低速大惯性，适合模拟重载车辆 |

**自定义配置**：创建 JSON 文件，包含以下字段：

```json
{
  "name": "我的小车",
  "max_speed": 200.0,
  "acceleration": 160.0,
  "longitudinal_friction": 2.0,
  "lateral_grip": 2.0,
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
    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        """输入灰度图像 + 当前车速，返回 (throttle, steer)"""
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
    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        # camera_image: 灰度图 (120, 160), uint8
        # speed: 当前速度 (px/s)
        # 白色=赛道, 黑色=背景

        # ... 你的算法逻辑 ...

        throttle = 0.5   # 油门
        steer = 0.0       # 转向
        return throttle, steer
```

在 `main.py` 中注册后即可使用。

## 迁移到真机

控制器的 `control()` 方法依赖灰度 numpy 图像和当前速度输入，与模拟器主框架解耦。部署到真机时：

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
    speed = read_wheel_speed()  # 编码器/里程计估算速度
    throttle, steer = ctrl.control(gray, speed)
    motor_drive(throttle, steer)  # 驱动电机
```
