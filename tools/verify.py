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



# --------------------------------------------------------------------------
# 其它客户端格式的校验
# --------------------------------------------------------------------------
LOON_ACTIONS = {"reject", "reject-200", "reject-dict", "reject-array",
                "reject-img", "reject-tinygif", "reject-video", "302", "307"}
RE_CLASH_DOMAIN = re.compile(r"^  - '(\+\.)?[a-z0-9*][a-z0-9.*-]*'$")
RE_CLASH_CLASSICAL = re.compile(r"^  - '(DOMAIN|DOMAIN-SUFFIX),[A-Za-z0-9.*-]+'$")


def check_clash_yaml(path: str) -> list[str]:
    errs: list[str] = []
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8")]
    payload = [l for l in lines if l.startswith("  - ")]
    others = [l for l in lines if l and not l.startswith("#")
              and not l.startswith("  - ") and l.strip() != "payload:"]
    classical = "classical" in path
    rx = RE_CLASH_CLASSICAL if classical else RE_CLASH_DOMAIN
    for l in others:
        errs.append(f"出现了非 payload 行：{l[:60]}")
    for l in payload:
        if not rx.match(l):
            errs.append(f"条目格式不符合 rule-provider 规范：{l[:60]}")
    if len(payload) < 50:
        errs.append(f"条目只有 {len(payload)} 条，疑似导出不完整")
    if len(set(payload)) != len(payload):
        errs.append("存在重复条目")
    try:
        import yaml  # 有就做一次真解析
    except ImportError:
        pass
    else:
        try:
            data = yaml.safe_load("\n".join(lines))
            if not isinstance(data, dict) or "payload" not in data:
                errs.append("YAML 解析后缺少 payload 键")
        except Exception as e:                              # noqa: BLE001
            errs.append(f"YAML 无法解析：{e}")
    print(f"{os.path.relpath(path, ROOT):<44} rule-provider 条目 {len(payload):>4}  "
          f"{'OK' if not errs else 'FAIL ' + str(len(errs))}")
    return [f"{os.path.relpath(path, ROOT)}: {e}" for e in errs]


def check_singbox_json(path: str) -> list[str]:
    import json
    errs: list[str] = []
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:                                  # noqa: BLE001
        errs.append(f"JSON 无法解析：{e}")
        print(f"{os.path.relpath(path, ROOT):<44} FAIL 1")
        return [f"{os.path.relpath(path, ROOT)}: {errs[0]}"]
    if d.get("version") != 1:
        errs.append("version 必须为 1")
    rules = d.get("rules")
    if not isinstance(rules, list) or not rules:
        errs.append("rules 为空")
    else:
        r = rules[0]
        for k in ("domain_suffix", "domain"):
            if not isinstance(r.get(k), list) or not r[k]:
                errs.append(f"rules[0].{k} 为空")
    n = len(rules[0].get("domain_suffix", [])) + len(rules[0].get("domain", [])) if rules else 0
    print(f"{os.path.relpath(path, ROOT):<44} rule-set 条目 {n:>4}  "
          f"{'OK' if not errs else 'FAIL ' + str(len(errs))}")
    return [f"{os.path.relpath(path, ROOT)}: {e}" for e in errs]


