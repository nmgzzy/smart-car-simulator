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
                 longitudinal_friction: float = 2.0,
                 lateral_grip: float = 2.0,
                 wheelbase: float = 30.0,
                 max_steer_angle: float = 35.0,
                 config: Optional[CarConfig] = None):
        # 状态
        self.x = x
        self.y = y
        self.heading = heading          # 弧度, 0=右, π/2=下
        self.speed = 0.0                # 像素/秒
        self.steer_angle = 0.0          # 当前前轮转角
        self.slip_angle = 0.0           # 运动方向相对车头的滑移角
        self.surface_grip = 1.0         # 当前路面抓地估计 [0, 1]

        # 如果提供了配置对象，使用配置参数；否则使用传入的参数
        if config is not None:
            self.max_speed = config.max_speed
            self.acceleration = config.acceleration
            self.longitudinal_friction = config.longitudinal_friction
            self.lateral_grip = config.lateral_grip
            self.wheelbase = config.wheelbase
            self.max_steer_rad = math.radians(config.max_steer_angle)
            self.config_name = config.name
            self.car_length = (float(config.car_length) if config.car_length is not None
                               else max(self.wheelbase * 1.35, self.wheelbase + 8.0))
            self.car_width = (float(config.car_width) if config.car_width is not None
                              else max(self.wheelbase * 0.60, 14.0))
            self.max_steer_speed = math.radians(config.max_steer_speed)
            self.max_slip_angle = math.radians(config.max_slip_angle)
            self.slip_build_rate = config.slip_build_rate
            self.slip_decay_rate = config.slip_decay_rate
        else:
            self.max_speed = max_speed
            self.acceleration = acceleration
            self.longitudinal_friction = longitudinal_friction
            self.lateral_grip = lateral_grip
            self.wheelbase = wheelbase
            self.max_steer_rad = math.radians(max_steer_angle)
            self.config_name = "自定义"
            # 低侵入增强参数: 加入转向动态与滑移状态, 但保留原来的控制接口
            self.car_length = max(self.wheelbase * 1.35, self.wheelbase + 8.0)
            self.car_width = max(self.wheelbase * 0.60, 14.0)
            self.max_steer_speed = math.radians(180.0)
            self.max_slip_angle = math.radians(20.0)
            self.slip_build_rate = 7.0
            self.slip_decay_rate = 4.5

        # 保存初始状态用于重置
        self._init = (x, y, heading)

    def update(self, throttle: float, steer: float, dt: float,
               on_track: bool = True,
               surface_grip: Optional[float] = None):
        """
        更新一步物理状态.

        Parameters
        ----------
        throttle : float  -1 (刹车/倒车) ~ 1 (加速)
        steer    : float  -1 (左转) ~ 1 (右转)
        dt       : float  时间步长 (秒)
        on_track : bool   兼容旧接口的赛道布尔判定
        surface_grip : float, optional
            连续路面抓地估计 [0, 1]; 若未提供则退回到 on_track 布尔值
        """
        if dt <= 0.0:
            return

        throttle = max(-1.0, min(1.0, throttle))
        steer = max(-1.0, min(1.0, steer))
        self.surface_grip = max(
            0.0, min(1.0, surface_grip if surface_grip is not None
                     else (1.0 if on_track else 0.0))
        )

        # 抓地不是开关量, 离开赛道后仍保留少量可控性, 但加速/转向都会明显变差
        traction = 0.2 + 0.8 * self.surface_grip

        # 转向输入先经过舵机动态, 避免瞬时满打满回
        target_steer_angle = steer * self.max_steer_rad
        max_steer_step = self.max_steer_speed * dt
        steer_delta = target_steer_angle - self.steer_angle
        steer_delta = max(-max_steer_step, min(max_steer_step, steer_delta))
        self.steer_angle += steer_delta

        # 速度更新: 路面变差后, 驱动效率下降且滚阻增加
        drive_scale = 0.45 + 0.55 * traction
        long_fric = self.longitudinal_friction * (1.0 + 0.9 * (1.0 - traction))
        self.speed += (
            throttle * self.acceleration * drive_scale
            - long_fric * self.speed
        ) * dt
        self.speed = max(-self.max_speed * 0.3,
                         min(self.max_speed, self.speed))

        # 抓地较差时逐步限制可维持的速度, 避免跨出边线后突兀"钳住"
        if traction < 0.999:
            offtrack_limit = min(self.max_speed * (0.25 + 0.55 * traction), 120.0)
            if self.speed > offtrack_limit:
                self.speed = max(
                    offtrack_limit,
                    self.speed - self.acceleration * (1.2 + 0.8 * (1.0 - traction)) * dt
                )
            elif self.speed < -offtrack_limit * 0.5:
                self.speed = min(
                    -offtrack_limit * 0.5,
                    self.speed + self.acceleration * (1.2 + 0.8 * (1.0 - traction)) * dt
                )

        # 朝向更新: 抓地不足时不会立刻失控, 而是逐步积累成滑移角
        speed_abs = abs(self.speed)
        if abs(self.speed) > 0.1:
            ideal_turn_rate = (self.speed / self.wheelbase) * math.tan(self.steer_angle)

            # 横向加速度需求 a_lat = v * omega = v^2 / R
            requested_lat_acc = abs(self.speed * ideal_turn_rate)

            # lateral_grip 越大, 越不容易出现侧滑; 抓地下降会连续降低极限
            lateral_grip_limit = max(20.0, 220.0 * self.lateral_grip * traction)
            overload = max(0.0, requested_lat_acc - lateral_grip_limit)
            target_slip_ratio = min(1.0, overload / max(lateral_grip_limit, 1e-6))

            speed_ratio = min(speed_abs / max(self.max_speed, 1e-6), 1.0)
            target_slip_angle = (
                self.max_slip_angle
                * target_slip_ratio
                * (0.35 + 0.65 * speed_ratio)
            )
            target_slip_angle = math.copysign(target_slip_angle, self.steer_angle)

            # 滑移角带时间常数, 形成"有记忆"的甩尾/回正过程
            slip_rate = (self.slip_build_rate
                         if abs(target_slip_angle) > abs(self.slip_angle)
                         else self.slip_decay_rate)
            slip_blend = min(1.0, slip_rate * dt)
            self.slip_angle += (target_slip_angle - self.slip_angle) * slip_blend

            slip_ratio = min(1.0, abs(self.slip_angle) / self.max_slip_angle)
            grip_ratio = max(0.18, 1.0 - 0.82 * slip_ratio)
            turn_rate = ideal_turn_rate * grip_ratio
            self.heading += turn_rate * dt
        else:
            slip_blend = min(1.0, self.slip_decay_rate * dt)
            self.slip_angle += (0.0 - self.slip_angle) * slip_blend

        # 位置更新: 运动方向滞后于车头方向, 形成连续的侧滑感
        move_heading = self.heading - self.slip_angle
        if abs(self.slip_angle) > 1e-6:
            slip_ratio = min(1.0, abs(self.slip_angle) / self.max_slip_angle)
            self.speed *= max(0.0, 1.0 - slip_ratio * 0.9 * dt)

        self.x += self.speed * math.cos(move_heading) * dt
        self.y += self.speed * math.sin(move_heading) * dt

    def get_contact_points(self) -> list[tuple[float, float]]:
        """返回用于估算路面接触情况的多个采样点."""
        half_len = self.car_length * 0.5
        half_w = self.car_width * 0.5
        cos_h = math.cos(self.heading)
        sin_h = math.sin(self.heading)

        def to_world(dx: float, dy: float) -> tuple[float, float]:
            return (
                self.x + dx * cos_h - dy * sin_h,
                self.y + dx * sin_h + dy * cos_h,
            )

        sample_offsets = [
            (0.0, 0.0),
            (half_len * 0.70, 0.0),
            (-half_len * 0.70, 0.0),
            (0.0, half_w * 0.85),
            (0.0, -half_w * 0.85),
            (half_len * 0.55, half_w * 0.70),
            (half_len * 0.55, -half_w * 0.70),
            (-half_len * 0.55, half_w * 0.70),
            (-half_len * 0.55, -half_w * 0.70),
        ]
        return [to_world(dx, dy) for dx, dy in sample_offsets]

    def reset(self):
        """重置到初始状态"""
        self.x, self.y, self.heading = self._init
        self.speed = 0.0
        self.steer_angle = 0.0
        self.slip_angle = 0.0
        self.surface_grip = 1.0
