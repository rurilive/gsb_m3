# cookiest

网关进程内共享的 Cookie 罐：上游 Set-Cookie 解析、按请求匹配、重启恢复。多线程共用一个实例，纯标准库，无外部依赖。

## 模块

- `cookiest/cookie.py`：`Cookie` 值对象、`parse_set_cookie` / `parse_expires`
- `cookiest/jar.py`：`CookieJar`——add / set_cookie / match_for(url) / remove / snapshot，clock 可注入
- `cookiest/serial.py`：dump / load（JSON）

## 运行

```bash
python3 demo.py
```

## Known Issues

以下问题已修复（防回归测试见 `tests/`，`python3 -m unittest discover -s tests`）：

- **跨域串 cookie（evil-example.com 拿到 example.com 的会话）**
  根因：`jar.py` 的 `_domain_match` 用 `host.endswith(domain)` 做后缀匹配，
  `evil-example.com` 以 `example.com` 结尾即误判通过。修复：改为精确相等或
  以 `"." + domain` 结尾（点边界），并兼容前导点的 Domain 写法。
- **/pay 的 cookie 发给 /paypal（接口串号）**
  根因：`_path_match` 用裸 `startswith`，`/paypal` 以 `/pay` 开头即误配。
  修复：按 RFC 6265 path-match——完全相同，或前缀命中且 cookie path 以 `/`
  结尾 / 下一字符为 `/`。
- **每天凌晨固定时段集中掉登录**
  根因：`parse_expires` 把 GMT 的 Expires 解析成 naive datetime，
  `is_expired` 取 `timestamp()` 时按本地时区（UTC+8）折算，过期时刻整体
  提前 8 小时，正好落在凌晨。修复：解析时显式带上 `tzinfo=timezone.utc`。
- **重启后 secure / http_only 标记丢失**
  根因：`serial.py` 的 `_to_dict` / `_from_dict` 只导出了 name/value/
  domain/path/expires，两个安全标记未入 JSON，恢复后默认 False，权限变宽。
  修复：导出并恢复 `secure`、`http_only`，同时兼容无这两个字段的旧存档。
