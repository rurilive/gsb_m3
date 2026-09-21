"""侧栏的统计报告：逐行词数、合计、词频。"""

from collections import Counter


def summarize(document):
    """逐行报词数，空行跳过，最后给合计。"""
    lines = ["第 {} 行: {} 个词".format(number, len(words))
             for number, words in document.commands()]
    lines.append("合计: {} 行, {} 个词".format(
        document.line_count(), document.word_count()))
    return "\n".join(lines)


def word_frequency(document, top=None):
    """全篇词频，按次数降序、同频按词升序；top 给前几名。"""
    if top is not None and top < 0:
        raise ValueError("top 不能是负数")
    counter = Counter()
    for _, words in document.commands():
        counter.update(words)
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if top is not None:
        ranked = ranked[:top]
    return ranked
