"""
sensor.py  —— 摄像头模拟

从赛道图片中按小车位置/朝向裁剪前方区域, 经透视变换生成模拟摄像头图像.
输出与真机摄像头格式一致 (灰度 numpy 数组), 便于算法迁移.
"""

import math
import numpy as np
import cv2


class CameraSensor:
    """模拟下视/前视摄像头"""

    def __init__(self,
                 resolution: tuple = (160, 120),
                 near_dist: float = 10.0,
                 far_dist: float = 200.0,
                 near_half_width: float = 50.0,
                 far_half_width: float = 120.0):
        """
        Parameters
        ----------
        resolution : (宽, 高)  输出图像分辨率
        near_dist  : 摄像头近端距离 (像素, 从车身算起)
        far_dist   : 摄像头远端距离
        near_half_width : 近端半宽度
        far_half_width  : 远端半宽度
        """
        self.out_w, self.out_h = resolution
        self.near_dist = near_dist
        self.far_dist = far_dist
        self.near_hw = near_half_width
        self.far_hw = far_half_width

        # 目标矩形 (固定)
        self._dst = np.array([
            [0,            self.out_h - 1],   # near-left  → 左下
            [self.out_w - 1, self.out_h - 1],   # near-right → 右下
            [self.out_w - 1, 0],                 # far-right  → 右上
            [0,            0],                   # far-left   → 左上
        ], dtype=np.float32)

    def capture(self, track_image: np.ndarray,
                car_x: float, car_y: float,
                car_heading: float) -> np.ndarray:
        """
        拍摄一帧摄像头图像.

        Parameters
        ----------
        track_image : 赛道灰度图 (H, W), uint8
        car_x, car_y : 小车位置 (像素坐标)
        car_heading  : 小车朝向 (弧度)

        Returns
        -------
        image : np.ndarray (out_h, out_w), uint8, 灰度
        """
        ch = math.cos(car_heading)
        sh = math.sin(car_heading)
        # 前方 (forward) 和 右方 (right) 单位向量
        # y-down 屏幕坐标: forward=(cos h, sin h), right=(-sin h, cos h)
        fwd = (ch, sh)
        rt = (-sh, ch)

        # 车辆局部坐标 → 世界 (赛道图) 坐标
        local = [
            (self.near_dist, -self.near_hw),   # near-left
            (self.near_dist,  self.near_hw),   # near-right
            (self.far_dist,   self.far_hw),    # far-right
            (self.far_dist,  -self.far_hw),    # far-left
        ]
        src = np.array([
            (car_x + fwd[0] * fd + rt[0] * rd,
             car_y + fwd[1] * fd + rt[1] * rd)
            for fd, rd in local
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(src, self._dst)
        out = cv2.warpPerspective(track_image, M,
                                  (self.out_w, self.out_h),
                                  flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT,
                                  borderValue=0)
        return out
