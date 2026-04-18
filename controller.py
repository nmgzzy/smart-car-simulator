"""
controller.py  —— 控制器接口与示例实现

BaseController   : 抽象基类
KeyboardController : 键盘手动驾驶
LineFollowController : 基于图像处理的循线示例算法
"""

from typing import Optional

import numpy as np

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

    def get_debug_lines(self) -> list[str]:
        """返回需要显示在模拟器面板上的调试信息."""
        return []

    def get_tuning_help_lines(self) -> list[str]:
        """返回调参快捷键说明."""
        return []

    def handle_keydown(self, key: int, mods: int = 0) -> bool:
        """处理调参相关按键，返回是否已消费该按键."""
        _ = (key, mods)
        return False


class PIDController:
    """简单 PID 控制器，封装误差积分与微分状态."""

    def __init__(self,
                 kp: float = 0.0,
                 ki: float = 0.0,
                 kd: float = 0.0,
                 integral_limit: Optional[float] = None,
                 output_limit: Optional[float] = None):
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.integral_limit = integral_limit
        self.output_limit = output_limit
        self.integral = 0.0
        self.last_error = 0.0

    def reset(self):
        self.integral = 0.0
        self.last_error = 0.0

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0.0:
            derivative = 0.0
        else:
            self.integral += error * dt
            derivative = (error - self.last_error) / dt

        if self.integral_limit is not None:
            self.integral = float(np.clip(
                self.integral, -self.integral_limit, self.integral_limit
            ))

        output = (
            self.kp * error
            + self.ki * self.integral
            + self.kd * derivative
        )
        if self.output_limit is not None:
            output = float(np.clip(output, -self.output_limit, self.output_limit))

        self.last_error = error
        return float(output)

    def build_tunables(self,
                       prefix: str,
                       include: tuple = ("kp", "ki", "kd"),
                       steps: Optional[dict] = None,
                       minimum: float = 0.0) -> list[dict]:
        """生成可直接供 TunableControllerMixin 使用的 tunable 定义."""
        steps = steps or {}
        tunables = []
        for attr in include:
            tunables.append({
                "label": f"{prefix}_{attr}",
                "step": steps.get(attr, 0.05),
                "min": minimum,
                "getter": (lambda attr=attr: float(getattr(self, attr))),
                "setter": (lambda value, attr=attr: setattr(self, attr, float(value))),
            })
        return tunables


class TunableControllerMixin:
    """为控制器提供统一的热调参与调试展示能力."""

    TUNING_HELP_LINES = [
        "[ / ]: Select param",
        "- / =: Adjust value",
        "Shift: coarse step",
        "0: Reset params",
        "P: Print params",
    ]

    def _setup_tunables(self, tunables: list[dict]):
        self._tunables = list(tunables)
        self._selected_tunable = 0
        self._defaults = [
            float(self._get_tunable_value(item))
            for item in self._tunables
        ]

    def _get_tunable_label(self, item: dict) -> str:
        return item.get("label", item.get("name", "param"))

    def _get_tunable_value(self, item: dict) -> float:
        getter = item.get("getter")
        if getter is not None:
            return float(getter())
        return float(getattr(self, item["name"]))

    def _set_tunable_value(self, item: dict, value: float):
        setter = item.get("setter")
        if setter is not None:
            setter(float(value))
            return
        setattr(self, item["name"], float(value))

    def _current_tunable(self) -> dict:
        return self._tunables[self._selected_tunable]

    def _adjust_selected_param(self, direction: float, coarse: bool = False):
        cfg = self._current_tunable()
        step = cfg["step"] * (5.0 if coarse else 1.0)
        value = self._get_tunable_value(cfg) + direction * step
        value = max(cfg.get("min", -np.inf), value)
        value = min(cfg.get("max", np.inf), value)
        self._set_tunable_value(cfg, value)

    def _reset_tunables(self):
        for item, value in zip(self._tunables, self._defaults):
            self._set_tunable_value(item, value)
        self._selected_tunable = 0
        self._after_tunable_reset()

    def _after_tunable_reset(self):
        """子类可在恢复参数默认值后同步内部状态."""

    def _format_tuning_summary(self) -> str:
        return ", ".join(
            f"{self._get_tunable_label(item)}={self._get_tunable_value(item):.3f}"
            for item in self._tunables
        )

    def _get_extra_debug_lines(self) -> list[str]:
        return []

    def get_debug_lines(self) -> list[str]:
        lines = ["--- Controller Debug ---"]
        for idx, item in enumerate(self._tunables):
            prefix = ">" if idx == self._selected_tunable else " "
            label = self._get_tunable_label(item)
            value = self._get_tunable_value(item)
            lines.append(f"{prefix} {label}: {value:7.3f}")

        extra_lines = self._get_extra_debug_lines()
        if extra_lines:
            lines.extend([""])
            lines.extend(extra_lines)
        return lines

    def get_tuning_help_lines(self) -> list[str]:
        return list(self.TUNING_HELP_LINES)

    def handle_keydown(self, key: int, mods: int = 0) -> bool:
        if pygame is None:
            return False

        coarse = bool(mods & pygame.KMOD_SHIFT)
        if key == pygame.K_LEFTBRACKET:
            self._selected_tunable = (
                self._selected_tunable - 1
            ) % len(self._tunables)
            return True
        if key == pygame.K_RIGHTBRACKET:
            self._selected_tunable = (
                self._selected_tunable + 1
            ) % len(self._tunables)
            return True
        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._adjust_selected_param(-1.0, coarse=coarse)
            return True
        if key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self._adjust_selected_param(1.0, coarse=coarse)
            return True
        if key == pygame.K_0:
            self._reset_tunables()
            print(f"[{type(self).__name__}] reset: {self._format_tuning_summary()}")
            return True
        if key == pygame.K_p:
            print(f"[{type(self).__name__}] {self._format_tuning_summary()}")
            return True
        return False


