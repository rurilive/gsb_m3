# vaultfile

内部对账报表的落盘加密库，纯标准库，无外部依赖（不装三方包，也不用任何
现成加密库；密钥流和认证标签由 hmac/hashlib 组合出来）。

## 用法

```python
from vaultfile import seal, unseal, seal_file, unseal_file

blob = seal(b"payload", b"0123456789abcdef")   # bytes 进 bytes 出
assert unseal(blob, b"0123456789abcdef") == b"payload"

seal_file("report.vlt", b"payload", b"0123456789abcdef")   # 直接落盘
assert unseal_file("report.vlt", b"0123456789abcdef") == b"payload"
```

密钥也可以传 `{版本: 密钥}` 的映射，加密时用 `key_version=` 指定写哪个
版本，解密时按容器头部记的版本自动挑密钥。密钥版本不在映射里抛
`UnknownKeyError`。

## 模块

- `vaultfile/keystream.py`：密钥派生、HMAC-SHA256 伪随机流、标签与恒时比较
- `vaultfile/format.py`：v1 容器结构，头部字段与尾部标签的拼装和校验
- `vaultfile/vault.py`：`seal`/`unseal` 与文件版 `seal_file`/`unseal_file`
- `vaultfile/chunked.py`：v2 分块容器，`seal_stream`/`unseal_stream`/`rotate_file`

容器布局：四字节 magic，一字节格式号，一字节密钥版本，16 字节盐，16 字节
nonce，八字节密文长度，密文，32 字节标签。标签盖住头部与全部密文，所以
先验标签再解密，标签不过一个明文字节都不往外吐。

v1 是整份数据一次读进内存的老格式，几百 MB 的报表会把内存打爆，新文件
一律走下面的流式入口；`unseal_stream` 同时认 v1，老文件不解密重存也能开。

## 流式分块（v2）

```python
from vaultfile import seal_stream, unseal_stream, rotate_file

# src/dst 可以是路径，也可以是二进制文件对象（BytesIO 等）
seal_stream("report.bin", "report.vlt2", key, chunk_size=1 << 20)
unseal_stream("report.vlt2", "report.out", {1: key})
```

按 `chunk_size`（默认 1 MiB，可传参）定长分块，逐块读、逐块加密写盘，
处理侧峰值内存只跟块大小走，不随文件大小涨。

v2 文件布局：

    magic(4)="VLT2" | fmt(1)=2 | salt(16) | chunk_size(4)
    然后每块：
    key_version(1) | flags(1) | index(8) | length(4)
    | ciphertext(length) | tag(32)

- 每块 nonce 由密钥、文件 salt 和块号派生
  （`derive(key, "nonce2", salt || index)`），同一密钥下跨文件（salt 每份
  文件随机）跨块（index 不同）都不重样。
- 每块的 tag 为 HMAC-SHA256，盖住文件头 + 块头 + 密文。文件被动过、块被
  调包或挪位、尾巴被截，解密都会在对应块抛 `AuthError`，消息里带块号；
  严格先验 tag 再解密，没认证的块一个明文字节都不落盘。
- 每块头部都记自己的密钥版本，解密按块取密钥。

## 密钥轮换

```python
rotate_file(
    "report.vlt2",
    new_key={1: old_key, 2: new_key},
    start=100, end=200,      # 半开区间 [100, 200)，end=None 转到文件尾
    new_key_version=2,
)
```

区间内的块先用旧密钥验签解密，再用新密钥重加密重打 tag；区间外的块连同
文件头原样字节搬运（不重新加密）。轮换后的文件新旧版本混排，
`unseal_stream` 按每块自己记的版本取密钥；密钥环里缺版本抛
`UnknownKeyError`。v1 老容器不支持原地轮换，先 `unseal` 再 `seal_stream`
转成 v2。dst 缺省时原地替换（同目录临时文件 + 原子 rename）。

## 运行

```bash
python3 demo.py                            # 加密、解回、改一个字节看报错
python3 -m unittest discover -s tests -v   # 行为基线测试
```
