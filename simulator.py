"""
simulator.py  —— 主仿真循环与 Pygame 可视化

左侧: 赛道俯视图 + 小车位置
右上: 摄像头实时画面
右下: 状态信息
支持按键: Space=暂停, R=重置, Tab=切换控制器
"""

import math
import numpy as np
import cv2
import pygame

from track import Track
from car import Car
from sensor import CameraSensor
from controller import BaseController, KeyboardController


# ---- 颜色常量 ----
COLOR_BG      = (30, 30, 30)
COLOR_TEXT    = (220, 220, 220)
COLOR_CAR     = (255, 60, 60)
COLOR_CAR_DIR = (255, 200, 60)
COLOR_PANEL   = (40, 40, 50)
COLOR_GREEN   = (60, 220, 100)
COLOR_YELLOW  = (240, 200, 40)
COLOR_RED     = (240, 60, 60)


class Simulator:
    """小车模拟器主类"""

    FPS = 60
    PANEL_W = 300           # 右侧面板宽度
    CAM_DISPLAY_H = 200     # 摄像头画面显示高度

    def __init__(self, track: Track, car: Car,
                 sensor: CameraSensor,
                 controllers: list,
                 window_size: tuple = None):
        """
        Parameters
        ----------
        track       : Track 对象
        car         : Car 对象
        sensor      : CameraSensor 对象
        controllers : 控制器列表 (Tab 键切换)
        window_size : (宽, 高), None 则自动计算
        """
        self.track = track
        self.car = car
        self.sensor = sensor
        self.controllers = controllers
        self.ctrl_idx = 0
        self.paused = False

        # 计算窗口尺寸
        if window_size is None:
            # 赛道区域高度限制 800, 宽度按比例
            max_h = 800
            scale = max_h / track.height
            tw = int(track.width * scale)
            self.win_w = tw + self.PANEL_W
            self.win_h = max_h
        else:
            self.win_w, self.win_h = window_size

        # 赛道显示区域
        self.track_area_w = self.win_w - self.PANEL_W
        self.track_area_h = self.win_h
        self.scale = min(self.track_area_w / track.width,
                         self.track_area_h / track.height)
        # 居中偏移
        self.offset_x = (self.track_area_w - track.width * self.scale) / 2
        self.offset_y = (self.track_area_h - track.height * self.scale) / 2

        # 摄像头显示区域
        cam_ratio = sensor.out_w / sensor.out_h
        self.cam_disp_w = self.PANEL_W - 20
        self.cam_disp_h = int(self.cam_disp_w / cam_ratio)

    @property
    def controller(self) -> BaseController:
        return self.controllers[self.ctrl_idx]

    def _to_screen(self, wx, wy):
        """世界坐标 → 屏幕坐标"""
        sx = int(wx * self.scale + self.offset_x)
        sy = int(wy * self.scale + self.offset_y)
        return sx, sy

    # ---- Pygame 初始化 ----

    def _init_pygame(self):
        pygame.init()
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        pygame.display.set_caption("智能小车模拟器")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)
        self.font_big = pygame.font.SysFont("consolas", 20, bold=True)

        # 预渲染赛道背景
        self._build_track_surface()

        # 小车图标 (三角形)
        self.car_size = max(8, int(30 * self.scale))
        self._build_car_surface()

    def _build_track_surface(self):
        """将赛道灰度图转为 Pygame Surface 并缩放"""
        rgb = cv2.cvtColor(self.track.image, cv2.COLOR_GRAY2RGB)
        # 赛道白色改为浅蓝白, 背景改为深灰, 更好看
        mask = self.track.image > 127
        rgb[mask] = [240, 245, 250]
        rgb[~mask] = [35, 35, 40]

        surf = pygame.surfarray.make_surface(
            np.transpose(rgb, (1, 0, 2)))
        tw = int(self.track.width * self.scale)
        th = int(self.track.height * self.scale)
        self.track_surface = pygame.transform.scale(surf, (tw, th))

    def _build_car_surface(self):
        """创建小车三角形图标"""
        s = self.car_size
        self.car_surf = pygame.Surface((s, s), pygame.SRCALPHA)
        pts = [(s, s // 2), (0, 0), (0, s - 1)]
        pygame.draw.polygon(self.car_surf, COLOR_CAR, pts)

    # ---- 渲染 ----

    def _render(self, camera_image: np.ndarray):
        self.screen.fill(COLOR_BG)

        # 1) 赛道
        self.screen.blit(self.track_surface,
                         (int(self.offset_x), int(self.offset_y)))

        # 2) 小车
        sx, sy = self._to_screen(self.car.x, self.car.y)
        angle_deg = -math.degrees(self.car.heading)
        rotated = pygame.transform.rotate(self.car_surf, angle_deg)
        rect = rotated.get_rect(center=(sx, sy))
        self.screen.blit(rotated, rect)

        # 方向指示线
        dx = int(20 * self.scale * math.cos(self.car.heading))
        dy = int(20 * self.scale * math.sin(self.car.heading))
        pygame.draw.line(self.screen, COLOR_CAR_DIR,
                         (sx, sy), (sx + dx, sy + dy), 2)

        # 3) 右侧面板背景
        panel_x = self.track_area_w
        pygame.draw.rect(self.screen, COLOR_PANEL,
                         (panel_x, 0, self.PANEL_W, self.win_h))

        # 4) 摄像头画面
        if camera_image is not None:
            cam_rgb = cv2.cvtColor(camera_image, cv2.COLOR_GRAY2RGB)
            cam_surf = pygame.surfarray.make_surface(
                np.transpose(cam_rgb, (1, 0, 2)))
            cam_surf = pygame.transform.scale(
                cam_surf, (self.cam_disp_w, self.cam_disp_h))
            cam_x = panel_x + 10
            cam_y = 10
            self.screen.blit(cam_surf, (cam_x, cam_y))
            pygame.draw.rect(self.screen, COLOR_TEXT,
                             (cam_x, cam_y,
                              self.cam_disp_w, self.cam_disp_h), 1)
            # 标题
            lbl = self.font.render("Camera View", True, COLOR_TEXT)
            self.screen.blit(lbl, (cam_x, cam_y + self.cam_disp_h + 4))

        # 5) 状态信息
        info_y = self.cam_disp_h + 50
        self._draw_info(panel_x + 10, info_y)

        pygame.display.flip()

    def _draw_info(self, x, y):
        """绘制状态文本"""
        ctrl_name = type(self.controller).__name__
        on = self.track.is_on_track(self.car.x, self.car.y)
        lines = [
            f"Car: {self.car.config_name}",
            f"Controller: {ctrl_name}",
            "",
            f"Speed: {self.car.speed:6.1f} px/s",
            f"Heading: {math.degrees(self.car.heading):6.1f} deg",
            f"Pos: ({self.car.x:.0f}, {self.car.y:.0f})",
            f"On track: {'YES' if on else 'NO'}",
            "",
            "--- Controls ---",
            "Arrow/WASD: Drive",
            "Space: Pause",
            "R: Reset",
            "Tab: Switch ctrl",
            "Esc: Quit",
        ]
        if self.paused:
            lines.insert(0, "** PAUSED **")

        for i, line in enumerate(lines):
            color = COLOR_YELLOW if "PAUSED" in line else COLOR_TEXT
            if "NO" in line and "On track" in line:
                color = COLOR_RED
            surf = self.font.render(line, True, color)
            self.screen.blit(surf, (x, y + i * 22))

    # ---- 主循环 ----

    def run(self):
        """启动模拟器"""
        self._init_pygame()
        running = True
        camera_image = None

        while running:
            dt = self.clock.tick(self.FPS) / 1000.0
            dt = min(dt, 0.05)  # 防止帧间隔过大

            # 事件处理
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r:
                        self.car.reset()
                    elif event.key == pygame.K_TAB:
                        self.ctrl_idx = (self.ctrl_idx + 1) % \
                            len(self.controllers)
                        print(f"切换控制器: "
                              f"{type(self.controller).__name__}")

            if not self.paused:
                # 键盘输入
                keys = pygame.key.get_pressed()
                if isinstance(self.controller, KeyboardController):
                    self.controller.handle_keys(keys)

                # 摄像头采集
                camera_image = self.sensor.capture(
                    self.track.image,
                    self.car.x, self.car.y, self.car.heading)

                # 控制决策
                throttle, steer = self.controller.control(camera_image)

                # 物理更新
                on_track = self.track.is_on_track(self.car.x, self.car.y)
                self.car.update(throttle, steer, dt, on_track)

            # 渲染
            self._render(camera_image)

        pygame.quit()