class KeyboardController(BaseController):
    """键盘手动控制 (方向键)"""

    def __init__(self,
                 throttle_alpha: float = 0.2,
                 steer_alpha: float = 0.15):
        self._throttle = 0.0
        self._steer = 0.0
        self._target_throttle = 0.0
        self._target_steer = 0.0
        self._throttle_alpha = float(np.clip(throttle_alpha, 0.0, 1.0))
        self._steer_alpha = float(np.clip(steer_alpha, 0.0, 1.0))

    def handle_keys(self, keys):
        """由 Simulator 每帧调用, 传入 pygame.key.get_pressed() 结果"""
        self._target_throttle = 0.0
        self._target_steer = 0.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self._target_throttle = 1.0
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self._target_throttle = -1.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self._target_steer = -1.0
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self._target_steer = 1.0

        # 轻量低通滤波: 避免按键输入在 0 和 1 之间瞬间跳变过猛
        self._throttle += (
            self._target_throttle - self._throttle
        ) * self._throttle_alpha
        self._steer += (
            self._target_steer - self._steer
        ) * self._steer_alpha

    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        return self._throttle, self._steer


class LineFollowController(TunableControllerMixin, BaseController):
    """
    循线示例算法

    通过对摄像头图像二值化, 检测白色赛道区域的重心偏移,
    以比例控制方式输出转向量.
    """

    def __init__(self):
        self.max_speed = 200.0
        self.pid_dt = 0.01
        self.turn_pid = PIDController(
            kp=3.0,
            kd=0.3,
            output_limit=1.0,
        )
        self.speed_pid = PIDController(
            kp=1.0,
            ki=1.0,
            kd=1.0,
            integral_limit=self.max_speed,
        )

        self._setup_tunables([
            {"name": "max_speed", "step": 10.0, "min": 0.0},
            *self.turn_pid.build_tunables(
                "turn",
                include=("kp", "kd"),
                steps={"kp": 0.05, "kd": 0.02},
            ),
            *self.speed_pid.build_tunables(
                "speed",
                include=("kp", "kd", "ki"),
                steps={"kp": 0.10, "kd": 0.05, "ki": 0.02},
            ),
        ])

        self.line_found = False
        self.line_center_x = 0.0
        self.turn_error = 0.0
        self.target_speed = 0.0
        self.last_throttle = 0.0
        self.last_steer = 0.0

    def _after_tunable_reset(self):
        self.turn_pid.reset()
        self.speed_pid.reset()

    def _get_extra_debug_lines(self) -> list[str]:
        return [
            f"Line found: {'YES' if self.line_found else 'NO'}",
            f"Line center: {self.line_center_x:6.1f}",
            f"Turn error: {self.turn_error:6.3f}",
            f"Target spd: {self.target_speed:6.1f}",
            f"Speed int:  {self.speed_pid.integral:6.3f}",
            f"Throttle:   {self.last_throttle:6.3f}",
            f"Steer:      {self.last_steer:6.3f}",
        ]

    def control(self, camera_image: np.ndarray, speed: float) -> tuple:
        h, w = camera_image.shape[:2]
        roi = camera_image[h // 2:, :]
        track_mask = roi > 127

        if np.any(track_mask):
            xs = np.nonzero(track_mask)[1]
            center_x = float(np.mean(xs))
            raw_error = (center_x - (w / 2.0)) / max(w / 2.0, 1.0)
            self.line_found = True
            self.line_center_x = center_x
            self.turn_error = float(np.clip(raw_error, -1.0, 1.0))
        else:
            self.line_found = False
            self.line_center_x = w / 2.0
            # 丢线时保留上一帧转向趋势，避免立即回正后继续冲出赛道
            self.turn_error = float(np.clip(
                self.turn_pid.last_error, -1.0, 1.0
            ))

        steer = self.turn_pid.compute(self.turn_error, self.pid_dt)

        speed_scale = 1.0 - 0.7 * min(abs(self.turn_error), 1.0)
        if not self.line_found:
            speed_scale *= 0.35
        self.target_speed = self.max_speed * speed_scale

        speed_error = self.target_speed - speed
        self.speed_pid.integral_limit = self.max_speed
        throttle = self.speed_pid.compute(
            speed_error / max(self.max_speed, 1.0),
            self.pid_dt,
        )
        throttle = float(np.clip(throttle, -1.0, 1.0))

        self.last_throttle = throttle
        self.last_steer = steer
        return throttle, steer
