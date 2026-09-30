"""graycode 的位序列工具（改造前的现状）。

现在只有一条路：生成位数的格雷码序列靠对所有二进制串反复试凑，从全零串
出发，每一步试着翻转一个位，挑一个还没用过又恰好只差一位的串记下去，走不
通就回退重挑；判断一条序列是不是合法格雷码、求某个串在序列里的位置，都靠
把整条序列造出来再逐个比对。结果都对，但每一步都要把候选串挨个试一遍，规
模一大试凑次数就疯涨。线性做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class GrayError(Erro):
    """位序列或位数的非法输入。"""


def _check_width(width):
    """位数必须是大于等于零的整数。"""
    if isinstance(width, bool) or not isinstance(width, int):
        raise GrayError("width must be an int")
    if width < 0:
        raise GrayError("width must not be negative")
    return width


def _check_bits(bits):
    """位串必须是仅由零与一组成的字符串，允许空串（零位）。"""
    if not isinstance(bits, str):
        raise GrayError("bits must be a str")
    for ch in bits:
        if ch not in ("0", "1"):
            raise GrayError("bits must contain only 0 and 1")
    return bits


def _check_sequence(seq):
    """序列必须是由等长位串组成的非空列表或元组。"""
    if not isinstance(seq, (list, tuple)):
        raise GrayError("sequence must be a list or tuple")
    if len(seq) == 0:
        raise GrayError("sequence must not be empty")
    width = None
    for item in seq:
        _check_bits(item)
        if width is None:
            width = len(item)
        elif len(item) != width:
            raise GrayError("all codes must share one width")
    return list(seq)


def _bits(value, width):
    """把整数写成定宽位串，最高位在左。"""
    if width == 0:
        return ""
    return format(value, "0%db" % width)


def _flip(code, pos):
    """翻转从左数第 pos 位（零起），返回新位串。"""
    chars = list(code)
    chars[pos] = "1" if chars[pos] == "0" else "0"
    return "".join(chars)


def diff_count(a, b):
    """两个等长位串之间取值不同的位数。"""
    _check_bits(a)
    _check_bits(b)
    if len(a) != len(b):
        raise GrayError("codes must share one width")
    count = 0
    for x, y in zip(a, b):
        if x != y:
            count += 1
    return count


def is_gray_sequence(seq, wrap=True):
    """判断一条位串序列是不是合法格雷码。

    相邻两项必须恰好相差一位；wrap 为真时首尾之间也要相差一位（回环）。
    形状合法但相邻差多于一位、或出现重复串，都判为假。
    """
    codes = _check_sequence(seq)
    if len(codes) == 1:
        return True
    for i in range(len(codes) - 1):
        if diff_count(codes[i], codes[i + 1]) != 1:
            return False
    if wrap and diff_count(codes[-1], codes[0]) != 1:
        return False
    return True


def gray_sequence(width):
    """朴素生成位数的格雷码序列，靠最低位优先的试凑加深搜回退。

    从全零串起步，每一步对每一位依次试着翻转，挑一个还没用过又只差一位的
    串往下走；走到死路就回退换一个候选，直到把全部二进制串排成一圈。结果
    与标准反射码一致，但反复试凑，位数一大就很慢。
    """
    _check_width(width)
    if width == 0:
        return [""]
    total = 1 << width
    codes = [_bits(i, width) for i in range(total)]
    position = dict((code, i) for i, code in enumerate(codes))
    used = [False] * total
    used[0] = True
    seq = [codes[0]]

    def walk(current):
        if len(seq) == total:
            return diff_count(seq[-1], seq[0]) == 1
        for pos in range(width - 1, -1, -1):
            nxt = _flip(current, pos)
            j = position[nxt]
            if used[j]:
                continue
            if diff_count(current, nxt) != 1:
                continue
            used[j] = True
            seq.append(nxt)
            if walk(nxt):
                return True
            seq.pop()
            used[j] = False
        return False

    if not walk(codes[0]):
        raise GrayError("no gray sequence found for width %d" % width)
    return list(seq)


def gray_index(bits):
    """某个位串在格雷码序列里的位置（零起），靠造出整条序列再逐个比对。"""
    _check_bits(bits)
    width = len(bits)
    for i, code in enumerate(gray_sequence(width)):
        if code == bits:
            return i
    raise GrayError("code not found")


def subsets_in_bit_order(elements):
    """按二进制计数顺序枚举集合的全部子集。

    第 i 个子集取 i 的定宽二进制里为一的那些位对应的元素，零起，低位在右。
    """
    items = list(elements)
    n = len(items)
    result = []
    for mask in range(1 << n):
        result.append([items[i] for i in range(n) if (mask >> (n - 1 - i)) & 1])
    return result


def subsets_in_gray_order(elements):
    """按格雷码顺序枚举集合的全部子集，并给出每步增删的元素下标。

    返回二元组：子集列表，以及相邻两步之间的操作序列；每个操作是（元素下标，
    添加或删除），相邻子集恰好只差这一个元素，首尾回环也恰好只差一个。元素
    下标零起。
    """
    items = list(elements)
    n = len(items)
    codes = gray_sequence(n)
    subsets = []
    steps = []
    previous = None
    for code in codes:
        subsets.append([items[i] for i in range(n) if code[i] == "1"])
        if previous is not None:
            changed = [i for i in range(n) if code[i] != previous[i]]
            k = changed[0]
            op = "add" if code[k] == "1" else "remove"
            steps.append((k, op))
        previous = code
    return subsets, steps


class GrayTools:
    """绑定一个位数的位序列工具，只有反复试凑这一条路。

    生成序列时把每次试探一个候选串都记进计数器，供与线性做法对照规模。
    位数在构造时校验并固定。
    """

    def __init__(self, width):
        self._width = _check_width(width)
        self._trial_count = 0

    def width(self):
        """返回绑定的位数。"""
        return self._width

    def reset_trial_count(self):
        """把试凑计数清零。"""
        self._trial_count = 0

    def trial_count(self):
        """自上次清零以来累计试探了多少个候选位串。"""
        return self._trial_count

    def gray_sequence(self):
        """朴素生成序列，每试一个候选串就累计一次试凑计数。"""
        width = self._width
        if width == 0:
            return [""]
        total = 1 << width
        codes = [_bits(i, width) for i in range(total)]
        position = dict((code, i) for i, code in enumerate(codes))
        used = [False] * total
        used[0] = True
        seq = [codes[0]]

        def walk(current):
            if len(seq) == total:
                return diff_count(seq[-1], seq[0]) == 1
            for pos in range(width - 1, -1, -1):
                nxt = _flip(current, pos)
                j = position[nxt]
                if used[j]:
                    continue
                self._trial_count += 1
                if diff_count(current, nxt) != 1:
                    continue
                used[j] = True
                seq.append(nxt)
                if walk(nxt):
                    return True
                seq.pop()
                used[j] = False
            return False

        if not walk(codes[0]):
            raise GrayError("no gray sequence found for width %d" % width)
        return list(seq)

    def gray_index(self, bits):
        """朴素定位：造出整条序列再逐个比对。"""
        _check_bits(bits)
        for i, code in enumerate(self.gray_sequence()):
            if code == bits:
                return i
        raise GrayError("code not found")

    def is_gray_sequence(self, seq, wrap=True):
        """判断序列是否合法格雷码，逻辑同模块级函数。"""
        return is_gray_sequence(seq, wrap=wrap)

    def subsets_in_gray_order(self, elements):
        """按绑定位数下的格雷码顺序枚举子集，逻辑同模块级函数。"""
        items = list(elements)
        if len(items) != self._width:
            raise GrayError("element count must match width")
        codes = self.gray_sequence()
        subsets = []
        steps = []
        previous = None
        for code in codes:
            subsets.append([items[i] for i in range(self._width) if code[i] == "1"])
            if previous is not None:
                changed = [i for i in range(self._width) if code[i] != previous[i]]
                k = changed[0]
                op = "add" if code[k] == "1" else "remove"
                steps.append((k, op))
            previous = code
        return subsets, steps
