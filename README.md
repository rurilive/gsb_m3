# stanza

纯标准库的模板渲染小包，无外部依赖。

## 现状

stanza/render.py 提供最朴素的行内占位符替换器 Renderer：

- 构造时给定一个上下文字典，render 把模板里形如双大括号的行内占位符换成
  上下文里同名键的取值，缺键按空串处理，取值原样插入不做转义
- 便捷函数 render(template, context) 等价于一次性 Renderer(context).render()
- stanza/__init__.py 只导出 Renderer 与 render

没有条件，没有循环，没有模板继承与命名块，没有转义，也没有把模板编译成可
复用的语法树的能力，每次渲染都从头扫一遍文本。

## 目标（见任务描述）

把 stanza 从单一占位符替换扩成小模板语言：模板先编译成节点树（文本节点、
变量节点、条件节点、循环节点），编译结果可复用且与逐次直接渲染结果一致；
变量按作用域链查找并支持点路径取嵌套字段，缺失变量按明确策略处理；条件节点
按真假选择分支，循环节点对序列展开并支持循环内变量、嵌套循环作用域不串；
子模板可继承父模板并覆写命名块，多级继承按就近覆写生效；默认对插值做 HTML
转义且可显式关闭。全部仍在 stanza 里，纯标准库，边界情形 fail fast，异常继承
StanzaError 基类。约束：

- 现有行为与 tests/test_render.py 基线保持一致（基线一个字不改）
- 新行为另开 tests/test_template.py，用固定模板与上下文断言
- 纯标准库，不引第三方

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
