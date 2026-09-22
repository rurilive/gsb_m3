"""跑一遍 mailnorm 现有的能力：拆头部、取正文、拆 Content-Type、切地址。

python3 demo.py
"""

from mailnorm import MailParseError, Message, parse_content_type, split_addresses

SAMPLE = """\
From: postmaster@example.com
To: ops@example.com, dev@example.com
Subject: nightly report
Content-Type: text/plain; charset=us-ascii

all jobs finished
"""

ADDRESS_LINE = "ops@example.com, dev@example.com, qa@example.com"

FOLDED = """\
Subject: this line continues
    on an indented line
Content-Type: text/plain

body
"""


def main():
    msg = Message.parse(SAMPLE)
    print("== 头部字段 ==")
    for name in msg.headers.names():
        print("  %s: %s" % (name, msg.get(name)))
    print("  正文: %r" % msg.text())
    print("  主类型: %s，参数: %s，起始偏移: %d"
          % (msg.content_type, msg.params, msg.body_offset))

    print("== Content-Type 拆解 ==")
    media, params = parse_content_type('text/html; charset="utf-8"; format=flowed')
    print("  %s %s" % (media, params))
    media, params = parse_content_type("")
    print("  空值兜底: %s %s" % (media, params))

    print("== 地址列表 ==")
    for addr in split_addresses(ADDRESS_LINE):
        print("  %s" % addr)

    print("== 折叠头部（现状）==")
    try:
        Message.parse(FOLDED)
    except MailParseError as exc:
        print("  报错: %s，行号 %s" % (exc.reason, exc.line))


if __name__ == "__main__":
    main()
