"""cmdparse 现状演示。

四段：空白分词把引号切散的现场、逐行统计、词频、NUL 字节的拒收报错。
末尾是新词法 tokenize / quote_word 的演示：词素坐标、报错定位、往返。
"""

from cmdparse import (
    CommandDocument,
    ParseError,
    quote_word,
    summarize,
    tokenize,
    word_frequency,
)

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

    print()
    print("=== 新词法：词素文本与原文区间 ===")
    lexer_source = "\n".join([
        'echo "a b"  \'c d\' e\\ f',
        'printf \'%s\\n\' "$GREETING" # 行内注释',
        'tar -czf out.tgz src/ \\',
        '    docs/',
    ])
    lexer_tokens = tokenize(lexer_source)
    for token in lexer_tokens:
        span = token.source_slice(lexer_source)
        print("  第 {} 行第 {} 列起: text={!r} 原文区间={!r}".format(
            token.start_line, token.start_column, token.text, span))

    print()
    print("=== 新词法：未闭合引号与悬空转义 ===")
    for broken, label in [
        ('echo "a b', "未闭合引号"),
        ("echo 'ab", "未闭合单引号"),
        ("echo a\\", "悬空转义"),
        ('echo "ab\\', "双引号里的悬空转义"),
    ]:
        try:
            tokenize(broken)
        except ParseError as error:
            print("  [{}] 输入 {!r}".format(label, broken))
            print("  " + error.format().replace("\n", "\n  "))

    print()
    print("=== 规范引用：quote_word 往返一致 ===")
    words = [token.text for token in lexer_tokens]
    rejoined = " ".join(quote_word(word) for word in words)
    reparsed = [token.text for token in tokenize(rejoined)]
    print("  词素:", words)
    print("  拼回:", rejoined)
    print("  往返一致:", reparsed == words)

    print()
    print("=== CommandDocument.tokens() 认续行，老 commands() 不碰 ===")
    document = CommandDocument(lexer_source)
    for number, line_tokens in document.tokens():
        print("  第 {} 行: {}".format(
            number, [token.text for token in line_tokens]))

    print()
    print("=== bytes 与乱码不崩 ===")
    print("  ", [token.text for token in tokenize(b'echo "a b" \xff\xfe done')])


if __name__ == "__main__":
    main()
