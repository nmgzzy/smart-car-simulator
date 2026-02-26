"""
track_generator.py  —— 随机赛道生成器 v2

生成策略:
  1. 在变形椭圆上生成控制点, 形成基础闭合环路
  2. 用 Catmull-Rom 样条插值, 得到平滑中心线 (自动包含直线与大/中/小弯道)
  3. 在相邻控制点间插入侧移点, 形成 S 弯道
  4. 在中心线上叠加十字路口 (垂直穿越道路)
  5. 在中心线上叠加环岛 (圆环 + 臂)

赛道元素: 直线、大/中/小弯道、连续S弯道、十字路口、环岛
白色(255) = 赛道, 黑色(0) = 背景

用法:
    python track_generator.py --output assets/track_default.png --seed 42
"""

import numpy as np
import cv2
import math
import random
import argparse
import os


# ================================================================
#  基础几何工具
# ================================================================

def _lerp(x0, y0, x1, y1, step=3.0):
    """直线插值"""
    d = math.hypot(x1 - x0, y1 - y0)
    n = max(int(d / step), 2)
    return [(x0 + (x1 - x0) * i / n,
             y0 + (y1 - y0) * i / n) for i in range(n + 1)]


def _arc(cx, cy, r, a0, sweep, step=3.0):
    """圆弧插值"""
    arc_len = abs(r * sweep)
    n = max(int(arc_len / step), 8)
    return [(cx + r * math.cos(a0 + sweep * i / n),
             cy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


# ================================================================
#  Catmull-Rom 闭合样条
# ================================================================

def _cr_seg(P0, P1, P2, P3, n=50):
    """P1→P2 段的 Catmull-Rom 插值"""
    t = np.linspace(0, 1, n, endpoint=False).reshape(-1, 1)
    t2, t3 = t * t, t * t * t
    P = np.array([P0, P1, P2, P3], dtype=float)
    C = 0.5 * np.array([[-1,  3, -3,  1],
                         [ 2, -5,  4, -1],
                         [-1,  0,  1,  0],
                         [ 0,  2,  0,  0]], dtype=float)
    A = C @ P
    pts = t3 * A[0] + t2 * A[1] + t * A[2] + A[3]
    return [tuple(row) for row in pts]


def _closed_spline(waypoints, sps=60):
    """对闭合控制点做 Catmull-Rom 样条插值"""
    N = len(waypoints)
    pts = []
    for i in range(N):
        pts.extend(_cr_seg(
            waypoints[(i - 1) % N], waypoints[i],
            waypoints[(i + 1) % N], waypoints[(i + 2) % N], sps))
    return pts


# ================================================================
#  Step 1 — 基础控制点 (变形椭圆)
# ================================================================

def _make_waypoints(n, rx, ry, jitter=0.30):
    """
    在椭圆上均匀分布 n 个控制点, 带半径抖动.
    角度间距有小幅随机偏移但保持顺序, 防止自交叉.
    """
    gap = 2 * math.pi / n
    max_aj = gap * 0.30        # 角度抖动 ≤ 间隔的 30%
    wps = []
    for i in range(n):
        a = gap * i + random.uniform(-max_aj, max_aj)
        rf = 1.0 + random.uniform(-jitter, jitter)
        wps.append((rx * rf * math.cos(a),
                     ry * rf * math.sin(a)))
    return wps


# ================================================================
#  Step 2 — 插入 S 弯道
# ================================================================

def _insert_s_curves(wps, count):
    """
    在随机选取的相邻控制点之间插入一个侧移控制点,
    Catmull-Rom 样条经过此点后自然形成 S 弯.
    """
    n = len(wps)
    count = min(count, n // 3)
    if count <= 0:
        return wps

    # 选不相邻的位置
    candidates = list(range(n))
    random.shuffle(candidates)
    chosen = []
    used = set()
    for c in candidates:
        if c not in used and (c - 1) % n not in used and (c + 1) % n not in used:
            chosen.append(c)
            used.update([c, (c - 1) % n, (c + 1) % n])
            if len(chosen) >= count:
                break

    # 从后往前插入, 防止下标移位
    for i in sorted(chosen, reverse=True):
        p1 = np.array(wps[i])
        p2 = np.array(wps[(i + 1) % len(wps)])
        mid = (p1 + p2) / 2
        d = p2 - p1
        seg_len = np.linalg.norm(d)
        if seg_len < 30:
            continue
        perp = np.array([-d[1], d[0]]) / seg_len
        offset = random.choice([-1, 1]) * random.uniform(0.30, 0.50) * seg_len
        wobble = tuple(mid + perp * offset)
        wps.insert(i + 1, wobble)

    return wps


# ================================================================
#  Step 3 — 十字路口
# ================================================================

def _crossroad_extras(centerline, count, arm_len):
    """在中心线上均匀分散地放置十字路口 (垂直穿越道路)"""
    n = len(centerline)
    extras = []
    spacing = n // (count + 1)

    for k in range(count):
        idx = spacing * (k + 1) + random.randint(-spacing // 6, spacing // 6)
        idx = idx % n
        px, py = centerline[idx]

        # 切线方向
        i1 = (idx - 20) % n
        i2 = (idx + 20) % n
        dx = centerline[i2][0] - centerline[i1][0]
        dy = centerline[i2][1] - centerline[i1][1]
        l = math.hypot(dx, dy)
        if l < 1:
            continue
        nx, ny = -dy / l, dx / l      # 法线方向

        a1 = (px + nx * arm_len, py + ny * arm_len)
        a2 = (px - nx * arm_len, py - ny * arm_len)
        extras.append(_lerp(a1[0], a1[1], a2[0], a2[1]))

    return extras


# ================================================================
#  Step 4 — 环岛
# ================================================================

def _roundabout_extras(centerline, count, ring_r, arm_len):
    """
    在中心线上叠加环岛.
    圆环中心偏置到路径一侧, 与主路在切点处自然衔接.
    额外绘制两条臂, 形成四路环岛.
    """
    n = len(centerline)
    extras = []
    spacing = n // (count + 1)

    for k in range(count):
        idx = spacing * (k + 1) + random.randint(-spacing // 6, spacing // 6)
        idx = idx % n
        px, py = centerline[idx]

        # 切线
        i1 = (idx - 25) % n
        i2 = (idx + 25) % n
        dx = centerline[i2][0] - centerline[i1][0]
        dy = centerline[i2][1] - centerline[i1][1]
        heading = math.atan2(dy, dx)

        # 圆心偏置到路径一侧 (距离 = ring_r, 使主路与圆环相切)
        side = random.choice([-1, 1])
        cx = px + ring_r * math.cos(heading + side * math.pi / 2)
        cy = py + ring_r * math.sin(heading + side * math.pi / 2)

        # 完整圆环
        ring = _arc(cx, cy, ring_r, 0, 2 * math.pi, step=2.0)
        ring.append(ring[0])          # 确保闭合
        extras.append(ring)

        # 两条臂 (与主路垂直方向, 从圆环外侧延伸)
        entry_a = math.atan2(py - cy, px - cx)
        for off in [math.pi / 2, -math.pi / 2]:
            aa = entry_a + off
            ax = cx + ring_r * math.cos(aa)
            ay = cy + ring_r * math.sin(aa)
            bx = ax + arm_len * math.cos(aa)
            by = ay + arm_len * math.sin(aa)
            extras.append(_lerp(ax, ay, bx, by))

    return extras


# ================================================================
#  渲染
# ================================================================

def _render(centerline, extras, width, margin=200):
    """将中心线 (闭合) + 额外道路渲染为灰度图"""
    all_xy = list(centerline)
    for ex in extras:
        all_xy.extend(ex)

    arr = np.array(all_xy, dtype=np.float64)
    lo = arr.min(axis=0) - margin
    hi = arr.max(axis=0) + margin
    W = int(hi[0] - lo[0])
    H = int(hi[1] - lo[1])
    img = np.zeros((H, W), dtype=np.uint8)

    # 主路 (闭合)
    cl = np.array([(int(x - lo[0]), int(y - lo[1]))
                    for x, y in centerline], dtype=np.int32)
    cv2.polylines(img, [cl], isClosed=True,
                  color=255, thickness=width, lineType=cv2.LINE_AA)

    # 额外道路 (十字路口臂 / 环岛圆环与臂)
    for ex in extras:
        if len(ex) >= 2:
            pts = np.array([(int(x - lo[0]), int(y - lo[1]))
                            for x, y in ex], dtype=np.int32)
            cv2.polylines(img, [pts], isClosed=False,
                          color=255, thickness=width, lineType=cv2.LINE_AA)

    return img, (lo[0], lo[1])


# ================================================================
#  主生成入口
# ================================================================

def generate_track(num_elements=12, track_width=80, seed=None, max_retries=5):
    """
    生成随机闭合赛道.

    Parameters
    ----------
    num_elements : 控制赛道复杂度 (控制点 + 特殊元素总数)
    track_width  : 赛道宽度 (像素)
    seed         : 随机种子
    max_retries  : 最大重试次数

    Returns
    -------
    img        : np.ndarray (H, W), uint8
    start_info : (start_x, start_y, start_heading) 图片坐标
    """
    for attempt in range(max_retries):
        s = (seed if seed is not None else random.randint(0, 999999)) + attempt
        random.seed(s)
        np.random.seed(s % (2 ** 31))

        # ---- 参数 ----
        rx = random.randint(500, 700)
        ry = random.randint(380, 580)
        n_base = max(6, num_elements - 3)     # 基础控制点数
        s_count = random.randint(1, 3)        # S弯数
        cross_count = random.randint(1, 2)    # 十字路口数
        ra_count = random.randint(1, 2)       # 环岛数

        # ---- 控制点 ----
        wps = _make_waypoints(n_base, rx, ry, jitter=0.30)
        wps = _insert_s_curves(wps, s_count)

        # ---- 平滑闭合中心线 ----
        centerline = _closed_spline(wps, sps=80)
        if len(centerline) < 100:
            continue

        # ---- 特殊元素 ----
        extras = []
        extras.extend(_crossroad_extras(
            centerline, cross_count, arm_len=track_width * 1.8))
        extras.extend(_roundabout_extras(
            centerline, ra_count,
            ring_r=random.randint(100, 140),
            arm_len=90))

        # ---- 渲染 ----
        img, lo = _render(centerline, extras, track_width)
        if img.shape[0] < 100 or img.shape[1] < 100:
            continue

        # ---- 起点 (中心线首点) ----
        sx = centerline[0][0] - lo[0]
        sy = centerline[0][1] - lo[1]
        dx = centerline[1][0] - centerline[0][0]
        dy = centerline[1][1] - centerline[0][1]
        sh = math.atan2(dy, dx)

        return img, (sx, sy, sh)

    # 所有重试失败 → 椭圆保底
    W, H = 1200, 900
    img = np.zeros((H, W), dtype=np.uint8)
    cv2.ellipse(img, (W // 2, H // 2), (400, 280),
                0, 0, 360, 255, track_width, cv2.LINE_AA)
    return img, (float(W // 2 + 400), float(H // 2), math.pi / 2)


# ================================================================
#  CLI
# ================================================================

def main():
    ap = argparse.ArgumentParser(description="随机赛道生成器")
    ap.add_argument("--output", default="assets/track_default.png",
                    help="输出赛道图片路径")
    ap.add_argument("--width", type=int, default=80,
                    help="赛道宽度 (像素)")
    ap.add_argument("--seed", type=int, default=None,
                    help="随机种子")
    ap.add_argument("--elements", type=int, default=12,
                    help="赛道元素数量")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    print(f"正在生成赛道 (elements={args.elements}, "
          f"width={args.width}, seed={args.seed}) ...")
    img, info = generate_track(args.elements, args.width, args.seed)

    cv2.imwrite(args.output, img)
    print(f"已保存: {args.output}  ({img.shape[1]}x{img.shape[0]})")
    print(f"起点: ({info[0]:.0f}, {info[1]:.0f})  "
          f"朝向: {math.degrees(info[2]):.1f}°")

    # 保存起点信息
    info_path = args.output.replace(".png", "_info.txt")
    with open(info_path, "w") as f:
        f.write(f"{info[0]},{info[1]},{info[2]}\n")
    print(f"起点信息: {info_path}")


if __name__ == "__main__":
    main()
