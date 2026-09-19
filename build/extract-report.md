# 抽取报告

### lal_AdBlockLite.sgmodule 无法解析的行（3）
    ^https:\/\/gab\.122\.gov\.cn\/eapp\/m\/sysquery - rejinitect   # 未知动作 'rejinitect'
    ^https?:\/\/bp-image\.bestv\.com\.cn\/[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{25}\.jpg url reject-20   # 未知动作 'reject-20'
    ^https?:\/\/ad\.mcloud\.139\.com\/advertapi\/adv-filter\/adv-filter\/AdInfoFilter\/getAdInfos - reject-d   # 未知动作 'reject-d'

- `10-general`：重写 502 条，脚本 0 条，规则 0 条
- `20-ad-sdk`：重写 0 条，脚本 1 条，规则 0 条
### d_biliad.module 无法解析的行（1）
    (^https?:\/\/app\.biliintl.com\/intl\/.+)(&sim_code=\d+)(.+)-302$1$3   # tokens<2

- `30-bilibili`：重写 11 条，脚本 2 条，规则 0 条
- `40-weibo`：重写 17 条，脚本 19 条，规则 0 条
- `50-zhihu`：重写 20 条，脚本 20 条，规则 1 条
- `60-xiaohongshu`：重写 4 条，脚本 11 条，规则 0 条
- `70-reading-music`：重写 27 条，脚本 13 条，规则 0 条
- `80-others`：重写 35 条，脚本 6 条，规则 0 条
- `90-youtube`：重写 6 条，脚本 3 条，规则 0 条
