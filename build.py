#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py —— 把 src/ 下的规则源文件合并、去重、校验，产出 dist/ 里的模块。

做的事情：
  1. 合并 src/rewrite|scripts|rules|mitm 与 src/additions 的内容
  2. 修正常见上游错误（未锚定正则、非法 reject 动作、拼写错误）
  3. 去重：同一 pattern 只保留一次；动作冲突时保留“更精确”的那个
  4. 校验：正则能否编译、括号是否配对、脚本行是否缺字段、规则策略是否合法
  5. 交叉校验：重写规则/脚本的域名是否被 [MITM] 覆盖（没覆盖的规则永远不会生效）
  6. 输出模块文件 + build/BUILD_REPORT.md 报告

用法：
    python3 tools/fetch_upstream.sh    # 首次或更新规则时
    python3 tools/extract.py
    python3 build.py
"""
from __future__ import annotations

import os
import re
import sys
import datetime
import collections

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")

# 重写动作白名单（Shadowrocket / Surge 通用）
ACTIONS = {
    "reject", "reject-200", "reject-dict", "reject-array", "reject-img",
    "reject-tinygif", "reject-video", "302", "307",
}
# 需要 replacement 的动作
NEEDS_REPLACEMENT = {"302", "307"}
# 动作“精度”排序：同一 pattern 冲突时保留分数最高的
ACTION_RANK = {
    "reject-dict": 60, "reject-array": 60, "reject-200": 50,
    "reject-img": 40, "reject-tinygif": 40, "reject-video": 40,
    "reject": 30, "302": 20, "307": 20,
}
# [Rule] 合法策略
POLICIES = {
    "REJECT", "REJECT-DICT", "REJECT-ARRAY", "REJECT-200", "REJECT-IMG",
    "REJECT-TINYGIF", "REJECT-VIDEO", "REJECT-DROP", "REJECT-NO-DROP",
    "DIRECT", "PROXY",
}

RE_MODULE_HEADER = re.compile(r"^#!")


class Ctx:
    """收集构建过程中的统计与告警。"""

    def __init__(self) -> None:
        self.fixed: list[str] = []
        self.dropped: list[str] = []
        self.deduped = 0
        self.conflicts: list[str] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.uncovered: list[str] = []

    def fix(self, what: str, detail: str) -> None:
        self.fixed.append(f"{what}：{detail}")

    def drop(self, line: str, why: str) -> None:
        self.dropped.append(f"{why} → `{line}`")

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def read_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f]


def sanitize_for_python(pattern: str) -> str:
    """把 PCRE 合法但 Python 不认的写法改成等价写法，仅用于本地校验，不改写出内容。

    覆盖三类：
      1. 原子组 (?>...) / 命名组 (?<name>...)
      2. 字符类里紧跟类转义的连字符，如 [\\w-.]（PCRE 视为字面量，Python 报 bad range）
      3. \\cX 控制字符转义（上游 typo 常见，如 kfc\\.com.\\cn）
    """
    s = pattern.replace("(?>", "(?:")
    s = re.sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", s)
    s = re.sub(r"\\c[A-Za-z]?", "x", s)

    out: list[str] = []
    i = 0
    in_class = False
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            out.append(s[i:i + 2])
            i += 2
            continue
        if not in_class and ch == "[":
            in_class = True
        elif in_class and ch == "]":
            in_class = False
        elif in_class and ch == "-":
            out.append("\\-")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def compile_tolerant(pattern: str):
    """校验正则是否可用，返回 (ok, 提示)。

    分两步：先用 Python re 原样编译；不行再按"PCRE 专有写法 → 等价写法"重试。
    PCRE 专有构造用**显式检测**给出固定措辞的提示，这样提示文字不依赖本机 Python 版本
    （3.11+ 原生支持原子组 (?>)，3.9 不支持，否则同一份规则在不同机器上会生成不同报告）。
    """
    notes: list[str] = []
    if "(?>" in pattern:
        notes.append("含 PCRE 原子组 (?>…)")
    if re.search(r"\\c[A-Za-z]?", pattern):
        notes.append("含 \\c 控制字符转义（上游常见笔误，注意确认域名是否写错）")

    def finish(extra: str = "") -> tuple[bool, str]:
        allnotes = notes + ([extra] if extra else [])
        return True, ("；".join(allnotes) + "，已按等价写法校验") if allnotes else ""

    try:
        re.compile(pattern)
        return finish()
    except re.error:
        pass

    try:
        re.compile(sanitize_for_python(pattern))
    except re.error as e:
        return False, str(e)
    return finish("" if notes else "含 PCRE 专有写法")


def balanced(pattern: str) -> bool:
    depth = 0
    escaped = False
    in_class = False
    for ch in pattern:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if in_class:
            if ch == "]":
                in_class = False
            continue
        if ch == "[":
            in_class = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_class


def host_expr_to_witnesses(pattern: str) -> list[str]:
    """从重写正则里取出域名部分，生成若干“可能的真实域名”用于 MITM 覆盖检查。"""
    p = pattern[1:] if pattern.startswith("^") else pattern
    m = re.match(r"^https?\??:(?:\\?/){2}", p)
    if not m:
        return []          # 形如 `^[a-z]+://`，无法静态判断
    p = p[m.end():]

    out: list[str] = []
    i = 0
    while i < len(p):
        ch = p[i]
        if ch == "\\":
            nxt = p[i + 1] if i + 1 < len(p) else ""
            if nxt in ("/", "b", "B"):   # \/ 路径开始；\b 词边界，域名到此为止
                break
            if nxt in "wdshWDS":
                out.append("*")          # \w \d \s 等类转义 -> 通配
            else:
                out.append(nxt)          # \. -> . , \- -> -
            i += 2
            continue
        if ch in "/$":
            break
        if ch == "." and p[i + 1:i + 2] in ("+", "*", "?"):
            out.append("*")             # .+ / .* -> 通配
            i += 2
            continue
        if ch == "(" and p[i + 1:i + 2] == "?":
            i += 3 if p[i + 2:i + 3] in (">", ":") else 2   # 跳过 (?> / (?:
            out.append("(")
            continue
        if ch in "?+*":       # 量词（如 interface3?\.music）不是查询串起始，跳过
            i += 1
            continue
        out.append(ch)
        i += 1

    host = "".join(out)
    if not host:
        return []

    # 正则片段 -> 通配符片段
    host = re.sub(r"\(\?>|\?:", "(", host)            # 去掉原子组/非捕获组前缀
    host = re.sub(r"\[\^?[^\]]*\][+*?]?", "*", host)  # [\w-]+ / [a-z0-9]* -> *
    host = re.sub(r"\.\*\??|\.\+", "*", host)         # .* / .+ -> *
    host = re.sub(r"\.[{][^}]*[}]", "*", host)          # .{2,3} -> *
    host = re.sub(r"[{][^}]*[}]", "*", host)           # {2,3} -> *
    host = re.sub(r":\d+", "", host)                 # 去掉端口
    host = re.sub(r"\*+", "*", host)                  # 合并连续通配

    # 展开简单分组 (a|b)，不做嵌套
    def expand(s: str, depth: int = 0) -> list[str]:
        if depth > 3:
            return [s]
        m2 = re.search(r"\(([^()]*)\)(\?|\+|\*)?", s)
        if not m2:
            return [s]
        body = m2.group(1)
        results: list[str] = []
        for alt in body.split("|"):
            replaced = s[:m2.start()] + alt + s[m2.end():]
            results.extend(expand(replaced, depth + 1))
        return results

    hosts = [h for h in expand(host, 0) if h]
    # 残留括号 = 分组没展开干净；不像主机名的（IP 正则展开产物等）一并丢弃
    shape = re.compile(r"^(\*|[A-Za-z0-9*][A-Za-z0-9\-*]*)(\.[A-Za-z0-9*][A-Za-z0-9\-*]*)+$")
    # 再排掉「数字紧贴通配」的样本（IP 正则 25[0-5]\d 展开的产物）和「纯通配」样本（*.* 之类）
    return [h for h in hosts
            if "(" not in h and ")" not in h and shape.match(h)
            and not re.search(r"\d\*|\*\d", h)
            and re.search(r"[A-Za-z0-9]{2,}", h)]


def host_to_regex(host: str) -> "re.Pattern[str] | None":
    """把 MITM 域名（可能含 * 通配）转成正则，用于匹配规则里的域名。"""
    h = host.strip().lower()
    if not h:
        return None
    h = h.split(":")[0] if not h.startswith("-") else h
    parts = []
    for ch in h:
        if ch == "*":
            parts.append("[^.]*" if False else ".*")
        else:
            parts.append(re.escape(ch))
    try:
        return re.compile("^" + "".join(parts) + "$")
    except re.error:
        return None



# 兜底探针：任何 MITM 条目只要命中这些“无关域名”，说明它宽到会把全网流量拉进解密
MITM_PROBES = ["apple.com", "icloud.com", "google.com", "example.org", "wikipedia.org"]


def normalize_mitm(host: str) -> str:
    """上游有些条目写成 `*.pstatp.com.*` / `gurd.snssdk.com.*`，尾部 `.*` 没有任何作用，
    却会让 `x.pstatp.com.evil.tld` 这种域名也命中，属于无意义的解密范围放大，直接去掉。"""
    h = host.strip()
    if h.endswith(".*") and len(h) > 2:
        h = h[:-2]
    return h


def is_overbroad_mitm(host: str) -> bool:
    rx = host_to_regex(host)
    if rx is None:
        return True
    return all(rx.match(p) for p in MITM_PROBES)


def host_covered(rule_host: str, mitm_hosts: list[str], mitm_res: list) -> bool:
    """规则域名是否被任一 MITM 域名覆盖（两边都可能是 `*` 通配）。"""
    rh = rule_host.lower()
    rrx = host_to_regex(rh)
    for entry, rx in zip(mitm_hosts, mitm_res):
        if rx is None:
            continue
        e = entry.lower()
        if "*" not in e and "*" not in rh:
            if e == rh:
                return True
            continue
        if "*" not in e:                      # MITM 是字面量，规则是通配
            if rrx and rrx.match(e):
                return True
            continue
        if "*" not in rh:                     # 规则是字面量，MITM 是通配
            if rx.match(rh):
                return True
            continue
        # 双方都有通配：用各自的“代表样本”互相试探
        if rx.match(rh.replace("*", "x")) or (rrx and rrx.match(e.replace("*", "x"))):
            return True
    return False



CLASS_ESCAPE_DASH = re.compile(r"(\\[wdsWDS])-")


def fix_class_dash(text: str) -> str:
    """`[\w-.]` -> `[\w\-.]`：PCRE 认前者，iOS NSRegularExpression 可能直接报非法区间。"""
    return CLASS_ESCAPE_DASH.sub(r"\1\\-", text)


# --------------------------------------------------------------------------
# 解析模块片段
# --------------------------------------------------------------------------
class Bundle:
    def __init__(self) -> None:
        # (pattern, action, replacement|None)
        self.rewrites: list[tuple[str, str, "str | None"]] = []
        self.headers: list[str] = []
        self.scripts: list[str] = []
        self.rules: list[str] = []
        self.mitm: list[str] = []


def load_conf(path: str, b: Bundle, ctx: Ctx) -> None:
    """读取 src/rewrite|scripts|rules 下的片段文件。"""
    for raw in read_lines(path):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[Header Rewrite]"):
            b.headers.append(line[len("[Header Rewrite]"):].strip())
            continue

        if "=" in line and "script-path=" in line:
            b.scripts.append(line)
            continue

        if line.startswith(("RULE-SET", "DOMAIN", "IP-CIDR", "URL-REGEX", "PROCESS", "USER-AGENT")):
            b.rules.append(line)
            continue

        tokens = line.split()
        if len(tokens) >= 3 and tokens[-2] in ("-", "_"):
            pattern = " ".join(tokens[:-2])
            action = tokens[-1].lower()
            b.rewrites.append((pattern, action, None))
            continue
        # 带 replacement 的跳转：`pattern replacement 302`
        if len(tokens) >= 3 and tokens[-1].lower() in NEEDS_REPLACEMENT:
            b.rewrites.append((" ".join(tokens[:-2]), tokens[-1].lower(), tokens[-2]))
            continue

        ctx.error(f"{os.path.relpath(path, ROOT)}：无法识别的行 `{line}`")


def load_hosts(path: str, b: Bundle) -> None:
    for raw in read_lines(path):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        for h in line.replace("%APPEND%", " ").split(","):
            h = h.strip()
            if h:
                b.mitm.append(h)


# --------------------------------------------------------------------------
# 去重 + 校验
# --------------------------------------------------------------------------
def load_drops(path: str) -> list[str]:
    """src/additions/drop.txt：需要从上游规则里剔除的片段（子串匹配）。"""
    out = []
    for raw in read_lines(path):
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def merge_rewrites(items, ctx: Ctx, drops: list[str]):
    best: "collections.OrderedDict[str, tuple[str, str, str | None]]" = collections.OrderedDict()
    for pattern, action, replacement in items:
        # 修正 0：剔除已知有害/过宽的上游规则
        # drop 列表按子串匹配，带上动作和 replacement，才能精确到"某一条规则"
        haystack = f"{pattern} - {action}" + (f" {replacement}" if replacement else "")
        hit = next((d for d in drops if d in haystack), None)
        if hit:
            ctx.drop(f"{pattern} - {action}", f"命中 drop 列表（{hit[:48]}…）")
            continue
        # 修正 1：非法动作
        if action not in ACTIONS:
            ctx.error(f"非法重写动作 `{action}`（pattern: {pattern}），已丢弃")
            continue
        # 修正 1.5：字符类里紧跟类转义的连字符（ICU 正则兼容性）
        fixed = fix_class_dash(pattern)
        if fixed != pattern:
            ctx.fix("转义字符类中的连字符", f"`{pattern[:60]}…`")
            pattern = fixed

        # 修正 2：未锚定 -> 补 ^（带 replacement 的规则和以 `(` 开头的分组规则跳过）
        head = pattern.lstrip("(")
        if replacement is None and not pattern.startswith("(") and not head.startswith("^"):
            pattern = "^" + pattern
            ctx.fix("补锚点", f"`{pattern[:70]}…`")
        # 修正 3：括号不配对
        if not balanced(pattern):
            ctx.error(f"括号不配对，已丢弃：`{pattern}`")
            continue
        # 修正 4：正则可编译性
        ok, note = compile_tolerant(pattern)
        if not ok:
            ctx.error(f"正则无法编译（{note}），已丢弃：`{pattern}`")
            continue
        if note:
            ctx.warn(f"`{pattern[:60]}…` {note}")

        key = pattern + ("\x00" + replacement if replacement else "")
        if key in best:
            old_action = best[key][1]
            if old_action != action:
                keep_new = ACTION_RANK.get(action, 0) > ACTION_RANK.get(old_action, 0)
                ctx.conflicts.append(
                    f"`{pattern[:70]}…`：{old_action} vs {action} → 保留 "
                    f"{action if keep_new else old_action}"
                )
                if keep_new:
                    best[key] = (pattern, action, replacement)
            ctx.deduped += 1
            continue
        best[key] = (pattern, action, replacement)
    return list(best.values())


def validate_scripts(scripts: list[str], ctx: Ctx, drops: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for s in scripts:
        hit = next((d for d in drops if d in s), None)
        if hit:
            ctx.drop(s, f"命中 drop 列表（{hit[:48]}…）")
            continue
        s = fix_class_dash(s)
        if "{{{ " in s or "{{{" in s:
            s = re.sub(r",argument=[^,]*\{\{\{[^}]*\}\}\}?", "", s)
            ctx.fix("移除未定义参数占位符", s[:80] + "…")
        if "engine=" in s and "{{{" in s:
            continue
        m = re.search(r"pattern=([^,]+)", s)
        if not m:
            ctx.error(f"脚本行缺少 pattern：`{s[:90]}`")
            continue
        pattern = m.group(1)
        ok, note = compile_tolerant(pattern)
        if not ok:
            ctx.error(f"脚本 pattern 无法编译（{note}）：`{s[:90]}`")
            continue
        if not re.search(r"type=(http-request|http-response|rule|dns|event|cron)", s):
            ctx.error(f"脚本行缺少 type：`{s[:90]}`")
            continue
        if "script-path=" not in s:
            ctx.error(f"脚本行缺少 script-path：`{s[:90]}`")
            continue
        if s in seen:
            ctx.deduped += 1
            continue
        seen.add(s)
        out.append(s)
    return out


def validate_rules(rules: list[str], ctx: Ctx) -> list[str]:
    out, seen = [], set()
    for r in rules:
        if r in seen:
            ctx.deduped += 1
            continue
        seen.add(r)
        if r.startswith("RULE-SET"):
            parts = [p.strip() for p in r.split(",")]
            if len(parts) < 3:
                ctx.error(f"RULE-SET 字段不足：`{r}`")
                continue
            if parts[-1].upper() == "REJECT-DROP":
                r = r[: r.rfind(",")] + ",REJECT"
                ctx.fix("REJECT-DROP→REJECT", "Shadowrocket 兼容性")
            out.append(r)
            continue
        policy = r.split(",")[-1].strip().upper()
        if policy not in POLICIES:
            ctx.warn(f"规则策略 `{policy}` 不在白名单内（若为策略组名可忽略）：`{r}`")
        out.append(r)
    return out


# --------------------------------------------------------------------------
# 模块定义
# --------------------------------------------------------------------------
# 通用部分：注意 30-bilibili 已被拆成独立模块（见 README「B站为什么单独装」）
COMMON_PARTS = ["10-general", "20-ad-sdk", "40-weibo",
                "50-zhihu", "60-xiaohongshu", "70-reading-music", "80-others"]

# script_mode：
#   none   —— 一个脚本都不带
#   text   —— 只带 requires-body 的文本/JSON 改写脚本（跨客户端兼容性最好）
#   binary —— 只带 binary-body-mode 的协议级改写脚本（gRPC/protobuf，兼容性最差，单独放实验模块）
MODULES = [
    {
        "file": "NoAd.sgmodule",
        "name": "NoAd · App 去广告（纯规则版）",
        "desc": "通用App/微博/知乎/小红书/阅读音乐类去广告。纯 URL Rewrite + 域名规则，不含任何脚本，最稳定。",
        "parts": COMMON_PARTS,
        "script_mode": "none",
    },
    {
        "file": "NoAd-Plus.sgmodule",
        "name": "NoAd Plus · App 去广告（增强版）",
        "desc": "在纯规则版基础上追加文本/JSON 类脚本：广告联盟SDK、微博/知乎/小红书信息流、起点、腾讯新闻、喜马拉雅。",
        "parts": COMMON_PARTS,
        "script_mode": "text",
    },
    {
        "file": "modules/Bilibili.sgmodule",
        "name": "NoAd · 哔哩哔哩（可选）",
        "desc": "B站开屏、首页推荐流、搜索默认词、相关推荐、漫画与直播广告。默认不含 proto 改写，避免影响视频详情接口。",
        "parts": ["30-bilibili"],
        "script_mode": "text",
    },
    {
        "file": "modules/YouTube.sgmodule",
        "name": "NoAd · YouTube 去广告（可选）",
        "desc": "拦截 YouTube 贴片/首页广告请求。需要 HTTPS 解密。",
        "parts": ["90-youtube"],
        "script_mode": "none",
    },
    {
        "file": "modules/Experimental-Proto.sgmodule",
        "name": "NoAd · 协议级改写（实验性，出问题先删它）",
        "desc": "gRPC/protobuf 响应改写：B站视频详情与动态、贴吧列表、Spotify、百度地图、网易云、YouTube。上游只保证 Surge/Loon/QX，小火箭上可能导致接口异常，仅推荐给愿意折腾的人。",
        "parts": ["30-bilibili", "70-reading-music", "80-others", "90-youtube"],
        "script_mode": "binary",
        "rewrites": False,   # 只取脚本，规则交给各自的模块，避免重复
    },
]


def build_module(cfg: dict, ctx_all: dict) -> str:
    ctx = Ctx()
    b = Bundle()

    mode = cfg.get("script_mode", "none")
    want_rewrites = cfg.get("rewrites", True)

    # ---- 载入源片段 ----
    for p in cfg["parts"]:
        if want_rewrites:
            load_conf(os.path.join(SRC, "rewrite", f"{p}.conf"), b, ctx)
        if mode != "none":
            load_conf(os.path.join(SRC, "scripts", f"{p}.script"), b, ctx)
            load_conf(os.path.join(SRC, "rules", f"{p}.list"), b, ctx)
        # 人工增补/修正（每个分类一个文件）
        add = os.path.join(SRC, "additions", f"{p}.conf")
        if want_rewrites and os.path.exists(add):
            load_conf(add, b, ctx)
    load_conf(os.path.join(SRC, "additions", "00-global.conf"), b, ctx)
    load_hosts(os.path.join(SRC, "mitm", "collected.hosts"), b)
    load_hosts(os.path.join(SRC, "mitm", "extra.hosts"), b)
    # 域名级 [Rule] 只属于主模块，独立的小模块（如 YouTube）不需要
    if "10-general" in cfg["parts"]:
        load_conf(os.path.join(SRC, "rules", "ad-domains.list"), b, ctx)
    drops = load_drops(os.path.join(SRC, "additions", "drop.txt"))
    skip_hosts = [h.lower() for h in load_drops(os.path.join(SRC, "mitm", "skip.hosts"))]

    # ---- 处理 ----
    rewrites = merge_rewrites(b.rewrites, ctx, drops)
    headers = list(dict.fromkeys(b.headers))
    scripts = validate_scripts(b.scripts, ctx, drops) if mode != "none" else []
    if mode == "text":
        scripts = [x for x in scripts if "binary-body-mode" not in x]
    elif mode == "binary":
        scripts = [x for x in scripts if "binary-body-mode" in x]
    if mode == "binary" and not want_rewrites:
        ctx.fix("实验模块只保留协议级脚本", f"共 {len(scripts)} 条")
    rules = validate_rules(b.rules, ctx)

    # ---- MITM：只保留真正被规则/脚本用到的域名 ----
    mitm_all = []
    for h in b.mitm:
        if h.startswith("-"):
            continue
        fixed = normalize_mitm(h)
        if fixed != h:
            ctx.fix("去掉 MITM 条目尾部多余的 .*", f"`{h}` → `{fixed}`")
        if fixed not in mitm_all:
            mitm_all.append(fixed)
    mitm_res = [host_to_regex(h) for h in mitm_all]

    need_hosts: list[tuple[str, str]] = []
    for pattern, _action, _repl in rewrites:
        for h in host_expr_to_witnesses(pattern):
            need_hosts.append((h, pattern))
    for s in scripts:
        m = re.search(r"pattern=([^,]+)", s)
        if m:
            for h in host_expr_to_witnesses(m.group(1)):
                need_hosts.append((h, s[:70]))

    used_mitm_pre = [
        e for e in mitm_all
        if any(host_covered(w, [e], [host_to_regex(e)]) for w, _ in need_hosts)
    ]

    # 排除项只在“它排除了本模块确实要解密的主机”时才有意义
    mitm_excluded = [
        h for h in dict.fromkeys(b.mitm)
        if h.startswith("-") and host_covered(
            h[1:], used_mitm_pre, [host_to_regex(x) for x in used_mitm_pre])
    ]

    def narrowest(witness: str) -> "str | None":
        """在 MITM 清单里挑覆盖该域名且最“窄”的一条（通配最少、长度最短）。"""
        cands = [e for e in mitm_all if host_covered(witness, [e], [host_to_regex(e)])]
        if not cands:
            return None
        cands.sort(key=lambda e: (e.count("*"), len(e)))
        return cands[0]

    # 收敛解密范围：规则里的域名是精确主机名时，不用上游的大范围通配条目，
    # 直接用这个精确主机名——规则只会匹配它，没必要把同域其它流量也解密。
    keep: "collections.OrderedDict[str, None]" = collections.OrderedDict()
    for h, _src in need_hosts:
        entry = narrowest(h)
        if entry is None:
            continue
        keep[h if "*" not in entry else entry] = None
    used_mitm = [h for h in keep.keys() if not is_overbroad_mitm(h)]
    for h in keep.keys():
        if is_overbroad_mitm(h):
            ctx.error(f"MITM 条目 `{h}` 过于宽泛（会解密无关域名），已剔除并连带剔除依赖它的规则")

    # 反向检查：哪些规则的域名没被 MITM 覆盖（静默失效）
    used_res = [host_to_regex(x) for x in used_mitm]
    safe_rewrites = []
    for item in rewrites:
        ws = host_expr_to_witnesses(item[0])
        if ws and not any(host_covered(w, used_mitm, used_res) for w in ws) \
           and not all(w.lower() in skip_hosts or w.lower() in ("*", "*.*") for w in ws):
            ctx.drop(f"{item[0]} - {item[1]}", "MITM 范围校验未通过（无法安全解密该域名）")
            continue
        safe_rewrites.append(item)
    rewrites = safe_rewrites
    for h, src in need_hosts:
        if h.lower() in skip_hosts:
            continue
        if not host_covered(h, used_mitm, used_res):
            ctx.uncovered.append(f"域名 `{h}` 未被 [MITM] 覆盖 → 规则可能不生效：`{src[:80]}`")

    # ---- 组装 ----
    today = datetime.date.today().isoformat()
    out: list[str] = []
    out.append(f"#!name={cfg['name']}")
    out.append(f"#!desc={cfg['desc']}（构建 {today}）")
    out.append("#!author=规则聚合自 blackmatrix7 / app2smile / deezertidal / ddgksf2013 / Maasea / "
               "lalifeier 等开源项目，由 NoAd 构建脚本合并整理")
    out.append("#!homepage=https://github.com/blackmatrix7/ios_rule_script")
    out.append(f"# 构建日期：{today}　由 build.py 自动生成，请勿直接编辑")
    out.append("# 使用前请在 Shadowrocket 中开启 HTTPS 解密（安装并信任 CA 证书）")

    if rules:
        out.append("")
        out.append("[Rule]")
        out += rules

    if rewrites:
        out.append("")
        out.append("[URL Rewrite]")
        out += [(f"{p} {r} {a}" if r else f"{p} - {a}") for p, a, r in rewrites]

    if headers:
        out.append("")
        out.append("[Header Rewrite]")
        out += headers

    if scripts:
        out.append("")
        out.append("[Script]")
        out += scripts

    if used_mitm:
        out.append("")
        out.append("[MITM]")
        line = "%APPEND% " + ", ".join(used_mitm)
        if mitm_excluded:
            line += ", " + ", ".join(mitm_excluded)   # 保留上游的 -排除主机名
        out.append("hostname = " + line)

    ctx_all[cfg["file"]] = {
        "ctx": ctx,
        "counts": {
            "重写": len(rewrites), "脚本": len(scripts), "规则": len(rules),
            "头部重写": len(headers), "MITM 域名": len(used_mitm),
            "被裁掉的 MITM 域名": len(mitm_all) - len(used_mitm),
        },
    }
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    os.makedirs(DIST, exist_ok=True)
    os.makedirs(os.path.join(DIST, "modules"), exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)

    results = {}
    for cfg in MODULES:
        text = build_module(cfg, results)
        path = os.path.join(DIST, cfg["file"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # ---- 报告 ----
    rep = ["# 构建报告", "", f"构建时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}", ""]
    total_errors = 0
    for fname, r in results.items():
        ctx: Ctx = r["ctx"]
        rep.append(f"## {fname}")
        rep.append("")
        rep.append("| 项目 | 数量 |")
        rep.append("| --- | --- |")
        for k, v in r["counts"].items():
            rep.append(f"| {k} | {v} |")
        rep.append("")
        total_errors += len(ctx.errors)

        if ctx.dropped:
            rep.append(f"<details><summary>按 drop 列表剔除 {len(ctx.dropped)} 条</summary>")
            rep.append("")
            rep += [f"- {x}" for x in ctx.dropped]
            rep.append("")
            rep.append("</details>")
            rep.append("")
        if ctx.fixed:
            rep.append(f"<details><summary>自动修正 {len(ctx.fixed)} 处</summary>")
            rep.append("")
            rep += [f"- {x}" for x in ctx.fixed]
            rep.append("")
            rep.append("</details>")
            rep.append("")
        if ctx.conflicts:
            rep.append(f"<details><summary>动作冲突 {len(ctx.conflicts)} 处（已按精度保留）</summary>")
            rep.append("")
            rep += [f"- {x}" for x in ctx.conflicts]
            rep.append("")
            rep.append("</details>")
            rep.append("")
        if ctx.uncovered:
            rep.append(f"<details><summary>MITM 未覆盖的域名 {len(ctx.uncovered)} 处（需人工确认）</summary>")
            rep.append("")
            rep += [f"- {x}" for x in ctx.uncovered[:120]]
            rep.append("")
            rep.append("</details>")
            rep.append("")
        if ctx.errors:
            rep.append(f"### 错误 {len(ctx.errors)}")
            rep.append("")
            rep += [f"- {x}" for x in ctx.errors]
            rep.append("")
        if ctx.warnings:
            rep.append(f"### 提示 {len(ctx.warnings)}")
            rep.append("")
            rep += [f"- {x}" for x in ctx.warnings[:60]]
            rep.append("")
        rep.append(f"去重合并：{ctx.deduped} 条")
        rep.append("")

    with open(os.path.join(BUILD, "BUILD_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep).rstrip() + "\n")

    print("\n".join(rep[:200]))
    print()
    for cfg in MODULES:
        p = os.path.join(DIST, cfg["file"])
        print(f"  {cfg['file']:<28} {os.path.getsize(p):>7} bytes")
    if total_errors:
        print(f"\n!! 有 {total_errors} 个错误，详见 build/BUILD_REPORT.md")
        return 1
    print("\n构建成功（无错误）。报告：build/BUILD_REPORT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
