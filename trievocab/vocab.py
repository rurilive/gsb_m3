"""朴素字符串词表: 一切查询都退化成一个字符串列表上的线性扫描。

这是改造前的基线实现。内部只保存一份字符串列表, 插入是追加, 删除是按值
从头找位置再挪走, 存在性判定逐个字符串做整串逐字符相等比较, 前缀判定与
前缀计数都拿前缀对每个字符串从头逐字符比较, 按前缀取全部字符串与按前缀
取去重集合都靠扫全表后再排序, 最长公共前缀逐列比较全部字符串。词表一大,
每次查询都要把整份词表从头扫一遍, 代价随词表规模与串长同时膨胀, 没有任何
树形层级结构能把前缀的公共部分复用起来。
"""


class VocabError(Exception):
    """本包全部自定义错误的基类。"""


class EmptyError(VocabError):
    """空词表上执行了需要至少一个字符串的操作。"""


class NotFoundError(VocabError):
    """要删除的字符串不在词表里。"""


class FlatVocab:
    """用一个字符串列表保存元素, 每次查询都扫全表。

    - insert / remove: 把字符串追加进列表 / 从列表里按值移除一个。
    - contains: 逐个字符串做整串逐字符相等比较。
    - has_prefix / count_prefix: 逐个字符串用逐字符前缀比较判定与计数。
    - words_with_prefix / distinct_with_prefix: 扫全表挑出以该前缀开头的,
      去重的那条先去重再排序。
    - all_words: 返回排序后的全部字符串副本, 含重复。
    - longest_common_prefix: 空表抛 EmptyError, 否则逐列比较全部字符串。
    - compare_count: 自上次归零以来查询实际走过的字符比较步数。
    """

    def __init__(self):
        # 元素按插入顺序排列, 允许重复。
        self._items = []
        # 查询逐字符比较的累积步数, 用来量出线性扫描到底扫了多少。
        self._compare = 0

    # --- 写入 ---

    def insert(self, word):
        """加入字符串 word, 可重复加入同一串。"""
        if not isinstance(word, str):
            raise VocabError("word must be str")
        self._items.append(word)

    def remove(self, word):
        """删除一个值等于 word 的元素; 不存在时抛 NotFoundError。"""
        if not isinstance(word, str):
            raise VocabError("word must be str")
        for i, w in enumerate(self._items):
            if w == word:
                del self._items[i]
                return
        raise NotFoundError("word not present")

    def __len__(self):
        """返回元素个数, 含重复。"""
        return len(self._items)

    # --- 逐字符比较原语 (朴素且不做任何提前复用) ---

    def _is_prefix(self, word, prefix):
        """判断 word 是否以 prefix 开头, 逐位比较并累计步数。

        比较 min(两者长度) 个位置, 每个位置都走一遍并记账, 不提前退出。
        """
        n = len(word) if len(word) < len(prefix) else len(prefix)
        matched = True
        for i in range(n):
            self._compare += 1
            if word[i] != prefix[i]:
                matched = False
        return matched and len(word) >= len(prefix)

    def _equal(self, word, target):
        """判断 word 与 target 是否整串相等, 逐位比较并累计步数。"""
        n = len(word) if len(word) < len(target) else len(target)
        same = True
        for i in range(n):
            self._compare += 1
            if word[i] != target[i]:
                same = False
        return same and len(word) == len(target)

    # --- 基本属性 ---

    @property
    def compare_count(self):
        """自上次归零以来, 查询逐字符比较实际走过的步数。"""
        return self._compare

    def reset_compare_count(self):
        """把字符比较步数计数器归零。"""
        self._compare = 0

    # --- 查询 ---

    def contains(self, word):
        """判断 word 是否作为完整字符串在词表里。"""
        if not isinstance(word, str):
            raise VocabError("word must be str")
        for w in self._items:
            if self._equal(w, word):
                return True
        return False

    def has_prefix(self, prefix):
        """判断是否存在以 prefix 开头的字符串。"""
        if not isinstance(prefix, str):
            raise VocabError("prefix must be str")
        found = False
        for w in self._items:
            if self._is_prefix(w, prefix):
                found = True
        return found

    def count_prefix(self, prefix):
        """统计以 prefix 开头的字符串个数, 含重复。"""
        if not isinstance(prefix, str):
            raise VocabError("prefix must be str")
        n = 0
        for w in self._items:
            if self._is_prefix(w, prefix):
                n += 1
        return n

    def words_with_prefix(self, prefix):
        """返回以 prefix 开头的全部字符串, 按字典序升序, 含重复。"""
        if not isinstance(prefix, str):
            raise VocabError("prefix must be str")
        out = [w for w in self._items if self._is_prefix(w, prefix)]
        out.sort()
        return out

    def distinct_with_prefix(self, prefix):
        """返回以 prefix 开头的不同字符串, 按字典序升序, 去重后各留一个。"""
        if not isinstance(prefix, str):
            raise VocabError("prefix must be str")
        seen = set()
        for w in self._items:
            if self._is_prefix(w, prefix):
                seen.add(w)
        return sorted(seen)

    def all_words(self):
        """返回全部字符串, 按字典序升序, 含重复。"""
        return sorted(self._items)

    def longest_common_prefix(self):
        """返回全部字符串的最长公共前缀; 空表时抛 EmptyError。"""
        if not self._items:
            raise EmptyError("empty vocab")
        first = self._items[0]
        limit = len(first)
        for w in self._items[1:]:
            if len(w) < limit:
                limit = len(w)
        i = 0
        while i < limit:
            ch = first[i]
            for w in self._items[1:]:
                if w[i] != ch:
                    return first[:i]
            i += 1
        return first[:i]
