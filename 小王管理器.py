# -*- coding: utf-8 -*-
"""
小王管理器 —— 王者荣耀账号记录工具（本地单机版） v1.1.4

结构（5 层路径）：
    登录方式(Q=QQ区 / V=微信区) -> 账号(qq号或vx号) -> 平台(安卓/iOS) -> 小区(第几区+小区名) -> 昵称

功能：
- 左侧树含「全部账号」与「大号」两个顶级节点；小区节点直接显示 小区-昵称
- 小区字段：昵称、等级(1-30)、段位、生日(仅月日)、荣耀水晶累计次数、
  剩余夺宝券、战令皮肤领取、2券兑换、礼册领取、动态活动列
- 5连抽联动：水晶+5、券-4（一次操作）；支持 +1/-1 手动微调
- 大号为小区级属性（可多个）：编辑小区勾选，左侧树「大号」节点金色高亮，表格行底色突出
- 双击「标记」列可给小区打/取消 ★ 自定义标记；筛选「只看标记」随列名联动
- 添加账号向导：选登录方式 -> 输入/复用账号 -> 选平台 -> 设置第一个小区
- 新赛季一键重置 2券/战令皮/段位；礼册单独一键重置；搜索/筛选；底部统计条；启动生日提醒
- 列头可拖动排序、双击重命名、列设置显示/隐藏；行底色可自定义开关与配色
- 活动列管理按钮独立在右侧表格上方工具栏；表头只显示活动名称
- 左右分隔条可拖动调节目录树宽度并记忆
- 改动即时自动保存到同目录 JSON 文件，启动自动读取（自动迁移旧数据）
运行：python 小王管理器.py（或双击 启动小王管理器.bat）
"""

import json
import os
import re
import sys
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
import tkinter.font as tkfont
from datetime import datetime, date

APP_TITLE = "小王管理器 v1.1.4"
LOGINS = ["Q", "V"]                 # 登录方式：Q=QQ区, V=微信区
LOGIN_LABELS = {"Q": "QQ", "V": "VX"}
PLATFORMS = ["安卓", "iOS"]         # 平台
DATA_FILE = "小王管理器数据.json"
RANK_LIST = ["倔强青铜", "秩序白银", "荣耀黄金", "尊贵铂金",
             "永恒钻石", "至尊星耀", "最强王者", "荣耀·王者"]
COL_TYPE_NAMES = {"boolean": "✓对勾", "text": "文本", "number": "数字", "date": "日期"}
COL_TYPES = ["boolean", "text", "number", "date"]


def login_label(login):
    """登录方式显示名：Q -> QQ，V -> VX（数据里仍存 Q/V）"""
    return LOGIN_LABELS.get(login, login or "")

FIXED_COLUMNS = [
    ("main_star", "标记", 55),
    ("login", "登录", 55),
    ("account", "账号", 120),
    ("platform", "平台", 65),
    ("zone", "小区", 130),
    ("nickname", "昵称", 90),
    ("level", "等级", 55),
    ("rank", "段位", 95),
    ("birthday", "生日", 70),
    ("crystal", "水晶次数", 95),
    ("tickets", "剩余券", 75),
    ("skin", "战令皮", 75),
    ("two", "2券", 85),
    ("gift", "礼册", 55),
]

# 固定列（始终显示、不可隐藏）：账号、小区、昵称
LOCKED_COLUMNS = ["account", "zone", "nickname"]


def data_path():
    # 打包成 exe 后，数据文件放在 exe 所在目录；源码运行时放在 py 文件所在目录
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, DATA_FILE)


def _setup_frozen_tk():
    # 打包成 exe 后，把内嵌的 tcl/tk 图形库路径告诉 tkinter（Store 版 Python 的
    # tcl 目录不在标准位置，PyInstaller 默认收集不到，需要这里显式指定）
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            tcl_lib = os.path.join(meipass, "tcl", "tcl8.6")
            tk_lib = os.path.join(meipass, "tcl", "tk8.6")
            if os.path.isdir(tcl_lib):
                os.environ["TCL_LIBRARY"] = tcl_lib
            if os.path.isdir(tk_lib):
                os.environ["TK_LIBRARY"] = tk_lib


_setup_frozen_tk()


# ------------------------------------------------------------- 工具函数
def zone_label(z):
    """小区显示名：1区-XXXX / 1区 / （未命名小区）"""
    try:
        no = int(z.get("zone_no", 0) or 0)
    except (TypeError, ValueError):
        no = 0
    name = (z.get("zone_name", "") or "").strip()
    if name:
        return "%d区-%s" % (no, name)
    if no:
        return "%d区" % no
    return name or "（未命名小区）"


def tree_zone_text(z):
    """左侧目录树的小区节点文本：区号按 3 位补空格，使「区号-区名」间的连字符垂直对齐。
    例：' 14区-永生之血-输了会琺人' 与 '144区-无心人偶-等我刷骷髅头' 的连字符在同一列"""
    try:
        no = int(z.get("zone_no", 0) or 0)
    except (TypeError, ValueError):
        no = 0
    name = (z.get("zone_name", "") or "").strip() or "（未命名小区）"
    nick = (z.get("nickname", "") or "").strip()
    text = (str(no) if no else "").rjust(3, " ") + "区-" + name
    if nick:
        text += "-" + nick
    return text


def split_login_platform(zone):
    """旧版大区(安卓Q等) -> (登录方式, 平台)"""
    if zone == "安卓Q":
        return "Q", "安卓"
    if zone == "安卓V":
        return "V", "安卓"
    if zone == "iOS Q":
        return "Q", "iOS"
    if zone == "iOS V":
        return "V", "iOS"
    return "Q", "安卓"


def parse_old_zone_name(name):
    """旧版小区名("1区-XXXX" / "2") -> (第几区, 小区名)"""
    m = re.match(r"^(\d+)区-(.*)$", name or "")
    if m:
        return int(m.group(1)), m.group(2)
    m = re.match(r"^(\d+)$", name or "")
    if m:
        return int(m.group(1)), ""
    return 0, (name or "")


