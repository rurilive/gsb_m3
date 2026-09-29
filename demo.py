"""sparsem 现状演示。

第一段：构造一个稀疏度很高的矩阵，读几个元素，看稠密存储的样子。
第二段：预留的稀疏改造演示位子（见文末注释）。
"""

from sparsem.matrix import DenseMatrix


def main():
    print("=== 稠密存储（现有能力） ===")
    n = 200
    grid = [[0] * n for _ in range(n)]   # 40000 个格子，绝大多数是零
    grid[0][0] = 1.5
    grid[0][199] = 2.5
    grid[199][0] = 3.5
    m = DenseMatrix(n, n, grid)
    print(f"  形状          -> {m.rows()} x {m.cols()}")
    print(f"  get(0, 0)     -> {m.get(0, 0)}")
    print(f"  get(0, 1)     -> {m.get(0, 1)}")
    print(f"  get(0, 199)   -> {m.get(0, 199)}")
    print(f"  get(199, 0)   -> {m.get(199, 0)}")
    print(f"  底层存了 {m.rows() * m.cols()} 个格子，"
          f"其中非零只有 3 个，其余全在内存里，零也照存")

    # TODO(稀疏存储改造): 稀疏实现落地后，在这里加一段演示：
    # 用坐标三元组构造一个稀疏矩阵（重复坐标相加合并、零元素不落存储），
    # 做一次稀疏加法或乘法，打印结果的非零个数，证明存储规模只跟非零元走，
    # 而不是跟行列总数走。


if __name__ == "__main__":
    main()
