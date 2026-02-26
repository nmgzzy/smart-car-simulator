"""
config.py  —— 小车配置文件加载模块

支持从 JSON 文件加载小车参数，方便切换不同的小车模型
"""

import json
import os
from typing import Dict, Any


class CarConfig:
    """小车配置类"""

    # 默认参数
    DEFAULT_CONFIG = {
        "name": "默认小车",
        "max_speed": 200.0,        # 最大速度 (px/s)
        "acceleration": 160.0,     # 加速度 (px/s²)
        "friction": 2.0,           # 摩擦系数
        "wheelbase": 30.0,         # 轴距 (px)
        "max_steer_angle": 35.0,   # 最大转向角 (度)
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
        self.friction = float(cfg["friction"])
        self.wheelbase = float(cfg["wheelbase"])
        self.max_steer_angle = float(cfg["max_steer_angle"])

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
            "friction": self.friction,
            "wheelbase": self.wheelbase,
            "max_steer_angle": self.max_steer_angle,
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
                f"friction={self.friction}, "
                f"wheelbase={self.wheelbase}, "
                f"max_steer_angle={self.max_steer_angle}")
