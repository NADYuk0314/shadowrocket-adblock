# 构建报告

构建时间：2026-09-19 21:02:49

## NoAd.sgmodule

| 项目 | 数量 |
| --- | --- |
| 重写 | 584 |
| 脚本 | 0 |
| 规则 | 76 |
| 头部重写 | 1 |
| MITM 域名 | 345 |
| 被裁掉的 MITM 域名 | 47 |

<details><summary>按 drop 列表剔除 5 条</summary>

- 命中 drop 列表（^https?:\/\/res\.kfc\.com.\cn\/advertisement\/…） → `^https?:\/\/res\.kfc\.com.\cn\/advertisement\/ - reject`
- 命中 drop 列表（^https?:\/\/[^(apple|10010)]+\.(com|cn)\/(a|A)d(…） → `^https?:\/\/[^(apple|10010)]+\.(com|cn)\/(a|A)d(s|v)?(\/|\.js) - reject-img`
- 命中 drop 列表（bilibili\.com\/x\/v\d\/splash\/ - reject…） → `^https?:\/\/app\.bilibili\.com\/x\/v\d\/splash\/ - reject`
- 命中 drop 列表（manga\.bilibili\.com\/twirp\/comic\.v\d\.Comic\/…） → `^https?:\/\/manga\.bilibili\.com\/twirp\/comic\.v\d\.Comic\/Flash - reject`
- 命中 drop 列表（https://aweme.snssdk.com/aweme/v1/…） → `^https?:\/\/api.*\.amemv\.com\/aweme\/v\d\/ - 302`

</details>

<details><summary>自动修正 17 处</summary>

- 补锚点：`^https?://res\.xiaojukeji\.com\/resapi\/activity\/mget…`
- 补锚点：`^https?:\/\/res\.xiaojukeji\.com\/resapi\/activity\/get(Ruled|Preload|…`
- 补锚点：`^https?:\/\/awg\.enmonster\.com\/apa\/(advert\/demand\/home\/poster|in…`
- 转义字符类中的连字符：`^https?://v\d-api\.miaopai\.com/miaopai/advertisement/…`
- 补锚点：`^https://ccsp-egmas.sf-express.com/cx-app-base/base/app/ad/queryAdImag…`
- 转义字符类中的连字符：`^https?:\/\/(gw|heic)\.alicdn\.com\/imgextra\/\w{2}\/[\w!]+-…`
- 转义字符类中的连字符：`^https?:\/\/[\w-.]+\.ott\.cibntv\.net\/[\w\/-]+.mp4\?sid=…`
- 转义字符类中的连字符：`^https?:\/\/[\w-.]+\.ott\.cibntv\.net\/[\w\/-]+.mp4\?ccode=0…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.(amemv|musical|snssdk|tiktokv)\.(com|ly)…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.snssdk\.com\/.+_ad\/…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.snssdk\.com\/motor\/operation\/activity\…`
- 去掉 MITM 条目尾部多余的 .*：`*.pangolin-sdk-toutiao.*` → `*.pangolin-sdk-toutiao`
- 去掉 MITM 条目尾部多余的 .*：`*.pstatp.com.*` → `*.pstatp.com`
- 去掉 MITM 条目尾部多余的 .*：`*.pglstatp-toutiao.com.*` → `*.pglstatp-toutiao.com`
- 去掉 MITM 条目尾部多余的 .*：`gurd.snssdk.com.*` → `gurd.snssdk.com`
- 去掉 MITM 条目尾部多余的 .*：`*.xima*.*` → `*.xima*`
- 去掉 MITM 条目尾部多余的 .*：`*.xmcdn.*` → `*.xmcdn`

</details>

<details><summary>动作冲突 1 处（已按精度保留）</summary>

- `^https?:\/\/m\.client\.10010\.com\/uniAdmsInterface\/getWelcomeAd…`：reject-200 vs reject → 保留 reject-200

</details>

### 提示 1

- `^https?:\/\/(?>heic|gw)\.alicdn\.com\/tfs\/TB1.+?-\d{4}-\d{4…` 含 PCRE 原子组 (?>…)，已按等价写法校验

去重合并：17 条

## NoAd-Plus.sgmodule

| 项目 | 数量 |
| --- | --- |
| 重写 | 584 |
| 脚本 | 61 |
| 规则 | 77 |
| 头部重写 | 1 |
| MITM 域名 | 353 |
| 被裁掉的 MITM 域名 | 39 |

<details><summary>按 drop 列表剔除 6 条</summary>

- 命中 drop 列表（^https?:\/\/res\.kfc\.com.\cn\/advertisement\/…） → `^https?:\/\/res\.kfc\.com.\cn\/advertisement\/ - reject`
- 命中 drop 列表（^https?:\/\/[^(apple|10010)]+\.(com|cn)\/(a|A)d(…） → `^https?:\/\/[^(apple|10010)]+\.(com|cn)\/(a|A)d(s|v)?(\/|\.js) - reject-img`
- 命中 drop 列表（bilibili\.com\/x\/v\d\/splash\/ - reject…） → `^https?:\/\/app\.bilibili\.com\/x\/v\d\/splash\/ - reject`
- 命中 drop 列表（manga\.bilibili\.com\/twirp\/comic\.v\d\.Comic\/…） → `^https?:\/\/manga\.bilibili\.com\/twirp\/comic\.v\d\.Comic\/Flash - reject`
- 命中 drop 列表（https://aweme.snssdk.com/aweme/v1/…） → `^https?:\/\/api.*\.amemv\.com\/aweme\/v\d\/ - 302`
- 命中 drop 列表（fmz200/wool_scripts/main/Scripts/douyin/douyin.j…） → `douyin = type=http-response, pattern=^https?:\/\/aweme\.snssdk\.com\/aweme\/v[12]\/((|follow\/|nearby\/)feed|aweme\/post|hot\/search\/video\/list|mix\/aweme|aweme\/detail)\/\?, script-path=https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/douyin/douyin.js, requires-body=true, max-size=-1, timeout=60`

</details>

<details><summary>自动修正 18 处</summary>

- 补锚点：`^https?://res\.xiaojukeji\.com\/resapi\/activity\/mget…`
- 补锚点：`^https?:\/\/res\.xiaojukeji\.com\/resapi\/activity\/get(Ruled|Preload|…`
- 补锚点：`^https?:\/\/awg\.enmonster\.com\/apa\/(advert\/demand\/home\/poster|in…`
- 转义字符类中的连字符：`^https?://v\d-api\.miaopai\.com/miaopai/advertisement/…`
- 补锚点：`^https://ccsp-egmas.sf-express.com/cx-app-base/base/app/ad/queryAdImag…`
- 转义字符类中的连字符：`^https?:\/\/(gw|heic)\.alicdn\.com\/imgextra\/\w{2}\/[\w!]+-…`
- 转义字符类中的连字符：`^https?:\/\/[\w-.]+\.ott\.cibntv\.net\/[\w\/-]+.mp4\?sid=…`
- 转义字符类中的连字符：`^https?:\/\/[\w-.]+\.ott\.cibntv\.net\/[\w\/-]+.mp4\?ccode=0…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.(amemv|musical|snssdk|tiktokv)\.(com|ly)…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.snssdk\.com\/.+_ad\/…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.snssdk\.com\/motor\/operation\/activity\…`
- 移除未定义参数占位符：tieba = type=http-response,pattern=^https?:\/\/(tiebac|c\.tieba)\.baidu\.com\/c\…
- 去掉 MITM 条目尾部多余的 .*：`*.pangolin-sdk-toutiao.*` → `*.pangolin-sdk-toutiao`
- 去掉 MITM 条目尾部多余的 .*：`*.pstatp.com.*` → `*.pstatp.com`
- 去掉 MITM 条目尾部多余的 .*：`*.pglstatp-toutiao.com.*` → `*.pglstatp-toutiao.com`
- 去掉 MITM 条目尾部多余的 .*：`gurd.snssdk.com.*` → `gurd.snssdk.com`
- 去掉 MITM 条目尾部多余的 .*：`*.xima*.*` → `*.xima*`
- 去掉 MITM 条目尾部多余的 .*：`*.xmcdn.*` → `*.xmcdn`

</details>

<details><summary>动作冲突 1 处（已按精度保留）</summary>

- `^https?:\/\/m\.client\.10010\.com\/uniAdmsInterface\/getWelcomeAd…`：reject-200 vs reject → 保留 reject-200

</details>

### 提示 1

- `^https?:\/\/(?>heic|gw)\.alicdn\.com\/tfs\/TB1.+?-\d{4}-\d{4…` 含 PCRE 原子组 (?>…)，已按等价写法校验

去重合并：17 条

## modules/Bilibili.sgmodule

| 项目 | 数量 |
| --- | --- |
| 重写 | 10 |
| 脚本 | 1 |
| 规则 | 0 |
| 头部重写 | 0 |
| MITM 域名 | 4 |
| 被裁掉的 MITM 域名 | 388 |

<details><summary>按 drop 列表剔除 2 条</summary>

- 命中 drop 列表（^https?:\/\/app\.bilibili\.com\/x\/resource\/ip…） → `^https?:\/\/app\.bilibili\.com\/x\/resource\/ip - reject`
- 命中 drop 列表（^https?:\/\/app\.bilibili\.com\/bilibili\.app\.i…） → `^https?:\/\/app\.bilibili\.com\/bilibili\.app\.interface\.v1\.Search\/Default - reject`

</details>

<details><summary>自动修正 6 处</summary>

- 去掉 MITM 条目尾部多余的 .*：`*.pangolin-sdk-toutiao.*` → `*.pangolin-sdk-toutiao`
- 去掉 MITM 条目尾部多余的 .*：`*.pstatp.com.*` → `*.pstatp.com`
- 去掉 MITM 条目尾部多余的 .*：`*.pglstatp-toutiao.com.*` → `*.pglstatp-toutiao.com`
- 去掉 MITM 条目尾部多余的 .*：`gurd.snssdk.com.*` → `gurd.snssdk.com`
- 去掉 MITM 条目尾部多余的 .*：`*.xima*.*` → `*.xima*`
- 去掉 MITM 条目尾部多余的 .*：`*.xmcdn.*` → `*.xmcdn`

</details>

去重合并：0 条

## modules/YouTube.sgmodule

| 项目 | 数量 |
| --- | --- |
| 重写 | 6 |
| 脚本 | 0 |
| 规则 | 0 |
| 头部重写 | 0 |
| MITM 域名 | 3 |
| 被裁掉的 MITM 域名 | 389 |

<details><summary>自动修正 9 处</summary>

- 转义字符类中的连字符：`(^https?:\/\/[\w-]+\.googlevideo\.com\/(?!dclk_video_ads).+?…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.googlevideo\.com\/(?!(dclk_video_ads|vid…`
- 转义字符类中的连字符：`^https?:\/\/[\w-]+\.googlevideo\.com\/initplayback.+&oad…`
- 去掉 MITM 条目尾部多余的 .*：`*.pangolin-sdk-toutiao.*` → `*.pangolin-sdk-toutiao`
- 去掉 MITM 条目尾部多余的 .*：`*.pstatp.com.*` → `*.pstatp.com`
- 去掉 MITM 条目尾部多余的 .*：`*.pglstatp-toutiao.com.*` → `*.pglstatp-toutiao.com`
- 去掉 MITM 条目尾部多余的 .*：`gurd.snssdk.com.*` → `gurd.snssdk.com`
- 去掉 MITM 条目尾部多余的 .*：`*.xima*.*` → `*.xima*`
- 去掉 MITM 条目尾部多余的 .*：`*.xmcdn.*` → `*.xmcdn`

</details>

去重合并：0 条

## modules/Experimental-Proto.sgmodule

| 项目 | 数量 |
| --- | --- |
| 重写 | 0 |
| 脚本 | 10 |
| 规则 | 0 |
| 头部重写 | 0 |
| MITM 域名 | 9 |
| 被裁掉的 MITM 域名 | 383 |

<details><summary>按 drop 列表剔除 1 条</summary>

- 命中 drop 列表（fmz200/wool_scripts/main/Scripts/douyin/douyin.j…） → `douyin = type=http-response, pattern=^https?:\/\/aweme\.snssdk\.com\/aweme\/v[12]\/((|follow\/|nearby\/)feed|aweme\/post|hot\/search\/video\/list|mix\/aweme|aweme\/detail)\/\?, script-path=https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/douyin/douyin.js, requires-body=true, max-size=-1, timeout=60`

</details>

<details><summary>自动修正 10 处</summary>

- 移除未定义参数占位符：tieba = type=http-response,pattern=^https?:\/\/(tiebac|c\.tieba)\.baidu\.com\/c\…
- 移除未定义参数占位符：youtubead = type=http-request,pattern=^https:\/\/youtubei\.googleapis\.com\/yout…
- 移除未定义参数占位符：youtubead = type=http-response,pattern=^https:\/\/youtubei\.googleapis\.com\/you…
- 实验模块只保留协议级脚本：共 10 条
- 去掉 MITM 条目尾部多余的 .*：`*.pangolin-sdk-toutiao.*` → `*.pangolin-sdk-toutiao`
- 去掉 MITM 条目尾部多余的 .*：`*.pstatp.com.*` → `*.pstatp.com`
- 去掉 MITM 条目尾部多余的 .*：`*.pglstatp-toutiao.com.*` → `*.pglstatp-toutiao.com`
- 去掉 MITM 条目尾部多余的 .*：`gurd.snssdk.com.*` → `gurd.snssdk.com`
- 去掉 MITM 条目尾部多余的 .*：`*.xima*.*` → `*.xima*`
- 去掉 MITM 条目尾部多余的 .*：`*.xmcdn.*` → `*.xmcdn`

</details>

去重合并：0 条

## 其它客户端格式

```
导出 dist/clash/NoAd-AdDomains.yaml                    2134 bytes
  导出 dist/clash/NoAd-AdDomains-classical.yaml          2772 bytes
  导出 dist/sing-box/NoAd-ruleset.json                   2048 bytes
  导出 dist/loon/NoAd-Plus.plugin                       65722 bytes
  导出 dist/loon/Bilibili.plugin                         1633 bytes
  导出 dist/quantumultx/NoAd-Plus.conf                  56132 bytes
  导出 dist/quantumultx/Bilibili.conf                    1286 bytes
```
