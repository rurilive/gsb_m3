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

    print("\n=== 事务：一组编辑整体回退 ===")
    plan = Buffer("plan", "方案A")
    tx_stack = EditStack()
    tx_stack.begin()
    tx_stack.execute(InsertText(plan, 3, "（加缓存"))
    tx_stack.execute(InsertText(plan, len(plan.text), "，限流）"))
    show("事务内", plan)
    tx_stack.rollback()
    show("rollback", plan)
    tx_stack.begin()
    tx_stack.execute(InsertText(plan, 3, "（先灰度）"))
    tx_stack.commit()
    show("commit ", plan)
    tx_stack.undo()
    show("undo 一步撤整批", plan)

    print("\n=== 合并：连打一串字母只占一条历史 ===")
    msg = Buffer("msg", "")
    typing = EditStack(coalesce_window_ms=500)
    for ch in "hello":
        typing.execute(InsertText(msg, len(msg.text), ch))
    show("连打", msg)
    typing.undo()
    show("undo 一步", msg)


if __name__ == "__main__":
    main()
