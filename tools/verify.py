#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify.py —— 独立校验 dist/ 里产出的模块文件（不依赖 build.py 的内部状态）。

检查项：
  1. 头部指令：#!name / #!desc 是否存在且在第一行附近
  2. 分节名是否合法
  3. [URL Rewrite] 每行格式是否为 `pattern - action` 或 `pattern replacement action`
  4. [Script] 每行是否含 type / pattern / script-path，且 pattern 语法合法
  5. [MITM] 是否只有一行 hostname，且以 %APPEND% 开头（否则会覆盖用户配置里的其它域名）
  6. 重写 pattern 是否有重复
  7. [Rule] 每行字段数与策略是否合法

用法：python3 tools/verify.py
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

SECTIONS = {
    "Rule", "URL Rewrite", "Header Rewrite", "Body Rewrite", "Script", "MITM",
    "General", "Host", "Map Local", "Panel",
}
ACTIONS = {
    "reject", "reject-200", "reject-dict", "reject-array", "reject-img",
    "reject-tinygif", "reject-video", "302", "307",
}
POLICIES = {
    "REJECT", "REJECT-DICT", "REJECT-ARRAY", "REJECT-200", "REJECT-IMG",
    "REJECT-TINYGIF", "REJECT-VIDEO", "REJECT-DROP", "REJECT-NO-DROP",
    "DIRECT", "PROXY",
}


def sections_of(path: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        s = line.strip()
        m = re.fullmatch(r"\[(.+?)\]", s)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        if cur and s and not s.startswith("#"):
            out[cur].append(s)
    return out


def check(path: str) -> list[str]:
    rel = os.path.relpath(path, ROOT)
    errs: list[str] = []
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8")]

    # 1. 头部
    if not lines or not lines[0].startswith("#!name="):
        errs.append("首行不是 #!name=")
    if not any(l.startswith("#!desc=") for l in lines[:5]):
        errs.append("缺少 #!desc=")

    secs = sections_of(path)

    # 2. 分节名
    for name in secs:
        if name not in SECTIONS:
            errs.append(f"未知分节 [{name}]")

    # 3. URL Rewrite
    seen: set[str] = set()
    n_rw = 0
    for line in secs.get("URL Rewrite", []):
        n_rw += 1
        t = line.split()
        if len(t) >= 3 and t[-2] in ("-", "_"):
            pattern, action = " ".join(t[:-2]), t[-1].lower()
        elif len(t) >= 3 and t[-1].lower() in ("302", "307"):
            pattern, action = " ".join(t[:-2]), t[-1].lower()
        else:
            errs.append(f"无法解析的重写行：{line[:100]}")
            continue
        if action not in ACTIONS:
            errs.append(f"非法动作 {action}：{line[:100]}")
        if not pattern.startswith("^") and not pattern.startswith("("):
            errs.append(f"pattern 未锚定：{line[:100]}")
        if pattern in seen:
            errs.append(f"pattern 重复：{line[:100]}")
        seen.add(pattern)
        try:
            re.compile(pattern)
        except re.error as e:
            soft = pattern.replace("(?>", "(?:")
            try:
                re.compile(soft)
            except re.error:
                errs.append(f"pattern 无法编译（{e}）：{line[:100]}")

    # 4. Script
    for line in secs.get("Script", []):
        for key in ("type=", "pattern=", "script-path="):
            if key not in line:
                errs.append(f"脚本行缺少 {key}：{line[:100]}")
        m = re.search(r"pattern=([^,]+)", line)
        if m:
            try:
                re.compile(m.group(1))
            except re.error as e:
                errs.append(f"脚本 pattern 无法编译（{e}）：{line[:100]}")
        if "{{{" in line:
            errs.append(f"脚本行含未替换的参数占位符：{line[:100]}")

    # 5. MITM
    mitm = secs.get("MITM", [])
    if len(mitm) != 1:
        errs.append(f"[MITM] 应当只有一行 hostname，实际 {len(mitm)} 行")
    else:
        if not mitm[0].startswith("hostname"):
            errs.append("[MITM] 行不是 hostname = ...")
        elif "%APPEND%" not in mitm[0]:
            errs.append("[MITM] 缺少 %APPEND%，会覆盖用户配置中的其它解密域名")
        hosts = mitm[0].split("=", 1)[1]
        for h in [x.strip() for x in hosts.split(",") if x.strip()]:
            if h.startswith("%APPEND%"):
                continue
            if " " in h:
                errs.append(f"MITM 域名含空格：{h!r}")

    # 6. Rule
    for line in secs.get("Rule", []):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            errs.append(f"规则字段不足：{line[:100]}")
            continue
        if parts[-1].upper() not in POLICIES:
            errs.append(f"未知策略 {parts[-1]}：{line[:100]}")

    print(f"{rel:<32} 重写 {n_rw:>4}  脚本 {len(secs.get('Script', [])):>3}  "
          f"规则 {len(secs.get('Rule', [])):>3}  "
          f"MITM {len(mitm[0].split(',')) if mitm else 0:>4}  "
          f"{'OK' if not errs else 'FAIL ' + str(len(errs))}")
    return [f"{rel}: {e}" for e in errs]


def check_urls(targets: list[str]) -> list[str]:
    """--check-urls：脚本地址是远程 JS，死链会导致“装了模块但没效果”，值得单独检查一次。"""
    import subprocess
    urls: set[str] = set()
    for t in targets:
        secs = sections_of(t)
        for line in secs.get("Script", []):
            m = re.search(r"script-path=([^,\s]+)", line)
            if m:
                urls.add(m.group(1))
    problems = []
    for u in sorted(urls):
        try:
            code = subprocess.run(
                ["curl", "-sSL", "-o", "/dev/null", "-m", "25", "-w", "%{http_code}", u],
                capture_output=True, text=True, timeout=40).stdout.strip()
        except Exception as e:                      # noqa: BLE001
            code = f"ERR {e}"
        flag = "OK " if code == "200" else "!! "
        print(f"  {flag}{code}  {u}")
        if code != "200":
            problems.append(f"脚本地址不可用（{code}）：{u}")
    return problems


def main() -> int:
    targets = []
    for root, _dirs, files in os.walk(DIST):
        for f in sorted(files):
            if f.endswith((".sgmodule", ".module", ".conf")):
                targets.append(os.path.join(root, f))
    if not targets:
        print("dist/ 下没有找到模块文件，先跑 build.py")
        return 1

    problems: list[str] = []
    for t in sorted(targets):
        problems += check(t)

    print()
    if "--check-urls" in sys.argv:
        print("检查远程脚本地址（18 个左右，需要联网）：")
        problems += check_urls(sorted(targets))
        print()
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for p in problems:
            print("  -", p)
        return 1
    print("全部通过校验。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
