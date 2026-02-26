"""
track_editor.py —— 赛道指令编辑器

通过文本指令逐步构建赛道, Pygame 实时预览, 支持保存.

指令集
------
  F<距离>                前进直线          F200
  R<半径>-<角度>         右转弯道          R100-90
  L<半径>-<角度>         左转弯道          L80-45
  S<半径>-<角度>-<次数>  S弯道(先左后右)   S60-45-4
  X<臂长>               十字路口          X120
  O<半径>               环岛(默认270°)    O100
  O<半径>-<角度>         环岛(自定义弧度)  O100-180
  FINISH                闭合回起点

快捷键
------
  Enter       添加指令
  Ctrl+Z      撤销上一条
  Ctrl+S      保存赛道 (PNG + 起点信息 + 指令文件)
  Ctrl+F      自动适配视图
  Ctrl+E      加载示例指令
  鼠标拖拽    平移视图
  滚轮        缩放视图
  Esc         退出

用法
----
  python track_editor.py
  python track_editor.py --output assets/my_track.png
  python track_editor.py --load assets/my_track_instr.txt
"""

import numpy as np
import cv2
import math
import re
import os
import sys
import argparse

try:
    import pygame
except ImportError:
    print("需要 pygame: pip install pygame")
    sys.exit(1)


# ================================================================
#  示例指令集
# ================================================================

EXAMPLE_INSTRUCTIONS = [
    "F200",
    "R100-90",
    "F300",
    "L120-60",
    "F200",
    "S70-40-4",
    "F150",
    "X130",
    "F200",
    "R80-90",
    "F250",
    "O100",
    "F180",
    "L100-45",
    "F200",
    "FINISH",
]


# ================================================================
#  指令解析
# ================================================================

def parse_instruction(text: str):
    """
    解析单条指令字符串.

    Returns (type, params) 或 None (无效).
    type: 'F' | 'R' | 'L' | 'S' | 'X' | 'O' | 'FINISH'
    """
    text = text.strip().upper()
    if not text:
        return None

    if text == "FINISH":
        return ("FINISH", {})

    # F<dist>
    m = re.match(r"^F(\d+(?:\.\d+)?)$", text)
    if m:
        return ("F", {"dist": float(m.group(1))})

    # R<radius>-<angle>
    m = re.match(r"^R(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$", text)
    if m:
        return ("R", {"radius": float(m.group(1)),
                       "angle": float(m.group(2))})

    # L<radius>-<angle>
    m = re.match(r"^L(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$", text)
    if m:
        return ("L", {"radius": float(m.group(1)),
                       "angle": float(m.group(2))})

    # S<radius>-<angle>-<count>
    m = re.match(r"^S(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-(\d+)$", text)
    if m:
        return ("S", {"radius": float(m.group(1)),
                       "angle": float(m.group(2)),
                       "count": int(m.group(3))})

    # X<arm_len>
    m = re.match(r"^X(\d+(?:\.\d+)?)$", text)
    if m:
        return ("X", {"arm_len": float(m.group(1))})

    # O<radius> or O<radius>-<sweep>
    m = re.match(r"^O(\d+(?:\.\d+)?)(?:-(\d+(?:\.\d+)?))?$", text)
    if m:
        ring_r = float(m.group(1))
        sweep = float(m.group(2)) if m.group(2) else 270.0
        return ("O", {"ring_r": ring_r, "sweep": sweep})

    return None


# ================================================================
#  TrackBuilder — 按指令构建赛道
# ================================================================