# ------------------------------------------------------------- 自绘表格
class Grid(tk.Canvas):
    """自绘表格（替代 ttk.Treeview）：
    - Excel 风格行间浅色网格线
    - 账号分隔行压成 3px 细横线（贯穿整行），普通行保持正常高度
    - 整体缩放：字号/行高/列宽按 zoom 比例联动
    对外接口：set_columns / set_rows / clear / iids / set_cell / selected_key /
              region_at / col_at_x / row_at_y / on_select / on_double_row /
              on_heading_double / on_heading_release / on_column_resize
    """
    def __init__(self, master, **kw):
        super().__init__(master, highlightthickness=0, bd=0,
                         background="#ffffff", **kw)
        self._cols = []            # [{"cid","title","width"}]
        self._rows = []            # [{"values","tag","key"}]
        self._tag_bg = {"bg_bad": "#fff3e6", "bg_good": "#e8f7e8",
                        "bg_main": "#fdf3e0", "sep": "#b0b0b0"}
        self._zoom = 100
        self._row_h = 20
        self._header_h = 28
        self._sep_h = 3
        self._selected = None      # 行索引
        self._press_col = None
        self._resize_col = None    # 正在拖宽度的列索引
        self._resize_x0 = 0
        self._resize_w0 = 0
        self._font_cache = {}
        self.on_select = None      # 回调(idx)
        self.on_double_row = None  # 回调(idx, cid)
        self.on_heading_double = None  # 回调(cid)
        self.on_heading_release = None  # 回调(from_cid, to_cid)
        self.on_column_resize = None    # 回调(cid, width_px)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-1>", self._on_double)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Motion>", self._on_motion)
        self.bind("<MouseWheel>", self._on_wheel)          # Windows / macOS
        self.bind("<Button-4>", self._on_wheel_linux)      # X11 向上
        self.bind("<Button-5>", self._on_wheel_linux)      # X11 向下
        self.configure(yscrollincrement=self._row_h)       # 滚轮按行滚动

    # ---------------- 配置 ----------------
    def _on_wheel(self, event):
        """鼠标滚轮上下滚动表格（每格滚 3 行，配合 scrollincrement=行高）"""
        steps = int(getattr(event, "delta", 0) / 120) or 0
        if steps:
            self.yview("scroll", -steps * 3, "units")

    def _on_wheel_linux(self, event):
        """X11 老式滚轮事件（Button-4 向上 / Button-5 向下）"""
        self.yview("scroll", -3 if event.num == 4 else 3, "units")

    def set_zoom(self, zoom):
        self._zoom = max(60, min(200, zoom))
        self._row_h = max(16, int(20 * self._zoom / 100))
        self._header_h = self._row_h + 8
        self._font_cache.clear()
        self.configure(yscrollincrement=self._row_h)  # 缩放后行高变化，滚轮步进同步
        self.redraw()

    def set_tag_bg(self, tag, color):
        self._tag_bg[tag] = color
        self.redraw()

    def set_columns(self, cols):
        """cols: [(cid, title, width_px)]"""
        self._cols = [{"cid": c, "title": t, "width": max(20, int(w))}
                      for c, t, w in cols]
        self.redraw()

    def set_rows(self, rows):
        """rows: [(values(list), tag(str|None), key(tuple|None))]"""
        self._rows = [{"values": v, "tag": t, "key": k} for v, t, k in rows]
        self._selected = None
        self.redraw()

    def clear(self):
        self._rows = []
        self._selected = None
        self.redraw()

    def iids(self):
        return ["i%d" % i for i in range(len(self._rows))]

    def selected_key(self):
        if self._selected is None or not (0 <= self._selected < len(self._rows)):
            return None
        return self._rows[self._selected]["key"]

    def set_cell(self, idx, cid, value):
        if not (0 <= idx < len(self._rows)):
            return
        for i, c in enumerate(self._cols):
            if c["cid"] == cid:
                if idx < len(self._rows):
                    vals = self._rows[idx]["values"]
                    while len(vals) <= i:
                        vals.append("")
                    vals[i] = value
                break
        self.redraw()

    def set_row_tag(self, idx, tag):
        """更新某行的底色 tag（如对勾切换后行底色变化）"""
        if 0 <= idx < len(self._rows):
            self._rows[idx]["tag"] = tag
            self.redraw()

    # ---------------- 命中测试（坐标已按滚动偏移换算） ----------------
    def region_at(self, x, y):
        if y < self._header_h:
            return "heading"
        return "cell" if self.row_at_y(y) is not None else None

    def col_at_x(self, x):
        x0 = 0
        for c in self._cols:
            if x0 <= x < x0 + c["width"]:
                return c["cid"]
            x0 += c["width"]
        return None

    def _edge_at(self, x):
        """返回鼠标所在列边界（x 距某列右边界≤4px）的列索引；否则 None"""
        x0 = 0
        for i, c in enumerate(self._cols):
            x0 += c["width"]
            if abs(x - x0) <= 4:
                return i
        return None

    def row_at_y(self, y):
        y -= self._header_h
        for idx, r in enumerate(self._rows):
            h = self._sep_h if r["tag"] == "sep" else self._row_h
            if y < h:
                return idx
            y -= h
        return None

    # ---------------- 绘制 ----------------
    def redraw(self):
        self.delete("all")
        total_w = sum(c["width"] for c in self._cols)
        if not self._cols:
            self.configure(scrollregion=(0, 0, 0, 0))
            return
        head_font = self._font(self._row_h - 6)
        # 表头
        x0 = 0
        for c in self._cols:
            self.create_rectangle(x0, 0, x0 + c["width"], self._header_h,
                                  fill="#f2f2f2", outline="#c9c9c9")
            self.create_text(x0 + c["width"] / 2, self._header_h / 2,
                             text=c["title"], anchor="center",
                             font=head_font, fill="#333333")
            x0 += c["width"]
        # 行
        body_font = self._font(self._row_h - 8)
        y = self._header_h
        for idx, r in enumerate(self._rows):
            is_sep = r["tag"] == "sep"
            h = self._sep_h if is_sep else self._row_h
            bg = self._tag_bg.get(r["tag"], "#ffffff") if r["tag"] else "#ffffff"
            if is_sep:
                # 分隔行 = 贯穿整行的细横线
                self.create_rectangle(0, y, total_w, y + h, fill=bg, outline="")
            else:
                x0 = 0
                for ci, c in enumerate(self._cols):
                    self.create_rectangle(x0, y, x0 + c["width"], y + h,
                                          fill=bg, outline="#e3e3e3")
                    val = r["values"][ci] if ci < len(r["values"]) else ""
                    if val:
                        self.create_text(
                            x0 + c["width"] / 2, y + h / 2,
                            text=self._fit_text(str(val), c["width"], body_font),
                            anchor="center", font=body_font, fill="#222222")
                    x0 += c["width"]
                if idx == self._selected:
                    self.create_rectangle(0, y, total_w, y + h,
                                          outline="#1a73e8", width=2)
            y += h
        self.configure(scrollregion=(0, 0, total_w, y))

    def _font(self, size):
        size = max(7, size)
        if size not in self._font_cache:
            self._font_cache[size] = tkfont.Font(family="Microsoft YaHei", size=size)
        return self._font_cache[size]

    def _fit_text(self, s, width, fnt):
        if fnt.measure(s) <= width - 8:
            return s
        while s and fnt.measure(s + "…") > width - 8:
            s = s[:-1]
        return s + "…" if s else ""

    # ---------------- 事件 ----------------
    def _on_motion(self, event):
        """列头边界悬停 -> 显示左右拉伸光标"""
        if self._resize_col is not None:
            return
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        if y < self._header_h and self._edge_at(x) is not None:
            self.config(cursor="sb_h_double_arrow")
        else:
            self.config(cursor="")

    def _on_press(self, event):
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        if y < self._header_h:
            edge = self._edge_at(x)
            if edge is not None:
                # 拖动列边界：调整列宽
                self._resize_col = edge
                self._resize_x0 = x
                self._resize_w0 = self._cols[edge]["width"]
                return
            self._press_col = self.col_at_x(x)
            return
        idx = self.row_at_y(y)
        if idx is not None:
            self._selected = idx
            self.redraw()
            if self.on_select:
                self.on_select(idx)

    def _on_drag(self, event):
        """拖动列头边界实时调整列宽"""
        if self._resize_col is None:
            return
        x = self.canvasx(event.x)
        new_w = max(30, self._resize_w0 + (x - self._resize_x0))
        if new_w != self._cols[self._resize_col]["width"]:
            self._cols[self._resize_col]["width"] = int(new_w)
            self.redraw()

    def _on_release(self, event):
        if self._resize_col is not None:
            c = self._cols[self._resize_col]
            if self.on_column_resize:
                self.on_column_resize(c["cid"], c["width"])
            self._resize_col = None
            self.config(cursor="")
            return
        if self._press_col:
            x, y = self.canvasx(event.x), self.canvasy(event.y)
            to = self.col_at_x(x) if y < self._header_h else None
            if to and to != self._press_col and self.on_heading_release:
                self.on_heading_release(self._press_col, to)
            self._press_col = None

    def _on_double(self, event):
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        if y < self._header_h:
            cid = self.col_at_x(x)
            if cid and self.on_heading_double:
                self.on_heading_double(cid)
            return
        idx = self.row_at_y(y)
        if idx is not None:
            cid = self.col_at_x(x)
            self._selected = idx
            self.redraw()
            if self.on_select:
                self.on_select(idx)
            if self.on_double_row:
                self.on_double_row(idx, cid)


