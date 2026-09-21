"""cmdparse: 部署面板背后的命令流解析小包，纯标准库。"""

from cmdparse.diagnostics import ParseError, render_caret
from cmdparse.document import CommandDocument
from cmdparse.lexer import Token, tokenize
from cmdparse.quote import quote_word
from cmdparse.report import summarize, word_frequency
from cmdparse.tokenizer import split_words

__all__ = [
    "CommandDocument",
    "ParseError",
    "Token",
    "quote_word",
    "render_caret",
    "split_words",
    "summarize",
    "tokenize",
    "word_frequency",
]
