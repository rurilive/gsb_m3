"""命令栈演示。

第一段：一段文案的三次编辑，逐步 undo / redo。
第二段：undo 之后继续编辑，展示重做分支被截断。
第三段：事务——一组编辑整体提交或回滚。
第四段：插入合并——连打一串字母只占一条历史。
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

    print("\n=== 事务：一组编辑整体回退 ===")
    stack.begin()
    stack.execute(InsertText(doc, len(doc.text), "，先停旧集群"))
    stack.execute(InsertText(doc, len(doc.text), "，再切流量"))
    show("事务内", doc)
    stack.rollback()
    show("rollback", doc)
    stack.begin()
    stack.execute(InsertText(doc, len(doc.text), "，先扩容"))
    stack.execute(InsertText(doc, len(doc.text), "，再切换"))
    stack.commit()
    show("commit ", doc)
    stack.undo()
    show("undo 一步撤整批", doc)

    print("\n=== 合并：连打字母只占一条历史 ===")
    typed = Buffer("typed", "版本：")
    typing = EditStack(coalesce_window_ms=800)
    for ch in "v2.0":
        typing.execute(InsertText(typed, len(typed.text), ch))
    show("连打后", typed)
    typing.undo()
    show("undo 一步", typed)


if __name__ == "__main__":
    main()
