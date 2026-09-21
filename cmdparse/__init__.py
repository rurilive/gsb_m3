"""cmdparse: 部署面板背后的命令流解析小包，纯标准库。"""

from cmdparse.diagnostics import ParseError, render_caret
from cmdparse.document import CommandDocument
from cmdparse.lexer import Position, Segment, Token, tokenize
from cmdparse.quote import quote_word
from cmdparse.report import summarize, word_frequency
from cmdparse.tokenizer import split_words

__all__ = [
    "CommandDocument",
    "ParseError",
    "Position",
    "Segment",
    "Token",
    "render_caret",
    "quote_word",
    "split_words",
    "summarize",
    "tokenize",
    "word_frequency",
]
