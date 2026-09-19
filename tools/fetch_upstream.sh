#!/usr/bin/env bash
# 拉取上游模块到 vendor/（可重复执行，用于更新规则）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR"
cd "$VENDOR"

DEEZER="https://raw.githubusercontent.com/deezertidal/shadowrocket-rules/HEAD/modules"
LAL="https://raw.githubusercontent.com/lalifeier/Shadowrocket/main/modules"
A2S="https://raw.githubusercontent.com/app2smile/rules/HEAD/module"
DD="https://raw.githubusercontent.com/ddgksf2013/Rewrite/master/AdBlock"

get() { # get <输出名> <url>
  printf '  %-34s' "$1"
  if curl -fsSL --retry 3 --connect-timeout 15 -m 60 -o "$1" "$2"; then
    printf 'ok  %s bytes\n' "$(wc -c < "$1" | tr -d ' ')"
  else
    printf 'FAIL  %s\n' "$2"
  fi
}

echo "== deezertidal/shadowrocket-rules"
get d_AdBlock.module        "$DEEZER/AdBlock.module"
get d_biliad.module         "$DEEZER/biliad.module"
get d_YouTubeAd.sgmodule    "$DEEZER/YouTubeAd.sgmodule"
get d_WeiboBlock.sgmodule   "$DEEZER/WeiboBlock.sgmodule"
get d_ZhihuBlock.sgmodule   "$DEEZER/ZhihuBlock.sgmodule"

echo "== lalifeier/Shadowrocket"
get lal_AdBlockLite.sgmodule "$LAL/AdBlockLite.sgmodule"
get lal_weibo.sgmodule       "$LAL/weibo.sgmodule"
get lal_zhihu.sgmodule       "$LAL/zhihu.sgmodule"
get lal_xiaohongshu.sgmodule "$LAL/xiaohongshu.sgmodule"
get lal_netease.sgmodule     "$LAL/netease.sgmodule"
get lal_douyin.sgmodule      "$LAL/douyin.sgmodule"
get lal_amap.sgmodule        "$LAL/amap.sgmodule"
get lal_bdmap.sgmodule       "$LAL/bdmap.sgmodule"
get lal_cainiao.sgmodule     "$LAL/cainiao.sgmodule"
get lal_smzdm.sgmodule       "$LAL/smzdm.sgmodule"
get lal_youtube.sgmodule     "$LAL/youtube.sgmodule"

echo "== app2smile/rules"
for m in adsense bilibili youtube zhihu qidian tieba qqnews baidumap vgtime; do
  get "a2s_$m.sgmodule" "$A2S/$m.sgmodule"
done
get a2s_spotify.module "$A2S/spotify.module"

echo "== ddgksf2013/Rewrite"
get dd_Ximalaya.conf       "$DD/Ximalaya.conf"
get dd_YoutubeAds.conf     "$DD/YoutubeAds.conf"

echo
echo "完成。接着运行： python3 tools/extract.py && python3 build.py"
