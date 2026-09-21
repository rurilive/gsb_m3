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

大报表走流式分块（v2 容器），按固定块大小逐块读写，峰值内存只跟块大小
走，不随文件总长涨：

```python
from vaultfile import seal_stream, unseal_stream, rotate_file

with open("report.vlt", "wb") as dest, open("report.csv", "rb") as src:
    seal_stream(dest, src, keyring, key_version=1, chunk_size=4 * 1024 * 1024)

with open("report.vlt", "rb") as src:
    for plain_chunk in unseal_stream(src, keyring):   # 生成器，逐块吐明文
        ...

rotate_file("report.vlt", 2, keyring, start=10, end=20)  # 只轮换第 [10,20) 块
```

`unseal_stream` 是生成器：标签不过的块一个明文字节都不吐；任何块被改动、
调包、挪位或尾巴被截，迭代时抛 `AuthError`，异常的 `chunk_index` 记着出
问题的块号（错误消息里也带）。老的 v1 单块容器同样能从 `unseal_stream`
解开。轮换后一个文件里新旧密钥版本混排，解密时按每块头里记的版本各自取
密钥。

## 模块

- `vaultfile/keystream.py`：密钥派生、HMAC-SHA256 伪随机流、标签与恒时比较
- `vaultfile/format.py`：v1 容器结构，头部字段与尾部标签的拼装和校验
- `vaultfile/vault.py`：`seal`/`unseal` 与文件版 `seal_file`/`unseal_file`

v1 容器布局（`seal`/`unseal`，单块）：四字节 magic，一字节格式号，一字节
密钥版本，16 字节盐，16 字节 nonce，八字节密文长度，密文，32 字节标签。
标签盖住头部与全部密文，先验标签再解密。

v2 容器布局（`seal_stream`/`unseal_stream`，分块流式）：

```
文件头: magic(4) | fmt(1) | key_version(1) | salt(16) | chunk_size(4)
每块:   index(4) | flags(1) | length(4) | key_version(1)
        | ciphertext(length) | tag(32)
```

每块标签盖住 文件头 + 块头 + 本块密文：块号、长度、密钥版本都在认证范围
内，块被调包或挪位、跨文件拼块都过不了。非末块密文长度固定为
chunk_size，末块 <= chunk_size；空文件也有一帧零长末块，整帧被截一样
查得出来。每块 nonce = HMAC 派生(密钥, salt, 块号)：salt 是每份文件现取
的 16 字节随机量，所以同一密钥下跨文件、跨块 nonce 都不重样；轮换密钥后
由新密钥重新派生。

## 运行

```bash
python3 demo.py                            # 加密、解回、改一个字节看报错
python3 -m unittest discover -s tests -v   # 行为基线测试
```
