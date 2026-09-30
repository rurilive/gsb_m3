"""稳定婚姻的现有实现。

两拨人，一拨称男方一拨称女方，男方只对女方有偏好、女方只对男方有偏好。
当前只有一条朴素路径：穷举男女之间的全部配对方案，逐个方案检查里面还有
没有彼此更中意的一男一女，把所有稳定方案挑出来，再在稳定方案里选对男方
最有利的那一个返回。方案个数随人数阶乘增长，人数一多就跑不动。
"""
import itertools


class Erro(Exception):
    """本库所有异常的基类。"""


class InvalidInput(Erro):
    """输入不合法：名单与偏好表对不上，或者偏好里有不认识的人。"""


class UnstableMatching(Erro):
    """在现有口径下没能得到任何一个稳定配对。"""


def _pad(seq, universe, own):
    """把偏好序列补齐：给定次序在前，没提到的人按名字升序补在后面。"""
    tail = [x for x in sorted(universe) if x != own and x not in seq]
    return list(seq) + tail


def normalise(men, women, men_prefs, women_prefs):
    """校验输入并整理成统一形状，返回 (男, 女, 男偏好, 女偏好)。

    男偏好把每个男方姓名映射到他对女方的偏好次序，女偏好方向相反。两侧
    姓名都必须是非空字符串且互不重名，偏好表必须与对应一侧的姓名一一对应，
    偏好里不能出现自己或对面之外的人，同一个人不能重复出现。补齐规则：没
    在偏好里提到的对面成员，按名字升序排在后面。
    """
    men = _name_list(men, "男方")
    women = _name_list(women, "女方")
    if set(men) & set(women):
        raise InvalidInput("男女两侧不能有重名")
    mprefs = _clean_prefs(men_prefs, men, women, "男偏好")
    wprefs = _clean_prefs(women_prefs, women, men, "女偏好")
    padded_m = {}
    for m in men:
        padded_m[m] = _pad(mprefs[m], women, m)
    padded_w = {}
    for w in women:
        padded_w[w] = _pad(wprefs[w], men, w)
    return men, women, padded_m, padded_w


def _name_list(names, label):
    if names is None:
        raise InvalidInput(label + "名单不能为空")
    names = list(names)
    for one in names:
        if not isinstance(one, str) or not one:
            raise InvalidInput(label + "姓名必须是非空字符串")
    if len(set(names)) != len(names):
        raise InvalidInput(label + "名单里有重名")
    return names


def _clean_prefs(prefs, side, other_side, label):
    if not isinstance(prefs, dict):
        raise InvalidInput(label + "表必须是字典")
    for one in side:
        if one not in prefs:
            raise InvalidInput(label + "表里缺少 " + one)
    for key in prefs:
        if key not in side:
            raise InvalidInput(label + "表里有名单之外的人 " + str(key))
    cleaned = {}
    for one in side:
        seq = list(prefs[one])
        for other in seq:
            if not isinstance(other, str):
                raise InvalidInput(label + "里必须是字符串")
            if other == one:
                raise InvalidInput("谁也不能把自己列进偏好")
            if other not in other_side:
                raise InvalidInput(label + "里出现了 " + other)
            if seq.count(other) != 1:
                raise InvalidInput(label + "里不能重复列出同一个人")
        cleaned[one] = seq
    return cleaned


def _rank_table(prefs):
    """把偏好字典翻成名次表，名次越小越靠前。"""
    table = {}
    for who in prefs:
        table[who] = {other: i for i, other in enumerate(prefs[who])}
    return table


def _rank(table, who, target):
    """who 看 target 的名次，target 为 None 时名次当作最后。"""
    if target is None:
        return len(table[who]) + 1
    return table[who][target]


def instabilities(pairing, men_prefs, women_prefs):
    """列出配对方案里所有不稳定的一男一女，按 (男, 女) 成对返回。

    判别口径：这一男一女眼下没配在一起，但双方各自都把对方排在自己当前对象
    前面，于是两人都有动机绕开当前安排，这就是一个不稳定对。pairing 把每个
    人映射到对象或 None，两个偏好字典都应是补齐过的。
    """
    mtable = _rank_table(men_prefs)
    wtable = _rank_table(women_prefs)
    result = []
    for man in men_prefs:
        for woman in women_prefs:
            if pairing.get(man) == woman:
                continue
            wants = (mtable[man][woman] < _rank(mtable, man, pairing.get(man))
                     and wtable[woman][man] < _rank(wtable, woman, pairing.get(woman)))
            if wants:
                result.append((man, woman))
    return result


def first_unstable(pairing, men_prefs, women_prefs):
    """挑出第一个不稳定的一男一女，都稳定时返回 None。"""
    got = instabilities(pairing, men_prefs, women_prefs)
    if got:
        return got[0]
    return None


def enumerate_pairings(men, women):
    """穷举两侧之间的全部配对方案。

    人数不等时，把人数较少的一侧全部配对，多出来的那侧按名字升序留空。
    每条方案是一个字典，两侧所有人都映射到对象或 None。
    """
    out = []
    if len(men) <= len(women):
        for combo in itertools.permutations(women, len(men)):
            pairing = {}
            for m, w in zip(men, combo):
                pairing[m] = w
                pairing[w] = m
            for w in women:
                if w not in pairing:
                    pairing[w] = None
            out.append(pairing)
    else:
        for combo in itertools.permutations(men, len(women)):
            pairing = {}
            for w, m in zip(women, combo):
                pairing[w] = m
                pairing[m] = w
            for m in men:
                if m not in pairing:
                    pairing[m] = None
            out.append(pairing)
    return out


def _men_vector(pairing, men, safe_m):
    """把方案读成男方视角的名次向量，用于在多个稳定方案里比谁对男方更有利。"""
    return tuple(_rank(safe_m, m, pairing.get(m)) for m in men)


def all_stable(men, women, men_prefs, women_prefs):
    """把全部稳定方案找出来，按男方名次向量的升序返回。

    任一侧为空时没有可谈的方案，直接返回空列表。
    """
    if not men or not women:
        return []
    safe_m = _rank_table(men_prefs)
    stable = []
    for pairing in enumerate_pairings(men, women):
        if first_unstable(pairing, men_prefs, women_prefs) is None:
            stable.append(((_men_vector(pairing, men, safe_m)), pairing))
    stable.sort(key=lambda item: item[0])
    return [pairing for _, pairing in stable]


def stable_pairing(men, women, men_prefs, women_prefs):
    """给出一个稳定配对，返回把每个人映到对象或 None 的字典。

    当前实现穷举全部方案，挑出所有稳定方案，再选对男方最有利（逐个男方按
    偏好次序综合最优）的那一个返回。输入不合法抛 InvalidInput，一个稳定
    方案都没有时抛 UnstableMatching。
    """
    men, women, men_prefs, women_prefs = normalise(men, women, men_prefs, women_prefs)
    found = all_stable(men, women, men_prefs, women_prefs)
    if not found:
        raise UnstableMatching("没有找到稳定配对")
    return found[0]
