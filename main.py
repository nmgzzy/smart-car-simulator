"""
main.py  —— 智能小车模拟系统入口

用法:
    python main.py                          # 使用默认赛道 + 键盘控制
    python main.py --generate --seed 123    # 先生成随机赛道再启动
    python main.py --controller linefollow  # 使用循线算法
    python main.py --track my_track.png     # 使用自定义赛道
"""

import argparse
import os

from track_generator import generate_track
from track import Track
from car import Car
from sensor import CameraSensor
from controller import KeyboardController, LineFollowController
from simulator import Simulator
from config import CarConfig


def main():
    ap = argparse.ArgumentParser(description="智能小车模拟系统")
    ap.add_argument("--track", type=str, default="assets/track_default.png",
                    help="赛道图片路径")
    ap.add_argument("--controller", type=str, default="keyboard",
                    choices=["keyboard", "linefollow"],
                    help="初始控制器类型")
    ap.add_argument("--car-config", type=str, default=None,
                    help="小车配置文件路径 (JSON 格式)")
    ap.add_argument("--generate", action="store_true",
                    help="启动前先生成随机赛道")
    ap.add_argument("--seed", type=int, default=None,
                    help="赛道生成随机种子")
    ap.add_argument("--elements", type=int, default=12,
                    help="赛道元素数量")
    ap.add_argument("--track-width", type=int, default=80,
                    help="赛道宽度 (像素)")
    args = ap.parse_args()

    track_path = args.track

    # ---- 生成赛道 ----
    if args.generate or not os.path.exists(track_path):
        import cv2, math
        print("正在生成随机赛道 ...")
        os.makedirs(os.path.dirname(track_path) or ".", exist_ok=True)
        img, info = generate_track(
            num_elements=args.elements,
            track_width=args.track_width,
            seed=args.seed,
        )
        cv2.imwrite(track_path, img)
        info_path = track_path.replace(".png", "_info.txt")
        with open(info_path, "w") as f:
            f.write(f"{info[0]},{info[1]},{info[2]}\n")
        print(f"赛道已生成: {track_path} "
              f"({img.shape[1]}x{img.shape[0]})")

    # ---- 加载赛道 ----
    track = Track(track_path)
    print(f"赛道加载完成: {track.width}x{track.height}")
    print(f"起点: ({track.start_x:.0f}, {track.start_y:.0f}), "
          f"朝向: {__import__('math').degrees(track.start_heading):.1f}°")

    # ---- 加载小车配置 ----
    car_config = None
    if args.car_config:
        try:
            car_config = CarConfig.from_file(args.car_config)
            print(f"小车配置已加载: {car_config.name}")
            print(f"  最大速度: {car_config.max_speed} px/s")
            print(f"  加速度: {car_config.acceleration} px/s²")
            print(f"  摩擦系数: {car_config.friction}")
            print(f"  轴距: {car_config.wheelbase} px")
            print(f"  最大转向角: {car_config.max_steer_angle}°")
        except FileNotFoundError as e:
            print(f"警告: {e}")
            print("使用默认配置")
    else:
        print("使用默认小车配置")

    # ---- 创建小车 ----
    car = Car(track.start_x, track.start_y, track.start_heading, config=car_config)

    # ---- 创建传感器 ----
    sensor = CameraSensor(resolution=(160, 120))

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
