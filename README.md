# NoAd —— Shadowrocket 去广告模块

把 GitHub 上几个长期维护的去广告模块（blackmatrix7 / app2smile / deezertidal / ddgksf2013 / Maasea / lalifeier …）
合并、纠错、按需拆分后，产出可以直接导入 Shadowrocket 的模块文件。

不是简单拼接：上游规则里有 **4 条因为写错动作/域名而完全失效的规则**、**1 条会误伤正常请求的过宽规则**、
**57 个「规则写了但没加入解密清单，所以永远不会命中」的域名**，以及大量重复条目。这些都由脚本逐条挑出来并处理，
每一次改动都记录在 `build/BUILD_REPORT.md` 里。

---

## 一、五个文件怎么选

| 文件 | 内容 | 建议 |
| --- | --- | --- |
| `dist/NoAd.sgmodule` | **584 条 URL 重写 + 76 条域名拦截，零脚本、零协议改写** | **首选**。稳定、省电、不动 App 的私有协议 |
| `dist/NoAd-Plus.sgmodule` | 上面全部 + 61 条**文本/JSON 类**脚本（广告联盟 SDK、微博/知乎/小红书信息流、起点、腾讯新闻、喜马拉雅） | 想把信息流里的推广也清干净时用 |
| `dist/modules/Bilibili.sgmodule` | B站 9 条规则 + 1 条 JSON 脚本（开屏、首页推荐流、搜索默认词、相关推荐、漫画广告） | **B站 必须单独装这一个**，主模块不碰 B站 |
| `dist/modules/YouTube.sgmodule` | 6 条重写（贴片/首页广告请求） | 看 YouTube 就装，不看不用装 |
| `dist/modules/Experimental-Proto.sgmodule` | **协议级改写（gRPC/protobuf）**：B站视频详情与动态、贴吧列表、Spotify、百度地图、网易云、YouTube | ⚠️ 实验性，见下文，出问题**先删这个** |

主模块（`NoAd` / `NoAd-Plus`）**任选一个**；`modules/` 下的三个按需叠加。同类模块不要重复装。

### ⚠️ 为什么 B站 / YouTube 要单独一个模块，还有那个"实验模块"

因为去广告有两类完全不同的做法：

1. **改 URL**（`[URL Rewrite]` + 域名规则）——只是拦掉请求，App 拿不到广告而已，风险低。
2. **改响应体**（`[Script]`）——要看懂 App 的返回内容再删掉广告字段。这一步分成两档：
   - 文本/JSON 改写（`requires-body=1`）：返回的是 JSON，改坏了顶多是某个列表空掉，**跨客户端兼容性最好**，所以留在 Plus 里。
   - **协议级改写**（`binary-body-mode=1`，gRPC / protobuf 二进制）：要解二进制协议再重新编码，上游 app2smile 只声明支持 Surge / Loon / QuantumultX，**并未声明支持 Shadowrocket**。一旦小火箭侧的解码/回写与脚本预期不一致，返回体就会损坏。

B站 那个 proto 脚本改的正好是 `bilibili.app.viewunite.v1.View/View`（**视频详情**）和动态接口 —— 视频详情加载失败，视频和评论区就会一起刷不出来。所以现在：

- 这个脚本被移进了 `Experimental-Proto.sgmodule`，**默认不装**；
- B站 从主模块里**完全移出**（连之前夹在通用段落里的 2 条开屏规则也一并移走，主模块对 B站 零改动）；
- 另外两条"不是广告、但可能影响播放"的 B站 规则（`x/resource/ip` 地区探测、gRPC 搜索默认词）也从默认模块里移出，改成了注释备选，见 `src/additions/30-bilibili.conf`。

## 二、安装

### A. 用在线地址（推荐，可自动更新）

Shadowrocket → 配置 → 模块 → 右上角 `➕` → 粘贴下面的地址 → 下载。
以后规则更新了，点模块里的「更新」即可，不用重新导入。

| 模块 | 地址 |
| --- | --- |
| NoAd（纯规则版） | `https://raw.githubusercontent.com/NADYuk0314/shadowrocket-adblock/main/dist/NoAd.sgmodule` |
| NoAd Plus（含文本脚本） | `https://raw.githubusercontent.com/NADYuk0314/shadowrocket-adblock/main/dist/NoAd-Plus.sgmodule` |
| B站（可选） | `https://raw.githubusercontent.com/NADYuk0314/shadowrocket-adblock/main/dist/modules/Bilibili.sgmodule` |
| YouTube（可选） | `https://raw.githubusercontent.com/NADYuk0314/shadowrocket-adblock/main/dist/modules/YouTube.sgmodule` |
| 协议级改写（实验性） | `https://raw.githubusercontent.com/NADYuk0314/shadowrocket-adblock/main/dist/modules/Experimental-Proto.sgmodule` |