# ------------------------------------------------------------- 数据层
class DataStore:
    def __init__(self, path):
        self.path = path
        self.data = self._load()
        self._ensure_column_meta()
        # 若发生了旧版数据迁移，启动时立即保存为新版本
        if getattr(self, "_needs_save", False):
            self.save()

    def _default(self):
        return {"version": 3, "activity_columns": [], "accounts": [],
                "column_order": [c[0] for c in FIXED_COLUMNS],
                "hidden_columns": ["login", "platform"],
                "tree_width": 250, "auto_sort": True, "zoom": 100,
                "last_platform": "安卓"}

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "accounts" in data:
                    old_v = int(data.get("version", 1))
                    data = self._migrate(data)
                    if old_v < 3:
                        self._needs_save = True
                    return data
            except Exception:
                pass
        return self._default()

    def _migrate(self, data):
        """v1 -> v2：大区拆为登录方式+平台、小区名拆区号+区名；v2 -> v3：大号由账号级改为小区级"""
        if int(data.get("version", 1)) < 2:
            for a in data.get("accounts", []):
                if "platforms" in a:
                    continue
                login, platform = split_login_platform(a.get("zone", "安卓Q"))
                a["login"] = login
                a.pop("zone", None)
                zones = []
                for z in a.get("zones", []):
                    no, zname = parse_old_zone_name(z.get("name", ""))
                    z["zone_no"] = no
                    z["zone_name"] = zname
                    z.pop("name", None)
                    zones.append(z)
                a["platforms"] = [{"id": uuid.uuid4().hex[:8],
                                   "platform": platform, "zones": zones}]
                a.pop("zones", None)
            data["version"] = 2
        if int(data.get("version", 2)) < 3:
            # 账号级大号 -> 小区级大号：账号是大号则其全部小区都设为小区级大号
            for a in data.get("accounts", []):
                am = bool(a.pop("is_main", False))
                for p in a.get("platforms", []):
                    for z in p.get("zones", []):
                        z["is_main"] = bool(z.get("is_main", am))
            data["version"] = 3
        return data

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ---------- 账号 ----------
    def add_account(self, login, name, is_main=False):
        # is_main 兼容参数：大号已改为小区级（v3），账号本身不再保存大号身份
        acc = {"id": uuid.uuid4().hex[:8], "login": login, "name": name,
               "platforms": []}
        self.data["accounts"].append(acc)
        return acc["id"]

    def get_account(self, acc_id):
        for a in self.data["accounts"]:
            if a["id"] == acc_id:
                return a
        return None

    def find_account(self, login, name):
        for a in self.data["accounts"]:
            if a["login"] == login and a["name"] == name:
                return a
        return None

    def update_account(self, acc_id, login, name, is_main=None):
        a = self.get_account(acc_id)
        if a:
            a["login"] = login
            a["name"] = name
            # is_main 已改为小区级（v3），账号不再保存大号身份

    def delete_account(self, acc_id):
        self.data["accounts"] = [a for a in self.data["accounts"] if a["id"] != acc_id]

    # ---------- 平台 ----------
    def get_platform(self, acc_id, plat_id):
        a = self.get_account(acc_id)
        if a:
            for p in a["platforms"]:
                if p["id"] == plat_id:
                    return p
        return None

    def find_platform(self, acc_id, platform):
        a = self.get_account(acc_id)
        if a:
            for p in a["platforms"]:
                if p["platform"] == platform:
                    return p
        return None

    def add_platform(self, acc_id, platform):
        if self.find_platform(acc_id, platform):
            return None
        a = self.get_account(acc_id)
        if not a:
            return None
        p = {"id": uuid.uuid4().hex[:8], "platform": platform, "zones": []}
        a["platforms"].append(p)
        return p["id"]

    def delete_platform(self, acc_id, plat_id):
        a = self.get_account(acc_id)
        if a:
            a["platforms"] = [p for p in a["platforms"] if p["id"] != plat_id]

    # ---------- 小区 ----------
    def add_zone(self, acc_id, plat_id, zone_no, zone_name):
        p = self.get_platform(acc_id, plat_id)
        if not p:
            return None
        z = {"id": uuid.uuid4().hex[:8], "zone_no": int(zone_no),
             "zone_name": zone_name,
             "nickname": "", "level": 1, "rank": "", "birthday": "",
             "crystal_count": 0, "tickets": 0,
             "battlepass_skin": False, "two_tickets": False,
             "gift_claimed": False, "marked": False, "is_main": False,
             "activities": {}}
        p["zones"].append(z)
        return z["id"]

    def get_zone(self, acc_id, zone_id):
        """返回 (platform, zone)，找不到返回 None"""
        a = self.get_account(acc_id)
        if a:
            for p in a["platforms"]:
                for z in p["zones"]:
                    if z["id"] == zone_id:
                        return p, z
        return None

    def update_zone_fields(self, acc_id, zone_id, fields):
        r = self.get_zone(acc_id, zone_id)
        if r:
            _p, z = r
            for k, v in fields.items():
                z[k] = v

    def delete_zone(self, acc_id, zone_id):
        a = self.get_account(acc_id)
        if a:
            for p in a["platforms"]:
                p["zones"] = [z for z in p["zones"] if z["id"] != zone_id]

    # ---------- 快捷操作 ----------
    def five_pull(self, acc_id, zone_id):
        r = self.get_zone(acc_id, zone_id)
        if r:
            _p, z = r
            z["crystal_count"] = int(z.get("crystal_count", 0)) + 5
            z["tickets"] = max(0, int(z.get("tickets", 0)) - 4)

    def tickets_minus4(self, acc_id, zone_id):
        r = self.get_zone(acc_id, zone_id)
        if r:
            _p, z = r
            z["tickets"] = max(0, int(z.get("tickets", 0)) - 4)

    def reset_two_tickets(self):
        """新赛季：2券→未兑换、战令皮→未领、段位→清空"""
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    z["two_tickets"] = False
                    z["battlepass_skin"] = False
                    z["rank"] = ""

    def reset_gift(self):
        """重置礼册：全部小区→未领取（与新赛季分开重置）"""
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    z["gift_claimed"] = False

    # ---------- 活动列 ----------
    def add_activity_column(self, name, ctype):
        if self.get_activity_column(name):
            return False
        self.data["activity_columns"].append({"name": name, "type": ctype})
        default = "" if ctype != "boolean" else False
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    z["activities"][name] = default
        return True

    def get_activity_column(self, name):
        for c in self.data["activity_columns"]:
            if c["name"] == name:
                return c
        return None

    def delete_activity_column(self, name):
        self.data["activity_columns"] = [c for c in self.data["activity_columns"] if c["name"] != name]
        if "column_titles" in self.data:
            self.data["column_titles"].pop(name, None)
        if "column_widths" in self.data:
            self.data["column_widths"].pop(name, None)
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    z["activities"].pop(name, None)

    def rename_activity_column(self, old, new):
        if old == new:
            return True
        if self.get_activity_column(new):
            return False
        for c in self.data["activity_columns"]:
            if c["name"] == old:
                c["name"] = new
        if "column_titles" in self.data and old in self.data["column_titles"]:
            self.data["column_titles"][new] = self.data["column_titles"].pop(old)
        if "column_widths" in self.data and old in self.data["column_widths"]:
            self.data["column_widths"][new] = self.data["column_widths"].pop(old)
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    if old in z["activities"]:
                        z["activities"][new] = z["activities"].pop(old)
        return True

    # ---------- 列显示配置（顺序 / 显隐 / 自定义标题） ----------
    def _ensure_column_meta(self):
        if "column_order" not in self.data:
            self.data["column_order"] = [c[0] for c in FIXED_COLUMNS]
        if "hidden_columns" not in self.data:
            self.data["hidden_columns"] = ["login", "platform"]
        if "column_titles" not in self.data:
            self.data["column_titles"] = {}
        if "column_widths" not in self.data:
            self.data["column_widths"] = {}
        if "row_colors" not in self.data:
            self.data["row_colors"] = {
                "enabled": True,
                "bad": "#fff3e6",    # 有对勾列未领/未兑换
                "good": "#e8f7e8",   # 对勾列全部已领/已兑换
                "main": "#fdf3e0",   # 大号账号行
            }
        if "tree_width" not in self.data:
            self.data["tree_width"] = 250
        if "auto_sort" not in self.data:
            self.data["auto_sort"] = True
        if "zoom" not in self.data:
            self.data["zoom"] = 100
        if "last_platform" not in self.data:
            self.data["last_platform"] = "安卓"
        fixed = [c[0] for c in FIXED_COLUMNS]
        names = [c["name"] for c in self.data["activity_columns"]]
        for c in self.data["activity_columns"]:
            if c["name"] not in self.data["column_order"]:
                self.data["column_order"].append(c["name"])
        self.data["column_order"] = [x for x in self.data["column_order"] if x in fixed or x in names]
        self.data["hidden_columns"] = [x for x in self.data["hidden_columns"]
                                       if x in self.data["column_order"] and x not in LOCKED_COLUMNS]
        self.data["column_titles"] = {k: v for k, v in self.data["column_titles"].items()
                                      if k in self.data["column_order"]}

    def get_column_order(self):
        self._ensure_column_meta()
        return list(self.data["column_order"])

    def get_hidden_columns(self):
        self._ensure_column_meta()
        return list(self.data["hidden_columns"])

    def set_column_order(self, order):
        # 顺序始终保留全部列（隐藏列也在全量顺序里，便于恢复显示）
        full = [c[0] for c in FIXED_COLUMNS] + [c["name"] for c in self.data["activity_columns"]]
        merged = [x for x in order if x in full]
        for x in full:
            if x not in merged:
                merged.append(x)
        self.data["column_order"] = merged

    def set_hidden_columns(self, hidden):
        # 固定列不可隐藏
        self.data["hidden_columns"] = [h for h in hidden if h not in LOCKED_COLUMNS]

    def get_column_title(self, cid):
        """数据列的自定义显示名（无自定义时返回空串）"""
        self._ensure_column_meta()
        return self.data["column_titles"].get(cid, "")

    def set_column_title(self, cid, title):
        """设置数据列的自定义显示名；传空则恢复默认"""
        self._ensure_column_meta()
        title = (title or "").strip()
        if title:
            self.data["column_titles"][cid] = title
        else:
            self.data["column_titles"].pop(cid, None)

    def get_column_width(self, cid):
        """自定义列宽（基础宽度，0 表示未设置/用默认）"""
        self._ensure_column_meta()
        return int(self.data["column_widths"].get(cid, 0) or 0)

    def set_column_width(self, cid, width):
        """记录自定义列宽（基础宽度，不随缩放变化）；传 0/负值恢复默认"""
        self._ensure_column_meta()
        width = int(width)
        if width <= 0:
            self.data["column_widths"].pop(cid, None)
        else:
            self.data["column_widths"][cid] = max(30, width)

    def get_last_platform(self):
        """上次添加账号/小区时选择的平台（iOS/安卓）"""
        self._ensure_column_meta()
        return self.data.get("last_platform", "安卓")

    def set_last_platform(self, platform):
        self._ensure_column_meta()
        self.data["last_platform"] = platform if platform in PLATFORMS else "安卓"

    # ---------- 查询 / 统计 ----------
    def all_zone_entries(self):
        entries = []
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    entries.append((a, p, z))
        return entries

    def stats(self):
        n_zones = 0
        n_main = 0
        n_two = 0
        n_skin = 0
        n_tickets = 0
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    n_zones += 1
                    if z.get("is_main"):
                        n_main += 1
                    if not z["two_tickets"]:
                        n_two += 1
                    if not z["battlepass_skin"]:
                        n_skin += 1
                    n_tickets += int(z.get("tickets", 0))
        return {"zones": n_zones, "main_zones": n_main, "two_unclaimed": n_two,
                "skin_unclaimed": n_skin, "tickets": n_tickets}

    def birthdays_soon(self, days=3):
        today = date.today()
        out = []
        for a in self.data["accounts"]:
            for p in a["platforms"]:
                for z in p["zones"]:
                    b = z.get("birthday", "") or ""
                    if len(b) == 5 and b[2] == "-":
                        try:
                            m, d = int(b[:2]), int(b[3:])
                        except ValueError:
                            continue
                        try:
                            diff = (date(today.year, m, d) - today).days
                            if diff < 0:
                                diff = (date(today.year + 1, m, d) - today).days
                        except ValueError:
                            continue
                        if 0 <= diff <= days:
                            out.append((a, p, z, b, diff))
        out.sort(key=lambda x: x[4])
        return out


