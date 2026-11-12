# jump.py

任意网址 → `b23.tv` 短链。输入一个网址，回车出结果。仅标准库，无第三方依赖。

```
$ python jump.py
请输入网址：
> https://ipinfo.io/json

短链接：https://b23.tv/g0k4hUq
```

## 一、B 站原本的短链接口

`/x/share/click` 是 App 端「复制链接」背后的接口：

```http
POST https://api.biliapi.net/x/share/click
Content-Type: application/x-www-form-urlencoded

platform=android&share_channel=COPY&share_id=public.webview.0.0.pv
&share_mode=3&oid=<对象>&buvid=qwq&build=6114514
```

`share_id=public.webview.0.0.pv` 表示「分享一个 webview 跳转」，此时 `oid` 应当是一个完整链接。接口把 `oid` 内联进一条 `bilibili://` 深链，再包成 `member.bilibili.com/.../download_bcut?appScheme=<深链>` 的形式，最后为该长链生成 `b23.tv` 短码。

返回值形如：

```json
{"code": 0, "message": "OK", "ttl": 1,
 "data": {"content": "https://b23.tv/U2WNU6x", "count": 0, "card_type": 0}}
```

短链在 `data.content` 里。注意 `code` 永远是 0、`message` 永远是 OK，失败时也不改。判断成功只能看 `data.content` 在不在。

## 二、被挡住的是什么

`oid` 的宿主必须在 `*.bilibili.com` 之下。给出站外域名时，服务端不报错，直接**静默降级**：

```json
{"code": 0, "message": "OK", "ttl": 1,
 "data": {"count": 0, "card_type": 0}}
```

没有 `content`，没有错误码，`code` 仍为 0。最初那版脚本报「`code=0 message='OK'` 却说接口未返回短链」，就是撞在这里：请求被拒了，但拒绝没有任何提示。

这一层校验是 2021 年前后补上的。更早的做法是直接把任意 URL 塞进 `oid`，接口照单全收。

绕过它的尝试也不是没有：`https://www.bilibili.com/?@bing.com`、`https://www.bilibili.com\@bing.com` 这类「URL 解析歧义」写法。实测前者能出短链，但解 302 看到落点是 `www.bilibili.com/?%40bing.com=`，仍然停在 B 站自己的页面。歧义骗过了校验器，没骗过跳转逻辑。

## 三、真实可用的路径：借一个合法载体

校验的对象只有**宿主**，查询串内容不管。于是换个思路：选一个真实存在的 B 站页面，把目标网址塞进它的查询参数里，宿主不去伪造。

`member.bilibili.com/studio/annyroal/download_bcut` 符合这两点。它接受 `appScheme` 参数，App 内会把它当深链拉起：

```
https://member.bilibili.com/studio/annyroal/download_bcut
  ?appScheme=bilibili://smallapp/minigame/web/?mini_game_extra_web_url=https://ipinfo.io/json
```

宿主是 `member.bilibili.com`，校验通过；而 `appScheme` 里的 `mini_game_extra_web_url` 携带的却是任意目标网址。整条作为 `oid` 交出去，短链正常生成。

解 302 验证（`b23.tv/g0k4hUq`）：

```
Location: https://member.bilibili.com/studio/annyroal/download_bcut
          ?appScheme=bilibili%3A%2F%2Fsmallapp%2Fminigame%2Fweb%2F
            %3Fmini_game_extra_web_url%3Dhttps%253A%252F%252Fipinfo.io%252Fjson
          &plat_id=124&share_from=h5&share_plat=android&share_source=COPY
          &share_tag=s_i&timestamp=...&unique_k=g0k4hUq
```

剥一层 URL 解码得到 `appScheme`：

```
bilibili://smallapp/minigame/web/?mini_game_extra_web_url=https%3A%2F%2Fipinfo.io%2Fjson
```

再剥一层得到目标：

```
https://ipinfo.io/json
```

