"""cmdparse 现状演示。

四段：空白分词把引号切散的现场、逐行统计、词频、NUL 字节的拒收报错。
末尾留了新词法落地后的演示位子。
"""

from cmdparse import CommandDocument, ParseError, summarize, word_frequency

PASTE = "\n".join([
    "cd /srv/app && ls -l",
    "# 清理昨天的产物",
    "rm -rf build \"old logs\"",
    "git commit -m 'fix parser' -m \"see ticket 42\"",
    "export GREETING='hello world'",
    "printf '%s\\n' \"$GREETING\"",
    "tar -czf out.tgz src/ \\",
    "    docs/ README.md",
    "grep -n \"a b\" notes.txt",
])


def main():
    document = CommandDocument(PASTE)

    print("=== 空白分词现状（引号被切散）===")
    for number, words in document.commands():
        print("  第 {} 行: {}".format(number, words))

    print()
    print("=== 逐行统计 ===")
    print("  " + summarize(document).replace("\n", "\n  "))

    print()
    print("=== 词频前五 ===")
    for word, count in word_frequency(document, top=5):
        print("  {!r}: {}".format(word, count))

    print()
    print("=== NUL 字节被拒收 ===")
    try:
        CommandDocument("ls\nrm \x00rf /tmp")
    except ParseError as error:
        print("  " + error.format().replace("\n", "\n  "))

    # TODO(词法改造): tokenize 与 quote_word 落地后在这里补演示：
    # 1) 引号里的空格、引号内外的转义、行内注释、行尾续行各来一行，
    #    打每个词素的原文区间，核对区间切出来的字符对不对
    # 2) 未闭合引号、悬空转义各抓一次 ParseError，把行列与脱字符打出来
    # 3) 词素用 quote_word 拼回命令行再 tokenize，核对往返一致


if __name__ == "__main__":
    main()