# ------------------------------------------------------------- 界面
class App:
    def __init__(self, root, store, auto_remind=True):
        self.root = root
        self.store = store
        self.row_keys = []              # 表格行 -> (acc_id, zone_id)
        self.col_order = store.get_column_order()
        self.hidden = set(store.get_hidden_columns())
        self.zoom = int(self.store.data.get("zoom", 100))
        self.root.bind("<Control-MouseWheel>", self._on_zoom)
        self._build_style()
        self._build_toolbar()
        self._build_main()
        self._build_actions()
        self._build_stats()
        self._apply_zoom()
        self.refresh_all()
        if auto_remind:
            self.check_birthday_reminder()

    # ---------------- 界面构建 ----------------
    def _build_style(self):
        self.table = None
        self.tree = None
        # 左侧目录树使用独立样式：固定字号与行高，不随 Ctrl+滚轮缩放
        st = ttk.Style(self.root)
        st.configure("Sidebar.Treeview", font=("Microsoft YaHei", 9), rowheight=20, indent=20)
        st.configure("Sidebar.Treeview.Item", padding=(2, 2))

    # ---------------- 缩放（Ctrl + 滚轮） ----------------
    def _on_zoom(self, event):
        try:
            delta = 1 if event.delta > 0 else -1
        except AttributeError:
            delta = -1 if getattr(event, "num", 0) == 5 else 1
        new_zoom = min(200, max(60, self.zoom + 5 * delta))
        if new_zoom != self.zoom:
            self.zoom = new_zoom
            self.store.data["zoom"] = new_zoom
            self.store.save()
            self._apply_zoom()

    def _apply_zoom(self):
        """整体缩放：右侧表格字号/行高/列宽等比缩放；左侧目录树保持原大小"""
        if self.table is not None:
            self.table.set_zoom(self.zoom)
            self._apply_column_widths()

    def _apply_column_widths(self):
        """列宽按缩放比例整体放大/缩小（基础宽度 × zoom%）"""
        col_defs = []
        for cid in self._visible_columns():
            text, width = self._col_meta(cid)
            col_defs.append((cid, text, max(40, int(width * self.zoom / 100))))
        self.table.set_columns(col_defs)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(8, 6))
        bar.pack(fill="x")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.apply_filters())
        ttk.Label(bar, text="搜索:").pack(side="left")
        ttk.Entry(bar, textvariable=self.search_var, width=16).pack(side="left", padx=(2, 8))

        self.auto_sort_var = tk.BooleanVar(value=bool(self.store.data.get("auto_sort", True)))

        self.filter_mode = "all"  # all | two | skin | marked | tickets
        self.filter_var = tk.StringVar()
        ttk.Label(bar, text="筛选:").pack(side="left")
        self.filter_combo = ttk.Combobox(bar, textvariable=self.filter_var,
                                         state="readonly", width=12)
        self.filter_combo.pack(side="left", padx=(2, 4))
        self._refresh_filter_combo()
        self.filter_combo.bind("<<ComboboxSelected>>", self._on_filter_selected)
        ttk.Button(bar, text="刷新", command=self.apply_filters).pack(side="left", padx=(0, 10))

        ttk.Button(bar, text="＋ 添加账号", command=self.add_account_dialog).pack(side="left", padx=3)
        ttk.Button(bar, text="＋ 添加小区", command=self.add_zone_dialog).pack(side="left", padx=3)
        ttk.Button(bar, text="新赛季重置", command=self.reset_two_tickets).pack(side="left", padx=3)
        ttk.Button(bar, text="重置礼册", command=self.reset_gift).pack(side="left", padx=3)
        ttk.Button(bar, text="打开数据文件夹", command=self.open_data_folder).pack(side="left", padx=3)

        # 右上角：上方显示当前日期时间，下方显示已保存时间
        right = ttk.Frame(bar)
        right.pack(side="right")
        self.clock_label = ttk.Label(right, text="", foreground="#8a94a3")
        self.clock_label.pack(anchor="e")
        self.save_label = ttk.Label(right, text="", foreground="#8a94a3")
        self.save_label.pack(anchor="e")
        self._set_saved_text()
        self._update_clock()

    def _on_filter_selected(self, _ev=None):
        try:
            self.filter_mode = ["all", "two", "skin", "marked", "tickets"][
                self.filter_combo.current()]
        except (tk.TclError, IndexError):
            self.filter_mode = "all"
        self.apply_filters()

    def _refresh_filter_combo(self):
        """筛选选项文字同步「标记」列的自定义列名"""
        title = self._col_meta("main_star")[0]
        opts = ["全部", "2券未兑换", "战令皮未领", "只看%s" % title, "剩余券≥5"]
        try:
            self.filter_combo["values"] = opts
            idx = ["all", "two", "skin", "marked", "tickets"].index(self.filter_mode)
            self.filter_var.set(opts[idx])
        except (tk.TclError, ValueError):
            pass

    def _update_clock(self):
        try:
            self.clock_label.config(text=datetime.now().strftime("%Y-%m-%d-%H:%M"))
            self.root.after(1000, self._update_clock)
        except tk.TclError:
            pass

    def _build_main(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        # 左右可拖动的分隔条（Panedwindow）：左侧目录树宽度可手动调节并记忆
        paned = ttk.Panedwindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True)
        tw = int(self.store.data.get("tree_width", 250))

        # 左侧树（登录方式 -> 账号 -> 平台 -> 小区-昵称）
        tree_frame = ttk.Frame(paned, width=tw)
        tree_frame.pack_propagate(False)
        paned.add(tree_frame, weight=0)
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse",
                                 style="Sidebar.Treeview")
        ys = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.tree.tag_configure("main", foreground="#b26a12")
        self.tree.bind("<Double-1>", self._on_tree_double)

        # 右侧表格区（顶部工具条 + 全量表格）
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=1)

        # 拖动分隔条结束（松开在 sash 上）时记住左侧树宽度
        def _save_tree_width(_e=None):
            try:
                w = int(tree_frame.winfo_width())
                if 120 <= w <= 900:
                    self.store.data["tree_width"] = w
                    self.store.save()
            except Exception:
                pass
        paned.bind("<ButtonRelease-1>", _save_tree_width)

        tbar = ttk.Frame(table_frame, padding=(0, 2))
        tbar.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        ttk.Label(tbar, text="活动列:").pack(side="left", padx=(0, 4))

        def _toggle_auto_sort():
            self.store.data["auto_sort"] = bool(self.auto_sort_var.get())
            self.store.save()
            self.apply_filters()

        ttk.Checkbutton(tbar, text="自动排序", variable=self.auto_sort_var,
                        command=_toggle_auto_sort).pack(side="left", padx=(0, 4))
        ttk.Button(tbar, text="列设置（显示/隐藏）",
                   command=self.show_columns_dialog).pack(side="left", padx=3)
        ttk.Button(tbar, text="管理活动列（添加/改名/删除）",
                   command=self.manage_columns_dialog).pack(side="left", padx=3)
        ttk.Button(tbar, text="底色设置",
                   command=self.row_colors_dialog).pack(side="left", padx=3)
        ttk.Label(tbar, text="拖列头换序/拖边界调宽；双击列名重命名",
                  foreground="#8a94a3").pack(side="left", padx=(8, 0))

        # 自绘表格（Excel 风格网格线 + 分隔细线 + 整体缩放）
        self.table = Grid(table_frame)
        self.table.on_select = lambda _idx: self._on_table_select()
        self.table.on_double_row = self._on_row_double
        self.table.on_heading_double = self._on_heading_double
        self.table.on_heading_release = self._on_col_swap
        self.table.on_column_resize = self._on_column_resize
        vs = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        hs = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.table.grid(row=1, column=0, sticky="nsew")
        vs.grid(row=1, column=1, sticky="ns")
        hs.grid(row=2, column=0, sticky="ew")
        table_frame.rowconfigure(1, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self._apply_row_colors()

    def _build_actions(self):
        bar = ttk.Frame(self.root, padding=(8, 2))
        bar.pack(fill="x")
        ttk.Label(bar, text="选中小区后:").pack(side="left", padx=(0, 6))
        self.btn_five = ttk.Button(bar, text="⚡5连抽（水晶+5·券-4）", command=self.five_pull_selected, state="disabled")
        self.btn_five.pack(side="left", padx=3)
        self.btn_m4 = ttk.Button(bar, text="券-4", command=self.tickets_minus4_selected, state="disabled")
        self.btn_m4.pack(side="left", padx=3)
        self.btn_edit = ttk.Button(bar, text="编辑", command=self.edit_selected, state="disabled")
        self.btn_edit.pack(side="left", padx=3)
        self.btn_del = ttk.Button(bar, text="删除", command=self.delete_selected, state="disabled")
        self.btn_del.pack(side="left", padx=3)

    def _build_stats(self):
        self.stats_var = tk.StringVar()
        ttk.Label(self.root, textvariable=self.stats_var, padding=(10, 6),
                  background="#f2f5f9", foreground="#3a4656", anchor="w").pack(fill="x")

    # ---------------- 数据刷新 ----------------
    def refresh_all(self):
        self.rebuild_tree()
        self.apply_filters()
        self.update_stats()

    def _set_saved_text(self):
        self.save_label.config(text="已保存 " + datetime.now().strftime("%H:%M"))

    def _after_change(self):
        try:
            self.store.save()
            self._set_saved_text()
        except Exception as e:
            messagebox.showwarning("保存失败", "数据未能写入本地文件：\n%s" % e)
        self._refresh_filter_combo()
        self.refresh_all()

    # ---------------- 左侧树 ----------------
    def rebuild_tree(self):
        t = self.tree
        t.delete(*t.get_children())
        all_n = len(self.store.all_zone_entries())
        t.insert("", "end", iid="root_all", text="全部账号（%d个小区）" % all_n, open=True)
        # 大号节点：与「全部账号」同级，下一级直接显示 小区-昵称
        mains = [e for e in self.store.all_zone_entries() if e[2].get("is_main")]
        t.insert("", "end", iid="root_main",
                 text="大号（%d个小区）" % len(mains), open=True, tags=("main",))
        for acc, p, z in mains:
            t.insert("root_main", "end",
                     iid="mz|%s|%s|%s" % (acc["id"], p["id"], z["id"]),
                     text=tree_zone_text(z), tags=("main",))
        for login in LOGINS:
            accs = [a for a in self.store.data["accounts"] if a["login"] == login]
            label = login_label(login)
            t.insert("root_all", "end", iid="login|" + login,
                     text="%s（%d个号）" % (label, len(accs)), open=True)
            for a in accs:
                t.insert("login|" + login, "end", iid="acc|" + a["id"],
                         text="%s（%d个平台）" % (a["name"], len(a["platforms"])))
                for p in a["platforms"]:
                    t.insert("acc|" + a["id"], "end",
                             iid="plat|%s|%s" % (a["id"], p["id"]),
                             text="%s（%d个小区）" % (p["platform"], len(p["zones"])))
                    for z in p["zones"]:
                        zid = "zone|%s|%s|%s" % (a["id"], p["id"], z["id"])
                        t.insert("plat|%s|%s" % (a["id"], p["id"]), "end",
                                 iid=zid, text=tree_zone_text(z))

    def _on_tree_double(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        parts = iid.split("|")
        if parts[0] == "acc" and len(parts) == 2:
            acc = self.store.get_account(parts[1])
            if acc:
                self.edit_account_dialog(acc)
        elif parts[0] in ("zone", "nick", "mz") and len(parts) == 4:
            acc = self.store.get_account(parts[1])
            r = self.store.get_zone(parts[1], parts[3])
            if acc and r:
                self.edit_zone_dialog(acc, r[0], r[1])

    # ---------------- 右侧表格 ----------------
    def apply_filters(self):
        text = self.search_var.get().strip().lower()
        f = self.filter_mode
        entries = []
        for acc, p, z in self.store.all_zone_entries():
            if f == "two" and z["two_tickets"]:
                continue
            if f == "skin" and z["battlepass_skin"]:
                continue
            if f == "marked" and not z.get("marked"):
                continue
            if f == "tickets" and int(z.get("tickets", 0)) < 5:
                continue
            if text:
                hay = ("%s %s %s %s %s %s" % (
                    acc.get("name", ""), acc.get("login", ""),
                    p.get("platform", ""), zone_label(z),
                    z.get("nickname", ""), z.get("zone_name", ""))).lower()
                if text not in hay:
                    continue
            entries.append((acc, p, z))
        # 自动排序：账号按添加先后分组（合并显示）；组内先按平台集中（iOS 组在前）-> 大号在前 -> 小区号从小到大
        if self.auto_sort_var.get():
            plat_order = {"iOS": 0, "安卓": 1}
            acc_order = {a["id"]: i for i, a in enumerate(self.store.data["accounts"])}
            entries.sort(key=lambda e: (
                acc_order.get(e[0]["id"], 0),
                plat_order.get(e[1]["platform"], 0),
                not bool(e[2].get("is_main")),
                int(e[2].get("zone_no", 0))))
        self._fill_table(entries)

    @staticmethod
    def _fmt_act(v, ctype):
        if ctype == "boolean":
            return "√" if v else ""
        if v is None or v == "":
            return ""
        return str(v)

    def _apply_row_colors(self):
        """按「底色设置」配置刷新行底色（开关/三种颜色）；分隔线固定浅灰"""
        rc = self.store.data.get("row_colors", {})
        enabled = bool(rc.get("enabled", True))
        if enabled:
            self.table.set_tag_bg("bg_bad", rc.get("bad", "#fff3e6"))
            self.table.set_tag_bg("bg_good", rc.get("good", "#e8f7e8"))
            self.table.set_tag_bg("bg_main", rc.get("main", "#fdf3e0"))
        else:
            self.table.set_tag_bg("bg_bad", "#ffffff")
            self.table.set_tag_bg("bg_good", "#ffffff")
            self.table.set_tag_bg("bg_main", "#ffffff")
        self.table.set_tag_bg("sep", "#b0b0b0")

    def _row_tag(self, z, is_main):
        """行底色规则（优先级：错色 > 大号色 > 对色）：
        - 错色：存在任一「对勾列」未领/未兑换（False）
        - 大号色：属于大号账号
        - 对色：有对勾列且全部已领/已兑换
        """
        bool_ids = [c["name"] for c in self.store.data["activity_columns"]
                    if c["type"] == "boolean"]
        values = [z.get("battlepass_skin"), z.get("two_tickets"), z.get("gift_claimed")]
        values += [z["activities"].get(b, False) for b in bool_ids]
        any_bad = any(v is False for v in values)
        if any_bad:
            return "bg_bad"
        if is_main:
            return "bg_main"
        if values and all(v is True for v in values):
            return "bg_good"
        return ""

    def _visible_columns(self):
        # 固定列（账号/小区/昵称）始终显示
        return [c for c in self.col_order if c not in self.hidden or c in LOCKED_COLUMNS]

    def _col_meta(self, cid):
        """返回 (显示名, 基础宽度)；数据列支持自定义显示名与自定义宽度"""
        default = cid
        width = 110
        for fc in FIXED_COLUMNS:
            if fc[0] == cid:
                default, width = fc[1], fc[2]
                break
        title = self.store.get_column_title(cid) or default
        cw = self.store.get_column_width(cid)
        if cw:
            width = cw
        return title, width

    def _cell_value(self, cid, acc, p, z):
        if cid == "main_star":
            return "★" if z.get("marked") else ""
        if cid == "login":
            return login_label(acc["login"])
        if cid == "account":
            return acc["name"]
        if cid == "platform":
            return p["platform"]
        if cid == "zone":
            return zone_label(z)
        if cid == "nickname":
            return z.get("nickname", "") or ""
        if cid == "level":
            return str(z.get("level", ""))
        if cid == "rank":
            return z.get("rank", "") or "-"
        if cid == "birthday":
            return z.get("birthday", "") or "-"
        if cid == "crystal":
            return str(z.get("crystal_count", ""))
        if cid == "tickets":
            return str(z.get("tickets", ""))
        if cid == "skin":
            return "√" if z.get("battlepass_skin") else ""
        if cid == "two":
            return "√" if z.get("two_tickets") else ""
        if cid == "gift":
            return "√" if z.get("gift_claimed") else ""
        c = self.store.get_activity_column(cid)
        if c:
            return self._fmt_act(z["activities"].get(cid), c["type"])
        return ""

    def _fill_table(self, entries):
        self.row_keys = []
        cols = self._visible_columns()
        col_defs = []
        for cid in cols:
            text, width = self._col_meta(cid)
            col_defs.append((cid, text, max(40, int(width * self.zoom / 100))))
        self.table.set_columns(col_defs)
        acc_idx = cols.index("account") if "account" in cols else -1
        rows = []
        last_name = None
        for acc, p, z in entries:
            # 自动排序开启时 entries 已按账号分组：组间插入贯穿整行的细横线
            if last_name is not None and acc["name"] != last_name:
                rows.append(([""] * len(cols), "sep", None))
                self.row_keys.append(None)
            show_acc = (acc["name"] != last_name)
            last_name = acc["name"]
            is_main = z.get("is_main")
            values = [self._cell_value(cid, acc, p, z) for cid in cols]
            # 同一账号只在该组第一行显示账号（视觉合并单元格）
            if acc_idx >= 0 and not show_acc:
                values[acc_idx] = ""
            tag = self._row_tag(z, is_main)
            rows.append((values, tag, (acc["id"], z["id"])))
            self.row_keys.append((acc["id"], z["id"]))
        self.table.set_rows(rows)

    def update_stats(self):
        st = self.store.stats()
        bd = self.store.birthdays_soon(3)
        if bd:
            first = bd[0]
            star = "★ " if first[2].get("is_main") else ""
            bd_text = "近3日生日：%s%s · %s（%s）" % (
                star, first[0]["name"], zone_label(first[2]), first[3])
        else:
            bd_text = "近3日生日：无"
        self.stats_var.set(
            "小区合计：%d 个   |   大号小区：%d 个   |   2券未兑换：%d 个   |   "
            "战令皮未领：%d 个   |   剩余券合计：%d 张   |   %s"
            % (st["zones"], st["main_zones"], st["two_unclaimed"],
               st["skin_unclaimed"], st["tickets"], bd_text))

    # ---------------- 表格选中 ----------------
    def selected_zone(self):
        key = self.table.selected_key()
        if not key:
            return None
        acc_id, zone_id = key
        acc = self.store.get_account(acc_id)
        r = self.store.get_zone(acc_id, zone_id)
        if not acc or not r:
            return None
        return acc, r[0], r[1]

    def _on_table_select(self, _event=None):
        state = "normal" if self.selected_zone() else "disabled"
        for b in (self.btn_five, self.btn_m4, self.btn_edit, self.btn_del):
            b.config(state=state)

    def _on_row_double(self, idx, cid):
        """Grid 双击行回调：标记列 -> 打/取消★；对勾列 -> 直接切换√/空白；其他列 -> 打开编辑窗口"""
        if cid == "main_star":
            self._toggle_mark()
            return
        if self._is_boolean_col(cid):
            self._toggle_boolean(cid)
            return
        res = self.selected_zone()
        if res:
            self.edit_zone_dialog(res[0], res[1], res[2])

    def _is_boolean_col(self, cid):
        """对勾类型列：内置战令皮/2券/礼册 + 活动对勾列"""
        if cid in ("skin", "two", "gift"):
            return True
        c = self.store.get_activity_column(cid)
        return bool(c and c["type"] == "boolean")

    def _toggle_boolean(self, cid):
        """双击对勾列单元格：直接切换 √ / 空白（已领<->未领，无需打开编辑窗口）"""
        res = self.selected_zone()
        if not res:
            return
        acc, _p, z = res
        if cid == "skin":
            z["battlepass_skin"] = not bool(z.get("battlepass_skin", False))
        elif cid == "two":
            z["two_tickets"] = not bool(z.get("two_tickets", False))
        elif cid == "gift":
            z["gift_claimed"] = not bool(z.get("gift_claimed", False))
        else:
            z["activities"][cid] = not bool(z["activities"].get(cid, False))
        for idx, k in enumerate(self.row_keys):
            if k == (acc["id"], z["id"]):
                self.table.set_cell(idx, cid, self._cell_value(cid, acc, _p, z))
                self.table.set_row_tag(idx, self._row_tag(z, bool(z.get("is_main"))))
                break
        self.store.save()
        self._set_saved_text()

    def _toggle_mark(self):
        """双击「标记」列单元格：给该小区打/取消 ★（自定义标记）"""
        res = self.selected_zone()
        if not res:
            return
        acc, _p, z = res
        z["marked"] = not bool(z.get("marked", False))
        for idx, k in enumerate(self.row_keys):
            if k == (acc["id"], z["id"]):
                self.table.set_cell(idx, "main_star", "★" if z["marked"] else "")
                break
        self.store.save()
        self._set_saved_text()

    # ---------------- 列头：双击重命名 / 拖动换序 ----------------
    def _on_heading_double(self, cid):
        """Grid 双击列头回调 -> 重命名列"""
        if not cid:
            return
        if cid in LOCKED_COLUMNS:
            messagebox.showinfo("提示", "「账号/小区/昵称」为固定列，不可重命名。")
            return
        if cid in [c[0] for c in FIXED_COLUMNS]:
            # 内置数据列：可自定义显示名（数据字段不受影响）
            cur = self._col_meta(cid)[0]
            new = simpledialog.askstring(
                "重命名列", "新的列名（仅改显示，数据不受影响；留空恢复默认）：",
                parent=self.root, initialvalue=cur)
            if new is None:
                return
            new = new.strip()
            self.store.set_column_title(cid, new)
            self._after_change()
            return
        # 活动列：改名（列名即字段名）
        new = simpledialog.askstring("重命名活动列", "新的列名：", parent=self.root,
                                     initialvalue=cid)
        if new is None:
            return
        new = new.strip()
        if not new:
            messagebox.showwarning("提示", "列名不能为空")
            return
        if not self.store.rename_activity_column(cid, new):
            messagebox.showwarning("提示", "已存在同名列：%s" % new)
            return
        # 同步列顺序里的引用，保持原位置
        self.col_order = [new if x == cid else x for x in self.col_order]
        self.store.set_column_order(self.col_order)
        self._after_change()

    def _on_col_swap(self, from_cid, to_cid):
        """Grid 拖动列头换序回调"""
        if not from_cid or not to_cid or from_cid == to_cid:
            return
        order = self.store.get_column_order()
        try:
            i, j = order.index(from_cid), order.index(to_cid)
        except ValueError:
            return
        order[i], order[j] = order[j], order[i]
        self.store.set_column_order(order)
        self.col_order = list(order)
        self._after_change()

    def _on_column_resize(self, cid, width_px):
        """列头拖拽调宽后保存（存基础宽度，缩放时按比例放大）"""
        base = max(30, int(width_px * 100 / self.zoom))
        self.store.set_column_width(cid, base)
        self._after_change()

    def _require_selection(self):
        res = self.selected_zone()
        if not res:
            messagebox.showinfo("提示", "请先在列表中选中一个小区")
        return res

    def five_pull_selected(self):
        res = self._require_selection()
        if not res:
            return
        acc, p, z = res
        if int(z.get("tickets", 0)) < 4:
            messagebox.showwarning(
                "券不足", "「%s」剩余夺宝券只有 %d 张，不足 4 张，无法 5 连抽。\n"
                "如需记录，请用「券-4」或「编辑」手动调整。"
                % (zone_label(z), int(z.get("tickets", 0))))
            return
        self.store.five_pull(acc["id"], z["id"])
        self._after_change()

    def tickets_minus4_selected(self):
        res = self._require_selection()
        if not res:
            return
        acc, p, z = res
        if int(z.get("tickets", 0)) < 4:
            messagebox.showwarning(
                "券不足", "「%s」剩余夺宝券只有 %d 张，不足 4 张。\n如需记录，请用「编辑」手动调整。"
                % (zone_label(z), int(z.get("tickets", 0))))
            return
        self.store.tickets_minus4(acc["id"], z["id"])
        self._after_change()

    def edit_selected(self):
        res = self._require_selection()
        if res:
            self.edit_zone_dialog(res[0], res[1], res[2])

    def delete_selected(self):
        res = self._require_selection()
        if not res:
            return
        acc, p, z = res
        if not messagebox.askyesno("确认删除", "确定删除小区「%s」吗？此操作不可恢复。"
                                   % zone_label(z)):
            return
        self.store.delete_zone(acc["id"], z["id"])
        self._after_change()

    # ---------------- 添加账号（向导） ----------------
    def add_account_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("添加账号")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        login_var = tk.StringVar(value="Q")
        name_var = tk.StringVar()
        reuse_var = tk.StringVar()
        platform_var = tk.StringVar(value=self.store.get_last_platform())
        no_var = tk.StringVar(value="1")
        zname_var = tk.StringVar()
        reuse_options = []          # [(显示文本, 账号id 或 None)]
        reuse_map = {}

        def refresh_reuse():
            """根据登录方式+账号名，刷新'复用已有账号'下拉"""
            nonlocal reuse_options, reuse_map
            name = name_var.get().strip()
            login = login_var.get()
            existing = self.store.find_account(login, name) if name else None
            if existing:
                reuse_options = [
                    ("复用已有：%s" % name, existing["id"]),
                    ("新建账号（%s）" % name, None),
                ]
            else:
                reuse_options = [("（将新建账号）", None)]
            reuse_map = {label: aid for label, aid in reuse_options}
            reuse_var.set(reuse_options[0][0])
            cb.configure(values=[label for label, _ in reuse_options])
            tip.set(("已找到同名账号，可选「复用」把它下面的平台/小区补全；"
                     "或新建。" if existing else "该登录方式下无同名账号，将新建账号。"))

        pad = {"padx": 8, "pady": 5}
        ttk.Label(win, text="按顺序填写，小区其它信息（昵称/等级/段位等）添加后可再改。",
                  foreground="#a8640d").grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(10, 4))

        # 第1步 登录方式
        ttk.Label(win, text="① 登录方式：").grid(row=1, column=0, sticky="e", **pad)
        fr1 = ttk.Frame(win)
        fr1.grid(row=1, column=1, columnspan=3, sticky="w", **pad)
        ttk.Radiobutton(fr1, text="QQ", variable=login_var, value="Q",
                        command=refresh_reuse).pack(side="left")
        ttk.Radiobutton(fr1, text="VX", variable=login_var, value="V",
                        command=refresh_reuse).pack(side="left", padx=(14, 0))

        # 第2步 账号
        ttk.Label(win, text="② 账号：").grid(row=2, column=0, sticky="e", **pad)
        ttk.Label(win, text="QQ号 / 微信号：").grid(row=2, column=1, sticky="e")
        ttk.Entry(win, textvariable=name_var, width=18).grid(row=2, column=2, sticky="w")
        name_var.trace_add("write", lambda *a: refresh_reuse())
        cb = ttk.Combobox(win, textvariable=reuse_var, state="readonly", width=26)
        cb.grid(row=3, column=2, sticky="w", padx=8, pady=2)
        tip = tk.StringVar()
        ttk.Label(win, textvariable=tip, foreground="#8a94a3", wraplength=300)\
            .grid(row=3, column=3, sticky="w", padx=(4, 8))

        # 第3步 平台
        ttk.Label(win, text="③ 平台：").grid(row=4, column=0, sticky="e", **pad)
        fr3 = ttk.Frame(win)
        fr3.grid(row=4, column=1, columnspan=3, sticky="w", **pad)
        for pl in PLATFORMS:
            ttk.Radiobutton(fr3, text=pl, variable=platform_var, value=pl).pack(side="left", padx=(0, 14))

        # 第4步 第一个小区
        ttk.Label(win, text="④ 第一个小区：").grid(row=5, column=0, sticky="e", **pad)
        ttk.Label(win, text="第几区：").grid(row=5, column=1, sticky="e")
        ttk.Spinbox(win, from_=1, to=999, textvariable=no_var, width=6).grid(row=5, column=2, sticky="w")
        ttk.Label(win, text="小区名：").grid(row=6, column=1, sticky="e", padx=(0, 6), pady=5)
        ttk.Entry(win, textvariable=zname_var, width=18).grid(row=6, column=2, sticky="w", pady=5)
        ttk.Label(win, text="如：29 区 · 回旋打击", foreground="#8a94a3")\
            .grid(row=6, column=3, sticky="w", padx=(4, 8))

        def save():
            login = login_var.get()
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "请填写 QQ 号或微信号")
                return
            mode = reuse_map.get(reuse_var.get(), None)
            if mode is None:
                # 新建账号
                if self.store.find_account(login, name):
                    messagebox.showwarning("提示",
                        "该登录方式下已存在账号「%s」，请选择下拉框里的「复用已有」。" % name)
                    return
                acc_id = self.store.add_account(login, name, is_main=False)
            else:
                acc_id = mode
            platform = platform_var.get()
            self.store.set_last_platform(platform)
            p = self.store.find_platform(acc_id, platform)
            if p:
                plat_id = p["id"]
            else:
                plat_id = self.store.add_platform(acc_id, platform)
            try:
                no = int(no_var.get())
                if not 1 <= no <= 999:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "「第几区」须为 1–999 的整数")
                return
            zname = zname_var.get().strip()
            if not zname:
                messagebox.showwarning("提示", "请填写小区名（如：回旋打击）")
                return
            self.store.add_zone(acc_id, plat_id, no, zname)
            win.destroy()
            self._after_change()

        btns = ttk.Frame(win)
        btns.grid(row=7, column=0, columnspan=4, sticky="ew", padx=8, pady=(8, 12))
        ttk.Button(btns, text="添加", command=save).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=(6, 0))

        refresh_reuse()
        win.update_idletasks()
        w, h = win.winfo_reqwidth() + 30, win.winfo_reqheight() + 18
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    # ---------------- 编辑账号弹窗 ----------------
    def edit_account_dialog(self, acc):
        win = tk.Toplevel(self.root)
        win.title("编辑账号")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        login_var = tk.StringVar(value=acc["login"])
        name_var = tk.StringVar(value=acc["name"])

        pad = {"padx": 8, "pady": 6}
        ttk.Label(win, text="登录方式：").grid(row=0, column=0, sticky="e", **pad)
        fr1 = ttk.Frame(win)
        fr1.grid(row=0, column=1, sticky="w", **pad)
        ttk.Radiobutton(fr1, text="QQ", variable=login_var, value="Q").pack(side="left")
        ttk.Radiobutton(fr1, text="VX", variable=login_var, value="V").pack(side="left", padx=(12, 0))
        ttk.Label(win, text="账号名（QQ号/微信号）：").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(win, textvariable=name_var, width=22).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(win, text="大号已改为按小区设置：双击小区 → 勾选「大号」。",
                  foreground="#a8640d").grid(row=2, column=0, columnspan=2, sticky="w", padx=8)

        # 平台列表
        pf = ttk.LabelFrame(win, text="平台（安卓/iOS 互相独立）", padding=8)
        pf.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        for i, p in enumerate(acc["platforms"]):
            row = ttk.Frame(pf)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text="%s（%d个小区）" % (p["platform"], len(p["zones"]))).pack(side="left")
            ttk.Button(row, text="删除该平台", width=12,
                       command=lambda pid=p["id"], pname=p["platform"],
                       n=len(p["zones"]): self._delete_platform(acc["id"], pid, pname, n, win))\
                .pack(side="right")
        missing = [pl for pl in PLATFORMS if not self.store.find_platform(acc["id"], pl)]
        addfr = ttk.Frame(pf)
        addfr.pack(fill="x", pady=(6, 0))
        if missing:
            ttk.Label(addfr, text="＋ 添加平台：").pack(side="left")
            for pl in missing:
                ttk.Button(addfr, text=pl, width=8,
                           command=lambda pl2=pl: self._add_platform(acc["id"], pl2, win))\
                    .pack(side="left", padx=3)
        else:
            ttk.Label(addfr, text="安卓 / iOS 平台均已存在。", foreground="#8a94a3").pack(side="left")

        def save():
            login = login_var.get()
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "账号名不能为空")
                return
            other = self.store.find_account(login, name)
            if other and other["id"] != acc["id"]:
                messagebox.showwarning("提示",
                    "该登录方式下已存在账号「%s」，不能重复。" % name)
                return
            self.store.update_account(acc["id"], login, name)
            win.destroy()
            self._after_change()

        def delete_account():
            if messagebox.askyesno(
                    "确认删除",
                    "确定删除账号「%s」吗？其下 %d 个平台、全部小区将一并删除，不可恢复。"
                    % (acc["name"], len(acc["platforms"]))):
                self.store.delete_account(acc["id"])
                win.destroy()
                self._after_change()

        btns = ttk.Frame(win)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 10))
        ttk.Button(btns, text="保存", command=save).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="删除本账号（含全部小区）", command=delete_account).pack(side="right")

        win.update_idletasks()
        w, h = win.winfo_reqwidth() + 30, win.winfo_reqheight() + 18
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    def _add_platform(self, acc_id, platform, win):
        if self.store.add_platform(acc_id, platform) is None:
            messagebox.showinfo("提示", "该平台已存在")
            return
        win.destroy()
        self._after_change()

    def _delete_platform(self, acc_id, plat_id, pname, n, win):
        if n:
            if not messagebox.askyesno("确认删除",
                    "删除平台「%s」将一并删除其下 %d 个小区，不可恢复。确定？" % (pname, n)):
                return
        self.store.delete_platform(acc_id, plat_id)
        win.destroy()
        self._after_change()

    # ---------------- 添加小区弹窗 ----------------
    def add_zone_dialog(self, acc_id=None, platform=None):
        accs = self.store.data["accounts"]
        if not accs:
            messagebox.showinfo("提示", "请先添加账号，再添加小区")
            return
        win = tk.Toplevel(self.root)
        win.title("添加小区")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        acc_map = {}
        items = []
        for a in accs:
            label = "%s · %s" % (login_label(a["login"]), a["name"])
            items.append(label)
            acc_map[label] = a["id"]
        acc_var = tk.StringVar(value=items[0])
        if acc_id:
            for label, aid in acc_map.items():
                if aid == acc_id:
                    acc_var.set(label)
                    break
        platform_var = tk.StringVar(value=platform if platform else self.store.get_last_platform())
        no_var = tk.StringVar(value="1")
        zname_var = tk.StringVar()

        pad = {"padx": 8, "pady": 6}
        ttk.Label(win, text="所属账号：").grid(row=0, column=0, sticky="e", **pad)
        ttk.Combobox(win, textvariable=acc_var, state="readonly", values=items,
                     width=24).grid(row=0, column=1, columnspan=2, sticky="w", **pad)
        ttk.Label(win, text="平台：").grid(row=1, column=0, sticky="e", **pad)
        fr = ttk.Frame(win)
        fr.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        for pl in PLATFORMS:
            ttk.Radiobutton(fr, text=pl, variable=platform_var, value=pl).pack(side="left", padx=(0, 14))
        ttk.Label(win, text="第几区：").grid(row=2, column=0, sticky="e", **pad)
        ttk.Spinbox(win, from_=1, to=999, textvariable=no_var, width=6).grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(win, text="小区名：").grid(row=3, column=0, sticky="e", **pad)
        ttk.Entry(win, textvariable=zname_var, width=20).grid(row=3, column=1, columnspan=2, sticky="w", **pad)

        def save():
            acc_id2 = acc_map[acc_var.get()]
            platform = platform_var.get()
            self.store.set_last_platform(platform)
            try:
                no = int(no_var.get())
                if not 1 <= no <= 999:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "「第几区」须为 1–999 的整数")
                return
            zname = zname_var.get().strip()
            if not zname:
                messagebox.showwarning("提示", "请填写小区名（如：回旋打击）")
                return
            p = self.store.find_platform(acc_id2, platform)
            if p:
                plat_id = p["id"]
            else:
                plat_id = self.store.add_platform(acc_id2, platform)
            self.store.add_zone(acc_id2, plat_id, no, zname)
            win.destroy()
            self._after_change()

        btns = ttk.Frame(win)
        btns.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 10))
        ttk.Button(btns, text="添加", command=save).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=(6, 0))

        win.update_idletasks()
        w, h = win.winfo_reqwidth() + 24, win.winfo_reqheight() + 16
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    # ---------------- 编辑小区弹窗 ----------------
    def edit_zone_dialog(self, acc, p, z):
        win = tk.Toplevel(self.root)
        win.title("小区详情 · 编辑")
        win.transient(self.root)
        win.grab_set()

        star = "★ " if z.get("is_main") else ""
        ttk.Label(win, text="%s · %s%s ｜ %s ｜ %s" % (
            login_label(acc["login"]), star, acc["name"], p["platform"], zone_label(z)),
            padding=(10, 6), font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=4)

        # ---- 基础信息 ----
        f1 = ttk.Frame(nb, padding=10)
        nb.add(f1, text="基础信息")
        no_var = tk.StringVar(value=str(z.get("zone_no", 0) or 0))
        zname_var = tk.StringVar(value=z.get("zone_name", "") or "")
        nick_var = tk.StringVar(value=z.get("nickname", "") or "")
        level_var = tk.StringVar(value=str(z.get("level", 1)))
        rank_var = tk.StringVar(value=z.get("rank", "") or "")
        birth_var = tk.StringVar(value=z.get("birthday", "") or "")
        main_var = tk.BooleanVar(value=bool(z.get("is_main", False)))
        rows = [
            ("第几区", ttk.Spinbox(f1, from_=1, to=999, textvariable=no_var, width=8)),
            ("小区名", ttk.Entry(f1, textvariable=zname_var, width=20)),
            ("昵称", ttk.Entry(f1, textvariable=nick_var, width=20)),
            ("等级", ttk.Spinbox(f1, from_=1, to=30, textvariable=level_var, width=8)),
            ("段位", ttk.Combobox(f1, textvariable=rank_var, values=RANK_LIST, width=18)),
            ("生日", ttk.Entry(f1, textvariable=birth_var, width=12)),
        ]
        for i, (lab, wgt) in enumerate(rows):
            ttk.Label(f1, text=lab + "：").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=5)
            wgt.grid(row=i, column=1, sticky="w", pady=5)
        ttk.Label(f1, text="大号：").grid(row=len(rows), column=0, sticky="e", padx=(0, 6), pady=5)
        ttk.Checkbutton(f1, text="设为大号账号（左侧树 ★ 高亮）", variable=main_var)\
            .grid(row=len(rows), column=1, sticky="w")
        ttk.Label(f1, text="生日只记月日，格式如 10-13（可空）",
                  foreground="#a8640d").grid(row=len(rows) + 1, column=1, sticky="w")

        # ---- 抽奖记录 ----
        f2 = ttk.Frame(nb, padding=10)
        nb.add(f2, text="抽奖记录")
        crystal_var = tk.StringVar(value=str(z.get("crystal_count", 0)))
        ticket_var = tk.StringVar(value=str(z.get("tickets", 0)))

        def _adj(var, delta, lo=0):
            try:
                v = int(var.get())
            except ValueError:
                v = lo
            var.set(str(max(lo, v + delta)))

        def _five_in_dialog():
            try:
                t = int(ticket_var.get())
            except ValueError:
                t = 0
            if t < 4:
                messagebox.showwarning("券不足", "剩余夺宝券不足 4 张，无法 5 连抽")
                return
            _adj(crystal_var, 5)
            _adj(ticket_var, -4)

        ttk.Label(f2, text="荣耀水晶累计次数：").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=5)
        ttk.Entry(f2, textvariable=crystal_var, width=8).grid(row=0, column=1, sticky="w", pady=5)
        for txt, cmd in (("＋1", lambda: _adj(crystal_var, 1)), ("－1", lambda: _adj(crystal_var, -1))):
            ttk.Button(f2, text=txt, width=4, command=cmd).grid(row=0, column=2 if txt == "＋1" else 3, padx=3, pady=5)
        ttk.Label(f2, text="剩余夺宝券：").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=5)
        ttk.Entry(f2, textvariable=ticket_var, width=8).grid(row=1, column=1, sticky="w", pady=5)
        for txt, cmd in (("＋1", lambda: _adj(ticket_var, 1)), ("－1", lambda: _adj(ticket_var, -1))):
            ttk.Button(f2, text=txt, width=4, command=cmd).grid(row=1, column=2 if txt == "＋1" else 3, padx=3, pady=5)
        ttk.Button(f2, text="5连抽：水晶+5 · 券-4（联动）", command=_five_in_dialog).grid(row=2, column=0, columnspan=4, sticky="w", padx=0, pady=(8, 2))
        ttk.Label(f2, text="5连抽会同时改动上面两处；＋1/－1 用于手动微调。",
                  foreground="#a8640d").grid(row=3, column=0, columnspan=4, sticky="w")

        # ---- 福利领取 ----
        f3 = ttk.Frame(nb, padding=10)
        nb.add(f3, text="福利领取")
        skin_var = tk.BooleanVar(value=bool(z.get("battlepass_skin")))
        two_var = tk.BooleanVar(value=bool(z.get("two_tickets")))
        gift_var = tk.BooleanVar(value=bool(z.get("gift_claimed")))
        ttk.Label(f3, text="战令皮肤：").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=6)
        ttk.Checkbutton(f3, text="已领（战令免费皮肤）", variable=skin_var).grid(row=0, column=1, sticky="w")
        ttk.Label(f3, text="2券：").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=6)
        ttk.Checkbutton(f3, text="已兑换（战令15级换2张夺宝券）", variable=two_var).grid(row=1, column=1, sticky="w")
        ttk.Label(f3, text="礼册领取：").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=6)
        ttk.Checkbutton(f3, text="已领", variable=gift_var).grid(row=2, column=1, sticky="w")
        ttk.Label(f3, text="勾选 = 已领/已兑换；不勾 = 未领/未兑换。",
                  foreground="#a8640d").grid(row=3, column=1, sticky="w")

        # ---- 活动列 ----
        f4 = ttk.Frame(nb, padding=10)
        nb.add(f4, text="活动列")
        act_widgets = {}
        act_cols = self.store.data["activity_columns"]
        if not act_cols:
            ttk.Label(f4, text="还没有活动列，点上方「管理活动列」添加。",
                      foreground="#8a94a3").grid(row=0, column=0, sticky="w")
        for i, c in enumerate(act_cols):
            cname, ctype = c["name"], c["type"]
            cur = z["activities"].get(cname, "" if ctype != "boolean" else False)
            ttk.Label(f4, text="%s（%s）：" % (cname, COL_TYPE_NAMES[ctype])).grid(row=i, column=0, sticky="e", padx=(0, 6), pady=5)
            if ctype == "boolean":
                var = tk.BooleanVar(value=bool(cur))
                ttk.Checkbutton(f4, text="勾选 = 已领（空白 = 未领）", variable=var).grid(row=i, column=1, sticky="w")
            else:
                var = tk.StringVar(value="" if cur in (None, "") else str(cur))
                ttk.Entry(f4, textvariable=var, width=20).grid(row=i, column=1, sticky="w")
            act_widgets[cname] = (ctype, var)
        ttk.Button(f4, text="＋ 管理活动列（添加/改名/删除）",
                   command=lambda: self.manage_columns_dialog(parent=win)).grid(
            row=len(act_cols) + 1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # ---- 保存 ----
        def save():
            try:
                no = int(no_var.get())
                if not 1 <= no <= 999:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "「第几区」须为 1–999 的整数")
                return
            zname = zname_var.get().strip()
            if not zname:
                messagebox.showwarning("提示", "请填写小区名（如：回旋打击）")
                return
            try:
                level = int(level_var.get())
                if not 1 <= level <= 30:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "等级须为 1–30 的整数")
                return
            birth = birth_var.get().strip()
            if birth:
                if not (len(birth) == 5 and birth[2] == "-"):
                    messagebox.showwarning("提示", "生日格式应为 月-日，如 10-13")
                    return
                try:
                    m, d = int(birth[:2]), int(birth[3:])
                    if not (1 <= m <= 12 and 1 <= d <= 31):
                        raise ValueError
                except ValueError:
                    messagebox.showwarning("提示", "生日格式应为 月-日，如 10-13")
                    return
            for var, name in ((crystal_var, "水晶次数"), (ticket_var, "剩余券")):
                try:
                    if int(var.get()) < 0:
                        raise ValueError
                except ValueError:
                    messagebox.showwarning("提示", "「%s」须为不小于 0 的整数" % name)
                    return
            activities = {}
            for cname, (ctype, var) in act_widgets.items():
                if ctype == "boolean":
                    activities[cname] = bool(var.get())
                elif ctype == "number":
                    raw = var.get().strip()
                    if raw == "":
                        activities[cname] = ""
                    else:
                        try:
                            activities[cname] = int(raw)
                        except ValueError:
                            messagebox.showwarning("提示", "活动列「%s」须填数字（可留空）" % cname)
                            return
                else:
                    activities[cname] = var.get().strip()
            self.store.update_zone_fields(acc["id"], z["id"], {
                "zone_no": no,
                "zone_name": zname,
                "nickname": nick_var.get().strip(),
                "level": level,
                "rank": rank_var.get().strip(),
                "birthday": birth,
                "crystal_count": int(crystal_var.get()),
                "tickets": int(ticket_var.get()),
                "battlepass_skin": bool(skin_var.get()),
                "two_tickets": bool(two_var.get()),
                "gift_claimed": bool(gift_var.get()),
                "is_main": bool(main_var.get()),
                "activities": activities,
            })
            win.destroy()
            self._after_change()

        def delete_zone():
            if messagebox.askyesno("确认删除", "确定删除小区「%s」吗？此操作不可恢复。"
                                   % zone_label(z)):
                self.store.delete_zone(acc["id"], z["id"])
                win.destroy()
                self._after_change()

        btns = ttk.Frame(win, padding=(10, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", command=save).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="删除本小区", command=delete_zone).pack(side="right")

        win.update_idletasks()
        w = nb.winfo_reqwidth() + 40
        h = nb.winfo_reqheight() + 90
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    # ---------------- 底色设置弹窗 ----------------
    def row_colors_dialog(self, parent=None):
        win = tk.Toplevel(parent or self.root)
        win.title("底色设置")
        win.transient(self.root)
        win.resizable(False, False)
        rc = self.store.data.get("row_colors", {})
        enabled_var = tk.BooleanVar(value=bool(rc.get("enabled", True)))
        colors = {
            "bad": tk.StringVar(value=rc.get("bad", "#fff3e6")),
            "good": tk.StringVar(value=rc.get("good", "#e8f7e8")),
            "main": tk.StringVar(value=rc.get("main", "#fdf3e0")),
        }
        swatches = {}

        def pick(key):
            cur = colors[key].get()
            rgb, hexv = colorchooser.askcolor(color=cur, parent=win)
            if hexv:
                colors[key].set(hexv)
                swatches[key].configure(background=hexv)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Checkbutton(frame, text="启用行底色", variable=enabled_var)\
            .grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="错（有未领/未兑换）：").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=4)
        swatches["bad"] = tk.Label(frame, text="  ", background=colors["bad"].get(), width=4)
        swatches["bad"].grid(row=1, column=1, padx=2)
        ttk.Button(frame, text="选色", command=lambda: pick("bad")).grid(row=1, column=2, padx=6)

        ttk.Label(frame, text="对（全部已领）：").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=4)
        swatches["good"] = tk.Label(frame, text="  ", background=colors["good"].get(), width=4)
        swatches["good"].grid(row=2, column=1, padx=2)
        ttk.Button(frame, text="选色", command=lambda: pick("good")).grid(row=2, column=2, padx=6)

        ttk.Label(frame, text="大号账号行：").grid(row=3, column=0, sticky="e", padx=(0, 6), pady=4)
        swatches["main"] = tk.Label(frame, text="  ", background=colors["main"].get(), width=4)
        swatches["main"].grid(row=3, column=1, padx=2)
        ttk.Button(frame, text="选色", command=lambda: pick("main")).grid(row=3, column=2, padx=6)

        ttk.Label(frame, text="规则：有任意对勾列（战令皮/2券/礼册/活动）未领 → 错色；\n"
                            "大号账号行 → 大号色；对勾列全部已领 → 对色。",
                  foreground="#8a94a3", justify="left")\
            .grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 4))

        def save():
            self.store.data["row_colors"] = {
                "enabled": bool(enabled_var.get()),
                "bad": colors["bad"].get(),
                "good": colors["good"].get(),
                "main": colors["main"].get(),
            }
            self.store.save()
            self._apply_row_colors()
            self.apply_filters()
            self._set_saved_text()
            win.destroy()

        btns = ttk.Frame(win, padding=(10, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", command=save).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=(6, 0))
        win.update_idletasks()
        w = frame.winfo_reqwidth() + 40
        h = frame.winfo_reqheight() + 70
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    # ---------------- 活动列管理弹窗 ----------------
    def manage_columns_dialog(self, parent=None):
        win = tk.Toplevel(parent or self.root)
        win.title("管理活动列")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        list_frame = ttk.LabelFrame(win, text="已有列（选中后可改名/删除）", padding=8)
        list_frame.pack(fill="both", expand=True, padx=10, pady=8)
        tv = ttk.Treeview(list_frame, columns=("name", "type"), show="headings", height=5)
        tv.heading("name", text="列名")
        tv.heading("type", text="类型")
        tv.column("name", width=150)
        tv.column("type", width=90)
        tv.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        def reload():
            tv.delete(*tv.get_children())
            for c in self.store.data["activity_columns"]:
                tv.insert("", "end", values=(c["name"], COL_TYPE_NAMES[c["type"]]))

        reload()

        def rename_col():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("提示", "请先选中要改名的列")
                return
            old = tv.item(sel[0], "values")[0]
            new = simpledialog.askstring("重命名", "新的列名：", parent=win,
                                         initialvalue=old)
            if new is None:
                return
            new = new.strip()
            if not new:
                messagebox.showwarning("提示", "列名不能为空")
                return
            if not self.store.rename_activity_column(old, new):
                messagebox.showwarning("提示", "已存在同名列：%s" % new)
                return
            self._after_change()
            reload()

        def delete_col():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("提示", "请先选中要删除的列")
                return
            name = tv.item(sel[0], "values")[0]
            if messagebox.askyesno("确认删除", "删除列「%s」将同时清除所有小区的该列数据，确定？" % name):
                self.store.delete_activity_column(name)
                self._after_change()
                reload()

        ops = ttk.Frame(list_frame)
        ops.pack(fill="x")
        ttk.Button(ops, text="重命名", command=rename_col).pack(side="left", padx=(8, 4))
        ttk.Button(ops, text="删除列", command=delete_col).pack(side="left")

        add_frame = ttk.LabelFrame(win, text="新增列", padding=8)
        add_frame.pack(fill="x", padx=10, pady=(0, 8))
        name_var = tk.StringVar()
        type_var = tk.StringVar(value="boolean")
        ttk.Label(add_frame, text="列名：").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=4)
        ttk.Entry(add_frame, textvariable=name_var, width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(add_frame, text="类型：").grid(row=0, column=2, sticky="e", padx=(10, 6), pady=4)
        ttk.Combobox(add_frame, textvariable=type_var, state="readonly", width=8,
                     values=[COL_TYPE_NAMES[t] for t in COL_TYPES]).grid(row=0, column=3, sticky="w")

        def add_col():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "列名不能为空")
                return
            zh = type_var.get()
            ctype = [k for k, v in COL_TYPE_NAMES.items() if v == zh][0]
            if not self.store.add_activity_column(name, ctype):
                messagebox.showwarning("提示", "已存在同名列：%s" % name)
                return
            self._after_change()
            reload()
            name_var.set("")

        ttk.Button(add_frame, text="添加", command=add_col).grid(row=0, column=4, padx=(12, 0))
        ttk.Label(win, text="新列会同步出现在主表格和每个小区的编辑弹窗里。",
                  foreground="#a8640d").pack(anchor="w", padx=10, pady=(0, 8))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=(0, 10))

        win.update_idletasks()
        w = win.winfo_reqwidth() + 20
        h = win.winfo_reqheight() + 12
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    # ---------------- 列设置（显示/隐藏）弹窗 ----------------
    def show_columns_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("列设置 · 显示/隐藏")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        order = self.store.get_column_order()
        frame = ttk.LabelFrame(win, text="勾选 = 显示该列（取消勾选 = 隐藏）", padding=8)
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        canvas = tk.Canvas(frame, height=min(400, 30 * max(1, len(order)) + 10))
        inner = ttk.Frame(canvas)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(wid, width=e.width))

        vars_ = {}
        for i, cid in enumerate(order):
            text, _w = self._col_meta(cid)
            if cid in LOCKED_COLUMNS:
                var = tk.BooleanVar(value=True)
                ttk.Checkbutton(inner, text="%s（固定·始终显示）" % text,
                                variable=var, state="disabled")\
                    .grid(row=i, column=0, sticky="w", padx=4, pady=2)
            elif cid in [c[0] for c in FIXED_COLUMNS]:
                var = tk.BooleanVar(value=cid not in self.hidden)
                ttk.Checkbutton(inner, text="%s（数据）" % text, variable=var)\
                    .grid(row=i, column=0, sticky="w", padx=4, pady=2)
            else:
                var = tk.BooleanVar(value=cid not in self.hidden)
                ttk.Checkbutton(inner, text="%s（活动）" % text, variable=var)\
                    .grid(row=i, column=0, sticky="w", padx=4, pady=2)
            vars_[cid] = var

        def save():
            hidden = [cid for cid, var in vars_.items() if not var.get()]
            self.store.set_hidden_columns(hidden)
            self.hidden = set(hidden)
            win.destroy()
            self._after_change()

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="确定", command=save).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=(6, 0))
        ttk.Label(btns, text="隐藏的列数据不会丢失，可随时重新勾选显示。",
                  foreground="#8a94a3").pack(side="right")

        win.update_idletasks()
        w = win.winfo_reqwidth() + 24
        h = win.winfo_reqheight() + 16
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 2)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        return win

    # ---------------- 其他 ----------------
    def reset_two_tickets(self):
        if not self.store.data["accounts"]:
            return
        if not messagebox.askyesno(
                "新赛季重置",
                "将把全部小区：\n2券 → 未兑换\n战令皮 → 未领\n段位 → 清空\n\n"
                "确定继续？"):
            return
        self.store.reset_two_tickets()
        self._after_change()

    def reset_gift(self):
        if not self.store.data["accounts"]:
            return
        if not messagebox.askyesno(
                "重置礼册",
                "将把全部小区的「礼册」设为「未领取」。\n\n"
                "（与新赛季分开重置，礼册按自己的周期来）确定继续？"):
            return
        self.store.reset_gift()
        self._after_change()

    def check_birthday_reminder(self):
        soon = self.store.birthdays_soon(3)
        if not soon:
            return
        lines = []
        for a, p, z, b, diff in soon:
            star = "★ " if z.get("is_main") else ""
            tag = "今天" if diff == 0 else "%d 天后" % diff
            lines.append("%s%s · %s · %s（%s）· %s" % (
                star, a["name"], p["platform"], zone_label(z), b, tag))
        messagebox.showinfo("生日提醒", "近 3 天有生日的小区（记得上线领生日福利）：\n\n" + "\n".join(lines))

    def open_data_folder(self):
        folder = os.path.dirname(os.path.abspath(self.store.path))
        try:
            os.startfile(folder)  # Windows
        except Exception as e:
            messagebox.showwarning("提示", "无法打开文件夹：%s" % e)


def main():
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1200x700")
    app = App(root, DataStore(data_path()), auto_remind=True)
    # 启动成功标记（打包验证用；不影响正常使用）
    try:
        with open(os.path.join(os.path.dirname(data_path()), "启动成功标记.txt"), "w", encoding="utf-8") as f:
            f.write("START_OK " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
