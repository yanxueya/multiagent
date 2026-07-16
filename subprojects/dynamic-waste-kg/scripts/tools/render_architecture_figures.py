"""Render the four architecture figures used by the project audit.

The renderer intentionally uses only Python stdlib plus Pillow so the SVG and
PNG outputs can be reproduced on Windows and Ubuntu without a diagram editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 2400, 1350
BG = "#F7F9FC"
INK = "#172033"
MUTED = "#5B6577"
NAVY = "#173F6D"
BLUE = "#DCEEFF"
GREEN = "#DDF3E4"
GREEN_DARK = "#26734D"
ORANGE = "#FFF0D6"
ORANGE_DARK = "#B86616"
ROSE = "#FCE3E8"
ROSE_DARK = "#A33A50"
PURPLE = "#ECE5FF"
PURPLE_DARK = "#6548A8"
GRAY = "#E9EDF3"
GRAY_DARK = "#667085"
RED = "#C73E4D"
WHITE = "#FFFFFF"


def _font_path() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise FileNotFoundError("No suitable CJK font found")


FONT_PATH = _font_path()


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int
    title: str
    lines: list[str] = field(default_factory=list)
    fill: str = WHITE
    stroke: str = NAVY
    dashed: bool = False
    title_size: int = 31
    body_size: int = 23

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


class Figure:
    def __init__(self, title: str, subtitle: str) -> None:
        self.title = title
        self.subtitle = subtitle
        self.boxes: list[Box] = []
        self.arrows: list[tuple[int, int, int, int, str, str, bool]] = []
        self.labels: list[tuple[int, int, str, int, str, str]] = []
        self.bands: list[tuple[int, int, int, int, str, str, str]] = []

    def box(self, *args, **kwargs) -> Box:
        box = Box(*args, **kwargs)
        self.boxes.append(box)
        return box

    def arrow(self, x1: int, y1: int, x2: int, y2: int, label: str = "", color: str = NAVY, dashed: bool = False) -> None:
        self.arrows.append((x1, y1, x2, y2, label, color, dashed))

    def label(self, x: int, y: int, text: str, size: int = 24, color: str = INK, anchor: str = "middle") -> None:
        self.labels.append((x, y, text, size, color, anchor))

    def band(self, x: int, y: int, w: int, h: int, title: str, fill: str, stroke: str) -> None:
        self.bands.append((x, y, w, h, title, fill, stroke))

    def save(self, stem: Path) -> None:
        stem.parent.mkdir(parents=True, exist_ok=True)
        stem.with_suffix(".svg").write_text(self._svg(), encoding="utf-8")
        self._png().save(stem.with_suffix(".png"), dpi=(180, 180))

    def _svg(self) -> str:
        out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
            "<defs>",
            '<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="context-stroke"/></marker>',
            '<filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-opacity="0.12"/></filter>',
            "</defs>",
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>',
            f'<text x="90" y="72" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="42" font-weight="700" fill="{INK}">{escape(self.title)}</text>',
            f'<text x="90" y="112" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="23" fill="{MUTED}">{escape(self.subtitle)}</text>',
        ]
        for x, y, w, h, title, fill, stroke in self.bands:
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
            out.append(f'<text x="{x + 28}" y="{y + 42}" font-family="Microsoft YaHei, sans-serif" font-size="29" font-weight="700" fill="{stroke}">{escape(title)}</text>')
        for x1, y1, x2, y2, label, color, dashed in self.arrows:
            dash = ' stroke-dasharray="12 10"' if dashed else ""
            out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="4" marker-end="url(#arrow)"{dash}/>')
            if label:
                lx, ly = (x1 + x2) // 2, (y1 + y2) // 2 - 10
                out.append(f'<rect x="{lx - 82}" y="{ly - 24}" width="164" height="32" rx="8" fill="{BG}" opacity="0.94"/>')
                out.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="20" fill="{color}">{escape(label)}</text>')
        for box in self.boxes:
            dash = ' stroke-dasharray="12 9"' if box.dashed else ""
            out.append(f'<rect x="{box.x}" y="{box.y}" width="{box.w}" height="{box.h}" rx="18" fill="{box.fill}" stroke="{box.stroke}" stroke-width="3" filter="url(#shadow)"{dash}/>')
            out.append(f'<text x="{box.cx}" y="{box.y + 42}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="{box.title_size}" font-weight="700" fill="{box.stroke}">{escape(box.title)}</text>')
            y = box.y + 78
            for line in box.lines:
                out.append(f'<text x="{box.x + 22}" y="{y}" font-family="Microsoft YaHei, sans-serif" font-size="{box.body_size}" fill="{INK}">{escape(line)}</text>')
                y += box.body_size + 10
        for x, y, text, size, color, anchor in self.labels:
            out.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Microsoft YaHei, sans-serif" font-size="{size}" fill="{color}">{escape(text)}</text>')
        out.append("</svg>")
        return "\n".join(out)

    def _png(self) -> Image.Image:
        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(image)
        title_font = ImageFont.truetype(FONT_PATH, 42)
        sub_font = ImageFont.truetype(FONT_PATH, 23)
        draw.text((90, 35), self.title, font=title_font, fill=INK)
        draw.text((90, 84), self.subtitle, font=sub_font, fill=MUTED)
        for x, y, w, h, title, fill, stroke in self.bands:
            draw.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=fill, outline=stroke, width=3)
            draw.text((x + 28, y + 12), title, font=ImageFont.truetype(FONT_PATH, 29), fill=stroke)
        for x1, y1, x2, y2, label, color, dashed in self.arrows:
            self._draw_arrow(draw, x1, y1, x2, y2, color, dashed)
            if label:
                font = ImageFont.truetype(FONT_PATH, 20)
                bbox = draw.textbbox((0, 0), label, font=font)
                lx, ly = (x1 + x2) // 2, (y1 + y2) // 2 - 20
                tw = bbox[2] - bbox[0]
                draw.rounded_rectangle((lx - tw // 2 - 7, ly - 3, lx + tw // 2 + 7, ly + 27), 7, fill=BG)
                draw.text((lx - tw // 2, ly), label, font=font, fill=color)
        for box in self.boxes:
            draw.rounded_rectangle((box.x, box.y, box.x + box.w, box.y + box.h), radius=18, fill=box.fill, outline=box.stroke, width=3)
            if box.dashed:
                self._dashed_rect(draw, box.x, box.y, box.x + box.w, box.y + box.h, box.stroke)
            font = ImageFont.truetype(FONT_PATH, box.title_size)
            bbox = draw.textbbox((0, 0), box.title, font=font)
            draw.text((box.cx - (bbox[2] - bbox[0]) / 2, box.y + 12), box.title, font=font, fill=box.stroke)
            body = ImageFont.truetype(FONT_PATH, box.body_size)
            y = box.y + 72
            for line in box.lines:
                draw.text((box.x + 22, y), line, font=body, fill=INK)
                y += box.body_size + 10
        for x, y, text, size, color, anchor in self.labels:
            font = ImageFont.truetype(FONT_PATH, size)
            bbox = draw.textbbox((0, 0), text, font=font)
            xx = x if anchor == "start" else x - (bbox[2] - bbox[0]) / 2
            draw.text((xx, y - size), text, font=font, fill=color)
        return image

    @staticmethod
    def _draw_arrow(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color: str, dashed: bool) -> None:
        if dashed:
            segments = 14
            for i in range(0, segments, 2):
                a, b = i / segments, min((i + 1) / segments, 1)
                draw.line((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, x1 + (x2 - x1) * b, y1 + (y2 - y1) * b), fill=color, width=4)
        else:
            draw.line((x1, y1, x2, y2), fill=color, width=4)
        import math
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 18
        points = [(x2, y2), (x2 - size * math.cos(angle - 0.55), y2 - size * math.sin(angle - 0.55)), (x2 - size * math.cos(angle + 0.55), y2 - size * math.sin(angle + 0.55))]
        draw.polygon(points, fill=color)

    @staticmethod
    def _dashed_rect(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
        for x in range(x1, x2, 24):
            draw.line((x, y1, min(x + 13, x2), y1), fill=color, width=4)
            draw.line((x, y2, min(x + 13, x2), y2), fill=color, width=4)
        for y in range(y1, y2, 24):
            draw.line((x1, y, x1, min(y + 13, y2)), fill=color, width=4)
            draw.line((x2, y, x2, min(y + 13, y2)), fill=color, width=4)


def figure_1() -> Figure:
    f = Figure("① 三层动态知识图谱架构", "层级是语义分层，不在 Neo4j 中创建虚构 Layer 节点；类别由关系表达，不作为实例属性持久化")
    f.band(70, 145, 2260, 270, "长期知识层  Long-term knowledge", GREEN, GREEN_DARK)
    cat = f.box(130, 210, 680, 165, "WasteCategory（11类）", ["主键 category_name", "risk / fragility / graspability_prior", "VLM policy / handling policy / visual prototype"], GREEN, GREEN_DARK, body_size=21)
    f.box(940, 210, 610, 165, "知识种子证据边界", ["人工定义、待实验验证", "单次观测不得直接修改长期先验", "演化需审核、训练与独立验证"], WHITE, GREEN_DARK, body_size=21)
    f.box(1680, 210, 580, 165, "禁止进入 KG 的规划属性", ["task_value / priority_tier", "动态评分、动作顺序、失败策略"], WHITE, RED, body_size=21)

    f.band(70, 445, 2260, 430, "短期记忆层  Short-term memory", BLUE, NAVY)
    scene = f.box(120, 535, 390, 165, "Scene", ["scene_id / captured_at", "rgb_ref / depth_ref"], WHITE, NAVY)
    inst = f.box(660, 500, 620, 255, "ObjectInstance", ["识别：confidence / status / VLM consistency", "证据：bbox / mask / crop", "几何：center / depth ratio / extent / occlusion", "任务：handling policy / status / attempts"], WHITE, NAVY, body_size=20)
    sample = f.box(1430, 500, 410, 190, "UnknownSample", ["crop / mask / YOLO top-k", "VLM attributes / review status", "human label"], ORANGE, ORANGE_DARK, body_size=20)
    cluster = f.box(1910, 535, 360, 165, "UnknownCluster", ["members / prototype", "representative crop", "candidate category"], ORANGE, ORANGE_DARK, body_size=20)
    f.arrow(scene.x + scene.w, scene.cy, inst.x, inst.cy, "CONTAINS")
    f.arrow(inst.x + inst.w, inst.cy, sample.x, sample.cy, "RECORDED_AS", ORANGE_DARK)
    f.arrow(sample.x + sample.w, sample.cy, cluster.x, cluster.cy, "MEMBER_OF", ORANGE_DARK)
    f.arrow(inst.cx, inst.y, cat.cx, cat.y + cat.h, "CANDIDATE_OF / CONFIRMED_AS", GREEN_DARK)
    f.label(970, 825, "ObjectInstance <-> ObjectInstance：NEAR（无属性关系）", 22, NAVY)

    f.band(70, 905, 2260, 350, "事件日志层  Append-only event log", ROSE, ROSE_DARK)
    names = ["Detection", "VLMReview", "DepthUpdate", "HumanReview", "Planning", "Execution", "KnowledgeEvolution"]
    for i, name in enumerate(names):
        f.box(105 + i * 320, 995, 270, 115, name + "Event", ["event_id / time / source"], WHITE, ROSE_DARK, title_size=18, body_size=17)
    f.label(1200, 1180, "事件通过 IN_SCENE / DETECTED / REVIEWS / UPDATES / SELECTS / EXECUTES_ON / CREATES 等关系连接真实业务节点", 22, ROSE_DARK)
    return f


def figure_2() -> Figure:
    f = Figure("② 低置信度与人工复核的信息流", "YOLO 只给出候选；VLM 只做受约束属性一致性判断；人工决定通过 HumanReviewEvent 进入唯一 KG 写入口")
    inp = f.box(90, 205, 300, 135, "RGB / RGB-D", ["RealSense 或离线图像"], BLUE, NAVY)
    yolo = f.box(500, 190, 350, 165, "YOLO segmentation", ["11类候选 + confidence", "bbox / mask / crop"], BLUE, NAVY)
    gate = f.box(970, 175, 450, 195, "置信度与类别策略门控", ["<0.05：丢弃", "0.05–0.30：人工复核", "0.30–0.75：VLM复核", "≥0.75：仍检查 always 类别"], GRAY, GRAY_DARK, body_size=21)
    f.arrow(inp.x + inp.w, inp.cy, yolo.x, yolo.cy)
    f.arrow(yolo.x + yolo.w, yolo.cy, gate.x, gate.cy)

    vlm = f.box(690, 520, 420, 220, "受约束 VLM", ["颜色 / 透明度 / 光泽", "纹理 / 断裂 / 形状", "support 或 conflict"], PURPLE, PURPLE_DARK, body_size=21)
    accepted = f.box(1270, 470, 400, 180, "Accepted instance", ["CONFIRMED_AS", "仍需深度、遮挡与策略校验"], GREEN, GREEN_DARK, body_size=20)
    unknown = f.box(1270, 735, 430, 200, "Unknown / review_required", ["robot_forbidden 或 human_review_required", "RECORDED_AS -> UnknownSample"], ORANGE, ORANGE_DARK, body_size=20)
    kg = f.box(1850, 545, 420, 240, "KG Writer（唯一写入口）", ["schema 校验", "短期状态更新", "追加事件", "Neo4j / UI 镜像"], GREEN, GREEN_DARK, body_size=21)
    human = f.box(1790, 915, 520, 235, "人工复核 Human-in-the-loop", ["confirm_existing / mark_unknown", "approve_robot / forbid_robot", "discard_detection"], ORANGE, ORANGE_DARK, body_size=20)

    f.arrow(gate.x + 80, gate.y + gate.h, unknown.x, unknown.y, "0.05–0.30 -> review_required", ORANGE_DARK)
    f.arrow(gate.cx, gate.y + gate.h, vlm.cx, vlm.y, "需要VLM", PURPLE_DARK)
    f.arrow(gate.x + gate.w, gate.cy, accepted.cx, accepted.y, "高置信且策略允许", GREEN_DARK)
    f.arrow(vlm.x + vlm.w, vlm.cy - 35, accepted.x, accepted.cy, "support", GREEN_DARK)
    f.arrow(vlm.x + vlm.w, vlm.cy + 45, unknown.x, unknown.cy, "conflict / error", ORANGE_DARK)
    f.arrow(accepted.x + accepted.w, accepted.cy, kg.x, kg.cy - 55, "state + events", GREEN_DARK)
    f.arrow(unknown.x + unknown.w, unknown.cy, kg.x, kg.cy + 45, "state + events", ORANGE_DARK)
    f.arrow(kg.cx - 50, kg.y + kg.h, human.cx - 50, human.y, "interrupt", ORANGE_DARK)
    f.arrow(human.cx + 55, human.y, kg.cx + 55, kg.y + kg.h, "HumanReviewEvent", ROSE_DARK)

    f.box(220, 1060, 1420, 150, "规划放行条件（确定性硬过滤）", ["accepted ∧ auto_allowed ∧ depth_valid_ratio≥0.30 ∧ occlusion=none ∧ task=pending ∧ attempts<2；否则复核、重扫或不执行"], GRAY, GRAY_DARK, body_size=22)
    f.arrow(kg.x, kg.y + kg.h - 10, 1450, 1060, "graph_state", NAVY)
    return f


def figure_3() -> Figure:
    f = Figure("③ LangGraph 多智能体架构（自上而下）", "4个角色节点 + 2个确定性节点；当前外部视觉与 ROS2 工具尚待真实接入，Supervisor 路由和安全校验为确定性实现")
    user = f.box(900, 150, 600, 105, "用户目标 / UI / operation mode", [], WHITE, NAVY)
    sup = f.box(850, 330, 700, 145, "1  Supervisor Agent", ["三模式条件路由：探索 / 监督执行 / 人机协作"], BLUE, NAVY, body_size=22)
    per = f.box(130, 615, 440, 180, "2  Perception Agent", ["组织 YOLO / VLM / D435i", "产出 Observation 引用"], BLUE, NAVY, body_size=21)
    plan = f.box(690, 615, 440, 180, "3  Action Planning Agent", ["硬过滤 + 无权重字典序", "每次只生成一个动作"], BLUE, NAVY, body_size=21)
    human = f.box(1260, 615, 410, 180, "Human Review Interrupt", ["确定性暂停与恢复", "仅允许5种审核动作"], ORANGE, ORANGE_DARK, body_size=21)
    exe = f.box(1800, 615, 450, 180, "4  Execution Agent", ["采集新 Scene 或执行已校验动作", "action_id 幂等"], BLUE, NAVY, body_size=20)
    writer = f.box(845, 930, 710, 170, "KG Writer（确定性、唯一写入口）", ["perception / planning / human review / execution", "拒绝任意 Cypher；提交后刷新镜像"], GRAY, GRAY_DARK, body_size=21)
    tools = f.box(120, 1000, 520, 175, "外部工具 / 服务", ["YOLO、VLM、RealSense", "当前通过 runner 注入；真实工具待接"], PURPLE, PURPLE_DARK, dashed=True, body_size=21)
    ros = f.box(1780, 1000, 500, 175, "ROS2 / MoveIt / PiPER", ["结构化命令，不接收自由文本", "当前 placeholder / planned"], PURPLE, PURPLE_DARK, dashed=True, body_size=21)

    f.arrow(user.cx, user.y + user.h, sup.cx, sup.y)
    for target, label in [(per, "perceive"), (plan, "plan"), (human, "review"), (exe, "acquire / execute")]:
        f.arrow(sup.cx, sup.y + sup.h, target.cx, target.y, label)
    f.arrow(per.cx, per.y + per.h, writer.x + 120, writer.y, "perception write")
    f.arrow(plan.cx, plan.y + plan.h, writer.x + 300, writer.y, "planning event")
    f.arrow(human.cx, human.y + human.h, writer.x + 500, writer.y, "human event")
    f.arrow(exe.cx, exe.y + exe.h, writer.x + 650, writer.y, "execution event")
    f.arrow(tools.x + tools.w, tools.cy, per.x, per.cy, "Observation", PURPLE_DARK, dashed=True)
    f.arrow(exe.cx, exe.y + exe.h, ros.cx, ros.y, "ActionPlan", PURPLE_DARK, dashed=True)
    f.arrow(writer.cx, writer.y, sup.cx, sup.y + sup.h, "KG refs + eligible/review IDs", GREEN_DARK)
    f.label(1200, 1275, "实线：当前编排与契约已实现    虚线：真实设备/外部服务待接    Agent 节点目前未绑定可见的 LLM runtime", 23, MUTED)
    return f


def figure_4() -> Figure:
    f = Figure("④ 动态建筑废弃物系统总体 Framework", "从感知证据到可审计状态、保守决策和结构化执行；执行反馈必须触发新 Scene 与再感知")
    f.band(70, 155, 2260, 230, "A  感知与证据层", BLUE, NAVY)
    cam = f.box(110, 225, 360, 115, "RealSense D435i", ["RGB / depth / intrinsics"], WHITE, NAVY, dashed=True, body_size=18)
    yolo = f.box(570, 225, 360, 115, "YOLO11s-seg", ["11类候选 / mask / confidence"], WHITE, NAVY, body_size=18)
    vlm = f.box(1030, 225, 360, 115, "受约束 VLM", ["属性一致性 / conservative fallback"], WHITE, PURPLE_DARK, body_size=18)
    geom = f.box(1490, 225, 360, 115, "RGB-D geometry", ["center / extent / occlusion / NEAR"], WHITE, NAVY, dashed=True, body_size=18)
    hum = f.box(1950, 225, 330, 115, "Human review", ["确认 / 禁止 / 丢弃"], ORANGE, ORANGE_DARK, body_size=18)
    f.arrow(cam.x + cam.w, cam.cy, yolo.x, yolo.cy)
    f.arrow(yolo.x + yolo.w, yolo.cy, vlm.x, vlm.cy)
    f.arrow(vlm.x + vlm.w, vlm.cy, geom.x, geom.cy)

    f.band(70, 430, 2260, 270, "B  可审计世界状态层  dynamic-waste-kg", GREEN, GREEN_DARK)
    mem = f.box(130, 510, 560, 145, "In-memory KnowledgeGraph", ["长期类别 + 短期实例 + 追加事件"], WHITE, GREEN_DARK, body_size=20)
    neo = f.box(820, 510, 470, 145, "Neo4j mirror", ["唯一约束 / 受控 Cypher / 三层查询"], WHITE, GREEN_DARK, body_size=20)
    snap = f.box(1420, 510, 390, 145, "UI snapshot", ["schema + nodes + relations + events"], WHITE, GREEN_DARK, body_size=19)
    ui = f.box(1940, 510, 330, 145, "React UI", ["监控 / 复核 / trace"], WHITE, GREEN_DARK, body_size=19)
    f.arrow(mem.x + mem.w, mem.cy, neo.x, neo.cy, "mirror")
    f.arrow(neo.x + neo.w, neo.cy, snap.x, snap.cy, "read / publish")
    f.arrow(snap.x + snap.w, snap.cy, ui.x, ui.cy)
    f.arrow(yolo.cx, yolo.y + yolo.h, mem.x + 120, mem.y, "Observation")
    f.arrow(geom.cx, geom.y + geom.h, mem.x + 430, mem.y, "DepthUpdate")
    # Human decision enters through the deterministic interrupt below, not directly through perception.

    f.band(70, 745, 2260, 230, "C  多智能体决策层  dynamic-waste-agent", GRAY, GRAY_DARK)
    sup = f.box(850, 775, 700, 85, "Supervisor conditional router", [], WHITE, NAVY, title_size=27)
    per = f.box(100, 880, 420, 75, "Perception", [], WHITE, NAVY, title_size=23)
    plan = f.box(650, 880, 450, 75, "Action Planning", [], WHITE, NAVY, title_size=23)
    intr = f.box(1260, 880, 390, 75, "Human interrupt", [], ORANGE, ORANGE_DARK, title_size=23)
    exe = f.box(1810, 880, 430, 75, "Execution", [], WHITE, NAVY, title_size=23)
    f.arrow(mem.x + 210, mem.y + mem.h, sup.cx, sup.y, "KG refs + control IDs")
    f.arrow(sup.cx - 250, sup.y + sup.h, per.cx, per.y, "perceive")
    f.arrow(sup.cx - 80, sup.y + sup.h, plan.cx, plan.y, "plan")
    f.arrow(sup.cx + 80, sup.y + sup.h, intr.cx, intr.y, "review")
    f.arrow(sup.cx + 250, sup.y + sup.h, exe.cx, exe.y, "acquire / execute")
    f.arrow(hum.cx, hum.y + hum.h, intr.cx, intr.y, "人工决定", ORANGE_DARK)
    f.arrow(intr.x, intr.cy - 15, mem.x + mem.w, mem.cy + 20, "HumanReviewEvent", ROSE_DARK)

    f.band(70, 1020, 2260, 240, "D  执行与反馈层  dynamic-waste-ros2 / simulation", PURPLE, PURPLE_DARK)
    feedback = f.box(150, 1100, 420, 115, "Execution feedback", ["success/failure + physical_started"], WHITE, ROSE_DARK, dashed=True, body_size=18)
    robot = f.box(720, 1100, 390, 115, "PiPER / simulator", ["真实动作或 dry-run"], WHITE, PURPLE_DARK, dashed=True, body_size=18)
    moveit = f.box(1260, 1100, 420, 115, "MoveIt / safety gate", ["确认 / 限位 / 碰撞 / 急停"], WHITE, PURPLE_DARK, dashed=True, body_size=18)
    bridge = f.box(1830, 1100, 420, 115, "ROS2 bridge", ["结构化 Action command"], WHITE, PURPLE_DARK, dashed=True, body_size=18)
    f.arrow(exe.cx, exe.y + exe.h, bridge.cx, bridge.y, "validated ActionPlan", PURPLE_DARK, dashed=True)
    f.arrow(bridge.x, bridge.cy, moveit.x + moveit.w, moveit.cy, color=PURPLE_DARK, dashed=True)
    f.arrow(moveit.x, moveit.cy, robot.x + robot.w, robot.cy, color=PURPLE_DARK, dashed=True)
    f.arrow(robot.x, robot.cy, feedback.x + feedback.w, feedback.cy, color=ROSE_DARK, dashed=True)
    f.arrow(feedback.cx, feedback.y, mem.x + 100, mem.y + mem.h, "", ROSE_DARK, dashed=True)
    f.label(360, 1045, "ExecutionEvent -> Scene失效 -> 再感知", 19, ROSE_DARK)
    f.label(1200, 1320, "当前已验证边界：受控二维实例分割 → 可审计知识状态原型；RGB-D、ROS2 与真实抓取仍需 Ubuntu/硬件验证", 23, RED)
    return f


def render_all(output_dir: Path) -> None:
    figures: Iterable[tuple[str, Figure]] = [
        ("fig1_three_layer_knowledge_graph", figure_1()),
        ("fig2_low_confidence_human_review_flow", figure_2()),
        ("fig3_multi_agent_architecture", figure_3()),
        ("fig4_full_project_framework", figure_4()),
    ]
    for stem, figure in figures:
        figure.save(output_dir / stem)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render_all(root / "docs" / "architecture_review" / "figures")
