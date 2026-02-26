"""
car.py  —— 小车物理模型 (简化自行车模型)

状态:  位置 (x, y), 朝向 heading, 速度 speed
控制:  throttle (-1~1), steer (-1~1)
"""

import math
from typing import Optional
from config import CarConfig


class Car:
    """2D 小车 — 简化自行车运动模型"""

    def __init__(self, x: float, y: float, heading: float,
                 max_speed: float = 200.0,
                 acceleration: float = 160.0,
                 friction: float = 2.0,
                 wheelbase: float = 30.0,
                 max_steer_angle: float = 35.0,
                 config: Optional[CarConfig] = None):
        # 状态
        self.x = x
        self.y = y
        self.heading = heading          # 弧度, 0=右, π/2=下
        self.speed = 0.0                # 像素/秒

        # 如果提供了配置对象，使用配置参数；否则使用传入的参数
        if config is not None:
            self.max_speed = config.max_speed
            self.acceleration = config.acceleration
            self.friction = config.friction
            self.wheelbase = config.wheelbase
            self.max_steer_rad = math.radians(config.max_steer_angle)
            self.config_name = config.name
        else:
            self.max_speed = max_speed
            self.acceleration = acceleration
            self.friction = friction
            self.wheelbase = wheelbase
            self.max_steer_rad = math.radians(max_steer_angle)
            self.config_name = "自定义"

        # 保存初始状态用于重置
        self._init = (x, y, heading)

    def update(self, throttle: float, steer: float, dt: float,
               on_track: bool = True):
        """
        更新一步物理状态.

        Parameters
        ----------
        throttle : float  -1 (刹车/倒车) ~ 1 (加速)
        steer    : float  -1 (左转) ~ 1 (右转)
        dt       : float  时间步长 (秒)
        on_track : bool   是否在赛道上 (离开赛道加大摩擦)
        """
        throttle = max(-1.0, min(1.0, throttle))
        steer = max(-1.0, min(1.0, steer))

        # 摩擦系数: 离开赛道时阻力翻倍
        fric = self.friction * (1.0 if on_track else 3.0)

        # 速度更新
        self.speed += (throttle * self.acceleration - fric * self.speed) * dt
        self.speed = max(-self.max_speed * 0.3,
                         min(self.max_speed, self.speed))

        # 朝向更新 (自行车模型)
        steer_angle = steer * self.max_steer_rad
        if abs(self.speed) > 0.1:
            turn_rate = (self.speed / self.wheelbase) * math.tan(steer_angle)
            self.heading += turn_rate * dt

        # 位置更新
        self.x += self.speed * math.cos(self.heading) * dt
        self.y += self.speed * math.sin(self.heading) * dt

    def reset(self):
        """重置到初始状态"""
        self.x, self.y, self.heading = self._init
        self.speed = 0.0