> ⚠️ 国内直连 `raw.githubusercontent.com` 经常被墙，如果下载失败：先把小火箭切到「代理」模式或换个能通的节点再添加；
> 实在不行用下面 B / C 两种方式。
> ⚠️ 模块里的 [Rule] 只在「全局路由 = 配置」时生效，但**下载模块本身**不受这个限制。

### B. 本地临时服务（不改动任何线上内容）

```bash
cd dist && python3 -m http.server 8000
# 查本机内网 IP：ipconfig getifaddr en0
```

然后在小火箭里添加 `http://<你的电脑IP>:8000/NoAd.sgmodule`（手机和电脑要在同一个 Wi-Fi）。
缺点是电脑关机后「更新模块」会失败；已下载的内容不受影响。

### C. 复制内容新建本地模块

Shadowrocket → 配置 → 模块 → 新建模块 → 把文件内容整段粘进去 → 保存。
适合只想装一次、不想联外网的场景（Mac 上可以 `pbcopy < dist/NoAd-Plus.sgmodule` 走通用剪贴板粘贴）。

**B. 用电脑在局域网里发一个临时 HTTP 服务**

```bash
cd dist && python3 -m http.server 8000
# 查本机内网 IP：ipconfig getifaddr en0
```

然后在小火箭里添加 `http://<你的电脑IP>:8000/NoAd.sgmodule`（注意手机和电脑要在同一个 Wi-Fi）。

**C. 直接复制内容新建本地模块**
Shadowrocket → 配置 → 模块 → 新建模块 → 把文件内容整段粘进去 → 保存。

## 三、必做的三项设置（不做的话规则不生效）

1. **开启 HTTPS 解密**
   配置 → 点当前配置的 `ⓘ` → HTTPS 解密 → 证书 → 生成新的 CA 证书 → 安装描述文件 →
   系统设置 → 通用 → 关于本机 → 证书信任设置 → 打开对 Shadowrocket 证书的信任。
   > URL 重写要改的是 HTTPS 请求，不解密就只能看着它过去。

2. **全局路由设为「配置」**
   模块里的 `[Rule]` 只在「配置」模式下生效。
   如果你习惯用「全局路由 = 代理」，就在配置的 `[General]`（不是模块里）加一行：
   ```
   always-reject-url-rewrite = true
   ```
   这样 URL 重写的 REJECT 策略在所有路由模式下都会生效。

3. **系统版本 iOS 15 或更高**
   iOS 15 起网络扩展内存上限从 15 MB 提到 50 MB；低版本可能因为内存不足出现模块失效甚至 VPN 断开。

## 四、覆盖范围

| 分类 | 覆盖对象 | 规则来源 |
| --- | --- | --- |
| 通用 App | 500+ 条端点：58同城、淘宝/闲鱼/飞猪、爱奇艺、百度网盘、贝壳、必胜客、菜鸟、车来了、大众点评、豆瓣、滴滴、得物、饿了么、番茄小说、富途、各大银行 App、京东、驾考宝典、美团、猫眼、麦当劳、拼多多、去哪儿、顺丰、山姆、雪球、微信、中国移动/联通/电信、中通、最右、转转 … | AdBlockLite（blackmatrix7/app2smile/zwf23/RuCu6）、NoAd（Tartarus2014） |
| 广告联盟 SDK | 穿山甲、优量汇、快手联盟的激励视频/插屏/开屏响应体改写 | app2smile/rules `adsense.js` |
| B站（独立模块） | 开屏、首页推荐流、搜索默认词、相关推荐、漫画广告 | ddgksf2013、bm7、app2smile |
| 微博 | 首页/超话/发现页广告、开屏、评论区推广、创作者广告共享计划 | lalifeier（RuCu6/zmqcherish）、deezertidal |
| 知乎 | 开屏、悬浮框、推荐流、回答列表、预置搜索词 | blackmatrix7、app2smile、lalifeier |
| 小红书 | 信息流推广、惊喜弹窗、搜索页、开屏、水印 | lalifeier（RuCu6/fmz200） |
| 阅读 / 音乐 | 起点、网易云音乐、喜马拉雅、Spotify | app2smile、lalifeier（RuCu6/Keywos）、ddgksf2013 |
| 其它 | 抖音、高德地图、菜鸟、什么值得买、百度地图、贴吧、腾讯新闻 | fmz200、RuCu6、app2smile |
| 域名级拦截 | 76 条高置信度广告域名（Google/字节/腾讯/阿里广告平台 + 20 个海外广告 SDK） | 手工整理，不依赖解密即可生效 |

