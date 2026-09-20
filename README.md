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

容器布局：四字节 magic，一字节格式号，一字节密钥版本，16 字节盐，16 字节
nonce，八字节密文长度，密文，32 字节标签。标签盖住头部与全部密文，所以
先验标签再解密，标签不过一个明文字节都不往外吐。

当前实现把整份数据一次读进内存：内存占用跟数据大小同步涨。

## 运行

```bash
python3 demo.py                            # 加密、解回、改一个字节看报错
python3 -m unittest discover -s tests -v   # 行为基线测试
```
