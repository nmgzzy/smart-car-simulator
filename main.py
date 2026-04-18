"""
main.py  —— 智能小车模拟系统入口

用法:
    python main.py                          # 使用默认赛道 + 键盘控制
    python main.py --controller linefollow  # 使用循线算法
    python main.py --track my_track.png     # 使用自定义赛道
"""

import argparse
import os

from track import Track
from car import Car
from sensor import CameraSensor
from controller import KeyboardController, LineFollowController
from simulator import Simulator
from config import CarConfig


def main():
    ap = argparse.ArgumentParser(description="智能小车模拟系统")
    ap.add_argument("--track", type=str, default="assets/track.png",
                    help="赛道图片路径")
    ap.add_argument("--controller", type=str, default="keyboard",
                    choices=["keyboard", "linefollow"],
                    help="初始控制器类型")
    ap.add_argument("--car", type=str, default="configs/default.json",
                    help="小车配置文件路径 (JSON 格式)")
    args = ap.parse_args()

    track_path = args.track

    if not os.path.exists(track_path):
        raise FileNotFoundError(
            f"赛道文件不存在: {track_path}\n"
            "请先使用 `python track_editor.py` 创建赛道，"
            "或通过 `--track` 指定已存在的赛道 PNG。"
        )

    # ---- 加载赛道 ----
    track = Track(track_path)
    print(f"赛道加载完成: {track.width}x{track.height}")
    print(f"起点: ({track.start_x:.0f}, {track.start_y:.0f}), "
          f"朝向: {__import__('math').degrees(track.start_heading):.1f}°")

    # ---- 加载小车配置 ----
    car_config = None
    if args.car:
        try:
            car_config = CarConfig.from_file(args.car)
        except FileNotFoundError as e:
            print(f"警告: {e}")
            print("使用默认配置")
    if car_config is None:
        car_config = CarConfig.get_default()
        print(f"使用默认小车配置: {car_config.name}")
    else:
        print(f"小车配置已加载: {car_config.name}")

    print(f"  最大速度: {car_config.max_speed} px/s")
    print(f"  加速度: {car_config.acceleration} px/s²")
    print(f"  纵向摩擦: {car_config.longitudinal_friction}")
    print(f"  横向抓地: {car_config.lateral_grip}")
    print(f"  轴距: {car_config.wheelbase} px")
    print(f"  最大转向角: {car_config.max_steer_angle}°")
    print(f"  车长: {car_config.car_length if car_config.car_length is not None else 'auto'} px")
    print(f"  车宽: {car_config.car_width if car_config.car_width is not None else 'auto'} px")
    print(f"  最大转向速度: {car_config.max_steer_speed}°/s")
    print(f"  最大滑移角: {car_config.max_slip_angle}°")
    print(f"  滑移建立速率: {car_config.slip_build_rate}")
    print(f"  滑移衰减速率: {car_config.slip_decay_rate}")
    print(f"  传感器分辨率: {car_config.sensor_resolution[0]}x{car_config.sensor_resolution[1]}")
    print(f"  传感器近端距离: {car_config.sensor_near_dist} px")
    print(f"  传感器远端距离: {car_config.sensor_far_dist} px")
    print(f"  传感器近端半宽: {car_config.sensor_near_half_width} px")
    print(f"  传感器远端半宽: {car_config.sensor_far_half_width} px")

    # ---- 创建小车 ----
    car = Car(track.start_x, track.start_y, track.start_heading, config=car_config)

    # ---- 创建传感器 ----
    sensor = CameraSensor(
        resolution=car_config.sensor_resolution,
        near_dist=car_config.sensor_near_dist,
        far_dist=car_config.sensor_far_dist,
        near_half_width=car_config.sensor_near_half_width,
        far_half_width=car_config.sensor_far_half_width,
    )

    # ---- 创建控制器列表 ----
    controllers = [KeyboardController(), LineFollowController()]
    if args.controller == "linefollow":
        controllers = controllers[::-1]  # 循线在前

    # ---- 启动模拟器 ----
    sim = Simulator(track, car, sensor, controllers)
    print("按 Tab 切换控制器 | Space 暂停 | R 重置 | Esc 退出")
    sim.run()


if __name__ == "__main__":
    main()