## 五、相对于上游，我改了什么

全部改动都可在 `build/BUILD_REPORT.md` 里逐条核对。

**① 修好 4 条「写了但其实一直不生效」的规则**

| 上游写法 | 问题 | 处理 |
| --- | --- | --- |
| `... /sysquery - rejinitect` | 动作名拼错（`rejinitect`），非法 | 剔除（同目标已有精确规则 `/sysquery/adver$`） |
| `...bestv... .jpg url reject-20` | 动作名少个 0 | 改为 `reject-img`（图片请求返回 1px 图） |
| `...getAdInfos - reject-d` | 动作名残缺 | 改为 `reject-dict` |
| `res.kfc.com.\cn/advertisement/` | 域名写错（`.c` 被当成控制字符 `\cn`） | 改为 `res.kfc.com.cn` |

**② 删掉 1 条会误伤正常请求的过宽规则**
`^https?://[^(apple|10010)]+\.(com|cn)/(a|A)d(s|v)?(/|\.js)` —— 作者本意是「排除 10010 相关域名」，
但 `[^(apple|10010)]` 在正则里是「不含这些字符的任意字符」，实际会把 `https://t.snssdk.com/ad/...` 这类
正常路径也替换成 1px 图。剔除后中国联通的广告端点由另外几条精确规则负责。

**③ 补上 59 个被遗漏的 MITM 域名**
重写规则匹配的是 `https://<域名>/...`，但如果这个域名不在 `[MITM]` 清单里，HTTPS 根本没解密，
规则永远不会命中——上游存在大量这种「静默失效」。脚本把模块里每条规则的域名和 MITM 清单做了交叉比对，
补进了 `image1.ccb.com`、`wmapi.meituan.com`、`dsp.toutiao.com`、`c.tieba.baidu.com`、`qt.qq.com` 等 59 个精确域名
（其中最后 2 个是喜马拉雅：上游把解密域名写成 `*.xmcdn.*`，规范化后覆盖不到规则真正用的 `.com` 后缀）。
另外明确列出了**故意不补**的那些（如 `*.byteimg.com`：解密代价大于收益），见 `src/mitm/skip.hosts`。

**④ 收敛解密范围（对省电和隐私都有影响）**
上游常用 `*.weibo.cn` 这类大通配，会把整个域名的流量都拉进解密。这个模块在生成 `[MITM]` 时改为：
规则里写的是精确域名，就只解密那个精确域名，并自动挑最窄的条目。
结果：NoAd 的解密清单为 345 条（上游 336 条 + 手工补充 59 条，去掉重复，再裁掉与现有规则无关的部分），
且**新增了一条兜底检查**——
任何会命中 `apple.com`、`google.com` 等无关域名的 MITM 条目（比如上游混进来的 `*.*`）一律拒绝生成。
同时把 `*.pstatp.com.*`、`gurd.snssdk.com.*` 这类尾部多余通配（会让 `x.pstatp.com.evil.tld` 也命中）清理掉。

**⑤ 正则兼容性修正**
`[\w-.]` 这种「连字符紧跟类转义」的写法在 PCRE 里合法，但 iOS 的 `NSRegularExpression` 可能直接报非法区间，
共修正 7 处为 `[\w\-.]`。另有 4 条规则缺少行首锚点 `^`，已补上（语义不变、匹配更精确）；
上游 6 处 `*.xxx.com.*` 式的尾部多余通配也已清理。

**⑥ 剔除失效的第三方脚本**
抖音那条脚本引用的 `fmz200/wool_scripts/Scripts/douyin/douyin.js` 已被上游删除（实测 404）；
同时移除了配套的 `aweme.snssdk.com` 302 跳转（它是配合脚本做无水印下载的，与去广告无关，留着只会改变抖音 API 走向）。
`tools/verify.py --check-urls` 会定期检查所有脚本地址是否还能访问。

**⑦ 拆成「零脚本」与「含脚本」两个版本**
上游模块普遍把脚本和规则混在一起，脚本地址失效时整条链路一起坏，很难排查。现在标准版完全不含脚本。

**⑧ 去重与合并**
跨模块重复的 pattern 会去重（17 条），同一个 pattern 出现不同动作时保留更精确的那个
（例如 `getWelcomeAd` 同时有 `reject` 和 `reject-200`，保留 `reject-200`）。

**⑨ 把"高风险"和"去广告"拆开（因为踩过坑）**
第一版把 B站 的 gRPC/protobuf 改写脚本放进了增强版，实测会出现**视频和评论区一起刷不出来**——
原因见第一节的说明。现在按风险分三层：纯规则（NoAd）→ 文本/JSON 脚本（Plus）→ 协议级改写（实验模块，默认不装）。
主模块对 B站 零改动，要 B站 去广告就单独装 `modules/Bilibili.sgmodule`。

