"""
config.py  —— 小车配置文件加载模块

支持从 JSON 文件加载小车与传感器参数，方便切换不同配置
"""

import json
import os
from typing import Dict, Any


class CarConfig:
    """小车与传感器配置类"""

    # 默认参数
    DEFAULT_CONFIG = {
        "name": "默认小车",
        "max_speed": 200.0,        # 最大速度 (px/s)
        "acceleration": 160.0,     # 加速度 (px/s²)
        "longitudinal_friction": 2.0,  # 纵向阻力系数
        "lateral_grip": 2.0,           # 横向抓地系数
        "wheelbase": 30.0,         # 轴距 (px)
        "max_steer_angle": 35.0,   # 最大转向角 (度)
        "car_length": None,        # 车长 (px), None 表示按轴距推导
        "car_width": None,         # 车宽 (px), None 表示按轴距推导
        "max_steer_speed": 180.0,  # 最大转向速度 (度/秒)
        "max_slip_angle": 20.0,    # 最大滑移角 (度)
        "slip_build_rate": 7.0,    # 滑移建立速率
        "slip_decay_rate": 4.5,    # 滑移衰减速率
        "sensor_resolution": [160, 120],   # 传感器输出分辨率 [宽, 高]
        "sensor_near_dist": 10.0,          # 传感器近端距离
        "sensor_far_dist": 200.0,          # 传感器远端距离
        "sensor_near_half_width": 23.0,    # 传感器近端半宽
        "sensor_far_half_width": 346.0,    # 传感器远端半宽
    }

    def __init__(self, config_dict: Dict[str, Any] = None):
        """
        初始化配置

        Parameters
        ----------
        config_dict : dict, optional
            配置字典，如果为 None 则使用默认配置
        """
        cfg = self.DEFAULT_CONFIG.copy()
        if config_dict:
            cfg.update(config_dict)

        self.name = cfg["name"]
        self.max_speed = float(cfg["max_speed"])
        self.acceleration = float(cfg["acceleration"])
        self.longitudinal_friction = float(cfg["longitudinal_friction"])
        self.lateral_grip = float(cfg["lateral_grip"])
        self.wheelbase = float(cfg["wheelbase"])
        self.max_steer_angle = float(cfg["max_steer_angle"])
        self.car_length = (None if cfg["car_length"] is None
                           else float(cfg["car_length"]))
        self.car_width = (None if cfg["car_width"] is None
                          else float(cfg["car_width"]))
        self.max_steer_speed = float(cfg["max_steer_speed"])
        self.max_slip_angle = float(cfg["max_slip_angle"])
        self.slip_build_rate = float(cfg["slip_build_rate"])
        self.slip_decay_rate = float(cfg["slip_decay_rate"])
        sensor_resolution = cfg["sensor_resolution"]
        if len(sensor_resolution) != 2:
            raise ValueError("sensor_resolution 必须是 [宽, 高]")
        self.sensor_resolution = (
            int(sensor_resolution[0]),
            int(sensor_resolution[1]),
        )
        self.sensor_near_dist = float(cfg["sensor_near_dist"])
        self.sensor_far_dist = float(cfg["sensor_far_dist"])
        self.sensor_near_half_width = float(cfg["sensor_near_half_width"])
        self.sensor_far_half_width = float(cfg["sensor_far_half_width"])

    @classmethod
    def from_file(cls, filepath: str) -> "CarConfig":
        """
        从 JSON 文件加载配置

        Parameters
        ----------
        filepath : str
            配置文件路径

        Returns
        -------
        CarConfig
            配置对象
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"配置文件不存在: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            config_dict = json.load(f)

        return cls(config_dict)

    @classmethod
    def get_default(cls) -> "CarConfig":
        """获取默认配置"""
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "max_speed": self.max_speed,
            "acceleration": self.acceleration,
            "longitudinal_friction": self.longitudinal_friction,
            "lateral_grip": self.lateral_grip,
            "wheelbase": self.wheelbase,
            "max_steer_angle": self.max_steer_angle,
            "car_length": self.car_length,
            "car_width": self.car_width,
            "max_steer_speed": self.max_steer_speed,
            "max_slip_angle": self.max_slip_angle,
            "slip_build_rate": self.slip_build_rate,
            "slip_decay_rate": self.slip_decay_rate,
            "sensor_resolution": list(self.sensor_resolution),
            "sensor_near_dist": self.sensor_near_dist,
            "sensor_far_dist": self.sensor_far_dist,
            "sensor_near_half_width": self.sensor_near_half_width,
            "sensor_far_half_width": self.sensor_far_half_width,
        }

    def save(self, filepath: str):
        """
        保存配置到文件

        Parameters
        ----------
        filepath : str
            保存路径
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def __str__(self) -> str:
        return (f"CarConfig({self.name}): "
                f"max_speed={self.max_speed}, "
                f"acceleration={self.acceleration}, "
                f"longitudinal_friction={self.longitudinal_friction}, "
                f"lateral_grip={self.lateral_grip}, "
                f"wheelbase={self.wheelbase}, "
                f"max_steer_angle={self.max_steer_angle}, "
                f"car_length={self.car_length}, "
                f"car_width={self.car_width}, "
                f"max_steer_speed={self.max_steer_speed}, "
                f"max_slip_angle={self.max_slip_angle}, "
                f"slip_build_rate={self.slip_build_rate}, "
                f"slip_decay_rate={self.slip_decay_rate}, "
                f"sensor_resolution={self.sensor_resolution}, "
                f"sensor_near_dist={self.sensor_near_dist}, "
                f"sensor_far_dist={self.sensor_far_dist}, "
                f"sensor_near_half_width={self.sensor_near_half_width}, "
                f"sensor_far_half_width={self.sensor_far_half_width})")
