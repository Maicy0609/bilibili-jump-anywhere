"""任意网址 → b23.tv 短链（仅标准库）。输入一个网址，回车出短链。

原理：/x/share/click 的 oid 必须是 *.bilibili.com 宿主，否则服务端静默返回
data.count=0 且无 content。但服务端只校验宿主，不校验查询串内容 —— 于是把
目标网址塞进 B 站自家页面 download_bcut 的 appScheme 里当载体：
    member.bilibili.com/.../download_bcut?appScheme=bilibili://smallapp/minigame/web/?mini_game_extra_web_url=<目标>
生成短链后，App 内点击 → 拉起 bilibili:// 小程序 webview → 读出
mini_game_extra_web_url → 落到目标站。

落地条件（不是 bug，是链路本身）：
  - 装了 B 站 App 的手机上点击才会真正跳转；
  - 浏览器直接打开只会停在 download_bcut 页面；
  - 微信内会被 weixinbridge 拦截。
"""

import json
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

API_URL = "https://api.biliapi.net/x/share/click"
CARRIER = "https://member.bilibili.com/studio/annyroal/download_bcut"
TIMEOUT = 10.0
RETRIES = 3

# b23.tv 短链提取；中文标点常紧跟其后，故只吃字母数字
_SHORT_RE = re.compile(r"https://b23\.tv/[A-Za-z0-9]+")
_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


def normalize_url(url: str) -> str:
    """补全 scheme，拒绝空串与非 http(s) 协议。"""
    url = url.strip()
    if not url:
        raise ValueError("空链接")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"不支持的协议：{parts.scheme}")
    if not parts.hostname:
        raise ValueError("无法解析出域名")
    return url


def wrap_target(target: str) -> str:
    """把任意目标网址包进 B 站自家页面，作为 oid 交出去。

    两层编码：目标先 quote 进 appScheme 的查询串，appScheme 再被 urlencode
    整体编码成 download_bcut 的参数。少一层就会在 & 处被服务端截断。
    """
    inner = "bilibili://smallapp/minigame/web/?mini_game_extra_web_url=" + quote(
        target, safe=""
    )
    return f"{CARRIER}?{urlencode({'appScheme': inner})}"


def shorten(url: str) -> str:
    """任意 URL → b23.tv 短链。url 已由 normalize_url 处理过。"""
    form = urlencode(
        {
            "platform": "android",
            "share_channel": "COPY",
            "share_id": "public.webview.0.0.pv",
            "share_mode": 3,
            "oid": wrap_target(url),
            "buvid": "qwq",
            "build": 6114514,
        }
    ).encode()

    headers = {
        "User-Agent": _USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.bilibili.com/",
    }

    body: dict[str, object] = {}
    for attempt in range(RETRIES):
        request = Request(API_URL, data=form, headers=headers)
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                raw: object = json.load(response)
                if not isinstance(raw, dict):
                    raise RuntimeError(f"接口返回非对象：{type(raw).__name__}")
                body = {str(k): v for k, v in raw.items()}
            break
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == RETRIES - 1:
                raise RuntimeError(f"请求接口失败：{exc}") from exc
            time.sleep(0.6 * (2**attempt))

    data = body.get("data")
    content = ""
    if isinstance(data, dict):
        value = data.get("content")
        if isinstance(value, str):
            content = value

    match = _SHORT_RE.search(content)
    if match is None:
        raise RuntimeError(
            f"接口未返回短链（oid 被拒）：code={body.get('code')!r} "
            f"message={body.get('message')!r} data={data!r}"
        )
    return match.group()


def main() -> int:
    url = input("请输入网址：\n> ").strip()
    try:
        print(f"\n短链接：{shorten(normalize_url(url))}")
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"\n转换失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
