"""cmdparse 演示。

前四段是老空白分词的现场：引号切散、逐行统计、词频、NUL 拒收。
后三段是新词法：带坐标词素与高亮区间、错误定位、quote_word 往返。
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
    print("=== 新词法：词素、坐标与高亮区间 ===")
    lexer_source = PASTE
    for token in document.tokens():
        start, end = token.start, token.end
        raw = lexer_source[start.offset:end.offset]
        kinds = ",".join(segment.kind for segment in token.segments)
        print("  {:<18} 第{}行{}列-第{}行{}列 原文={!r} 段=[{}]".format(
            repr(token.text), start.line, start.column,
            end.line, end.column, raw, kinds))

    print()
    print("=== 新词法：未闭合引号与悬空转义 ===")
    for broken in ("cd 'unclosed dir", 'echo "a\\', "line2\n  rm 'x"):
        try:
            tokenize(broken)
        except ParseError as error:
            print("  输入 {!r}:".format(broken))
            print("  " + error.format().replace("\n", "\n  "))
            print()

    print("=== quote_word 往返：拼回去再解析，逐词一致 ===")
    new_tokens = document.tokens()
    rebuilt = " ".join(quote_word(token.text) for token in new_tokens)
    reparsed = tokenize(rebuilt)
    before = [token.text for token in new_tokens]
    after = [token.text for token in reparsed]
    print("  拼回: {}".format(rebuilt))
    print("  往返一致: {}".format(before == after))
    print("  空串也活: {} -> {} -> {}".format(
        repr(""), quote_word(""),
        [token.text for token in tokenize(quote_word(""))]))


if __name__ == "__main__":
    main()