链条完整。App 内点开短链 → 打开 `download_bcut` 页 → 按 `appScheme` 拉起 `bilibili://smallapp/minigame/web/` → 小程序 webview 读取 `mini_game_extra_web_url` → 落到目标站。

## 四、为什么是双层编码

`wrap_target()` 做了两次编码，少一次就断：

```python
inner = "bilibili://smallapp/minigame/web/?mini_game_extra_web_url=" + quote(target, safe="")
return f"{CARRIER}?{urlencode({'appScheme': inner})}"
```

1. 目标先 `quote(safe="")` 进 `mini_game_extra_web_url`，否则目标自带的 `&`、`?`、`#` 会在小程序解析时被当成参数分隔符，链接被截断。
2. `inner` 再被 `urlencode` 整体编码成 `download_bcut` 的 `appScheme`，否则 `inner` 里的 `&`（小程序那个）会被当成 `download_bcut` 的参数分隔符。

实测 `https://example.com/path?a=1&b=2` 经两层还原后一字不差：`https://example.com/path?a=1&b=2`。单层编码的版本在这条上会断成 `https://example.com/path?a=1`。

## 五、落地条件

短链本身的生成是全平台成功的，但**跳转只在一个场景成立**：

| 场景 | 结果 |
| --- | --- |
| 装了 B 站 App 的手机点击 | 拉起小程序，跳到目标站 |
| 手机浏览器直接打开 | 停在 `download_bcut` 页面，可能提示下载 App |
| 桌面浏览器打开 | 同上 |
| 微信内打开 | `weixinbridge` 拦截，多半被掐 |

所以这条短链只对装了 B 站 App 的人有效，发给别人之前先确认对方装没装。

## 六、程序结构

```
normalize_url(url)      补 scheme、拒空串、拒非 http(s)
wrap_target(target)     目标 → download_bcut 载体 URL（双层编码）
shorten(url)            POST /x/share/click，正则取 data.content 里的短链
main()                  单行输入 → 输出短链，失败走 stderr 与退出码 1
```

实现上的几个取舍：

失败判定只看 `data.content`。`code` 和 `message` 恒为 0/OK，不能当成功判据用。取不到短链时，报错里会带完整 `data`，方便判断是哪种拒绝。

请求带三次指数退避重试（0.6s / 1.2s / 2.4s）。接口无鉴权但按 IP 限流，单次脚本通常打不出限流，重试只是兜网络抖动。

短链正则写的是 `https://b23\.tv/[A-Za-z0-9]+`，不吞空白和中文标点。`content` 里短链后面可能紧跟标点，贪婪匹配会把标点一起吃进去。

`share_mode=3` 是走 webview 分支的开关。改成 1 或 4，`share_id` 对不上，拿不到 `content`，实测都返回 `count:0, card_type:0`。

`buvid` 和 `build` 填任意非空值即可，`build` 要大于 `5520400`。这里固定用 `qwq` / `6114514`，社区里流传的可用组合。

## 七、已知边界

接口无鉴权，也没有限速文档。高频调用会被按 IP 拒绝，返回的仍是 `code=0` 的空 `data`，程序这时会报「oid 被拒」，具有误导性。批量跑自己控间隔，别当公网服务用。

载体页面可能会失效。`download_bcut` 是现成的 Studio 页面，B 站改版或下线它，链条就断。换一个接受 `appScheme` 的 `*.bilibili.com` 页面同样可行，只需要改 `CARRIER` 常量。

短链可能被回收。`b23.tv` 有过清理非官方分享短链的先例，生成成功不等于长期有效。

微信生态里用不了。这条链路的终点是小程序 webview，微信侧有独立拦截策略，改程序绕不过去。

## 八、使用

```bash
python jump.py
```

单行输入，单行输出。没有参数，没有批量模式，也没有配置文件。

mypy 校验：

```bash
python -m mypy --strict jump.py
# Success: no issues found in 1 source file
```
