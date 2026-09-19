#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract.py —— 从 vendor/ 里的上游模块抽取规则，生成 src/ 可维护源文件。

支持三种上游格式：
  1. Shadowrocket / Surge 模块语法（[URL Rewrite] / [Script] / [MITM] 分节）
  2. QuantumultX 重写语法（`pattern url reject`、`pattern url script-response-body <url>`）
  3. ddgksf2013 那种无分节的 .conf（只有 hostname 行 + 重写行）

输出：
  src/rewrite/*.conf   各分类的重写规则（保留上游注释，便于溯源）
  src/scripts/*.script 各分类的脚本规则
  src/mitm/collected.hosts  汇总的 MITM 域名（每行一条，带来源注释）
  src/rules/*.list     [Rule] 规则
  build/extract-report.md   抽取报告（无法识别的行会列出来）
"""
from __future__ import annotations

import os
import re
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "vendor")
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "build")

SECTIONS = {
    "Rule", "URL Rewrite", "Header Rewrite", "Body Rewrite", "Script", "MITM",
    "General", "Host", "Map Local", "Panel", "Rewrite", "Rule Set", "MITM Hostname",
}

# 合法的重写动作（Surge / Shadowrocket 通用集合）
REWRITE_ACTIONS = {
    "reject", "reject-200", "reject-dict", "reject-array", "reject-img",
    "reject-tinygif", "reject-video", "reject-drop", "reject-no-drop",
    "302", "307", "header", "header-del", "header-add", "header-replace",
    "script-response-body", "script-request-body", "script-response-header",
    "script-request-header", "script-analyze-echo-response",
}
SCRIPT_ACTIONS = {
    "script-response-body": "http-response",
    "script-request-body": "http-request",
    "script-response-header": "http-response",
    "script-request-header": "http-request",
    "script-analyze-echo-response": "http-response",
}


class Part:
    """一个上游文件解析后的结果。"""

    def __init__(self, name: str):
        self.name = name
        self.rewrites: list[str] = []      # 归一化后的重写行（不含注释）
        self.script_lines: list[str] = []  # 归一化后的脚本行
        self.rules: list[str] = []         # 规则行
        self.mitm: list[str] = []          # 域名
        self.comments: dict[str, list[str]] = {}  # 区块名 -> 注释（用于保留分组说明）
        self.unparsed: list[str] = []


def _split_mitm_hosts(value: str) -> list[str]:
    value = value.replace("%APPEND%", " ").replace("%INSERT%", " ")
    return [h.strip() for h in value.split(",") if h.strip()]


def _looks_like_rewrite(tokens: list[str]) -> bool:
    return len(tokens) >= 2 and tokens[-1].lower() in REWRITE_ACTIONS


def normalize_rewrite(line: str) -> tuple[str | None, str | None]:
    """把一行重写归一化成 Shadowrocket 的 `pattern - action` / `pattern replacement action`。

    返回 (归一化行, 错误原因)；错误原因非空表示无法解析。
    """
    tokens = line.split()
    if len(tokens) < 2:
        return None, "tokens<2"

    last = tokens[-1].lower()
    prev = tokens[-2].lower() if len(tokens) >= 3 else ""

    # QuantumultX 脚本型：`pattern url script-response-body <url>`
    if len(tokens) >= 4 and tokens[-3].lower() == "url" and prev in SCRIPT_ACTIONS:
        kind = SCRIPT_ACTIONS[prev]
        pattern = " ".join(tokens[:-3])
        url = tokens[-1]
        return f"@SCRIPT@ {kind} {pattern} {url}", None

    # QuantumultX: `pattern url reject-dict`
    if prev == "url" and last in REWRITE_ACTIONS:
        pattern = " ".join(tokens[:-2])
        return f"{pattern} - {last}", None

    # Surge 风格：`pattern - reject`（部分作者用 `_` 占位表示无 replacement）
    if prev in ("-", "_") and last in REWRITE_ACTIONS:
        pattern = " ".join(tokens[:-2])
        return f"{pattern} - {last}", None

    # 无 replacement 的裸动作：`pattern reject`
    if last in REWRITE_ACTIONS and len(tokens) == 2:
        return f"{tokens[0]} - {last}", None

    # 带 replacement 的跳转：`pattern replacement 302`
    if last in ("302", "307") and len(tokens) >= 3:
        return line, None

    return None, f"未知动作 {last!r}"


SCRIPT_PREFIX = re.compile(r"^([^=\s]+)(\s*=\s*type=)")


def parse_file(path: str) -> Part:
    part = Part(os.path.basename(path))
    raw = open(path, encoding="utf-8", errors="replace").read().splitlines()

    cur = None
    saw_section = any(re.fullmatch(r"\[(.+?)\]", l.strip()) for l in raw)
    if not saw_section:
        cur = "URL Rewrite"  # 无分节文件整体当作重写区处理

    for raw_line in raw:
        line = raw_line.rstrip()
        s = line.strip()
        if not s:
            continue

        m = re.fullmatch(r"\[(.+?)\]", s)
        if m and m.group(1).strip() in SECTIONS:
            cur = m.group(1).strip()
            part.comments.setdefault(cur, [])
            continue

        # 元数据头 / 注释：QX 的 // 头块直接丢弃，其余注释保留
        if s.startswith("//"):
            continue
        if s.startswith("#"):
            if s.startswith("#!") or s.startswith("##"):
                continue
            if cur:
                part.comments.setdefault(cur, []).append(s)
            continue

        low = s.lower()

        if cur == "MITM" or low.startswith("hostname"):
            if low.startswith("hostname"):
                value = s.split("=", 1)[1] if "=" in s else ""
                part.mitm.extend(_split_mitm_hosts(value))
            continue

        if cur == "Rule":
            part.rules.append(s)
            continue

        if cur == "Script":
            line2 = norm_script_line(s)
            m2 = SCRIPT_PREFIX.match(line2)
            if m2:
                line2 = f"{script_name(part.name)}{line2[m2.end(1):]}"
            part.script_lines.append(line2)
            continue

        if cur == "URL Rewrite":
            norm, err = normalize_rewrite(s)
            if norm is None:
                part.unparsed.append(f"{s}   # {err}")
            elif norm.startswith("@SCRIPT@"):
                _, kind, pattern, url = norm.split(" ", 3)
                part.script_lines.append(
                    f"{script_name(part.name)} = type={kind},pattern={pattern},"
                    f"requires-body=1,max-size=-1,script-path={url}"
                )
            else:
                part.rewrites.append(norm)
            continue

        if cur in ("Header Rewrite", "Body Rewrite"):
            part.rewrites.append(f"[{cur}] {s}")
            continue

    return part


def script_name(fname: str) -> str:
    """把来源文件名变成可读的脚本名（会显示在 Shadowrocket 的脚本列表里）。"""
    n = re.sub(r"\.(sgmodule|module|conf)$", "", fname)
    n = re.sub(r"^(d_|lal_|a2s_|dd_)", "", n)
    return re.sub(r"[^A-Za-z0-9_]+", "-", n).strip("-").lower() or "script"


def norm_script_line(line: str) -> str:
    """统一脚本行：`name = type=http-response,pattern=...,script-path=...`"""
    s = line.strip()
    # 旧的 Surge 2 语法： `http-response <pattern> requires-body=1,script-path=...`
    m = re.match(r"^(http-request|http-response|http-response-jq)\s+(\S+)\s+(.*)$", s)
    if m:
        kind, pattern, rest = m.groups()
        return f"script = type={kind},pattern={pattern},{rest}"
    return s


# --------------------------------------------------------------------------
# 源文件 -> 分类 的映射
# --------------------------------------------------------------------------
LAYOUT: "OrderedDict[str, dict]" = OrderedDict([
    ("10-general", {
        "title": "通用 App 去广告（开屏 / 信息流 / 横幅 / 悬浮）",
        "rewrite": [
            ("lal_AdBlockLite.sgmodule", "AdBlockLite @blackmatrix7/@app2smile/@zwf23/@RuCu6"),
            ("d_AdBlock.module", "NoAd @Tartarus2014"),
        ],
        "scripts": [],
    }),
    ("20-ad-sdk", {
        "title": "广告联盟 SDK（穿山甲 / 优量汇 / 快手联盟 / 字节）",
        "rewrite": [],
        "scripts": [("a2s_adsense.sgmodule", "app2smile/rules adsense")],
    }),
    ("30-bilibili", {
        "title": "哔哩哔哩",
        "rewrite": [
            ("d_biliad.module", "biliad @ddgksf2013/@bm7"),
        ],
        "scripts": [("a2s_bilibili.sgmodule", "app2smile/rules bilibili")],
    }),
    ("40-weibo", {
        "title": "微博 / 微博国际版",
        "rewrite": [
            ("lal_weibo.sgmodule", "lalifeier/Shadowrocket 微博 @RuCu6/@zmqcherish"),
            ("d_WeiboBlock.sgmodule", "WeiboBlock @deezertidal"),
        ],
        "scripts": [("lal_weibo.sgmodule", "lalifeier/Shadowrocket 微博 @RuCu6/@zmqcherish")],
    }),
    ("50-zhihu", {
        "title": "知乎",
        "rewrite": [
            ("lal_zhihu.sgmodule", "lalifeier/Shadowrocket 知乎 @RuCu6"),
            ("d_ZhihuBlock.sgmodule", "ZhihuBlock @blackmatrix7"),
        ],
        "rules": [("d_ZhihuBlock.sgmodule", "ZhihuBlock @blackmatrix7")],
        "scripts": [
            ("lal_zhihu.sgmodule", "lalifeier/Shadowrocket 知乎 @RuCu6"),
            ("a2s_zhihu.sgmodule", "app2smile/rules 知乎"),
        ],
    }),
    ("60-xiaohongshu", {
        "title": "小红书",
        "rewrite": [
            ("lal_xiaohongshu.sgmodule", "lalifeier/Shadowrocket 小红书 @RuCu6/@fmz200"),
        ],
        "scripts": [("lal_xiaohongshu.sgmodule", "lalifeier/Shadowrocket 小红书")],
    }),
    ("70-reading-music", {
        "title": "阅读 / 音乐 / 播客（起点、网易云、喜马拉雅、Spotify）",
        "rewrite": [
            ("lal_netease.sgmodule", "网易云音乐 @RuCu6/@Keywos"),
            ("dd_Ximalaya.conf", "喜马拉雅 @ddgksf2013（QuantumultX 语法，已转换）"),
            ("a2s_spotify.module", "Spotify @app2smile"),
        ],
        "scripts": [
            ("lal_netease.sgmodule", "网易云音乐 @RuCu6/@Keywos"),
            ("dd_Ximalaya.conf", "喜马拉雅 @ddgksf2013"),
            ("a2s_qidian.sgmodule", "起点 @app2smile"),
            ("a2s_spotify.module", "Spotify @app2smile"),
        ],
        "headers": [("a2s_spotify.module", "Spotify @app2smile")],
    }),
    ("80-others", {
        "title": "其它高频 App（抖音、高德、菜鸟、什么值得买、贴吧、腾讯新闻、百度地图）",
        "rewrite": [
            ("lal_douyin.sgmodule", "抖音 @fmz200"),
            ("lal_amap.sgmodule", "高德地图 @RuCu6"),
            ("lal_cainiao.sgmodule", "菜鸟 @RuCu6"),
            ("lal_smzdm.sgmodule", "什么值得买 @RuCu6"),
            ("lal_bdmap.sgmodule", "百度地图 @RuCu6"),
        ],
        "scripts": [
            ("lal_douyin.sgmodule", "抖音 @fmz200"),
            ("a2s_tieba.sgmodule", "贴吧 @app2smile"),
            ("a2s_qqnews.sgmodule", "腾讯新闻 @app2smile"),
            ("a2s_baidumap.sgmodule", "百度地图 @app2smile"),
            ("a2s_vgtime.sgmodule", "vgtime @app2smile"),
        ],
    }),
    ("90-youtube", {
        "title": "YouTube（可选模块）",
        "rewrite": [
            ("d_YouTubeAd.sgmodule", "YouTubeAd @Maasea"),
            ("lal_youtube.sgmodule", "lalifeier/Shadowrocket YouTube"),
        ],
        "scripts": [
            ("a2s_youtube.sgmodule", "app2smile/rules YouTube"),
            ("d_YouTubeAd.sgmodule", "YouTubeAd @Maasea"),
        ],
    }),
])


def main() -> int:
    report = ["# 抽取报告", ""]
    all_mitm: "OrderedDict[str, list[str]]" = OrderedDict()
    missing_src = []

    for key, cfg in LAYOUT.items():
        out_rewrite: list[str] = []
        out_scripts: list[str] = []
        out_rules: list[str] = []
        seen_files = set()

        def load(fname: str):
            path = os.path.join(VENDOR, fname)
            if not os.path.exists(path):
                missing_src.append(fname)
                return None
            if fname not in seen_files:
                seen_files.add(fname)
                p = parse_file(path)
                if p.mitm:
                    all_mitm.setdefault(fname, []).extend(p.mitm)
                if p.unparsed:
                    report.append(f"### {fname} 无法解析的行（{len(p.unparsed)}）")
                    report.extend(f"    {u}" for u in p.unparsed)
                    report.append("")
            return parse_file(path)

        for fname, credit in cfg.get("rewrite", []):
            p = load(fname)
            if not p:
                continue
            out_rewrite.append(f"# ---- 来源：{credit} ({fname}) ----")
            out_rewrite += p.rewrites
            out_rewrite.append("")

        for fname, credit in cfg.get("rules", []):
            p = load(fname)
            if not p:
                continue
            out_rules.append(f"# ---- 来源：{credit} ({fname}) ----")
            out_rules += p.rules
            out_rules.append("")

        for fname, credit in cfg.get("scripts", []):
            p = load(fname)
            if not p:
                continue
            out_scripts.append(f"# ---- 来源：{credit} ({fname}) ----")
            out_scripts += p.script_lines
            out_scripts.append("")

        for fname, credit in cfg.get("headers", []):
            p = load(fname)
            if not p:
                continue
            hdr = [r for r in p.rewrites if r.startswith("[Header Rewrite]")]
            if hdr:
                out_rewrite.append(f"# ---- 来源：{credit} ({fname}) ----")
                out_rewrite += hdr
                out_rewrite.append("")

        os.makedirs(os.path.join(SRC, "rewrite"), exist_ok=True)
        os.makedirs(os.path.join(SRC, "scripts"), exist_ok=True)
        os.makedirs(os.path.join(SRC, "rules"), exist_ok=True)

        with open(os.path.join(SRC, "rewrite", f"{key}.conf"), "w", encoding="utf-8") as f:
            f.write(f"# {cfg['title']}\n")
            f.write("\n".join(out_rewrite).rstrip() + "\n")
        if out_scripts or cfg.get("scripts"):
            with open(os.path.join(SRC, "scripts", f"{key}.script"), "w", encoding="utf-8") as f:
                f.write(f"# {cfg['title']}\n")
                f.write("\n".join(out_scripts).rstrip() + "\n")
        if out_rules:
            with open(os.path.join(SRC, "rules", f"{key}.list"), "w", encoding="utf-8") as f:
                f.write(f"# {cfg['title']}\n")
                f.write("\n".join(out_rules).rstrip() + "\n")

        report.append(f"- `{key}`：重写 {sum(1 for l in out_rewrite if l and not l.startswith('#'))} 条，"
                      f"脚本 {sum(1 for l in out_scripts if l and not l.startswith('#'))} 条，"
                      f"规则 {sum(1 for l in out_rules if l and not l.startswith('#'))} 条")

    # MITM 汇总
    os.makedirs(os.path.join(SRC, "mitm"), exist_ok=True)
    with open(os.path.join(SRC, "mitm", "collected.hosts"), "w", encoding="utf-8") as f:
        f.write("# 由上游模块汇总的 MITM 域名，build.py 会去重并合并成一行\n")
        for fname, hosts in all_mitm.items():
            uniq = list(OrderedDict.fromkeys(hosts))
            f.write(f"# 来源：{fname}\n")
            f.write(", ".join(uniq) + "\n")

    if missing_src:
        report.append("")
        report.append("## 缺失的 vendor 文件（先跑 tools/fetch_upstream.sh）")
        report += [f"- {m}" for m in sorted(set(missing_src))]

    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "extract-report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report).rstrip() + "\n")

    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
