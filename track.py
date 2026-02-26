"""
track.py  —— 赛道加载与查询

加载赛道图片 (白色=赛道, 黑色=背景), 提供像素级查询.
"""

import numpy as np
import cv2
import os


class Track:
    """赛道管理器"""

    def __init__(self, image_path: str):
        self.image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if self.image is None:
            raise FileNotFoundError(f"无法加载赛道图片: {image_path}")

        self.height, self.width = self.image.shape
        self.start_x, self.start_y, self.start_heading = \
            self._load_start_info(image_path)

    # ---- 查询接口 ----

    def is_on_track(self, x: float, y: float) -> bool:
        """坐标 (x, y) 是否在赛道 (白色区域) 上"""
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < self.width and 0 <= iy < self.height:
            return self.image[iy, ix] > 127
        return False

    def get_region(self, x: float, y: float, half_size: int) -> np.ndarray:
        """获取以 (x,y) 为中心、边长 2*half_size 的方形区域 (越界部分填0)"""
        ix, iy = int(round(x)), int(round(y))
        x0 = ix - half_size
        y0 = iy - half_size
        size = 2 * half_size
        region = np.zeros((size, size), dtype=np.uint8)

        # 源图像裁剪范围
        sx0 = max(x0, 0)
        sy0 = max(y0, 0)
        sx1 = min(x0 + size, self.width)
        sy1 = min(y0 + size, self.height)

        # 目标区域偏移
        dx = sx0 - x0
        dy = sy0 - y0
        w = sx1 - sx0
        h = sy1 - sy0

        if w > 0 and h > 0:
            region[dy:dy + h, dx:dx + w] = self.image[sy0:sy1, sx0:sx1]
        return region

    # ---- 起点信息 ----

    def _load_start_info(self, image_path: str):
        info_path = image_path.replace(".png", "_info.txt")
        if os.path.exists(info_path):
            with open(info_path, "r") as f:
                parts = f.read().strip().split(",")
                return float(parts[0]), float(parts[1]), float(parts[2])
        return self._auto_find_start()

    def _auto_find_start(self):
        """在赛道图上自动寻找起点 (靠近图像中心的白色像素)"""
        white = np.where(self.image > 127)
        if len(white[0]) == 0:
            return float(self.width // 2), float(self.height // 2), 0.0

        cy, cx = self.height // 2, self.width // 2
        dists = (white[1].astype(float) - cx) ** 2 + \
                (white[0].astype(float) - cy) ** 2
        idx = int(np.argmin(dists))
        return float(white[1][idx]), float(white[0][idx]), 0.0