class TrackBuilder:
    """Turtle-graphics 风格赛道构建器"""

    def __init__(self, track_width=80):
        self.track_width = track_width
        self.reset()

    # ---- 状态 ----

    def reset(self):
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0          # 弧度, 0=右, π/2=下
        self.centerline = [(0.0, 0.0)]
        self.extras = []            # 十字路口 / 环岛附加线段
        self.closed = False

    # ---- 基本元素 ----

    def forward(self, dist, step=3.0):
        """直线前进 dist 像素"""
        n = max(int(dist / step), 2)
        dx = math.cos(self.heading)
        dy = math.sin(self.heading)
        for i in range(1, n + 1):
            t = i / n
            self.centerline.append((self.x + dx * dist * t,
                                    self.y + dy * dist * t))
        self.x += dx * dist
        self.y += dy * dist

    def arc(self, radius, angle_deg, direction, step=3.0):
        """
        圆弧转弯.
        direction: 'R' 右转(屏幕坐标顺时针) / 'L' 左转
        """
        angle_rad = math.radians(angle_deg)

        if direction == "R":
            cx = self.x + radius * math.cos(self.heading + math.pi / 2)
            cy = self.y + radius * math.sin(self.heading + math.pi / 2)
            sweep = angle_rad
            h_change = angle_rad
        else:
            cx = self.x + radius * math.cos(self.heading - math.pi / 2)
            cy = self.y + radius * math.sin(self.heading - math.pi / 2)
            sweep = -angle_rad
            h_change = -angle_rad

        start_a = math.atan2(self.y - cy, self.x - cx)
        arc_len = radius * abs(angle_rad)
        n = max(int(arc_len / step), 4)

        for i in range(1, n + 1):
            a = start_a + sweep * i / n
            self.centerline.append((cx + radius * math.cos(a),
                                    cy + radius * math.sin(a)))

        end_a = start_a + sweep
        self.x = cx + radius * math.cos(end_a)
        self.y = cy + radius * math.sin(end_a)
        self.heading += h_change

    def s_curve(self, radius, angle_deg, count):
        """连续 S 弯 (先左后右交替)"""
        for i in range(count):
            self.arc(radius, angle_deg, "L" if i % 2 == 0 else "R")

    def crossroad(self, arm_len):
        """十字路口 (在当前位置添加垂直道路)"""
        nx = -math.sin(self.heading)
        ny = math.cos(self.heading)
        a1 = (self.x + nx * arm_len, self.y + ny * arm_len)
        a2 = (self.x - nx * arm_len, self.y - ny * arm_len)
        self.extras.append(_lerp(a1[0], a1[1], a2[0], a2[1]))

    def roundabout(self, ring_r, sweep_deg=270):
        """
        环岛: 小车进入右侧圆环, 顺时针绕行 sweep_deg 度后驶出.
        同时绘制完整圆环和额外臂.
        """
        # 圆心在行进方向右侧
        cx = self.x + ring_r * math.cos(self.heading + math.pi / 2)
        cy = self.y + ring_r * math.sin(self.heading + math.pi / 2)

        # 完整圆环 (视觉)
        ring = _arc_pts(cx, cy, ring_r, 0, 2 * math.pi, step=2.0)
        ring.append(ring[0])
        self.extras.append(ring)

        # 小车沿圆环行驶
        entry_a = math.atan2(self.y - cy, self.x - cx)
        sweep = math.radians(sweep_deg)
        arc_len = ring_r * abs(sweep)
        n = max(int(arc_len / 3), 8)
        for i in range(1, n + 1):
            a = entry_a + sweep * i / n
            self.centerline.append((cx + ring_r * math.cos(a),
                                    cy + ring_r * math.sin(a)))

        end_a = entry_a + sweep
        self.x = cx + ring_r * math.cos(end_a)
        self.y = cy + ring_r * math.sin(end_a)
        self.heading += sweep

        # 额外臂 (在 90° / 180° 位置)
        for off_deg in [90, 180]:
            aa = entry_a + math.radians(off_deg)
            ax = cx + ring_r * math.cos(aa)
            ay = cy + ring_r * math.sin(aa)
            bx = ax + ring_r * 0.75 * math.cos(aa)
            by = ay + ring_r * 0.75 * math.sin(aa)
            self.extras.append(_lerp(ax, ay, bx, by))

    def finish(self):
        """用 Hermite 曲线平滑闭合回起点"""
        sx, sy = self.centerline[0]
        d = math.hypot(self.x - sx, self.y - sy)
        if d < 5:
            self.closed = True
            return

        P0 = np.array([self.x, self.y])
        P1 = np.array([sx, sy])
        T0 = np.array([math.cos(self.heading),
                        math.sin(self.heading)]) * d * 0.45
        T1 = np.array([math.cos(0), math.sin(0)]) * d * 0.45  # 起始朝向=0

        n = max(int(d / 3), 10)
        for i in range(1, n + 1):
            t = i / n
            h00 = 2 * t**3 - 3 * t**2 + 1
            h10 = t**3 - 2 * t**2 + t
            h01 = -2 * t**3 + 3 * t**2
            h11 = t**3 - t**2
            p = h00 * P0 + h10 * T0 + h01 * P1 + h11 * T1
            self.centerline.append(tuple(p))

        self.x, self.y = sx, sy
        self.heading = 0.0
        self.closed = True

    # ---- 批量构建 ----

    def build(self, instructions):
        """从指令列表构建赛道"""
        self.reset()
        for text in instructions:
            parsed = parse_instruction(text)
            if parsed is None:
                continue
            cmd, p = parsed
            if cmd == "F":
                self.forward(p["dist"])
            elif cmd == "R":
                self.arc(p["radius"], p["angle"], "R")
            elif cmd == "L":
                self.arc(p["radius"], p["angle"], "L")
            elif cmd == "S":
                self.s_curve(p["radius"], p["angle"], p["count"])
            elif cmd == "X":
                self.crossroad(p["arm_len"])
            elif cmd == "O":
                self.roundabout(p["ring_r"], p.get("sweep", 270))
            elif cmd == "FINISH":
                self.finish()
                break

    # ---- 渲染 ----

    def render(self, margin=200):
        """渲染为灰度图 (兼容 Track 类)"""
        if len(self.centerline) < 2:
            img = np.zeros((400, 400), dtype=np.uint8)
            return img, (0.0, 0.0)

        all_xy = list(self.centerline)
        for ex in self.extras:
            all_xy.extend(ex)

        arr = np.array(all_xy, dtype=np.float64)
        lo = arr.min(axis=0) - margin
        hi = arr.max(axis=0) + margin
        W = max(int(hi[0] - lo[0]), 100)
        H = max(int(hi[1] - lo[1]), 100)

        img = np.zeros((H, W), dtype=np.uint8)
        tw = self.track_width

        cl_pts = np.array([(int(x - lo[0]), int(y - lo[1]))
                            for x, y in self.centerline], np.int32)
        cv2.polylines(img, [cl_pts], self.closed,
                      255, tw, cv2.LINE_AA)

        for ex in self.extras:
            if len(ex) >= 2:
                pts = np.array([(int(x - lo[0]), int(y - lo[1]))
                                for x, y in ex], np.int32)
                cv2.polylines(img, [pts], False,
                              255, tw, cv2.LINE_AA)

        return img, (lo[0], lo[1])