def _read_sections(path: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for raw in open(path, encoding="utf-8"):
        s = raw.strip()
        if s.startswith("#!") or not s:
            continue
        m = re.fullmatch(r"\[(.+?)\]", s)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        if cur and not s.startswith("#"):
            out[cur].append(s)
    return out


def check_loon(path: str) -> list[str]:
    errs: list[str] = []
    text = open(path, encoding="utf-8").read()
    if not text.startswith("#!name="):
        errs.append("首行不是 #!name=")
    secs = _read_sections(path)
    for name in secs:
        if name not in ("Mitm", "MITM", "Rewrite", "Script", "General", "Rule"):
            errs.append(f"未知分节 [{name}]")
    n_rw = n_sc = 0
    for line in secs.get("Rewrite", []):
        n_rw += 1
        if line.split()[-1].lower() not in LOON_ACTIONS:
            errs.append(f"重写动作不合法：{line[:80]}")
    for line in secs.get("Script", []):
        if "binary-body-mode" in line:
            errs.append(f"Loon 插件里不应出现协议级脚本（风险分层）：{line[:60]}")
            continue
        n_sc += 1
        if not line.startswith(("http-request", "http-response")):
            errs.append(f"脚本行应以 http-request/http-response 开头：{line[:80]}")
        for key in ("script-path=", "tag="):
            if key not in line:
                errs.append(f"脚本行缺少 {key}：{line[:80]}")
    mitm = secs.get("Mitm") or secs.get("MITM") or []
    if len(mitm) != 1 or not mitm[0].startswith("hostname"):
        errs.append("[Mitm] 应当只有一行 hostname")
    print(f"{os.path.relpath(path, ROOT):<44} 重写 {n_rw:>4}  脚本 {n_sc:>3}  "
          f"{'OK' if not errs else 'FAIL ' + str(len(errs))}")
    return [f"{os.path.relpath(path, ROOT)}: {e}" for e in errs]


def check_qx(path: str) -> list[str]:
    errs: list[str] = []
    secs = _read_sections(path)
    for name in secs:
        if name not in ("rewrite_local", "filter_local", "mitm", "general",
                        "server_local", "policy"):
            errs.append(f"未知分节 [{name}]")
    n_rw = n_ft = 0
    for line in secs.get("rewrite_local", []):
        n_rw += 1
        if " url " not in line:
            errs.append(f"缺少 url 关键字：{line[:80]}")
        elif line.split()[-1].lower() not in LOON_ACTIONS:
            errs.append(f"重写动作不合法：{line[:80]}")
        if "script-" in line:
            errs.append(f"不应出现脚本型重写（未做 QX 脚本移植）：{line[:60]}")
    for line in secs.get("filter_local", []):
        n_ft += 1
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3 or parts[0] not in ("host", "host-suffix", "host-keyword", "host-wildcard"):
            errs.append(f"过滤规则格式不合法：{line[:80]}")
        elif parts[-1].lower() != "reject":
            errs.append(f"过滤策略应为 reject：{line[:80]}")
    mitm = secs.get("mitm", [])
    if len(mitm) != 1 or not mitm[0].startswith("hostname"):
        errs.append("[mitm] 应当只有一行 hostname")
    elif "%APPEND%" not in mitm[0]:
        errs.append("[mitm] 缺少 %APPEND%，会覆盖用户配置")
    print(f"{os.path.relpath(path, ROOT):<44} 重写 {n_rw:>4}  过滤 {n_ft:>4}  "
          f"{'OK' if not errs else 'FAIL ' + str(len(errs))}")
    return [f"{os.path.relpath(path, ROOT)}: {e}" for e in errs]


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
    targets, clash, singbox, loon, qx = [], [], [], [], []
    for root, _dirs, files in os.walk(DIST):
        for f in sorted(files):
            p = os.path.join(root, f)
            if "/clash/" in p and f.endswith(".yaml"):
                clash.append(p)
            elif "/sing-box/" in p and f.endswith(".json"):
                singbox.append(p)
            elif "/loon/" in p and f.endswith(".plugin"):
                loon.append(p)
            elif "/quantumultx/" in p and f.endswith(".conf"):
                qx.append(p)
            elif f.endswith((".sgmodule", ".module")):
                targets.append(p)
    if not targets:
        print("dist/ 下没有找到模块文件，先跑 build.py")
        return 1

    problems: list[str] = []
    print("--- Shadowrocket / Surge 模块 ---")
    for t in sorted(targets):
        problems += check(t)
    for group, fn, label in ((clash, check_clash_yaml, "Clash / Mihomo rule-provider"),
                             (singbox, check_singbox_json, "sing-box rule-set"),
                             (loon, check_loon, "Loon 插件"),
                             (qx, check_qx, "QuantumultX 配置")):
        if group:
            print(f"--- {label} ---")
            for t in sorted(group):
                problems += fn(t)

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
