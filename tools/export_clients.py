#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_clients.py —— 把 dist/ 里的 Shadowrocket/Surge 模块导出成其它客户端可用的格式。

为什么不能"全量移植"：
  Clash 系（Clash Mi / Mihomo / Clash Verge / Stash / sing-box）**没有 URL 重写和 MITM 能力**，
  只能按域名/IP 分流。所以对它们只能导出「域名级拦截」这一部分。
  真正需要改请求/改响应体的开屏、信息流广告，只有 Surge 系（Surge / Shadowrocket / Loon）和
  QuantumultX 才能拦。

导出内容：
  dist/clash/NoAd-AdDomains.yaml            rule-provider（behavior: domain）
  dist/clash/NoAd-AdDomains-classical.yaml  rule-provider（behavior: classical）
  dist/sing-box/NoAd-ruleset.json           sing-box rule-set
  dist/loon/*.plugin                        Loon 插件（Rewrite + Script + Mitm）
  dist/quantumultx/*.conf                   QuantumultX（rewrite_local + filter_local + mitm）

用法：python3 tools/export_clients.py   （build.py 会自动调用）
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")

SECTIONS = {"Rule", "URL Rewrite", "Header Rewrite", "Body Rewrite", "Script",
            "MITM", "General", "Host", "Map Local", "Panel"}
# Loon / QuantumultX 认的重写动作
LOON_ACTIONS = {"reject", "reject-200", "reject-dict", "reject-array",
                "reject-img", "reject-tinygif", "reject-video", "302", "307"}

REPO_URL = "https://github.com/NADYuk0314/shadowrocket-adblock"


def parse_module(path: str) -> dict[str, list[str]]:
    """读取模块文件，返回 {分节名: [行]}（跳过注释与空行）。"""
    out: dict[str, list[str]] = {}
    cur = None
    if not os.path.exists(path):
        return out
    for raw in open(path, encoding="utf-8"):
        s = raw.strip()
        if not s:
            continue
        m = re.fullmatch(r"\[(.+?)\]", s)
        if m and m.group(1) in SECTIONS:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        if s.startswith("#") or cur is None:
            continue
        out[cur].append(s)
    return out


def parse_script_line(line: str) -> tuple[str, dict[str, str]]:
    """Surge 风格脚本行 -> (名字, {k: v})。pattern 里可能含逗号，所以只在 ",键=" 处切。"""
    name, _, body = line.partition("=")
    kv: dict[str, str] = {}
    # 注意：上游有的模块写成 `type=xxx, pattern=yyy`（逗号后有空格），所以空格要做成可选的
    for part in re.split(r",\s*(?=[A-Za-z][A-Za-z0-9-]*=)", body):
        k, _, v = part.partition("=")
        if k.strip():
            kv[k.strip()] = v.strip()
    return name.strip(), kv


def parse_ad_domains() -> tuple[list[str], list[str]]:
    """从 src/rules/ad-domains.list 取出 (DOMAIN-SUFFIX 列表, DOMAIN 精确列表)。"""
    suffix: list[str] = []
    exact: list[str] = []
    for raw in open(os.path.join(SRC, "rules", "ad-domains.list"), encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3 or parts[2].upper() not in ("REJECT", "REJECT-DROP"):
            continue
        if parts[0].upper() == "DOMAIN-SUFFIX" and parts[1] not in suffix:
            suffix.append(parts[1])
        elif parts[0].upper() == "DOMAIN" and parts[1] not in exact:
            exact.append(parts[1])
    return suffix, exact


def mitm_hosts(secs: dict[str, list[str]]) -> list[str]:
    hosts: list[str] = []
    for line in secs.get("MITM", []):
        if not line.lower().startswith("hostname"):
            continue
        value = line.split("=", 1)[1] if "=" in line else ""
        value = value.replace("%APPEND%", " ")
        for h in value.split(","):
            h = h.strip()
            if h and not h.startswith("-") and h not in hosts:
                hosts.append(h)
    return hosts


def split_rewrite(line: str) -> tuple[str, str | None, str] | None:
    """`pattern - action` / `pattern replacement 302` -> (pattern, replacement, action)"""
    t = line.split()
    if len(t) >= 3 and t[-2] in ("-", "_"):
        return " ".join(t[:-2]), None, t[-1].lower()
    if len(t) >= 3 and t[-1] in ("302", "307"):
        return " ".join(t[:-2]), t[-2], t[-1].lower()
    return None


# --------------------------------------------------------------------------
# Clash / sing-box：只有域名级拦截可移植
# --------------------------------------------------------------------------
def export_clash(suffix: list[str], exact: list[str]) -> list[str]:
    os.makedirs(os.path.join(DIST, "clash"), exist_ok=True)
    written = []

    # behavior: domain —— mihomo 约定：'+.x.com' 表示域名及其子域，'x.com' 表示精确匹配
    lines = [
        "# NAME: NoAd-AdDomains",
        "# AUTHOR: NoAd (shadowrocket-adblock)",
        f"# REPO: {REPO_URL}",
        "# USAGE: Clash Mi / Mihomo / Clash Verge / Stash —— rule-provider, behavior: domain",
        "# 说明：Shadowrocket 系模块里的 URL 重写与脚本无法移植到 Clash，",
        "#       这里只导出「域名级拦截」部分（不依赖 MITM，直接生效）。",
        f"# DOMAIN-SUFFIX: {len(suffix)}",
        f"# DOMAIN: {len(exact)}",
        f"# TOTAL: {len(suffix) + len(exact)}",
        "",
        "payload:",
    ]
    lines += [f"  - '+.{d}'" for d in suffix]
    lines += [f"  - '{d}'" for d in exact]
    p = os.path.join(DIST, "clash", "NoAd-AdDomains.yaml")
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    written.append(p)

    # behavior: classical —— 保留完整的规则写法，便于和别的规则混用
    lines = [
        "# NAME: NoAd-AdDomains-Classical",
        "# AUTHOR: NoAd (shadowrocket-adblock)",
        f"# REPO: {REPO_URL}",
        "# USAGE: rule-provider, behavior: classical",
        f"# TOTAL: {len(suffix) + len(exact)}",
        "",
        "payload:",
    ]
    lines += [f"  - 'DOMAIN-SUFFIX,{d}'" for d in suffix]
    lines += [f"  - 'DOMAIN,{d}'" for d in exact]
    p = os.path.join(DIST, "clash", "NoAd-AdDomains-classical.yaml")
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    written.append(p)
    return written


def export_singbox(suffix: list[str], exact: list[str]) -> list[str]:
    os.makedirs(os.path.join(DIST, "sing-box"), exist_ok=True)
    data = {
        "version": 1,
        "rules": [
            {
                "domain_suffix": suffix,
                "domain": exact,
            }
        ],
    }
    p = os.path.join(DIST, "sing-box", "NoAd-ruleset.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return [p]


# --------------------------------------------------------------------------
# Loon：插件格式，重写/脚本语法与 Surge 略有差别
# --------------------------------------------------------------------------
def export_loon(module_path: str, out_name: str, name: str, desc: str) -> list[str]:
    secs = parse_module(module_path)
    if not secs:
        return []
    os.makedirs(os.path.join(DIST, "loon"), exist_ok=True)

    out = [
        f"#!name={name}",
        f"#!desc={desc}",
        f"#!openUrl={REPO_URL}",
        "#!author=规则聚合自 blackmatrix7 / app2smile / deezertidal / ddgksf2013 / lalifeier，由 NoAd 构建脚本整理",
        "#!tag=去广告,NoAd",
        "# 由 tools/export_clients.py 从 Shadowrocket 模块转换，未在真机验证，有问题请到仓库提 issue。",
        "# 按风险分层原则：协议级（binary-body-mode）脚本未导出；头部重写（Header Rewrite）未导出。",
    ]

    hosts = mitm_hosts(secs)
    if hosts:
        out += ["", "[Mitm]", "hostname = " + ", ".join(hosts)]

    rewrites = []
    seen = set()
    for line in secs.get("URL Rewrite", []):
        r = split_rewrite(line)
        if not r:
            continue
        pattern, replacement, action = r
        if action not in LOON_ACTIONS:
            continue
        loon_line = f"{pattern} {replacement} {action}" if replacement else f"{pattern} {action}"
        if loon_line not in seen:
            seen.add(loon_line)
            rewrites.append(loon_line)
    if rewrites:
        out += ["", "[Rewrite]"] + rewrites

    # 脚本：Surge 的 `name = type=...,pattern=...,script-path=...`
    #   转成 Loon 的 `<type> <pattern> script-path=..., requires-body=true, timeout=10, tag=name`
    scripts = []
    for line in secs.get("Script", []):
        name_, kv = parse_script_line(line)
        if "binary-body-mode" in kv:      # 协议级改写不导出（风险分层）
            continue
        pattern, url = kv.get("pattern"), kv.get("script-path")
        stype = kv.get("type", "http-response")
        if not pattern or not url:
            continue
        opts = [f"script-path={url}"]
        if kv.get("requires-body") in ("1", "true"):
            opts.append("requires-body=true")
        opts.append("timeout=10")
        opts.append(f"tag={name_}")
        scripts.append(f"{stype} {pattern} " + ", ".join(opts))
    if scripts:
        out += ["", "[Script]"] + scripts

    p = os.path.join(DIST, "loon", out_name)
    open(p, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")
    return [p]


# --------------------------------------------------------------------------
# QuantumultX：conf 格式；脚本 API 与 Surge 不同，因此只导出重写与域名过滤
# --------------------------------------------------------------------------
def export_qx(module_path: str, out_name: str, name: str, desc: str,
              suffix: list[str] | None, exact: list[str] | None) -> list[str]:
    secs = parse_module(module_path)
    if not secs:
        return []
    os.makedirs(os.path.join(DIST, "quantumultx"), exist_ok=True)

    out = [
        f"# {name}",
        f"# {desc}",
        f"# {REPO_URL}",
        "# 由 tools/export_clients.py 从 Shadowrocket 模块转换，未在真机验证。",
        "# 只包含重写规则与域名过滤：QuantumultX 的脚本 API 与 Surge 不同，未做脚本移植；",
        "#       需要脚本型去广告请用上游 app2smile 等仓库的 QX 原生版本。",
    ]

    rewrites = []
    seen = set()
    for line in secs.get("URL Rewrite", []):
        r = split_rewrite(line)
        if not r:
            continue
        pattern, replacement, action = r
        if action not in LOON_ACTIONS:
            continue
        qx_line = f"{pattern} url {action} {replacement}" if replacement else f"{pattern} url {action}"
        if qx_line not in seen:
            seen.add(qx_line)
            rewrites.append(qx_line)
    if rewrites:
        out += ["", "[rewrite_local]"] + rewrites

    if suffix or exact:
        out += ["", "[filter_local]"]
        out += [f"host-suffix, {d}, reject" for d in (suffix or [])]
        out += [f"host, {d}, reject" for d in (exact or [])]

    hosts = mitm_hosts(secs)
    if hosts:
        out += ["", "[mitm]", "hostname = %APPEND% " + ", ".join(hosts)]

    p = os.path.join(DIST, "quantumultx", out_name)
    open(p, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")
    return [p]


def main() -> int:
    suffix, exact = parse_ad_domains()
    if not suffix and not exact:
        print("没有读到域名规则，先跑 build.py", file=sys.stderr)
        return 1

    written: list[str] = []
    written += export_clash(suffix, exact)
    written += export_singbox(suffix, exact)

    written += export_loon(
        os.path.join(DIST, "NoAd-Plus.sgmodule"), "NoAd-Plus.plugin",
        "NoAd Plus（去广告·增强版）",
        "通用App/微博/知乎/小红书/阅读音乐类去广告；不含协议级改写。")
    written += export_loon(
        os.path.join(DIST, "modules", "Bilibili.sgmodule"), "Bilibili.plugin",
        "NoAd · 哔哩哔哩",
        "B站开屏、首页推荐流、搜索默认词、相关推荐、漫画广告。")

    written += export_qx(
        os.path.join(DIST, "NoAd-Plus.sgmodule"), "NoAd-Plus.conf",
        "NoAd Plus（去广告·增强版）",
        "通用App/微博/知乎/小红书/阅读音乐类去广告。",
        suffix, exact)
    written += export_qx(
        os.path.join(DIST, "modules", "Bilibili.sgmodule"), "Bilibili.conf",
        "NoAd · 哔哩哔哩", "B站开屏、首页推荐流、搜索默认词等。",
        None, None)

    for p in written:
        print(f"  导出 {os.path.relpath(p, ROOT):<46} {os.path.getsize(p):>7} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