**⑩ 开屏广告改成硬拦（不再依赖脚本）**
上游处理 B站 开屏是「`splash/show` 拒绝 + `splash/list` 交给 JS 脚本清理」。脚本依赖小火箭的 JS 引擎与参数支持，
一旦没跑起来，开屏列表就照常返回广告数据 —— 表现就是"规则都装了，开屏广告还在"。
现在整个 `/x/v2/splash/` 命名空间直接返回空 JSON，不依赖任何脚本。

## 六、校验机制

```bash
python3 build.py                 # 生成 dist/ 与 build/BUILD_REPORT.md
python3 tools/verify.py          # 独立校验产物（格式、动作白名单、正则、MITM 是否 %APPEND%）
python3 tools/verify.py --check-urls   # 额外检查 18 个远程脚本地址是否还活着
```

`verify.py` 与 `build.py` 相互独立：前者按「一个全新解析器」的标准重新读一遍产物，
包括检查 `[URL Rewrite]` 每行动作是否在合法集合内、pattern 是否能编译、是否有重复、
`[MITM]` 是否带 `%APPEND%`（漏了会覆盖掉用户配置里的其它解密域名）。

## 七、已知风险

- **「看广告解锁」类功能会失效**：域名级拦截把广告 SDK 直接拒掉，App 拿不到广告自然也没法发奖励。
- **个别 App 的营销横幅属于正常功能**：比如银行 App 的活动位。介意的话删掉对应的重写行即可。
- **MITM 本身的风险**：开启 HTTPS 解密意味着模块作者（或脚本地址的所有者）理论上能看到解密后的流量。
  这个模块引用的脚本来自公开仓库，但**脚本内容是随时可能变化的**——在意的话用零脚本的 `NoAd.sgmodule`。
- **上游失效**：规则是抓取上游生成的，上游改路径需要重新跑更新流程。
- **不要和同类模块叠加**：AdBlockLite、NoAd、各种 App 专用模块同时开会重复拦截，出问题时难以定位。

## 八、更新规则

```bash
bash tools/fetch_upstream.sh    # 重新抓取上游模块到 vendor/
python3 tools/extract.py        # 重新生成 src/ 里的规则源文件
python3 build.py                # 重新合并、纠错、去重、校验
python3 tools/verify.py         # 校验产物
```

手工维护的内容放在 `src/additions/`（增补与修正）、`src/mitm/extra.hosts`（补充解密域名）、
`src/mitm/skip.hosts`（故意不解密的域名）、`src/rules/ad-domains.list`（域名级拦截）。
`extract.py` 只覆盖 `src/rewrite|scripts|rules/` 和 `src/mitm/collected.hosts`，不会碰上述手工文件。

## 九、目录结构

```
shadowrocket-adblock/
├── dist/                       # 成品（导入小火箭的就是这里）
│   ├── NoAd.sgmodule
│   ├── NoAd-Plus.sgmodule
│   └── modules/YouTube.sgmodule
├── src/                        # 规则源
│   ├── rewrite/                # 按分类整理的重写规则（由 extract.py 生成）
│   ├── scripts/                # 脚本规则（由 extract.py 生成）
│   ├── rules/                  # [Rule] 规则（ad-domains.list 为手工维护）
│   ├── mitm/                   # MITM 域名（collected 自动，extra/skip 手工）
│   └── additions/              # 人工增补与修正、drop 列表
├── vendor/                     # 上游模块原始文件（可随时重新抓取）
├── tools/                      # fetch_upstream.sh / extract.py / verify.py
├── build.py                    # 合并 + 纠错 + 去重 + 交叉校验
└── build/BUILD_REPORT.md       # 每次构建的完整改动清单
```

## 十、来源与致谢

规则全部来自以下开源项目，模块只是把它们合并与纠错，版权归原作者：

- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)
- [app2smile/rules](https://github.com/app2smile/rules)
- [deezertidal/shadowrocket-rules](https://github.com/deezertidal/shadowrocket-rules)
- [ddgksf2013/Rewrite](https://github.com/ddgksf2013/Rewrite)
- [lalifeier/Shadowrocket](https://github.com/lalifeier/Shadowrocket)
- [Maasea/sgmodule](https://github.com/Maasea/sgmodule)
- [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts)
- [Keywos/rule](https://github.com/Keywos/rule)
- 语法参考：[LOWERTOP/Shadowrocket 使用手册](https://github.com/LOWERTOP/Shadowrocket)

仅供学习与交流，请勿用于商业用途；使用第三方脚本的风险请自行评估。
