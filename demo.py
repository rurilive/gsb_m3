"""命令栈现状演示。

第一段：一段文案的三次编辑，逐步 undo / redo。
第二段：undo 之后继续编辑，展示重做分支被截断。
"""

from editstack.commands import Buffer, DeleteText, InsertText
from editstack.stack import EditStack


def show(tag, buf):
    print(f"  [{tag}] {buf.text}")


def main():
    doc = Buffer("doc", "部署清单：")
    stack = EditStack()

    print("=== 连续编辑 ===")
    stack.execute(InsertText(doc, 5, "重启服务"))
    show("插入", doc)
    stack.execute(InsertText(doc, 9, "，重启网关"))
    show("插入", doc)
    stack.execute(DeleteText(doc, 5, 4))
    show("删除", doc)

    print("\n=== 逐步撤销 / 重做 ===")
    stack.undo()
    show("undo 1", doc)
    stack.undo()
    show("undo 2", doc)
    stack.redo()
    show("redo  ", doc)

    print("\n=== undo 后新编辑截断重做分支 ===")
    stack.undo()
    show("undo  ", doc)
    print(f"  can_redo = {stack.can_redo}")
    stack.execute(InsertText(doc, len(doc.text), "（改走灰度）"))
    show("新编辑", doc)
    print(f"  新编辑后 can_redo = {stack.can_redo}（原重做分支已丢弃）")

    # TODO(事务与合并): 实现后在这里演示两件事：
    # 1) begin/rollback：一组编辑整体撤销，文本回到事务前的样子；
    # 2) coalesce_window_ms：连打一串字母只占一条历史，undo 一步撤掉整段。


if __name__ == "__main__":
    main()
