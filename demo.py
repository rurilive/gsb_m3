"""fftconv 现状演示。

第一段：拿几个小多项式，用双重循环的朴素路子做乘法、求值与由根构造；
第二段：预留的快速变换改造演示位子（见文末注释）。
"""

from fftconv.conv import (
    Poly,
    check_transform_length,
    convolve_naive,
    evaluate_many,
    from_roots,
)


def main():
    print("=== 朴素多项式乘法 ===")
    a = [1, 2, 3]
    b = [4, 5]
    print("  系数 %s 与 %s" % (a, b))
    print("  朴素卷积 %s" % convolve_naive(a, b))
    print("  结果长度 %d" % len(convolve_naive(a, b)))

    p = Poly([1, 1])
    q = Poly([1, -1])
    print("  平方展开 %s" % p.mul_naive(p).to_list())
    print("  差平方展开 %s" % q.mul_naive(q).to_list())

    print("  在零点的取值 %d" % Poly([7, 3, 1]).evaluate(0))
    print("  多点求值 %s" % evaluate_many([1, 2], [0, 1, 2, 3]))

    print("  根为 1 与 2 的多项式 %s" % from_roots([1, 2]).to_list())

    try:
        check_transform_length(6, 998244353)
    except Exception as exc:
        print("  长度六被拒 %s" % type(exc).__name__)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
