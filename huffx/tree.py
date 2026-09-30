"""huffx 改造前基线：朴素哈夫曼编码。

这里只用最直白的做法完成哈夫曼编码：每合并一步就把仍然可用的全部节点
整表重扫一遍，线性挑出频次最小的两个。结果正确，但规模一大就慢，
堆与优先队列一个也没有。
"""


class HuffError(Exception):
    """huffx 所有自定义异常的基类。"""


class InvalidFrequencyError(HuffError):
    """符号频次不合法：负数、零、非整数或非数值。"""


class EmptySymbolError(HuffError):
    """符号集为空，无法构建编码。"""


class UnknownSymbolError(HuffError):
    """编码时遇到码表里没有的符号。"""


class InvalidBitstreamError(HuffError):
    """位流不合法：含非零一字符，或在符号中途提前结束。"""


def build_frequency(text):
    """统计文本里每个符号出现的次数，返回符号到次数的映射。"""
    counts = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return counts


class Node(object):
    """哈夫曼树节点：叶子带符号，内部节点符号为空。"""

    def __init__(self, symbol, weight, left=None, right=None):
        self.symbol = symbol
        self.weight = weight
        self.left = left
        self.right = right

    def is_leaf(self):
        return self.left is None and self.right is None


class HuffmanTree(object):
    """朴素哈夫曼编码器：每次线性重扫挑最小频次，逐字符构造位串。"""

    def __init__(self, frequencies):
        if not isinstance(frequencies, dict):
            raise InvalidFrequencyError("频次必须是符号到次数的映射")
        if not frequencies:
            raise EmptySymbolError("符号集不能为空")
        checked = {}
        for symbol, weight in frequencies.items():
            if isinstance(weight, bool) or not isinstance(weight, int):
                raise InvalidFrequencyError("频次必须是整数: %r" % (weight,))
            if weight <= 0:
                raise InvalidFrequencyError("频次必须为正: %r" % (weight,))
            checked[symbol] = weight
        self._frequencies = checked
        self._rescan_count = 0
        leaves = [Node(sym, checked[sym]) for sym in sorted(checked)]
        self._root = self._build(leaves)
        self._codes = {}
        self._assign(self._root, "")
        self._ordered = sorted(self._codes.items(), key=lambda kv: (len(kv[1]), kv[0]))

    def _index_of_min(self, pool):
        """朴素取最小：把整个可用节点表线性重扫一遍。"""
        self._rescan_count += 1
        best = 0
        for i in range(1, len(pool)):
            if pool[i].weight < pool[best].weight:
                best = i
        return best

    def _build(self, leaves):
        pool = list(leaves)
        while len(pool) > 1:
            first = pool.pop(self._index_of_min(pool))
            second = pool.pop(self._index_of_min(pool))
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
        """按码长升序、码长相同按符号序给出码表条目列表。"""
        return list(self._ordered)

    def symbols(self):
        """取回参与编码的符号，升序。"""
        return sorted(self._frequencies)

    def rescan_count(self):
        """线性重扫节点的次数，供与后续更省的做法对照。"""
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
        """加权路径长度，也就是全部符号频次乘各自码长之和。"""
        total = 0
        for symbol, weight in self._frequencies.items():
            total += weight * len(self._codes[symbol])
        return total

    def average_length(self):
        """平均码长，等于加权路径长度除以总频次。"""
        total = sum(self._frequencies.values())
        return self.weighted_path_length() / total

    def fixed_width(self):
        """朴素定长口径的位宽：仅由符号集大小决定，向上取整到整位。"""
        n = len(self._frequencies)
        if n <= 1:
            return 0
        width = 0
        while (1 << width) < n:
            width += 1
        return width

    def naive_average_length(self):
        """逐字符定长编码的平均码长，与哈夫曼路径对照。"""
        total = sum(self._frequencies.values())
        width = self.fixed_width()
        return sum(weight * width for weight in self._frequencies.values()) / total
