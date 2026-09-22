"""定标整数的低位裁剪。

乘除落到目标精度时，多出来的低位在这里裁掉。现在只有一种裁法：
朝零截断，即丢掉低位不看，正负都往零的方向收。
"""


def div_trunc(num, den):
    """整数商 num / den，低位朝零截断。

    den 不能为零，其余不设限制。丢掉的那部分不留痕迹。
    """
    if den == 0:
        raise ZeroDivisionError("division by zero: num=%r" % (num,))
    return num // den
