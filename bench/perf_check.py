"""词法性能验收：32 MB 命令流 60 秒内，放大 8 倍耗时不超 10 倍。

用法：python3 bench/perf_check.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cmdparse import tokenize

TEMPLATE = (
    "cd /srv/app && ./deploy.sh --env production \\\n"
    '  --targets "web-1 web-2" --message \'it is a message\'\n'
    "# 清理昨天的产物并重启服务\n"
    "export GREETING='hello world'\n"
    'printf \'%s\\n\' "$GREETING" # 打个招呼\n'
    'rm -rf build "old logs" && tar -czf out.tgz src/ \\\n'
    '    docs/ README.md && grep -n "a b" notes.txt\n'
)


def build(megabytes):
    """按整块模板重复，既不从词中间截断，大小也贴近目标。"""
    target = megabytes * 1024 * 1024
    block = TEMPLATE * 1000
    repeats = max(1, round(target / len(block.encode("utf-8"))))
    return block * repeats


def run(megabytes):
    data = build(megabytes)
    start = time.perf_counter()
    tokens = tokenize(data)
    elapsed = time.perf_counter() - start
    size_mb = len(data.encode("utf-8")) / 1024 / 1024
    return elapsed, size_mb, len(tokens)


def main():
    base_seconds, base_mb, base_tokens = run(32)
    big_seconds, big_mb, big_tokens = run(256)
    ratio = big_seconds / base_seconds
    size_ratio = big_mb / base_mb
    print("{:>6} MB: {:7.3f} s, {:>10,} tokens".format(
        int(base_mb), base_seconds, base_tokens))
    print("{:>6} MB: {:7.3f} s, {:>10,} tokens".format(
        int(big_mb), big_seconds, big_tokens))
    print("数据放大 {:.1f} 倍，耗时放大 {:.2f} 倍".format(size_ratio, ratio))

    ok = base_seconds < 60 and ratio < 10
    print("验收:", "通过" if ok else "不通过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
