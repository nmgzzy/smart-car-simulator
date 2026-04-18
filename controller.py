"""
controller.py  —— 控制器接口与示例实现

BaseController   : 抽象基类
KeyboardController : 键盘手动驾驶
LineFollowController : 基于图像处理的循线示例算法
"""

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pygame
except ImportError:
    pygame = None


class BaseController:
    """控制器抽象基类"""

    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        """
        根据摄像头图像和当前车速决策.

        Parameters
        ----------
        camera_image : np.ndarray (H, W), uint8, 灰度
        speed : float
            当前车速 (px/s)

        Returns
        -------
        (throttle, steer) : throttle ∈ [-1,1], steer ∈ [-1,1]
        """
        _ = (camera_image, speed)
        raise NotImplementedError


class KeyboardController(BaseController):
    """键盘手动控制 (方向键)"""

    def __init__(self):
        self._throttle = 0.0
        self._steer = 0.0

    def handle_keys(self, keys):
        """由 Simulator 每帧调用, 传入 pygame.key.get_pressed() 结果"""
        self._throttle = 0.0
        self._steer = 0.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self._throttle = 1.0
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self._throttle = -1.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self._steer = -1.0
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self._steer = 1.0

    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        return self._throttle, self._steer


class LineFollowController(BaseController):
    """
    循线示例算法

    通过对摄像头图像二值化, 检测白色赛道区域的重心偏移,
    以比例控制方式输出转向量.
    """

    def __init__(self, kp: float = 1.0,
                 target_speed: float = 120.0,
                 speed_kp: float = 0.02):
        self.kp = kp
        self.target_speed = target_speed
        self.speed_kp = speed_kp

    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        h, w = camera_image.shape[:2]

        # 取图像下半部分 (近处道路) 做检测
        roi = camera_image[h // 2:, :]
        _, binary = cv2.threshold(roi, 127, 255, cv2.THRESH_BINARY)

        white_cols = np.where(binary > 0)[1]
        if len(white_cols) == 0:
            # 看不到赛道: 低速直行 (或可改为原地转圈寻找)
            return 0.15, 0.0

        # 白色区域重心 x 坐标的归一化偏差 [-1, 1]
        cx = float(np.mean(white_cols))
        error = (cx - w / 2) / (w / 2)

        steer = self.kp * error
        steer = max(-1.0, min(1.0, steer))

        # 速度闭环: 弯道降低目标速度, 直道恢复
        speed_scale = 1.0 - 0.5 * abs(error)
        desired_speed = self.target_speed * max(0.35, speed_scale)
        throttle = (desired_speed - speed) * self.speed_kp
        throttle = max(-1.0, min(1.0, throttle))
        return throttle, steer
