"""最朴素的等值连接实现。

NestedLoopJoin 对左右两表逐对比较连接键，键相等即输出一行配对。它不建哈希表、
不做排序归并、也不分块，内存占用随左右表规模的乘积增长，是哈希连接、排序归并
连接、分块落盘与多表连接改造前的基线实现。
"""


class NestedLoopJoin:
    """双重循环的等值连接器。

    连接键由两个函数分别从左右表的行里取出；比较只用相等关系，取出的键类型
    不限，只要可比较即可。返回的连接结果按外层左表、内层右表的顺序稳定排列。
    """

    def join(self, left, right, left_key, right_key=None):
        """返回左右两表所有等值配对的连接结果。

        参数 left、right 为行的可迭代对象（行本身可以是元组、字典等任意结构）。
        left_key 是从左表行取出连接键的函数；right_key 缺省时复用 left_key，
        即左右用同一种取键方式。返回列表，每个元素是 (左行, 右行) 二元组，
        顺序为外层遍历左表、内层遍历右表，不修改任何入参。
        """
        if right_key is None:
            right_key = left_key
        result = []
        for lrow in left:
            lkey = left_key(lrow)
            for rrow in right:
                if lkey == right_key(rrow):
                    result.append((lrow, rrow))
        return result

    def count(self, left, right, left_key, right_key=None):
        """返回等值配对的数量，等价于 join 结果的长度。"""
        return len(self.join(left, right, left_key, right_key))