# ---- 几何工具 (模块级) ----

def _lerp(x0, y0, x1, y1, step=3.0):
    d = math.hypot(x1 - x0, y1 - y0)
    n = max(int(d / step), 2)
    return [(x0 + (x1 - x0) * i / n,
             y0 + (y1 - y0) * i / n) for i in range(n + 1)]


def _arc_pts(cx, cy, r, a0, sweep, step=3.0):
    arc_len = abs(r * sweep)
    n = max(int(arc_len / step), 8)
    return [(cx + r * math.cos(a0 + sweep * i / n),
             cy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


# ================================================================
#  TrackEditor — Pygame 实时编辑器
# ================================================================

class TrackEditor:
    SIDEBAR_W = 340
    STATUS_H = 36
    BG = (35, 35, 40)
    SIDEBAR_BG = (45, 45, 52)
    INPUT_BG = (30, 30, 35)
    TEXT = (210, 215, 220)
    DIM = (120, 120, 130)
    ACCENT = (90, 170, 255)
    GREEN = (80, 230, 120)
    RED = (255, 90, 90)
    WHITE = (255, 255, 255)

    def __init__(self, track_width=80, output="assets/track_editor.png"):
        self.track_width = track_width
        self.output = output
        self.builder = TrackBuilder(track_width)
        self.instructions: list[str] = []
        self.input_text = ""
        self.message = ""
        self.msg_timer = 0

        # 视口
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 0.45
        self.dragging = False
        self.drag_start = None

        # 指令列表滚动
        self.scroll_y = 0

        # Pygame
        pygame.init()
        info = pygame.display.Info()
        self.W = min(1400, info.current_w - 80)
        self.H = min(920, info.current_h - 80)
        self.screen = pygame.display.set_mode((self.W, self.H), pygame.RESIZABLE)
        pygame.display.set_caption("赛道指令编辑器  |  Track Instruction Editor")

        # 字体
        self.font = pygame.font.SysFont("microsoftyahei,consolas,arial", 15)
        self.font_b = pygame.font.SysFont("microsoftyahei,consolas,arial", 16, bold=True)
        self.font_s = pygame.font.SysFont("consolas,microsoftyahei,arial", 13)
        self.font_mono = pygame.font.SysFont("consolas,courier", 15)

        self.clock = pygame.time.Clock()

        # 预览 surface 缓存
        self.track_surface = None
        self.surf_offset = (0.0, 0.0)
        self._cached_zoom = -1.0
        self._cached_scaled = None

        self._rebuild()

    # ---- 核心逻辑 ----

    def _rebuild(self):
        """重新构建赛道 & 更新预览 surface"""
        self.builder.build(self.instructions)
        self._update_surface()
        self._cached_zoom = -1.0     # 使缩放缓存失效

    def _update_surface(self):
        """用 OpenCV 渲染赛道为 Pygame Surface"""
        cl = self.builder.centerline
        if len(cl) < 2:
            self.track_surface = None
            return

        all_xy = list(cl)
        for ex in self.builder.extras:
            all_xy.extend(ex)

        arr = np.array(all_xy, dtype=np.float64)
        margin = self.builder.track_width + 60
        lo = arr.min(axis=0) - margin
        hi = arr.max(axis=0) + margin
        W = max(int(hi[0] - lo[0]), 100)
        H = max(int(hi[1] - lo[1]), 100)

        # 限制预览图大小
        if max(W, H) > 5000:
            self.track_surface = None
            return

        bgr = np.zeros((H, W, 3), dtype=np.uint8)
        tw = self.builder.track_width

        # 白色赛道
        cl_pts = np.array([(int(x - lo[0]), int(y - lo[1]))
                            for x, y in cl], np.int32)
        cv2.polylines(bgr, [cl_pts], self.builder.closed,
                      (255, 255, 255), tw, cv2.LINE_AA)

        for ex in self.builder.extras:
            if len(ex) >= 2:
                pts = np.array([(int(x - lo[0]), int(y - lo[1]))
                                for x, y in ex], np.int32)
                cv2.polylines(bgr, [pts], False,
                              (255, 255, 255), tw, cv2.LINE_AA)

        # 中心线 (淡灰细线)
        cv2.polylines(bgr, [cl_pts], self.builder.closed,
                      (90, 90, 90), 1, cv2.LINE_AA)

        # BGR → RGB, 再创建 Pygame surface
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.track_surface = pygame.image.frombuffer(
            rgb.tobytes(), (W, H), "RGB")
        self.surf_offset = (lo[0], lo[1])

    def _auto_fit(self):
        """自动缩放/平移使赛道适配视口"""
        all_pts = list(self.builder.centerline)
        for ex in self.builder.extras:
            all_pts.extend(ex)

        if len(all_pts) < 2:
            self.cam_x = self.cam_y = 0.0
            self.zoom = 0.45
            return

        arr = np.array(all_pts)
        lo = arr.min(axis=0)
        hi = arr.max(axis=0)
        cx = (lo[0] + hi[0]) / 2
        cy = (lo[1] + hi[1]) / 2

        vp_w = self.W - self.SIDEBAR_W
        vp_h = self.H - self.STATUS_H
        span_x = max(hi[0] - lo[0], 50) + self.builder.track_width * 2
        span_y = max(hi[1] - lo[1], 50) + self.builder.track_width * 2

        self.zoom = min(vp_w / span_x, vp_h / span_y, 2.0) * 0.88
        self.cam_x = cx
        self.cam_y = cy
        self._cached_zoom = -1.0

    def _show_msg(self, text, frames=120):
        self.message = text
        self.msg_timer = frames

    # ---- 坐标变换 ----

    def _w2s(self, wx, wy):
        """世界坐标 → 屏幕像素"""
        vp_w = self.W - self.SIDEBAR_W
        vp_h = self.H - self.STATUS_H
        return (int((wx - self.cam_x) * self.zoom + vp_w / 2),
                int((wy - self.cam_y) * self.zoom + vp_h / 2))

    # ---- 保存 ----

    def _save(self):
        if len(self.builder.centerline) < 2:
            self._show_msg("赛道为空, 无法保存!")
            return

        os.makedirs(os.path.dirname(self.output) or ".", exist_ok=True)

        # 灰度赛道图
        img, lo = self.builder.render(margin=200)
        cv2.imwrite(self.output, img)

        # 起点信息
        sx = self.builder.centerline[0][0] - lo[0]
        sy = self.builder.centerline[0][1] - lo[1]
        if len(self.builder.centerline) >= 2:
            dx = self.builder.centerline[1][0] - self.builder.centerline[0][0]
            dy = self.builder.centerline[1][1] - self.builder.centerline[0][1]
            sh = math.atan2(dy, dx)
        else:
            sh = 0.0

        info_path = self.output.replace(".png", "_info.txt")
        with open(info_path, "w") as f:
            f.write(f"{sx},{sy},{sh}\n")

        # 指令文件
        instr_path = self.output.replace(".png", "_instr.txt")
        with open(instr_path, "w") as f:
            for inst in self.instructions:
                f.write(inst + "\n")

        self._show_msg(
            f"Saved: {self.output} ({img.shape[1]}x{img.shape[0]})")

    # ---- 渲染 ----

    def _render_preview(self):
        vp_w = self.W - self.SIDEBAR_W
        vp_h = self.H - self.STATUS_H

        # 视口黑底
        pygame.draw.rect(self.screen, (15, 15, 20), (0, 0, vp_w, vp_h))

        # 赛道 surface
        if self.track_surface is not None:
            z = self.zoom
            sw = self.track_surface.get_width()
            sh = self.track_surface.get_height()
            zw = max(1, int(sw * z))
            zh = max(1, int(sh * z))

            if zw < 6000 and zh < 6000:
                # 缓存缩放后的 surface
                if abs(z - self._cached_zoom) > 1e-5 or self._cached_scaled is None:
                    self._cached_scaled = pygame.transform.scale(
                        self.track_surface, (zw, zh))
                    self._cached_zoom = z

                ox = (self.surf_offset[0] - self.cam_x) * z + vp_w / 2
                oy = (self.surf_offset[1] - self.cam_y) * z + vp_h / 2
                self.screen.blit(self._cached_scaled, (int(ox), int(oy)))

        # 起点标记 (红色)
        sx, sy = self._w2s(0, 0)
        if -50 < sx < vp_w + 50 and -50 < sy < vp_h + 50:
            pygame.draw.circle(self.screen, self.RED, (sx, sy), 7)
            pygame.draw.circle(self.screen, (180, 50, 50), (sx, sy), 7, 2)
            ax, ay = self._w2s(35 * math.cos(0), 35 * math.sin(0))
            pygame.draw.line(self.screen, self.RED, (sx, sy), (ax, ay), 2)
            lbl = self.font_s.render("START", True, self.RED)
            self.screen.blit(lbl, (sx + 10, sy - 8))

        # 当前位置标记 (绿色)
        bx, by = self.builder.x, self.builder.y
        csx, csy = self._w2s(bx, by)
        if -50 < csx < vp_w + 50 and -50 < csy < vp_h + 50:
            pygame.draw.circle(self.screen, self.GREEN, (csx, csy), 7)
            pygame.draw.circle(self.screen, (40, 160, 60), (csx, csy), 7, 2)
            hx = bx + 35 * math.cos(self.builder.heading)
            hy = by + 35 * math.sin(self.builder.heading)
            hsx, hsy = self._w2s(hx, hy)
            pygame.draw.line(self.screen, self.GREEN,
                             (csx, csy), (hsx, hsy), 2)

    def _render_sidebar(self):
        vp_w = self.W - self.SIDEBAR_W
        sb_x = vp_w

        pygame.draw.rect(self.screen, self.SIDEBAR_BG,
                         (sb_x, 0, self.SIDEBAR_W, self.H))

        y = 8
        title = self.font_b.render("Instructions", True, self.ACCENT)
        self.screen.blit(title, (sb_x + 12, y))
        y += 24

        # 帮助
        helps = [
            "F<d>  R<r>-<a>  L<r>-<a>",
            "S<r>-<a>-<n>  X<arm>  O<r>",
            "O<r>-<sweep>  FINISH",
        ]
        for h in helps:
            s = self.font_s.render(h, True, self.DIM)
            self.screen.blit(s, (sb_x + 12, y))
            y += 16
        y += 4

        # 分割线
        pygame.draw.line(self.screen, (65, 65, 72),
                         (sb_x + 6, y), (sb_x + self.SIDEBAR_W - 6, y))
        y += 6

        # 指令列表
        line_h = 22
        list_top = y
        list_bot = self.H - 80
        max_vis = max(1, (list_bot - list_top) // line_h)

        # 保证滚动范围
        max_scroll = max(0, len(self.instructions) - max_vis)
        self.scroll_y = max(0, min(self.scroll_y, max_scroll))

        for idx in range(self.scroll_y,
                         min(len(self.instructions), self.scroll_y + max_vis)):
            inst = self.instructions[idx]
            valid = parse_instruction(inst) is not None
            color = self.TEXT if valid else self.RED
            num = f"{idx + 1:3d}. "
            s = self.font_mono.render(num + inst, True, color)
            self.screen.blit(s, (sb_x + 10, list_top + (idx - self.scroll_y) * line_h))

        if len(self.instructions) > max_vis:
            bar_h = max(20, int(max_vis / len(self.instructions) * (list_bot - list_top)))
            bar_y = list_top + int(self.scroll_y / max(1, max_scroll) * (list_bot - list_top - bar_h))
            pygame.draw.rect(self.screen, (70, 70, 80),
                             (sb_x + self.SIDEBAR_W - 10, bar_y, 6, bar_h),
                             border_radius=3)

        # 输入框
        input_y = self.H - 68
        pygame.draw.line(self.screen, (65, 65, 72),
                         (sb_x + 6, input_y - 6),
                         (sb_x + self.SIDEBAR_W - 6, input_y - 6))

        pygame.draw.rect(self.screen, self.INPUT_BG,
                         (sb_x + 8, input_y, self.SIDEBAR_W - 16, 28),
                         border_radius=4)
        pygame.draw.rect(self.screen, self.ACCENT,
                         (sb_x + 8, input_y, self.SIDEBAR_W - 16, 28),
                         width=1, border_radius=4)

        cursor = "_" if (pygame.time.get_ticks() % 900) < 450 else ""
        prompt = "> " + self.input_text + cursor
        s = self.font_mono.render(prompt, True, self.TEXT)
        self.screen.blit(s, (sb_x + 14, input_y + 5))

        # 底部提示
        hints = "Enter:Add  Ctrl+Z:Undo  Ctrl+S:Save  Ctrl+E:Example"
        s = self.font_s.render(hints, True, (100, 100, 110))
        self.screen.blit(s, (sb_x + 10, input_y + 34))

    def _render_status(self):
        vp_w = self.W - self.SIDEBAR_W
        y = self.H - self.STATUS_H

        pygame.draw.rect(self.screen, (28, 28, 32),
                         (0, y, vp_w, self.STATUS_H))

        cx, cy = self.builder.x, self.builder.y
        h_deg = math.degrees(self.builder.heading) % 360
        n_instr = len(self.instructions)
        status = (f"Pos ({cx:.0f}, {cy:.0f})  "
                  f"Heading {h_deg:.1f}\u00b0  "
                  f"Instr {n_instr}")
        if self.builder.closed:
            status += "  [CLOSED]"

        s = self.font_s.render(status, True, (160, 160, 170))
        self.screen.blit(s, (10, y + 10))

        if self.msg_timer > 0:
            self.msg_timer -= 1
            s = self.font_b.render(self.message, True, self.GREEN)
            self.screen.blit(s, (vp_w // 2 - s.get_width() // 2, y + 8))

    # ---- 主循环 ----

    def run(self):
        self._auto_fit()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.W, self.H = event.w, event.h
                    self.screen = pygame.display.set_mode(
                        (self.W, self.H), pygame.RESIZABLE)
                    self._cached_zoom = -1.0

                elif event.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()

                    if event.key == pygame.K_ESCAPE:
                        running = False

                    elif event.key == pygame.K_RETURN:
                        txt = self.input_text.strip()
                        if txt:
                            parsed = parse_instruction(txt)
                            if parsed:
                                self.instructions.append(txt.upper())
                                self.input_text = ""
                                self._rebuild()
                                self._auto_fit()
                            else:
                                self._show_msg(f"Invalid: {txt}")

                    elif event.key == pygame.K_BACKSPACE:
                        if self.input_text:
                            self.input_text = self.input_text[:-1]

                    elif event.key == pygame.K_z and mods & pygame.KMOD_CTRL:
                        if self.instructions:
                            self.instructions.pop()
                            self._rebuild()
                            self._auto_fit()
                            self._show_msg("Undo")

                    elif event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
                        self._save()

                    elif event.key == pygame.K_f and mods & pygame.KMOD_CTRL:
                        self._auto_fit()

                    elif event.key == pygame.K_e and mods & pygame.KMOD_CTRL:
                        self.instructions = list(EXAMPLE_INSTRUCTIONS)
                        self.input_text = ""
                        self._rebuild()
                        self._auto_fit()
                        self._show_msg("Loaded example")

                    elif event.unicode and event.unicode.isprintable():
                        self.input_text += event.unicode

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    vp_w = self.W - self.SIDEBAR_W
                    if event.button == 1 and event.pos[0] < vp_w:
                        self.dragging = True
                        self.drag_start = event.pos
                    elif event.button == 4:       # scroll up
                        if event.pos[0] < vp_w:
                            self.zoom = min(5.0, self.zoom * 1.12)
                            self._cached_zoom = -1.0
                        else:
                            self.scroll_y = max(0, self.scroll_y - 3)
                    elif event.button == 5:       # scroll down
                        if event.pos[0] < vp_w:
                            self.zoom = max(0.03, self.zoom / 1.12)
                            self._cached_zoom = -1.0
                        else:
                            self.scroll_y += 3

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.dragging = False

                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging and self.drag_start:
                        dx = event.pos[0] - self.drag_start[0]
                        dy = event.pos[1] - self.drag_start[1]
                        self.cam_x -= dx / self.zoom
                        self.cam_y -= dy / self.zoom
                        self.drag_start = event.pos
                        self._cached_zoom = -1.0

            # 绘制
            self.screen.fill(self.BG)
            self._render_preview()
            self._render_sidebar()
            self._render_status()
            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()


# ================================================================
#  CLI 入口
# ================================================================

def main():
    ap = argparse.ArgumentParser(
        description="赛道指令编辑器 — 实时预览 & 保存")
    ap.add_argument("--output", default="assets/track_editor.png",
                    help="输出赛道图片路径")
    ap.add_argument("--width", type=int, default=80,
                    help="赛道宽度 (像素)")
    ap.add_argument("--load", default=None,
                    help="加载已有指令文件 (.txt, 每行一条)")
    args = ap.parse_args()

    editor = TrackEditor(track_width=args.width, output=args.output)

    if args.load and os.path.exists(args.load):
        with open(args.load, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and parse_instruction(line):
                    editor.instructions.append(line.upper())
        editor._rebuild()
        editor._auto_fit()
        print(f"已加载 {len(editor.instructions)} 条指令: {args.load}")

    editor.run()


if __name__ == "__main__":
    main()
