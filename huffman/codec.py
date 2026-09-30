"""huffman 改造前基线：朴素哈夫曼编码。

这里只用最直白的做法完成哈夫曼编码：每合并一步就把仍然可用的全部节点
整表重扫一遍，线性挑出权重最小的两个再合并。结果正确，但规模一大就慢，
优先队列与堆结构一个也没有。
"""

import heapq


class Erro(Exception):
    """huffman 所有自定义异常的公共基类。"""


class InvalidWeightError(Erro):
    """权重不合法：负数、非整数或非数值。"""


class EmptySymbolError(Erro):
    """符号表为空，无法构建编码。"""


class UnknownSymbolError(Erro):
    """编码时遇到码表里没有的符号。"""


class InvalidBitstreamError(Erro):
    """位流不合法：含非零一字符，或在符号中途提前结束。"""


class Node(object):
    """哈夫曼树节点，朴素可变结构：叶子带符号，内部节点符号为空。"""

    def __init__(self, symbol, weight, left=None, right=None):
        self.symbol = symbol
        self.weight = weight
        self.left = left
        self.right = right

    def is_leaf(self):
        return self.left is None and self.right is None


def build_frequency(text):
    """统计文本里每个符号出现的次数，返回符号到次数的映射。"""
    counts = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return counts


def _checked_weights(weights):
    """校验权重表：只接受非负整数，布尔值不算整数。"""
    if not isinstance(weights, dict):
        raise InvalidWeightError("权重必须是符号到整数的映射")
    checked = {}
    for symbol, weight in weights.items():
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise InvalidWeightError("权重必须是整数: %r" % (weight,))
        if weight < 0:
            raise InvalidWeightError("权重不能为负: %r" % (weight,))
        checked[symbol] = weight
    return checked


class HuffmanCodec(object):
    """朴素哈夫曼编码器：每次线性重扫挑最小权重，逐字符拼位串。"""

    def __init__(self, weights):
        checked = _checked_weights(weights)
        if not checked:
            raise EmptySymbolError("符号表不能为空")
        self._weights = checked
        self._rescan_count = 0
        if len(checked) == 1:
            # 单符号退化：叶子直接当根，按约定记零码。
            symbol = sorted(checked)[0]
            self._root = Node(symbol, checked[symbol])
        else:
            leaves = [Node(sym, checked[sym]) for sym in sorted(checked)]
            self._root = self._build(leaves)
        self._codes = {}
        self._assign(self._root, "")
        self._ordered = sorted(self._codes.items(), key=lambda kv: (len(kv[1]), kv[0]))

    def _pop_min(self, pool):
        """朴素取最小：把整个可用节点表线性重扫一遍。"""
        self._rescan_count += 1
        best = 0
        for i in range(1, len(pool)):
            if pool[i].weight < pool[best].weight:
                best = i
        return pool.pop(best)

    def _build(self, leaves):
        pool = list(leaves)
        while len(pool) > 1:
            first = self._pop_min(pool)
            second = self._pop_min(pool)
            pool.append(Node(None, first.weight + second.weight, first, second))
        return pool[0]

    def _assign(self, node, prefix):
        if node.is_leaf():
            self._codes[node.symbol] = prefix or "0"
            return
        self._assign(node.left, prefix + "0")
        self._assign(node.right, prefix + "1")

    def codes(self):
        """取回符号到码字的映射，对外只读。"""
        return dict(self._codes)

    def code_table(self):
        """按码长升序、码长相同按符号序给出码表条目。"""
        return list(self._ordered)

    def symbols(self):
        """取回参与编码的符号，升序。"""
        return sorted(self._weights)

    def rescan_count(self):
        """线性重扫挑选最小的次数，供与更省的做法对照。"""
        return self._rescan_count

    def encode(self, text):
        """把文本逐字符编成零一串。"""
        bits = []
        for ch in text:
            code = self._codes.get(ch)
            if code is None:
                raise UnknownSymbolError("码表里没有符号: %r" % (ch,))
            bits.append(code)
        return "".join(bits)

    def decode(self, bits):
        """把零一串按树还原成文本。"""
        if self._root.is_leaf():
            symbol = self._root.symbol
            for bit in bits:
                if bit != "0":
                    raise InvalidBitstreamError("单符号码表只接受零位")
            return symbol * len(bits)
        out = []
        node = self._root
        for bit in bits:
            if bit == "0":
                node = node.left
            elif bit == "1":
                node = node.right
            else:
                raise InvalidBitstreamError("位流含非零一字符: %r" % (bit,))
            if node.is_leaf():
                out.append(node.symbol)
                node = self._root
        if node is not self._root:
            raise InvalidBitstreamError("位流在符号中途提前结束")
        return "".join(out)

    def weighted_path_length(self):
        """加权路径长度，也就是全部符号权重乘各自码长之和。"""
        total = 0
        for symbol, weight in self._weights.items():
            total += weight * len(self._codes[symbol])
        return total

    def average_length(self):
        """平均码长，等于加权路径长度除以总权重。"""
        total = sum(self._weights.values())
        return self.weighted_path_length() / total


def encode(text):
    """便捷入口：按文本统计频次建树并编码，返回位串。"""
    return HuffmanCodec(build_frequency(text)).encode(text)


def decode(bits, weights):
    """便捷入口：按给定权重表建树并解码位串。"""
    return HuffmanCodec(weights).decode(bits)


def build_codes(weights):
    """便捷入口：按给定权重表建树并取回符号到码字的映射。"""
    return HuffmanCodec(weights).codes()


def weighted_path_length(weights):
    """便捷入口：按给定权重表求加权路径长度。"""
    return HuffmanCodec(weights).weighted_path_length()


class NaiveIndexHeap(object):
    """以朴素线性重扫为底的索引堆，纯标准库自实现，接口与二叉堆一致。

    元素以 (键, 编号) 表示：键是整数向量，按字典序排序；编号是稳定唯一序，
    用来打破并列，保证进出堆的顺序确定。堆底用一次线性重扫找出最小元素，
    规模一大就是平方级；但它与二叉堆对外接口完全相同，可互为对照。
    所有比较都走元素自带的顺序，自研堆与标准库堆在同一批数据上给出同一序列。
    """

    def __init__(self):
        self._items = []

    def __len__(self):
        return len(self._items)

    def push(self, item):
        """把元素加入堆。"""
        self._items.append(item)

    def pop(self):
        """取出并返回最小元素。"""
        if not self._items:
            raise IndexError("堆为空")
        best = 0
        for i in range(1, len(self._items)):
            if self._items[i] < self._items[best]:
                best = i
        return self._items.pop(best)

    def peek(self):
        """查看最小元素但不取出。"""
        if not self._items:
            raise IndexError("堆为空")
        best = 0
        for i in range(1, len(self._items)):
            if self._items[i] < self._items[best]:
                best = i
        return self._items[best]
